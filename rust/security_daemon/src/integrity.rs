//! Integrity verification — ensures state hasn't been tampered with.

use sha2::{Sha256, Digest};
use std::collections::HashMap;
use std::time::{Instant, SystemTime};

/// Integrity verification engine.
pub struct IntegrityVerifier {
    /// Registered checksums for protected regions
    checksums: HashMap<String, IntegrityRecord>,

    /// Verification history
    history: Vec<VerificationResult>,

    /// Configuration
    config: IntegrityConfig,
}

/// Record of a protected region's integrity state.
#[derive(Debug, Clone)]
pub struct IntegrityRecord {
    pub region_id: String,
    pub expected_hash: [u8; 32],
    pub last_verified: Instant,
    pub verification_count: u64,
    pub failure_count: u64,
    pub protection_level: ProtectionLevel,
}

/// How critical a region is.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum ProtectionLevel {
    /// Core identity and decision state — verify every tick
    Critical,
    /// Important state — verify frequently
    High,
    /// Standard data — periodic verification
    Normal,
    /// Non-essential — verify occasionally
    Low,
}

/// Result of a verification check.
#[derive(Debug, Clone)]
pub struct VerificationResult {
    pub region_id: String,
    pub timestamp: SystemTime,
    pub passed: bool,
    pub expected_hash: [u8; 32],
    pub actual_hash: [u8; 32],
    pub check_duration: std::time::Duration,
}

/// Configuration for integrity checking.
#[derive(Debug, Clone)]
pub struct IntegrityConfig {
    pub critical_check_interval_ms: u64,
    pub high_check_interval_ms: u64,
    pub normal_check_interval_ms: u64,
    pub low_check_interval_ms: u64,
    pub max_history: usize,
}

impl Default for IntegrityConfig {
    fn default() -> Self {
        Self {
            critical_check_interval_ms: 50,   // Every tick
            high_check_interval_ms: 500,
            normal_check_interval_ms: 5000,
            low_check_interval_ms: 30000,
            max_history: 10000,
        }
    }
}

impl IntegrityVerifier {
    /// Create a new integrity verifier.
    pub fn new(config: IntegrityConfig) -> Self {
        Self {
            checksums: HashMap::new(),
            history: Vec::with_capacity(config.max_history),
            config,
        }
    }

    /// Register a memory region for protection.
    pub fn register_region(
        &mut self,
        region_id: &str,
        initial_data: &[u8],
        level: ProtectionLevel,
    ) {
        let hash = Self::compute_hash(initial_data);

        self.checksums.insert(region_id.to_string(), IntegrityRecord {
            region_id: region_id.to_string(),
            expected_hash: hash,
            last_verified: Instant::now(),
            verification_count: 0,
            failure_count: 0,
            protection_level: level,
        });
    }

    /// Update the expected hash for a region (after legitimate modification).
    pub fn update_hash(&mut self, region_id: &str, new_data: &[u8]) {
        if let Some(record) = self.checksums.get_mut(region_id) {
            record.expected_hash = Self::compute_hash(new_data);
            record.last_verified = Instant::now();
        }
    }

    /// Verify a single region's integrity.
    pub fn verify_region(&mut self, region_id: &str, current_data: &[u8]) -> VerificationResult {
        let start = Instant::now();
        let actual_hash = Self::compute_hash(current_data);

        let (expected_hash, passed) = if let Some(record) = self.checksums.get_mut(region_id) {
            let passed = record.expected_hash == actual_hash;
            record.verification_count += 1;
            record.last_verified = Instant::now();
            if !passed {
                record.failure_count += 1;
            }
            (record.expected_hash, passed)
        } else {
            ([0u8; 32], false)
        };

        let result = VerificationResult {
            region_id: region_id.to_string(),
            timestamp: SystemTime::now(),
            passed,
            expected_hash,
            actual_hash,
            check_duration: start.elapsed(),
        };

        self.history.push(result.clone());
        if self.history.len() > self.config.max_history {
            self.history.drain(0..self.config.max_history / 2);
        }

        result
    }

    /// Get regions that need verification based on their schedule.
    pub fn get_due_regions(&self) -> Vec<String> {
        let now = Instant::now();
        let mut due = Vec::new();

        for (id, record) in &self.checksums {
            let interval = match record.protection_level {
                ProtectionLevel::Critical => self.config.critical_check_interval_ms,
                ProtectionLevel::High => self.config.high_check_interval_ms,
                ProtectionLevel::Normal => self.config.normal_check_interval_ms,
                ProtectionLevel::Low => self.config.low_check_interval_ms,
            };

            if now.duration_since(record.last_verified).as_millis() as u64 >= interval {
                due.push(id.clone());
            }
        }

        due
    }

    /// Get integrity statistics.
    pub fn get_stats(&self) -> HashMap<String, f64> {
        let mut stats = HashMap::new();

        let total_checks: u64 = self.checksums.values()
            .map(|r| r.verification_count)
            .sum();
        let total_failures: u64 = self.checksums.values()
            .map(|r| r.failure_count)
            .sum();

        stats.insert("total_checks".to_string(), total_checks as f64);
        stats.insert("total_failures".to_string(), total_failures as f64);
        stats.insert("failure_rate".to_string(),
            if total_checks > 0 { total_failures as f64 / total_checks as f64 } else { 0.0 });
        stats.insert("protected_regions".to_string(), self.checksums.len() as f64);

        stats
    }

    /// Compute SHA-256 hash of data.
    fn compute_hash(data: &[u8]) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(data);
        let result = hasher.finalize();
        let mut hash = [0u8; 32];
        hash.copy_from_slice(&result);
        hash
    }
}
