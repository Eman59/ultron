//! Stream management - handles real-time data streams with backpressure,
//! windowing, and stream composition.

use std::collections::VecDeque;
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime};

use tokio::sync::{mpsc, RwLock};
use tracing::{debug, info, warn};

use crate::{DataRecord, PipelineError, Result};

/// A managed real-time data stream with windowing and aggregation.
pub struct DataStream {
    /// Stream identifier
    id: String,

    /// Stream configuration
    config: StreamConfig,

    /// Sliding window buffer
    window: Arc<RwLock<SlidingWindow>>,

    /// Stream metrics
    metrics: Arc<RwLock<StreamMetrics>>,

    /// Active state
    active: Arc<RwLock<bool>>,
}

/// Configuration for a data stream.
#[derive(Debug, Clone)]
pub struct StreamConfig {
    /// Window type
    pub window_type: WindowType,

    /// Window size (duration or count)
    pub window_size: WindowSize,

    /// Slide interval (for sliding windows)
    pub slide_interval: Option<Duration>,

    /// Maximum buffer size
    pub max_buffer_size: usize,

    /// Enable deduplication
    pub dedup_enabled: bool,

    /// Backpressure strategy
    pub backpressure: BackpressureStrategy,
}

/// Types of windowing.
#[derive(Debug, Clone)]
pub enum WindowType {
    /// Fixed-size tumbling windows
    Tumbling,
    /// Sliding windows with overlap
    Sliding,
    /// Session windows (gap-based)
    Session { gap: Duration },
    /// Global window (unbounded)
    Global,
}

/// Window size specification.
#[derive(Debug, Clone)]
pub enum WindowSize {
    /// Time-based window
    Duration(Duration),
    /// Count-based window
    Count(usize),
}

/// Backpressure handling strategies.
#[derive(Debug, Clone)]
pub enum BackpressureStrategy {
    /// Drop oldest records when full
    DropOldest,
    /// Drop newest records when full
    DropNewest,
    /// Block until space available
    Block,
    /// Sample at a rate
    Sample(f64),
}

/// A sliding window over data records.
struct SlidingWindow {
    records: VecDeque<DataRecord>,
    max_size: usize,
    window_start: Instant,
    window_duration: Duration,
}

/// Metrics for a data stream.
#[derive(Debug, Clone, Default)]
pub struct StreamMetrics {
    pub records_received: u64,
    pub records_emitted: u64,
    pub records_dropped: u64,
    pub windows_completed: u64,
    pub current_window_size: usize,
    pub avg_throughput: f64,
    pub backpressure_events: u64,
}

/// Result of a window aggregation.
#[derive(Debug, Clone)]
pub struct WindowResult {
    pub window_start: SystemTime,
    pub window_end: SystemTime,
    pub record_count: usize,
    pub aggregations: WindowAggregations,
}

/// Aggregated values from a window.
#[derive(Debug, Clone)]
pub struct WindowAggregations {
    pub count: u64,
    pub sum: f64,
    pub mean: f64,
    pub min: f64,
    pub max: f64,
    pub variance: f64,
    pub p50: f64,
    pub p95: f64,
    pub p99: f64,
}

impl Default for StreamConfig {
    fn default() -> Self {
        Self {
            window_type: WindowType::Sliding,
            window_size: WindowSize::Duration(Duration::from_secs(60)),
            slide_interval: Some(Duration::from_secs(10)),
            max_buffer_size: 10_000,
            dedup_enabled: false,
            backpressure: BackpressureStrategy::DropOldest,
        }
    }
}

impl DataStream {
    /// Create a new data stream.
    pub fn new(id: &str, config: StreamConfig) -> Self {
        let window_duration = match &config.window_size {
            WindowSize::Duration(d) => *d,
            WindowSize::Count(_) => Duration::from_secs(3600), // Use large duration for count-based
        };

        Self {
            id: id.to_string(),
            config: config.clone(),
            window: Arc::new(RwLock::new(SlidingWindow {
                records: VecDeque::new(),
                max_size: config.max_buffer_size,
                window_start: Instant::now(),
                window_duration,
            })),
            metrics: Arc::new(RwLock::new(StreamMetrics::default())),
            active: Arc::new(RwLock::new(true)),
        }
    }

    /// Push a record into the stream.
    pub async fn push(&self, record: DataRecord) -> Result<()> {
        if !*self.active.read().await {
            return Err(PipelineError::Stream("Stream is inactive".to_string()));
        }

        let mut window = self.window.write().await;
        let mut metrics = self.metrics.write().await;

        metrics.records_received += 1;

        // Check capacity and apply backpressure
        if window.records.len() >= window.max_size {
            match &self.config.backpressure {
                BackpressureStrategy::DropOldest => {
                    window.records.pop_front();
                    metrics.records_dropped += 1;
                }
                BackpressureStrategy::DropNewest => {
                    metrics.records_dropped += 1;
                    metrics.backpressure_events += 1;
                    return Ok(()); // Drop this record
                }
                BackpressureStrategy::Sample(rate) => {
                    // Probabilistic sampling
                    if rand_float() > *rate {
                        metrics.records_dropped += 1;
                        return Ok(());
                    }
                }
                BackpressureStrategy::Block => {
                    // In real implementation, would block until space available
                    metrics.backpressure_events += 1;
                    return Err(PipelineError::CapacityExceeded(
                        "Stream buffer full".to_string(),
                    ));
                }
            }
        }

        // Deduplication check
        if self.config.dedup_enabled {
            let exists = window.records.iter().any(|r| r.id == record.id);
            if exists {
                return Ok(()); // Skip duplicate
            }
        }

        window.records.push_back(record);
        metrics.current_window_size = window.records.len();

        Ok(())
    }

    /// Get the current window contents.
    pub async fn get_window(&self) -> Vec<DataRecord> {
        let window = self.window.read().await;
        window.records.iter().cloned().collect()
    }

    /// Compute aggregations over the current window.
    pub async fn aggregate(&self) -> WindowResult {
        let window = self.window.read().await;
        let mut metrics = self.metrics.write().await;

        let values: Vec<f64> = window
            .records
            .iter()
            .map(|r| match &r.payload {
                crate::DataPayload::Numeric(n) => n.value,
                _ => 0.0,
            })
            .collect();

        let aggregations = if values.is_empty() {
            WindowAggregations {
                count: 0,
                sum: 0.0,
                mean: 0.0,
                min: 0.0,
                max: 0.0,
                variance: 0.0,
                p50: 0.0,
                p95: 0.0,
                p99: 0.0,
            }
        } else {
            let count = values.len() as u64;
            let sum: f64 = values.iter().sum();
            let mean = sum / count as f64;
            let min = values.iter().cloned().fold(f64::INFINITY, f64::min);
            let max = values.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
            let variance = values.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / count as f64;

            let mut sorted = values.clone();
            sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));

            let p50 = percentile(&sorted, 50.0);
            let p95 = percentile(&sorted, 95.0);
            let p99 = percentile(&sorted, 99.0);

            WindowAggregations {
                count,
                sum,
                mean,
                min,
                max,
                variance,
                p50,
                p95,
                p99,
            }
        };

        metrics.windows_completed += 1;

        WindowResult {
            window_start: SystemTime::now(),
            window_end: SystemTime::now(),
            record_count: window.records.len(),
            aggregations,
        }
    }

    /// Flush the window (emit and clear).
    pub async fn flush(&self) -> Vec<DataRecord> {
        let mut window = self.window.write().await;
        let mut metrics = self.metrics.write().await;

        let records: Vec<DataRecord> = window.records.drain(..).collect();
        metrics.records_emitted += records.len() as u64;
        metrics.windows_completed += 1;
        metrics.current_window_size = 0;

        window.window_start = Instant::now();

        records
    }

    /// Get stream metrics.
    pub async fn get_metrics(&self) -> StreamMetrics {
        self.metrics.read().await.clone()
    }

    /// Get stream ID.
    pub fn id(&self) -> &str {
        &self.id
    }

    /// Stop the stream.
    pub async fn stop(&self) {
        *self.active.write().await = false;
    }
}

/// Compose multiple streams into one.
pub struct StreamComposer {
    streams: Vec<Arc<DataStream>>,
    merge_strategy: MergeStrategy,
}

/// Strategy for merging multiple streams.
#[derive(Debug, Clone)]
pub enum MergeStrategy {
    /// Round-robin between streams
    RoundRobin,
    /// Priority-based (higher priority first)
    Priority,
    /// Time-ordered (oldest first)
    TimeOrdered,
    /// All streams simultaneously
    Parallel,
}

impl StreamComposer {
    pub fn new(merge_strategy: MergeStrategy) -> Self {
        Self {
            streams: Vec::new(),
            merge_strategy,
        }
    }

    pub fn add_stream(&mut self, stream: Arc<DataStream>) {
        self.streams.push(stream);
    }

    /// Get the next record from composed streams.
    pub async fn next(&self) -> Option<DataRecord> {
        match &self.merge_strategy {
            MergeStrategy::Priority => {
                // Get highest priority record across all streams
                let mut best: Option<DataRecord> = None;
                for stream in &self.streams {
                    let window = stream.get_window().await;
                    if let Some(record) = window.first() {
                        if best.as_ref().map_or(true, |b| record.priority > b.priority) {
                            best = Some(record.clone());
                        }
                    }
                }
                best
            }
            MergeStrategy::TimeOrdered => {
                // Get oldest record
                let mut oldest: Option<DataRecord> = None;
                for stream in &self.streams {
                    let window = stream.get_window().await;
                    if let Some(record) = window.first() {
                        if oldest.as_ref().map_or(true, |o| record.timestamp < o.timestamp) {
                            oldest = Some(record.clone());
                        }
                    }
                }
                oldest
            }
            _ => {
                // RoundRobin / Parallel - just get from first non-empty
                for stream in &self.streams {
                    let window = stream.get_window().await;
                    if let Some(record) = window.first() {
                        return Some(record.clone());
                    }
                }
                None
            }
        }
    }
}

// ─────────────────────── Helpers ───────────────────────

fn percentile(sorted: &[f64], p: f64) -> f64 {
    if sorted.is_empty() {
        return 0.0;
    }

    let idx = (p / 100.0 * (sorted.len() - 1) as f64).round() as usize;
    sorted[idx.min(sorted.len() - 1)]
}

fn rand_float() -> f64 {
    // Simple pseudo-random using system time
    let nanos = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .unwrap_or_default()
        .subsec_nanos();
    (nanos % 1000) as f64 / 1000.0
}
