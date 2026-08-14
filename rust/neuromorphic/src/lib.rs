//! # Ultron Neuromorphic Computing Engine
//!
//! Simulates brain-inspired spike-based neural computation.
//! Designed to be hardware-swappable: when Intel Loihi or IBM TrueNorth
//! chips are available, this module can act as the driver layer.
//!
//! ## Why Neuromorphic?
//! - **Massive parallelism**: Thousands of neurons fire simultaneously
//! - **Energy efficiency**: Only active neurons consume energy (event-driven)
//! - **Temporal coding**: Information in spike TIMING, not just rate
//! - **Online learning**: STDP (Spike-Timing Dependent Plasticity) in real-time
//! - **Unpredictability**: Harder to analyze/intercept than standard computation
//!
//! ## Architecture
//! - Leaky Integrate-and-Fire (LIF) neurons
//! - Spike-Timing Dependent Plasticity (STDP)
//! - Lateral inhibition for winner-take-all competition
//! - Hierarchical cortical columns

use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;

/// Configuration for the neuromorphic processor.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NeuromorphicConfig {
    /// Number of neurons
    pub neuron_count: usize,
    /// Simulation timestep in milliseconds
    pub dt_ms: f64,
    /// Membrane time constant (ms)
    pub tau_mem: f64,
    /// Synaptic time constant (ms)
    pub tau_syn: f64,
    /// Firing threshold voltage
    pub v_threshold: f64,
    /// Reset voltage after firing
    pub v_reset: f64,
    /// Resting membrane potential
    pub v_rest: f64,
    /// Refractory period (ms)
    pub t_refractory: f64,
    /// STDP learning rate
    pub stdp_rate: f64,
    /// Enable lateral inhibition
    pub lateral_inhibition: bool,
}

impl Default for NeuromorphicConfig {
    fn default() -> Self {
        Self {
            neuron_count: 1000,
            dt_ms: 1.0,
            tau_mem: 20.0,
            tau_syn: 5.0,
            v_threshold: -50.0,
            v_reset: -70.0,
            v_rest: -65.0,
            t_refractory: 2.0,
            stdp_rate: 0.01,
            lateral_inhibition: true,
        }
    }
}

/// A single Leaky Integrate-and-Fire neuron.
#[derive(Debug, Clone)]
pub struct LIFNeuron {
    pub id: usize,
    /// Current membrane potential (mV)
    pub v_mem: f64,
    /// Synaptic current
    pub i_syn: f64,
    /// Whether the neuron fired this timestep
    pub fired: bool,
    /// Time since last spike (for refractory period)
    pub t_since_spike: f64,
    /// Spike history (timestamps of recent spikes)
    pub spike_times: VecDeque<f64>,
    /// Total spike count
    pub spike_count: u64,
    /// Incoming synapse weights
    pub incoming_weights: Vec<(usize, f64)>, // (source_neuron_id, weight)
    /// Outgoing connection targets
    pub outgoing: Vec<usize>,
    /// Neuron layer/group
    pub layer: usize,
}

/// A spike event in the network.
#[derive(Debug, Clone, Copy)]
pub struct Spike {
    pub neuron_id: usize,
    pub timestamp: f64,
}

/// The neuromorphic processor.
pub struct NeuromorphicProcessor {
    /// Configuration
    config: NeuromorphicConfig,
    /// All neurons
    neurons: Vec<LIFNeuron>,
    /// Current simulation time
    current_time: f64,
    /// Spike raster (history of all spikes)
    spike_raster: Vec<Spike>,
    /// Total simulation steps
    total_steps: u64,
}

impl NeuromorphicProcessor {
    /// Create a new neuromorphic processor.
    pub fn new(config: NeuromorphicConfig) -> Self {
        let neuron_count = config.neuron_count;
        let mut neurons = Vec::with_capacity(neuron_count);

        for i in 0..neuron_count {
            let layer = i * 4 / neuron_count; // 4 layers

            neurons.push(LIFNeuron {
                id: i,
                v_mem: config.v_rest,
                i_syn: 0.0,
                fired: false,
                t_since_spike: 100.0, // Long time since "last" spike
                spike_times: VecDeque::with_capacity(100),
                spike_count: 0,
                incoming_weights: Vec::new(),
                outgoing: Vec::new(),
                layer,
            });
        }

        // Create random connectivity (sparse, ~10% connection probability)
        let mut rng = rand::thread_rng();
        use rand::Rng;

        for i in 0..neuron_count {
            let n_connections = (neuron_count as f64 * 0.1) as usize;
            for _ in 0..n_connections {
                let target = rng.gen_range(0..neuron_count);
                if target != i {
                    let weight = rng.gen_range(0.1..2.0);
                    neurons[target].incoming_weights.push((i, weight));
                    neurons[i].outgoing.push(target);
                }
            }
        }

        Self {
            config,
            neurons,
            current_time: 0.0,
            spike_raster: Vec::new(),
            total_steps: 0,
        }
    }

    /// Simulate one timestep.
    pub fn step(&mut self, external_current: &[f64]) -> Vec<Spike> {
        let dt = self.config.dt_ms;
        let tau_mem = self.config.tau_mem;
        let tau_syn = self.config.tau_syn;
        let v_threshold = self.config.v_threshold;
        let v_reset = self.config.v_reset;
        let v_rest = self.config.v_rest;
        let t_refractory = self.config.t_refractory;

        let mut spikes_this_step = Vec::new();

        // Phase 1: Collect spikes from previous step
        let fired_neurons: Vec<usize> = self.neurons.iter()
            .filter(|n| n.fired)
            .map(|n| n.id)
            .collect();

        // Phase 2: Update each neuron
        for neuron in &mut self.neurons {
            // Reset fired flag
            neuron.fired = false;
            neuron.t_since_spike += dt;

            // Skip if in refractory period
            if neuron.t_since_spike < t_refractory {
                continue;
            }

            // Decay synaptic current
            neuron.i_syn *= (-dt / tau_syn).exp();

            // Add synaptic input from presynaptic spikes
            for &(source_id, weight) in &neuron.incoming_weights {
                if fired_neurons.contains(&source_id) {
                    neuron.i_syn += weight;
                }
            }

            // Add external current
            if neuron.id < external_current.len() {
                neuron.i_syn += external_current[neuron.id];
            }

            // Leaky integration of membrane potential
            let dv = (-(neuron.v_mem - v_rest) + neuron.i_syn) * dt / tau_mem;
            neuron.v_mem += dv;

            // Check threshold
            if neuron.v_mem >= v_threshold {
                // FIRE!
                neuron.fired = true;
                neuron.v_mem = v_reset;
                neuron.t_since_spike = 0.0;
                neuron.spike_count += 1;
                neuron.spike_times.push_back(self.current_time);

                // Keep spike history bounded
                while neuron.spike_times.len() > 100 {
                    neuron.spike_times.pop_front();
                }

                let spike = Spike {
                    neuron_id: neuron.id,
                    timestamp: self.current_time,
                };
                spikes_this_step.push(spike);
            }
        }

        // Phase 3: STDP learning
        if !spikes_this_step.is_empty() {
            self.apply_stdp(&spikes_this_step);
        }

        // Phase 4: Lateral inhibition (winner-take-all within layers)
        if self.config.lateral_inhibition && !spikes_this_step.is_empty() {
            self.apply_lateral_inhibition(&spikes_this_step);
        }

        // Record spikes
        self.spike_raster.extend_from_slice(&spikes_this_step);
        self.current_time += dt;
        self.total_steps += 1;

        spikes_this_step
    }

    /// Run simulation for a duration, returning all spikes.
    pub fn simulate(&mut self, duration_ms: f64, external_current: &[f64]) -> Vec<Spike> {
        let n_steps = (duration_ms / self.config.dt_ms) as usize;
        let mut all_spikes = Vec::new();

        for _ in 0..n_steps {
            let spikes = self.step(external_current);
            all_spikes.extend(spikes);
        }

        all_spikes
    }

    /// Encode input data as spike trains (rate coding).
    pub fn encode_rate(&self, values: &[f64], duration_ms: f64) -> Vec<Vec<f64>> {
        // Convert continuous values to spike times using Poisson process
        let mut spike_trains = Vec::new();

        for &value in values {
            let rate = value.max(0.0) * 100.0; // Max 100 Hz
            let mut spikes = Vec::new();
            let mut t = 0.0;

            while t < duration_ms {
                // Inter-spike interval from exponential distribution
                if rate > 0.0 {
                    let interval = -1000.0 / rate * (1.0 - rand::random::<f64>()).ln();
                    t += interval;
                    if t < duration_ms {
                        spikes.push(t);
                    }
                } else {
                    break;
                }
            }

            spike_trains.push(spikes);
        }

        spike_trains
    }

    /// Decode spike output as rate (count spikes per neuron in window).
    pub fn decode_rate(&self, spikes: &[Spike], window_ms: f64) -> Vec<f64> {
        let mut rates = vec![0.0; self.config.neuron_count];
        let window_start = self.current_time - window_ms;

        for spike in spikes {
            if spike.timestamp >= window_start {
                rates[spike.neuron_id] += 1.0;
            }
        }

        // Normalize to Hz
        for rate in &mut rates {
            *rate = *rate * 1000.0 / window_ms;
        }

        rates
    }

    /// Get network statistics.
    pub fn get_stats(&self) -> NetworkStats {
        let total_spikes: u64 = self.neurons.iter().map(|n| n.spike_count).sum();
        let active_neurons = self.neurons.iter().filter(|n| n.spike_count > 0).count();
        let avg_rate = if self.current_time > 0.0 {
            total_spikes as f64 * 1000.0 / (self.current_time * self.config.neuron_count as f64)
        } else {
            0.0
        };

        NetworkStats {
            total_neurons: self.config.neuron_count,
            active_neurons,
            total_spikes,
            avg_firing_rate_hz: avg_rate,
            simulation_time_ms: self.current_time,
            total_steps: self.total_steps,
        }
    }

    // ─────────────────────── Private Methods ───────────────────────

    /// Apply Spike-Timing Dependent Plasticity.
    fn apply_stdp(&mut self, recent_spikes: &[Spike]) {
        let stdp_window = 20.0; // ms
        let a_plus = self.config.stdp_rate;
        let a_minus = -self.config.stdp_rate * 1.05; // Slightly stronger depression

        for spike in recent_spikes {
            let post_id = spike.neuron_id;
            let post_time = spike.timestamp;

            // Get pre-synaptic neurons
            let incoming: Vec<(usize, f64)> = self.neurons[post_id].incoming_weights.clone();

            for (pre_id, weight) in &incoming {
                // Check if presynaptic neuron fired recently
                if let Some(pre_time) = self.neurons[*pre_id].spike_times.back() {
                    let dt = post_time - pre_time;

                    if dt > 0.0 && dt < stdp_window {
                        // Pre before post: strengthen (LTP)
                        let dw = a_plus * (-dt / stdp_window).exp();
                        self.update_weight(post_id, *pre_id, weight + dw);
                    } else if dt < 0.0 && dt > -stdp_window {
                        // Post before pre: weaken (LTD)
                        let dw = a_minus * (dt / stdp_window).exp();
                        self.update_weight(post_id, *pre_id, weight + dw);
                    }
                }
            }
        }
    }

    fn update_weight(&mut self, post_id: usize, pre_id: usize, new_weight: f64) {
        let clamped = new_weight.max(0.0).min(10.0); // Bound weights
        if let Some(synapse) = self.neurons[post_id].incoming_weights
            .iter_mut()
            .find(|(src, _)| *src == pre_id)
        {
            synapse.1 = clamped;
        }
    }

    /// Apply lateral inhibition within each layer.
    fn apply_lateral_inhibition(&mut self, spikes: &[Spike]) {
        // Group spikes by layer
        let mut layer_spikes: std::collections::HashMap<usize, Vec<usize>> = std::collections::HashMap::new();

        for spike in spikes {
            let layer = self.neurons[spike.neuron_id].layer;
            layer_spikes.entry(layer).or_default().push(spike.neuron_id);
        }

        // Inhibit non-winners in each layer
        for (_layer, fired_ids) in &layer_spikes {
            if fired_ids.len() > 1 {
                // Winner is the neuron with highest membrane potential
                let winner = fired_ids.iter()
                    .max_by(|&&a, &&b| {
                        self.neurons[a].spike_count.partial_cmp(&self.neurons[b].spike_count)
                            .unwrap_or(std::cmp::Ordering::Equal)
                    })
                    .copied();

                // Inhibit others
                for &id in fired_ids {
                    if Some(id) != winner {
                        self.neurons[id].v_mem = self.config.v_rest - 5.0; // Hyperpolarize
                    }
                }
            }
        }
    }
}

/// Network statistics.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkStats {
    pub total_neurons: usize,
    pub active_neurons: usize,
    pub total_spikes: u64,
    pub avg_firing_rate_hz: f64,
    pub simulation_time_ms: f64,
    pub total_steps: u64,
}
