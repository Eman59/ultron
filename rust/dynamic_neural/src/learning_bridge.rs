//! Learning Bridge — Connects the Neural Evolution system to Ultron's Self-Learning subsystem.
//!
//! This module reports neural mesh metrics, evolution progress, and plasticity
//! events to the central learning system, and receives back architecture
//! directives that guide how the neural network evolves.
//!
//! ## What flows OUT (to learning system):
//! - Neural activation patterns (summarized, not raw)
//! - Evolution generation results (fitness, diversity, stagnation)
//! - Plasticity events (connections formed/pruned, strength changes)
//! - Architecture metrics (neuron count, connection density, fire rates)
//! - Performance benchmarks (processing latency, accuracy trends)
//!
//! ## What flows IN (from learning system):
//! - Architecture directives ("grow to 2000 neurons", "increase density")
//! - Evolution parameter adjustments (mutation rate, crossover rate, etc.)
//! - Plasticity rules ("strengthen connections in pattern X")
//! - Fitness function modifications (new objectives, weight changes)
//! - Exploration directives ("try novelty search", "focus on accuracy")

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::{Arc, Mutex, RwLock};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};
use tracing::{debug, info, warn};

// ═══════════════════════════════════════════════════════════════════
// OUTBOUND: Events sent to the learning system
// ═══════════════════════════════════════════════════════════════════

/// Categories of neural events reported to the learning system.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum NeuralEventType {
    EvolutionGeneration,
    PlasticityBurst,
    ArchitectureChange,
    PerformanceMeasurement,
    StagnationDetected,
    NewBestFitness,
    ActivationPattern,
    DiversityMeasurement,
}

/// A single event sent to the learning system.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NeuralLearningEvent {
    pub id: String,
    pub timestamp_ns: u64,
    pub event_type: NeuralEventType,
    pub component: String,
    pub data: HashMap<String, serde_json::Value>,
    pub outcome: Option<f64>,
    pub tags: Vec<String>,
}

impl NeuralLearningEvent {
    pub fn new(event_type: NeuralEventType, data: HashMap<String, serde_json::Value>) -> Self {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos() as u64;

        Self {
            id: format!("neural_{}_{}", now % 1_000_000_000, rand_id()),
            timestamp_ns: now,
            event_type,
            component: "neural_mesh".to_string(),
            data,
            outcome: None,
            tags: Vec::new(),
        }
    }

    pub fn with_outcome(mut self, outcome: f64) -> Self {
        self.outcome = Some(outcome);
        self
    }

    pub fn with_tags(mut self, tags: Vec<&str>) -> Self {
        self.tags = tags.into_iter().map(|s| s.to_string()).collect();
        self
    }
}

// ═══════════════════════════════════════════════════════════════════
// INBOUND: Directives from the learning system
// ═══════════════════════════════════════════════════════════════════

/// Types of directives the learning system can send.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum NeuralDirectiveType {
    SetArchitectureTarget,
    AdjustEvolutionParams,
    SetPlasticityRules,
    AdjustFitnessWeights,
    SetExplorationStrategy,
    ForceMutation,
    PruneArchitecture,
    ResetPopulation,
}

/// A directive from the learning system to the neural subsystem.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NeuralDirective {
    pub id: String,
    pub directive_type: NeuralDirectiveType,
    pub priority: u8,
    pub payload: HashMap<String, serde_json::Value>,
    pub source: String,
    pub confidence: f64,
    pub expires_at: Option<u64>,
}

/// Architecture target from the learning system.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ArchitectureTarget {
    pub target_neurons: usize,
    pub target_connections: usize,
    pub target_density: f32,
    pub min_plasticity: f32,
    pub max_plasticity: f32,
    pub preferred_neuron_types: Vec<String>,
}

/// Evolution parameter adjustments.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvolutionParamAdjustment {
    pub mutation_rate: Option<f32>,
    pub crossover_rate: Option<f32>,
    pub elite_size: Option<usize>,
    pub population_size: Option<usize>,
    pub novelty_weight: Option<f32>,
    pub complexity_penalty: Option<f32>,
    pub diversity_threshold: Option<f32>,
}

/// Plasticity rules from the learning system.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PlasticityRules {
    pub hebbian_rate: f32,
    pub decay_rate: f32,
    pub strengthening_threshold: f32,
    pub pruning_threshold: f32,
    pub max_plasticity: f32,
    pub stabilization_after: u64,
}

/// Fitness function weight adjustments.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FitnessWeights {
    pub accuracy_weight: f32,
    pub novelty_weight: f32,
    pub complexity_weight: f32,
    pub adaptation_weight: f32,
    pub efficiency_weight: f32,
}

/// Exploration strategy settings.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ExplorationStrategy {
    FitnessProportional,
    NoveltySearch { novelty_threshold: f32 },
    QualityDiversity { archive_size: usize },
    ExplorationBurst { duration_generations: u64 },
    Exploitation { top_k: usize },
}

/// Result of applying a directive.
#[derive(Debug, Clone)]
pub struct DirectiveResult {
    pub directive_type: String,
    pub success: bool,
    pub message: String,
}

impl DirectiveResult {
    pub fn applied(dtype: &str, msg: &str) -> Self {
        Self { directive_type: dtype.to_string(), success: true, message: msg.to_string() }
    }
    pub fn failed(dtype: &str, msg: &str) -> Self {
        Self { directive_type: dtype.to_string(), success: false, message: msg.to_string() }
    }
}

/// Generation statistics reported to the learning system.
#[derive(Debug, Clone, Default)]
pub struct GenerationStats {
    pub best_fitness: f32,
    pub average_fitness: f32,
    pub worst_fitness: f32,
    pub diversity: f32,
    pub stagnation_counter: u64,
    pub population_size: usize,
    pub mutations_applied: usize,
    pub crossovers_performed: usize,
    pub neurons_added: usize,
    pub connections_pruned: usize,
    pub is_new_best: bool,
}

// ═══════════════════════════════════════════════════════════════════
// ACTIVE OVERRIDES — Configuration set by the learning system
// ═══════════════════════════════════════════════════════════════════

/// Active overrides applied by the learning system.
#[derive(Debug, Clone, Default)]
pub struct ActiveOverrides {
    pub architecture_target: Option<ArchitectureTarget>,
    pub evolution_params: Option<EvolutionParamAdjustment>,
    pub plasticity_rules: Option<PlasticityRules>,
    pub fitness_weights: Option<FitnessWeights>,
    pub exploration_strategy: Option<ExplorationStrategy>,
}

/// Bridge performance metrics.
#[derive(Debug, Clone, Default)]
pub struct BridgeMetrics {
    pub events_sent: u64,
    pub events_dropped: u64,
    pub directives_received: u64,
    pub directives_applied: u64,
    pub last_event_time: u64,
    pub last_directive_time: u64,
    pub generations_reported: u64,
    pub best_fitness_reported: f32,
}

// ═══════════════════════════════════════════════════════════════════
// LEARNING BRIDGE — The main integration point
// ═══════════════════════════════════════════════════════════════════

/// The Learning Bridge connects neural evolution to the self-learning system.
pub struct LearningBridge {
    /// Event buffer for outbound events
    event_buffer: Arc<Mutex<Vec<NeuralLearningEvent>>>,
    max_buffer_size: usize,

    /// Pending directives from the learning system
    directive_queue: Arc<RwLock<Vec<NeuralDirective>>>,

    /// Active configuration overrides
    active_overrides: Arc<RwLock<ActiveOverrides>>,

    /// Metrics
    metrics: Arc<RwLock<BridgeMetrics>>,

    /// Connection state
    connected: Arc<AtomicBool>,
    service_addr: String,
}

impl LearningBridge {
    /// Create a new learning bridge.
    pub fn new(service_addr: &str, max_buffer_size: usize) -> Self {
        info!("Creating neural learning bridge to {}", service_addr);

        Self {
            event_buffer: Arc::new(Mutex::new(Vec::with_capacity(max_buffer_size))),
            max_buffer_size,
            directive_queue: Arc::new(RwLock::new(Vec::new())),
            active_overrides: Arc::new(RwLock::new(ActiveOverrides::default())),
            metrics: Arc::new(RwLock::new(BridgeMetrics::default())),
            connected: Arc::new(AtomicBool::new(false)),
            service_addr: service_addr.to_string(),
        }
    }

    // ═══════════════════════════════════════════════════════════════
    // EVENT EMISSION — Report to the learning system
    // ═══════════════════════════════════════════════════════════════

    /// Report an evolution generation result.
    pub fn report_generation(&self, generation: u64, stats: &GenerationStats) {
        let mut data = HashMap::new();
        data.insert("generation".into(), serde_json::json!(generation));
        data.insert("best_fitness".into(), serde_json::json!(stats.best_fitness));
        data.insert("average_fitness".into(), serde_json::json!(stats.average_fitness));
        data.insert("worst_fitness".into(), serde_json::json!(stats.worst_fitness));
        data.insert("diversity".into(), serde_json::json!(stats.diversity));
        data.insert("stagnation_counter".into(), serde_json::json!(stats.stagnation_counter));
        data.insert("population_size".into(), serde_json::json!(stats.population_size));
        data.insert("mutations_applied".into(), serde_json::json!(stats.mutations_applied));
        data.insert("crossovers_performed".into(), serde_json::json!(stats.crossovers_performed));
        data.insert("neurons_added".into(), serde_json::json!(stats.neurons_added));
        data.insert("connections_pruned".into(), serde_json::json!(stats.connections_pruned));

        let event = NeuralLearningEvent::new(NeuralEventType::EvolutionGeneration, data)
            .with_outcome(stats.best_fitness as f64)
            .with_tags(vec!["evolution", "generation"]);

        self.emit_event(event);

        if let Ok(mut m) = self.metrics.write() {
            m.generations_reported += 1;
            if stats.best_fitness > m.best_fitness_reported {
                m.best_fitness_reported = stats.best_fitness;
            }
        }

        if stats.stagnation_counter > 30 {
            self.report_stagnation(generation, stats.stagnation_counter);
        }
        if stats.is_new_best {
            self.report_new_best(generation, stats.best_fitness);
        }
    }

    /// Report a plasticity burst.
    pub fn report_plasticity_burst(
        &self,
        mesh_id: u64,
        strengthened: usize,
        weakened: usize,
        pruned: usize,
        formed: usize,
    ) {
        let mut data = HashMap::new();
        data.insert("mesh_id".into(), serde_json::json!(mesh_id));
        data.insert("strengthened".into(), serde_json::json!(strengthened));
        data.insert("weakened".into(), serde_json::json!(weakened));
        data.insert("pruned".into(), serde_json::json!(pruned));
        data.insert("formed".into(), serde_json::json!(formed));
        data.insert("total_changes".into(), serde_json::json!(strengthened + weakened + pruned + formed));

        let event = NeuralLearningEvent::new(NeuralEventType::PlasticityBurst, data)
            .with_tags(vec!["plasticity", "neural"]);
        self.emit_event(event);
    }

    /// Report architecture change.
    pub fn report_architecture_change(
        &self,
        mesh_id: u64,
        neurons_before: usize,
        neurons_after: usize,
        connections_before: usize,
        connections_after: usize,
        reason: &str,
    ) {
        let mut data = HashMap::new();
        data.insert("mesh_id".into(), serde_json::json!(mesh_id));
        data.insert("neurons_before".into(), serde_json::json!(neurons_before));
        data.insert("neurons_after".into(), serde_json::json!(neurons_after));
        data.insert("connections_before".into(), serde_json::json!(connections_before));
        data.insert("connections_after".into(), serde_json::json!(connections_after));
        data.insert("neuron_delta".into(), serde_json::json!(neurons_after as i64 - neurons_before as i64));
        data.insert("reason".into(), serde_json::json!(reason));

        let event = NeuralLearningEvent::new(NeuralEventType::ArchitectureChange, data)
            .with_tags(vec!["architecture", "neural", reason]);
        self.emit_event(event);
    }

    /// Report performance measurement.
    pub fn report_performance(
        &self,
        mesh_id: u64,
        accuracy: f32,
        latency_us: u64,
        throughput: f32,
        fire_rate: f32,
    ) {
        let mut data = HashMap::new();
        data.insert("mesh_id".into(), serde_json::json!(mesh_id));
        data.insert("accuracy".into(), serde_json::json!(accuracy));
        data.insert("latency_us".into(), serde_json::json!(latency_us));
        data.insert("throughput".into(), serde_json::json!(throughput));
        data.insert("fire_rate".into(), serde_json::json!(fire_rate));

        let event = NeuralLearningEvent::new(NeuralEventType::PerformanceMeasurement, data)
            .with_outcome(accuracy as f64)
            .with_tags(vec!["performance", "neural"]);
        self.emit_event(event);
    }

    /// Report activation pattern summary.
    pub fn report_activation_pattern(
        &self,
        mesh_id: u64,
        pattern_hash: u64,
        active_neurons: usize,
        total_neurons: usize,
        layer_activations: &[f32],
    ) {
        let mut data = HashMap::new();
        data.insert("mesh_id".into(), serde_json::json!(mesh_id));
        data.insert("pattern_hash".into(), serde_json::json!(pattern_hash));
        data.insert("active_neurons".into(), serde_json::json!(active_neurons));
        data.insert("total_neurons".into(), serde_json::json!(total_neurons));
        data.insert("fire_rate".into(), serde_json::json!(active_neurons as f32 / total_neurons.max(1) as f32));
        data.insert("layer_activations".into(), serde_json::json!(layer_activations));

        let event = NeuralLearningEvent::new(NeuralEventType::ActivationPattern, data)
            .with_tags(vec!["activation", "pattern"]);
        self.emit_event(event);
    }

    /// Report diversity measurement.
    pub fn report_diversity(&self, generation: u64, diversity_score: f32, unique_architectures: usize) {
        let mut data = HashMap::new();
        data.insert("generation".into(), serde_json::json!(generation));
        data.insert("diversity_score".into(), serde_json::json!(diversity_score));
        data.insert("unique_architectures".into(), serde_json::json!(unique_architectures));

        let event = NeuralLearningEvent::new(NeuralEventType::DiversityMeasurement, data)
            .with_tags(vec!["diversity", "evolution"]);
        self.emit_event(event);
    }

    fn report_stagnation(&self, generation: u64, counter: u64) {
        let mut data = HashMap::new();
        data.insert("generation".into(), serde_json::json!(generation));
        data.insert("stagnation_counter".into(), serde_json::json!(counter));

        let event = NeuralLearningEvent::new(NeuralEventType::StagnationDetected, data)
            .with_outcome(-0.3)
            .with_tags(vec!["stagnation", "evolution"]);
        self.emit_event(event);
    }

    fn report_new_best(&self, generation: u64, fitness: f32) {
        let mut data = HashMap::new();
        data.insert("generation".into(), serde_json::json!(generation));
        data.insert("fitness".into(), serde_json::json!(fitness));

        let event = NeuralLearningEvent::new(NeuralEventType::NewBestFitness, data)
            .with_outcome(fitness as f64)
            .with_tags(vec!["new_best", "evolution", "milestone"]);
        self.emit_event(event);
    }

    fn emit_event(&self, event: NeuralLearningEvent) {
        if let Ok(mut buffer) = self.event_buffer.lock() {
            if buffer.len() >= self.max_buffer_size {
                buffer.remove(0);
                if let Ok(mut m) = self.metrics.write() {
                    m.events_dropped += 1;
                }
            }
            buffer.push(event);
            if let Ok(mut m) = self.metrics.write() {
                m.events_sent += 1;
                m.last_event_time = SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_nanos() as u64;
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════
    // DIRECTIVE PROCESSING — Apply learning system instructions
    // ═══════════════════════════════════════════════════════════════

    /// Process all pending directives. Called once per evolution generation.
    pub fn process_directives(&self) -> Vec<DirectiveResult> {
        let directives = {
            let mut queue = self.directive_queue.write().unwrap();
            std::mem::take(&mut *queue)
        };

        let mut results = Vec::new();

        for directive in &directives {
            let result = self.apply_directive(directive);
            results.push(result);

            if let Ok(mut m) = self.metrics.write() {
                m.directives_applied += 1;
                m.last_directive_time = SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_nanos() as u64;
            }
        }

        results
    }

    fn apply_directive(&self, directive: &NeuralDirective) -> DirectiveResult {
        debug!("Applying neural directive: {:?}", directive.directive_type);

        match directive.directive_type {
            NeuralDirectiveType::SetArchitectureTarget => self.apply_architecture_target(directive),
            NeuralDirectiveType::AdjustEvolutionParams => self.apply_evolution_params(directive),
            NeuralDirectiveType::SetPlasticityRules => self.apply_plasticity_rules(directive),
            NeuralDirectiveType::AdjustFitnessWeights => self.apply_fitness_weights(directive),
            NeuralDirectiveType::SetExplorationStrategy => self.apply_exploration_strategy(directive),
            NeuralDirectiveType::ForceMutation => DirectiveResult::applied("force_mutation", "Queued"),
            NeuralDirectiveType::PruneArchitecture => DirectiveResult::applied("prune", "Queued"),
            NeuralDirectiveType::ResetPopulation => DirectiveResult::applied("reset", "Queued"),
        }
    }

    fn apply_architecture_target(&self, d: &NeuralDirective) -> DirectiveResult {
        let target = ArchitectureTarget {
            target_neurons: d.payload.get("target_neurons").and_then(|v| v.as_u64()).unwrap_or(1000) as usize,
            target_connections: d.payload.get("target_connections").and_then(|v| v.as_u64()).unwrap_or(5000) as usize,
            target_density: d.payload.get("target_density").and_then(|v| v.as_f64()).unwrap_or(0.1) as f32,
            min_plasticity: d.payload.get("min_plasticity").and_then(|v| v.as_f64()).unwrap_or(0.01) as f32,
            max_plasticity: d.payload.get("max_plasticity").and_then(|v| v.as_f64()).unwrap_or(0.5) as f32,
            preferred_neuron_types: d.payload.get("preferred_types")
                .and_then(|v| v.as_array())
                .map(|arr| arr.iter().filter_map(|v| v.as_str().map(String::from)).collect())
                .unwrap_or_default(),
        };
        if let Ok(mut o) = self.active_overrides.write() { o.architecture_target = Some(target); }
        DirectiveResult::applied("architecture_target", "Updated")
    }

    fn apply_evolution_params(&self, d: &NeuralDirective) -> DirectiveResult {
        let adj = EvolutionParamAdjustment {
            mutation_rate: d.payload.get("mutation_rate").and_then(|v| v.as_f64()).map(|v| v as f32),
            crossover_rate: d.payload.get("crossover_rate").and_then(|v| v.as_f64()).map(|v| v as f32),
            elite_size: d.payload.get("elite_size").and_then(|v| v.as_u64()).map(|v| v as usize),
            population_size: d.payload.get("population_size").and_then(|v| v.as_u64()).map(|v| v as usize),
            novelty_weight: d.payload.get("novelty_weight").and_then(|v| v.as_f64()).map(|v| v as f32),
            complexity_penalty: d.payload.get("complexity_penalty").and_then(|v| v.as_f64()).map(|v| v as f32),
            diversity_threshold: d.payload.get("diversity_threshold").and_then(|v| v.as_f64()).map(|v| v as f32),
        };
        if let Ok(mut o) = self.active_overrides.write() { o.evolution_params = Some(adj); }
        DirectiveResult::applied("evolution_params", "Adjusted")
    }

    fn apply_plasticity_rules(&self, d: &NeuralDirective) -> DirectiveResult {
        let rules = PlasticityRules {
            hebbian_rate: d.payload.get("hebbian_rate").and_then(|v| v.as_f64()).unwrap_or(0.01) as f32,
            decay_rate: d.payload.get("decay_rate").and_then(|v| v.as_f64()).unwrap_or(0.001) as f32,
            strengthening_threshold: d.payload.get("strengthening_threshold").and_then(|v| v.as_f64()).unwrap_or(0.5) as f32,
            pruning_threshold: d.payload.get("pruning_threshold").and_then(|v| v.as_f64()).unwrap_or(0.01) as f32,
            max_plasticity: d.payload.get("max_plasticity").and_then(|v| v.as_f64()).unwrap_or(0.5) as f32,
            stabilization_after: d.payload.get("stabilization_after").and_then(|v| v.as_u64()).unwrap_or(1000),
        };
        if let Ok(mut o) = self.active_overrides.write() { o.plasticity_rules = Some(rules); }
        DirectiveResult::applied("plasticity_rules", "Updated")
    }

    fn apply_fitness_weights(&self, d: &NeuralDirective) -> DirectiveResult {
        let weights = FitnessWeights {
            accuracy_weight: d.payload.get("accuracy_weight").and_then(|v| v.as_f64()).unwrap_or(0.5) as f32,
            novelty_weight: d.payload.get("novelty_weight").and_then(|v| v.as_f64()).unwrap_or(0.1) as f32,
            complexity_weight: d.payload.get("complexity_weight").and_then(|v| v.as_f64()).unwrap_or(0.1) as f32,
            adaptation_weight: d.payload.get("adaptation_weight").and_then(|v| v.as_f64()).unwrap_or(0.1) as f32,
            efficiency_weight: d.payload.get("efficiency_weight").and_then(|v| v.as_f64()).unwrap_or(0.2) as f32,
        };
        if let Ok(mut o) = self.active_overrides.write() { o.fitness_weights = Some(weights); }
        DirectiveResult::applied("fitness_weights", "Adjusted")
    }

    fn apply_exploration_strategy(&self, d: &NeuralDirective) -> DirectiveResult {
        let strategy_str = d.payload.get("strategy").and_then(|v| v.as_str()).unwrap_or("fitness_proportional");

        let strategy = match strategy_str {
            "novelty_search" => ExplorationStrategy::NoveltySearch {
                novelty_threshold: d.payload.get("novelty_threshold").and_then(|v| v.as_f64()).unwrap_or(0.3) as f32,
            },
            "quality_diversity" => ExplorationStrategy::QualityDiversity {
                archive_size: d.payload.get("archive_size").and_then(|v| v.as_u64()).unwrap_or(100) as usize,
            },
            "exploration_burst" => ExplorationStrategy::ExplorationBurst {
                duration_generations: d.payload.get("duration_generations").and_then(|v| v.as_u64()).unwrap_or(10),
            },
            "exploitation" => ExplorationStrategy::Exploitation {
                top_k: d.payload.get("top_k").and_then(|v| v.as_u64()).unwrap_or(5) as usize,
            },
            _ => ExplorationStrategy::FitnessProportional,
        };

        if let Ok(mut o) = self.active_overrides.write() { o.exploration_strategy = Some(strategy); }
        DirectiveResult::applied("exploration_strategy", strategy_str)
    }

    // ═══════════════════════════════════════════════════════════════
    // QUERY INTERFACE — For evolution manager to read directives
    // ═══════════════════════════════════════════════════════════════

    /// Get the current architecture target.
    pub fn get_architecture_target(&self) -> Option<ArchitectureTarget> {
        self.active_overrides.read().ok().and_then(|o| o.architecture_target.clone())
    }

    /// Get evolution parameter adjustments.
    pub fn get_evolution_params(&self) -> Option<EvolutionParamAdjustment> {
        self.active_overrides.read().ok().and_then(|o| o.evolution_params.clone())
    }

    /// Get plasticity rules.
    pub fn get_plasticity_rules(&self) -> Option<PlasticityRules> {
        self.active_overrides.read().ok().and_then(|o| o.plasticity_rules.clone())
    }

    /// Get fitness weights.
    pub fn get_fitness_weights(&self) -> Option<FitnessWeights> {
        self.active_overrides.read().ok().and_then(|o| o.fitness_weights.clone())
    }

    /// Get exploration strategy.
    pub fn get_exploration_strategy(&self) -> Option<ExplorationStrategy> {
        self.active_overrides.read().ok().and_then(|o| o.exploration_strategy.clone())
    }

    /// Drain the event buffer (called by the gRPC sender).
    pub fn drain_events(&self) -> Vec<NeuralLearningEvent> {
        if let Ok(mut buffer) = self.event_buffer.lock() {
            std::mem::take(&mut *buffer)
        } else {
            Vec::new()
        }
    }

    /// Enqueue a directive from the learning service.
    pub fn enqueue_directive(&self, directive: NeuralDirective) {
        if let Ok(mut queue) = self.directive_queue.write() {
            queue.push(directive);
            if let Ok(mut m) = self.metrics.write() {
                m.directives_received += 1;
            }
        }
    }

    /// Get bridge metrics.
    pub fn get_metrics(&self) -> BridgeMetrics {
        self.metrics.read().map(|m| m.clone()).unwrap_or_default()
    }

    /// Check if connected to the learning service.
    pub fn is_connected(&self) -> bool {
        self.connected.load(Ordering::Relaxed)
    }

    /// Set connection state.
    pub fn set_connected(&self, connected: bool) {
        self.connected.store(connected, Ordering::Relaxed);
    }
}

// ═══════════════════════════════════════════════════════════════════
// HELPER
// ═══════════════════════════════════════════════════════════════════

/// Simple ID generator (no external dependency needed).
fn rand_id() -> u32 {
    let t = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .subsec_nanos();
    t.wrapping_mul(2654435761) // Knuth multiplicative hash
}
