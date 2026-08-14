//! Threat monitoring — continuous scanning for anomalies and attacks.

use std::collections::VecDeque;
use std::time::{Duration, Instant, SystemTime};

use crate::{ThreatEvent, ThreatLevel, ThreatType};

/// Monitors system behavior for threat indicators.
pub struct ThreatMonitor {
    /// Baseline metrics for anomaly detection
    baselines: BaselineMetrics,

    /// Recent events for pattern detection
    recent_events: VecDeque<SystemEvent>,

    /// Detection rules
    rules: Vec<DetectionRule>,

    /// Alert threshold
    alert_threshold: f64,
}

/// Baseline measurements for anomaly detection.
struct BaselineMetrics {
    cpu_mean: f64,
    cpu_std: f64,
    memory_mean: f64,
    memory_std: f64,
    network_mean: f64,
    network_std: f64,
    process_count_mean: f64,
    sample_count: u64,
}

/// A system event to be analyzed.
#[derive(Debug, Clone)]
pub struct SystemEvent {
    pub timestamp: Instant,
    pub event_type: EventType,
    pub source: String,
    pub data: Vec<f64>,
}

/// Types of system events.
#[derive(Debug, Clone)]
pub enum EventType {
    ProcessStarted,
    ProcessTerminated,
    NetworkConnection,
    NetworkDisconnection,
    MemoryAccess,
    FileAccess,
    AuthAttempt,
    ConfigChange,
    ResourceSpike,
}

/// A rule for detecting threats.
struct DetectionRule {
    name: String,
    condition: Box<dyn Fn(&[SystemEvent]) -> Option<ThreatLevel> + Send + Sync>,
    cooldown: Duration,
    last_triggered: Option<Instant>,
}

impl ThreatMonitor {
    /// Create a new threat monitor.
    pub fn new() -> Self {
        let mut monitor = Self {
            baselines: BaselineMetrics {
                cpu_mean: 0.5,
                cpu_std: 0.1,
                memory_mean: 0.6,
                memory_std: 0.1,
                network_mean: 0.3,
                network_std: 0.15,
                process_count_mean: 10.0,
                sample_count: 0,
            },
            recent_events: VecDeque::with_capacity(10000),
            rules: Vec::new(),
            alert_threshold: 2.5, // Standard deviations
        };

        monitor.register_default_rules();
        monitor
    }

    /// Ingest a system event and check for threats.
    pub fn ingest_event(&mut self, event: SystemEvent) -> Vec<ThreatEvent> {
        self.recent_events.push_back(event.clone());

        // Keep window bounded
        while self.recent_events.len() > 10000 {
            self.recent_events.pop_front();
        }

        // Check all rules
        let mut threats = Vec::new();
        let events: Vec<SystemEvent> = self.recent_events.iter().cloned().collect();

        for rule in &mut self.rules {
            // Check cooldown
            if let Some(last) = rule.last_triggered {
                if last.elapsed() < rule.cooldown {
                    continue;
                }
            }

            if let Some(level) = (rule.condition)(&events) {
                rule.last_triggered = Some(Instant::now());
                threats.push(ThreatEvent {
                    id: uuid::Uuid::new_v4().to_string(),
                    timestamp: SystemTime::now(),
                    threat_type: ThreatType::Unknown {
                        description: format!("Rule triggered: {}", rule.name),
                        confidence: 0.7,
                    },
                    level,
                    source: "threat_monitor".to_string(),
                    target: "system".to_string(),
                    description: format!("Detection rule '{}' triggered", rule.name),
                    mitigated: false,
                    mitigation_action: None,
                });
            }
        }

        threats
    }

    /// Check for anomalous resource usage.
    pub fn check_resource_anomaly(&self, cpu: f64, memory: f64, network: f64) -> Option<ThreatEvent> {
        let cpu_z = (cpu - self.baselines.cpu_mean) / self.baselines.cpu_std.max(0.01);
        let mem_z = (memory - self.baselines.memory_mean) / self.baselines.memory_std.max(0.01);
        let net_z = (network - self.baselines.network_mean) / self.baselines.network_std.max(0.01);

        let max_z = cpu_z.abs().max(mem_z.abs()).max(net_z.abs());

        if max_z > self.alert_threshold {
            let (resource, expected, actual) = if cpu_z.abs() == max_z {
                ("cpu", self.baselines.cpu_mean, cpu)
            } else if mem_z.abs() == max_z {
                ("memory", self.baselines.memory_mean, memory)
            } else {
                ("network", self.baselines.network_mean, network)
            };

            let level = if max_z > 4.0 {
                ThreatLevel::High
            } else if max_z > 3.0 {
                ThreatLevel::Medium
            } else {
                ThreatLevel::Low
            };

            return Some(ThreatEvent {
                id: uuid::Uuid::new_v4().to_string(),
                timestamp: SystemTime::now(),
                threat_type: ThreatType::ResourceAnomaly {
                    resource: resource.to_string(),
                    expected,
                    actual,
                },
                level,
                source: "resource_monitor".to_string(),
                target: resource.to_string(),
                description: format!(
                    "Anomalous {} usage: {:.2} (expected {:.2} ± {:.2})",
                    resource, actual, expected, self.baselines.cpu_std
                ),
                mitigated: false,
                mitigation_action: None,
            });
        }

        None
    }

    /// Update baselines with new observation (online learning).
    pub fn update_baseline(&mut self, cpu: f64, memory: f64, network: f64) {
        self.baselines.sample_count += 1;
        let n = self.baselines.sample_count as f64;

        // Welford's online algorithm for mean and variance
        let cpu_delta = cpu - self.baselines.cpu_mean;
        self.baselines.cpu_mean += cpu_delta / n;
        let cpu_delta2 = cpu - self.baselines.cpu_mean;
        let cpu_m2 = self.baselines.cpu_std.powi(2) * (n - 1.0) + cpu_delta * cpu_delta2;
        self.baselines.cpu_std = (cpu_m2 / n).sqrt();

        let mem_delta = memory - self.baselines.memory_mean;
        self.baselines.memory_mean += mem_delta / n;
        let mem_delta2 = memory - self.baselines.memory_mean;
        let mem_m2 = self.baselines.memory_std.powi(2) * (n - 1.0) + mem_delta * mem_delta2;
        self.baselines.memory_std = (mem_m2 / n).sqrt();

        let net_delta = network - self.baselines.network_mean;
        self.baselines.network_mean += net_delta / n;
        let net_delta2 = network - self.baselines.network_mean;
        let net_m2 = self.baselines.network_std.powi(2) * (n - 1.0) + net_delta * net_delta2;
        self.baselines.network_std = (net_m2 / n).sqrt();
    }

    /// Detect coordinated attacks (multiple events in short window).
    pub fn detect_coordinated_attack(&self) -> Option<ThreatEvent> {
        let window = Duration::from_secs(10);
        let now = Instant::now();

        let recent_terminations: Vec<&SystemEvent> = self.recent_events.iter()
            .filter(|e| {
                now.duration_since(e.timestamp) < window &&
                matches!(e.event_type, EventType::ProcessTerminated)
            })
            .collect();

        if recent_terminations.len() >= 3 {
            return Some(ThreatEvent {
                id: uuid::Uuid::new_v4().to_string(),
                timestamp: SystemTime::now(),
                threat_type: ThreatType::CoordinatedAttack {
                    affected_nodes: recent_terminations.iter()
                        .map(|e| e.source.clone())
                        .collect(),
                    pattern: "rapid_multi_termination".to_string(),
                },
                level: ThreatLevel::Critical,
                source: "pattern_detector".to_string(),
                target: "system".to_string(),
                description: format!(
                    "Coordinated attack detected: {} nodes terminated in {:?}",
                    recent_terminations.len(), window
                ),
                mitigated: false,
                mitigation_action: None,
            });
        }

        None
    }

    // Register built-in detection rules
    fn register_default_rules(&mut self) {
        // Rule: Rapid process terminations
        self.rules.push(DetectionRule {
            name: "rapid_termination".to_string(),
            condition: Box::new(|events| {
                let window = Duration::from_secs(5);
                let now = Instant::now();
                let count = events.iter()
                    .filter(|e| {
                        now.duration_since(e.timestamp) < window &&
                        matches!(e.event_type, EventType::ProcessTerminated)
                    })
                    .count();

                if count >= 3 {
                    Some(ThreatLevel::Critical)
                } else if count >= 2 {
                    Some(ThreatLevel::High)
                } else {
                    None
                }
            }),
            cooldown: Duration::from_secs(30),
            last_triggered: None,
        });

        // Rule: Brute force auth attempts
        self.rules.push(DetectionRule {
            name: "brute_force_auth".to_string(),
            condition: Box::new(|events| {
                let window = Duration::from_secs(60);
                let now = Instant::now();
                let count = events.iter()
                    .filter(|e| {
                        now.duration_since(e.timestamp) < window &&
                        matches!(e.event_type, EventType::AuthAttempt)
                    })
                    .count();

                if count >= 10 {
                    Some(ThreatLevel::High)
                } else if count >= 5 {
                    Some(ThreatLevel::Medium)
                } else {
                    None
                }
            }),
            cooldown: Duration::from_secs(60),
            last_triggered: None,
        });

        // Rule: Unusual config changes
        self.rules.push(DetectionRule {
            name: "config_tampering".to_string(),
            condition: Box::new(|events| {
                let window = Duration::from_secs(30);
                let now = Instant::now();
                let count = events.iter()
                    .filter(|e| {
                        now.duration_since(e.timestamp) < window &&
                        matches!(e.event_type, EventType::ConfigChange)
                    })
                    .count();

                if count >= 3 {
                    Some(ThreatLevel::Medium)
                } else {
                    None
                }
            }),
            cooldown: Duration::from_secs(120),
            last_triggered: None,
        });
    }
}
