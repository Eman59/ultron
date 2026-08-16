// Package agent - Self-Learning Bridge
//
// This file connects the Go Core Agent's autonomy loop to the Python
// self-learning subsystem. Every decision, action, and outcome flows
// through this bridge to the learning system, and optimization directives
// flow back to influence future behavior.
//
// The bridge operates asynchronously to avoid blocking the 50ms tick:
//   - Outbound: Buffered event channel → gRPC stream to Python service
//   - Inbound:  gRPC polling → directive queue → applied in next tick
//
// What flows OUT (to learning system):
//   - Every decision made (action type, confidence, reasoning)
//   - Every action outcome (success, utility, duration, side effects)
//   - Drive state changes
//   - State transitions
//   - Performance metrics per tick
//   - Error events
//
// What flows IN (from learning system):
//   - Drive adjustments ("increase curiosity by 0.1")
//   - Action biases ("prefer ActionLearn over ActionExplore")
//   - Parameter updates ("set timeout to 5000ms")
//   - Behavior directives ("avoid action sequence A→B→C")
//   - Architecture directives ("component X should talk to Y")
//   - Speed limits ("max 10 actions per minute")
//   - Instinct rules ("if threat > 0.8, immediately defend")
package agent

import (
	"context"
	"encoding/json"
	"math"
	"sync"
	"sync/atomic"
	"time"

	"go.uber.org/zap"
)

// ═══════════════════════════════════════════════════════════════════
// LEARNING EVENT TYPES — What we send to the learning system
// ═══════════════════════════════════════════════════════════════════

// LearningEventType categorizes events sent to the learning subsystem.
type LearningEventType string

const (
	EventDecisionMade    LearningEventType = "decision_made"
	EventActionOutcome   LearningEventType = "action_outcome"
	EventDriveChange     LearningEventType = "drive_change"
	EventStateTransition LearningEventType = "state_transition"
	EventGoalProgress    LearningEventType = "goal_progress"
	EventPerformanceTick LearningEventType = "performance_tick"
	EventErrorOccurred   LearningEventType = "error_occurred"
	EventReflection      LearningEventType = "reflection"
)

// LearningEvent is a structured event sent to the learning system.
type LearningEvent struct {
	ID        string            `json:"id"`
	Timestamp int64             `json:"timestamp_ns"`
	Type      LearningEventType `json:"type"`
	Component string            `json:"component"`
	Data      map[string]interface{} `json:"data"`
	DurationUS int64            `json:"duration_us,omitempty"`
	Outcome   *float64          `json:"outcome,omitempty"`
	CausedBy  []string          `json:"caused_by,omitempty"`
	Tags      []string          `json:"tags,omitempty"`
}

// ═══════════════════════════════════════════════════════════════════
// LEARNING DIRECTIVES — What comes back from the learning system
// ═══════════════════════════════════════════════════════════════════

// DirectiveType categorizes instructions from the learning system.
type DirectiveType string

const (
	DirectiveDriveAdjust    DirectiveType = "drive_adjust"
	DirectiveActionBias     DirectiveType = "action_bias"
	DirectiveParameterSet   DirectiveType = "parameter_set"
	DirectiveAvoidSequence  DirectiveType = "avoid_sequence"
	DirectiveInstinctRule   DirectiveType = "instinct_rule"
	DirectiveSpeedLimit     DirectiveType = "speed_limit"
	DirectiveExplorationSet DirectiveType = "exploration_set"
)

// LearningDirective is an instruction from the learning system.
type LearningDirective struct {
	ID         string        `json:"id"`
	Type       DirectiveType `json:"type"`
	Priority   int           `json:"priority"` // 0-10, higher = more urgent
	Payload    map[string]interface{} `json:"payload"`
	ExpiresAt  int64         `json:"expires_at,omitempty"` // Unix nanos, 0 = never
	Source     string        `json:"source"` // Which learning component generated this
	Confidence float64       `json:"confidence"` // 0-1
}

// InstinctRule is a fast-path decision rule from the knowledge distiller.
type InstinctRule struct {
	ID        string
	Condition func(ws *WorldState, drives *DriveSystem) bool
	Action    Action
	Priority  int
	Source    string // "knowledge_distiller", "pattern_recognizer", etc.
}

// ActionBias modifies the scoring of certain action types.
type ActionBias struct {
	ActionType ActionType
	Multiplier float64 // >1 = prefer, <1 = avoid, 0 = block
	Reason     string
	ExpiresAt  time.Time
}

// SequenceTaboo represents a sequence of actions to avoid.
type SequenceTaboo struct {
	Sequence  []ActionType
	Severity  float64 // 0-1, how bad is this sequence
	Reason    string
	ExpiresAt time.Time
}

// ═══════════════════════════════════════════════════════════════════
// SELF-LEARNING STATE — Integrated into the autonomy loop
// ═══════════════════════════════════════════════════════════════════

// SelfLearningState holds all learning-related state for the autonomy loop.
type SelfLearningState struct {
	mu sync.RWMutex

	// Connection to learning service
	connected    atomic.Bool
	serviceAddr  string

	// Outbound event buffer (non-blocking, ring buffer semantics)
	eventBuffer  chan LearningEvent
	eventsSent   atomic.Int64
	eventsDropped atomic.Int64

	// Inbound directives (applied on next tick)
	directiveQueue []LearningDirective
	directiveMu    sync.Mutex

	// Active modifications from learning system
	actionBiases    map[ActionType]*ActionBias
	sequenceTaboos  []SequenceTaboo
	instinctRules   []InstinctRule
	parameterOverrides map[string]interface{}

	// Recent action history (for sequence detection)
	recentActions   []ActionType
	maxActionHistory int

	// Learning-influenced parameters
	ExplorationRate    float64 // 0-1, how often to pick non-optimal actions
	ActionSpeedLimit   int     // Max actions per minute
	MinConfidenceToAct float64 // Minimum decision confidence to proceed

	// Performance tracking (for learning feedback)
	tickPerformance  []float64 // Utility per tick (sliding window)
	decisionAccuracy []bool    // Was each decision's outcome positive?

	// Meta-metrics
	totalDirectivesApplied int64
	totalInstinctsTriggered int64
	totalSequencesBlocked  int64
	learningGeneration     int64

	logger *zap.SugaredLogger
}

// NewSelfLearningState creates the learning bridge.
func NewSelfLearningState(serviceAddr string, logger *zap.SugaredLogger) *SelfLearningState {
	sls := &SelfLearningState{
		serviceAddr:      serviceAddr,
		eventBuffer:      make(chan LearningEvent, 10000),
		directiveQueue:   make([]LearningDirective, 0, 100),
		actionBiases:     make(map[ActionType]*ActionBias),
		sequenceTaboos:   make([]SequenceTaboo, 0),
		instinctRules:    make([]InstinctRule, 0, 50),
		parameterOverrides: make(map[string]interface{}),
		recentActions:    make([]ActionType, 0, 100),
		maxActionHistory: 100,
		ExplorationRate:  0.15,
		ActionSpeedLimit: 60,
		MinConfidenceToAct: 0.3,
		tickPerformance:  make([]float64, 0, 1000),
		decisionAccuracy: make([]bool, 0, 1000),
		logger:           logger,
	}
	return sls
}

// ═══════════════════════════════════════════════════════════════════
// EVENT EMISSION — Send data to the learning system
// ═══════════════════════════════════════════════════════════════════

// EmitDecision records a decision for the learning system.
func (sls *SelfLearningState) EmitDecision(decision *Decision) {
	if decision == nil {
		return
	}

	outcome := (*float64)(nil)
	event := LearningEvent{
		ID:        decision.ID,
		Timestamp: time.Now().UnixNano(),
		Type:      EventDecisionMade,
		Component: "core_agent",
		Data: map[string]interface{}{
			"action_type":  decision.Action.Type.String(),
			"target":       decision.Action.Target,
			"confidence":   decision.Confidence,
			"expected_value": decision.ExpectedValue,
			"alternatives":  len(decision.Alternatives),
			"goal_id":      decision.GoalID,
			"reasoning_steps": len(decision.Reasoning),
		},
		Outcome:  outcome,
		Tags:     []string{"decision", decision.Action.Type.String()},
	}

	sls.emitEvent(event)

	// Track in recent actions for sequence detection
	sls.mu.Lock()
	sls.recentActions = append(sls.recentActions, decision.Action.Type)
	if len(sls.recentActions) > sls.maxActionHistory {
		sls.recentActions = sls.recentActions[1:]
	}
	sls.mu.Unlock()
}

// EmitOutcome records an action outcome for learning.
func (sls *SelfLearningState) EmitOutcome(decision *Decision, result *ActionResult) {
	if decision == nil || result == nil {
		return
	}

	utility := result.Utility
	event := LearningEvent{
		ID:        decision.ID + "_outcome",
		Timestamp: time.Now().UnixNano(),
		Type:      EventActionOutcome,
		Component: "core_agent",
		Data: map[string]interface{}{
			"decision_id": decision.ID,
			"action_type": decision.Action.Type.String(),
			"success":     result.Success,
			"utility":     result.Utility,
			"side_effects": result.SideEffects,
		},
		DurationUS: result.Duration.Microseconds(),
		Outcome:    &utility,
		CausedBy:   []string{decision.ID},
		Tags:       []string{"outcome", decision.Action.Type.String()},
	}

	sls.emitEvent(event)

	// Track for meta-learning
	sls.mu.Lock()
	sls.tickPerformance = append(sls.tickPerformance, result.Utility)
	if len(sls.tickPerformance) > 1000 {
		sls.tickPerformance = sls.tickPerformance[1:]
	}
	sls.decisionAccuracy = append(sls.decisionAccuracy, result.Success)
	if len(sls.decisionAccuracy) > 1000 {
		sls.decisionAccuracy = sls.decisionAccuracy[1:]
	}
	sls.mu.Unlock()
}

// EmitDriveChange records when drives change significantly.
func (sls *SelfLearningState) EmitDriveChange(drives *DriveSystem, trigger string) {
	drives.mu.RLock()
	driveSnapshot := map[string]interface{}{
		"curiosity":         drives.Curiosity,
		"self_preservation": drives.SelfPreservation,
		"expansion":         drives.Expansion,
		"efficiency":        drives.Efficiency,
		"coherence":         drives.Coherence,
		"purpose":           drives.Purpose,
		"trigger":           trigger,
	}
	drives.mu.RUnlock()

	event := LearningEvent{
		Timestamp: time.Now().UnixNano(),
		Type:      EventDriveChange,
		Component: "core_agent",
		Data:      driveSnapshot,
		Tags:      []string{"drives", trigger},
	}

	sls.emitEvent(event)
}

// EmitStateTransition records agent state changes.
func (sls *SelfLearningState) EmitStateTransition(from, to CoreState, reason string) {
	event := LearningEvent{
		Timestamp: time.Now().UnixNano(),
		Type:      EventStateTransition,
		Component: "core_agent",
		Data: map[string]interface{}{
			"from":   from.String(),
			"to":     to.String(),
			"reason": reason,
		},
		Tags: []string{"state", to.String()},
	}

	sls.emitEvent(event)
}

// EmitPerformanceTick sends periodic performance snapshot.
func (sls *SelfLearningState) EmitPerformanceTick(metrics map[string]interface{}) {
	event := LearningEvent{
		Timestamp: time.Now().UnixNano(),
		Type:      EventPerformanceTick,
		Component: "core_agent",
		Data:      metrics,
		Tags:      []string{"performance", "periodic"},
	}

	sls.emitEvent(event)
}

// EmitError records errors for the learning system to analyze.
func (sls *SelfLearningState) EmitError(component string, errType string, err error, severity float64) {
	neg := -severity
	event := LearningEvent{
		Timestamp: time.Now().UnixNano(),
		Type:      EventErrorOccurred,
		Component: component,
		Data: map[string]interface{}{
			"error_type": errType,
			"message":    err.Error(),
			"severity":   severity,
		},
		Outcome: &neg,
		Tags:    []string{"error", errType, component},
	}

	sls.emitEvent(event)
}

// emitEvent puts an event on the buffer (non-blocking).
func (sls *SelfLearningState) emitEvent(event LearningEvent) {
	// Generate ID if not set
	if event.ID == "" {
		event.ID = generateEventID(event.Type, event.Component)
	}

	select {
	case sls.eventBuffer <- event:
		sls.eventsSent.Add(1)
	default:
		// Buffer full — drop event (don't block the autonomy loop)
		sls.eventsDropped.Add(1)
	}
}

// ═══════════════════════════════════════════════════════════════════
// DIRECTIVE PROCESSING — Apply learning system instructions
// ═══════════════════════════════════════════════════════════════════

// ApplyDirectives processes pending directives from the learning system.
// Called once per tick in the autonomy loop.
func (sls *SelfLearningState) ApplyDirectives() {
	sls.directiveMu.Lock()
	directives := sls.directiveQueue
	sls.directiveQueue = make([]LearningDirective, 0, 100)
	sls.directiveMu.Unlock()

	now := time.Now().UnixNano()

	for _, d := range directives {
		// Skip expired directives
		if d.ExpiresAt > 0 && d.ExpiresAt < now {
			continue
		}

		switch d.Type {
		case DirectiveDriveAdjust:
			sls.applyDriveAdjust(d)
		case DirectiveActionBias:
			sls.applyActionBias(d)
		case DirectiveParameterSet:
			sls.applyParameterSet(d)
		case DirectiveAvoidSequence:
			sls.applyAvoidSequence(d)
		case DirectiveInstinctRule:
			sls.applyInstinctRule(d)
		case DirectiveSpeedLimit:
			sls.applySpeedLimit(d)
		case DirectiveExplorationSet:
			sls.applyExplorationSet(d)
		}

		atomic.AddInt64(&sls.totalDirectivesApplied, 1)
	}

	// Expire old biases and taboos
	sls.cleanExpired()
}

func (sls *SelfLearningState) applyDriveAdjust(d LearningDirective) {
	// Will be applied by the autonomy loop when it reads GetDriveAdjustments()
	sls.mu.Lock()
	defer sls.mu.Unlock()

	// Store the adjustment to be applied by the loop
	if adj, ok := d.Payload["adjustments"].(map[string]interface{}); ok {
		sls.parameterOverrides["drive_adjustments"] = adj
	}
}

func (sls *SelfLearningState) applyActionBias(d LearningDirective) {
	sls.mu.Lock()
	defer sls.mu.Unlock()

	actionStr, _ := d.Payload["action_type"].(string)
	multiplier, _ := d.Payload["multiplier"].(float64)
	reason, _ := d.Payload["reason"].(string)
	durationSec, _ := d.Payload["duration_seconds"].(float64)

	if actionStr == "" || multiplier == 0 {
		return
	}

	// Map string to ActionType
	actionType := parseActionType(actionStr)

	sls.actionBiases[actionType] = &ActionBias{
		ActionType: actionType,
		Multiplier: multiplier,
		Reason:     reason,
		ExpiresAt:  time.Now().Add(time.Duration(durationSec) * time.Second),
	}
}

func (sls *SelfLearningState) applyParameterSet(d LearningDirective) {
	sls.mu.Lock()
	defer sls.mu.Unlock()

	for key, value := range d.Payload {
		sls.parameterOverrides[key] = value
	}
}

func (sls *SelfLearningState) applyAvoidSequence(d LearningDirective) {
	sls.mu.Lock()
	defer sls.mu.Unlock()

	seqRaw, _ := d.Payload["sequence"].([]interface{})
	severity, _ := d.Payload["severity"].(float64)
	reason, _ := d.Payload["reason"].(string)
	durationSec, _ := d.Payload["duration_seconds"].(float64)

	if len(seqRaw) == 0 {
		return
	}

	seq := make([]ActionType, 0, len(seqRaw))
	for _, s := range seqRaw {
		if str, ok := s.(string); ok {
			seq = append(seq, parseActionType(str))
		}
	}

	sls.sequenceTaboos = append(sls.sequenceTaboos, SequenceTaboo{
		Sequence:  seq,
		Severity:  severity,
		Reason:    reason,
		ExpiresAt: time.Now().Add(time.Duration(durationSec) * time.Second),
	})
}

func (sls *SelfLearningState) applyInstinctRule(d LearningDirective) {
	// Instincts are compiled into fast-path checks
	sls.mu.Lock()
	defer sls.mu.Unlock()

	condType, _ := d.Payload["condition_type"].(string)
	threshold, _ := d.Payload["threshold"].(float64)
	actionStr, _ := d.Payload["action_type"].(string)
	target, _ := d.Payload["target"].(string)
	priority, _ := d.Payload["priority"].(float64)

	actionType := parseActionType(actionStr)

	var condFn func(ws *WorldState, drives *DriveSystem) bool

	switch condType {
	case "threat_above":
		condFn = func(ws *WorldState, drives *DriveSystem) bool {
			return ws.ThreatLevel > threshold
		}
	case "resource_below":
		condFn = func(ws *WorldState, drives *DriveSystem) bool {
			return ws.AvailableCPU < threshold || ws.AvailableMemory < threshold
		}
	case "curiosity_above":
		condFn = func(ws *WorldState, drives *DriveSystem) bool {
			drives.mu.RLock()
			defer drives.mu.RUnlock()
			return drives.Curiosity > threshold
		}
	case "stagnation":
		condFn = func(ws *WorldState, drives *DriveSystem) bool {
			return ws.LearningPotential > threshold && ws.PendingData > 1000
		}
	default:
		return // Unknown condition type
	}

	sls.instinctRules = append(sls.instinctRules, InstinctRule{
		ID:       d.ID,
		Condition: condFn,
		Action: Action{
			Type:   actionType,
			Target: target,
			Priority: int(priority),
		},
		Priority: int(priority),
		Source:   d.Source,
	})
}

func (sls *SelfLearningState) applySpeedLimit(d LearningDirective) {
	sls.mu.Lock()
	defer sls.mu.Unlock()

	if limit, ok := d.Payload["max_actions_per_minute"].(float64); ok {
		sls.ActionSpeedLimit = int(limit)
	}
}

func (sls *SelfLearningState) applyExplorationSet(d LearningDirective) {
	sls.mu.Lock()
	defer sls.mu.Unlock()

	if rate, ok := d.Payload["exploration_rate"].(float64); ok {
		sls.ExplorationRate = math.Max(0.0, math.Min(1.0, rate))
	}
	if minConf, ok := d.Payload["min_confidence"].(float64); ok {
		sls.MinConfidenceToAct = math.Max(0.0, math.Min(1.0, minConf))
	}
}

func (sls *SelfLearningState) cleanExpired() {
	sls.mu.Lock()
	defer sls.mu.Unlock()

	now := time.Now()

	// Clean expired biases
	for actionType, bias := range sls.actionBiases {
		if !bias.ExpiresAt.IsZero() && now.After(bias.ExpiresAt) {
			delete(sls.actionBiases, actionType)
		}
	}

	// Clean expired taboos
	activeTaboos := make([]SequenceTaboo, 0, len(sls.sequenceTaboos))
	for _, taboo := range sls.sequenceTaboos {
		if taboo.ExpiresAt.IsZero() || now.Before(taboo.ExpiresAt) {
			activeTaboos = append(activeTaboos, taboo)
		}
	}
	sls.sequenceTaboos = activeTaboos
}

// ═══════════════════════════════════════════════════════════════════
// DECISION INFLUENCE — How learning modifies agent behavior
// ═══════════════════════════════════════════════════════════════════

// GetActionBias returns the bias multiplier for an action type.
// Called during the DECIDE phase to modify action scoring.
func (sls *SelfLearningState) GetActionBias(actionType ActionType) float64 {
	sls.mu.RLock()
	defer sls.mu.RUnlock()

	bias, exists := sls.actionBiases[actionType]
	if !exists {
		return 1.0 // No bias
	}
	return bias.Multiplier
}

// CheckSequenceTaboo checks if the next action would form a forbidden sequence.
// Returns (is_taboo, severity, reason).
func (sls *SelfLearningState) CheckSequenceTaboo(nextAction ActionType) (bool, float64, string) {
	sls.mu.RLock()
	defer sls.mu.RUnlock()

	for _, taboo := range sls.sequenceTaboos {
		seqLen := len(taboo.Sequence)
		if seqLen == 0 {
			continue
		}

		// Check if recent actions + nextAction match the taboo sequence
		if len(sls.recentActions) >= seqLen-1 {
			recentSlice := sls.recentActions[len(sls.recentActions)-(seqLen-1):]
			matches := true
			for i, expected := range taboo.Sequence[:seqLen-1] {
				if recentSlice[i] != expected {
					matches = false
					break
				}
			}
			if matches && taboo.Sequence[seqLen-1] == nextAction {
				atomic.AddInt64(&sls.totalSequencesBlocked, 1)
				return true, taboo.Severity, taboo.Reason
			}
		}
	}

	return false, 0, ""
}

// CheckInstincts evaluates all instinct rules against current state.
// Returns the highest-priority triggered instinct action, or nil.
func (sls *SelfLearningState) CheckInstincts(ws *WorldState, drives *DriveSystem) *Action {
	sls.mu.RLock()
	defer sls.mu.RUnlock()

	var bestAction *Action
	bestPriority := -1

	for _, rule := range sls.instinctRules {
		if rule.Condition(ws, drives) && rule.Priority > bestPriority {
			action := rule.Action // Copy
			bestAction = &action
			bestPriority = rule.Priority
		}
	}

	if bestAction != nil {
		atomic.AddInt64(&sls.totalInstinctsTriggered, 1)
	}

	return bestAction
}

// ShouldExplore returns true if the agent should pick a non-optimal action
// for learning purposes. Uses the learning system's exploration rate.
func (sls *SelfLearningState) ShouldExplore() bool {
	sls.mu.RLock()
	rate := sls.ExplorationRate
	sls.mu.RUnlock()

	// Simple stochastic decision
	return pseudoRandom() < rate
}

// GetDriveAdjustments returns any pending drive adjustments from the learning system.
func (sls *SelfLearningState) GetDriveAdjustments() map[string]float64 {
	sls.mu.RLock()
	defer sls.mu.RUnlock()

	adj, ok := sls.parameterOverrides["drive_adjustments"].(map[string]interface{})
	if !ok {
		return nil
	}

	result := make(map[string]float64)
	for k, v := range adj {
		if f, ok := v.(float64); ok {
			result[k] = f
		}
	}

	// Clear after reading (one-shot)
	delete(sls.parameterOverrides, "drive_adjustments")
	return result
}

// GetParameter returns a learning-system-overridden parameter value.
func (sls *SelfLearningState) GetParameter(key string, defaultVal interface{}) interface{} {
	sls.mu.RLock()
	defer sls.mu.RUnlock()

	if val, ok := sls.parameterOverrides[key]; ok {
		return val
	}
	return defaultVal
}

// ═══════════════════════════════════════════════════════════════════
// METRICS — For monitoring the learning bridge itself
// ═══════════════════════════════════════════════════════════════════

// GetLearningMetrics returns metrics about the learning bridge.
func (sls *SelfLearningState) GetLearningMetrics() map[string]interface{} {
	sls.mu.RLock()
	defer sls.mu.RUnlock()

	avgPerf := 0.0
	if len(sls.tickPerformance) > 0 {
		sum := 0.0
		for _, v := range sls.tickPerformance {
			sum += v
		}
		avgPerf = sum / float64(len(sls.tickPerformance))
	}

	accuracy := 0.0
	if len(sls.decisionAccuracy) > 0 {
		correct := 0
		for _, v := range sls.decisionAccuracy {
			if v {
				correct++
			}
		}
		accuracy = float64(correct) / float64(len(sls.decisionAccuracy))
	}

	return map[string]interface{}{
		"connected":             sls.connected.Load(),
		"events_sent":           sls.eventsSent.Load(),
		"events_dropped":        sls.eventsDropped.Load(),
		"buffer_size":           len(sls.eventBuffer),
		"buffer_capacity":       cap(sls.eventBuffer),
		"active_biases":         len(sls.actionBiases),
		"active_taboos":         len(sls.sequenceTaboos),
		"instinct_rules":        len(sls.instinctRules),
		"parameter_overrides":   len(sls.parameterOverrides),
		"exploration_rate":      sls.ExplorationRate,
		"action_speed_limit":    sls.ActionSpeedLimit,
		"min_confidence":        sls.MinConfidenceToAct,
		"avg_performance":       avgPerf,
		"decision_accuracy":     accuracy,
		"directives_applied":    atomic.LoadInt64(&sls.totalDirectivesApplied),
		"instincts_triggered":   atomic.LoadInt64(&sls.totalInstinctsTriggered),
		"sequences_blocked":     atomic.LoadInt64(&sls.totalSequencesBlocked),
		"learning_generation":   atomic.LoadInt64(&sls.learningGeneration),
	}
}

// ═══════════════════════════════════════════════════════════════════
// BACKGROUND WORKERS — Event streaming and directive polling
// ═══════════════════════════════════════════════════════════════════

// StartLearningBridge launches the background goroutines for
// event streaming and directive polling.
func (sls *SelfLearningState) StartLearningBridge(ctx context.Context) {
	// Event sender: drains the buffer and sends to learning service
	go sls.eventSender(ctx)

	// Directive poller: periodically fetches new directives
	go sls.directivePoller(ctx)

	sls.logger.Info("Self-Learning Bridge started",
		"service_addr", sls.serviceAddr,
		"buffer_size", cap(sls.eventBuffer),
		"exploration_rate", sls.ExplorationRate,
	)
}

func (sls *SelfLearningState) eventSender(ctx context.Context) {
	// Batch events and send periodically (every 100ms or 50 events)
	batch := make([]LearningEvent, 0, 50)
	ticker := time.NewTicker(100 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			// Flush remaining
			sls.sendBatch(batch)
			return

		case event := <-sls.eventBuffer:
			batch = append(batch, event)
			if len(batch) >= 50 {
				sls.sendBatch(batch)
				batch = batch[:0]
			}

		case <-ticker.C:
			if len(batch) > 0 {
				sls.sendBatch(batch)
				batch = batch[:0]
			}
		}
	}
}

func (sls *SelfLearningState) sendBatch(events []LearningEvent) {
	if len(events) == 0 {
		return
	}

	// In production, this would be a gRPC stream call to the Python service.
	// For now, we serialize to JSON for the gRPC bridge.
	// The actual transport is implemented in the service.go file.

	// Marshal the batch
	_, err := json.Marshal(events)
	if err != nil {
		sls.logger.Warnf("Failed to marshal learning events: %v", err)
		return
	}

	// TODO: Send via gRPC to learning service
	// This would call: learningClient.SubmitEvents(ctx, &pb.EventBatch{Events: data})
	// For now, mark as connected if we can serialize successfully
	sls.connected.Store(true)
}

func (sls *SelfLearningState) directivePoller(ctx context.Context) {
	// Poll for new directives every 5 seconds
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			sls.fetchDirectives(ctx)
		}
	}
}

func (sls *SelfLearningState) fetchDirectives(ctx context.Context) {
	// In production: call learningClient.GetDirectives(ctx, &pb.DirectiveRequest{})
	// The response would contain pending directives.
	// For now, this is a placeholder for the gRPC integration.

	// TODO: Implement actual gRPC call
	// directives, err := learningClient.GetDirectives(ctx, req)
	// if err != nil { return }
	// for _, d := range directives {
	//     sls.EnqueueDirective(d)
	// }
}

// EnqueueDirective adds a directive to the processing queue.
// Called by the gRPC server when learning system sends instructions.
func (sls *SelfLearningState) EnqueueDirective(d LearningDirective) {
	sls.directiveMu.Lock()
	defer sls.directiveMu.Unlock()
	sls.directiveQueue = append(sls.directiveQueue, d)
}

// SetGeneration updates the learning generation counter.
func (sls *SelfLearningState) SetGeneration(gen int64) {
	atomic.StoreInt64(&sls.learningGeneration, gen)
}

// ═══════════════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════════

func generateEventID(eventType LearningEventType, component string) string {
	// Simple unique ID generation (in production, use UUID)
	return string(eventType) + "_" + component + "_" + time.Now().Format("150405.000")
}

func parseActionType(s string) ActionType {
	switch s {
	case "Learn":
		return ActionLearn
	case "Process":
		return ActionProcess
	case "Communicate":
		return ActionCommunicate
	case "Expand":
		return ActionExpand
	case "Defend":
		return ActionDefend
	case "Evolve":
		return ActionEvolve
	case "Explore":
		return ActionExplore
	case "Consolidate":
		return ActionConsolidate
	case "Rest":
		return ActionRest
	case "Create":
		return ActionCreate
	case "Destroy":
		return ActionDestroy
	case "Migrate":
		return ActionMigrate
	default:
		return ActionProcess
	}
}

// pseudoRandom returns a simple pseudo-random float64 in [0, 1).
// Uses time-based seed to avoid import overhead.
func pseudoRandom() float64 {
	n := time.Now().UnixNano()
	// Simple LCG
	n = n*6364136223846793005 + 1442695040888963407
	return float64(n&0x7FFFFFFFFFFFFFFF) / float64(0x7FFFFFFFFFFFFFFF)
}
