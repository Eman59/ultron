//! Dynamic Neural Architecture Library
//!
//! This module implements a neural network system that can adapt its structure
//! in real-time, featuring weightless connections, dynamic topology evolution,
//! and memory-efficient neural representation.

pub mod neural_mesh;
pub mod plasticity_engine;
pub mod evolution_manager;
pub mod quantum_simulator;
pub mod neural_types;
pub mod learning_bridge;
pub mod hot_swap;

pub use neural_mesh::NeuralMesh;
pub use plasticity_engine::PlasticityEngine;
pub use evolution_manager::EvolutionManager;
pub use quantum_simulator::QuantumSimulator;
pub use learning_bridge::LearningBridge;
pub use hot_swap::HotSwapEngine;

/// Re-exports for common neural types
pub mod prelude {
    pub use super::neural_types::*;
    pub use super::NeuralMesh;
    pub use super::PlasticityEngine;
    pub use super::EvolutionManager;
    pub use super::QuantumSimulator;
}