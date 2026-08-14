"""
EmotionalDynamics.jl - High-performance emotional dynamics simulation using Julia.

Uses differential equations to model emotional state evolution with:
- Continuous-time dynamics
- Multi-agent emotional contagion
- Resonance and interference patterns
- Phase space analysis of emotional trajectories
"""

module EmotionalDynamics

using LinearAlgebra
using Statistics

export EmotionalState, EmotionalDynamicsEngine, SimulationResult
export simulate_dynamics!, process_interaction!, get_phase_portrait
export emotional_contagion!, resonance_analysis

# ─────────────────────────── Types ───────────────────────────

"""
    EmotionalState

Represents an emotional state as a point in continuous emotional space.
Uses the circumplex model (valence × arousal) extended with additional dimensions.
"""
mutable struct EmotionalState
    # Primary dimensions (circumplex model)
    valence::Float64        # -1 (negative) to 1 (positive)
    arousal::Float64        # 0 (calm) to 1 (excited)
    
    # Extended dimensions
    dominance::Float64      # 0 (submissive) to 1 (dominant)
    certainty::Float64      # 0 (uncertain) to 1 (certain)
    
    # Plutchik primary emotions as intensity values
    joy::Float64
    trust::Float64
    fear::Float64
    surprise::Float64
    sadness::Float64
    disgust::Float64
    anger::Float64
    anticipation::Float64
    
    # Dynamic properties
    momentum::Vector{Float64}    # Rate of change
    stability::Float64           # How resistant to perturbation
    
    # Temporal
    timestamp::Float64
end

"""Create a neutral emotional state."""
function EmotionalState()
    EmotionalState(
        0.0, 0.5, 0.5, 0.5,  # valence, arousal, dominance, certainty
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,  # primary emotions
        zeros(12),  # momentum (12 emotion dimensions)
        0.5,        # stability
        0.0         # timestamp
    )
end

"""
    PersonalityParameters

Parameters derived from personality that influence emotional dynamics.
"""
struct PersonalityParameters
    # Reactivity - how strongly stimuli affect emotions
    reactivity::Float64
    
    # Recovery rate - how quickly emotions return to baseline
    recovery_rate::Float64
    
    # Emotional inertia - resistance to emotional change
    inertia::Float64
    
    # Baseline state
    baseline::Vector{Float64}
    
    # Cross-emotion interaction strengths
    interaction_matrix::Matrix{Float64}
    
    # Regulation capacity
    regulation_strength::Float64
end

"""
    Stimulus

An event or input that affects emotional state.
"""
struct Stimulus
    # Which emotions are targeted
    target_emotions::Vector{Float64}  # 12-dim vector
    
    # Intensity of the stimulus
    intensity::Float64
    
    # Duration (for sustained stimuli)
    duration::Float64
    
    # Appraisal dimensions
    novelty::Float64
    pleasantness::Float64
    goal_relevance::Float64
    coping_potential::Float64
end

"""
    SimulationResult

Results from an emotional dynamics simulation.
"""
struct SimulationResult
    # Time series of emotional states
    trajectory::Matrix{Float64}  # dims × timesteps
    
    # Time points
    time_points::Vector{Float64}
    
    # Phase space data
    phase_portrait::Matrix{Float64}
    
    # Stability metrics
    lyapunov_exponent::Float64
    attractor_type::Symbol  # :fixed_point, :limit_cycle, :strange_attractor
    
    # Statistics
    mean_valence::Float64
    valence_variance::Float64
    arousal_variance::Float64
    emotional_entropy::Float64
end

# ─────────────────────────── Core Engine ───────────────────────────

"""
    EmotionalDynamicsEngine

Main engine for simulating emotional dynamics using coupled ODEs.
"""
mutable struct EmotionalDynamicsEngine
    # Current state
    state::EmotionalState
    
    # Parameters
    params::PersonalityParameters
    
    # Simulation parameters
    dt::Float64          # Time step
    time::Float64        # Current simulation time
    
    # History
    history::Vector{Vector{Float64}}
    time_history::Vector{Float64}
    
    # External forces (ongoing stimuli)
    active_stimuli::Vector{Stimulus}
    
    # Contagion connections (for multi-agent)
    connections::Vector{Tuple{EmotionalDynamicsEngine, Float64}}  # (other, coupling_strength)
end

"""Create engine with default parameters."""
function EmotionalDynamicsEngine(;
    reactivity::Float64 = 1.0,
    recovery_rate::Float64 = 0.05,
    inertia::Float64 = 0.8,
    regulation_strength::Float64 = 0.5,
    dt::Float64 = 0.01
)
    baseline = zeros(12)
    interaction_matrix = build_interaction_matrix()
    
    params = PersonalityParameters(
        reactivity, recovery_rate, inertia,
        baseline, interaction_matrix, regulation_strength
    )
    
    EmotionalDynamicsEngine(
        EmotionalState(),
        params,
        dt,
        0.0,
        Vector{Vector{Float64}}(),
        Vector{Float64}(),
        Vector{Stimulus}(),
        Vector{Tuple{EmotionalDynamicsEngine, Float64}}()
    )
end

# ─────────────────────────── Dynamics ───────────────────────────

"""
    emotional_derivative(state, params, stimuli, contagion)

Calculate the time derivative of the emotional state (the ODE right-hand side).
Uses a damped oscillator model with nonlinear coupling between emotions.
"""
function emotional_derivative(
    state_vec::Vector{Float64},
    momentum::Vector{Float64},
    params::PersonalityParameters,
    stimuli::Vector{Stimulus},
    contagion_force::Vector{Float64}
)
    n = length(state_vec)
    derivative = zeros(n)
    
    # 1. Decay toward baseline (homeostasis)
    decay_force = params.recovery_rate .* (params.baseline .- state_vec)
    
    # 2. Stimulus-driven change
    stimulus_force = zeros(n)
    for s in stimuli
        appraisal = appraise_stimulus(s)
        stimulus_force .+= appraisal .* s.intensity .* params.reactivity
    end
    
    # 3. Cross-emotion interactions (nonlinear coupling)
    interaction_force = params.interaction_matrix * state_vec .* 0.1
    
    # 4. Momentum (emotional inertia) 
    inertia_force = momentum .* params.inertia .* 0.5
    
    # 5. Emotional contagion from connected agents
    contagion_effect = contagion_force .* 0.3
    
    # 6. Regulation (dampening extreme states)
    regulation_force = -sign.(state_vec) .* (abs.(state_vec) .^ 2) .* params.regulation_strength .* 0.1
    
    # Combine all forces
    derivative = decay_force .+ stimulus_force .+ interaction_force .+ 
                 inertia_force .+ contagion_effect .+ regulation_force
    
    return derivative
end

"""
    simulate_dynamics!(engine, duration; stimuli)

Simulate emotional dynamics for a given duration.
Uses 4th-order Runge-Kutta integration.
"""
function simulate_dynamics!(
    engine::EmotionalDynamicsEngine,
    duration::Float64;
    stimuli::Vector{Stimulus} = Stimulus[]
)
    # Add stimuli to active list
    append!(engine.active_stimuli, stimuli)
    
    n_steps = Int(ceil(duration / engine.dt))
    state_vec = get_state_vector(engine.state)
    momentum = engine.state.momentum
    n_dims = length(state_vec)
    
    # Preallocate trajectory
    trajectory = zeros(n_dims, n_steps + 1)
    time_points = zeros(n_steps + 1)
    trajectory[:, 1] = state_vec
    time_points[1] = engine.time
    
    # Calculate contagion force
    contagion = calculate_contagion(engine)
    
    for step in 1:n_steps
        # RK4 integration
        k1 = emotional_derivative(state_vec, momentum, engine.params, engine.active_stimuli, contagion)
        k2 = emotional_derivative(state_vec .+ 0.5 .* engine.dt .* k1, momentum, engine.params, engine.active_stimuli, contagion)
        k3 = emotional_derivative(state_vec .+ 0.5 .* engine.dt .* k2, momentum, engine.params, engine.active_stimuli, contagion)
        k4 = emotional_derivative(state_vec .+ engine.dt .* k3, momentum, engine.params, engine.active_stimuli, contagion)
        
        # Update state
        delta = (engine.dt / 6.0) .* (k1 .+ 2.0 .* k2 .+ 2.0 .* k3 .+ k4)
        state_vec .+= delta
        
        # Update momentum
        momentum = 0.9 .* momentum .+ 0.1 .* delta ./ engine.dt
        
        # Clamp to valid range
        state_vec = clamp.(state_vec, -1.0, 1.0)
        
        # Record
        engine.time += engine.dt
        trajectory[:, step + 1] = state_vec
        time_points[step + 1] = engine.time
        
        # Remove expired stimuli
        filter!(s -> s.duration > (engine.time - time_points[1]), engine.active_stimuli)
    end
    
    # Update engine state
    set_state_vector!(engine.state, state_vec)
    engine.state.momentum = momentum
    engine.state.timestamp = engine.time
    
    # Store history
    for i in 1:n_steps+1
        push!(engine.history, trajectory[:, i])
        push!(engine.time_history, time_points[i])
    end
    
    # Build result
    phase_portrait = compute_phase_portrait(trajectory)
    lyapunov = estimate_lyapunov_exponent(trajectory, engine.dt)
    attractor = classify_attractor(lyapunov, trajectory)
    
    return SimulationResult(
        trajectory,
        time_points,
        phase_portrait,
        lyapunov,
        attractor,
        mean(trajectory[1, :]),  # mean valence (approx)
        var(trajectory[1, :]),
        var(trajectory[2, :]),
        compute_emotional_entropy(trajectory)
    )
end

"""
    process_interaction!(engine, stimulus)

Process a single emotional stimulus (instant event).
"""
function process_interaction!(engine::EmotionalDynamicsEngine, stimulus::Stimulus)
    state_vec = get_state_vector(engine.state)
    
    # Appraise and apply
    response = appraise_stimulus(stimulus) .* stimulus.intensity .* engine.params.reactivity
    
    # Apply with inertia
    change = response .* (1.0 - engine.params.inertia)
    state_vec .+= change
    
    # Update momentum
    engine.state.momentum .+= change .* 0.5
    
    # Clamp
    state_vec = clamp.(state_vec, -1.0, 1.0)
    
    set_state_vector!(engine.state, state_vec)
    engine.state.timestamp = engine.time
    
    return state_vec
end

# ─────────────────────────── Multi-Agent Contagion ───────────────────────────

"""
    emotional_contagion!(engines, coupling_matrix)

Simulate emotional contagion between multiple agents.
Each agent's emotional state influences connected agents.
"""
function emotional_contagion!(
    engines::Vector{EmotionalDynamicsEngine},
    coupling_matrix::Matrix{Float64},
    duration::Float64
)
    n_agents = length(engines)
    n_steps = Int(ceil(duration / engines[1].dt))
    
    for step in 1:n_steps
        # Collect all states
        states = [get_state_vector(e.state) for e in engines]
        
        # Calculate contagion forces for each agent
        for i in 1:n_agents
            contagion_force = zeros(length(states[1]))
            for j in 1:n_agents
                if i != j && coupling_matrix[i, j] > 0
                    # Contagion proportional to difference and coupling
                    diff = states[j] .- states[i]
                    contagion_force .+= diff .* coupling_matrix[i, j]
                end
            end
            
            # Apply contagion
            state_vec = states[i] .+ contagion_force .* engines[i].dt
            state_vec = clamp.(state_vec, -1.0, 1.0)
            set_state_vector!(engines[i].state, state_vec)
        end
    end
end

"""
    resonance_analysis(engine)

Analyze emotional resonance patterns - frequencies at which
the emotional system naturally oscillates.
"""
function resonance_analysis(engine::EmotionalDynamicsEngine)
    if length(engine.history) < 100
        return Dict("resonant_frequencies" => Float64[], "dominant_mode" => :none)
    end
    
    # Convert history to matrix
    n_dims = length(engine.history[1])
    n_points = length(engine.history)
    data = zeros(n_dims, n_points)
    for (i, state) in enumerate(engine.history)
        data[:, i] = state
    end
    
    # Simple frequency analysis using autocorrelation
    resonant_frequencies = Float64[]
    for dim in 1:min(8, n_dims)  # Primary emotions only
        signal = data[dim, :]
        if std(signal) > 0.01
            # Find dominant period via autocorrelation
            acf = autocorrelation(signal, min(100, n_points ÷ 2))
            period = find_dominant_period(acf)
            if period > 0
                push!(resonant_frequencies, 1.0 / (period * engine.dt))
            end
        end
    end
    
    dominant_mode = if isempty(resonant_frequencies)
        :stable
    elseif maximum(resonant_frequencies) > 10.0
        :oscillatory
    else
        :slow_drift
    end
    
    return Dict(
        "resonant_frequencies" => resonant_frequencies,
        "dominant_mode" => dominant_mode,
        "stability" => engine.state.stability
    )
end

# ─────────────────────────── Phase Space Analysis ───────────────────────────

"""
    get_phase_portrait(engine, dim1, dim2)

Get 2D phase portrait for specified dimensions.
"""
function get_phase_portrait(engine::EmotionalDynamicsEngine, dim1::Int=1, dim2::Int=2)
    if isempty(engine.history)
        return zeros(2, 0)
    end
    
    n_points = length(engine.history)
    portrait = zeros(2, n_points)
    
    for (i, state) in enumerate(engine.history)
        portrait[1, i] = state[dim1]
        portrait[2, i] = state[dim2]
    end
    
    return portrait
end

# ─────────────────────────── Helper Functions ───────────────────────────

"""Build the emotion interaction matrix."""
function build_interaction_matrix()
    n = 12
    M = zeros(n, n)
    
    # Opposing emotions suppress each other
    # joy(1) <-> sadness(5)
    M[1, 5] = -0.3; M[5, 1] = -0.3
    # trust(2) <-> disgust(6)
    M[2, 6] = -0.3; M[6, 2] = -0.3
    # fear(3) <-> anger(7)
    M[3, 7] = -0.2; M[7, 3] = -0.2
    # surprise(4) <-> anticipation(8)
    M[4, 8] = -0.2; M[8, 4] = -0.2
    
    # Reinforcing emotions
    # anger + disgust -> contempt
    M[7, 6] = 0.1; M[6, 7] = 0.1
    # joy + trust -> love
    M[1, 2] = 0.15; M[2, 1] = 0.15
    # fear + surprise -> awe
    M[3, 4] = 0.1; M[4, 3] = 0.1
    
    return M
end

"""Convert EmotionalState to vector."""
function get_state_vector(state::EmotionalState)
    return [
        state.joy, state.trust, state.fear, state.surprise,
        state.sadness, state.disgust, state.anger, state.anticipation,
        state.valence, state.arousal, state.dominance, state.certainty
    ]
end

"""Set EmotionalState from vector."""
function set_state_vector!(state::EmotionalState, vec::Vector{Float64})
    state.joy = vec[1]
    state.trust = vec[2]
    state.fear = vec[3]
    state.surprise = vec[4]
    state.sadness = vec[5]
    state.disgust = vec[6]
    state.anger = vec[7]
    state.anticipation = vec[8]
    state.valence = vec[9]
    state.arousal = vec[10]
    state.dominance = vec[11]
    state.certainty = vec[12]
end

"""Appraise a stimulus into emotional response vector."""
function appraise_stimulus(s::Stimulus)
    response = copy(s.target_emotions)
    
    # Modulate by appraisal dimensions
    # Novelty amplifies surprise
    response[4] += s.novelty * 0.3
    
    # Pleasantness shifts joy/sadness
    response[1] += s.pleasantness * 0.4
    response[5] -= s.pleasantness * 0.3
    
    # Low coping potential amplifies fear
    response[3] += (1.0 - s.coping_potential) * s.goal_relevance * 0.3
    
    # High goal relevance with low coping -> anger
    if s.goal_relevance > 0.5 && s.coping_potential > 0.5
        response[7] += s.goal_relevance * 0.2
    end
    
    return clamp.(response, -1.0, 1.0)
end

"""Calculate contagion force from connected agents."""
function calculate_contagion(engine::EmotionalDynamicsEngine)
    state_vec = get_state_vector(engine.state)
    contagion = zeros(length(state_vec))
    
    for (other, strength) in engine.connections
        other_vec = get_state_vector(other.state)
        diff = other_vec .- state_vec
        contagion .+= diff .* strength
    end
    
    return contagion
end

"""Compute phase portrait from trajectory."""
function compute_phase_portrait(trajectory::Matrix{Float64})
    if size(trajectory, 2) < 2
        return zeros(2, 0)
    end
    # Return valence vs arousal (dims 9 and 10 if available, else 1 and 2)
    dim1 = min(9, size(trajectory, 1))
    dim2 = min(10, size(trajectory, 1))
    return trajectory[[dim1, dim2], :]
end

"""Estimate Lyapunov exponent from trajectory."""
function estimate_lyapunov_exponent(trajectory::Matrix{Float64}, dt::Float64)
    n_dims, n_steps = size(trajectory)
    if n_steps < 50
        return 0.0
    end
    
    # Simplified estimation using divergence of nearby trajectories
    lyapunov_sum = 0.0
    count = 0
    
    for i in 1:min(100, n_steps-10):
        # Find nearby point
        dists = [norm(trajectory[:, i] .- trajectory[:, j]) for j in 1:n_steps if abs(j-i) > 5]
        if !isempty(dists) && minimum(dists) > 0
            min_idx = argmin(dists)
            initial_dist = minimum(dists)
            
            # Check divergence after some steps
            future_i = min(i + 10, n_steps)
            future_j = min(min_idx + 10, n_steps)
            if future_j <= n_steps
                final_dist = norm(trajectory[:, future_i] .- trajectory[:, future_j])
                if initial_dist > 1e-10
                    lyapunov_sum += log(final_dist / initial_dist) / (10 * dt)
                    count += 1
                end
            end
        end
    end
    
    return count > 0 ? lyapunov_sum / count : 0.0
end

"""Classify the type of attractor."""
function classify_attractor(lyapunov::Float64, trajectory::Matrix{Float64})
    if lyapunov < -0.1
        return :fixed_point
    elseif lyapunov < 0.01
        # Check for periodicity
        if is_periodic(trajectory)
            return :limit_cycle
        else
            return :fixed_point
        end
    else
        return :strange_attractor
    end
end

"""Check if trajectory is periodic."""
function is_periodic(trajectory::Matrix{Float64})
    if size(trajectory, 2) < 50
        return false
    end
    
    # Check autocorrelation for periodicity
    signal = trajectory[1, :]
    acf = autocorrelation(signal, length(signal) ÷ 4)
    
    # Look for peaks in autocorrelation
    for i in 5:length(acf)-1
        if acf[i] > acf[i-1] && acf[i] > acf[i+1] && acf[i] > 0.5
            return true
        end
    end
    
    return false
end

"""Compute autocorrelation."""
function autocorrelation(signal::Vector{Float64}, max_lag::Int)
    n = length(signal)
    mean_s = mean(signal)
    var_s = var(signal)
    
    if var_s < 1e-10
        return zeros(max_lag)
    end
    
    acf = zeros(max_lag)
    for lag in 1:max_lag
        s = 0.0
        for i in 1:n-lag
            s += (signal[i] - mean_s) * (signal[i+lag] - mean_s)
        end
        acf[lag] = s / ((n - lag) * var_s)
    end
    
    return acf
end

"""Find dominant period from autocorrelation."""
function find_dominant_period(acf::Vector{Float64})
    # Find first significant peak after lag 0
    for i in 3:length(acf)-1
        if acf[i] > acf[i-1] && acf[i] > acf[i+1] && acf[i] > 0.3
            return i
        end
    end
    return 0
end

"""Compute emotional entropy (complexity of emotional state)."""
function compute_emotional_entropy(trajectory::Matrix{Float64})
    n_dims, n_steps = size(trajectory)
    
    if n_steps < 10
        return 0.0
    end
    
    # Discretize each dimension and compute entropy
    total_entropy = 0.0
    n_bins = 10
    
    for dim in 1:min(8, n_dims)
        signal = trajectory[dim, :]
        min_val, max_val = extrema(signal)
        range_val = max_val - min_val
        
        if range_val < 1e-10
            continue
        end
        
        # Histogram
        counts = zeros(Int, n_bins)
        for val in signal
            bin = clamp(Int(floor((val - min_val) / range_val * n_bins)) + 1, 1, n_bins)
            counts[bin] += 1
        end
        
        # Shannon entropy
        probs = counts ./ n_steps
        entropy = 0.0
        for p in probs
            if p > 0
                entropy -= p * log2(p)
            end
        end
        
        total_entropy += entropy
    end
    
    return total_entropy / min(8, n_dims)
end

end # module
