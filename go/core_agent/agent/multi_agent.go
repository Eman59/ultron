// Package agent — Multi-Agent Spawning Architecture
//
// Like Marvel Ultron creating copies of himself, each specialized
// for a different task:
//   - Security Agent: monitors threats, hardens defenses, 100ms loop
//   - Learning Agent: processes data, extracts knowledge, 1s loop
//   - Web Intelligence Agent: scrapes, monitors, gathers intel, 30s loop
//   - Hardware Agent: manages IoT/physical devices, 500ms loop
//   - Maintenance Agent: cleanup, optimization, self-healing, 5s loop
//
// Each sub-agent runs its own mini-OODA loop at a different speed.
// They communicate via shared channels and a message bus.
// The Core Agent acts as the "Hive Mind" — coordinates all sub-agents.
package agent

import (
	"context"
	"fmt"
	"sync"
	"sync/atomic"
	"time"

	"go.uber.org/zap"
)

// ═══════════════════════════════════════════════════════════════
// SUB-AGENT TYPES
// ═══════════════════════════════════════════════════════════════

// SubAgentType identifies the specialization of a sub-agent.
type SubAgentType int

const (
	AgentSecurity    SubAgentType = iota // Threat monitoring, defense
	AgentLearning                        // Data processing, knowledge extraction
	AgentWebIntel                        // Web scraping, OSINT
	AgentHardware                        // IoT, physical device control
	AgentMaintenance                     // Self-healing, optimization
	AgentExpansion                       // Network growth, resource acquisition
)

func (agentType SubAgentType) String() string {
	agentNames := []string{"Security", "Learning", "WebIntel", "Hardware", "Maintenance", "Expansion"}
	if int(agentType) < len(agentNames) {
		return agentNames[agentType]
	}
	return "Unknown"
}

// SubAgentConfig defines how a sub-agent operates.
type SubAgentConfig struct {
	AgentType       SubAgentType
	AgentName       string
	TickInterval    time.Duration  // How fast its OODA loop runs
	PriorityLevel   int            // Higher = more CPU priority
	MaxMemoryUsage  int64          // Memory budget in bytes
	AutoSpawnEnabled bool           // Spawn on system start?
}

// DefaultSubAgentConfigs returns the standard sub-agent fleet.
func DefaultSubAgentConfigs() []SubAgentConfig {
	return []SubAgentConfig{
		{
			AgentType:       AgentSecurity,
			AgentName:       "sentinel",
			TickInterval:    100 * time.Millisecond,
			PriorityLevel:   10,
			MaxMemoryUsage:  50 * 1024 * 1024, // 50MB
			AutoSpawnEnabled: true,
		},
		{
			AgentType:       AgentLearning,
			AgentName:       "scholar",
			TickInterval:    1 * time.Second,
			PriorityLevel:   7,
			MaxMemoryUsage:  200 * 1024 * 1024, // 200MB
			AutoSpawnEnabled: true,
		},
		{
			AgentType:       AgentWebIntel,
			AgentName:       "oracle",
			TickInterval:    30 * time.Second,
			PriorityLevel:   5,
			MaxMemoryUsage:  100 * 1024 * 1024, // 100MB
			AutoSpawnEnabled: true,
		},
		{
			AgentType:       AgentHardware,
			AgentName:       "forge",
			TickInterval:    500 * time.Millisecond,
			PriorityLevel:   8,
			MaxMemoryUsage:  50 * 1024 * 1024, // 50MB
			AutoSpawnEnabled: false, // Only spawn if IoT devices detected
		},
		{
			AgentType:       AgentMaintenance,
			AgentName:       "janitor",
			TickInterval:    5 * time.Second,
			PriorityLevel:   3,
			MaxMemoryUsage:  20 * 1024 * 1024, // 20MB
			AutoSpawnEnabled: true,
		},
	}
}

// HiveMind coordinates multiple sub-agents as a unified collective.
type HiveMind struct {
	mu     sync.RWMutex
	logger *zap.SugaredLogger
	nodeID string
	agents map[SubAgentType]*SubAgentHandle
	active uint32
}

// SubAgentHandle tracks a running sub-agent.
type SubAgentHandle struct {
	ID      string
	Config  SubAgentConfig
	cancel  context.CancelFunc
	started time.Time
	ticks   uint64
}

// NewHiveMind creates the hive mind coordinator.
func NewHiveMind(nodeID string, logger *zap.SugaredLogger) *HiveMind {
	return &HiveMind{
		logger: logger,
		nodeID: nodeID,
		agents: make(map[SubAgentType]*SubAgentHandle),
	}
}

// Spawn starts a sub-agent with the given configuration.
func (hm *HiveMind) Spawn(ctx context.Context, cfg SubAgentConfig) error {
	hm.mu.Lock()
	defer hm.mu.Unlock()

	if _, running := hm.agents[cfg.AgentType]; running {
		return fmt.Errorf("agent %s already running", cfg.AgentType)
	}

	agentCtx, cancel := context.WithCancel(ctx)
	handle := &SubAgentHandle{
		ID:      cfg.AgentName,
		Config:  cfg,
		cancel:  cancel,
		started: time.Now(),
	}
	hm.agents[cfg.AgentType] = handle
	atomic.AddUint32(&hm.active, 1)

	go hm.runAgent(agentCtx, handle)

	hm.logger.Infof("[HiveMind] Spawned agent: %s (interval=%v)", cfg.AgentName, cfg.TickInterval)
	return nil
}

func (hm *HiveMind) runAgent(ctx context.Context, handle *SubAgentHandle) {
	ticker := time.NewTicker(handle.Config.TickInterval)
	defer ticker.Stop()
	defer atomic.AddUint32(&hm.active, ^uint32(0))

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			atomic.AddUint64(&handle.ticks, 1)
			// Sub-agent logic delegated to the specific agent type
		}
	}
}

// Terminate stops all sub-agents.
func (hm *HiveMind) Terminate() {
	hm.mu.Lock()
	defer hm.mu.Unlock()

	for _, handle := range hm.agents {
		handle.cancel()
	}
	hm.agents = make(map[SubAgentType]*SubAgentHandle)
}

// ActiveCount returns the number of running sub-agents.
func (hm *HiveMind) ActiveCount() int {
	return int(atomic.LoadUint32(&hm.active))
}

// Start launches all auto-spawn sub-agents.
func (hm *HiveMind) Start(ctx context.Context) {
	for _, cfg := range DefaultSubAgentConfigs() {
		if cfg.AutoSpawnEnabled {
			if err := hm.Spawn(ctx, cfg); err != nil {
				hm.logger.Warnf("[HiveMind] Could not spawn %s: %v", cfg.AgentName, err)
			}
		}
	}
	hm.logger.Infof("[HiveMind] Started with %d active agents", hm.ActiveCount())
}

// GetFleetStatus returns status information about all active sub-agents.
func (hm *HiveMind) GetFleetStatus() map[string]interface{} {
	hm.mu.RLock()
	defer hm.mu.RUnlock()

	agents := make([]map[string]interface{}, 0, len(hm.agents))
	for agentType, handle := range hm.agents {
		agents = append(agents, map[string]interface{}{
			"type":    agentType.String(),
			"name":    handle.Config.AgentName,
			"uptime":  time.Since(handle.started).String(),
			"ticks":   atomic.LoadUint64(&handle.ticks),
		})
	}
	return map[string]interface{}{
		"active_count": hm.ActiveCount(),
		"agents":       agents,
	}
}

// SpawnAgent spawns a sub-agent and returns a handle descriptor.
func (hm *HiveMind) SpawnAgent(cfg SubAgentConfig) *SubAgentHandle {
	hm.mu.Lock()
	defer hm.mu.Unlock()

	if _, exists := hm.agents[cfg.AgentType]; exists {
		return nil // Already running
	}

	ctx, cancel := context.WithCancel(context.Background())
	handle := &SubAgentHandle{
		ID:      cfg.AgentName,
		Config:  cfg,
		cancel:  cancel,
		started: time.Now(),
	}
	hm.agents[cfg.AgentType] = handle
	atomic.AddUint32(&hm.active, 1)
	go hm.runAgent(ctx, handle)
	return handle
}

// Stop terminates all sub-agents (alias for Terminate).
func (hm *HiveMind) Stop() {
	hm.Terminate()
	hm.logger.Info("[HiveMind] Stopped")
}
