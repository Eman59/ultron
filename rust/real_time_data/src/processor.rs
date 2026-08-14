//! Processing modules - transform, filter, enrich, and analyze data records.

use std::collections::HashMap;
use std::time::SystemTime;

use async_trait::async_trait;
use serde_json;

use crate::{DataPayload, DataRecord, NumericPayload, PipelineError, Result, TextPayload};

/// Trait for data processors that transform records.
#[async_trait]
pub trait Processor: Send + Sync {
    /// Process a single data record in-place.
    async fn process(&self, record: &mut DataRecord) -> Result<()>;

    /// Get processor name.
    fn name(&self) -> &str;

    /// Check if this processor can handle the given record.
    fn can_process(&self, record: &DataRecord) -> bool {
        true
    }
}

// ─────────────────────── Built-in Processors ───────────────────────

/// Filter processor - drops records that don't match criteria.
pub struct FilterProcessor {
    name: String,
    /// Filter function returns true to keep, false to drop
    filter_fn: Box<dyn Fn(&DataRecord) -> bool + Send + Sync>,
}

impl FilterProcessor {
    pub fn new(name: &str, filter_fn: impl Fn(&DataRecord) -> bool + Send + Sync + 'static) -> Self {
        Self {
            name: name.to_string(),
            filter_fn: Box::new(filter_fn),
        }
    }

    /// Create a priority filter (only pass records above threshold).
    pub fn priority_filter(min_priority: u8) -> Self {
        Self::new("priority_filter", move |record| record.priority >= min_priority)
    }
}

#[async_trait]
impl Processor for FilterProcessor {
    async fn process(&self, record: &mut DataRecord) -> Result<()> {
        if (self.filter_fn)(record) {
            Ok(())
        } else {
            Err(PipelineError::Processing("Record filtered out".to_string()))
        }
    }

    fn name(&self) -> &str {
        &self.name
    }
}

/// Enrichment processor - adds metadata and derived fields.
pub struct EnrichmentProcessor {
    name: String,
    enrichments: Vec<Box<dyn Fn(&mut DataRecord) + Send + Sync>>,
}

impl EnrichmentProcessor {
    pub fn new(name: &str) -> Self {
        Self {
            name: name.to_string(),
            enrichments: Vec::new(),
        }
    }

    pub fn add_enrichment(
        mut self,
        enrichment: impl Fn(&mut DataRecord) + Send + Sync + 'static,
    ) -> Self {
        self.enrichments.push(Box::new(enrichment));
        self
    }

    /// Add timestamp enrichment.
    pub fn with_timestamps(self) -> Self {
        self.add_enrichment(|record| {
            record.metadata.insert(
                "processing_timestamp".to_string(),
                format!("{:?}", SystemTime::now()),
            );
        })
    }

    /// Add payload size enrichment.
    pub fn with_size_info(self) -> Self {
        self.add_enrichment(|record| {
            record.metadata.insert(
                "payload_size_bytes".to_string(),
                record.size_bytes().to_string(),
            );
        })
    }
}

#[async_trait]
impl Processor for EnrichmentProcessor {
    async fn process(&self, record: &mut DataRecord) -> Result<()> {
        for enrichment in &self.enrichments {
            enrichment(record);
        }
        Ok(())
    }

    fn name(&self) -> &str {
        &self.name
    }
}

/// Sentiment analysis processor for text data.
pub struct SentimentProcessor {
    name: String,
}

impl SentimentProcessor {
    pub fn new() -> Self {
        Self {
            name: "sentiment_analysis".to_string(),
        }
    }
}

#[async_trait]
impl Processor for SentimentProcessor {
    async fn process(&self, record: &mut DataRecord) -> Result<()> {
        if let DataPayload::Text(ref mut text) = record.payload {
            // Simplified sentiment analysis
            // In production, this would use a proper NLP model
            let sentiment = Self::analyze_sentiment(&text.content);
            text.sentiment = Some(sentiment);
            record
                .metadata
                .insert("sentiment_score".to_string(), format!("{:.3}", sentiment));
        }
        Ok(())
    }

    fn name(&self) -> &str {
        &self.name
    }

    fn can_process(&self, record: &DataRecord) -> bool {
        matches!(record.payload, DataPayload::Text(_))
    }
}

impl SentimentProcessor {
    /// Simple keyword-based sentiment analysis.
    fn analyze_sentiment(text: &str) -> f64 {
        let positive_words = [
            "good", "great", "excellent", "amazing", "wonderful", "positive",
            "happy", "love", "best", "awesome", "fantastic", "brilliant",
            "success", "win", "growth", "profit", "gain", "rise",
        ];
        let negative_words = [
            "bad", "terrible", "awful", "horrible", "negative", "sad",
            "hate", "worst", "poor", "failure", "loss", "crash",
            "decline", "fall", "risk", "danger", "fear", "drop",
        ];

        let lower = text.to_lowercase();
        let words: Vec<&str> = lower.split_whitespace().collect();
        let total = words.len() as f64;

        if total == 0.0 {
            return 0.0;
        }

        let pos_count = words
            .iter()
            .filter(|w| positive_words.contains(&w.trim_matches(|c: char| !c.is_alphanumeric())))
            .count() as f64;

        let neg_count = words
            .iter()
            .filter(|w| negative_words.contains(&w.trim_matches(|c: char| !c.is_alphanumeric())))
            .count() as f64;

        (pos_count - neg_count) / total.sqrt()
    }
}

/// Anomaly detection processor for numeric data.
pub struct AnomalyDetector {
    name: String,
    /// Running mean
    mean: f64,
    /// Running variance
    variance: f64,
    /// Number of samples seen
    count: u64,
    /// Standard deviations threshold for anomaly
    threshold: f64,
}

impl AnomalyDetector {
    pub fn new(threshold: f64) -> Self {
        Self {
            name: "anomaly_detector".to_string(),
            mean: 0.0,
            variance: 0.0,
            count: 0,
            threshold,
        }
    }

    fn update_statistics(&mut self, value: f64) {
        self.count += 1;
        let delta = value - self.mean;
        self.mean += delta / self.count as f64;
        let delta2 = value - self.mean;
        self.variance += delta * delta2;
    }

    fn is_anomaly(&self, value: f64) -> bool {
        if self.count < 30 {
            return false; // Not enough data
        }

        let std_dev = (self.variance / self.count as f64).sqrt();
        if std_dev < 1e-10 {
            return false;
        }

        let z_score = (value - self.mean).abs() / std_dev;
        z_score > self.threshold
    }
}

#[async_trait]
impl Processor for AnomalyDetector {
    async fn process(&self, record: &mut DataRecord) -> Result<()> {
        if let DataPayload::Numeric(ref numeric) = record.payload {
            let is_anomaly = self.is_anomaly(numeric.value);

            record.metadata.insert(
                "is_anomaly".to_string(),
                is_anomaly.to_string(),
            );

            if is_anomaly {
                record.metadata.insert(
                    "anomaly_severity".to_string(),
                    format!(
                        "{:.2}",
                        ((numeric.value - self.mean).abs()
                            / (self.variance / self.count as f64).sqrt().max(1e-10))
                    ),
                );
                // Boost priority for anomalies
                record.priority = record.priority.saturating_add(2);
            }
        }
        Ok(())
    }

    fn name(&self) -> &str {
        &self.name
    }

    fn can_process(&self, record: &DataRecord) -> bool {
        matches!(record.payload, DataPayload::Numeric(_))
    }
}

/// Aggregation processor - computes running statistics.
pub struct AggregationProcessor {
    name: String,
    window_size: usize,
    buffer: Vec<f64>,
}

impl AggregationProcessor {
    pub fn new(window_size: usize) -> Self {
        Self {
            name: "aggregation".to_string(),
            window_size,
            buffer: Vec::with_capacity(window_size),
        }
    }
}

#[async_trait]
impl Processor for AggregationProcessor {
    async fn process(&self, record: &mut DataRecord) -> Result<()> {
        if let DataPayload::Numeric(ref mut numeric) = record.payload {
            // In a real implementation, we'd maintain the buffer with proper synchronization
            // For now, just set the moving average field
            numeric.moving_average = Some(numeric.value); // Simplified

            record.metadata.insert(
                "window_size".to_string(),
                self.window_size.to_string(),
            );
        }
        Ok(())
    }

    fn name(&self) -> &str {
        &self.name
    }
}

/// Transform processor - applies transformations to data.
pub struct TransformProcessor {
    name: String,
    transform_fn: Box<dyn Fn(&mut DataRecord) -> Result<()> + Send + Sync>,
}

impl TransformProcessor {
    pub fn new(
        name: &str,
        transform_fn: impl Fn(&mut DataRecord) -> Result<()> + Send + Sync + 'static,
    ) -> Self {
        Self {
            name: name.to_string(),
            transform_fn: Box::new(transform_fn),
        }
    }
}

#[async_trait]
impl Processor for TransformProcessor {
    async fn process(&self, record: &mut DataRecord) -> Result<()> {
        (self.transform_fn)(record)
    }

    fn name(&self) -> &str {
        &self.name
    }
}

/// Neural feed processor - formats data for the neural architecture.
pub struct NeuralFeedProcessor {
    name: String,
    embedding_dim: usize,
}

impl NeuralFeedProcessor {
    pub fn new(embedding_dim: usize) -> Self {
        Self {
            name: "neural_feed".to_string(),
            embedding_dim,
        }
    }

    /// Convert text to a simple bag-of-words embedding.
    fn text_to_embedding(&self, text: &str) -> Vec<f64> {
        let words: Vec<&str> = text.split_whitespace().collect();
        let mut embedding = vec![0.0f64; self.embedding_dim];

        for (i, word) in words.iter().enumerate() {
            let hash = Self::simple_hash(word);
            let idx = hash % self.embedding_dim;
            embedding[idx] += 1.0 / (i as f64 + 1.0).sqrt();
        }

        // Normalize
        let norm: f64 = embedding.iter().map(|x| x * x).sum::<f64>().sqrt();
        if norm > 0.0 {
            for v in embedding.iter_mut() {
                *v /= norm;
            }
        }

        embedding
    }

    fn simple_hash(s: &str) -> usize {
        let mut hash: usize = 5381;
        for byte in s.bytes() {
            hash = hash.wrapping_mul(33).wrapping_add(byte as usize);
        }
        hash
    }
}

#[async_trait]
impl Processor for NeuralFeedProcessor {
    async fn process(&self, record: &mut DataRecord) -> Result<()> {
        let embedding = match &record.payload {
            DataPayload::Text(text) => self.text_to_embedding(&text.content),
            DataPayload::Numeric(num) => {
                let mut emb = vec![0.0; self.embedding_dim];
                emb[0] = num.value;
                emb
            }
            _ => vec![0.0; self.embedding_dim],
        };

        // Store embedding in metadata as JSON
        record.metadata.insert(
            "neural_embedding".to_string(),
            serde_json::to_string(&embedding).unwrap_or_default(),
        );
        record
            .metadata
            .insert("embedding_dim".to_string(), self.embedding_dim.to_string());

        Ok(())
    }

    fn name(&self) -> &str {
        &self.name
    }
}
