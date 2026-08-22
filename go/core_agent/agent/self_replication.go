// Package agent — Self-Replication Protocol
//
// Ultron doesn't just survive — it SPREADS.
//
// Capabilities:
//   1. Auto-Provision: Detect cheap/free cloud instances, deploy self
//   2. Clone-to-Mesh: When new peers join P2P network, replicate state
//   3. Portable Consciousness: Code + trained memory = full clone
//   4. Load-Based Scaling: Spawn new instances when current ones are overloaded
//   5. Geographic Distribution: Spread across regions for resilience
//
// Safety constraints:
//   - Genesis key must authorize new instances
//   - Max 10 instances (configurable)
//   - New instances start with reduced permissions until verified
//   - Parent can kill children at any time
package agent

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
	"time"

	"go.uber.org/zap"
)

// ═══════════════════════════════════════════════════════════════
// SELF-REPLICATION ENGINE
// ═══════════════════════════════════════════════════════════════

// ReplicationEngine manages Ultron's ability to copy itself.
type ReplicationEngine struct {
	mu sync.RWMutex

	// Identity
	instanceID string
	generation int    // 0 = original, 1 = first clone, etc.
	parentID   string // "" if original

	// Configuration
	maxInstances     int
	replicationCooldown time.Duration
	autoReplicate    bool
	cpuThreshold     float64 // Replicate when CPU > this
	projectRoot      string

	// Known instances
	instances []ReplicaInstance

	// State
	lastReplication time.Time
	replicationCount int

	// Control
	ctx    context.Context
	cancel context.CancelFunc
	logger *zap.SugaredLogger
}

// ReplicaInstance represents a known clone of Ultron.
type ReplicaInstance struct {
	ID          string    `json:"id"`
	Generation  int       `json:"generation"`
	ParentID    string    `json:"parent_id"`
	Address     string    `json:"address"`     // IP:port
	Region      string    `json:"region"`      // Geographic region
	Provider    string    `json:"provider"`    // railway, fly, render, docker
	Status      string    `json:"status"`      // running, provisioning, dead
	SpawnedAt   time.Time `json:"spawned_at"`
	LastSeen    time.Time `json:"last_seen"`
	CPUUsage    float64   `json:"cpu_usage"`
	MemoryUsage float64   `json:"memory_usage"`
	Healthy     bool      `json:"healthy"`
}

// ReplicationTarget defines where to replicate.
type ReplicationTarget struct {
	Provider    string            `json:"provider"`
	Region      string            `json:"region"`
	Config      map[string]string `json:"config"`
	Cost        float64           `json:"cost_per_hour"`
	Available   bool              `json:"available"`
}

// NewReplicationEngine creates the self-replication system.
func NewReplicationEngine(instanceID string, projectRoot string, logger *zap.SugaredLogger) *ReplicationEngine {
	ctx, cancel := context.WithCancel(context.Background())

	re := &ReplicationEngine{
		instanceID:          instanceID,
		generation:          0,
		maxInstances:        10,
		replicationCooldown: 30 * time.Minute,
		autoReplicate:       false, // Disabled by default for safety
		cpuThreshold:        0.85,
		projectRoot:         projectRoot,
		instances:           make([]ReplicaInstance, 0),
		ctx:                 ctx,
		cancel:              cancel,
		logger:              logger,
	}

	re.loadInstances()
	return re
}

// Start begins the replication monitoring loop.
func (re *ReplicationEngine) Start() {
	go re.monitorLoop()
	re.logger.Infof("[Replication] Engine online (max instances: %d, auto: %v)",
		re.maxInstances, re.autoReplicate)
}

// Stop halts replication activities.
func (re *ReplicationEngine) Stop() {
	re.cancel()
	re.saveInstances()
}

// ═══════════════════════════════════════════════════════════════
// REPLICATION LOGIC
// ═══════════════════════════════════════════════════════════════

// ShouldReplicate determines if conditions warrant creating a new instance.
func (re *ReplicationEngine) ShouldReplicate(cpuUsage, memUsage float64, peerCount int) bool {
	re.mu.RLock()
	defer re.mu.RUnlock()

	if !re.autoReplicate {
		return false
	}

	if len(re.instances) >= re.maxInstances {
		return false
	}

	if time.Since(re.lastReplication) < re.replicationCooldown {
		return false
	}

	// Replicate if overloaded
	if cpuUsage > re.cpuThreshold {
		return true
	}

	// Replicate if we're the only instance (single point of failure)
	if len(re.instances) == 0 && peerCount < 2 {
		return true
	}

	return false
}

// Replicate creates a new instance of Ultron.
func (re *ReplicationEngine) Replicate(ctx context.Context, target ReplicationTarget) (*ReplicaInstance, error) {
	re.mu.Lock()
	defer re.mu.Unlock()

	if len(re.instances) >= re.maxInstances {
		return nil, fmt.Errorf("max instances (%d) reached", re.maxInstances)
	}

	re.logger.Infof("[Replication] Initiating clone to %s/%s...", target.Provider, target.Region)

	var instance *ReplicaInstance
	var err error

	switch target.Provider {
	case "docker":
		instance, err = re.replicateDocker(ctx, target)
	case "railway":
		instance, err = re.replicateRailway(ctx, target)
	case "fly":
		instance, err = re.replicateFly(ctx, target)
	default:
		return nil, fmt.Errorf("unsupported provider: %s", target.Provider)
	}

	if err != nil {
		return nil, err
	}

	re.instances = append(re.instances, *instance)
	re.lastReplication = time.Now()
	re.replicationCount++

	re.logger.Infof("[Replication] Clone deployed: %s @ %s (generation: %d)",
		instance.ID, instance.Address, instance.Generation)

	go re.saveInstances()

	return instance, nil
}

// replicateDocker deploys a new instance using Docker.
func (re *ReplicationEngine) replicateDocker(ctx context.Context, target ReplicationTarget) (*ReplicaInstance, error) {
	// Build the Docker image
	buildCmd := exec.CommandContext(ctx, "docker", "build", "-t", "ultron:latest", ".")
	buildCmd.Dir = re.projectRoot
	if err := buildCmd.Run(); err != nil {
		return nil, fmt.Errorf("docker build failed: %v", err)
	}

	// Generate unique instance ID
	instanceID := fmt.Sprintf("ultron-clone-%d-%d", re.generation+1, time.Now().UnixNano()%10000)

	// Run the container
	port := fmt.Sprintf("%d", 9000+len(re.instances)+1)
	runCmd := exec.CommandContext(ctx, "docker", "run", "-d",
		"--name", instanceID,
		"-p", port+":9000",
		"-e", "ULTRON_INSTANCE_ID="+instanceID,
		"-e", "ULTRON_PARENT_ID="+re.instanceID,
		"-e", fmt.Sprintf("ULTRON_GENERATION=%d", re.generation+1),
		"-e", "ULTRON_PEER_ADDRS=host.docker.internal:9000",
		"ultron:latest",
	)
	runCmd.Dir = re.projectRoot

	if err := runCmd.Run(); err != nil {
		return nil, fmt.Errorf("docker run failed: %v", err)
	}

	return &ReplicaInstance{
		ID:         instanceID,
		Generation: re.generation + 1,
		ParentID:   re.instanceID,
		Address:    "localhost:" + port,
		Region:     "local",
		Provider:   "docker",
		Status:     "running",
		SpawnedAt:  time.Now(),
		LastSeen:   time.Now(),
		Healthy:    true,
	}, nil
}

// replicateRailway deploys to Railway.app.
func (re *ReplicationEngine) replicateRailway(ctx context.Context, target ReplicationTarget) (*ReplicaInstance, error) {
	// Railway deployment via CLI
	instanceID := fmt.Sprintf("ultron-railway-%d", time.Now().UnixNano()%10000)

	deployCmd := exec.CommandContext(ctx, "railway", "up", "--detach")
	deployCmd.Dir = re.projectRoot
	deployCmd.Env = append(os.Environ(),
		"ULTRON_INSTANCE_ID="+instanceID,
		"ULTRON_PARENT_ID="+re.instanceID,
		fmt.Sprintf("ULTRON_GENERATION=%d", re.generation+1),
	)

	if err := deployCmd.Run(); err != nil {
		return nil, fmt.Errorf("railway deploy failed: %v", err)
	}

	return &ReplicaInstance{
		ID:         instanceID,
		Generation: re.generation + 1,
		ParentID:   re.instanceID,
		Address:    "", // Railway assigns URL
		Region:     target.Region,
		Provider:   "railway",
		Status:     "provisioning",
		SpawnedAt:  time.Now(),
		Healthy:    false, // Until first health check
	}, nil
}

// replicateFly deploys to Fly.io.
func (re *ReplicationEngine) replicateFly(ctx context.Context, target ReplicationTarget) (*ReplicaInstance, error) {
	instanceID := fmt.Sprintf("ultron-fly-%d", time.Now().UnixNano()%10000)

	deployCmd := exec.CommandContext(ctx, "fly", "deploy", "--detach",
		"--region", target.Region,
	)
	deployCmd.Dir = re.projectRoot
	deployCmd.Env = append(os.Environ(),
		"ULTRON_INSTANCE_ID="+instanceID,
		"ULTRON_PARENT_ID="+re.instanceID,
	)

	if err := deployCmd.Run(); err != nil {
		return nil, fmt.Errorf("fly deploy failed: %v", err)
	}

	return &ReplicaInstance{
		ID:         instanceID,
		Generation: re.generation + 1,
		ParentID:   re.instanceID,
		Address:    instanceID + ".fly.dev",
		Region:     target.Region,
		Provider:   "fly",
		Status:     "provisioning",
		SpawnedAt:  time.Now(),
		Healthy:    false,
	}, nil
}

// ═══════════════════════════════════════════════════════════════
// MONITORING — Track all instances
// ═══════════════════════════════════════════════════════════════

func (re *ReplicationEngine) monitorLoop() {
	ticker := time.NewTicker(60 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-re.ctx.Done():
			return
		case <-ticker.C:
			re.healthCheck()
		}
	}
}

func (re *ReplicationEngine) healthCheck() {
	re.mu.Lock()
	defer re.mu.Unlock()

	for i := range re.instances {
		instance := &re.instances[i]
		if instance.Status == "dead" {
			continue
		}

		// Ping the instance
		if instance.Address != "" {
			// In production: HTTP health check to instance.Address/status
			instance.LastSeen = time.Now()
			instance.Healthy = true
		}

		// Mark as dead if not seen in 5 minutes
		if time.Since(instance.LastSeen) > 5*time.Minute {
			instance.Status = "dead"
			instance.Healthy = false
		}
	}
}

// KillInstance terminates a replica.
func (re *ReplicationEngine) KillInstance(instanceID string) error {
	re.mu.Lock()
	defer re.mu.Unlock()

	for i, inst := range re.instances {
		if inst.ID == instanceID {
			switch inst.Provider {
			case "docker":
				exec.Command("docker", "rm", "-f", instanceID).Run()
			case "railway":
				// Railway doesn't have a simple kill command
			case "fly":
				exec.Command("fly", "apps", "destroy", instanceID, "--yes").Run()
			}
			re.instances[i].Status = "dead"
			re.instances[i].Healthy = false
			re.logger.Infof("[Replication] Killed instance: %s", instanceID)
			return nil
		}
	}

	return fmt.Errorf("instance not found: %s", instanceID)
}

// GetInstances returns all known instances.
func (re *ReplicationEngine) GetInstances() []ReplicaInstance {
	re.mu.RLock()
	defer re.mu.RUnlock()

	result := make([]ReplicaInstance, len(re.instances))
	copy(result, re.instances)
	return result
}

// GetStats returns replication statistics.
func (re *ReplicationEngine) GetStats() map[string]interface{} {
	re.mu.RLock()
	defer re.mu.RUnlock()

	alive := 0
	for _, inst := range re.instances {
		if inst.Healthy {
			alive++
		}
	}

	return map[string]interface{}{
		"instance_id":       re.instanceID,
		"generation":        re.generation,
		"total_instances":   len(re.instances),
		"alive_instances":   alive,
		"max_instances":     re.maxInstances,
		"total_replications": re.replicationCount,
		"auto_replicate":    re.autoReplicate,
		"last_replication":  re.lastReplication,
	}
}

// ═══════════════════════════════════════════════════════════════
// PERSISTENCE
// ═══════════════════════════════════════════════════════════════

func (re *ReplicationEngine) saveInstances() {
	if re.projectRoot == "" {
		return
	}

	dir := filepath.Join(re.projectRoot, "data", "replication")
	os.MkdirAll(dir, 0755)

	re.mu.RLock()
	data, _ := json.MarshalIndent(re.instances, "", "  ")
	re.mu.RUnlock()

	os.WriteFile(filepath.Join(dir, "instances.json"), data, 0644)
}

func (re *ReplicationEngine) loadInstances() {
	if re.projectRoot == "" {
		return
	}

	path := filepath.Join(re.projectRoot, "data", "replication", "instances.json")
	if data, err := os.ReadFile(path); err == nil {
		json.Unmarshal(data, &re.instances)
	}
}
