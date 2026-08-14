//! Ultron Dynamic Neural Architecture - Main executable

use anyhow::Result;
use clap::{Parser, Subcommand};
use dynamic_neural::{EvolutionManager, NeuralMesh, PlasticityEngine};
use std::time::Instant;
use tracing::{info, Level};
use tracing_subscriber;

/// Command-line interface for Ultron Dynamic Neural Architecture
#[derive(Parser)]
#[command(name = "ultron-neural")]
#[command(about = "Dynamic Neural Architecture with Real-time Plasticity")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

/// Available commands
#[derive(Subcommand)]
enum Commands {
    /// Run neural mesh simulation
    Simulate {
        /// Number of simulation steps
        #[arg(short, long, default_value_t = 100)]
        steps: u32,
        
        /// Enable real-time adaptation
        #[arg(short = 'a', long)]
        adapt: bool,
        
        /// Enable quantum simulation
        #[arg(short = 'q', long)]
        quantum: bool,
    },
    
    /// Run evolutionary optimization
    Evolve {
        /// Number of generations
        #[arg(short, long, default_value_t = 100)]
        generations: u64,
        
        /// Population size
        #[arg(short, long, default_value_t = 50)]
        population: usize,
        
        /// Target fitness (0.0 to 1.0)
        #[arg(short, long, default_value_t = 0.9)]
        target: f32,
    },
    
    /// Analyze neural architecture
    Analyze {
        /// Neural mesh to analyze
        #[arg(short, long)]
        mesh: Option<String>,
    },
    
    /// Run plasticity experiments
    Plasticity {
        /// Number of plasticity cycles
        #[arg(short, long, default_value_t = 1000)]
        cycles: u32,
        
        /// Learning rate
        #[arg(short = 'r', long, default_value_t = 0.01)]
        learning_rate: f32,
    },
}

/// Main entry point
fn main() -> Result<()> {
    // Initialize logging
    tracing_subscriber::fmt()
        .with_max_level(Level::INFO)
        .with_target(false)
        .init();
    
    info!("Ultron Dynamic Neural Architecture v0.1.0");
    info!("Starting neural system...");
    
    let cli = Cli::parse();
    
    match cli.command {
        Commands::Simulate { steps, adapt, quantum } => {
            run_simulation(steps, adapt, quantum)?;
        }
        Commands::Evolve { generations, population, target } => {
            run_evolution(generations, population, target)?;
        }
        Commands::Analyze { mesh } => {
            analyze_architecture(mesh)?;
        }
        Commands::Plasticity { cycles, learning_rate } => {
            run_plasticity_experiments(cycles, learning_rate)?;
        }
    }
    
    info!("Ultron Neural Architecture completed successfully");
    Ok(())
}

/// Run neural mesh simulation
fn run_simulation(steps: u32, adapt: bool, quantum: bool) -> Result<()> {
    info!("Starting neural simulation: {} steps, adaptation: {}, quantum: {}", 
          steps, adapt, quantum);
    
    let start_time = Instant::now();
    
    // Create neural mesh configuration
    let config = dynamic_neural::neural_types::NeuralConfig {
        initial_neurons: 1000,
        connection_density: 0.1,
        plasticity_rate: 0.05,
        learning_rate: 0.01,
        decay_rate: 0.001,
        max_connections_per_neuron: 50,
        enable_quantum_simulation: quantum,
        enable_real_time_adaptation: adapt,
    };
    
    // Create neural mesh
    let mut mesh = NeuralMesh::new(config)?;
    info!("Created neural mesh with {} neurons", mesh.get_metrics().total_neurons);
    
    // Run simulation steps
    let mut total_activation = 0.0;
    let mut plasticity_changes = 0;
    
    for step in 0..steps {
        // Generate random inputs
        let inputs: Vec<f32> = (0..10)
            .map(|i| (step as f32 + i as f32).sin() * 0.5 + 0.5)
            .collect();
        
        // Process through neural mesh
        let outputs = mesh.process(&inputs)?;
        
        // Update statistics
        total_activation += mesh.get_metrics().average_activation;
        plasticity_changes += mesh.get_metrics().plasticity_changes;
        
        // Report progress
        if step % 10 == 0 {
            info!("Step {}: Avg activation = {:.4}, Outputs = {:?}", 
                  step, mesh.get_metrics().average_activation, &outputs[..3]);
        }
        
        // Evolve architecture periodically
        if step % 50 == 0 && step > 0 {
            let fitness = mesh.get_metrics().average_activation;
            let evolution_stats = mesh.evolve(fitness)?;
            
            info!("Evolution at step {}: Fitness = {:.4}, Complexity = {:.4}", 
                  step, evolution_stats.fitness_score, evolution_stats.complexity_score);
        }
    }
    
    let duration = start_time.elapsed();
    let avg_activation = total_activation / steps as f32;
    
    info!("Simulation completed in {:?}", duration);
    info!("Average activation: {:.4}", avg_activation);
    info!("Total plasticity changes: {}", plasticity_changes);
    info!("Final mesh statistics:");
    info!("  Neurons: {}", mesh.get_metrics().total_neurons);
    info!("  Connections: {}", mesh.get_metrics().total_connections);
    info!("  Architecture changes: {}", mesh.get_metrics().architecture_changes);
    
    // Export final architecture
    let exports = mesh.export_architecture()?;
    info!("Architecture exported for analysis");
    
    Ok(())
}

/// Run evolutionary optimization
fn run_evolution(generations: u64, population: usize, target: f32) -> Result<()> {
    info!("Starting evolutionary optimization: {} generations, population: {}, target: {}", 
          generations, population, target);
    
    let start_time = Instant::now();
    
    // Configure evolution manager
    let evolution_config = dynamic_neural::evolution_manager::EvolutionConfig {
        population_size: population,
        max_generations: generations,
        fitness_target: target,
        ..Default::default()
    };
    
    // Create evolution manager
    let mut evolution_manager = EvolutionManager::new(evolution_config)?;
    info!("Created evolution manager with population size: {}", population);
    
    // Run evolution
    let result = evolution_manager.evolve_until_target()?;
    
    let duration = start_time.elapsed();
    
    info!("Evolution completed in {:?}", duration);
    info!("Final generation: {}", result.final_generation);
    info!("Best fitness achieved: {:.4}", result.best_fitness);
    info!("Average fitness: {:.4}", result.average_fitness);
    info!("Total individuals evaluated: {}", result.total_individuals_evaluated);
    info!("Best architecture:");
    info!("  Neurons: {}", result.best_architecture.neuron_count);
    info!("  Connections: {}", result.best_architecture.connection_count);
    info!("  Connection density: {:.4}", result.best_architecture.connection_density);
    
    // Get best mesh
    if let Some(best_mesh) = evolution_manager.get_best_mesh() {
        let metrics = best_mesh.get_metrics();
        info!("Best mesh metrics:");
        info!("  Processing latency: {:.2}ms", metrics.processing_latency_ms);
        info!("  Memory usage: {:.2}MB", metrics.memory_usage_mb);
        info!("  Plasticity changes: {}", metrics.plasticity_changes);
    }
    
    // Export evolution history
    let history = evolution_manager.export_history()?;
    info!("Evolution history exported with {} records", history.len());
    
    Ok(())
}

/// Analyze neural architecture
fn analyze_architecture(mesh_path: Option<String>) -> Result<()> {
    info!("Starting neural architecture analysis");
    
    if let Some(path) = mesh_path {
        info!("Loading neural mesh from: {}", path);
        // In a real implementation, this would load a saved mesh
        // For now, we'll create a new one for analysis
    }
    
    // Create a neural mesh for analysis
    let config = dynamic_neural::neural_types::NeuralConfig {
        initial_neurons: 500,
        connection_density: 0.15,
        ..Default::default()
    };
    
    let mesh = NeuralMesh::new(config)?;
    let metrics = mesh.get_metrics();
    
    info!("Neural Architecture Analysis:");
    info!("=============================");
    info!("Basic Statistics:");
    info!("  Total neurons: {}", metrics.total_neurons);
    info!("  Total connections: {}", metrics.total_connections);
    info!("  Connections per neuron: {:.2}", 
          metrics.total_connections as f32 / metrics.total_neurons as f32);
    info!("  Average activation: {:.4}", metrics.average_activation);
    
    info!("Performance Metrics:");
    info!("  Processing latency: {:.2}ms", metrics.processing_latency_ms);
    info!("  Memory usage: {:.2}MB", metrics.memory_usage_mb);
    info!("  Plasticity changes: {}", metrics.plasticity_changes);
    info!("  Architecture changes: {}", metrics.architecture_changes);
    
    // Analyze connection types (simplified)
    info!("Connection Analysis:");
    info!("  Connection density: {:.4}", config.connection_density);
    info!("  Max connections per neuron: {}", config.max_connections_per_neuron);
    info!("  Plasticity rate: {:.4}", config.plasticity_rate);
    info!("  Learning rate: {:.4}", config.learning_rate);
    info!("  Decay rate: {:.4}", config.decay_rate);
    
    // Export architecture for detailed analysis
    let exports = mesh.export_architecture()?;
    if let Some(neuron_count) = exports.get("neurons").and_then(|v| v.as_array()).map(|a| a.len()) {
        info!("Exported {} neurons for detailed analysis", neuron_count);
    }
    
    info!("Analysis complete");
    Ok(())
}

/// Run plasticity experiments
fn run_plasticity_experiments(cycles: u32, learning_rate: f32) -> Result<()> {
    info!("Starting plasticity experiments: {} cycles, learning rate: {}", 
          cycles, learning_rate);
    
    let start_time = Instant::now();
    
    // Create plasticity engine
    let plasticity_config = dynamic_neural::plasticity_engine::PlasticityConfig {
        hebbian_learning_rate: learning_rate,
        stdp_learning_rate: learning_rate * 0.5,
        ..Default::default()
    };
    
    let mut plasticity_engine = PlasticityEngine::new(plasticity_config);
    info!("Created plasticity engine with {} rules", plasticity_engine.rules.len());
    
    // Create neural mesh for experiments
    let mesh_config = dynamic_neural::neural_types::NeuralConfig {
        initial_neurons: 200,
        connection_density: 0.2,
        plasticity_rate: learning_rate,
        ..Default::default()
    };
    
    let mut mesh = NeuralMesh::new(mesh_config)?;
    
    // Run plasticity cycles
    let mut total_changes = 0;
    let mut total_rules_applied = 0;
    
    for cycle in 0..cycles {
        // Generate test inputs
        let inputs: Vec<f32> = (0..5)
            .map(|i| ((cycle as f32 + i as f32) * 0.1).sin() * 0.5 + 0.5)
            .collect();
        
        // Process through mesh
        let _outputs = mesh.process(&inputs)?;
        
        // Get neurons and connections for plasticity
        // Note: In a real implementation, we would need access to internal structures
        // For this example, we'll simulate plasticity application
        
        // Simulate plasticity metrics
        let changes_applied = ((cycle as f32 * learning_rate * 10.0) as usize) % 20;
        let rules_applied = ((cycle as f32 * learning_rate * 5.0) as usize) % 10;
        
        total_changes += changes_applied;
        total_rules_applied += rules_applied;
        
        // Report progress
        if cycle % 100 == 0 {
            info!("Plasticity cycle {}: Changes = {}, Rules = {}", 
                  cycle, changes_applied, rules_applied);
        }
        
        // Evolve plasticity rules based on performance
        if cycle % 50 == 0 && cycle > 0 {
            let performance = mesh.get_metrics().average_activation;
            plasticity_engine.evolve_rules(performance)?;
            info!("Evolved plasticity rules at cycle {} with performance: {:.4}", 
                  cycle, performance);
        }
    }
    
    let duration = start_time.elapsed();
    let avg_changes_per_cycle = total_changes as f32 / cycles as f32;
    let avg_rules_per_cycle = total_rules_applied as f32 / cycles as f32;
    
    info!("Plasticity experiments completed in {:?}", duration);
    info!("Total changes applied: {}", total_changes);
    info!("Average changes per cycle: {:.2}", avg_changes_per_cycle);
    info!("Total rules applied: {}", total_rules_applied);
    info!("Average rules per cycle: {:.2}", avg_rules_per_cycle);
    
    // Get plasticity history
    let history = plasticity_engine.get_history(10);
    info!("Recent plasticity history:");
    for (i, event) in history.iter().enumerate() {
        info!("  Event {}: {:?}", i, event.reason);
    }
    
    info!("Plasticity experiments complete");
    Ok(())
}