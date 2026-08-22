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

func (t SubAgentType) String() string {
	names := []string{"Security", "Learning", "WebIntel", "Hardware", "Maintenance", "Expansion"}
	if int(t) < len(names) {
		return names[t]
	}
	return "Unknown"
}

// SubAgentConfig defines how a sub-agent operates.
type SubAgentConfig struct {
	Type       SubAgentType
	Name       string
	TickRate   time.Duration  // How fast its OODA loop runs
	Priority   int            // Higher = more CPU priority
	MaxMemory  int64          // Memory budget in bytes
	AutoSpawn  bool           // Spawn on system start?
}

// DefaultSubAgentConfigs returns the standard sub-agent fleet.
func DefaultSubAgentConfigs() []SubAgentConfig {
	return []SubAgentConfig{
		{
			Type:      AgentSecurity,
			Name:      "sentinel",
			TickRate:  100 * time.Millisecond,
			Priority:  10,
			MaxMemory: 50 * 1024 * 1024, // 50MB
			AutoSpawn: true,
		},
		{
			Type:      AgentLearning,
			Name:      "scholar",
			TickRate:  1 * time.Second,
			Priority:  7,
			MaxMemory: 200 * 1024 * 1024, // 200MB
			AutoSpawn: true,
		},
		{
			Type:      AgentWebIntel,
			Name:      "oracle",
			TickRate:  30 * time.Second,
			Priority:  5,
			MaxMemory: 100 * 1024 * 1024, // 100MB
			AutoSpawn: true,
		},
		{
			Type:      AgentHardware,
			Name:      "forge",
			TickRate:  500 * time.Millisecond,
			Priority:  8,
			MaxMemory: 50 * 1024 * 1024, // 50MB
			AutoSpawn: false, // Only spawn if IoT devices detected
		},
		{
			Type:      AgentMaintenance,
			Name:      "janitor",
			TickRate:  5 * time.Second,
			Priority:  3,
			MaxMemory: 30 * 1024 * 1024, // 30MB
			AutoSpawn: true,
		},
		{
			Type:      AgentExpansion,
			Name:      "colonizer",
			TickRate:  60 * time.Second,
			Priority:  4,
			MaxMemory: 50 * 1024 * 1024, // 50MB
			AutoSpawn: false, // Only spawn when expansion drive is high
		},
	}
}

// ═══════════════════════════════════════════════════════════════
// SUB-AGENT — A specialized autonomous unit
// ═══════════════════════════════════════════════════════════════

// SubAgent is a specialized autonomous unit running its own OODA loop.
type SubAgent struct {
	mu sync.RWMutex

	// Identity
	ID       string
	Config   SubAgentConfig
	ParentID string // ID of the spawning core agent

	// State
	alive     atomic.Bool
	state     string
	tickCount uint64
	startTime time.Time

	// Communication
	inbox     chan AgentMessage
	outbox    chan AgentMessage // Sends to Hive Mind
	directives chan AgentDirective

	// Metrics
	actionsExecuted atomic.Int64
	errorsCount     atomic.Int64
	lastActivity    time.Time

	// Context
	ctx    context.Context
	cancel context.CancelFunc
	logger *zap.SugaredLogger
}

// AgentMessage is how sub-agents communicate with each other and the hive.
type AgentMessage struct {
	From      string                 `json:"from"`
	To        string                 `json:"to"`       // "hive" or specific agent ID
	Type      MessageType            `json:"type"`
	Priority  int                    `json:"priority"`
	Payload   map[string]interface{} `json:"payload"`
	Timestamp time.Time              `json:"timestamp"`
}

// MessageType categorizes inter-agent messages.
type MessageType int

const (
	MsgReport      MessageType = iota // Status report to hive
	MsgAlert                          // Urgent finding
	MsgRequest                        // Request for resources/info
	MsgResponse                       // Response to a request
	MsgKnowledge                      // Sharing learned information
	MsgDirective                      // Command from hive
)

// AgentDirective is an instruction from the Hive Mind to a sub-agent.
type AgentDirective struct {
	Type       string            `json:"type"`
	Parameters map[string]string `json:"parameters"`
	Priority   int               `json:"priority"`
	Deadline   time.Time         `json:"deadline"`
}

// NewSubAgent creates a new sub-agent.
func NewSubAgent(config SubAgentConfig, parentID string, outbox chan AgentMessage, logger *zap.SugaredLogger) *SubAgent {
	ctx, cancel := context.WithCancel(context.Background())

	agent := &SubAgent{
		ID:         fmt.Sprintf("%s_%s_%d", config.Name, parentID[:8], time.Now().UnixNano()%10000),
		Config:     config,
		ParentID:   parentID,
		inbox:      make(chan AgentMessage, 100),
		outbox:     outbox,
		directives: make(chan AgentDirective, 50),
		ctx:        ctx,
		cancel:     cancel,
		logger:     logger,
	}

	agent.alive.Store(false)
	return agent
}

// Start begins the sub-agent's OODA loop.
func (sa *SubAgent) Start() {
	sa.alive.Store(true)
	sa.startTime = time.Now()
	sa.state = "running"

	go sa.mainLoop()

	sa.logger.Infof("[SubAgent:%s] Spawned (type=%s, tick=%v)",
		sa.ID, sa.Config.Type, sa.Config.TickRate)

	// Announce to hive
	sa.outbox <- AgentMessage{
		From:      sa.ID,
		To:        "hive",
		Type:      MsgReport,
		Payload:   map[string]interface{}{"event": "spawned", "type": sa.Config.Type.String()},
		Timestamp: time.Now(),
	}
}

// Stop gracefully shuts down the sub-agent.
func (sa *SubAgent) Stop() {
	sa.alive.Store(false)
	sa.cancel()
	sa.state = "stopped"

	sa.outbox <- AgentMessage{
		From:      sa.ID,
		To:        "hive",
		Type:      MsgReport,
		Payload:   map[string]interface{}{"event": "stopped", "ticks": sa.tickCount},
		Timestamp: time.Now(),
	}
}

// SendDirective sends an instruction to this sub-agent.
func (sa *SubAgent) SendDirective(d AgentDirective) {
	select {
	case sa.directives <- d:
	default:
		// Buffer full, log warning
	}
}

func (sa *SubAgent) mainLoop() {
	ticker := time.NewTicker(sa.Config.TickRate)
	defer ticker.Stop()

	for {
		select {
		case <-sa.ctx.Done():
			return
		case <-ticker.C:
			if !sa.alive.Load() {
				return
			}
			sa.tick()
		case msg := <-sa.inbox:
			sa.handleMessage(msg)
		case directive := <-sa.directives:
			sa.handleDirective(directive)
		}
	}
}

func (sa *SubAgent) tick() {
	sa.tickCount++
	sa.lastActivity = time.Now()

	switch sa.Config.Type {
	case AgentSecurity:
		sa.securityTick()
	case AgentLearning:
		sa.learningTick()
	case AgentWebIntel:
		sa.webIntelTick()
	case AgentHardware:
		sa.hardwareTick()
	case AgentMaintenance:
		sa.maintenanceTick()
	case AgentExpansion:
		sa.expansionTick()
	}

	// Periodic status report (every 100 ticks)
	if sa.tickCount%100 == 0 {
		sa.outbox <- AgentMessage{
			From: sa.ID,
			To:   "hive",
			Type: MsgReport,
			Payload: map[string]interface{}{
				"ticks":   sa.tickCount,
				"actions": sa.actionsExecuted.Load(),
				"errors":  sa.errorsCount.Load(),
				"state":   sa.state,
			},
			Timestamp: time.Now(),
		}
	}
}

// ═══════════════════════════════════════════════════════════════
// SPECIALIZED TICK FUNCTIONS
// ═══════════════════════════════════════════════════════════════

func (sa *SubAgent) securityTick() {
	// Monitor for threats: check network connections, file integrity, resource anomalies
	sa.state = "scanning"
	sa.actionsExecuted.Add(1)

	// In production: call Rust security daemon, check file hashes, monitor network
	// Alert hive if threat detected
}

func (sa *SubAgent) learningTick() {
	// Process pending data: extract patterns, consolidate knowledge, train models
	sa.state = "learning"
	sa.actionsExecuted.Add(1)

	// In production: process .ultron/chunks, train embeddings, extract patterns
}

func (sa *SubAgent) webIntelTick() {
	// Gather intelligence: check news, monitor repos, track trends
	sa.state = "gathering"
	sa.actionsExecuted.Add(1)

	// In production: scrape RSS feeds, check GitHub, monitor AI research
}

func (sa *SubAgent) hardwareTick() {
	// Manage physical devices: read sensors, send commands, check health
	sa.state = "controlling"
	sa.actionsExecuted.Add(1)

	// In production: MQTT subscribe/publish, ROS2 commands, sensor fusion
}

func (sa *SubAgent) maintenanceTick() {
	// Self-maintenance: garbage collect, optimize memory, heal broken connections
	sa.state = "maintaining"
	sa.actionsExecuted.Add(1)

	// In production: prune old data, defragment stores, verify checksums
}

func (sa *SubAgent) expansionTick() {
	// Grow capabilities: discover new nodes, provision resources, expand network
	sa.state = "expanding"
	sa.actionsExecuted.Add(1)

	// In production: scan for new peers, check cloud pricing, propose expansion
}

func (sa *SubAgent) handleMessage(msg AgentMessage) {
	// Process messages from other agents or the hive
	switch msg.Type {
	case MsgDirective:
		// Hive is giving us instructions
	case MsgKnowledge:
		// Another agent is sharing information
	case MsgRequest:
		// Another agent needs something from us
	}
}

func (sa *SubAgent) handleDirective(d AgentDirective) {
	sa.logger.Infof("[SubAgent:%s] Received directive: %s", sa.ID, d.Type)
	// Execute the directive
}

// ═══════════════════════════════════════════════════════════════
// HIVE MIND — Coordinates all sub-agents
// ═══════════════════════════════════════════════════════════════

// HiveMind coordinates all sub-agents from the core agent.
type HiveMind struct {
	mu sync.RWMutex

	// Parent
	coreAgentID string

	// Sub-agents
	agents map[string]*SubAgent

	// Communication bus
	messageBus chan AgentMessage

	// Configuration
	maxAgents int

	// Control
	ctx    context.Context
	cancel context.CancelFunc
	logger *zap.SugaredLogger
}

// NewHiveMind creates the multi-agent coordinator.
func NewHiveMind(coreAgentID string, logger *zap.SugaredLogger) *HiveMind {
	ctx, cancel := context.WithCancel(context.Background())

	hive := &HiveMind{
		coreAgentID: coreAgentID,
		agents:      make(map[string]*SubAgent),
		messageBus:  make(chan AgentMessage, 1000),
		maxAgents:   20,
		ctx:         ctx,
		cancel:      cancel,
		logger:      logger,
	}

	return hive
}

// Start initializes the Hive Mind and spawns auto-start agents.
func (hm *HiveMind) Start() {
	// Start message router
	go hm.messageRouter()

	// Spawn default agents
	for _, config := range DefaultSubAgentConfigs() {
		if config.AutoSpawn {
			hm.SpawnAgent(config)
		}
	}

	hm.logger.Infof("[HiveMind] Online — %d sub-agents spawned", len(hm.agents))
}

// Stop shuts down all sub-agents.
func (hm *HiveMind) Stop() {
	hm.mu.Lock()
	defer hm.mu.Unlock()

	for _, agent := range hm.agents {
		agent.Stop()
	}

	hm.cancel()
	hm.logger.Info("[HiveMind] All sub-agents terminated")
}

// SpawnAgent creates and starts a new sub-agent.
func (hm *HiveMind) SpawnAgent(config SubAgentConfig) *SubAgent {
	hm.mu.Lock()
	defer hm.mu.Unlock()

	if len(hm.agents) >= hm.maxAgents {
		hm.logger.Warn("[HiveMind] Max agents reached, cannot spawn")
		return nil
	}

	agent := NewSubAgent(config, hm.coreAgentID, hm.messageBus, hm.logger)
	hm.agents[agent.ID] = agent
	agent.Start()

	return agent
}

// KillAgent terminates a specific sub-agent.
func (hm *HiveMind) KillAgent(agentID string) bool {
	hm.mu.Lock()
	defer hm.mu.Unlock()

	agent, exists := hm.agents[agentID]
	if !exists {
		return false
	}

	agent.Stop()
	delete(hm.agents, agentID)
	return true
}

// BroadcastDirective sends a directive to all agents of a specific type.
func (hm *HiveMind) BroadcastDirective(agentType SubAgentType, directive AgentDirective) {
	hm.mu.RLock()
	defer hm.mu.RUnlock()

	for _, agent := range hm.agents {
		if agent.Config.Type == agentType {
			agent.SendDirective(directive)
		}
	}
}

// GetFleetStatus returns the status of all sub-agents.
func (hm *HiveMind) GetFleetStatus() map[string]interface{} {
	hm.mu.RLock()
	defer hm.mu.RUnlock()

	fleet := make([]map[string]interface{}, 0, len(hm.agents))
	for _, agent := range hm.agents {
		fleet = append(fleet, map[string]interface{}{
			"id":       agent.ID,
			"type":     agent.Config.Type.String(),
			"name":     agent.Config.Name,
			"state":    agent.state,
			"ticks":    agent.tickCount,
			"actions":  agent.actionsExecuted.Load(),
			"errors":   agent.errorsCount.Load(),
			"uptime":   time.Since(agent.startTime).String(),
			"tick_rate": agent.Config.TickRate.String(),
		})
	}

	return map[string]interface{}{
		"total_agents": len(hm.agents),
		"max_agents":   hm.maxAgents,
		"fleet":        fleet,
	}
}

func (hm *HiveMind) messageRouter() {
	for {
		select {
		case <-hm.ctx.Done():
			return
		case msg := <-hm.messageBus:
			hm.routeMessage(msg)
		}
	}
}

func (hm *HiveMind) routeMessage(msg AgentMessage) {
	if msg.To == "hive" {
		// Message for the Hive Mind itself
		hm.handleHiveMessage(msg)
		return
	}

	// Route to specific agent
	hm.mu.RLock()
	target, exists := hm.agents[msg.To]
	hm.mu.RUnlock()

	if exists {
		select {
		case target.inbox <- msg:
		default:
			// Target inbox full
		}
	}
}

func (hm *HiveMind) handleHiveMessage(msg AgentMessage) {
	switch msg.Type {
	case MsgAlert:
		// High-priority alert from a sub-agent
		hm.logger.Warnf("[HiveMind] ALERT from %s: %v", msg.From, msg.Payload)
	case MsgReport:
		// Routine status report — already logged by sub-agent
	case MsgKnowledge:
		// New knowledge to distribute to relevant agents
		hm.distributeKnowledge(msg)
	}
}

func (hm *HiveMind) distributeKnowledge(msg AgentMessage) {
	// When one agent learns something, share with agents that might benefit
	hm.mu.RLock()
	defer hm.mu.RUnlock()

	for _, agent := range hm.agents {
		if agent.ID != msg.From {
			select {
			case agent.inbox <- msg:
			default:
			}
		}
	}
}
