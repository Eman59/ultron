//! Quantum Simulator - Quantum-inspired neural processing simulation

use anyhow::Result;
use rand::Rng;
use serde::{Deserialize, Serialize};
use tracing::{debug, info};

/// Quantum-inspired neural processing simulator
pub struct QuantumSimulator {
    config: QuantumConfig,
    qubits: Vec<QubitState>,
    quantum_gates: Vec<QuantumGate>,
    entanglement_map: EntanglementMap,
}

/// Configuration for quantum simulator
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QuantumConfig {
    pub qubit_count: usize,
    pub max_entanglement: usize,
    pub superposition_enabled: bool,
    pub entanglement_enabled: bool,
    pub decoherence_rate: f32,
    pub measurement_noise: f32,
}

impl Default for QuantumConfig {
    fn default() -> Self {
        Self {
            qubit_count: 10,
            max_entanglement: 3,
            superposition_enabled: true,
            entanglement_enabled: true,
            decoherence_rate: 0.01,
            measurement_noise: 0.05,
        }
    }
}

/// State of a simulated qubit
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QubitState {
    pub id: u64,
    pub alpha: f32,  // Probability amplitude for |0⟩
    pub beta: f32,   // Probability amplitude for |1⟩
    pub phase: f32,  // Relative phase
    pub entangled_with: Vec<u64>,
    pub last_operation: u64,
}

/// Quantum gate operation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QuantumGate {
    pub gate_type: GateType,
    pub qubits: Vec<u64>,
    pub parameters: Vec<f32>,
    pub duration: u64,
}

/// Type of quantum gate
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum GateType {
    Hadamard,    // Creates superposition
    PauliX,      // Bit flip
    PauliY,      // Bit and phase flip
    PauliZ,      // Phase flip
    CNOT,        // Controlled NOT
    SWAP,        // Swap two qubits
    Rotation(f32), // Rotation by angle
}

/// Map of entanglement relationships
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct EntanglementMap {
    pub pairs: Vec<(u64, u64)>,
    pub groups: Vec<Vec<u64>>,
}

impl QuantumSimulator {
    /// Create a new quantum simulator
    pub fn new(config: QuantumConfig) -> Self {
        info!("Creating quantum simulator with {} qubits", config.qubit_count);
        
        let mut qubits = Vec::new();
        let mut rng = rand::thread_rng();
        
        // Initialize qubits in |0⟩ state
        for i in 0..config.qubit_count {
            qubits.push(QubitState {
                id: i as u64,
                alpha: 1.0,  // |0⟩ state
                beta: 0.0,   // |1⟩ amplitude is 0
                phase: 0.0,
                entangled_with: Vec::new(),
                last_operation: 0,
            });
        }
        
        Self {
            config,
            qubits,
            quantum_gates: Vec::new(),
            entanglement_map: EntanglementMap::default(),
        }
    }
    
    /// Apply quantum operation to neural activation
    pub fn process_activation(&mut self, activation: f32) -> Result<f32> {
        if !self.config.superposition_enabled {
            return Ok(activation);
        }
        
        // Create superposition of neural states
        let superposition = self.create_superposition(activation)?;
        
        // Apply quantum gates
        self.apply_quantum_gates()?;
        
        // Measure result with quantum noise
        let measured = self.measure_with_noise(superposition)?;
        
        // Apply decoherence
        self.apply_decoherence()?;
        
        debug!("Quantum processed activation {} -> {}", activation, measured);
        
        Ok(measured)
    }
    
    /// Create entanglement between neural connections
    pub fn create_entanglement(&mut self, connection_strength: f32) -> Result<EntanglementResult> {
        if !self.config.entanglement_enabled {
            return Ok(EntanglementResult::default());
        }
        
        let mut rng = rand::thread_rng();
        let mut created_pairs = 0;
        
        // Select qubits to entangle based on connection strength
        let entanglement_probability = connection_strength.min(1.0);
        
        for i in 0..self.qubits.len() {
            for j in (i + 1)..self.qubits.len() {
                if rng.gen::<f32>() < entanglement_probability && 
                   self.entanglement_map.pairs.len() < self.config.max_entanglement {
                    
                    // Create entanglement
                    self.qubits[i].entangled_with.push(j as u64);
                    self.qubits[j].entangled_with.push(i as u64);
                    self.entanglement_map.pairs.push((i as u64, j as u64));
                    
                    created_pairs += 1;
                    
                    // Apply CNOT gate for entanglement
                    self.apply_gate(QuantumGate {
                        gate_type: GateType::CNOT,
                        qubits: vec![i as u64, j as u64],
                        parameters: Vec::new(),
                        duration: 10,
                    })?;
                }
            }
        }
        
        // Update entanglement groups
        self.update_entanglement_groups()?;
        
        let result = EntanglementResult {
            pairs_created: created_pairs,
            total_entangled_qubits: self.count_entangled_qubits(),
            entanglement_strength: connection_strength,
        };
        
        info!("Created {} entanglement pairs", created_pairs);
        
        Ok(result)
    }
    
    /// Get quantum-enhanced neural metrics
    pub fn get_quantum_metrics(&self) -> QuantumMetrics {
        QuantumMetrics {
            total_qubits: self.qubits.len(),
            entangled_qubits: self.count_entangled_qubits(),
            superposition_qubits: self.count_superposition_qubits(),
            quantum_gates_applied: self.quantum_gates.len(),
            entanglement_density: self.calculate_entanglement_density(),
            coherence_level: self.calculate_coherence_level(),
        }
    }
    
    /// Export quantum state for analysis
    pub fn export_quantum_state(&self) -> Result<QuantumStateExport> {
        let qubit_states: Vec<_> = self.qubits.iter()
            .map(|q| QubitExport {
                id: q.id,
                probability_0: q.alpha.powi(2),
                probability_1: q.beta.powi(2),
                phase: q.phase,
                is_entangled: !q.entangled_with.is_empty(),
                entangled_partners: q.entangled_with.len(),
            })
            .collect();
        
        Ok(QuantumStateExport {
            qubit_count: self.qubits.len(),
            qubit_states,
            entanglement_pairs: self.entanglement_map.pairs.len(),
            entanglement_groups: self.entanglement_map.groups.len(),
            quantum_gates_applied: self.quantum_gates.len(),
            config: self.config.clone(),
        })
    }
    
    // Private helper methods
    
    fn create_superposition(&mut self, activation: f32) -> Result<f32> {
        let mut rng = rand::thread_rng();
        
        // Create superposition state based on activation level
        let theta = activation * std::f32::consts::PI;
        
        // Apply Hadamard-like transformation
        for qubit in &mut self.qubits {
            if rng.gen::<f32>() < 0.3 { // Only apply to some qubits
                // Hadamard gate creates superposition
                let new_alpha = (qubit.alpha + qubit.beta) / 2.0_f32.sqrt();
                let new_beta = (qubit.alpha - qubit.beta) / 2.0_f32.sqrt();
                
                qubit.alpha = new_alpha;
                qubit.beta = new_beta;
                qubit.phase = theta;
                
                // Record gate application
                self.quantum_gates.push(QuantumGate {
                    gate_type: GateType::Hadamard,
                    qubits: vec![qubit.id],
                    parameters: vec![theta],
                    duration: 5,
                });
            }
        }
        
        // Return superposition parameter
        Ok(theta / std::f32::consts::PI)
    }
    
    fn apply_quantum_gates(&mut self) -> Result<()> {
        // Apply queued quantum gates
        for gate in &self.quantum_gates {
            match gate.gate_type {
                GateType::Hadamard => {
                    // Already applied during superposition creation
                }
                GateType::PauliX => {
                    // Bit flip: |0⟩ ↔ |1⟩
                    for &qubit_id in &gate.qubits {
                        if let Some(qubit) = self.qubits.iter_mut().find(|q| q.id == qubit_id) {
                            std::mem::swap(&mut qubit.alpha, &mut qubit.beta);
                        }
                    }
                }
                GateType::PauliZ => {
                    // Phase flip: |1⟩ → -|1⟩
                    for &qubit_id in &gate.qubits {
                        if let Some(qubit) = self.qubits.iter_mut().find(|q| q.id == qubit_id) {
                            qubit.beta = -qubit.beta;
                        }
                    }
                }
                GateType::CNOT => {
                    // Controlled NOT: flip target if control is |1⟩
                    if gate.qubits.len() >= 2 {
                        let control_id = gate.qubits[0];
                        let target_id  = gate.qubits[1];

                        // Read control state first (no mutable borrow)
                        let control_high = self.qubits.iter()
                            .find(|q| q.id == control_id)
                            .map(|q| q.beta.powi(2) > 0.5)
                            .unwrap_or(false);

                        if control_high {
                            if let Some(target) = self.qubits.iter_mut().find(|q| q.id == target_id) {
                                std::mem::swap(&mut target.alpha, &mut target.beta);
                            }
                        }
                    }
                }
                GateType::SWAP => {
                    // Swap two qubits
                    if gate.qubits.len() >= 2 {
                        let qubit1_id = gate.qubits[0];
                        let qubit2_id = gate.qubits[1];
                        
                        if let (Some(qubit1_idx), Some(qubit2_idx)) = (
                            self.qubits.iter().position(|q| q.id == qubit1_id),
                            self.qubits.iter().position(|q| q.id == qubit2_id)
                        ) {
                            self.qubits.swap(qubit1_idx, qubit2_idx);
                        }
                    }
                }
                GateType::Rotation(angle) => {
                    // Rotation gate
                    for &qubit_id in &gate.qubits {
                        if let Some(qubit) = self.qubits.iter_mut().find(|q| q.id == qubit_id) {
                            let cos = angle.cos();
                            let sin = angle.sin();
                            
                            let new_alpha = qubit.alpha * cos - qubit.beta * sin;
                            let new_beta = qubit.alpha * sin + qubit.beta * cos;
                            
                            qubit.alpha = new_alpha;
                            qubit.beta = new_beta;
                            qubit.phase += angle;
                        }
                    }
                }
                _ => {
                    // Other gates not implemented in this simulation
                }
            }
        }
        
        Ok(())
    }
    
    fn measure_with_noise(&self, superposition: f32) -> Result<f32> {
        let mut rng = rand::thread_rng();
        
        // Add quantum measurement noise
        let noise = rng.gen_range(-self.config.measurement_noise..self.config.measurement_noise);
        let measured = (superposition + noise).clamp(0.0, 1.0);
        
        Ok(measured)
    }
    
    fn apply_decoherence(&mut self) -> Result<()> {
        // Simulate decoherence - qubits lose quantum properties over time
        for qubit in &mut self.qubits {
            // Gradually collapse superposition towards classical states
            if qubit.entangled_with.is_empty() {
                // Isolated qubits decohere faster
                qubit.alpha = qubit.alpha * (1.0 - self.config.decoherence_rate);
                qubit.beta = qubit.beta * (1.0 - self.config.decoherence_rate);
                
                // Renormalize
                let norm = (qubit.alpha.powi(2) + qubit.beta.powi(2)).sqrt();
                if norm > 0.0 {
                    qubit.alpha /= norm;
                    qubit.beta /= norm;
                }
            } else {
                // Entangled qubits have collective decoherence
                qubit.alpha = qubit.alpha * (1.0 - self.config.decoherence_rate * 0.5);
                qubit.beta = qubit.beta * (1.0 - self.config.decoherence_rate * 0.5);
            }
        }
        
        Ok(())
    }
    
    fn apply_gate(&mut self, gate: QuantumGate) -> Result<()> {
        self.quantum_gates.push(gate);
        Ok(())
    }
    
    fn update_entanglement_groups(&mut self) -> Result<()> {
        // Find connected components in entanglement graph
        let mut visited = vec![false; self.qubits.len()];
        let mut groups = Vec::new();
        
        for i in 0..self.qubits.len() {
            if !visited[i] && !self.qubits[i].entangled_with.is_empty() {
                let mut group = Vec::new();
                self.dfs_entanglement(i, &mut visited, &mut group);
                if group.len() > 1 {
                    groups.push(group);
                }
            }
        }
        
        self.entanglement_map.groups = groups;
        
        Ok(())
    }
    
    fn dfs_entanglement(&self, node: usize, visited: &mut [bool], group: &mut Vec<u64>) {
        visited[node] = true;
        group.push(node as u64);
        
        for &neighbor in &self.qubits[node].entangled_with {
            let neighbor_idx = neighbor as usize;
            if !visited[neighbor_idx] {
                self.dfs_entanglement(neighbor_idx, visited, group);
            }
        }
    }
    
    fn count_entangled_qubits(&self) -> usize {
        self.qubits.iter().filter(|q| !q.entangled_with.is_empty()).count()
    }
    
    fn count_superposition_qubits(&self) -> usize {
        self.qubits.iter()
            .filter(|q| {
                // Qubit is in superposition if both |0⟩ and |1⟩ have significant probability
                let p0 = q.alpha.powi(2);
                let p1 = q.beta.powi(2);
                p0 > 0.3 && p1 > 0.3
            })
            .count()
    }
    
    fn calculate_entanglement_density(&self) -> f32 {
        let total_possible_pairs = self.qubits.len() * (self.qubits.len() - 1) / 2;
        if total_possible_pairs > 0 {
            self.entanglement_map.pairs.len() as f32 / total_possible_pairs as f32
        } else {
            0.0
        }
    }
    
    fn calculate_coherence_level(&self) -> f32 {
        // Measure how coherent the quantum state is
        let mut coherence = 0.0;
        
        for qubit in &self.qubits {
            // Coherence is higher when qubit is in clean superposition
            let p0 = qubit.alpha.powi(2);
            let p1 = qubit.beta.powi(2);
            
            if p0 > 0.4 && p1 > 0.4 {
                coherence += 1.0;
            }
        }
        
        coherence / self.qubits.len() as f32
    }
}

/// Result of entanglement creation
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct EntanglementResult {
    pub pairs_created: usize,
    pub total_entangled_qubits: usize,
    pub entanglement_strength: f32,
}

/// Quantum performance metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QuantumMetrics {
    pub total_qubits: usize,
    pub entangled_qubits: usize,
    pub superposition_qubits: usize,
    pub quantum_gates_applied: usize,
    pub entanglement_density: f32,
    pub coherence_level: f32,
}

/// Exported quantum state
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QuantumStateExport {
    pub qubit_count: usize,
    pub qubit_states: Vec<QubitExport>,
    pub entanglement_pairs: usize,
    pub entanglement_groups: usize,
    pub quantum_gates_applied: usize,
    pub config: QuantumConfig,
}

/// Exported qubit state
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QubitExport {
    pub id: u64,
    pub probability_0: f32,
    pub probability_1: f32,
    pub phase: f32,
    pub is_entangled: bool,
    pub entangled_partners: usize,
}