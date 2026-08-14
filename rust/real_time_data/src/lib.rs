//! # Ultron Real-Time Data Processing Pipeline
//!
//! High-performance, low-latency data ingestion and processing system.
//! Handles continuous streams of real-time data from multiple sources,
//! processes them through configurable pipelines, and feeds results
//! to the neural architecture and meta-learning systems.
//!
//! ## Architecture
//! - Ingestion Layer: Accepts data from multiple protocols/sources
//! - Processing Layer: Transforms, filters, and enriches data
//! - Distribution Layer: Routes processed data to consumers
//! - Storage Layer: Time-series storage with configurable retention

pub mod ingestion;
pub mod pipeline;
pub mod processor;
pub mod stream;

use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime};

use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use thiserror::Error;
use uuid::Uuid;

/// Errors that can occur in the data pipeline.
#[derive(Error, Debug)]
pub enum PipelineError {
    #[error("Ingestion error: {0}")]
    Ingestion(String),

    #[error("Processing error: {0}")]
    Processing(String),

    #[error("Pipeline configuration error: {0}")]
    Configuration(String),

    #[error("Stream error: {0}")]
    Stream(String),

    #[error("Capacity exceeded: {0}")]
    CapacityExceeded(String),

    #[error("Timeout: {0}")]
    Timeout(String),
}

pub type Result<T> = std::result::Result<T, PipelineError>;

/// A single data record flowing through the pipeline.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DataRecord {
    /// Unique record identifier
    pub id: String,

    /// Source of the data
    pub source: DataSource,

    /// Timestamp when data was generated
    pub timestamp: SystemTime,

    /// Timestamp when data entered the pipeline
    pub ingestion_time: SystemTime,

    /// The actual data payload
    pub payload: DataPayload,

    /// Processing metadata
    pub metadata: HashMap<String, String>,

    /// Processing stage tracking
    pub processing_stages: Vec<ProcessingStage>,

    /// Priority (higher = more important)
    pub priority: u8,
}

/// Sources of real-time data.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum DataSource {
    /// Social media streams
    SocialMedia { platform: String, stream_type: String },

    /// Financial market data
    Financial { exchange: String, instrument: String },

    /// News feeds
    News { provider: String, category: String },

    /// Sensor/IoT data
    Sensor { device_id: String, sensor_type: String },

    /// Network traffic analysis
    Network { interface: String, protocol: String },

    /// API endpoint data
    Api { endpoint: String, method: String },

    /// Internal system metrics
    SystemMetrics { component: String },

    /// Custom source
    Custom { source_type: String, identifier: String },
}

/// The actual data payload.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum DataPayload {
    /// Text data (tweets, articles, messages)
    Text(TextPayload),

    /// Numeric data (prices, metrics, sensor readings)
    Numeric(NumericPayload),

    /// Structured data (JSON objects, events)
    Structured(serde_json::Value),

    /// Binary data (images, audio, compressed)
    Binary(Vec<u8>),

    /// Time series data points
    TimeSeries(Vec<TimeSeriesPoint>),
}

/// Text-based payload.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TextPayload {
    pub content: String,
    pub language: Option<String>,
    pub sentiment: Option<f64>,
    pub entities: Vec<String>,
    pub keywords: Vec<String>,
}

/// Numeric payload.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NumericPayload {
    pub value: f64,
    pub unit: Option<String>,
    pub min: Option<f64>,
    pub max: Option<f64>,
    pub moving_average: Option<f64>,
}

/// A single time series data point.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimeSeriesPoint {
    pub timestamp: SystemTime,
    pub value: f64,
    pub labels: HashMap<String, String>,
}

/// Tracks processing through pipeline stages.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessingStage {
    pub stage_name: String,
    pub started_at: SystemTime,
    pub completed_at: Option<SystemTime>,
    pub status: StageStatus,
    pub output_metadata: HashMap<String, String>,
}

/// Status of a processing stage.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum StageStatus {
    Pending,
    Processing,
    Completed,
    Failed(String),
    Skipped,
}

/// Pipeline metrics for monitoring.
#[derive(Debug, Clone, Default)]
pub struct PipelineMetrics {
    pub records_ingested: u64,
    pub records_processed: u64,
    pub records_failed: u64,
    pub records_dropped: u64,
    pub bytes_processed: u64,
    pub avg_latency_ms: f64,
    pub max_latency_ms: f64,
    pub throughput_per_sec: f64,
    pub active_streams: u32,
    pub queue_depth: u32,
    pub last_updated: Option<Instant>,
}

/// Configuration for the data pipeline.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PipelineConfig {
    /// Maximum records in the processing queue
    pub max_queue_size: usize,

    /// Number of worker threads
    pub worker_threads: usize,

    /// Maximum processing latency before dropping
    pub max_latency: Duration,

    /// Batch size for batch processing
    pub batch_size: usize,

    /// How often to flush metrics
    pub metrics_interval: Duration,

    /// Enable backpressure handling
    pub backpressure_enabled: bool,

    /// Data retention duration
    pub retention_period: Duration,

    /// Priority processing enabled
    pub priority_processing: bool,
}

impl Default for PipelineConfig {
    fn default() -> Self {
        Self {
            max_queue_size: 100_000,
            worker_threads: 4,
            max_latency: Duration::from_millis(100),
            batch_size: 1000,
            metrics_interval: Duration::from_secs(10),
            backpressure_enabled: true,
            retention_period: Duration::from_secs(3600), // 1 hour
            priority_processing: true,
        }
    }
}

impl DataRecord {
    /// Create a new data record.
    pub fn new(source: DataSource, payload: DataPayload, priority: u8) -> Self {
        let now = SystemTime::now();
        Self {
            id: Uuid::new_v4().to_string(),
            source,
            timestamp: now,
            ingestion_time: now,
            payload,
            metadata: HashMap::new(),
            processing_stages: Vec::new(),
            priority,
        }
    }

    /// Add a processing stage.
    pub fn add_stage(&mut self, stage_name: &str) {
        self.processing_stages.push(ProcessingStage {
            stage_name: stage_name.to_string(),
            started_at: SystemTime::now(),
            completed_at: None,
            status: StageStatus::Processing,
            output_metadata: HashMap::new(),
        });
    }

    /// Complete the current processing stage.
    pub fn complete_stage(&mut self) {
        if let Some(stage) = self.processing_stages.last_mut() {
            stage.completed_at = Some(SystemTime::now());
            stage.status = StageStatus::Completed;
        }
    }

    /// Calculate end-to-end latency.
    pub fn latency(&self) -> Duration {
        self.ingestion_time
            .elapsed()
            .unwrap_or(Duration::from_secs(0))
    }

    /// Get payload size in bytes (approximate).
    pub fn size_bytes(&self) -> usize {
        match &self.payload {
            DataPayload::Text(t) => t.content.len(),
            DataPayload::Numeric(_) => 8,
            DataPayload::Structured(v) => v.to_string().len(),
            DataPayload::Binary(b) => b.len(),
            DataPayload::TimeSeries(ts) => ts.len() * 16,
        }
    }
}
