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
	"sync"
	"time"
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

// TaskResult holds the output of a completed task.
type TaskResult struct {
	ExitCode   int               `json:"exit_code"`
	Stdout     string            `json:"stdout"`
	Stderr     string            `json:"stderr"`
	Duration   time.Duration     `json:"duration"`
	OutputFiles []string         `json:"output_files"`
	Metadata   map[string]string `json:"metadata"`
}

// TaskStatus tracks task lifecycle.
type TaskStatus int

const (
	TaskPending  TaskStatus = iota
	TaskRunning
	TaskCompleted
	TaskFailed
)

// ValidateComputeNode checks for empty or invalid fields.
func ValidateComputeNode(node *ComputeNode) error {
	if node.ID == "" || node.Name == "" || node.Address == "" {
		return fmt.Errorf("compute node ID, name, or address is empty")
	}
	if node.Port <= 0 {
		return fmt.Errorf("compute node port is invalid")
	}
	if node.AuthMethod == "" || node.Credential == "" {
		return fmt.Errorf("compute node auth method or credential is empty")
	}
	return nil
}

// ValidateComputeTask checks for empty or invalid fields.
func ValidateComputeTask(task *ComputeTask) error {
	if task.ID == "" || task.Name == "" || task.Command == "" {
		return fmt.Errorf("compute task ID, name, or command is empty")
	}
	if task.WorkDir == "" {
		return fmt.Errorf("compute task work directory is empty")
	}
	if task.MinCPU < 0 || task.MinCPU > 1 {
		return fmt.Errorf("compute task minimum CPU is invalid")
	}
	if task.MinMemGB < 0 {
		return fmt.Errorf("compute task minimum memory is invalid")
	}
	if task.MaxLatency < 0 {
		return fmt.Errorf("compute task maximum latency is invalid")
	}
	return nil
}

// ValidateTaskStatus checks for invalid task status.
func ValidateTaskStatus(status TaskStatus) error {
	switch status {
	case TaskPending, TaskRunning, TaskCompleted, TaskFailed:
		return nil
	default:
		return fmt.Errorf("invalid task status")
	}
}

// WithTimeout executes a function with a given timeout.
func WithTimeout(ctx context.Context, timeout time.Duration, fn func(context.Context) error) error {
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	return fn(ctx)
}

// WithRetry executes a function with a given number of retries.
func WithRetry(ctx context.Context, retries int, fn func(context.Context) error) error {
	for i := 0; i < retries; i++ {
		if err := fn(ctx); err != nil {
			continue
		}
		return nil
	}
	return fmt.Errorf("all retries failed")
}

// LoadBalancerConfig holds configuration for the load balancer.
type LoadBalancerConfig struct {
	MaxNodes       int
	ScheduleInterval time.Duration
	EnergyAware    bool
	GPUAware       bool
}

// DefaultLoadBalancerConfig returns sensible defaults.
func DefaultLoadBalancerConfig() *LoadBalancerConfig {
	return &LoadBalancerConfig{
		MaxNodes:         50,
		ScheduleInterval: 10 * time.Second,
		EnergyAware:      true,
		GPUAware:         true,
	}
}

// LoadBalancer manages work distribution across compute nodes.
type LoadBalancer struct {
	mu     sync.RWMutex
	cfg    *LoadBalancerConfig
	nodes  map[string]*ComputeNode
	tasks  map[string]*ComputeTask
}

// NewLoadBalancer creates a new load balancer.
func NewLoadBalancer(logger interface{}, cfg *LoadBalancerConfig) *LoadBalancer {
	return &LoadBalancer{
		cfg:   cfg,
		nodes: make(map[string]*ComputeNode),
		tasks: make(map[string]*ComputeTask),
	}
}

// Start begins the scheduling loop.
func (lb *LoadBalancer) Start(ctx interface{}) {
	// Stub: real implementation schedules tasks across nodes
}

// RegisterNode adds a compute node to the pool.
func (lb *LoadBalancer) RegisterNode(node ComputeNode) error {
	if err := ValidateComputeNode(&node); err != nil {
		return err
	}
	lb.mu.Lock()
	lb.nodes[node.ID] = &node
	lb.mu.Unlock()
	return nil
}

// SubmitTask enqueues a task for execution.
func (lb *LoadBalancer) SubmitTask(task *ComputeTask) error {
	if err := ValidateComputeTask(task); err != nil {
		return err
	}
	lb.mu.Lock()
	lb.tasks[task.ID] = task
	lb.mu.Unlock()
	return nil
}

// GetStatus returns load balancer status metrics.
func (lb *LoadBalancer) GetStatus() map[string]interface{} {
	lb.mu.RLock()
	defer lb.mu.RUnlock()
	return map[string]interface{}{
		"nodes": len(lb.nodes),
		"tasks": len(lb.tasks),
	}
}
