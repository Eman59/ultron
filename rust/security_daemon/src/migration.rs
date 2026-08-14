//! State migration — moves critical state to safe nodes under threat.

use std::collections::HashMap;
use std::time::{Duration, Instant, SystemTime};

/// Migration controller — handles state migration under threat.
pub struct MigrationController {
    /// Known safe nodes
    safe_nodes: Vec<NodeCandidate>,

    /// Active migrations
    active_migrations: Vec<Migration>,

    /// Migration history
    history: Vec<MigrationRecord>,

    /// Configuration
    config: MigrationConfig,
}

/// A candidate node for receiving migrated state.
#[derive(Debug, Clone)]
pub struct NodeCandidate {
    pub node_id: String,
    pub address: String,
    pub capacity: f64,      // Available storage (0-1)
    pub reliability: f64,   // Historical uptime (0-1)
    pub latency: Duration,  // Network latency
    pub trust_score: f64,   // How much we trust this node (0-1)
    pub last_seen: Instant,
}

/// An active state migration.
#[derive(Debug, Clone)]
pub struct Migration {
    pub id: String,
    pub source_node: String,
    pub target_nodes: Vec<String>,
    pub state_regions: Vec<String>,
    pub started_at: Instant,
    pub progress: f64,      // 0-1
    pub bytes_transferred: u64,
    pub total_bytes: u64,
    pub status: MigrationStatus,
}

/// Status of a migration.
#[derive(Debug, Clone, PartialEq)]
pub enum MigrationStatus {
    Preparing,
    Transferring,
    Verifying,
    Completed,
    Failed(String),
    Cancelled,
}

/// Record of a completed migration.
#[derive(Debug, Clone)]
pub struct MigrationRecord {
    pub id: String,
    pub timestamp: SystemTime,
    pub source: String,
    pub targets: Vec<String>,
    pub regions: Vec<String>,
    pub duration: Duration,
    pub bytes_transferred: u64,
    pub success: bool,
    pub reason: String,
}

/// Migration configuration.
#[derive(Debug, Clone)]
pub struct MigrationConfig {
    /// Minimum trust score for target node
    pub min_trust: f64,
    /// Maximum acceptable latency for target
    pub max_latency: Duration,
    /// Minimum replication factor during migration
    pub min_replication: usize,
    /// Timeout for a single migration
    pub timeout: Duration,
    /// Whether to encrypt during transit
    pub encrypt_in_transit: bool,
    /// Whether to verify after transfer
    pub verify_after_transfer: bool,
}

impl Default for MigrationConfig {
    fn default() -> Self {
        Self {
            min_trust: 0.7,
            max_latency: Duration::from_millis(200),
            min_replication: 2,
            timeout: Duration::from_secs(60),
            encrypt_in_transit: true,
            verify_after_transfer: true,
        }
    }
}

impl MigrationController {
    /// Create a new migration controller.
    pub fn new(config: MigrationConfig) -> Self {
        Self {
            safe_nodes: Vec::new(),
            active_migrations: Vec::new(),
            history: Vec::new(),
            config,
        }
    }

    /// Register a node as a potential migration target.
    pub fn register_safe_node(&mut self, candidate: NodeCandidate) {
        // Only accept nodes meeting trust threshold
        if candidate.trust_score >= self.config.min_trust {
            self.safe_nodes.push(candidate);
        }
    }

    /// Select best target nodes for migration.
    pub fn select_targets(&self, required_capacity: f64, count: usize) -> Vec<&NodeCandidate> {
        let mut candidates: Vec<&NodeCandidate> = self.safe_nodes.iter()
            .filter(|n| {
                n.capacity >= required_capacity / count as f64 &&
                n.trust_score >= self.config.min_trust &&
                n.latency <= self.config.max_latency &&
                n.last_seen.elapsed() < Duration::from_secs(30)
            })
            .collect();

        // Sort by composite score: trust * reliability * (1/latency) * capacity
        candidates.sort_by(|a, b| {
            let score_a = a.trust_score * a.reliability * a.capacity
                / (a.latency.as_millis() as f64 + 1.0);
            let score_b = b.trust_score * b.reliability * b.capacity
                / (b.latency.as_millis() as f64 + 1.0);
            score_b.partial_cmp(&score_a).unwrap_or(std::cmp::Ordering::Equal)
        });

        candidates.into_iter().take(count).collect()
    }

    /// Initiate an emergency migration.
    pub fn initiate_migration(
        &mut self,
        source: &str,
        regions: Vec<String>,
        total_bytes: u64,
    ) -> Option<String> {
        // Select best targets
        let capacity_needed = total_bytes as f64 / (1024.0 * 1024.0 * 1024.0); // In GB
        let targets = self.select_targets(capacity_needed, self.config.min_replication);

        if targets.is_empty() {
            tracing::error!("No suitable migration targets available!");
            return None;
        }

        let migration_id = uuid::Uuid::new_v4().to_string();

        let migration = Migration {
            id: migration_id.clone(),
            source_node: source.to_string(),
            target_nodes: targets.iter().map(|t| t.node_id.clone()).collect(),
            state_regions: regions,
            started_at: Instant::now(),
            progress: 0.0,
            bytes_transferred: 0,
            total_bytes,
            status: MigrationStatus::Preparing,
        };

        self.active_migrations.push(migration);

        tracing::warn!(
            "Migration {} initiated: {} -> {:?}",
            migration_id,
            source,
            targets.iter().map(|t| &t.node_id).collect::<Vec<_>>()
        );

        Some(migration_id)
    }

    /// Update migration progress.
    pub fn update_progress(&mut self, migration_id: &str, bytes: u64) {
        if let Some(migration) = self.active_migrations.iter_mut()
            .find(|m| m.id == migration_id) {
            migration.bytes_transferred += bytes;
            migration.progress = migration.bytes_transferred as f64 / migration.total_bytes as f64;
            migration.status = MigrationStatus::Transferring;

            if migration.progress >= 1.0 {
                migration.status = if self.config.verify_after_transfer {
                    MigrationStatus::Verifying
                } else {
                    MigrationStatus::Completed
                };
            }
        }
    }

    /// Complete a migration (after verification).
    pub fn complete_migration(&mut self, migration_id: &str, success: bool) {
        if let Some(pos) = self.active_migrations.iter().position(|m| m.id == migration_id) {
            let mut migration = self.active_migrations.remove(pos);

            migration.status = if success {
                MigrationStatus::Completed
            } else {
                MigrationStatus::Failed("Verification failed".to_string())
            };

            // Record in history
            self.history.push(MigrationRecord {
                id: migration.id,
                timestamp: SystemTime::now(),
                source: migration.source_node,
                targets: migration.target_nodes,
                regions: migration.state_regions,
                duration: migration.started_at.elapsed(),
                bytes_transferred: migration.bytes_transferred,
                success,
                reason: if success { "emergency_migration" } else { "verification_failed" }.to_string(),
            });
        }
    }

    /// Get active migration status.
    pub fn get_active_migrations(&self) -> &[Migration] {
        &self.active_migrations
    }

    /// Get migration statistics.
    pub fn get_stats(&self) -> HashMap<String, f64> {
        let mut stats = HashMap::new();

        let total = self.history.len();
        let successful = self.history.iter().filter(|m| m.success).count();

        stats.insert("total_migrations".to_string(), total as f64);
        stats.insert("successful_migrations".to_string(), successful as f64);
        stats.insert("success_rate".to_string(),
            if total > 0 { successful as f64 / total as f64 } else { 0.0 });
        stats.insert("active_migrations".to_string(), self.active_migrations.len() as f64);
        stats.insert("safe_nodes_available".to_string(), self.safe_nodes.len() as f64);

        if let Some(last) = self.history.last() {
            stats.insert("last_migration_duration_ms".to_string(),
                last.duration.as_millis() as f64);
        }

        stats
    }
}
