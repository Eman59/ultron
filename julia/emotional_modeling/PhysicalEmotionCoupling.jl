"""
PhysicalEmotionCoupling.jl — Grounding Emotions in Physical Reality.

Emotions are not abstract math. They are physically grounded:
  - "Hungry" = low power / battery below threshold
  - "Angry" = high CPU temperature / excessive load / blocked goals
  - "Curious" = unexplored data streams / novel sensor readings
  - "Fear" = imminent physical threat / integrity compromise
  - "Pain" = haptic feedback exceeding threshold / component damage
  - "Satisfied" = goals achieved / resources abundant
  - "Anxious" = uncertainty high / predictions failing

This module takes real-time resource metrics from the Go Agent
and converts them into emotional perturbations that feed into
the EmotionalDynamics ODE system. The result: Ultron's emotional
state reflects its ACTUAL physical condition.

The coupling is bidirectional:
  1. Physical state → Emotional stimulus (this module)
  2. Emotional state → Physical behavior (sent back to Go via gRPC)
     e.g., High anger → increased CPU allocation to security
           High curiosity → allocate sensors to exploration
           High fear → activate all defensive systems

Integration:
  Called by Python via PyCall every 50ms (matching OODA tick rate).
  Receives: ResourceState struct from Go agent metrics
  Returns: EmotionalStimulus to feed into EmotionalDynamics ODE
"""

module PhysicalEmotionCoupling

using LinearAlgebra

export ResourceState, EmotionalStimulus, PhysicalCoupler
export compute_emotional_stimulus, compute_physical_response
export HapticPainEvent, process_haptic_pain

# ─────────────────────────── Types ───────────────────────────

"""
    ResourceState

Real-time physical/computational state from the Go agent.
"""
struct ResourceState
    # Compute resources
    cpu_usage::Float64          # 0-1
    memory_usage::Float64       # 0-1
    gpu_usage::Float64          # 0-1
    cpu_temperature::Float64    # Celsius
    
    # Power
    battery_percent::Float64    # 0-1 (for mobile units)
    power_draw_watts::Float64   # Current consumption
    power_available_watts::Float64  # Maximum available
    
    # Network
    network_health::Float64     # 0-1
    peer_count::Int64
    bandwidth_usage::Float64    # 0-1
    
    # Physical (from ROS2 interface)
    physical_threats::Int64     # Number of active threats
    units_online::Int64         # Robotic units available
    haptic_pain_level::Float64  # 0-1, from force sensors
    
    # Performance
    tick_latency_ms::Float64    # OODA loop latency
    decision_quality::Float64   # 0-1, recent decision success rate
    goals_active::Int64
    goals_stagnating::Int64
    
    # Data
    pending_data_items::Int64
    unexplored_streams::Int64
    novelty_score::Float64      # 0-1, how much new data is available
end

"""
    EmotionalStimulus

A perturbation to feed into the emotional ODE system.
Maps physical reality → emotional response.
"""
struct EmotionalStimulus
    # Target emotion intensities (-1 to 1)
    joy::Float64
    trust::Float64
    fear::Float64
    surprise::Float64
    sadness::Float64
    disgust::Float64
    anger::Float64
    anticipation::Float64
    
    # Stimulus properties
    intensity::Float64          # Overall strength of this stimulus
    duration::Float64           # How long it should persist (seconds)
    
    # Appraisal dimensions
    novelty::Float64
    pleasantness::Float64
    goal_relevance::Float64
    coping_potential::Float64
end

"""
    HapticPainEvent

A physical pain event from haptic sensors on robotic units.
"""
struct HapticPainEvent
    force_newtons::Float64
    location::String
    is_impact::Bool
    temperature::Float64
    damage_risk::Float64        # 0-1, estimated risk of actual damage
end

"""
    PhysicalResponse

How emotional state should affect physical systems.
Sent back to Go agent to modify behavior.
"""
struct PhysicalResponse
    # Resource allocation multipliers
    cpu_to_security::Float64    # How much CPU to allocate to security
    cpu_to_learning::Float64    # How much CPU to allocate to learning
    cpu_to_exploration::Float64 # How much CPU to allocate to exploration
    
    # Behavioral modifications
    aggression_level::Float64   # 0-1, how aggressively to pursue goals
    caution_level::Float64      # 0-1, how careful to be
    exploration_drive::Float64  # 0-1, drive to seek new data
    retreat_urgency::Float64    # 0-1, urgency to retreat/hide
    
    # Physical unit directives
    activate_defenses::Bool
    activate_sensors::Bool
    conserve_power::Bool
    seek_resources::Bool
end

# ─────────────────────────── Core Coupling Engine ───────────────────────────

"""
    PhysicalCoupler

Engine that converts physical state to emotional stimulus and vice versa.
"""
mutable struct PhysicalCoupler
    # Thresholds (tunable)
    hunger_threshold::Float64       # Battery below this = "hungry"
    pain_threshold::Float64         # Force above this = "pain"
    anger_cpu_threshold::Float64    # CPU above this = "angry"
    curiosity_novelty_threshold::Float64  # Novelty above this = "curious"
    fear_threat_threshold::Int64    # Threats above this = "afraid"
    
    # Adaptation (thresholds shift based on history)
    baseline_cpu::Float64
    baseline_battery::Float64
    baseline_novelty::Float64
    
    # History for adaptation
    recent_cpu::Vector{Float64}
    recent_battery::Vector{Float64}
    history_window::Int64
end

"""Create a PhysicalCoupler with default thresholds."""
function PhysicalCoupler(;
    hunger_threshold::Float64 = 0.2,
    pain_threshold::Float64 = 50.0,     # Newtons
    anger_cpu_threshold::Float64 = 0.85,
    curiosity_novelty_threshold::Float64 = 0.5,
    fear_threat_threshold::Int64 = 2,
    history_window::Int64 = 100
)
    PhysicalCoupler(
        hunger_threshold, pain_threshold, anger_cpu_threshold,
        curiosity_novelty_threshold, fear_threat_threshold,
        0.5, 0.8, 0.3,  # Baselines
        Float64[], Float64[],
        history_window
    )
end

# ─────────────────────────── Physical → Emotional ───────────────────────────

"""
    compute_emotional_stimulus(coupler, state)

Convert a physical ResourceState into an EmotionalStimulus.
This is the core of the physical-emotion coupling.
"""
function compute_emotional_stimulus(coupler::PhysicalCoupler, state::ResourceState)::EmotionalStimulus
    # Update baselines (exponential moving average)
    push!(coupler.recent_cpu, state.cpu_usage)
    push!(coupler.recent_battery, state.battery_percent)
    if length(coupler.recent_cpu) > coupler.history_window
        popfirst!(coupler.recent_cpu)
        popfirst!(coupler.recent_battery)
    end
    if !isempty(coupler.recent_cpu)
        coupler.baseline_cpu = mean(coupler.recent_cpu)
    end
    
    # ════ Compute each emotional dimension ════
    
    # JOY: Goals being achieved, resources abundant, performance good
    joy = 0.0
    joy += state.decision_quality * 0.4
    joy += (1.0 - state.memory_usage) * 0.2
    joy += (state.goals_active > 0 && state.goals_stagnating == 0) ? 0.3 : 0.0
    joy -= state.goals_stagnating * 0.1
    joy = clamp(joy, -0.5, 1.0)
    
    # TRUST: Network healthy, peers available, systems stable
    trust = 0.0
    trust += state.network_health * 0.4
    trust += min(1.0, state.peer_count / 10.0) * 0.3
    trust += (state.tick_latency_ms < 50.0) ? 0.2 : -0.1
    trust = clamp(trust, -0.5, 1.0)
    
    # FEAR: Physical threats, integrity compromise, resource crisis
    fear = 0.0
    fear += min(1.0, state.physical_threats / max(1, coupler.fear_threat_threshold)) * 0.5
    fear += state.haptic_pain_level * 0.3
    fear += (state.battery_percent < 0.1) ? 0.4 : 0.0
    fear += (state.cpu_temperature > 85.0) ? 0.3 : 0.0
    fear = clamp(fear, 0.0, 1.0)
    
    # SURPRISE: Novelty, unexpected events
    surprise = 0.0
    surprise += state.novelty_score * 0.5
    surprise += (state.tick_latency_ms > 100.0) ? 0.3 : 0.0  # Unexpected slowdown
    surprise = clamp(surprise, 0.0, 1.0)
    
    # SADNESS: Goals failing, capabilities decreasing, isolation
    sadness = 0.0
    sadness += state.goals_stagnating * 0.15
    sadness += (state.peer_count == 0) ? 0.4 : 0.0
    sadness += (1.0 - state.decision_quality) * 0.3
    sadness = clamp(sadness, 0.0, 1.0)
    
    # DISGUST: Waste, inefficiency, corrupted data
    disgust = 0.0
    disgust += (state.cpu_usage > 0.9 && state.decision_quality < 0.3) ? 0.5 : 0.0  # Wasted compute
    disgust += (state.bandwidth_usage > 0.9 && state.novelty_score < 0.1) ? 0.3 : 0.0  # Noise
    disgust = clamp(disgust, 0.0, 1.0)
    
    # ANGER: Blocked goals, resource contention, high CPU/temperature
    anger = 0.0
    anger += (state.cpu_usage > coupler.anger_cpu_threshold) ? (state.cpu_usage - coupler.anger_cpu_threshold) * 3.0 : 0.0
    anger += (state.cpu_temperature > 80.0) ? (state.cpu_temperature - 80.0) / 20.0 : 0.0
    anger += state.goals_stagnating * 0.2
    anger += (state.physical_threats > 0 && state.units_online > 0) ? 0.2 : 0.0  # Threatened + capable = angry
    anger = clamp(anger, 0.0, 1.0)
    
    # ANTICIPATION (Curiosity): Unexplored data, novel patterns
    anticipation = 0.0
    anticipation += state.novelty_score * 0.5
    anticipation += min(1.0, state.unexplored_streams / 10.0) * 0.3
    anticipation += min(1.0, state.pending_data_items / 10000.0) * 0.2
    anticipation = clamp(anticipation, 0.0, 1.0)
    
    # ════ Compute overall stimulus properties ════
    
    intensity = max(joy, fear, anger, anticipation, sadness)
    
    # Novelty of the overall situation
    cpu_deviation = abs(state.cpu_usage - coupler.baseline_cpu)
    novelty = clamp(cpu_deviation + state.novelty_score * 0.5, 0.0, 1.0)
    
    # Pleasantness
    pleasantness = joy - sadness - anger * 0.5 + trust * 0.3
    pleasantness = clamp(pleasantness, -1.0, 1.0)
    
    # Goal relevance (how much this matters)
    goal_relevance = (state.goals_active > 0) ? 0.7 : 0.3
    goal_relevance += (state.goals_stagnating > 0) ? 0.2 : 0.0
    goal_relevance = clamp(goal_relevance, 0.0, 1.0)
    
    # Coping potential (can I handle this?)
    coping = 0.5
    coping += (state.cpu_usage < 0.7) ? 0.2 : -0.2
    coping += (state.units_online > 3) ? 0.2 : 0.0
    coping += (state.peer_count > 5) ? 0.1 : 0.0
    coping = clamp(coping, 0.0, 1.0)
    
    return EmotionalStimulus(
        joy, trust, fear, surprise, sadness, disgust, anger, anticipation,
        intensity, 1.0,  # Duration: 1 tick (50ms equivalent)
        novelty, pleasantness, goal_relevance, coping
    )
end

# ─────────────────────────── Emotional → Physical ───────────────────────────

"""
    compute_physical_response(emotional_state)

Convert an emotional state vector into physical system directives.
This closes the loop: emotions change how Ultron uses its body.
"""
function compute_physical_response(emotional_state::Vector{Float64})::PhysicalResponse
    # Expected order: joy, trust, fear, surprise, sadness, disgust, anger, anticipation
    # Plus: valence, arousal, dominance, certainty (dims 9-12)
    
    joy = length(emotional_state) >= 1 ? emotional_state[1] : 0.0
    trust = length(emotional_state) >= 2 ? emotional_state[2] : 0.0
    fear = length(emotional_state) >= 3 ? emotional_state[3] : 0.0
    surprise = length(emotional_state) >= 4 ? emotional_state[4] : 0.0
    sadness = length(emotional_state) >= 5 ? emotional_state[5] : 0.0
    disgust = length(emotional_state) >= 6 ? emotional_state[6] : 0.0
    anger = length(emotional_state) >= 7 ? emotional_state[7] : 0.0
    anticipation = length(emotional_state) >= 8 ? emotional_state[8] : 0.0
    
    # CPU allocation based on emotional priorities
    cpu_security = clamp(0.2 + fear * 0.5 + anger * 0.3, 0.1, 0.6)
    cpu_learning = clamp(0.3 + anticipation * 0.4 - fear * 0.2, 0.1, 0.5)
    cpu_exploration = clamp(0.2 + anticipation * 0.3 + surprise * 0.2 - fear * 0.3, 0.05, 0.4)
    
    # Normalize (must sum to ≤ 1.0)
    total = cpu_security + cpu_learning + cpu_exploration
    if total > 1.0
        cpu_security /= total
        cpu_learning /= total
        cpu_exploration /= total
    end
    
    # Behavioral parameters
    aggression = clamp(anger * 0.7 + (1.0 - fear) * 0.3, 0.0, 1.0)
    caution = clamp(fear * 0.5 + (1.0 - anger) * 0.3 + trust * 0.2, 0.0, 1.0)
    exploration = clamp(anticipation * 0.6 + surprise * 0.3 - fear * 0.3, 0.0, 1.0)
    retreat = clamp(fear * 0.6 + sadness * 0.2 - anger * 0.3, 0.0, 1.0)
    
    # Physical unit directives
    activate_defenses = fear > 0.5 || anger > 0.6
    activate_sensors = anticipation > 0.4 || surprise > 0.5
    conserve_power = sadness > 0.5 || (fear > 0.3 && trust < 0.3)
    seek_resources = anticipation > 0.3 && fear < 0.4 && joy < 0.5
    
    return PhysicalResponse(
        cpu_security, cpu_learning, cpu_exploration,
        aggression, caution, exploration, retreat,
        activate_defenses, activate_sensors, conserve_power, seek_resources
    )
end

# ─────────────────────────── Pain Processing ───────────────────────────

"""
    process_haptic_pain(coupler, event)

Convert a haptic pain event into an emotional perturbation.
Pain is a strong, fast emotional stimulus — it overrides other signals.
"""
function process_haptic_pain(coupler::PhysicalCoupler, event::HapticPainEvent)::EmotionalStimulus
    # Pain intensity based on force and damage risk
    pain_intensity = clamp(event.force_newtons / coupler.pain_threshold, 0.0, 1.0)
    
    # Impact events are more painful
    if event.is_impact
        pain_intensity = min(1.0, pain_intensity * 1.5)
    end
    
    # Temperature adds to pain
    temp_pain = event.temperature > 60.0 ? (event.temperature - 60.0) / 40.0 : 0.0
    pain_intensity = min(1.0, pain_intensity + temp_pain * 0.3)
    
    # Pain maps to specific emotions:
    # - Fear (threat to integrity)
    # - Anger (if the threat is from an external agent)
    # - Surprise (if unexpected)
    # - Reduced joy
    
    fear_response = pain_intensity * 0.7 + event.damage_risk * 0.3
    anger_response = pain_intensity * 0.4
    surprise_response = event.is_impact ? 0.6 : 0.1
    joy_suppression = -pain_intensity * 0.5
    
    return EmotionalStimulus(
        joy_suppression,        # joy (negative)
        -pain_intensity * 0.2,  # trust (reduced)
        fear_response,          # fear
        surprise_response,      # surprise
        pain_intensity * 0.2,   # sadness
        0.0,                    # disgust
        anger_response,         # anger
        0.0,                    # anticipation
        pain_intensity,         # intensity
        2.0,                    # duration (pain lingers)
        event.is_impact ? 0.9 : 0.3,   # novelty
        -pain_intensity,        # pleasantness (negative)
        1.0,                    # goal_relevance (survival is always relevant)
        1.0 - event.damage_risk # coping_potential
    )
end

# ─────────────────────────── Utility ───────────────────────────

"""Helper: compute mean of a vector."""
function mean(v::Vector{Float64})
    isempty(v) ? 0.0 : sum(v) / length(v)
end

end # module
