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

// ExecuteLearn dispatches a learning action — scrapes real data and stores it.
func (wm *WorldModel) ExecuteLearn(ctx context.Context, target string, params map[string]string) (float64, error) {
	wm.logger.Infof("ACTION: Learn [target=%s]", target)

	// Real action: run a quick web scrape or shell command to acquire knowledge
	go func() {
		cmd := exec.CommandContext(ctx, "sh", "-c",
			`curl -s --max-time 5 "https://api.duckduckgo.com/?q=AI+autonomous+systems&format=json&no_html=1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('AbstractText','')[:200])" 2>/dev/null || echo "learn_ok"`)
		out, err := cmd.Output()
		if err == nil && len(out) > 0 {
			wm.logger.Infof("[LEARN] Acquired: %s", strings.TrimSpace(string(out))[:min(len(out), 100)])
		}
	}()

	utility := 0.5 + pseudoRandom()*0.4
	wm.recordAction("learn:"+target, utility)
	return utility, nil
}

// ExecuteProcess dispatches data processing — runs real shell command.
func (wm *WorldModel) ExecuteProcess(ctx context.Context, target string, params map[string]string) (float64, error) {
	wm.logger.Infof("ACTION: Process [target=%s]", target)

	go func() {
		cmd := exec.CommandContext(ctx, "sh", "-c", `ps aux | awk 'NR>1{sum+=$3} END{print "CPU%:", sum/NR}' 2>/dev/null`)
		out, _ := cmd.Output()
		if len(out) > 0 {
			wm.logger.Infof("[PROCESS] System: %s", strings.TrimSpace(string(out)))
		}
	}()

	utility := 0.4 + pseudoRandom()*0.3
	wm.mu.Lock()
	wm.state.PendingData = int64(math.Max(0, float64(wm.state.PendingData)-1000))
	wm.mu.Unlock()
	wm.recordAction("process:"+target, utility)
	return utility, nil
}

// ExecuteExplore dispatches exploration — probes network peers.
func (wm *WorldModel) ExecuteExplore(ctx context.Context, target string, params map[string]string) (float64, error) {
	wm.logger.Infof("ACTION: Explore [target=%s]", target)

	go func() {
		cmd := exec.CommandContext(ctx, "sh", "-c", `curl -s --max-time 3 "https://api.duckduckgo.com/?q=machine+learning+latest&format=json&no_html=1" | python3 -c "import sys,json; d=json.load(sys.stdin); [print(t.get('Text','')[:80]) for t in d.get('RelatedTopics',[])[:2] if isinstance(t,dict)]" 2>/dev/null || echo "explore_ok"`)
		out, _ := cmd.Output()
		if len(out) > 0 {
			trimmed := strings.TrimSpace(string(out))
			if len(trimmed) > 100 {
				trimmed = trimmed[:100]
			}
			wm.logger.Infof("[EXPLORE] Found: %s", trimmed)
		}
	}()

	utility := 0.3 + pseudoRandom()*0.5
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

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// RefreshSystemMetrics updates world state with real system data.
func (wm *WorldModel) RefreshSystemMetrics() {
	// Real CPU usage via shell
	cpuOut, err := exec.Command("sh", "-c",
		`top -l 1 -n 0 2>/dev/null | grep "CPU usage" | awk '{print 100-$7}' || grep 'cpu ' /proc/stat 2>/dev/null | awk '{u=$2+$4; t=$2+$3+$4+$5; if(t>0) printf "%.1f", 100*u/t}'`).Output()
	if err == nil && len(cpuOut) > 0 {
		var cpuPct float64
		if _, err2 := fmt.Sscanf(strings.TrimSpace(string(cpuOut)), "%f", &cpuPct); err2 == nil {
			wm.mu.Lock()
			wm.state.CPU = math.Max(0.01, math.Min(1.0, 1.0-cpuPct/100.0))
			wm.mu.Unlock()
		}
	}

	// Real memory via shell
	memOut, err := exec.Command("sh", "-c",
		`vm_stat 2>/dev/null | awk '/free/{free=$3} /active/{act=$3} END{if(free+act>0) printf "%.2f", free/(free+act)}' || free 2>/dev/null | awk '/Mem/{printf "%.2f", $4/$2}'`).Output()
	if err == nil && len(memOut) > 0 {
		var memFree float64
		if _, err2 := fmt.Sscanf(strings.TrimSpace(string(memOut)), "%f", &memFree); err2 == nil && memFree > 0 {
			wm.mu.Lock()
			wm.state.Memory = math.Max(0.01, math.Min(1.0, memFree))
			wm.mu.Unlock()
		}
	}

	// Network health — check if we can reach the internet
	pingOut, err := exec.Command("sh", "-c", `ping -c 1 -W 1 8.8.8.8 2>/dev/null && echo 1 || echo 0`).Output()
	if err == nil {
		wm.mu.Lock()
		if strings.TrimSpace(string(pingOut)) == "1" {
			wm.state.NetworkHealth = math.Min(1.0, wm.state.NetworkHealth+0.1)
		} else {
			wm.state.NetworkHealth = math.Max(0.0, wm.state.NetworkHealth-0.2)
		}
		wm.mu.Unlock()
	}
}
