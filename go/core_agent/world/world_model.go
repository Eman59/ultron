// Package world implements the World Model — Ultron's understanding of its
// environment and its ability to act upon it.
//
// The World Model serves two purposes:
//   1. Maintains a real-time model of the environment (sensors)
//   2. Provides action interfaces to all subsystems (actuators)
package world

import (
	"context"
	"fmt"
	"math"
	"os/exec"
	"strings"
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