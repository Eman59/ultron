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