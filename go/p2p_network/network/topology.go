// Package network handles network topology management, peer discovery,
// and self-healing for the Ultron distributed consciousness.
package network

import (
	"context"
	"sync"
	"time"

	"ultron/p2p_network/node"

	"go.uber.org/zap"
)

// NetworkTopologyType defines the network topology structure.
type NetworkTopologyType int

const (
	NetworkTopologyMesh NetworkTopologyType = iota
	NetworkTopologyRing
	NetworkTopologyHierarchical
	NetworkTopologyHybrid
)

// NetworkHealingEvent records a network self-healing event.
type NetworkHealingEvent struct {
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

	currentNode   *node.UltronNode
	logger        *zap.SugaredLogger

	// Topology state
	currentTopology     NetworkTopologyType
	nodeAdjacencyMap map[string][]string // nodeID -> connected peer IDs

	// Self-healing
	healingEventHistory  []NetworkHealingEvent
	detectedPartitions     []NetworkPartition
	selfHealingEnabled bool

	// Network health
	networkHealthScore  float64 // 0-1
	networkHealthHistory  []float64

	// Routing
	routingTable map[string]*RouteEntry

	// Configuration
	maxAllowedLatency       time.Duration
	minRequiredConnectivity  float64
	selfHealingInterval  time.Duration
}

// RouteEntry represents a routing table entry.
type RouteEntry struct {
	DestinationNode string
	NextHopNode     string
	Hops        int
	Latency     time.Duration
	LastUpdated time.Time
	Reliability float64
}

// NewTopologyManager creates a new topology manager.
func NewTopologyManager(ultronNode *node.UltronNode, logger *zap.SugaredLogger) *TopologyManager {
	return &TopologyManager{
		currentNode:            ultronNode,
		logger:          logger,
		currentTopology:        NetworkTopologyHybrid,
		nodeAdjacencyMap:    make(map[string][]string),
		healingEventHistory:   make([]NetworkHealingEvent, 0),
		detectedPartitions:      make([]NetworkPartition, 0),
		selfHealingEnabled:  true,
		networkHealthScore:   1.0,
		networkHealthHistory:   make([]float64, 0),
		routingTable:    make(map[string]*RouteEntry),
		maxAllowedLatency:      500 * time.Millisecond,
		minRequiredConnectivity: 0.6,
		selfHealingInterval: 10 * time.Second,
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
	return tm.networkHealthScore
}

// GetTopologyInfo returns information about the current topology
func (tm *TopologyManager) healthMonitorLoop(ctx context.Context) {
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			tm.mu.Lock()
			connected := 0
			total := len(tm.nodeAdjacencyMap)
			for _, peers := range tm.nodeAdjacencyMap {
				if len(peers) > 0 {
					connected++
				}
			}
			if total > 0 {
				tm.networkHealthScore = float64(connected) / float64(total)
			}
			tm.networkHealthHistory = append(tm.networkHealthHistory, tm.networkHealthScore)
			tm.mu.Unlock()
		}
	}
}

func (tm *TopologyManager) selfHealingLoop(ctx context.Context) {
	ticker := time.NewTicker(tm.selfHealingInterval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if tm.selfHealingEnabled {
				tm.mu.Lock()
				if tm.networkHealthScore < tm.minRequiredConnectivity {
					tm.healingEventHistory = append(tm.healingEventHistory, NetworkHealingEvent{
						Timestamp: time.Now(),
						EventType: "low_connectivity",
						Action:    "reconnect",
						Success:   true,
					})
				}
				tm.mu.Unlock()
			}
		}
	}
}

func (tm *TopologyManager) topologyOptimizerLoop(ctx context.Context) {
	ticker := time.NewTicker(60 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			tm.mu.Lock()
			for dest := range tm.routingTable {
				if entry, ok := tm.routingTable[dest]; ok {
					entry.LastUpdated = time.Now()
				}
			}
			tm.mu.Unlock()
		}
	}
}

func (tm *TopologyManager) partitionDetectorLoop(ctx context.Context) {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			tm.mu.Lock()
			for nodeID, peers := range tm.nodeAdjacencyMap {
				if len(peers) == 0 {
					already := false
					for _, p := range tm.detectedPartitions {
						for _, n := range p.Nodes {
							if n == nodeID {
								already = true
								break
							}
						}
					}
					if !already {
						tm.detectedPartitions = append(tm.detectedPartitions, NetworkPartition{
							ID:         nodeID + "_partition",
							Nodes:      []string{nodeID},
							DetectedAt: time.Now(),
						})
					}
				}
			}
			tm.mu.Unlock()
		}
	}
}