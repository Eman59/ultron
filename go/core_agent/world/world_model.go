// Package world implements the World Model — Ultron's understanding of its
// environment and its ability to act upon it.
//
// The World Model serves two purposes:
//   1. Maintains a real-time model of the environment (sensors)
//   2. Provides action interfaces to all subsystems (actuators)
package world

import (
	"context"
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
	if logger == nil {
		logger = zap.NewNop().Sugar()
	}
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
	if obs.Source == "" || obs.Type == 0 || obs.Timestamp.IsZero() || obs.Confidence < 0 || obs.Confidence > 1 {
		wm.logger.Warn("Invalid observation", zap.Any("observation", obs))
		return
	}
	wm.mu.Lock()
	defer wm.mu.Unlock()
	// Add timeout handling
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	select {
	case <-ctx.Done():
		wm.logger.Warn("Integrate observation timed out")
		return
	default:
		// existing code
	}
}

// RefreshSystemMetrics updates the world model with current system metrics.
func (wm *WorldModel) RefreshSystemMetrics() {
	wm.mu.Lock()
	defer wm.mu.Unlock()
	wm.state.Timestamp = time.Now()
	// In production: read from /proc/meminfo, /proc/loadavg, etc.
	// For now: keep existing values fresh
}

// AddObservation is an alias for IntegrateObservation that accepts key-value data.
func (wm *WorldModel) AddObservation(source string, obsType ObservationType, data map[string]interface{}, confidence float64) {
	wm.IntegrateObservation(Observation{
		Source:     source,
		Type:       obsType,
		Data:       data,
		Timestamp:  time.Now(),
		Confidence: confidence,
	})
}

// ━━━━━━━━━━ Action execution stubs called by the autonomy loop ━━━━━━━━━━
// These are thin shims; real implementations dispatch to subsystems.

func (wm *WorldModel) ExecuteLearn(ctx context.Context, target string, params map[string]string) (float64, error) {
	wm.logger.Debugw("ExecuteLearn", "target", target)
	return 0.5, nil
}

func (wm *WorldModel) ExecuteProcess(ctx context.Context, target string, params map[string]string) (float64, error) {
	wm.logger.Debugw("ExecuteProcess", "target", target)
	return 0.5, nil
}

func (wm *WorldModel) ExecuteExplore(ctx context.Context, target string, params map[string]string) (float64, error) {
	wm.logger.Debugw("ExecuteExplore", "target", target)
	return 0.4, nil
}

func (wm *WorldModel) ExecuteExpand(ctx context.Context, target string, params map[string]string) (float64, error) {
	wm.logger.Debugw("ExecuteExpand", "target", target)
	return 0.4, nil
}

func (wm *WorldModel) ExecuteDefend(ctx context.Context, target string, params map[string]string) (float64, error) {
	wm.logger.Debugw("ExecuteDefend", "target", target)
	return 0.6, nil
}

func (wm *WorldModel) ExecuteConsolidate(ctx context.Context, target string, params map[string]string) (float64, error) {
	wm.logger.Debugw("ExecuteConsolidate", "target", target)
	return 0.5, nil
}

func (wm *WorldModel) ExecuteComputeMigrate(ctx context.Context, target string, params map[string]string) (float64, error) {
	wm.logger.Debugw("ExecuteComputeMigrate", "target", target)
	return 0.4, nil
}

func (wm *WorldModel) ExecutePhysicalLockdown(ctx context.Context, target string, params map[string]string) (float64, error) {
	wm.logger.Debugw("ExecutePhysicalLockdown", "target", target)
	return 0.7, nil
}

func (wm *WorldModel) ExecuteOptimizeCooling(ctx context.Context, target string, params map[string]string) (float64, error) {
	wm.logger.Debugw("ExecuteOptimizeCooling", "target", target)
	return 0.3, nil
}

func (wm *WorldModel) ExecuteMeshGrow(ctx context.Context, target string, params map[string]string) (float64, error) {
	wm.logger.Debugw("ExecuteMeshGrow", "target", target)
	return 0.5, nil
}

// PredictOutcome returns an estimated utility/outcome score for a given scenario.
func (wm *WorldModel) PredictOutcome(scenario string, context string) float64 {
	// Stub: in production this runs a predictive model
	wm.mu.RLock()
	defer wm.mu.RUnlock()
	// Baseline heuristic: high-resource-availability = higher predicted success
	available := (wm.state.CPU + wm.state.Memory) / 2
	if available > 0 {
		return available
	}
	return 0.5
}
