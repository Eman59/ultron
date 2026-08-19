//! Core neural types and structures for dynamic neural architecture

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Represents a neural connection between two neurons
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NeuralConnection {
    pub from: NeuronId,
    pub to: NeuronId,
    pub strength: ConnectionStrength,
    pub plasticity: f32, // How much this connection can change
    pub last_activated: u64, // Timestamp of last activation
    pub connection_type: ConnectionType,
}

/// Unique identifier for a neuron
#[derive(Debug, Clone, Copy, Hash, Eq, PartialEq, Serialize, Deserialize)]
pub struct NeuronId(pub u64);

/// Strength of a neural connection (0.0 to 1.0)
pub type ConnectionStrength = f32;

/// Type of neural connection
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum ConnectionType {
    Excitatory,      // Increases activation
    Inhibitory,      // Decreases activation
    Modulatory,      // Modulates other connections
    Plastic,         // Highly adaptable
    Stable,          // Resists change
}

/// Neural activation state
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NeuralState {
    pub neuron_id: NeuronId,
    pub activation: f32,
    pub threshold: f32,
    pub refractory_period: u32,
    pub last_fired: u64,
    pub neuron_type: NeuronType,
    pub position: NeuralPosition,
}

/// Type of neuron
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum NeuronType {
    Input,
    Hidden,
    Output,
    Memory,          // Maintains state over time
    Oscillator,      // Generates rhythmic patterns
    Integrator,      // Accumulates inputs over time
}

/// 3D position in neural space
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct NeuralPosition {
    pub x: f32,
    pub y: f32,
    pub z: f32,
}

/// Neural spike event
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NeuralSpike {
    pub source: NeuronId,
    pub target: NeuronId,
    pub strength: f32,
    pub timestamp: u64,
    pub spike_type: SpikeType,
}

/// Type of neural spike
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum SpikeType {
    Regular,
    Burst,
    Patterned,
    PlasticityTrigger,
}

/// Neural architecture configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NeuralConfig {
    pub initial_neurons: usize,
    pub connection_density: f32,
    pub plasticity_rate: f32,
    pub learning_rate: f32,
    pub decay_rate: f32,
    pub max_connections_per_neuron: usize,
    pub enable_quantum_simulation: bool,
    pub enable_real_time_adaptation: bool,
}

impl Default for NeuralConfig {
    fn default() -> Self {
        Self {
            initial_neurons: 1000,
            connection_density: 0.1,
            plasticity_rate: 0.05,
            learning_rate: 0.01,
            decay_rate: 0.001,
            max_connections_per_neuron: 50,
            enable_quantum_simulation: false,
            enable_real_time_adaptation: true,
        }
    }
}

/// Performance metrics for neural architecture
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NeuralMetrics {
    pub total_neurons: usize,
    pub total_connections: usize,
    pub average_activation: f32,
    pub plasticity_changes: u64,
    pub architecture_changes: u64,
    pub processing_latency_ms: f32,
    pub memory_usage_mb: f32,
}

/// Neural evolution statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvolutionStats {
    pub generation: u64,
    pub fitness_score: f32,
    pub complexity_score: f32,
    pub adaptation_score: f32,
    pub stability_score: f32,
    pub novelty_score: f32,
}

// ─── Plasticity event types (shared between neural_mesh & plasticity_engine) ───

/// Event recording a plasticity change
#[derive(Debug, Clone)]
pub struct PlasticityEvent {
    pub timestamp: u64,
    pub neuron_id: NeuronId,
    pub connection_change: ConnectionChange,
    pub reason: PlasticityReason,
}

/// Type of connection change recorded in a PlasticityEvent
#[derive(Debug, Clone)]
pub enum ConnectionChange {
    Added(NeuralConnection),
    Removed(NeuronId, NeuronId),
    Strengthened(NeuronId, NeuronId, f32),
    Weakened(NeuronId, NeuronId, f32),
}

/// Reason a plasticity change occurred
#[derive(Debug, Clone)]
pub enum PlasticityReason {
    HebbianLearning,
    SpikeTimingDependent,
    Homeostatic,
    Evolutionary,
    ExternalInput,
    PatternRecognition,
}

// ─── PartialEq for ConnectionType (needed for Applicability::SpecificTypes) ───
impl PartialEq for ConnectionType {
    fn eq(&self, other: &Self) -> bool {
        std::mem::discriminant(self) == std::mem::discriminant(other)
    }
}