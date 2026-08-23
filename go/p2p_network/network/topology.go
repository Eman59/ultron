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