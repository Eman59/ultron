//! Plasticity Engine - Real-time neural adaptation algorithms

use crate::neural_types::*;
use anyhow::Result;
use rand::Rng;
use std::collections::HashMap;
use tracing::{debug, info};

/// Engine for managing neural plasticity and adaptation
pub struct PlasticityEngine {
    rules: Vec<PlasticityRule>,
    history: Vec<PlasticityEvent>,
    config: PlasticityConfig,
}

/// Configuration for plasticity engine
#[derive(Debug, Clone)]
pub struct PlasticityConfig {
    pub hebbian_learning_rate: f32,
    pub stdp_learning_rate: f32,  // Spike-timing dependent plasticity
    pub homeostatic_target: f32,
    pub max_plasticity_change: f32,
    pub enable_meta_plasticity: bool,
    pub plasticity_decay_rate: f32,
}

impl Default for PlasticityConfig {
    fn default() -> Self {
        Self {
            hebbian_learning_rate: 0.01,
            stdp_learning_rate: 0.005,
            homeostatic_target: 0.5,
            max_plasticity_change: 0.1,
            enable_meta_plasticity: true,
            plasticity_decay_rate: 0.001,
        }
    }
}

/// Plasticity rule for neural adaptation
#[derive(Debug, Clone)]
pub struct PlasticityRule {
    pub name: String,
    pub rule_type: RuleType,
    pub activation_condition: ActivationCondition,
    pub strength: f32,
    pub applicability: Applicability,
}

/// Type of plasticity rule
#[derive(Debug, Clone)]
pub enum RuleType {
    Hebbian,           // "Neurons that fire together, wire together"
    AntiHebbian,       // "Neurons out of sync, lose their link"
    STDP,             // Spike-timing dependent plasticity
    Homeostatic,      // Maintains stability
    Heterosynaptic,   // Balances excitation and inhibition
    MetaPlasticity,   // Modifies plasticity of other rules
}

/// Condition for rule activation
#[derive(Debug, Clone)]
pub enum ActivationCondition {
    Always,
    WhenActivationAbove(f32),
    WhenActivationBelow(f32),
    WhenCorrelationAbove(f32, f32), // neuron1, neuron2, correlation threshold
    WhenFrequencyAbove(f32),        // firing frequency threshold
    PatternDetected(String),        // specific activation pattern
}

/// Applicability of rule
#[derive(Debug, Clone)]
pub enum Applicability {
    AllConnections,
    ExcitatoryOnly,
    InhibitoryOnly,
    PlasticOnly,
    SpecificTypes(Vec<ConnectionType>),
    DistanceBased(f32), // maximum distance between neurons
}

impl PlasticityEngine {
    /// Create a new plasticity engine with default rules
    pub fn new(config: PlasticityConfig) -> Self {
        info!("Creating plasticity engine with config: {:?}", config);
        
        let rules = Self::create_default_rules(&config);
        
        Self {
            rules,
            history: Vec::new(),
            config,
        }
    }
    
    /// Apply plasticity rules to neural connections
    pub fn apply_plasticity(
        &mut self,
        neurons: &HashMap<NeuronId, NeuralState>,
        connections: &mut HashMap<NeuronId, Vec<NeuralConnection>>,
    ) -> Result<PlasticityMetrics> {
        let mut metrics = PlasticityMetrics::default();
        
        for rule in &self.rules {
            let changes = self.apply_rule(rule, neurons, connections)?;
            metrics.changes_applied += changes;
            metrics.rules_applied += 1;
        }
        
        // Apply meta-plasticity if enabled
        if self.config.enable_meta_plasticity {
            self.apply_meta_plasticity(&mut metrics)?;
        }
        
        // Record plasticity event
        self.history.push(PlasticityEvent {
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_millis() as u64,
            neuron_id: NeuronId(0),
            connection_change: ConnectionChange::Strengthened(NeuronId(0), NeuronId(1), 0.0),
            reason: PlasticityReason::PatternRecognition,
        });
        
        debug!("Applied plasticity: {} changes from {} rules", 
               metrics.changes_applied, metrics.rules_applied);
        
        Ok(metrics)
    }
    
    /// Add a custom plasticity rule
    pub fn add_rule(&mut self, rule: PlasticityRule) {
        info!("Adding plasticity rule: {}", rule.name);
        self.rules.push(rule);
    }
    
    /// Get plasticity history for analysis
    pub fn get_history(&self, limit: usize) -> Vec<PlasticityEvent> {
        self.history.iter()
            .rev()
            .take(limit)
            .cloned()
            .collect()
    }
    
    /// Evolve plasticity rules based on performance
    pub fn evolve_rules(&mut self, performance_metric: f32) -> Result<()> {
        if performance_metric > 0.7 {
            // Good performance - strengthen effective rules
            for rule in &mut self.rules {
                rule.strength *= 1.1;
                rule.strength = rule.strength.clamp(0.01, 1.0);
            }
            info!("Strengthened plasticity rules due to good performance");
        } else if performance_metric < 0.3 {
            // Poor performance - weaken rules and add exploration
            for rule in &mut self.rules {
                rule.strength *= 0.9;
                rule.strength = rule.strength.clamp(0.01, 1.0);
            }
            
            // Add exploratory rule
            self.add_exploratory_rule();
            info!("Weakened rules and added exploratory rule due to poor performance");
        }
        
        Ok(())
    }
    
    // Private helper methods
    
    fn create_default_rules(config: &PlasticityConfig) -> Vec<PlasticityRule> {
        vec![
            PlasticityRule {
                name: "Hebbian Learning".to_string(),
                rule_type: RuleType::Hebbian,
                activation_condition: ActivationCondition::WhenCorrelationAbove(0.7, 0.7),
                strength: config.hebbian_learning_rate,
                applicability: Applicability::AllConnections,
            },
            PlasticityRule {
                name: "STDP Learning".to_string(),
                rule_type: RuleType::STDP,
                activation_condition: ActivationCondition::WhenFrequencyAbove(10.0),
                strength: config.stdp_learning_rate,
                applicability: Applicability::ExcitatoryOnly,
            },
            PlasticityRule {
                name: "Homeostatic Regulation".to_string(),
                rule_type: RuleType::Homeostatic,
                activation_condition: ActivationCondition::WhenActivationAbove(0.8),
                strength: 0.02,
                applicability: Applicability::AllConnections,
            },
            PlasticityRule {
                name: "Anti-Hebbian Exploration".to_string(),
                rule_type: RuleType::AntiHebbian,
                activation_condition: ActivationCondition::WhenActivationBelow(0.2),
                strength: 0.005,
                applicability: Applicability::PlasticOnly,
            },
        ]
    }
    
    fn apply_rule(
        &self,
        rule: &PlasticityRule,
        neurons: &HashMap<NeuronId, NeuralState>,
        connections: &mut HashMap<NeuronId, Vec<NeuralConnection>>,
    ) -> Result<usize> {
        let mut changes_applied = 0;
        
        // Check if rule should be activated
        if !self.should_activate_rule(rule, neurons) {
            return Ok(0);
        }
        
        // Apply rule to applicable connections
        for (neuron_id, neuron_connections) in connections.iter_mut() {
            for connection in neuron_connections.iter_mut() {
                if self.is_connection_applicable(rule, connection, neurons) {
                    self.apply_rule_to_connection(rule, connection);
                    changes_applied += 1;
                }
            }
        }
        
        Ok(changes_applied)
    }
    
    fn should_activate_rule(
        &self,
        rule: &PlasticityRule,
        neurons: &HashMap<NeuronId, NeuralState>,
    ) -> bool {
        match &rule.activation_condition {
            ActivationCondition::Always => true,
            ActivationCondition::WhenActivationAbove(threshold) => {
                neurons.values().any(|n| n.activation > *threshold)
            }
            ActivationCondition::WhenActivationBelow(threshold) => {
                neurons.values().any(|n| n.activation < *threshold)
            }
            ActivationCondition::WhenCorrelationAbove(neuron1_thresh, neuron2_thresh) => {
                // Simplified correlation check
                neurons.values().any(|n| n.activation > *neuron1_thresh) &&
                neurons.values().any(|n| n.activation > *neuron2_thresh)
            }
            ActivationCondition::WhenFrequencyAbove(_) => {
                // Frequency calculation would require tracking over time
                true // simplified
            }
            ActivationCondition::PatternDetected(_) => {
                // Pattern detection would require more complex logic
                true // simplified
            }
        }
    }
    
    fn is_connection_applicable(
        &self,
        rule: &PlasticityRule,
        connection: &NeuralConnection,
        neurons: &HashMap<NeuronId, NeuralState>,
    ) -> bool {
        match &rule.applicability {
            Applicability::AllConnections => true,
            Applicability::ExcitatoryOnly => {
                matches!(connection.connection_type, ConnectionType::Excitatory)
            }
            Applicability::InhibitoryOnly => {
                matches!(connection.connection_type, ConnectionType::Inhibitory)
            }
            Applicability::PlasticOnly => {
                matches!(connection.connection_type, ConnectionType::Plastic)
            }
            Applicability::SpecificTypes(types) => {
                types.contains(&connection.connection_type)
            }
            Applicability::DistanceBased(max_distance) => {
                if let (Some(from_neuron), Some(to_neuron)) = 
                    (neurons.get(&connection.from), neurons.get(&connection.to)) 
                {
                    let distance = ((from_neuron.position.x - to_neuron.position.x).powi(2) +
                                   (from_neuron.position.y - to_neuron.position.y).powi(2) +
                                   (from_neuron.position.z - to_neuron.position.z).powi(2)).sqrt();
                    distance <= *max_distance
                } else {
                    false
                }
            }
        }
    }
    
    fn apply_rule_to_connection(&self, rule: &PlasticityRule, connection: &mut NeuralConnection) {
        let change_amount = rule.strength * connection.plasticity;
        
        match rule.rule_type {
            RuleType::Hebbian => {
                // Strengthen connection
                connection.strength += change_amount;
            }
            RuleType::AntiHebbian => {
                // Weaken connection
                connection.strength -= change_amount;
            }
            RuleType::STDP => {
                // Spike-timing dependent plasticity
                // Simplified: strengthen based on recent activation
                if connection.last_activated > 0 {
                    let time_since_activation = std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH)
                        .unwrap()
                        .as_millis() as u64 - connection.last_activated;
                    
                    if time_since_activation < 100 {
                        connection.strength += change_amount * 2.0;
                    } else {
                        connection.strength -= change_amount * 0.5;
                    }
                }
            }
            RuleType::Homeostatic => {
                // Adjust to maintain target activation
                if connection.strength > 0.5 {
                    connection.strength -= change_amount * 0.5;
                } else {
                    connection.strength += change_amount * 0.5;
                }
            }
            RuleType::Heterosynaptic => {
                // Balance excitation and inhibition
                match connection.connection_type {
                    ConnectionType::Excitatory => {
                        connection.strength -= change_amount * 0.3;
                    }
                    ConnectionType::Inhibitory => {
                        connection.strength += change_amount * 0.3;
                    }
                    _ => {}
                }
            }
            RuleType::MetaPlasticity => {
                // Modify plasticity of the connection itself
                connection.plasticity += change_amount * 0.1;
                connection.plasticity = connection.plasticity.clamp(0.01, 0.5);
            }
        }
        
        // Clamp values
        connection.strength = connection.strength.clamp(0.0, 1.0);
        connection.strength = (connection.strength * 100.0).round() / 100.0; // round to 2 decimal places
    }
    
    fn apply_meta_plasticity(&mut self, metrics: &mut PlasticityMetrics) -> Result<()> {
        // Adjust rule strengths based on recent effectiveness
        for rule in &mut self.rules {
            let effectiveness = metrics.changes_applied as f32 / self.rules.len() as f32;
            
            if effectiveness > 0.5 {
                // Rules are effective - slightly increase strength
                rule.strength *= 1.05;
            } else {
                // Rules are less effective - slightly decrease strength
                rule.strength *= 0.95;
            }
            
            rule.strength = rule.strength.clamp(0.01, 1.0);
        }
        
        metrics.meta_plasticity_applied = true;
        
        Ok(())
    }
    
    fn add_exploratory_rule(&mut self) {
        let exploratory_rule = PlasticityRule {
            name: "Exploratory Plasticity".to_string(),
            rule_type: RuleType::MetaPlasticity,
            activation_condition: ActivationCondition::WhenActivationBelow(0.1),
            strength: 0.02,
            applicability: Applicability::PlasticOnly,
        };
        
        self.rules.push(exploratory_rule);
    }
}

/// Metrics for plasticity application
#[derive(Debug, Clone, Default)]
pub struct PlasticityMetrics {
    pub changes_applied: usize,
    pub rules_applied: usize,
    pub average_strength_change: f32,
    pub meta_plasticity_applied: bool,
    pub processing_time_ms: f32,
}