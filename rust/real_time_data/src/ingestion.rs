//! Data ingestion layer - accepts data from multiple sources and protocols.

use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, SystemTime};

use dashmap::DashMap;
use tokio::sync::{broadcast, mpsc, RwLock};
use tracing::{debug, error, info, warn};

use crate::{DataPayload, DataRecord, DataSource, PipelineConfig, PipelineError, Result};

/// Ingestion engine that manages multiple data source connections.
pub struct IngestionEngine {
    /// Active source connections
    sources: Arc<DashMap<String, SourceConnection>>,

    /// Output channel for ingested records
    output_tx: mpsc::Sender<DataRecord>,

    /// Configuration
    config: Arc<PipelineConfig>,

    /// Metrics
    metrics: Arc<RwLock<IngestionMetrics>>,

    /// Rate limiters per source
    rate_limiters: Arc<DashMap<String, RateLimiter>>,

    /// Running flag
    running: Arc<RwLock<bool>>,
}

/// A connection to a data source.
struct SourceConnection {
    source: DataSource,
    status: ConnectionStatus,
    records_received: u64,
    last_record_time: Option<SystemTime>,
    error_count: u64,
    created_at: SystemTime,
}

/// Status of a source connection.
#[derive(Debug, Clone, PartialEq)]
pub enum ConnectionStatus {
    Connected,
    Connecting,
    Disconnected,
    Error(String),
    RateLimited,
}

/// Rate limiter for data sources.
struct RateLimiter {
    max_per_second: u64,
    current_count: u64,
    window_start: SystemTime,
}

/// Ingestion-specific metrics.
#[derive(Debug, Clone, Default)]
pub struct IngestionMetrics {
    pub total_records: u64,
    pub records_per_source: HashMap<String, u64>,
    pub bytes_ingested: u64,
    pub dropped_records: u64,
    pub active_sources: u32,
    pub avg_ingestion_rate: f64,
}

impl IngestionEngine {
    /// Create a new ingestion engine.
    pub fn new(config: Arc<PipelineConfig>, output_tx: mpsc::Sender<DataRecord>) -> Self {
        Self {
            sources: Arc::new(DashMap::new()),
            output_tx,
            config,
            metrics: Arc::new(RwLock::new(IngestionMetrics::default())),
            rate_limiters: Arc::new(DashMap::new()),
            running: Arc::new(RwLock::new(false)),
        }
    }

    /// Start the ingestion engine.
    pub async fn start(&self) -> Result<()> {
        let mut running = self.running.write().await;
        *running = true;
        info!("Ingestion engine started");
        Ok(())
    }

    /// Stop the ingestion engine.
    pub async fn stop(&self) -> Result<()> {
        let mut running = self.running.write().await;
        *running = false;
        info!("Ingestion engine stopped");
        Ok(())
    }

    /// Register a new data source.
    pub async fn register_source(
        &self,
        source_id: &str,
        source: DataSource,
        max_rate: u64,
    ) -> Result<()> {
        let connection = SourceConnection {
            source,
            status: ConnectionStatus::Connecting,
            records_received: 0,
            last_record_time: None,
            error_count: 0,
            created_at: SystemTime::now(),
        };

        self.sources.insert(source_id.to_string(), connection);

        // Set up rate limiter
        self.rate_limiters.insert(
            source_id.to_string(),
            RateLimiter {
                max_per_second: max_rate,
                current_count: 0,
                window_start: SystemTime::now(),
            },
        );

        info!("Registered data source: {}", source_id);
        Ok(())
    }

    /// Ingest a single record from a source.
    pub async fn ingest(&self, source_id: &str, payload: DataPayload, priority: u8) -> Result<()> {
        // Check if running
        if !*self.running.read().await {
            return Err(PipelineError::Ingestion("Engine not running".to_string()));
        }

        // Check rate limit
        if !self.check_rate_limit(source_id) {
            return Err(PipelineError::Ingestion("Rate limited".to_string()));
        }

        // Get source info
        let source = match self.sources.get(source_id) {
            Some(conn) => conn.source.clone(),
            None => {
                return Err(PipelineError::Ingestion(format!(
                    "Unknown source: {}",
                    source_id
                )))
            }
        };

        // Create record
        let record = DataRecord::new(source, payload, priority);
        let record_size = record.size_bytes();

        // Send to pipeline
        match self.output_tx.try_send(record) {
            Ok(_) => {
                // Update metrics
                self.update_metrics(source_id, record_size).await;
                Ok(())
            }
            Err(mpsc::error::TrySendError::Full(_)) => {
                // Backpressure
                if self.config.backpressure_enabled {
                    warn!("Pipeline queue full, applying backpressure for source {}", source_id);
                    let mut metrics = self.metrics.write().await;
                    metrics.dropped_records += 1;
                }
                Err(PipelineError::CapacityExceeded(
                    "Pipeline queue full".to_string(),
                ))
            }
            Err(_) => Err(PipelineError::Ingestion("Pipeline closed".to_string())),
        }
    }

    /// Batch ingest multiple records.
    pub async fn ingest_batch(
        &self,
        source_id: &str,
        records: Vec<(DataPayload, u8)>,
    ) -> Result<usize> {
        let mut ingested = 0;

        for (payload, priority) in records {
            match self.ingest(source_id, payload, priority).await {
                Ok(_) => ingested += 1,
                Err(PipelineError::CapacityExceeded(_)) => break,
                Err(e) => {
                    error!("Batch ingestion error: {}", e);
                    continue;
                }
            }
        }

        Ok(ingested)
    }

    /// Get current metrics.
    pub async fn get_metrics(&self) -> IngestionMetrics {
        self.metrics.read().await.clone()
    }

    /// Get status of all sources.
    pub fn get_source_statuses(&self) -> HashMap<String, ConnectionStatus> {
        let mut statuses = HashMap::new();
        for entry in self.sources.iter() {
            statuses.insert(entry.key().clone(), entry.value().status.clone());
        }
        statuses
    }

    // ─────────────────────── Private Methods ───────────────────────

    fn check_rate_limit(&self, source_id: &str) -> bool {
        if let Some(mut limiter) = self.rate_limiters.get_mut(source_id) {
            let now = SystemTime::now();
            let elapsed = now
                .duration_since(limiter.window_start)
                .unwrap_or(Duration::from_secs(0));

            // Reset window if more than 1 second has passed
            if elapsed >= Duration::from_secs(1) {
                limiter.current_count = 0;
                limiter.window_start = now;
            }

            if limiter.current_count >= limiter.max_per_second {
                return false;
            }

            limiter.current_count += 1;
            true
        } else {
            true // No limiter = no limit
        }
    }

    async fn update_metrics(&self, source_id: &str, bytes: usize) {
        let mut metrics = self.metrics.write().await;
        metrics.total_records += 1;
        metrics.bytes_ingested += bytes as u64;

        *metrics
            .records_per_source
            .entry(source_id.to_string())
            .or_insert(0) += 1;

        // Update source connection
        if let Some(mut conn) = self.sources.get_mut(source_id) {
            conn.records_received += 1;
            conn.last_record_time = Some(SystemTime::now());
            conn.status = ConnectionStatus::Connected;
        }
    }
}
