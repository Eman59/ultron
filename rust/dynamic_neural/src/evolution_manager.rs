//! Evolution Manager - Neural architecture evolution and optimization

use crate::neural_types::*;
use anyhow::{Context, Result};
use rand::{Rng, SeedableRng};
use rand_chacha::ChaCha8Rng;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use tracing::{debug, info};

/// Manager for evolving neural architectures
pub struct EvolutionManager {
    population: Vec<NeuralMesh>,
    current_generation: u64,
    rng: ChaCha8Rng,
    config: EvolutionConfig,
    best_performers: Vec<EvolutionRecord>,
    mutation_rates: MutationRates,
}

/// Configuration for evolution manager
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvolutionConfig {
    pub population_size: usize,
    pub elite_size: usize,
    pub crossover_rate: f32,
    pub mutation_rate: f32,
    pub max_generations: u64,
    pub fitness_target: f32,
    pub diversity_threshold: f32,
    pub enable_novelty_search: bool,
    pub complexity_penalty: f32,
}

impl Default for EvolutionConfig {
    fn default() -> Self {
        Self {
            population_size: 50,
            elite_size: 5,
            crossover_rate: 0.7,
            mutation_rate: 0.1,
            max_generations: 1000,
            fitness_target: 0.9,
            diversity_threshold: 0.3,
            enable_novelty_search: true,
            complexity_penalty: 0.1,
        }
    }
}

/// Record of evolutionary performance
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvolutionRecord {
    pub generation: u64,
    pub mesh_id: u64,
    pub fitness_score: f32,
    pub complexity_score: f32,
    pub novelty_score: f32,
    pub adaptation_score: f32,
    pub architecture: NeuralArchitecture,
}

/// Neural architecture representation for evolution
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NeuralArchitecture {
    pub neuron_count: usize,
    pub connection_count: usize,
    pub connection_density: f32,
    pub average_plasticity: f32,
    pub activation_pattern: Vec<f32>,
}

/// Mutation rates for different evolutionary operations
#[derive(Debug, Clone)]
pub struct MutationRates {
    pub add_neuron: f32,
    pub remove_neuron: f32,
    pub add_connection: f32,
    pub remove_connection: f32,
    pub modify_strength: f32,
    pub modify_plasticity: f32,
    pub change_neuron_type: f32,
}

impl Default for MutationRates {
    fn default() -> Self {
        Self {
            add_neuron: 0.05,
            remove_neuron: 0.02,
            add_connection: 0.1,
            remove_connection: 0.05,
            modify_strength: 0.15,
            modify_plasticity: 0.08,
            change_neuron_type: 0.03,
        }
    }
}

impl EvolutionManager {
    /// Create a new evolution manager
    pub fn new(config: EvolutionConfig) -> Result<Self> {
        info!("Creating evolution manager with config: {:?}", config);
        
        let mut rng = ChaCha8Rng::seed_from_u64(42);
        let mut population = Vec::new();
        
        // Initialize population
        for i in 0..config.population_size {
            let mesh_config = NeuralConfig {
                initial_neurons: 500 + (i * 10) as usize,
                connection_density: 0.05 + (i as f32 * 0.01),
                ..NeuralConfig::default()
            };
            
            let mesh = NeuralMesh::new(mesh_config)?;
            population.push(mesh);
        }
        
        Ok(Self {
            population,
            current_generation: 0,
            rng,
            config,
            best_performers: Vec::new(),
            mutation_rates: MutationRates::default(),
        })
    }
    
    /// Run one evolutionary generation
    pub fn run_generation(&mut self) -> Result<EvolutionStats> {
        info!("Running generation {}", self.current_generation);
        
        // Evaluate fitness of all individuals
        let fitness_scores = self.evaluate_population()?;
        
        // Select parents for next generation
        let parents = self.select_parents(&fitness_scores)?;
        
        // Create offspring through crossover and mutation
        let offspring = self.create_offspring(&parents)?;
        
        // Form new population (elite + offspring)
        let new_population = self.form_new_population(offspring, &fitness_scores)?;
        
        // Update population
        self.population = new_population;
        
        // Calculate generation statistics
        let stats = self.calculate_generation_stats(&fitness_scores)?;
        
        // Update best performers
        self.update_best_performers(&fitness_scores)?;
        
        // Adjust mutation rates based on performance
        self.adjust_mutation_rates(&stats)?;
        
        self.current_generation += 1;
        
        debug!("Generation {} completed with avg fitness: {}", 
               self.current_generation - 1, stats.average_fitness);
        
        Ok(stats)
    }
    
    /// Run evolution until target fitness is reached
    pub fn evolve_until_target(&mut self) -> Result<EvolutionResult> {
        let mut best_fitness = 0.0;
        let mut stagnation_counter = 0;
        
        while self.current_generation < self.config.max_generations && best_fitness < self.config.fitness_target {
            let stats = self.run_generation()?;
            
            if stats.best_fitness > best_fitness {
                best_fitness = stats.best_fitness;
                stagnation_counter = 0;
                info!("New best fitness: {:.4}", best_fitness);
            } else {
                stagnation_counter += 1;
                
                if stagnation_counter > 50 {
                    info!("Stagnation detected - increasing exploration");
                    self.increase_exploration();
                    stagnation_counter = 0;
                }
            }
            
            // Early stopping if target reached
            if best_fitness >= self.config.fitness_target {
                break;
            }
        }
        
        let result = EvolutionResult {
            final_generation: self.current_generation,
            best_fitness,
            average_fitness: self.calculate_average_fitness()?,
            total_individuals_evaluated: self.current_generation * self.config.population_size as u64,
            best_architecture: self.get_best_architecture()?,
        };
        
        info!("Evolution completed: {:?}", result);
        
        Ok(result)
    }
    
    /// Get the best neural mesh from evolution
    pub fn get_best_mesh(&self) -> Option<&NeuralMesh> {
        if !self.best_performers.is_empty() {
            let best_id = self.best_performers.last().unwrap().mesh_id;
            self.population.get(best_id as usize)
        } else {
            None
        }
    }
    
    /// Export evolution history for analysis
    pub fn export_history(&self) -> Result<Vec<EvolutionRecord>> {
        Ok(self.best_performers.clone())
    }
    
    // Private helper methods
    
    fn evaluate_population(&mut self) -> Result<Vec<FitnessEvaluation>> {
        let mut evaluations = Vec::new();
        
        for (i, mesh) in self.population.iter_mut().enumerate() {
            // Use a simple pattern recognition task for fitness evaluation
            let inputs = vec![0.1, 0.2, 0.3, 0.4, 0.5];
            let expected_outputs = vec![0.5, 0.4, 0.3, 0.2, 0.1];
            
            let outputs = mesh.process(&inputs)?;
            
            // Calculate fitness based on accuracy
            let accuracy = self.calculate_accuracy(&outputs, &expected_outputs);
            
            // Calculate complexity
            let complexity = mesh.get_metrics().total_connections as f32 / 
                           mesh.get_metrics().total_neurons as f32;
            
            // Calculate novelty if enabled
            let novelty = if self.config.enable_novelty_search {
                self.calculate_novelty(mesh)?
            } else {
                0.0
            };
            
            // Calculate adaptation score
            let adaptation = mesh.get_metrics().plasticity_changes as f32 / 1000.0;
            
            // Combined fitness score with complexity penalty
            let fitness = accuracy * (1.0 - self.config.complexity_penalty * complexity)
                + 0.1 * novelty
                + 0.1 * adaptation;
            
            evaluations.push(FitnessEvaluation {
                individual_id: i,
                fitness,
                accuracy,
                complexity,
                novelty,
                adaptation,
            });
        }
        
        Ok(evaluations)
    }
    
    fn calculate_accuracy(&self, outputs: &[f32], expected: &[f32]) -> f32 {
        let mut total_error = 0.0;
        let min_len = outputs.len().min(expected.len());
        
        for i in 0..min_len {
            let error = (outputs[i] - expected[i]).abs();
            total_error += error;
        }
        
        if min_len > 0 {
            1.0 - (total_error / min_len as f32)
        } else {
            0.0
        }
    }
    
    fn calculate_novelty(&self, mesh: &NeuralMesh) -> Result<f32> {
        // Simple novelty calculation based on activation patterns
        let exports = mesh.export_architecture()?;
        
        if let Some(neurons) = exports.get("neurons") {
            if let serde_json::Value::Array(neuron_array) = neurons {
                let unique_activations: std::collections::HashSet<_> = neuron_array
                    .iter()
                    .filter_map(|n| {
                        if let serde_json::Value::Object(map) = n {
                            map.get("activation").and_then(|a| a.as_f64()).map(|a| (a * 100.0) as i32)
                        } else {
                            None
                        }
                    })
                    .collect();
                
                let novelty = unique_activations.len() as f32 / neuron_array.len() as f32;
                return Ok(novelty);
            }
        }
        
        Ok(0.0)
    }
    
    fn select_parents(&self, evaluations: &[FitnessEvaluation]) -> Result<Vec<usize>> {
        let mut parents = Vec::new();
        
        // Tournament selection
        for _ in 0..self.config.population_size {
            let tournament_size = 3;
            let mut tournament = Vec::new();
            
            for _ in 0..tournament_size {
                let idx = self.rng.gen_range(0..evaluations.len());
                tournament.push((idx, evaluations[idx].fitness));
            }
            
            tournament.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
            parents.push(tournament[0].0);
        }
        
        Ok(parents)
    }
    
    fn create_offspring(&mut self, parents: &[usize]) -> Result<Vec<NeuralMesh>> {
        let mut offspring = Vec::new();
        
        for i in 0..parents.len() / 2 {
            let parent1_idx = parents[i * 2];
            let parent2_idx = parents[i * 2 + 1];
            
            if self.rng.gen::<f32>() < self.config.crossover_rate {
                // Perform crossover
                let child = self.crossover(
                    &self.population[parent1_idx],
                    &self.population[parent2_idx],
                )?;
                offspring.push(child);
            } else {
                // Clone parent (with potential mutation)
                let mut child = self.clone_mesh(&self.population[parent1_idx])?;
                self.mutate_mesh(&mut child)?;
                offspring.push(child);
            }
        }
        
        Ok(offspring)
    }
    
    fn crossover(&self, parent1: &NeuralMesh, parent2: &NeuralMesh) -> Result<NeuralMesh> {
        // Simplified crossover: average connection strengths
        let child_config = NeuralConfig {
            initial_neurons: (parent1.get_metrics().total_neurons + 
                             parent2.get_metrics().total_neurons) / 2,
            connection_density: (parent1.get_metrics().total_connections as f32 / 
                               parent1.get_metrics().total_neurons as f32 +
                               parent2.get_metrics().total_connections as f32 / 
                               parent2.get_metrics().total_neurons as f32) / 2.0,
            ..NeuralConfig::default()
        };
        
        let child = NeuralMesh::new(child_config)?;
        Ok(child)
    }
    
    fn clone_mesh(&self, mesh: &NeuralMesh) -> Result<NeuralMesh> {
        // Create a new mesh with similar configuration
        let config = NeuralConfig {
            initial_neurons: mesh.get_metrics().total_neurons,
            connection_density: mesh.get_metrics().total_connections as f32 / 
                              mesh.get_metrics().total_neurons as f32,
            ..NeuralConfig::default()
        };
        
        NeuralMesh::new(config)
    }
    
    fn mutate_mesh(&mut self, mesh: &mut NeuralMesh) -> Result<()> {
        // Apply mutations based on mutation rates
        if self.rng.gen::<f32>() < self.mutation_rates.add_neuron {
            mesh.add_random_neurons(1)?;
        }
        
        if self.rng.gen::<f32>() < self.mutation_rates.remove_neuron {
            // Simplified: don't actually remove neurons in this implementation
        }
        
        if self.rng.gen::<f32>() < self.mutation_rates.modify_strength {
            // Would modify connection strengths in real implementation
        }
        
        Ok(())
    }
    
    fn form_new_population(
        &mut self,
        offspring: Vec<NeuralMesh>,
        evaluations: &[FitnessEvaluation],
    ) -> Result<Vec<NeuralMesh>> {
        let mut new_population = Vec::new();
        
        // Add elite individuals
        let mut elite_indices: Vec<_> = evaluations.iter().enumerate().collect();
        elite_indices.sort_by(|a, b| b.1.fitness.partial_cmp(&a.1.fitness).unwrap());
        
        for i in 0..self.config.elite_size.min(elite_indices.len()) {
            let mesh = self.clone_mesh(&self.population[elite_indices[i].0])?;
            new_population.push(mesh);
        }
        
        // Add offspring
        for child in offspring {
            new_population.push(child);
        }
        
        // Fill remaining slots with random individuals if needed
        while new_population.len() < self.config.population_size {
            let random_config = NeuralConfig {
                initial_neurons: self.rng.gen_range(100..1000),
                connection_density: self.rng.gen_range(0.01..0.5),
                ..NeuralConfig::default()
            };
            
            let random_mesh = NeuralMesh::new(random_config)?;
            new_population.push(random_mesh);
        }
        
        Ok(new_population)
    }
    
    fn calculate_generation_stats(&self, evaluations: &[FitnessEvaluation]) -> Result<EvolutionStats> {
        let total_fitness: f32 = evaluations.iter().map(|e| e.fitness).sum();
        let average_fitness = total_fitness / evaluations.len() as f32;
        
        let best_eval = evaluations.iter()
            .max_by(|a, b| a.fitness.partial_cmp(&b.fitness).unwrap())
            .unwrap();
        
        let worst_eval = evaluations.iter()
            .min_by(|a, b| a.fitness.partial_cmp(&b.fitness).unwrap())
            .unwrap();
        
        // Calculate diversity
        let fitness_std = self.calculate_fitness_std(evaluations);
        let diversity = fitness_std / average_fitness.max(0.001);
        
        Ok(EvolutionStats {
            generation: self.current_generation,
            best_fitness: best_eval.fitness,
            average_fitness,
            worst_fitness: worst_eval.fitness,
            diversity,
            complexity_score: best_eval.complexity,
            novelty_score: best_eval.novelty,
        })
    }
    
    fn calculate_fitness_std(&self, evaluations: &[FitnessEvaluation]) -> f32 {
        let mean: f32 = evaluations.iter().map(|e| e.fitness).sum::<f32>() / evaluations.len() as f32;
        let variance: f32 = evaluations.iter()
            .map(|e| (e.fitness - mean).powi(2))
            .sum::<f32>() / evaluations.len() as f32;
        variance.sqrt()
    }
    
    fn update_best_performers(&mut self, evaluations: &[FitnessEvaluation]) -> Result<()> {
        let best_idx = evaluations.iter()
            .enumerate()
            .max_by(|a, b| a.1.fitness.partial_cmp(&b.1.fitness).unwrap())
            .map(|(idx, _)| idx)
            .unwrap();
        
        let best_eval = &evaluations[best_idx];
        
        let architecture = NeuralArchitecture {
            neuron_count: self.population[best_idx].get_metrics().total_neurons,
            connection_count: self.population[best_idx].get_metrics().total_connections,
            connection_density: best_eval.complexity,
            average_plasticity: 0.1, // Simplified
            activation_pattern: vec![0.5], // Simplified
        };
        
        let record = EvolutionRecord {
            generation: self.current_generation,
            mesh_id: best_idx as u64,
            fitness_score: best_eval.fitness,
            complexity_score: best_eval.complexity,
            novelty_score: best_eval.novelty,
            adaptation_score: best_eval.adaptation,
            architecture,
        };
        
        self.best_performers.push(record);
        
        // Keep only recent best performers
        if self.best_performers.len() > 100 {
            self.best_performers.remove(0);
        }
        
        Ok(())
    }
    
    fn adjust_mutation_rates(&mut self, stats: &EvolutionStats) -> Result<()> {
        // Adjust mutation rates based on diversity
        if stats.diversity < self.config.diversity_threshold {
            // Low diversity - increase mutation for exploration
            self.mutation_rates.add_neuron *= 1.1;
            self.mutation_rates.modify_strength *= 1.05;
            debug!("Increased mutation rates due to low diversity");
        } else if stats.diversity > 0.5 {
            // High diversity - decrease mutation for exploitation
            self.mutation_rates.add_neuron *= 0.9;
            self.mutation_rates.modify_strength *= 0.95;
            debug!("Decreased mutation rates due to high diversity");
        }
        
        // Clamp mutation rates
        self.mutation_rates.add_neuron = self.mutation_rates.add_neuron.clamp(0.01, 0.3);
        self.mutation_rates.modify_strength = self.mutation_rates.modify_strength.clamp(0.05, 0.5);
        
        Ok(())
    }
    
    fn calculate_average_fitness(&self) -> Result<f32> {
        let total: f32 = self.best_performers.iter().map(|r| r.fitness_score).sum();
        let average = total / self.best_performers.len().max(1) as f32;
        Ok(average)
    }
    
    fn get_best_architecture(&self) -> Result<NeuralArchitecture> {
        if let Some(best) = self.best_performers.last() {
            Ok(best.architecture.clone())
        } else {
            Ok(NeuralArchitecture {
                neuron_count: 500,
                connection_count: 2500,
                connection_density: 0.1,
                average_plasticity: 0.1,
                activation_pattern: vec![0.5],
            })
        }
    }
    
    fn increase_exploration(&mut self) {
        // Significantly increase mutation rates
        self.mutation_rates.add_neuron *= 1.5;
        self.mutation_rates.remove_neuron *= 1.5;
        self.mutation_rates.modify_strength *= 1.3;
        
        // Clamp to reasonable values
        self.mutation_rates.add_neuron = self.mutation_rates.add_neuron.clamp(0.05, 0.5);
        self.mutation_rates.remove_neuron = self.mutation_rates.remove_neuron.clamp(0.02, 0.3);
        self.mutation_rates.modify_strength = self.mutation_rates.modify_strength.clamp(0.1, 0.8);
        
        info!("Increased exploration with new mutation rates: {:?}", self.mutation_rates);
    }
}

/// Fitness evaluation for an individual
#[derive(Debug, Clone)]
struct FitnessEvaluation {
    individual_id: usize,
    fitness: f32,
    accuracy: f32,
    complexity: f32,
    novelty: f32,
    adaptation: f32,
}

/// Statistics for a generation
#[derive(Debug, Clone)]
pub struct EvolutionStats {
    pub generation: u64,
    pub best_fitness: f32,
    pub average_fitness: f32,
    pub worst_fitness: f32,
    pub diversity: f32,
    pub complexity_score: f32,
    pub novelty_score: f32,
}

/// Final evolution result
#[derive(Debug, Clone)]
pub struct EvolutionResult {
    pub final_generation: u64,
    pub best_fitness: f32,
    pub average_fitness: f32,
    pub total_individuals_evaluated: u64,
    pub best_architecture: NeuralArchitecture,
}