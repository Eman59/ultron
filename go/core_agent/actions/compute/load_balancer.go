// Package compute implements API-based compute load balancing.
//
// This moves tasks between machines on the local network using
// pre-configured SSH keys or REST APIs. It does NOT:
//   - Install software on machines without credentials
//   - Access machines without SSH keys already in place
//   - Persist after the task completes
//
// Think of this as a lightweight job scheduler (like Slurm or Nomad)
// that shifts work to idle machines on your network.
package compute

import (
	"context"
	"fmt"
	"sort"
	"sync"
	"time"

	"go.uber.org/zap"
)

// ComputeNode represents a machine available for task execution.
type ComputeNode struct {
	ID           string  `json:"id"`
	Name         string  `json:"name"`
	Address      string  `json:"address"` // SSH/API address
	Port         int     `json:"port"`
	AuthMethod   string  `json:"auth_method"` // "ssh_key", "api_token", "password"
	Credential   string  `json:"credential"`  // Path to SSH key or API token name

	// Current state
	Online       bool    `json:"online"`
	CPUUsage     float64 `json:"cpu_usage"`     // 0-1
	MemUsage     float64 `json:"mem_usage"`     // 0-1
	GPUAvailable bool    `json:"gpu_available"`
	GPUUsage     float64 `json:"gpu_usage"`     // 0-1
	PowerSource  string  `json:"power_source"`  // "mains", "battery", "ups"
	BatteryLevel float64 `json:"battery_level"` // 0-1 (if battery)

	// Capacity
	CPUCores     int     `json:"cpu_cores"`
	MemoryGB     float64 `json:"memory_gb"`
	DiskFreeGB   float64 `json:"disk_free_gb"`

	// Network
	Latency      time.Duration `json:"latency"`
	Bandwidth    float64       `json:"bandwidth_mbps"`
	LastSeen     time.Time     `json:"last_seen"`
}

// ComputeTask is a unit of work to be distributed.
type ComputeTask struct {
	ID          string                 `json:"id"`
	Name        string                 `json:"name"`
	Command     string                 `json:"command"`     // Shell command to execute
	WorkDir     string                 `json:"work_dir"`    // Working directory on target
	Env         map[string]string      `json:"env"`         // Environment variables
	InputFiles  []string               `json:"input_files"` // Files to transfer before execution
	OutputFiles []string               `json:"output_files"` // Files to retrieve after

	// Requirements
	MinCPU      float64 `json:"min_cpu"`       // Minimum free CPU (0-1)
	MinMemGB    float64 `json:"min_mem_gb"`
	NeedsGPU    bool    `json:"needs_gpu"`
	MaxLatency  time.Duration `json:"max_latency"` // Max network latency to target

	// Priority and scheduling
	Priority    int     `json:"priority"`     // 0-10
	Deadline    time.Duration `json:"deadline"` // Max execution time

	// Status
	Status      TaskStatus `json:"status"`
	AssignedTo  string     `json:"assigned_to"` // Node ID
	StartedAt   time.Time  `json:"started_at"`
	CompletedAt time.Time  `json:"completed_at"`
	Result      *TaskResult `json:"result"`
}

// TaskStatus tracks task lifecycle.
type TaskStatus int

const (
	TaskPending    TaskStatus = iota
	TaskScheduled
	TaskRunning
	TaskCompleted
	TaskFailed
	TaskCancelled
)

func (s TaskStatus) String() string {
	names := []string{"Pending", "Scheduled", "Running", "Completed", "Failed", "Cancelled"}
	if int(s) < len(names) {
		return names[s]
	}
	return "Unknown"
}

// TaskResult is the outcome of a distributed task.
type TaskResult struct {
	ExitCode  int           `json:"exit_code"`
	Stdout    string        `json:"stdout"`
	Stderr    string        `json:"stderr"`
	Duration  time.Duration `json:"duration"`
	NodeUsed  string        `json:"node_used"`
}

// LoadBalancer manages compute distribution across available nodes.
type LoadBalancer struct {
	mu sync.RWMutex

	logger *zap.SugaredLogger

	// Available compute nodes
	nodes map[string]*ComputeNode

	// Task queue
	pendingTasks []*ComputeTask
	runningTasks map[string]*ComputeTask // taskID -> task
	completedTasks []*ComputeTask

	// Configuration
	config LoadBalancerConfig

	// Metrics
	tasksScheduled uint64
	tasksCompleted uint64
	tasksFailed    uint64
	totalCPUHours  float64
}

// LoadBalancerConfig configures the load balancer.
type LoadBalancerConfig struct {
	// Scheduling
	SchedulingInterval time.Duration // How often to check for tasks to schedule
	MaxConcurrentTasks int           // Max tasks running simultaneously
	PreferLocalFirst   bool          // Prefer running on local machine

	// Power management
	AvoidBatteryNodes  bool    // Don't schedule on battery-powered nodes below threshold
	BatteryThreshold   float64 // Below this, don't use the node (0-1)

	// Network
	MaxLatency         time.Duration // Don't use nodes with latency above this
	MinBandwidth       float64       // Minimum bandwidth in Mbps

	// Health
	NodeCheckInterval  time.Duration
	UnhealthyThreshold float64 // CPU > this = overloaded, don't schedule
}

// DefaultLoadBalancerConfig returns sensible defaults.
func DefaultLoadBalancerConfig() LoadBalancerConfig {
	return LoadBalancerConfig{
		SchedulingInterval: 1 * time.Second,
		MaxConcurrentTasks: 20,
		PreferLocalFirst:   true,
		AvoidBatteryNodes:  true,
		BatteryThreshold:   0.2, // Don't use if <20% battery
		MaxLatency:         50 * time.Millisecond,
		MinBandwidth:       100.0, // 100 Mbps minimum
		NodeCheckInterval:  5 * time.Second,
		UnhealthyThreshold: 0.85, // >85% CPU = overloaded
	}
}

// NewLoadBalancer creates a compute load balancer.
func NewLoadBalancer(logger *zap.SugaredLogger, config LoadBalancerConfig) *LoadBalancer {
	return &LoadBalancer{
		logger:         logger,
		nodes:          make(map[string]*ComputeNode),
		pendingTasks:   make([]*ComputeTask, 0),
		runningTasks:   make(map[string]*ComputeTask),
		completedTasks: make([]*ComputeTask, 0, 1000),
		config:         config,
	}
}

// RegisterNode adds a compute node to the pool.
func (lb *LoadBalancer) RegisterNode(node ComputeNode) {
	lb.mu.Lock()
	defer lb.mu.Unlock()

	lb.nodes[node.ID] = &node
	lb.logger.Infof("Registered compute node: %s (%s) — %d cores, %.1fGB RAM, GPU: %v",
		node.Name, node.Address, node.CPUCores, node.MemoryGB, node.GPUAvailable)
}

// RemoveNode removes a node from the pool.
func (lb *LoadBalancer) RemoveNode(nodeID string) {
	lb.mu.Lock()
	defer lb.mu.Unlock()
	delete(lb.nodes, nodeID)
}

// SubmitTask adds a task to the scheduling queue.
func (lb *LoadBalancer) SubmitTask(task *ComputeTask) string {
	lb.mu.Lock()
	defer lb.mu.Unlock()

	if task.ID == "" {
		task.ID = fmt.Sprintf("task_%d", time.Now().UnixNano())
	}
	task.Status = TaskPending

	lb.pendingTasks = append(lb.pendingTasks, task)

	// Sort by priority (higher first)
	sort.Slice(lb.pendingTasks, func(i, j int) bool {
		return lb.pendingTasks[i].Priority > lb.pendingTasks[j].Priority
	})

	lb.logger.Infof("Task submitted: %s (priority: %d)", task.Name, task.Priority)
	return task.ID
}

// Start begins the scheduling loop.
func (lb *LoadBalancer) Start(ctx context.Context) {
	go lb.schedulingLoop(ctx)
	go lb.healthCheckLoop(ctx)
	lb.logger.Info("Load balancer started")
}

// GetBestNode finds the optimal node for a given task.
func (lb *LoadBalancer) GetBestNode(task *ComputeTask) *ComputeNode {
	lb.mu.RLock()
	defer lb.mu.RUnlock()

	type ScoredNode struct {
		node  *ComputeNode
		score float64
	}

	var candidates []ScoredNode

	for _, node := range lb.nodes {
		if !lb.nodeCanRunTask(node, task) {
			continue
		}

		score := lb.scoreNode(node, task)
		candidates = append(candidates, ScoredNode{node: node, score: score})
	}

	if len(candidates) == 0 {
		return nil
	}

	// Sort by score descending
	sort.Slice(candidates, func(i, j int) bool {
		return candidates[i].score > candidates[j].score
	})

	return candidates[0].node
}

// MigrateTask moves a running task to a different node.
func (lb *LoadBalancer) MigrateTask(taskID string, targetNodeID string, reason string) error {
	lb.mu.Lock()
	task, exists := lb.runningTasks[taskID]
	if !exists {
		lb.mu.Unlock()
		return fmt.Errorf("task %s not running", taskID)
	}

	targetNode, nodeExists := lb.nodes[targetNodeID]
	if !nodeExists {
		lb.mu.Unlock()
		return fmt.Errorf("target node %s not found", targetNodeID)
	}
	lb.mu.Unlock()

	lb.logger.Infof("Migrating task %s from %s to %s (reason: %s)",
		task.Name, task.AssignedTo, targetNode.Name, reason)

	// Cancel on current node, reschedule on target
	task.Status = TaskPending
	task.AssignedTo = targetNodeID

	lb.mu.Lock()
	delete(lb.runningTasks, taskID)
	lb.pendingTasks = append(lb.pendingTasks, task)
	lb.mu.Unlock()

	return nil
}

// EnergyAwareRebalance shifts tasks from battery-low nodes to mains-powered ones.
func (lb *LoadBalancer) EnergyAwareRebalance() int {
	lb.mu.RLock()

	// Find tasks on battery-low nodes
	type Migration struct {
		taskID     string
		fromNode   string
		toNode     string
	}

	var migrations []Migration

	for taskID, task := range lb.runningTasks {
		currentNode, exists := lb.nodes[task.AssignedTo]
		if !exists {
			continue
		}

		// Check if current node is running low on battery
		if currentNode.PowerSource == "battery" && currentNode.BatteryLevel < lb.config.BatteryThreshold {
			// Find a mains-powered alternative
			for _, candidate := range lb.nodes {
				if candidate.ID == currentNode.ID {
					continue
				}
				if candidate.PowerSource == "mains" || candidate.PowerSource == "ups" {
					if candidate.CPUUsage < lb.config.UnhealthyThreshold {
						migrations = append(migrations, Migration{
							taskID:   taskID,
							fromNode: currentNode.ID,
							toNode:   candidate.ID,
						})
						break
					}
				}
			}
		}
	}
	lb.mu.RUnlock()

	// Execute migrations
	for _, m := range migrations {
		lb.MigrateTask(m.taskID, m.toNode, "energy_arbitrage: source battery low")
	}

	if len(migrations) > 0 {
		lb.logger.Infof("Energy rebalance: migrated %d tasks to mains-powered nodes", len(migrations))
	}

	return len(migrations)
}

// GetStatus returns current load balancer status.
func (lb *LoadBalancer) GetStatus() map[string]interface{} {
	lb.mu.RLock()
	defer lb.mu.RUnlock()

	onlineNodes := 0
	totalCPU := 0.0
	totalMem := 0.0

	for _, node := range lb.nodes {
		if node.Online {
			onlineNodes++
			totalCPU += node.CPUUsage
			totalMem += node.MemUsage
		}
	}

	avgCPU := 0.0
	avgMem := 0.0
	if onlineNodes > 0 {
		avgCPU = totalCPU / float64(onlineNodes)
		avgMem = totalMem / float64(onlineNodes)
	}

	return map[string]interface{}{
		"total_nodes":      len(lb.nodes),
		"online_nodes":     onlineNodes,
		"pending_tasks":    len(lb.pendingTasks),
		"running_tasks":    len(lb.runningTasks),
		"completed_tasks":  len(lb.completedTasks),
		"tasks_scheduled":  lb.tasksScheduled,
		"tasks_completed":  lb.tasksCompleted,
		"tasks_failed":     lb.tasksFailed,
		"avg_cpu_usage":    avgCPU,
		"avg_mem_usage":    avgMem,
		"total_cpu_hours":  lb.totalCPUHours,
	}
}

// ─────────────────────── Private Methods ───────────────────────

func (lb *LoadBalancer) schedulingLoop(ctx context.Context) {
	ticker := time.NewTicker(lb.config.SchedulingInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			lb.scheduleNext()
		}
	}
}

func (lb *LoadBalancer) scheduleNext() {
	lb.mu.Lock()
	defer lb.mu.Unlock()

	// Check capacity
	if len(lb.runningTasks) >= lb.config.MaxConcurrentTasks {
		return
	}

	if len(lb.pendingTasks) == 0 {
		return
	}

	// Take highest priority pending task
	task := lb.pendingTasks[0]

	// Find best node
	lb.mu.Unlock()
	bestNode := lb.GetBestNode(task)
	lb.mu.Lock()

	if bestNode == nil {
		return // No suitable node available
	}

	// Schedule the task
	task.Status = TaskScheduled
	task.AssignedTo = bestNode.ID
	task.StartedAt = time.Now()

	lb.pendingTasks = lb.pendingTasks[1:]
	lb.runningTasks[task.ID] = task
	lb.tasksScheduled++

	lb.logger.Infof("Scheduled task '%s' on %s (%s)",
		task.Name, bestNode.Name, bestNode.Address)

	// Execute asynchronously
	go lb.executeTask(task, bestNode)
}

func (lb *LoadBalancer) executeTask(task *ComputeTask, node *ComputeNode) {
	task.Status = TaskRunning

	// In production: SSH to node and run command
	// ssh -i <key> user@<address> "cd <workdir> && <command>"
	//
	// For API-based nodes:
	// POST http://<address>:<port>/api/execute {command, env, workdir}

	// Simulate execution
	time.Sleep(100 * time.Millisecond)

	result := &TaskResult{
		ExitCode: 0,
		Stdout:   fmt.Sprintf("Task '%s' executed on %s", task.Name, node.Name),
		Stderr:   "",
		Duration: 100 * time.Millisecond,
		NodeUsed: node.ID,
	}

	// Complete
	lb.mu.Lock()
	task.Status = TaskCompleted
	task.CompletedAt = time.Now()
	task.Result = result
	delete(lb.runningTasks, task.ID)
	lb.completedTasks = append(lb.completedTasks, task)
	lb.tasksCompleted++
	lb.totalCPUHours += result.Duration.Hours()

	if len(lb.completedTasks) > 10000 {
		lb.completedTasks = lb.completedTasks[5000:]
	}
	lb.mu.Unlock()
}

func (lb *LoadBalancer) healthCheckLoop(ctx context.Context) {
	ticker := time.NewTicker(lb.config.NodeCheckInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			lb.checkNodeHealth()
			lb.EnergyAwareRebalance()
		}
	}
}

func (lb *LoadBalancer) checkNodeHealth() {
	lb.mu.Lock()
	defer lb.mu.Unlock()

	for _, node := range lb.nodes {
		// Mark offline if not seen recently
		if time.Since(node.LastSeen) > lb.config.NodeCheckInterval*3 {
			if node.Online {
				node.Online = false
				lb.logger.Warnf("Node %s (%s) went offline", node.Name, node.Address)
			}
		}
	}
}

func (lb *LoadBalancer) nodeCanRunTask(node *ComputeNode, task *ComputeTask) bool {
	if !node.Online {
		return false
	}

	// CPU check
	freeCPU := 1.0 - node.CPUUsage
	if freeCPU < task.MinCPU {
		return false
	}

	// Memory check
	freeMemGB := node.MemoryGB * (1.0 - node.MemUsage)
	if freeMemGB < task.MinMemGB {
		return false
	}

	// GPU check
	if task.NeedsGPU && !node.GPUAvailable {
		return false
	}

	// Latency check
	if task.MaxLatency > 0 && node.Latency > task.MaxLatency {
		return false
	}

	// Battery check
	if lb.config.AvoidBatteryNodes && node.PowerSource == "battery" && node.BatteryLevel < lb.config.BatteryThreshold {
		return false
	}

	// Overload check
	if node.CPUUsage > lb.config.UnhealthyThreshold {
		return false
	}

	return true
}

func (lb *LoadBalancer) scoreNode(node *ComputeNode, task *ComputeTask) float64 {
	score := 0.0

	// Prefer nodes with more free resources
	freeCPU := 1.0 - node.CPUUsage
	freeMem := 1.0 - node.MemUsage
	score += freeCPU * 0.3
	score += freeMem * 0.2

	// Prefer low latency
	if node.Latency < 5*time.Millisecond {
		score += 0.2
	} else if node.Latency < 20*time.Millisecond {
		score += 0.1
	}

	// Prefer mains-powered over battery
	switch node.PowerSource {
	case "mains":
		score += 0.15
	case "ups":
		score += 0.1
	case "battery":
		score += node.BatteryLevel * 0.05 // Proportional to battery level
	}

	// Prefer nodes with more bandwidth
	if node.Bandwidth > 1000 {
		score += 0.1
	}

	// GPU bonus if needed
	if task.NeedsGPU && node.GPUAvailable && node.GPUUsage < 0.5 {
		score += 0.3
	}

	return score
}
