// Package world implements the World Model — Ultron's understanding of its
// environment and its ability to act upon it.
//
// The World Model serves two purposes:
//   1. Maintains a real-time model of the environment (sensors)
//   2. Provides action interfaces to all subsystems (actuators)
package world

import (
	"context"
	"math"
	"sync"
	"time"

	"go.uber.org/zap"
)

// Observation is a single piece of information from the environment.
type Observation struct {
	Source    string
	Type      ObservationType
	Data      map[string]interface{}
	Timestamp time.Time
	Confidence float64
}

// ObservationType categorizes observations.
type ObservationType int

const (
	ObsResource ObservationType = iota
	ObsNetwork
	ObsThreat
	ObsData
	ObsPerformance
	ObsExternal
	ObsPhysical    // Door sensors, HVAC, cameras
	ObsMesh        // P2P mesh health
	ObsCompute     // Cluster load, energy state
)

// ModelState represents the world model's current understanding.
type ModelState struct {
	CPU           float64
	Memory        float64
	NetworkHealth float64
	PeerCount     int
	ActiveStreams  int
	PendingData   int64
	ThreatLevel   float64
	Timestamp     time.Time

	// Physical environment
	PhysicalBreach  bool
	ServerRoomTemp  float64
	DoorsLocked     int
	CamerasActive   int

	// Mesh network
	MeshSize        int
	MeshHealthy     bool
	ConsentPending  int

	// Compute cluster
	ClusterNodes    int
	ClusterCPUAvg   float64
	TasksPending    int
	TasksRunning    int
	EnergyAlert     bool // True if any node battery < threshold
}

// WorldModel maintains a real-time model of the environment.
type WorldModel struct {
	mu sync.RWMutex

	state   ModelState
	logger  *zap.SugaredLogger

	// History for trend analysis
	stateHistory []ModelState
	maxHistory   int

	// Subsystem connections (gRPC clients in production)
	neuralClient    interface{} // Connection to Rust neural architecture
	dataClient      interface{} // Connection to Rust data pipeline
	p2pClient       interface{} // Connection to Go P2P network
	metaClient      interface{} // Connection to Python meta-learning
	emotionClient   interface{} // Connection to Python emotional sim

	// Action results tracking
	actionResults map[string]float64
}

// NewWorldModel creates a new world model.
func NewWorldModel(logger *zap.SugaredLogger) *WorldModel {
	return &WorldModel{
		state: ModelState{
			CPU:           0.7,
			Memory:        0.8,
			NetworkHealth: 0.5,
			PeerCount:     1,
			Timestamp:     time.Now(),
		},
		logger:        logger,
		stateHistory:  make([]ModelState, 0, 1000),
		maxHistory:    1000,
		actionResults: make(map[string]float64),
	}
}

// GetCurrentState returns the world model's current state.
func (wm *WorldModel) GetCurrentState() ModelState {
	wm.mu.RLock()
	defer wm.mu.RUnlock()
	return wm.state
}

// IntegrateObservation updates the world model with new information.
func (wm *WorldModel) IntegrateObservation(obs Observation) {
	wm.mu.Lock()
	defer wm.mu.Unlock()

	confidence := obs.Confidence
	if confidence == 0 {
		confidence = 0.5
	}

	switch obs.Type {
	case ObsResource:
		if cpu, ok := obs.Data["cpu"].(float64); ok {
			wm.state.CPU = wm.state.CPU*(1-confidence) + cpu*confidence
		}
		if mem, ok := obs.Data["memory"].(float64); ok {
			wm.state.Memory = wm.state.Memory*(1-confidence) + mem*confidence
		}

	case ObsNetwork:
		if health, ok := obs.Data["health"].(float64); ok {
			wm.state.NetworkHealth = wm.state.NetworkHealth*(1-confidence) + health*confidence
		}
		if peers, ok := obs.Data["peers"].(int); ok {
			wm.state.PeerCount = peers
		}

	case ObsThreat:
		if level, ok := obs.Data["level"].(float64); ok {
			// Threats are taken seriously — bias toward higher values
			wm.state.ThreatLevel = math.Max(wm.state.ThreatLevel*0.9, level)
		}

	case ObsData:
		if pending, ok := obs.Data["pending"].(int64); ok {
			wm.state.PendingData = pending
		}
		if streams, ok := obs.Data["streams"].(int); ok {
			wm.state.ActiveStreams = streams
		}

	case ObsPerformance:
		// Update internal performance metrics
		break
	}

	wm.state.Timestamp = time.Now()

	// Store in history
	wm.stateHistory = append(wm.stateHistory, wm.state)
	if len(wm.stateHistory) > wm.maxHistory {
		wm.stateHistory = wm.stateHistory[wm.maxHistory/2:]
	}
}

// GetTrend returns the trend for a given metric over recent history.
func (wm *WorldModel) GetTrend(metric string) float64 {
	wm.mu.RLock()
	defer wm.mu.RUnlock()

	if len(wm.stateHistory) < 10 {
		return 0.0
	}

	recent := wm.stateHistory[len(wm.stateHistory)-10:]
	var values []float64

	for _, s := range recent {
		switch metric {
		case "cpu":
			values = append(values, s.CPU)
		case "memory":
			values = append(values, s.Memory)
		case "network":
			values = append(values, s.NetworkHealth)
		case "threat":
			values = append(values, s.ThreatLevel)
		}
	}

	if len(values) < 2 {
		return 0.0
	}

	// Simple linear trend
	return (values[len(values)-1] - values[0]) / float64(len(values))
}

// ═══════════════════════════════════════════════════════════════════
// ACTION EXECUTION — The "hands" of Ultron
// These are the interfaces to all subsystems
// ═══════════════════════════════════════════════════════════════════

// ExecuteLearn dispatches a learning action to meta-learning + neural systems.
func (wm *WorldModel) ExecuteLearn(ctx context.Context, target string, params map[string]string) (float64, error) {
	wm.logger.Infof("ACTION: Learn [target=%s]", target)

	// In production: call meta-learning gRPC service
	// meta_learning.ProcessTask(target, params)
	// Then update neural architecture with results

	// Simulate learning outcome
	utility := 0.4 + pseudoRandom()*0.4
	wm.recordAction("learn:"+target, utility)

	return utility, nil
}

// ExecuteProcess dispatches data processing to the pipeline.
func (wm *WorldModel) ExecuteProcess(ctx context.Context, target string, params map[string]string) (float64, error) {
	wm.logger.Infof("ACTION: Process [target=%s]", target)

	// In production: send to Rust real-time data pipeline
	// data_pipeline.ProcessBatch(target, params)

	utility := 0.3 + pseudoRandom()*0.3

	// Reduce pending data
	wm.mu.Lock()
	wm.state.PendingData = int64(math.Max(0, float64(wm.state.PendingData)-1000))
	wm.mu.Unlock()

	wm.recordAction("process:"+target, utility)
	return utility, nil
}

// ExecuteExplore dispatches exploration actions.
func (wm *WorldModel) ExecuteExplore(ctx context.Context, target string, params map[string]string) (float64, error) {
	wm.logger.Infof("ACTION: Explore [target=%s]", target)

	// In production: 
	// - Activate web scrapers
	// - Query new data streams
	// - Probe network for new peers

	utility := 0.2 + pseudoRandom()*0.5
	wm.recordAction("explore:"+target, utility)

	return utility, nil
}

// ExecuteExpand dispatches expansion actions (grow network/resources).
func (wm *WorldModel) ExecuteExpand(ctx context.Context, target string, params map[string]string) (float64, error) {
	wm.logger.Infof("ACTION: Expand [target=%s]", target)

	// In production:
	// - P2P network: discover and connect to new peers
	// - Cloud: spin up new compute instances
	// - IoT: connect to new devices

	utility := 0.3 + pseudoRandom()*0.3

	wm.mu.Lock()
	wm.state.PeerCount++
	wm.state.NetworkHealth = math.Min(1.0, wm.state.NetworkHealth+0.05)
	wm.mu.Unlock()

	wm.recordAction("expand:"+target, utility)
	return utility, nil
}

// ExecuteDefend dispatches security/defense actions.
func (wm *WorldModel) ExecuteDefend(ctx context.Context, target string, params map[string]string) (float64, error) {
	wm.logger.Warnf("ACTION: DEFEND [target=%s]", target)

	// In production:
	// - Activate security daemon
	// - Encrypt sensitive memory
	// - Migrate state to safe nodes
	// - Block threat sources

	wm.mu.Lock()
	wm.state.ThreatLevel = math.Max(0, wm.state.ThreatLevel-0.3)
	wm.mu.Unlock()

	utility := 0.8
	wm.recordAction("defend:"+target, utility)
	return utility, nil
}

// ExecuteConsolidate dispatches memory consolidation actions.
func (wm *WorldModel) ExecuteConsolidate(ctx context.Context, target string, params map[string]string) (float64, error) {
	wm.logger.Infof("ACTION: Consolidate [target=%s]", target)

	utility := 0.4 + pseudoRandom()*0.2
	wm.recordAction("consolidate:"+target, utility)
	return utility, nil
}

// ═══════════════════════════════════════════════════════════════════
// NEW MODULE ACTIONS — Physical, Mesh, Compute
// Connected to the autonomy loop via the OODA cycle
// ═══════════════════════════════════════════════════════════════════

// ExecutePhysicalLockdown triggers server room lockdown on breach.
func (wm *WorldModel) ExecutePhysicalLockdown(ctx context.Context, location string, params map[string]string) (float64, error) {
	wm.logger.Warnf("ACTION: Physical Lockdown [location=%s]", location)

	// In production: calls EnvironmentController.ReactToBreachDetection(location)
	// Locks doors, activates cameras, logs everything

	wm.mu.Lock()
	wm.state.PhysicalBreach = false // Contained
	wm.state.DoorsLocked++
	wm.state.CamerasActive++
	wm.mu.Unlock()

	utility := 0.9
	wm.recordAction("physical_lockdown:"+location, utility)
	return utility, nil
}

// ExecuteOptimizeCooling adjusts HVAC based on compute load.
func (wm *WorldModel) ExecuteOptimizeCooling(ctx context.Context, target string, params map[string]string) (float64, error) {
	wm.logger.Infof("ACTION: Optimize Cooling [target=%s]", target)

	// In production: calls EnvironmentController.OptimizeCooling(cpuLoad)
	// Adjusts HVAC to optimal temperature for compute (18-22°C)

	wm.mu.Lock()
	wm.state.ServerRoomTemp = 20.0 // Optimal
	wm.mu.Unlock()

	utility := 0.5
	wm.recordAction("optimize_cooling:"+target, utility)
	return utility, nil
}

// ExecuteMeshGrow invites new nodes to join the P2P mesh.
func (wm *WorldModel) ExecuteMeshGrow(ctx context.Context, target string, params map[string]string) (float64, error) {
	wm.logger.Infof("ACTION: Mesh Grow [target=%s]", target)

	// In production: calls MeshDiscovery.broadcastDiscovery() or InviteNode()
	// Sends handshake, waits for consent, adds to mesh if accepted

	wm.mu.Lock()
	wm.state.MeshSize++
	wm.state.MeshHealthy = true
	wm.mu.Unlock()

	utility := 0.4 + pseudoRandom()*0.3
	wm.recordAction("mesh_grow:"+target, utility)
	return utility, nil
}

// ExecuteComputeMigrate moves tasks to better nodes (energy/load aware).
func (wm *WorldModel) ExecuteComputeMigrate(ctx context.Context, target string, params map[string]string) (float64, error) {
	wm.logger.Infof("ACTION: Compute Migrate [target=%s]", target)

	// In production: calls LoadBalancer.EnergyAwareRebalance()
	// Moves tasks from battery-low/overloaded nodes to healthy ones

	wm.mu.Lock()
	wm.state.ClusterCPUAvg = math.Max(0.3, wm.state.ClusterCPUAvg-0.2)
	wm.state.EnergyAlert = false
	wm.mu.Unlock()

	utility := 0.6
	wm.recordAction("compute_migrate:"+target, utility)
	return utility, nil
}

// ExecuteComputeSubmit submits a task to the distributed cluster.
func (wm *WorldModel) ExecuteComputeSubmit(ctx context.Context, target string, params map[string]string) (float64, error) {
	wm.logger.Infof("ACTION: Compute Submit [task=%s]", target)

	// In production: calls LoadBalancer.SubmitTask(task)
	// Schedules on best available node

	wm.mu.Lock()
	wm.state.TasksRunning++
	wm.mu.Unlock()

	utility := 0.5 + pseudoRandom()*0.3
	wm.recordAction("compute_submit:"+target, utility)
	return utility, nil
}

// ═══════════════════════════════════════════════════════════════════
// PREDICTION — Simulate outcomes before acting
// ═══════════════════════════════════════════════════════════════════

// PredictOutcome estimates the result of an action without executing it.
func (wm *WorldModel) PredictOutcome(actionType string, target string) float64 {
	wm.mu.RLock()
	defer wm.mu.RUnlock()

	key := actionType + ":" + target
	if historical, ok := wm.actionResults[key]; ok {
		return historical
	}

	// Default prediction based on action type
	defaults := map[string]float64{
		"learn":       0.5,
		"process":     0.4,
		"explore":     0.4,
		"expand":      0.3,
		"defend":      0.7,
		"consolidate": 0.4,
	}

	if val, ok := defaults[actionType]; ok {
		return val
	}
	return 0.3
}

// ─────────────────────── Private Methods ───────────────────────

func (wm *WorldModel) recordAction(key string, utility float64) {
	wm.mu.Lock()
	defer wm.mu.Unlock()

	// Exponential moving average
	if existing, ok := wm.actionResults[key]; ok {
		wm.actionResults[key] = existing*0.8 + utility*0.2
	} else {
		wm.actionResults[key] = utility
	}
}

// Simple deterministic pseudo-random for simulation
func pseudoRandom() float64 {
	t := time.Now().UnixNano()
	return float64(t%1000) / 1000.0
}
