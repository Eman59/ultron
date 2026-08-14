//! Pipeline orchestration - manages data flow through processing stages.

use std::collections::VecDeque;
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime};

use dashmap::DashMap;
use tokio::sync::{mpsc, RwLock, Semaphore};
use tracing::{debug, error, info, warn};

use crate::processor::Processor;
use crate::{
    DataRecord, PipelineConfig, PipelineError, PipelineMetrics, ProcessingStage, Result,
    StageStatus,
};

/// The main data processing pipeline.
pub struct Pipeline {
    /// Pipeline configuration
    config: Arc<PipelineConfig>,

    /// Ordered list of processing stages
    stages: Arc<RwLock<Vec<PipelineStage>>>,

    /// Input channel
    input_rx: Arc<RwLock<mpsc::Receiver<DataRecord>>>,

    /// Output channels (fan-out to consumers)
    output_txs: Arc<RwLock<Vec<mpsc::Sender<DataRecord>>>>,

    /// Dead letter queue (failed records)
    dead_letter_queue: Arc<RwLock<VecDeque<(DataRecord, String)>>>,

    /// Pipeline metrics
    metrics: Arc<RwLock<PipelineMetrics>>,

    /// Concurrency limiter
    semaphore: Arc<Semaphore>,

    /// Running state
    running: Arc<RwLock<bool>>,
}

/// A single stage in the processing pipeline.
pub struct PipelineStage {
    /// Stage name
    pub name: String,

    /// The processor for this stage
    pub processor: Box<dyn Processor + Send + Sync>,

    /// Whether this stage is required (failure = record dropped)
    pub required: bool,

    /// Maximum processing time for this stage
    pub timeout: Duration,

    /// Stage metrics
    pub records_processed: u64,
    pub records_failed: u64,
    pub avg_processing_time: Duration,
}

/// Pipeline builder for fluent configuration.
pub struct PipelineBuilder {
    config: PipelineConfig,
    stages: Vec<PipelineStage>,
}

impl PipelineBuilder {
    /// Create a new pipeline builder.
    pub fn new() -> Self {
        Self {
            config: PipelineConfig::default(),
            stages: Vec::new(),
        }
    }

    /// Set pipeline configuration.
    pub fn with_config(mut self, config: PipelineConfig) -> Self {
        self.config = config;
        self
    }

    /// Add a processing stage.
    pub fn add_stage(
        mut self,
        name: &str,
        processor: Box<dyn Processor + Send + Sync>,
        required: bool,
    ) -> Self {
        self.stages.push(PipelineStage {
            name: name.to_string(),
            processor,
            required,
            timeout: Duration::from_millis(50),
            records_processed: 0,
            records_failed: 0,
            avg_processing_time: Duration::from_secs(0),
        });
        self
    }

    /// Build the pipeline.
    pub fn build(self, input_rx: mpsc::Receiver<DataRecord>) -> Pipeline {
        let config = Arc::new(self.config.clone());
        Pipeline {
            config: config.clone(),
            stages: Arc::new(RwLock::new(self.stages)),
            input_rx: Arc::new(RwLock::new(input_rx)),
            output_txs: Arc::new(RwLock::new(Vec::new())),
            dead_letter_queue: Arc::new(RwLock::new(VecDeque::new())),
            metrics: Arc::new(RwLock::new(PipelineMetrics::default())),
            semaphore: Arc::new(Semaphore::new(self.config.worker_threads)),
            running: Arc::new(RwLock::new(false)),
        }
    }
}

impl Pipeline {
    /// Start the pipeline processing loop.
    pub async fn start(&self) -> Result<()> {
        *self.running.write().await = true;
        info!("Pipeline started with {} worker threads", self.config.worker_threads);

        // Start the processing loop
        let running = self.running.clone();
        let input_rx = self.input_rx.clone();
        let stages = self.stages.clone();
        let output_txs = self.output_txs.clone();
        let dead_letter = self.dead_letter_queue.clone();
        let metrics = self.metrics.clone();
        let semaphore = self.semaphore.clone();
        let config = self.config.clone();

        tokio::spawn(async move {
            loop {
                if !*running.read().await {
                    break;
                }

                let mut rx = input_rx.write().await;
                match rx.recv().await {
                    Some(record) => {
                        // Acquire semaphore permit for concurrency control
                        let permit = semaphore.clone().acquire_owned().await;
                        if permit.is_err() {
                            continue;
                        }

                        let stages = stages.clone();
                        let output_txs = output_txs.clone();
                        let dead_letter = dead_letter.clone();
                        let metrics = metrics.clone();
                        let config = config.clone();

                        // Process record in a spawned task
                        tokio::spawn(async move {
                            let start = Instant::now();
                            let result = Self::process_record(
                                record,
                                &stages,
                                &output_txs,
                                &dead_letter,
                                &config,
                            )
                            .await;

                            // Update metrics
                            let elapsed = start.elapsed();
                            let mut m = metrics.write().await;
                            match result {
                                Ok(_) => {
                                    m.records_processed += 1;
                                    m.avg_latency_ms = (m.avg_latency_ms
                                        * (m.records_processed - 1) as f64
                                        + elapsed.as_millis() as f64)
                                        / m.records_processed as f64;
                                    if elapsed.as_millis() as f64 > m.max_latency_ms {
                                        m.max_latency_ms = elapsed.as_millis() as f64;
                                    }
                                }
                                Err(_) => {
                                    m.records_failed += 1;
                                }
                            }
                            m.last_updated = Some(Instant::now());

                            drop(permit);
                        });
                    }
                    None => {
                        // Channel closed
                        break;
                    }
                }
            }
        });

        Ok(())
    }

    /// Stop the pipeline.
    pub async fn stop(&self) -> Result<()> {
        *self.running.write().await = false;
        info!("Pipeline stopped");
        Ok(())
    }

    /// Subscribe to pipeline output.
    pub async fn subscribe(&self) -> mpsc::Receiver<DataRecord> {
        let (tx, rx) = mpsc::channel(self.config.max_queue_size);
        self.output_txs.write().await.push(tx);
        rx
    }

    /// Get current pipeline metrics.
    pub async fn get_metrics(&self) -> PipelineMetrics {
        self.metrics.read().await.clone()
    }

    /// Get dead letter queue contents.
    pub async fn get_dead_letters(&self, limit: usize) -> Vec<(DataRecord, String)> {
        let dlq = self.dead_letter_queue.read().await;
        dlq.iter().take(limit).cloned().collect()
    }

    /// Process a single record through all stages.
    async fn process_record(
        mut record: DataRecord,
        stages: &RwLock<Vec<PipelineStage>>,
        output_txs: &RwLock<Vec<mpsc::Sender<DataRecord>>>,
        dead_letter: &RwLock<VecDeque<(DataRecord, String)>>,
        config: &PipelineConfig,
    ) -> Result<()> {
        let mut stages = stages.write().await;

        for stage in stages.iter_mut() {
            // Add processing stage to record
            record.add_stage(&stage.name);

            // Process with timeout
            let start = Instant::now();
            let result = tokio::time::timeout(stage.timeout, stage.processor.process(&mut record))
                .await;

            let elapsed = start.elapsed();

            match result {
                Ok(Ok(())) => {
                    // Success
                    record.complete_stage();
                    stage.records_processed += 1;
                    stage.avg_processing_time = Duration::from_nanos(
                        ((stage.avg_processing_time.as_nanos() as u64
                            * (stage.records_processed - 1)
                            + elapsed.as_nanos() as u64)
                            / stage.records_processed) as u64,
                    );
                }
                Ok(Err(e)) => {
                    // Processing error
                    stage.records_failed += 1;

                    if stage.required {
                        // Required stage failed - send to dead letter queue
                        let mut dlq = dead_letter.write().await;
                        dlq.push_back((record.clone(), format!("Stage '{}': {}", stage.name, e)));

                        // Trim DLQ
                        while dlq.len() > 10000 {
                            dlq.pop_front();
                        }

                        return Err(PipelineError::Processing(format!(
                            "Required stage '{}' failed: {}",
                            stage.name, e
                        )));
                    }

                    // Optional stage failed - mark as skipped and continue
                    if let Some(ps) = record.processing_stages.last_mut() {
                        ps.status = StageStatus::Failed(e.to_string());
                    }
                    warn!("Optional stage '{}' failed: {}", stage.name, e);
                }
                Err(_) => {
                    // Timeout
                    stage.records_failed += 1;

                    if stage.required {
                        let mut dlq = dead_letter.write().await;
                        dlq.push_back((
                            record.clone(),
                            format!("Stage '{}' timed out", stage.name),
                        ));
                        return Err(PipelineError::Timeout(format!(
                            "Stage '{}' exceeded {:?}",
                            stage.name, stage.timeout
                        )));
                    }

                    if let Some(ps) = record.processing_stages.last_mut() {
                        ps.status = StageStatus::Failed("Timeout".to_string());
                    }
                }
            }
        }

        // Check latency constraint
        if config.max_latency > Duration::from_secs(0) && record.latency() > config.max_latency {
            return Err(PipelineError::Timeout(format!(
                "End-to-end latency {:?} exceeded max {:?}",
                record.latency(),
                config.max_latency
            )));
        }

        // Distribute to all subscribers
        let txs = output_txs.read().await;
        for tx in txs.iter() {
            let _ = tx.try_send(record.clone());
        }

        Ok(())
    }
}
