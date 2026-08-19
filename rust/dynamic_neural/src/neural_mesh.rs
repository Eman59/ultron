//! Neural Mesh - Dynamic neural network with real-time plasticity

use crate::neural_types::*;
use anyhow::Result;
use rand::{Rng, SeedableRng};
use rand_chacha::ChaCha8Rng;
use std::collections::{HashMap, HashSet};
use tracing::{debug, info};

/// Main neural mesh structure that manages dynamic neural networks
pub struct NeuralMesh {
    neurons: HashMap<NeuronId, NeuralState>,
    connections: HashMap<NeuronId, Vec<NeuralConnection>>,
    config: NeuralConfig,
    rng: ChaCha8Rng,
    metrics: NeuralMetrics,
    plasticity_history: Vec<PlasticityEvent>,
}

impl NeuralMesh {
    /// Create a new neural mesh with the given configuration
    pub fn new(config: NeuralConfig) -> Result<Self> {
        info!("Creating neural mesh with config: {:?}", config);
        
        let mut rng = ChaCha8Rng::seed_from_u64(42);
        let mut neurons = HashMap::new();
        let mut connections = HashMap::new();
        
        // Initialize neurons
        for i in 0..config.initial_neurons {
            let neuron_id = NeuronId(i as u64);
            let neuron_type = match i {
                i if i < config.initial_neurons / 10 => NeuronType::Input,
                i if i > config.initial_neurons * 9 / 10 => NeuronType::Output,
                _ => NeuronType::Hidden,
            };
            
            let position = NeuralPosition {
                x: rng.gen_range(-1.0..1.0),
                y: rng.gen_range(-1.0..1.0),
                z: rng.gen_range(-1.0..1.0),
            };
            
            neurons.insert(neuron_id, NeuralState {
                neuron_id,
                activation: 0.0,
                threshold: rng.gen_range(0.3..0.7),
                refractory_period: 10,
                last_fired: 0,
                neuron_type,
                position,
            });
        }
        
        // Create initial connections
        for neuron_id in neurons.keys().copied().collect::<Vec<_>>() {
            let neuron_connections = Self::create_initial_connections(
                &neurons, neuron_id, &config, &mut rng
            );
            connections.insert(neuron_id, neuron_connections);
        }
        
        let metrics = NeuralMetrics {
            total_neurons: config.initial_neurons,
            total_connections: connections.values().map(|c| c.len()).sum(),
            average_activation: 0.0,
            plasticity_changes: 0,
            architecture_changes: 0,
            processing_latency_ms: 0.0,
            memory_usage_mb: 0.0,
        };
        
        Ok(Self {
            neurons,
            connections,
            config,
            rng,
            metrics,
            plasticity_history: Vec::new(),
        })
    }
    
    /// Process input through the neural mesh
    pub fn process(&mut self, inputs: &[f32]) -> Result<Vec<f32>> {
        let start_time = std::time::Instant::now();
        
        // Apply inputs to input neurons
        self.apply_inputs(inputs)?;
        
        // Propagate activation through the network
        self.propagate_activation()?;
        
        // Apply plasticity rules
        if self.config.enable_real_time_adaptation {
            self.apply_plasticity()?;
        }
        
        // Get outputs from output neurons
        let outputs = self.get_outputs();
        
        // Update metrics
        let latency = start_time.elapsed().as_millis() as f32;
        self.metrics.processing_latency_ms = latency;
        self.metrics.average_activation = self.calculate_average_activation();
        
        debug!("Processed inputs -> outputs in {}ms", latency);
        
        Ok(outputs)
    }
    
    /// Evolve the neural architecture
    pub fn evolve(&mut self, fitness_score: f32) -> Result<EvolutionStats> {
        info!("Evolving neural architecture with fitness: {}", fitness_score);
        
        let mut stats = EvolutionStats {
            generation: 0,
            fitness_score,
            complexity_score: self.calculate_complexity(),
            adaptation_score: self.calculate_adaptation(),
            stability_score: self.calculate_stability(),
            novelty_score: self.calculate_novelty(),
        };
        
        // Evolutionary operations
        if fitness_score > 0.7 {
            self.add_random_neurons(10)?;
            stats.complexity_score += 0.1;
        }
        
        if fitness_score < 0.3 {
            self.prune_weak_connections(0.1)?;
            stats.stability_score += 0.1;
        }
        
        // Update connections based on performance
        self.optimize_connections()?;
        
        self.metrics.architecture_changes += 1;
        
        Ok(stats)
    }
    
    /// Get current neural metrics
    pub fn get_metrics(&self) -> &NeuralMetrics {
        &self.metrics
    }
    
    /// Export neural architecture for analysis
    pub fn export_architecture(&self) -> Result<HashMap<String, serde_json::Value>> {
        let mut export = HashMap::new();
        
        // Export neuron data
        let neurons: Vec<_> = self.neurons.values()
            .map(|n| serde_json::to_value(n).unwrap())
            .collect();
        export.insert("neurons".to_string(), serde_json::Value::Array(neurons));
        
        // Export connection data (simplified)
        let total_connections: usize = self.connections.values().map(|c| c.len()).sum();
        export.insert("total_connections".to_string(), total_connections.into());
        
        // Export metrics
        export.insert("metrics".to_string(), serde_json::to_value(&self.metrics).unwrap());
        
        Ok(export)
    }
    
    // Private helper methods
    
    fn create_initial_connections(
        neurons: &HashMap<NeuronId, NeuralState>,
        source_id: NeuronId,
        config: &NeuralConfig,
        rng: &mut ChaCha8Rng,
    ) -> Vec<NeuralConnection> {
        let mut connections = Vec::new();
        let source_neuron = neurons.get(&source_id).unwrap();
        
        for target_id in neurons.keys().copied().collect::<Vec<_>>() {
            if source_id == target_id {
                continue;
            }
            
            // Random connection based on density
            if rng.gen::<f32>() < config.connection_density {
                let target_neuron = neurons.get(&target_id).unwrap();
                
                // Calculate distance-based connection strength
                let distance = Self::calculate_distance(&source_neuron.position, &target_neuron.position);
                let strength = 1.0 / (1.0 + distance);
                
                let connection_type = match rng.gen_range(0..5) {
                    0 => ConnectionType::Excitatory,
                    1 => ConnectionType::Inhibitory,
                    2 => ConnectionType::Modulatory,
                    3 => ConnectionType::Plastic,
                    _ => ConnectionType::Stable,
                };
                
                connections.push(NeuralConnection {
                    from: source_id,
                    to: target_id,
                    strength,
                    plasticity: rng.gen_range(0.01..0.1),
                    last_activated: 0,
                    connection_type,
                });
            }
        }
        
        // Limit connections per neuron
        if connections.len() > config.max_connections_per_neuron {
            connections.truncate(config.max_connections_per_neuron);
        }
        
        connections
    }
    
    fn calculate_distance(a: &NeuralPosition, b: &NeuralPosition) -> f32 {
        ((a.x - b.x).powi(2) + (a.y - b.y).powi(2) + (a.z - b.z).powi(2)).sqrt()
    }
    
    fn apply_inputs(&mut self, inputs: &[f32]) -> Result<()> {
        let input_neurons: Vec<_> = self.neurons.values()
            .filter(|n| matches!(n.neuron_type, NeuronType::Input))
            .map(|n| n.neuron_id)
            .collect();
        
        for (i, &neuron_id) in input_neurons.iter().enumerate() {
            if i < inputs.len() {
                if let Some(neuron) = self.neurons.get_mut(&neuron_id) {
                    neuron.activation = inputs[i];
                }
            }
        }
        
        Ok(())
    }
    
    fn propagate_activation(&mut self) -> Result<()> {
        let now_ms = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_millis() as u64;

        // Collect firing neurons first (avoids simultaneous mut + immut borrow)
        let firing: Vec<(NeuronId, f32)> = self.neurons
            .iter()
            .filter(|(_, s)| s.activation > s.threshold)
            .map(|(id, s)| (*id, s.activation))
            .collect();

        // Collect propagation targets: (target_id, activation_delta)
        let mut deltas: Vec<(NeuronId, f32)> = Vec::new();
        let mut update_timestamps: Vec<(NeuronId, NeuronId)> = Vec::new();

        for (src_id, src_act) in &firing {
            if let Some(conns) = self.connections.get(src_id) {
                for conn in conns {
                    deltas.push((conn.to, src_act * conn.strength));
                    update_timestamps.push((*src_id, conn.to));
                }
            }
        }

        // Apply deltas to target neurons
        for (target_id, delta) in deltas {
            if let Some(n) = self.neurons.get_mut(&target_id) {
                n.activation += delta;
            }
        }

        // Update last_fired on firing neurons and reset activation
        for (src_id, _) in &firing {
            if let Some(n) = self.neurons.get_mut(src_id) {
                n.last_fired = now_ms;
                n.activation = 0.0;
            }
        }

        // Stamp last_activated on connections that fired
        for (src_id, tgt_id) in update_timestamps {
            if let Some(conns) = self.connections.get_mut(&src_id) {
                if let Some(conn) = conns.iter_mut().find(|c| c.to == tgt_id) {
                    conn.last_activated = now_ms;
                }
            }
        }

        Ok(())
    }
    
    fn apply_plasticity(&mut self) -> Result<()> {
        let current_time = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_millis() as u64;

        let learning_rate = self.config.learning_rate;
        let decay_rate = self.config.decay_rate;
        let mut events: Vec<PlasticityEvent> = Vec::new();

        for conns in self.connections.values_mut() {
            for conn in conns.iter_mut() {
                if conn.last_activated > 0 {
                    // Hebbian: strengthen recently used connections
                    conn.strength += learning_rate * conn.plasticity;
                    conn.strength = conn.strength.clamp(0.0, 1.0);

                    events.push(PlasticityEvent {
                        timestamp: conn.last_activated,
                        neuron_id: conn.from,
                        connection_change: ConnectionChange::Strengthened(
                            conn.from,
                            conn.to,
                            conn.strength,
                        ),
                        reason: PlasticityReason::HebbianLearning,
                    });
                }

                // Decay idle connections
                if current_time.saturating_sub(conn.last_activated) > 1000 {
                    conn.strength -= decay_rate;
                    if conn.strength < 0.01 {
                        conn.strength = 0.0;
                    }
                }
            }
        }

        self.metrics.plasticity_changes += events.len() as u64;
        self.plasticity_history.extend(events);

        // Keep history bounded
        if self.plasticity_history.len() > 10_000 {
            self.plasticity_history.drain(0..5_000);
        }

        Ok(())
    }
    
    fn get_outputs(&self) -> Vec<f32> {
        self.neurons.values()
            .filter(|n| matches!(n.neuron_type, NeuronType::Output))
            .map(|n| n.activation)
            .collect()
    }
    
    fn calculate_average_activation(&self) -> f32 {
        let total: f32 = self.neurons.values().map(|n| n.activation).sum();
        total / self.neurons.len() as f32
    }
    
    pub fn add_random_neurons(&mut self, count: usize) -> Result<()> {
        let start_id = self.neurons.len() as u64;

        // First insert all new neurons
        for i in 0..count {
            let neuron_id = NeuronId(start_id + i as u64);
            let position = NeuralPosition {
                x: self.rng.gen_range(-1.0..1.0),
                y: self.rng.gen_range(-1.0..1.0),
                z: self.rng.gen_range(-1.0..1.0),
            };
            self.neurons.insert(neuron_id, NeuralState {
                neuron_id,
                activation: 0.0,
                threshold: self.rng.gen_range(0.3..0.7),
                refractory_period: 10,
                last_fired: 0,
                neuron_type: NeuronType::Hidden,
                position,
            });
        }

        // Then wire them (neurons map is fully populated now)
        let new_ids: Vec<NeuronId> = (0..count)
            .map(|i| NeuronId(start_id + i as u64))
            .collect();

        for neuron_id in new_ids {
            let connections = Self::create_initial_connections(
                &self.neurons, neuron_id, &self.config, &mut self.rng,
            );
            self.connections.insert(neuron_id, connections);
        }

        self.metrics.total_neurons += count;
        info!("Added {} new neurons to the mesh", count);

        Ok(())
    }
    
    pub fn prune_weak_connections(&mut self, threshold: f32) -> Result<()> {
        let mut pruned_count = 0;
        
        for connections in self.connections.values_mut() {
            let original_len = connections.len();
            connections.retain(|c| c.strength > threshold);
            pruned_count += original_len - connections.len();
        }
        
        self.metrics.total_connections -= pruned_count;
        info!("Pruned {} weak connections", pruned_count);
        
        Ok(())
    }
    
    fn optimize_connections(&mut self) -> Result<()> {
        // Simple optimization: strengthen strong connections, weaken weak ones
        for connections in self.connections.values_mut() {
            for connection in connections.iter_mut() {
                if connection.strength > 0.7 {
                    // Very strong connections become more stable
                    connection.plasticity *= 0.9;
                } else if connection.strength < 0.3 {
                    // Very weak connections become more plastic
                    connection.plasticity *= 1.1;
                }
                
                connection.plasticity = connection.plasticity.clamp(0.01, 0.5);
            }
        }
        
        Ok(())
    }
    
    fn calculate_complexity(&self) -> f32 {
        let total_connections = self.metrics.total_connections;
        let total_neurons = self.metrics.total_neurons;
        
        if total_neurons == 0 {
            return 0.0;
        }
        
        let connection_density = total_connections as f32 / total_neurons as f32;
        let normalized_density = connection_density / self.config.max_connections_per_neuron as f32;
        
        normalized_density
    }
    
    fn calculate_adaptation(&self) -> f32 {
        let recent_changes = self.plasticity_history.len().min(100);
        let change_rate = recent_changes as f32 / 100.0;
        
        change_rate.clamp(0.0, 1.0)
    }
    
    fn calculate_stability(&self) -> f32 {
        let avg_activation = self.metrics.average_activation;
        1.0 - (avg_activation - 0.5).abs() * 2.0
    }
    
    fn calculate_novelty(&self) -> f32 {
        // Simple novelty metric based on unique activation patterns
        let unique_activations = self.neurons.values()
            .map(|n| (n.activation * 10.0).round() as i32)
            .collect::<HashSet<_>>()
            .len();
        
        (unique_activations as f32 / self.neurons.len() as f32).clamp(0.0, 1.0)
    }
}