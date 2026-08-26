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