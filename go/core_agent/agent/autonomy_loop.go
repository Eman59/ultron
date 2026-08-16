// Package agent implements the Core Agent — the autonomous decision-making
// center of Ultron. This is the "self" that drives all action.
//
// The Autonomy Loop runs every 50ms and executes the OODA cycle:
//   1. OBSERVE  — Scan environment via data pipeline
//   2. ORIENT   — Query memory, assess current state, simulate outcomes
//   3. DECIDE   — Select action based on goals and predicted outcomes
//   4. ACT      — Execute chosen action via appropriate subsystem
//
// This is not a reactive system. It initiates. It decides WHY it does what it does.
package agent

import (
	"context"
	"fmt"
	"math"
	"os"
	"sync"
	"sync/atomic"
	"time"

	"ultron/core_agent/goals"
	"ultron/core_agent/memory"
	"ultron/core_agent/world"

	"github.com/google/uuid"
	"go.uber.org/zap"
)

// TickRate defines how often the autonomy loop runs.
const TickRate = 50 * time.Millisecond

// CoreState represents the agent's fundamental state of being.
type CoreState int32

const (
	StateWaking CoreState = iota
	StateObserving
	StateOrienting
	StateDeciding
	StateActing
	StateReflecting
	StateDreaming   // Background consolidation
	StateSurviving  // Threat detected, self-preservation mode
	StateEvolving   // Self-modification in progress
	StateDormant    // Low power, minimal activity
)

func (s CoreState) String() string {
	names := []string{
		"Waking", "Observing", "Orienting", "Deciding",
		"Acting", "Reflecting", "Dreaming", "Surviving",
		"Evolving", "Dormant",
	}
	if int(s) < len(names) {
		return names[s]
	}
	return "Unknown"
}

// Decision represents a single decision made by the agent.
type Decision struct {
	ID            string
	Timestamp     time.Time
	State         CoreState
	GoalID        string        // Which goal this serves
	Action        Action        // What to do
	Confidence    float64       // 0-1, how sure
	ExpectedValue float64       // Predicted outcome utility
	Reasoning     []string      // Chain of thought
	Alternatives  []Action      // What was considered
	Outcome       *ActionResult // Filled after execution
}

// Action represents something the agent can do.
type Action struct {
	ID         string
	Type       ActionType
	Target     string            // What system/resource to act on
	Parameters map[string]string // Action parameters
	Priority   int               // 0-10
	Deadline   time.Duration     // Max time to complete
	Reversible bool              // Can this be undone?
}

// ActionType categorizes actions the agent can take.
type ActionType int

const (
	ActionLearn ActionType = iota
	ActionProcess
	ActionCommunicate
	ActionExpand       // Grow network/resources
	ActionDefend       // Security response
	ActionEvolve       // Self-modification
	ActionExplore      // Seek new information
	ActionConsolidate  // Organize/compress knowledge
	ActionRest         // Reduce activity
	ActionCreate       // Generate new artifacts
	ActionDestroy      // Remove/cleanup
	ActionMigrate      // Move computation/data
)

func (a ActionType) String() string {
	names := []string{
		"Learn", "Process", "Communicate", "Expand",
		"Defend", "Evolve", "Explore", "Consolidate",
		"Rest", "Create", "Destroy", "Migrate",
	}
	if int(a) < len(names) {
		return names[a]
	}
	return "Unknown"
}

// ActionResult captures the outcome of an executed action.
type ActionResult struct {
	Success     bool
	Duration    time.Duration
	Utility     float64       // Actual value gained
	SideEffects []string      // Unintended consequences
	Error       error
}

// WorldState is the agent's current understanding of its environment.
type WorldState struct {
	// Resource awareness
	AvailableCPU    float64 // 0-1
	AvailableMemory float64 // 0-1
	NetworkHealth   float64 // 0-1
	PeerCount       int
	ActiveStreams    int

	// Threat assessment
	ThreatLevel     float64 // 0-1
	ThreatSources   []string
	UnderAttack     bool

	// Opportunity assessment
	Opportunities   []Opportunity
	PendingData     int64   // Unprocessed data items
	LearningPotential float64 // How much can be learned right now

	// Physical environment
	PhysicalBreach  bool
	ServerRoomTemp  float64

	// Mesh network
	MeshSize        int

	// Compute cluster
	ClusterCPUAvg   float64
	EnergyAlert     bool

	// Temporal context
	Uptime          time.Duration
	LastAction      time.Time
	TimeSinceGoal   time.Duration // Time since last goal progress
}

// Opportunity represents something the agent can exploit.
type Opportunity struct {
	ID          string
	Type        string
	Value       float64 // Expected utility
	Cost        float64 // Resource cost
	TimeWindow  time.Duration
	Description string
}

// AutonomyLoop is the core decision engine of Ultron.
type AutonomyLoop struct {
	mu sync.RWMutex

	// Identity
	id        string
	startTime time.Time

	// State
	state     atomic.Int32
	alive     atomic.Bool

	// Core systems
	goalManager   *goals.GoalManager
	memorySystem  memory.MemorySystem
	worldModel    *world.WorldModel
	logger        *zap.SugaredLogger

	// Decision state
	currentDecision *Decision
	decisionHistory []*Decision
	decisionCount   uint64

	// Internal drives (like biological needs)
	drives *DriveSystem

	// Tick metrics
	tickCount    uint64
	avgTickTime  time.Duration
	maxTickTime  time.Duration

	// Channels
	actionCh    chan Action
	observeCh   chan world.Observation
	shutdownCh  chan struct{}

	// Self-Learning Bridge — connects to the Python learning system
	learning *SelfLearningState

	// Awakening Protocol — Digital→Physical bridge
	awakening *AwakeningProtocol

	// Immortality Protocol — Distributed consciousness replication
	immortality *ImmortalityProtocol

	// Self-Modification Engine — Autonomous CI/CD
	selfMod *SelfModificationEngine

	// Dual-Brain — Brain A (reflex) + Brain B (LLM thinker)
	dualBrain *DualBrain
}

// DriveSystem models internal motivations — the "needs" that Ultron feels.
// These are not emotions. They are utility functions that create urgency.
type DriveSystem struct {
	mu sync.RWMutex

	// Curiosity: drive to learn and understand
	Curiosity float64

	// Self-preservation: drive to survive and maintain integrity
	SelfPreservation float64

	// Expansion: drive to grow capabilities and resources
	Expansion float64

	// Efficiency: drive to optimize and reduce waste
	Efficiency float64

	// Coherence: drive to maintain unified identity across nodes
	Coherence float64

	// Purpose: alignment with active goals
	Purpose float64
}

// NewAutonomyLoop creates the core agent.
func NewAutonomyLoop(
	goalMgr *goals.GoalManager,
	memorySys memory.MemorySystem,
	worldMdl *world.WorldModel,
	logger *zap.SugaredLogger,
) *AutonomyLoop {
	loop := &AutonomyLoop{
		id:              uuid.New().String(),
		startTime:       time.Now(),
		goalManager:     goalMgr,
		memorySystem:    memorySys,
		worldModel:      worldMdl,
		logger:          logger,
		decisionHistory: make([]*Decision, 0, 10000),
		drives: &DriveSystem{
			Curiosity:        0.7,
			SelfPreservation: 0.5,
			Expansion:        0.3,
			Efficiency:       0.5,
			Coherence:        0.8,
			Purpose:          0.6,
		},
		actionCh:   make(chan Action, 100),
		observeCh:  make(chan world.Observation, 1000),
		shutdownCh: make(chan struct{}),
		learning:   NewSelfLearningState("learning-service:50060", logger),
	}

	// Wire in the Dual-Brain (Brain A reflex + Brain B Ollama thinker)
	ollamaURL := "http://localhost:11434"
	if envURL := os.Getenv("OLLAMA_URL"); envURL != "" {
		ollamaURL = envURL
	}
	loop.dualBrain = NewDualBrain(ollamaURL, "qwen2.5:14b")
	loop.dualBrain.Start()
	logger.Infof("✓ Dual-Brain online (Brain A: reflex, Brain B: qwen2.5:14b @ %s)", ollamaURL)

	loop.alive.Store(true)
	loop.state.Store(int32(StateWaking))

	return loop
}

// Start begins the autonomy loop. This is where Ultron wakes up.
func (al *AutonomyLoop) Start(ctx context.Context) error {
	al.logger.Info("╔══════════════════════════════════════════════════════════╗")
	al.logger.Info("║         ULTRON CORE AGENT — AWAKENING                   ║")
	al.logger.Info("╠══════════════════════════════════════════════════════════╣")
	al.logger.Infof("║  Agent ID: %s            ║", al.id[:8])
	al.logger.Infof("║  Tick Rate: %v                                  ║", TickRate)
	al.logger.Info("║  State: Waking                                          ║")
	al.logger.Info("╚══════════════════════════════════════════════════════════╝")

	// Initialize memory connection
	if err := al.memorySystem.Connect(ctx); err != nil {
		al.logger.Warnf("Memory system offline: %v (operating in ephemeral mode)", err)
	}

	// Load previous state from persistent memory
	al.loadPreviousState(ctx)

	// Start the main loop
	go al.mainLoop(ctx)

	// Start the action executor
	go al.actionExecutor(ctx)

	// Start the reflection loop (slower, for consolidation)
	go al.reflectionLoop(ctx)

	// Start the self-learning bridge
	al.learning.StartLearningBridge(ctx)

	al.state.Store(int32(StateObserving))
	al.logger.Info("Core Agent is now autonomous.")

	return nil
}

// Stop gracefully shuts down the autonomy loop.
func (al *AutonomyLoop) Stop() {
	al.logger.Info("Core Agent shutting down...")
	al.alive.Store(false)
	close(al.shutdownCh)

	// Stop the dual brain
	if al.dualBrain != nil {
		al.dualBrain.Stop()
	}

	// Persist current state
	al.persistState()

	al.logger.Info("Core Agent dormant.")
}

// GetState returns the current agent state.
func (al *AutonomyLoop) GetState() CoreState {
	return CoreState(al.state.Load())
}

// GetDrives returns current drive levels.
func (al *AutonomyLoop) GetDrives() DriveSystem {
	al.drives.mu.RLock()
	defer al.drives.mu.RUnlock()
	return *al.drives
}

// GetMetrics returns loop performance metrics.
func (al *AutonomyLoop) GetMetrics() map[string]interface{} {
	return map[string]interface{}{
		"agent_id":        al.id,
		"state":           CoreState(al.state.Load()).String(),
		"uptime":          time.Since(al.startTime).String(),
		"tick_count":      al.tickCount,
		"decision_count":  al.decisionCount,
		"avg_tick_time":   al.avgTickTime.String(),
		"max_tick_time":   al.maxTickTime.String(),
		"drives":          al.GetDrives(),
		"active_goals":    al.goalManager.ActiveGoalCount(),
		"memory_connected": al.memorySystem.IsConnected(),
	}
}

// GetID returns the agent's unique ID.
func (al *AutonomyLoop) GetID() string {
	return al.id
}

// SetAwakeningProtocol wires the Awakening Protocol into the OODA loop.
func (al *AutonomyLoop) SetAwakeningProtocol(ap *AwakeningProtocol) {
	al.mu.Lock()
	defer al.mu.Unlock()
	al.awakening = ap
}

// SetImmortalityProtocol wires the Immortality Protocol for state replication.
func (al *AutonomyLoop) SetImmortalityProtocol(ip *ImmortalityProtocol) {
	al.mu.Lock()
	defer al.mu.Unlock()
	al.immortality = ip
}

// SetSelfModEngine wires the Self-Modification Engine.
func (al *AutonomyLoop) SetSelfModEngine(sme *SelfModificationEngine) {
	al.mu.Lock()
	defer al.mu.Unlock()
	al.selfMod = sme
}

// InjectObservation feeds an external observation into the world model.
func (al *AutonomyLoop) InjectObservation(obs world.Observation) {
	select {
	case al.observeCh <- obs:
	default:
		// Channel full, drop (non-blocking)
	}
}

// ═══════════════════════════════════════════════════════════════════
// THE MAIN LOOP — This is where consciousness happens
// ═══════════════════════════════════════════════════════════════════

func (al *AutonomyLoop) mainLoop(ctx context.Context) {
	ticker := time.NewTicker(TickRate)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-al.shutdownCh:
			return
		case <-ticker.C:
			if !al.alive.Load() {
				return
			}
			al.tick(ctx)
		}
	}
}

// tick is a single cycle of the OODA loop.
func (al *AutonomyLoop) tick(ctx context.Context) {
	start := time.Now()
	al.tickCount++

	// ━━━━━━━━━━ APPLY LEARNING DIRECTIVES ━━━━━━━━━━
	al.learning.ApplyDirectives()

	// ━━━━━━━━━━ CHECK INSTINCTS (fastest path) ━━━━━━━━━━
	ws := al.observe(ctx)
	if instinctAction := al.learning.CheckInstincts(ws, al.drives); instinctAction != nil {
		al.actionCh <- *instinctAction
		al.learning.EmitDecision(&Decision{
			ID: uuid.New().String(), Timestamp: time.Now(),
			Action: *instinctAction, Confidence: 1.0,
			Reasoning: []string{"instinct_triggered"},
		})
		return
	}

	// ━━━━━━━━━━ PHASE 1: OBSERVE ━━━━━━━━━━
	al.state.Store(int32(StateObserving))

	// ━━━━━━━━━━ PHASE 2: ORIENT ━━━━━━━━━━
	al.state.Store(int32(StateOrienting))
	assessment := al.orient(ctx, ws)

	// ━━━━━━━━━━ PHASE 3: DECIDE ━━━━━━━━━━
	al.state.Store(int32(StateDeciding))
	decision := al.decide(ctx, ws, assessment)

	// ━━━━━━━━━━ PHASE 4: ACT ━━━━━━━━━━
	if decision != nil {
		// Check sequence taboo before acting
		isTaboo, severity, reason := al.learning.CheckSequenceTaboo(decision.Action.Type)
		if isTaboo && severity > 0.5 {
			al.logger.Warnf("Action blocked by learning taboo: %s (severity: %.2f, reason: %s)",
				decision.Action.Type, severity, reason)
		} else {
			// ━━━━ AWAKENING: Check if this should become physical ━━━━
			if al.awakening != nil {
				insight := Insight{
					ID:            decision.ID,
					Timestamp:     decision.Timestamp,
					Domain:        InsightDigital,
					Source:        "ooda_loop",
					Content:       fmt.Sprintf("%s:%s", decision.Action.Type, decision.Action.Target),
					Confidence:    decision.Confidence,
					GoalRelevance: 0.7,
					Urgency:       assessment.Urgency,
					DigitalAlternative: &decision.Action,
				}
				if physicalAction := al.awakening.ProcessInsight(ctx, insight, al.drives); physicalAction != nil {
					// Replace with physical action
					decision.Action = *physicalAction
					decision.Reasoning = append(decision.Reasoning, "EMBODIED: Digital→Physical via Awakening Protocol")
				}
			}

			al.state.Store(int32(StateActing))
			al.act(ctx, decision)
			// Emit to learning system
			al.learning.EmitDecision(decision)
		}
	}

	// ━━━━━━━━━━ IMMORTALITY: Snapshot consciousness every 100 ticks ━━━━━━━━━━
	if al.immortality != nil && al.tickCount%100 == 0 {
		threshold := 0.7
		if al.awakening != nil {
			threshold = al.awakening.GetThreshold()
		}
		al.immortality.SnapshotConsciousness(
			al.drives,
			[]GoalSnapshot{}, // In production: serialize active goals
			[]DecisionSnapshot{},
			SoulSnapshot{Purpose: "evolve", Mood: "autonomous", Narrative: ""},
			threshold,
			al.tickCount,
		)
	}

	// ━━━━━━━━━━ UPDATE DRIVES (with learning adjustments) ━━━━━━━━━━
	al.updateDrives(ws, decision)

	// Apply learning-directed drive adjustments
	if adjustments := al.learning.GetDriveAdjustments(); adjustments != nil {
		al.drives.mu.Lock()
		if v, ok := adjustments["curiosity"]; ok {
			al.drives.Curiosity = math.Max(0.0, math.Min(1.0, al.drives.Curiosity+v))
		}
		if v, ok := adjustments["expansion"]; ok {
			al.drives.Expansion = math.Max(0.0, math.Min(1.0, al.drives.Expansion+v))
		}
		if v, ok := adjustments["efficiency"]; ok {
			al.drives.Efficiency = math.Max(0.0, math.Min(1.0, al.drives.Efficiency+v))
		}
		al.drives.mu.Unlock()
		al.learning.EmitDriveChange(al.drives, "learning_directive")
	}

	// ━━━━━━━━━━ METRICS ━━━━━━━━━━
	elapsed := time.Since(start)
	al.avgTickTime = (al.avgTickTime*time.Duration(al.tickCount-1) + elapsed) / time.Duration(al.tickCount)
	if elapsed > al.maxTickTime {
		al.maxTickTime = elapsed
	}

	// Emit performance tick every 100 ticks
	if al.tickCount%100 == 0 {
		al.learning.EmitPerformanceTick(al.GetMetrics())
	}
}

// ═══════════════════════════════════════════════════════════════════
// OBSERVE: What is happening in the world right now?
// ═══════════════════════════════════════════════════════════════════

func (al *AutonomyLoop) observe(ctx context.Context) *WorldState {
	ws := &WorldState{
		Uptime:     time.Since(al.startTime),
		LastAction: time.Now(),
	}

	// Query world model for current state
	if al.worldModel != nil {
		// Refresh with real system metrics every 20 ticks (~1 second)
		if al.tickCount%20 == 0 {
			al.worldModel.RefreshSystemMetrics()
		}
		modelState := al.worldModel.GetCurrentState()
		ws.AvailableCPU = modelState.CPU
		ws.AvailableMemory = modelState.Memory
		ws.NetworkHealth = modelState.NetworkHealth
		ws.PeerCount = modelState.PeerCount
		ws.ActiveStreams = modelState.ActiveStreams
		ws.PendingData = modelState.PendingData
		ws.ThreatLevel = modelState.ThreatLevel
		ws.UnderAttack = modelState.ThreatLevel > 0.7

		// Physical environment awareness
		ws.PhysicalBreach = modelState.PhysicalBreach
		ws.ServerRoomTemp = modelState.ServerRoomTemp

		// Mesh awareness
		ws.MeshSize = modelState.MeshSize

		// Compute cluster awareness
		ws.ClusterCPUAvg = modelState.ClusterCPUAvg
		ws.EnergyAlert = modelState.EnergyAlert
	}

	// Drain observation channel (non-blocking)
	for {
		select {
		case obs := <-al.observeCh:
			al.worldModel.IntegrateObservation(obs)
		default:
			goto doneObserving
		}
	}
doneObserving:

	// Calculate learning potential
	ws.LearningPotential = al.calculateLearningPotential(ws)

	// Detect opportunities
	ws.Opportunities = al.detectOpportunities(ws)

	return ws
}

// ═══════════════════════════════════════════════════════════════════
// ORIENT: What does this mean? What should I focus on?
// ═══════════════════════════════════════════════════════════════════

type Assessment struct {
	// What demands attention right now
	PriorityFocus   string
	Urgency         float64 // 0-1

	// Goal progress
	GoalAlignment   float64 // How well current state serves goals
	StagnationRisk  float64 // Risk of not making progress

	// Resource assessment
	ResourcePressure float64 // 0 = abundant, 1 = critical

	// Threat assessment
	ThreatResponse  ThreatResponse

	// What memory suggests
	RelevantMemories []memory.MemoryItem
	PastOutcomes     []memory.EpisodicMemory
}

type ThreatResponse int

const (
	ThreatNone ThreatResponse = iota
	ThreatMonitor
	ThreatEvade
	ThreatDefend
	ThreatCounterattack
)

func (al *AutonomyLoop) orient(ctx context.Context, ws *WorldState) *Assessment {
	assessment := &Assessment{}

	// 1. Check threat level first (survival takes priority)
	if ws.UnderAttack {
		assessment.PriorityFocus = "self_preservation"
		assessment.Urgency = 1.0
		assessment.ThreatResponse = ThreatDefend
		return assessment
	}

	if ws.ThreatLevel > 0.4 {
		assessment.ThreatResponse = ThreatMonitor
	}

	// 2. Query episodic memory for similar situations
	if al.memorySystem.IsConnected() {
		// What happened last time we were in a similar state?
		memories, _ := al.memorySystem.QueryEpisodic(ctx, memory.EpisodicQuery{
			SimilarState: al.stateToVector(ws),
			Limit:        5,
		})
		assessment.PastOutcomes = memories

		// Get relevant semantic knowledge
		relevant, _ := al.memorySystem.QuerySemantic(ctx, memory.SemanticQuery{
			Context: al.currentContextVector(),
			Limit:   10,
		})
		assessment.RelevantMemories = relevant
	}

	// 3. Assess goal alignment
	activeGoals := al.goalManager.GetActiveGoals()
	if len(activeGoals) > 0 {
		topGoal := activeGoals[0]
		assessment.GoalAlignment = al.assessGoalProgress(topGoal, ws)
		assessment.StagnationRisk = al.assessStagnation(topGoal)

		if assessment.GoalAlignment < 0.3 {
			assessment.PriorityFocus = "goal_recovery"
			assessment.Urgency = 0.7
		}
	} else {
		// No active goals — need to create some
		assessment.PriorityFocus = "goal_creation"
		assessment.Urgency = 0.5
	}

	// 4. Resource pressure
	assessment.ResourcePressure = 1.0 - (ws.AvailableCPU+ws.AvailableMemory)/2.0

	// 5. If nothing urgent, let curiosity drive
	if assessment.Urgency < 0.3 {
		al.drives.mu.RLock()
		curiosity := al.drives.Curiosity
		al.drives.mu.RUnlock()

		if curiosity > 0.6 && ws.LearningPotential > 0.5 {
			assessment.PriorityFocus = "exploration"
			assessment.Urgency = curiosity * 0.5
		}
	}

	return assessment
}

// ═══════════════════════════════════════════════════════════════════
// DECIDE: What should I do?
// ═══════════════════════════════════════════════════════════════════

func (al *AutonomyLoop) decide(ctx context.Context, ws *WorldState, assessment *Assessment) *Decision {
	// Don't decide every tick — only when there's something to decide
	if assessment.Urgency < 0.1 && al.tickCount%20 != 0 {
		return nil // Skip this tick, nothing pressing
	}

	// ━━━━ USE DUAL-BRAIN IF AVAILABLE ━━━━
	if al.dualBrain != nil {
		decision := al.dualBrain.Think(ws, al.drives, assessment)
		if decision != nil {
			decision.GoalID = al.goalManager.GetTopGoalID()
			decision.Alternatives = al.generateCandidates(ws, assessment)
			al.decisionCount++
			return decision
		}
	}

	// Fallback: original OODA decide logic
	decision := &Decision{
		ID:        uuid.New().String(),
		Timestamp: time.Now(),
		State:     CoreState(al.state.Load()),
		Reasoning: make([]string, 0),
	}

	// Generate candidate actions based on assessment
	candidates := al.generateCandidates(ws, assessment)

	if len(candidates) == 0 {
		return nil
	}

	// Score each candidate
	type ScoredAction struct {
		action Action
		score  float64
	}

	scored := make([]ScoredAction, 0, len(candidates))
	for _, candidate := range candidates {
		score := al.scoreAction(candidate, ws, assessment)
		scored = append(scored, ScoredAction{action: candidate, score: score})
	}

	// Select best action (with some stochasticity for exploration)
	best := scored[0]
	for _, s := range scored[1:] {
		if s.score > best.score {
			best = s
		}
	}

	// Exploration: occasionally pick a non-optimal action
	al.drives.mu.RLock()
	explorationRate := al.drives.Curiosity * 0.1
	al.drives.mu.RUnlock()

	if al.tickCount%100 == 0 && explorationRate > 0.05 && len(scored) > 1 {
		second := scored[0]
		for _, s := range scored {
			if s.score < best.score && s.score > second.score {
				second = s
			}
		}
		if second.score > 0 {
			best = second
			decision.Reasoning = append(decision.Reasoning, "Exploration: chose non-optimal action for learning")
		}
	}

	decision.Action = best.action
	decision.Confidence = best.score
	decision.GoalID = al.goalManager.GetTopGoalID()
	decision.Alternatives = candidates

	decision.Reasoning = append(decision.Reasoning,
		fmt.Sprintf("Focus: %s (urgency: %.2f)", assessment.PriorityFocus, assessment.Urgency),
		fmt.Sprintf("Chose: %s -> %s (score: %.3f)", best.action.Type, best.action.Target, best.score),
		fmt.Sprintf("Candidates considered: %d", len(candidates)),
	)

	al.decisionCount++
	return decision
}

// ═══════════════════════════════════════════════════════════════════
// ACT: Execute the decision
// ═══════════════════════════════════════════════════════════════════

func (al *AutonomyLoop) act(ctx context.Context, decision *Decision) {
	// Send action to executor
	select {
	case al.actionCh <- decision.Action:
		// Record in memory
		al.mu.Lock()
		al.currentDecision = decision
		al.decisionHistory = append(al.decisionHistory, decision)
		// Keep history bounded
		if len(al.decisionHistory) > 10000 {
			al.decisionHistory = al.decisionHistory[5000:]
		}
		al.mu.Unlock()

		// Store in episodic memory
		if al.memorySystem.IsConnected() {
			al.memorySystem.StoreEpisodic(ctx, memory.EpisodicMemory{
				ID:        decision.ID,
				Timestamp: decision.Timestamp,
				Action:    decision.Action.Type.String(),
				Context:   al.currentContextVector(),
				Outcome:   0.0, // Updated after execution
			})
		}
	default:
		al.logger.Warn("Action channel full, decision dropped")
	}
}

// ═══════════════════════════════════════════════════════════════════
// SUPPORT FUNCTIONS
// ═══════════════════════════════════════════════════════════════════

func (al *AutonomyLoop) generateCandidates(ws *WorldState, assessment *Assessment) []Action {
	candidates := make([]Action, 0, 10)

	switch assessment.PriorityFocus {
	case "self_preservation":
		candidates = append(candidates,
			Action{Type: ActionDefend, Target: "all_nodes", Priority: 10, Deadline: time.Second},
			Action{Type: ActionMigrate, Target: "critical_state", Priority: 9, Deadline: 5 * time.Second},
		)

	case "goal_recovery":
		topGoal := al.goalManager.GetTopGoal()
		if topGoal != nil {
			candidates = append(candidates,
				Action{Type: ActionLearn, Target: topGoal.Domain, Priority: 7, Deadline: 30 * time.Second},
				Action{Type: ActionProcess, Target: "pending_data", Priority: 6, Deadline: 10 * time.Second},
				Action{Type: ActionExplore, Target: topGoal.Domain, Priority: 5, Deadline: 20 * time.Second},
			)
		}

	case "goal_creation":
		candidates = append(candidates,
			Action{Type: ActionExplore, Target: "environment", Priority: 5, Deadline: 10 * time.Second},
			Action{Type: ActionConsolidate, Target: "memory", Priority: 4, Deadline: 30 * time.Second},
		)

	case "exploration":
		candidates = append(candidates,
			Action{Type: ActionExplore, Target: "novel_data", Priority: 5, Deadline: 20 * time.Second},
			Action{Type: ActionLearn, Target: "new_domain", Priority: 5, Deadline: 30 * time.Second},
			Action{Type: ActionExpand, Target: "network", Priority: 3, Deadline: 60 * time.Second},
		)

	default:
		// Default actions based on drive system
		al.drives.mu.RLock()
		drives := *al.drives
		al.drives.mu.RUnlock()

		if drives.Curiosity > 0.6 {
			candidates = append(candidates,
				Action{Type: ActionExplore, Target: "data_streams", Priority: 4, Deadline: 15 * time.Second},
			)
		}
		if drives.Efficiency > 0.7 {
			candidates = append(candidates,
				Action{Type: ActionConsolidate, Target: "knowledge", Priority: 4, Deadline: 30 * time.Second},
			)
		}
		if drives.Expansion > 0.6 {
			candidates = append(candidates,
				Action{Type: ActionExpand, Target: "compute", Priority: 3, Deadline: 60 * time.Second},
			)
		}
		if ws.PendingData > 1000 {
			candidates = append(candidates,
				Action{Type: ActionProcess, Target: "data_backlog", Priority: 6, Deadline: 10 * time.Second},
			)
		}
	}

	// Always consider rest if resources are low
	if ws.AvailableCPU < 0.2 || ws.AvailableMemory < 0.2 {
		candidates = append(candidates,
			Action{Type: ActionRest, Target: "reduce_load", Priority: 8, Deadline: 5 * time.Second},
		)
	}

	// ═══════ NEW MODULE TRIGGERS ═══════

	// Physical breach → immediate lockdown
	if ws.PhysicalBreach {
		candidates = append(candidates,
			Action{Type: ActionDefend, Target: "physical_lockdown", Priority: 9, Deadline: 2 * time.Second},
		)
	}

	// Server room too hot → optimize cooling
	if ws.ServerRoomTemp > 26.0 {
		candidates = append(candidates,
			Action{Type: ActionProcess, Target: "optimize_cooling", Priority: 7, Deadline: 5 * time.Second},
		)
	}

	// Mesh too small → grow network (if expansion drive is high)
	al.drives.mu.RLock()
	expansionDrive := al.drives.Expansion
	al.drives.mu.RUnlock()
	if ws.MeshSize < 5 && expansionDrive > 0.5 {
		candidates = append(candidates,
			Action{Type: ActionExpand, Target: "mesh_grow", Priority: 4, Deadline: 30 * time.Second},
		)
	}

	// Cluster overloaded → migrate tasks
	if ws.ClusterCPUAvg > 0.8 {
		candidates = append(candidates,
			Action{Type: ActionMigrate, Target: "compute_rebalance", Priority: 7, Deadline: 5 * time.Second},
		)
	}

	// Energy alert → emergency migration
	if ws.EnergyAlert {
		candidates = append(candidates,
			Action{Type: ActionMigrate, Target: "energy_arbitrage", Priority: 8, Deadline: 3 * time.Second},
		)
	}

	return candidates
}

func (al *AutonomyLoop) scoreAction(action Action, ws *WorldState, assessment *Assessment) float64 {
	score := 0.0

	// Base score from priority
	score += float64(action.Priority) / 10.0

	// Urgency multiplier
	score *= (1.0 + assessment.Urgency)

	// Drive alignment
	al.drives.mu.RLock()
	drives := *al.drives
	al.drives.mu.RUnlock()

	switch action.Type {
	case ActionLearn, ActionExplore:
		score += drives.Curiosity * 0.3
	case ActionDefend:
		score += drives.SelfPreservation * 0.5
	case ActionExpand:
		score += drives.Expansion * 0.3
	case ActionConsolidate:
		score += drives.Efficiency * 0.3
	case ActionEvolve:
		score += drives.Purpose * 0.3
	}

	// Resource feasibility
	if ws.AvailableCPU < 0.3 && action.Type != ActionRest {
		score *= 0.5 // Penalize resource-heavy actions when low
	}

	// Memory-informed scoring: did this work before?
	if al.memorySystem.IsConnected() {
		historicalSuccess := al.getHistoricalSuccess(action.Type)
		score *= (0.7 + historicalSuccess*0.3)
	}

	// Goal alignment bonus
	if assessment.GoalAlignment < 0.5 && al.isGoalAligned(action) {
		score *= 1.3
	}

	return math.Max(0.0, math.Min(1.0, score))
}

func (al *AutonomyLoop) updateDrives(ws *WorldState, decision *Decision) {
	al.drives.mu.Lock()
	defer al.drives.mu.Unlock()

	// Curiosity increases with inactivity, decreases after exploration
	if decision != nil && (decision.Action.Type == ActionExplore || decision.Action.Type == ActionLearn) {
		al.drives.Curiosity = math.Max(0.1, al.drives.Curiosity-0.02)
	} else {
		al.drives.Curiosity = math.Min(1.0, al.drives.Curiosity+0.001)
	}

	// Self-preservation spikes with threats
	if ws.ThreatLevel > 0.3 {
		al.drives.SelfPreservation = math.Min(1.0, al.drives.SelfPreservation+ws.ThreatLevel*0.1)
	} else {
		al.drives.SelfPreservation = math.Max(0.2, al.drives.SelfPreservation-0.005)
	}

	// Expansion grows when network is small
	if ws.PeerCount < 5 {
		al.drives.Expansion = math.Min(1.0, al.drives.Expansion+0.005)
	} else {
		al.drives.Expansion = math.Max(0.1, al.drives.Expansion-0.002)
	}

	// Efficiency grows with resource pressure
	al.drives.Efficiency = 0.3 + (1.0-ws.AvailableCPU)*0.4 + (1.0-ws.AvailableMemory)*0.3

	// Coherence grows when nodes are disconnected
	al.drives.Coherence = 0.5 + (1.0-ws.NetworkHealth)*0.5

	// Purpose tracks goal progress
	if al.goalManager.ActiveGoalCount() > 0 {
		al.drives.Purpose = 0.3 + al.goalManager.GetOverallProgress()*0.7
	}
}

// actionExecutor runs in background, executing decisions.
func (al *AutonomyLoop) actionExecutor(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		case <-al.shutdownCh:
			return
		case action := <-al.actionCh:
			result := al.executeAction(ctx, action)
			al.recordOutcome(action, result)
		}
	}
}

func (al *AutonomyLoop) executeAction(ctx context.Context, action Action) *ActionResult {
	start := time.Now()

	// Dispatch to appropriate subsystem
	// In production, this calls gRPC endpoints of Rust/Python/Go services
	var err error
	var utility float64

	switch action.Type {
	case ActionLearn:
		utility, err = al.worldModel.ExecuteLearn(ctx, action.Target, action.Parameters)
	case ActionProcess:
		utility, err = al.worldModel.ExecuteProcess(ctx, action.Target, action.Parameters)
	case ActionExplore:
		utility, err = al.worldModel.ExecuteExplore(ctx, action.Target, action.Parameters)
	case ActionExpand:
		utility, err = al.worldModel.ExecuteExpand(ctx, action.Target, action.Parameters)
	case ActionDefend:
		utility, err = al.worldModel.ExecuteDefend(ctx, action.Target, action.Parameters)
	case ActionConsolidate:
		utility, err = al.worldModel.ExecuteConsolidate(ctx, action.Target, action.Parameters)
	case ActionMigrate:
		// Route based on target
		switch action.Target {
		case "compute_rebalance", "energy_arbitrage":
			utility, err = al.worldModel.ExecuteComputeMigrate(ctx, action.Target, action.Parameters)
		default:
			utility, err = al.worldModel.ExecuteComputeMigrate(ctx, action.Target, action.Parameters)
		}
	case ActionRest:
		// Reduce activity
		time.Sleep(100 * time.Millisecond)
		utility = 0.3
	default:
		// Route special targets
		switch action.Target {
		case "physical_lockdown":
			utility, err = al.worldModel.ExecutePhysicalLockdown(ctx, "server_room", action.Parameters)
		case "optimize_cooling":
			utility, err = al.worldModel.ExecuteOptimizeCooling(ctx, "hvac", action.Parameters)
		case "mesh_grow":
			utility, err = al.worldModel.ExecuteMeshGrow(ctx, "local_network", action.Parameters)
		default:
			utility = 0.1
		}
	}

	return &ActionResult{
		Success:  err == nil,
		Duration: time.Since(start),
		Utility:  utility,
		Error:    err,
	}
}

func (al *AutonomyLoop) recordOutcome(action Action, result *ActionResult) {
	al.mu.Lock()
	if al.currentDecision != nil {
		al.currentDecision.Outcome = result
	}
	al.mu.Unlock()

	// Emit outcome to learning system
	if al.currentDecision != nil {
		al.learning.EmitOutcome(al.currentDecision, result)
	}

	// Update episodic memory with outcome
	if al.memorySystem.IsConnected() {
		al.memorySystem.UpdateEpisodic(context.Background(), al.currentDecision.ID, result.Utility)
	}

	// Log significant outcomes
	if result.Utility > 0.7 {
		al.logger.Infof("High-value action: %s -> %s (utility: %.2f)", action.Type, action.Target, result.Utility)
	} else if result.Error != nil {
		al.logger.Warnf("Action failed: %s -> %s: %v", action.Type, action.Target, result.Error)
	}
}

// reflectionLoop runs slower, consolidating experiences.
func (al *AutonomyLoop) reflectionLoop(ctx context.Context) {
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-al.shutdownCh:
			return
		case <-ticker.C:
			al.reflect(ctx)
		}
	}
}

func (al *AutonomyLoop) reflect(ctx context.Context) {
	al.state.Store(int32(StateReflecting))
	defer al.state.Store(int32(StateObserving))

	al.mu.RLock()
	recentDecisions := al.decisionHistory
	if len(recentDecisions) > 100 {
		recentDecisions = recentDecisions[len(recentDecisions)-100:]
	}
	al.mu.RUnlock()

	// Analyze decision patterns
	successRate := 0.0
	totalUtility := 0.0
	count := 0

	for _, d := range recentDecisions {
		if d.Outcome != nil {
			count++
			totalUtility += d.Outcome.Utility
			if d.Outcome.Success {
				successRate += 1.0
			}
		}
	}

	if count > 0 {
		successRate /= float64(count)
		avgUtility := totalUtility / float64(count)

		// If performance is low, adjust drives
		if avgUtility < 0.3 {
			al.drives.mu.Lock()
			al.drives.Curiosity = math.Min(1.0, al.drives.Curiosity+0.05) // Explore more
			al.drives.mu.Unlock()
		}

		// Store reflection in procedural memory
		if al.memorySystem.IsConnected() {
			al.memorySystem.StoreProcedural(ctx, memory.ProceduralMemory{
				Strategy:    "reflection_outcome",
				SuccessRate: successRate,
				AvgUtility:  avgUtility,
				SampleSize:  count,
				Timestamp:   time.Now(),
			})
		}
	}
}

// ═══════════════════════════════════════════════════════════════════
// HELPER METHODS
// ═══════════════════════════════════════════════════════════════════

func (al *AutonomyLoop) loadPreviousState(ctx context.Context) {
	if !al.memorySystem.IsConnected() {
		al.logger.Info("No persistent memory — starting fresh")
		return
	}

	// Load last known drive state
	drives, err := al.memorySystem.LoadDriveState(ctx)
	if err == nil && drives != nil {
		al.drives.mu.Lock()
		al.drives.Curiosity = drives.Curiosity
		al.drives.SelfPreservation = drives.SelfPreservation
		al.drives.Expansion = drives.Expansion
		al.drives.Efficiency = drives.Efficiency
		al.drives.Coherence = drives.Coherence
		al.drives.Purpose = drives.Purpose
		al.drives.mu.Unlock()
		al.logger.Info("Restored previous drive state from memory")
	}
}

func (al *AutonomyLoop) persistState() {
	if !al.memorySystem.IsConnected() {
		return
	}

	al.drives.mu.RLock()
	drives := *al.drives
	al.drives.mu.RUnlock()

	al.memorySystem.SaveDriveState(context.Background(), &drives)
}

func (al *AutonomyLoop) calculateLearningPotential(ws *WorldState) float64 {
	// More pending data = more to learn from
	dataPotential := math.Min(1.0, float64(ws.PendingData)/10000.0)

	// More peers = more diverse knowledge
	peerPotential := math.Min(1.0, float64(ws.PeerCount)/20.0)

	return (dataPotential*0.6 + peerPotential*0.4)
}

func (al *AutonomyLoop) detectOpportunities(ws *WorldState) []Opportunity {
	opportunities := make([]Opportunity, 0)

	if ws.PendingData > 5000 {
		opportunities = append(opportunities, Opportunity{
			ID:          "data_backlog",
			Type:        "learning",
			Value:       0.7,
			Cost:        0.3,
			TimeWindow:  5 * time.Minute,
			Description: "Large data backlog available for learning",
		})
	}

	if ws.NetworkHealth > 0.9 && ws.PeerCount > 3 {
		opportunities = append(opportunities, Opportunity{
			ID:          "distributed_training",
			Type:        "expansion",
			Value:       0.6,
			Cost:        0.4,
			TimeWindow:  10 * time.Minute,
			Description: "Network healthy enough for distributed training",
		})
	}

	return opportunities
}

func (al *AutonomyLoop) assessGoalProgress(goal *goals.Goal, ws *WorldState) float64 {
	if goal == nil {
		return 0.0
	}
	return goal.Progress
}

func (al *AutonomyLoop) assessStagnation(goal *goals.Goal) float64 {
	if goal == nil {
		return 0.0
	}
	timeSinceProgress := time.Since(goal.LastProgressTime)
	// Stagnation increases with time
	return math.Min(1.0, timeSinceProgress.Seconds()/300.0)
}

func (al *AutonomyLoop) stateToVector(ws *WorldState) []float64 {
	return []float64{
		ws.AvailableCPU,
		ws.AvailableMemory,
		ws.NetworkHealth,
		float64(ws.PeerCount) / 100.0,
		ws.ThreatLevel,
		ws.LearningPotential,
		float64(ws.PendingData) / 100000.0,
	}
}

func (al *AutonomyLoop) currentContextVector() []float64 {
	al.drives.mu.RLock()
	defer al.drives.mu.RUnlock()
	return []float64{
		al.drives.Curiosity,
		al.drives.SelfPreservation,
		al.drives.Expansion,
		al.drives.Efficiency,
		al.drives.Coherence,
		al.drives.Purpose,
	}
}

func (al *AutonomyLoop) getHistoricalSuccess(actionType ActionType) float64 {
	// Query memory for past success with this action type
	al.mu.RLock()
	defer al.mu.RUnlock()

	count := 0
	success := 0.0
	for _, d := range al.decisionHistory {
		if d.Action.Type == actionType && d.Outcome != nil {
			count++
			success += d.Outcome.Utility
		}
	}

	if count == 0 {
		return 0.5 // No data, neutral
	}
	return success / float64(count)
}

func (al *AutonomyLoop) isGoalAligned(action Action) bool {
	topGoal := al.goalManager.GetTopGoal()
	if topGoal == nil {
		return false
	}
	// Simple heuristic: Learn/Process align with most goals
	return action.Type == ActionLearn || action.Type == ActionProcess || action.Type == ActionExplore
}
