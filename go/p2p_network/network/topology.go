// Package network handles network topology management, peer discovery,
// and self-healing for the Ultron distributed consciousness.
package network

import (
	"context"
	"fmt"
	"math"
	"sort"
	"sync"
	"time"

	"ultron/p2p_network/node"

	"go.uber.org/zap"
)

// TopologyType defines the network topology structure.
type TopologyType int

const (
	TopologyMesh TopologyType = iota
	TopologyRing
	TopologyHierarchical
	TopologyHybrid
)

// HealingEvent records a network self-healing event.
type HealingEvent struct {
	Timestamp     time.Time
	EventType     string
	AffectedNodes []string
	Action        string
	Success       bool
	Duration      time.Duration
}

// NetworkPartition represents a detected network split.
type NetworkPartition struct {
	ID        string
	Nodes     []string
	DetectedAt time.Time
	Healed    bool
	HealedAt  time.Time
}

// TopologyManager manages the network topology and self-healing.
type TopologyManager struct {
	mu sync.RWMutex

	node   *node.UltronNode
	logger *zap.SugaredLogger

	// Topology state
	topology     TopologyType
	adjacencyMap map[string][]string // nodeID -> connected peer IDs

	// Self-healing
	healingEvents  []HealingEvent
	partitions     []NetworkPartition
	healingEnabled bool

	// Network health
	networkHealth  float64 // 0-1
	healthHistory  []float64

	// Routing
	routingTable map[string]*RouteEntry

	// Configuration
	maxLatency       time.Duration
	minConnectivity  float64
	healingInterval  time.Duration
}

// RouteEntry represents a routing table entry.
type RouteEntry struct {
	Destination string
	NextHop     string
	Hops        int
	Latency     time.Duration
	LastUpdated time.Time
	Reliability float64
}

// NewTopologyManager creates a new topology manager.
func NewTopologyManager(ultronNode *node.UltronNode, logger *zap.SugaredLogger) *TopologyManager {
	return &TopologyManager{
		node:            ultronNode,
		logger:          logger,
		topology:        TopologyHybrid,
		adjacencyMap:    make(map[string][]string),
		healingEvents:   make([]HealingEvent, 0),
		partitions:      make([]NetworkPartition, 0),
		healingEnabled:  true,
		networkHealth:   1.0,
		healthHistory:   make([]float64, 0),
		routingTable:    make(map[string]*RouteEntry),
		maxLatency:      500 * time.Millisecond,
		minConnectivity: 0.6,
		healingInterval: 10 * time.Second,
	}
}

// Start begins topology management.
func (tm *TopologyManager) Start(ctx context.Context) error {
	tm.logger.Info("Starting topology manager...")

	// Start health monitor
	go tm.healthMonitorLoop(ctx)

	// Start self-healing loop
	go tm.selfHealingLoop(ctx)

	// Start topology optimizer
	go tm.topologyOptimizerLoop(ctx)

	// Start partition detector
	go tm.partitionDetectorLoop(ctx)

	tm.logger.Info("Topology manager started")
	return nil
}

// GetNetworkHealth returns the current network health score.
func (tm *TopologyManager) GetNetworkHealth() float64 {
	tm.mu.RLock()
	defer tm.mu.RUnlock()
	return tm.networkHealth
}

// GetTopologyInfo returns information about the current topology.
func (tm *TopologyManager) GetTopologyInfo() map[string]interface{} {
	tm.mu.RLock()
	defer tm.mu.RUnlock()

	return map[string]interface{}{
		"topology_type":     tm.topology,
		"total_nodes":       len(tm.adjacencyMap),
		"total_edges":       tm.countEdges(),
		"network_health":    tm.networkHealth,
		"partitions":        len(tm.partitions),
		"healing_events":    len(tm.healingEvents),
		"routing_entries":   len(tm.routingTable),
		"avg_connectivity":  tm.calculateAvgConnectivity(),
	}
}

// TriggerHealing manually triggers a healing event.
func (tm *TopologyManager) TriggerHealing(reason string) *HealingEvent {
	event := tm.performHealing(reason)
	return event
}

// OptimizeTopology restructures the network for optimal performance.
func (tm *TopologyManager) OptimizeTopology() {
	tm.mu.Lock()
	defer tm.mu.Unlock()

	peers := tm.node.GetPeers()
	if len(peers) < 3 {
		return
	}

	// Calculate optimal connections based on latency
	type PeerDistance struct {
		ID      string
		Latency time.Duration
	}

	for _, peer := range peers {
		distances := make([]PeerDistance, 0)
		for _, other := range peers {
			if peer.ID != other.ID {
				distances = append(distances, PeerDistance{
					ID:      other.ID,
					Latency: other.Latency,
				})
			}
		}

		// Sort by latency
		sort.Slice(distances, func(i, j int) bool {
			return distances[i].Latency < distances[j].Latency
		})

		// Connect to closest peers (logarithmic scaling)
		maxConnections := int(math.Log2(float64(len(peers)))) + 2
		connections := make([]string, 0, maxConnections)
		for i := 0; i < maxConnections && i < len(distances); i++ {
			connections = append(connections, distances[i].ID)
		}

		tm.adjacencyMap[peer.ID] = connections
	}

	tm.logger.Info("Topology optimized")
}

// ─────────────────────────── Private Methods ───────────────────────────

func (tm *TopologyManager) healthMonitorLoop(ctx context.Context) {
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			tm.updateNetworkHealth()
		}
	}
}

func (tm *TopologyManager) updateNetworkHealth() {
	tm.mu.Lock()
	defer tm.mu.Unlock()

	peers := tm.node.GetPeers()
	if len(peers) == 0 {
		tm.networkHealth = 0.0
		return
	}

	// Factor 1: Connectivity
	connectivity := tm.calculateAvgConnectivity()

	// Factor 2: Latency
	var totalLatency time.Duration
	for _, peer := range peers {
		totalLatency += peer.Latency
	}
	avgLatency := totalLatency / time.Duration(len(peers))
	latencyScore := math.Max(0, 1.0-float64(avgLatency)/float64(tm.maxLatency))

	// Factor 3: Peer reliability
	var totalReliability float64
	for _, peer := range peers {
		totalReliability += peer.Reliability
	}
	avgReliability := totalReliability / float64(len(peers))

	// Factor 4: Active partitions
	partitionPenalty := float64(len(tm.partitions)) * 0.1

	// Combined health score
	health := (connectivity*0.3 + latencyScore*0.3 + avgReliability*0.3) - partitionPenalty
	health = math.Max(0, math.Min(1.0, health))

	// Smooth update
	tm.networkHealth = tm.networkHealth*0.8 + health*0.2
	tm.healthHistory = append(tm.healthHistory, tm.networkHealth)

	// Trim history
	if len(tm.healthHistory) > 1000 {
		tm.healthHistory = tm.healthHistory[500:]
	}
}

func (tm *TopologyManager) selfHealingLoop(ctx context.Context) {
	ticker := time.NewTicker(tm.healingInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if tm.healingEnabled && tm.networkHealth < tm.minConnectivity {
				tm.performHealing("low_health")
			}
		}
	}
}

func (tm *TopologyManager) performHealing(reason string) *HealingEvent {
	start := time.Now()
	tm.logger.Infof("Performing network healing (reason: %s)", reason)

	event := &HealingEvent{
		Timestamp: time.Now(),
		EventType: reason,
		Action:    "reconnect_and_rebalance",
	}

	// 1. Identify disconnected or degraded nodes
	disconnected := tm.findDisconnectedNodes()
	event.AffectedNodes = disconnected

	// 2. Attempt reconnection
	reconnected := 0
	for _, nodeID := range disconnected {
		if tm.attemptReconnection(nodeID) {
			reconnected++
		}
	}

	// 3. Rebalance topology
	tm.OptimizeTopology()

	// 4. Reassign orphaned shards
	tm.reassignOrphanedShards()

	event.Success = reconnected > 0 || len(disconnected) == 0
	event.Duration = time.Since(start)

	tm.mu.Lock()
	tm.healingEvents = append(tm.healingEvents, *event)
	tm.mu.Unlock()

	tm.logger.Infof("Healing complete: reconnected %d/%d nodes in %v",
		reconnected, len(disconnected), event.Duration)

	return event
}

func (tm *TopologyManager) topologyOptimizerLoop(ctx context.Context) {
	ticker := time.NewTicker(60 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			tm.OptimizeTopology()
		}
	}
}

func (tm *TopologyManager) partitionDetectorLoop(ctx context.Context) {
	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			tm.detectPartitions()
		}
	}
}

func (tm *TopologyManager) detectPartitions() {
	tm.mu.Lock()
	defer tm.mu.Unlock()

	if len(tm.adjacencyMap) < 3 {
		return
	}

	// BFS to find connected components
	visited := make(map[string]bool)
	components := make([][]string, 0)

	for nodeID := range tm.adjacencyMap {
		if visited[nodeID] {
			continue
		}

		// BFS from this node
		component := make([]string, 0)
		queue := []string{nodeID}

		for len(queue) > 0 {
			current := queue[0]
			queue = queue[1:]

			if visited[current] {
				continue
			}
			visited[current] = true
			component = append(component, current)

			for _, neighbor := range tm.adjacencyMap[current] {
				if !visited[neighbor] {
					queue = append(queue, neighbor)
				}
			}
		}

		components = append(components, component)
	}

	// Multiple components = partition detected
	if len(components) > 1 {
		for i, comp := range components {
			if i == 0 {
				continue // Main partition
			}

			partition := NetworkPartition{
				ID:         fmt.Sprintf("partition-%d-%d", time.Now().Unix(), i),
				Nodes:      comp,
				DetectedAt: time.Now(),
				Healed:     false,
			}
			tm.partitions = append(tm.partitions, partition)
			tm.logger.Warnf("Network partition detected: %d nodes isolated", len(comp))
		}
	}
}

func (tm *TopologyManager) findDisconnectedNodes() []string {
	peers := tm.node.GetPeers()
	disconnected := make([]string, 0)

	for _, peer := range peers {
		if peer.State == node.StateDegraded {
			disconnected = append(disconnected, peer.ID)
		}
	}

	return disconnected
}

func (tm *TopologyManager) attemptReconnection(nodeID string) bool {
	// In real implementation, this would attempt P2P reconnection
	tm.logger.Infof("Attempting reconnection to node %s", nodeID)
	return true // Simulated success
}

func (tm *TopologyManager) reassignOrphanedShards() {
	// Find shards owned by disconnected nodes and reassign
	tm.logger.Debug("Checking for orphaned shards...")
}

func (tm *TopologyManager) countEdges() int {
	total := 0
	for _, neighbors := range tm.adjacencyMap {
		total += len(neighbors)
	}
	return total / 2 // Undirected graph
}

func (tm *TopologyManager) calculateAvgConnectivity() float64 {
	if len(tm.adjacencyMap) == 0 {
		return 0
	}

	totalConnections := 0
	for _, neighbors := range tm.adjacencyMap {
		totalConnections += len(neighbors)
	}

	maxPossible := len(tm.adjacencyMap) * (len(tm.adjacencyMap) - 1)
	if maxPossible == 0 {
		return 0
	}

	return float64(totalConnections) / float64(maxPossible)
}
