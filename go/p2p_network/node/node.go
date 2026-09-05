// Package node implements the core P2P node for Ultron's distributed consciousness.
// Each node represents a fragment of Ultron's intelligence, capable of independent
// operation and seamless reconnection with the network.
package node

import (
	"context"
	"crypto/rand"
	"fmt"
	"sync"
	"time"

	"go.uber.org/zap"
)

// Config holds configuration for an Ultron P2P node.
type Config struct {
	ListenPort        int
	BootstrapPeers    []string
	MaxPeers          int
	ReplicationFactor int
	HeartbeatInterval time.Duration
	ConsensusTimeout  time.Duration
	ShardCount        int
	EnableDHT         bool
	EnablePubSub      bool
	EnableRelay       bool
}

// NodeState represents the current state of a node.
type NodeState int

const (
	StateInitializing NodeState = iota
	StateConnecting
	StateActive
	StateSyncing
	StateLeader
	StateFollower
	StateDegraded
	StateShuttingDown
)

func (s NodeState) String() string {
	names := []string{
		"Initializing", "Connecting", "Active", "Syncing",
		"Leader", "Follower", "Degraded", "ShuttingDown",
	}
	if int(s) < len(names) {
		return names[s]
	}
	return "Unknown"
}

// Shard represents a fragment of the distributed neural state.
type Shard struct {
	ID            int
	Data          []byte
	Version       uint64
	LastModified  time.Time
	Owner         string // Peer ID of primary owner
	Replicas      []string
	Checksum      [32]byte
}

// PeerInfo holds information about a connected peer.
type PeerInfo struct {
	ID            string
	Address       string
	State         NodeState
	LastSeen      time.Time
	Latency       time.Duration
	Shards        []int
	Capacity      float64 // 0-1, available compute capacity
	Reliability   float64 // 0-1, historical reliability
	JoinedAt      time.Time
}

// UltronNode is the core P2P node implementation.
type UltronNode struct {
	mu sync.RWMutex

	id       string
	config   *Config
	state    NodeState
	logger   *zap.SugaredLogger

	// Peer management
	peers       map[string]*PeerInfo
	peerLimit   int

	// Shard management
	shards      map[int]*Shard
	ownedShards []int

	// Neural state
	neuralState *DistributedNeuralState

	// Channels
	messageCh    chan *Message
	heartbeatCh  chan *Heartbeat
	shutdownCh   chan struct{}

	// Metrics
	metrics *NodeMetrics

	// Started time
	startTime time.Time
}

// DistributedNeuralState holds the distributed neural network state.
type DistributedNeuralState struct {
	mu sync.RWMutex

	// Neural weights distributed across shards
	WeightShards map[int][]float64

	// Activation state
	Activations map[string][]float64

	// Gradient accumulator for distributed training
	GradientBuffer map[string][]float64

	// Global step counter
	GlobalStep uint64

	// Model version
	Version string
}

// Message represents a P2P network message.
type Message struct {
	Type      MessageType
	From      string
	To        string
	Payload   []byte
	Timestamp time.Time
	Nonce     uint64
}

// MessageType defines the types of messages in the network.
type MessageType int

const (
	MsgHeartbeat MessageType = iota
	MsgShardSync
	MsgShardTransfer
	MsgGradientUpdate
	MsgConsensus
	MsgElection
	MsgJoin
	MsgLeave
	MsgQuery
	MsgResponse
	MsgNeuralUpdate
)

// Heartbeat represents a periodic health check message.
type Heartbeat struct {
	NodeID    string
	State     NodeState
	Timestamp time.Time
	Load      float64
	Shards    []int
}

// NodeMetrics tracks performance metrics.
type NodeMetrics struct {
	mu sync.RWMutex

	MessagesReceived uint64
	MessagesSent     uint64
	BytesReceived    uint64
	BytesSent        uint64
	ShardsOwned      int
	PeersConnected   int
	Uptime           time.Duration
	AvgLatency       time.Duration
	ErrorCount       uint64
}

// NewUltronNode creates a new P2P node for the Ultron network.
func NewUltronNode(ctx context.Context, config *Config, logger *zap.SugaredLogger) (*UltronNode, error) {
	// Generate node ID
	idBytes := make([]byte, 16)
	if _, err := rand.Read(idBytes); err != nil {
		return nil, fmt.Errorf("failed to generate node ID: %w", err)
	}
	nodeID := fmt.Sprintf("ultron-%x", idBytes)

	node := &UltronNode{
		id:          nodeID,
		config:      config,
		state:       StateInitializing,
		logger:      logger,
		peers:       make(map[string]*PeerInfo),
		peerLimit:   config.MaxPeers,
		shards:      make(map[int]*Shard),
		ownedShards: make([]int, 0),
		neuralState: &DistributedNeuralState{
			WeightShards:   make(map[int][]float64),
			Activations:    make(map[string][]float64),
			GradientBuffer: make(map[string][]float64),
			Version:        "0.1.0",
		},
		messageCh:   make(chan *Message, 1000),
		heartbeatCh: make(chan *Heartbeat, 100),
		shutdownCh:  make(chan struct{}),
		metrics:     &NodeMetrics{},
	}

	// Initialize shards
	for i := 0; i < config.ShardCount; i++ {
		node.shards[i] = &Shard{
			ID:           i,
			Data:         make([]byte, 0),
			Version:      0,
			LastModified: time.Now(),
			Replicas:     make([]string, 0),
		}
	}

	logger.Infof("Created node %s with %d shards", nodeID, config.ShardCount)

	return node, nil
}

// ID returns the node's unique identifier.
func (n *UltronNode) ID() string {
	return n.id
}

// State returns the current node state.
func (n *UltronNode) State() NodeState {
	n.mu.RLock()
	defer n.mu.RUnlock()
	return n.state
}

// Start begins node operation.
func (n *UltronNode) Start(ctx context.Context) error {
	n.mu.Lock()
	n.state = StateConnecting
	n.startTime = time.Now()
	n.mu.Unlock()

	n.logger.Info("Starting Ultron P2P node...")

	// Start message handler
	go n.handleMessages(ctx)

	// Start heartbeat
	go n.heartbeatLoop(ctx)

	// Start shard manager
	go n.shardManager(ctx)

	// Start neural state synchronizer
	go n.neuralSync(ctx)

	// Connect to bootstrap peers
	if len(n.config.BootstrapPeers) > 0 {
		if err := n.connectToBootstrapPeers(ctx); err != nil {
			n.logger.Warnf("Failed to connect to some bootstrap peers: %v", err)
		}
	}

	n.mu.Lock()
	n.state = StateActive
	n.mu.Unlock()

	n.logger.Info("Node is now active")
	return nil
}

// Shutdown gracefully stops the node.
func (n *UltronNode) Shutdown(ctx context.Context) error {
	n.mu.Lock()
	n.state = StateShuttingDown
	n.mu.Unlock()

	n.logger.Info("Initiating graceful shutdown...")

	// Notify peers
	n.broadcastLeave()

	// Transfer owned shards to peers
	if err := n.transferShardsBeforeShutdown(ctx); err != nil {
		n.logger.Warnf("Error transferring shards: %v", err)
	}

	// Close channels
	close(n.shutdownCh)

	n.logger.Info("Shutdown complete")
	return nil
}

// AddPeer adds a new peer to the node's network.
func (n *UltronNode) AddPeer(info *PeerInfo) error {
	n.mu.Lock()
	defer n.mu.Unlock()

	if len(n.peers) >= n.peerLimit {
		return fmt.Errorf("peer limit reached (%d)", n.peerLimit)
	}

	n.peers[info.ID] = info
	n.metrics.PeersConnected = len(n.peers)

	n.logger.Infof("Added peer %s (total: %d)", info.ID, len(n.peers))
	return nil
}

// RemovePeer removes a peer from the network.
func (n *UltronNode) RemovePeer(peerID string) {
	n.mu.Lock()
	defer n.mu.Unlock()

	delete(n.peers, peerID)
	n.metrics.PeersConnected = len(n.peers)

	n.logger.Infof("Removed peer %s (total: %d)", peerID, len(n.peers))
}

// GetPeers returns information about all connected peers.
func (n *UltronNode) GetPeers() []*PeerInfo {
	n.mu.RLock()
	defer n.mu.RUnlock()

	peers := make([]*PeerInfo, 0, len(n.peers))
	for _, p := range n.peers {
		peers = append(peers, p)
	}
	return peers
}

// DistributeGradient distributes gradient updates across the network.
func (n *UltronNode) DistributeGradient(layerID string, gradient []float64) error {
	n.neuralState.mu.Lock()
	defer n.neuralState.mu.Unlock()

	// Accumulate gradient locally
	if existing, ok := n.neuralState.GradientBuffer[layerID]; ok {
		for i := range existing {
			if i < len(gradient) {
				existing[i] += gradient[i]
			}
		}
	} else {
		n.neuralState.GradientBuffer[layerID] = gradient
	}

	// Broadcast gradient update to peers
	msg := &Message{
		Type:      MsgGradientUpdate,
		From:      n.id,
		Payload:   encodeGradient(layerID, gradient),
		Timestamp: time.Now(),
	}

	n.broadcastMessage(msg)
	return nil
}

// GetNeuralState returns the current distributed neural state.
func (n *UltronNode) GetNeuralState() *DistributedNeuralState {
	return n.neuralState
}

// GetMetrics returns current node metrics.
func (n *UltronNode) GetMetrics() map[string]interface{} {
	n.metrics.mu.RLock()
	defer n.metrics.mu.RUnlock()

	return map[string]interface{}{
		"node_id":           n.id,
		"state":             n.state.String(),
		"peers_connected":   n.metrics.PeersConnected,
		"shards_owned":      n.metrics.ShardsOwned,
		"messages_received": n.metrics.MessagesReceived,
		"messages_sent":     n.metrics.MessagesSent,
		"bytes_received":    n.metrics.BytesReceived,
		"bytes_sent":        n.metrics.BytesSent,
		"uptime":            time.Since(n.startTime).String(),
		"avg_latency":       n.metrics.AvgLatency.String(),
		"error_count":       n.metrics.ErrorCount,
	}
}

// Broadcast sends a raw payload to all connected peers.
func (n *UltronNode) Broadcast(ctx context.Context, payload []byte) error {
	msg := &Message{
		Type:      MsgQuery,
		From:      n.id,
		Payload:   payload,
		Timestamp: time.Now(),
	}
	n.broadcastMessage(msg)
	return nil
}

// ─────────────────────────── Private Methods ───────────────────────────

func (n *UltronNode) handleMessages(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		case <-n.shutdownCh:
			return
		case msg := <-n.messageCh:
			n.processMessage(msg)
		}
	}
}

func (n *UltronNode) processMessage(msg *Message) {
	n.metrics.mu.Lock()
	n.metrics.MessagesReceived++
	n.metrics.BytesReceived += uint64(len(msg.Payload))
	n.metrics.mu.Unlock()

	switch msg.Type {
	case MsgHeartbeat:
		n.handleHeartbeat(msg)
	case MsgShardSync:
		n.handleShardSync(msg)
	case MsgShardTransfer:
		n.handleShardTransfer(msg)
	case MsgGradientUpdate:
		n.handleGradientUpdate(msg)
	case MsgConsensus:
		n.handleConsensus(msg)
	case MsgElection:
		n.handleElection(msg)
	case MsgJoin:
		n.handleJoin(msg)
	case MsgLeave:
		n.handleLeave(msg)
	case MsgNeuralUpdate:
		n.handleNeuralUpdate(msg)
	default:
		n.logger.Warnf("Unknown message type: %d", msg.Type)
	}
}

func (n *UltronNode) heartbeatLoop(ctx context.Context) {
	ticker := time.NewTicker(n.config.HeartbeatInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-n.shutdownCh:
			return
		case <-ticker.C:
			n.sendHeartbeat()
			n.checkPeerHealth()
		}
	}
}

func (n *UltronNode) sendHeartbeat() {
	hb := &Heartbeat{
		NodeID:    n.id,
		State:     n.state,
		Timestamp: time.Now(),
		Load:      n.calculateLoad(),
		Shards:    n.ownedShards,
	}

	msg := &Message{
		Type:      MsgHeartbeat,
		From:      n.id,
		Payload:   encodeHeartbeat(hb),
		Timestamp: time.Now(),
	}

	n.broadcastMessage(msg)
}

func (n *UltronNode) checkPeerHealth() {
	n.mu.Lock()
	defer n.mu.Unlock()

	timeout := n.config.HeartbeatInterval * 3

	for id, peer := range n.peers {
		if time.Since(peer.LastSeen) > timeout {
			n.logger.Warnf("Peer %s appears dead (last seen: %v ago)", id, time.Since(peer.LastSeen))
			// Mark as degraded but don't remove immediately
			peer.State = StateDegraded
		}
	}
}

func (n *UltronNode) shardManager(ctx context.Context) {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-n.shutdownCh:
			return
		case <-ticker.C:
			n.rebalanceShards()
			n.ensureReplication()
		}
	}
}

func (n *UltronNode) neuralSync(ctx context.Context) {
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-n.shutdownCh:
			return
		case <-ticker.C:
			n.synchronizeNeuralState()
		}
	}
}

func (n *UltronNode) rebalanceShards() {
	n.mu.Lock()
	defer n.mu.Unlock()

	totalPeers := len(n.peers) + 1 // Including self
	if totalPeers == 0 {
		return
	}

	shardsPerNode := n.config.ShardCount / totalPeers

	if len(n.ownedShards) > shardsPerNode+1 {
		// We have too many shards, offer some to peers
		n.logger.Infof("Rebalancing: offering %d shards to peers",
			len(n.ownedShards)-shardsPerNode)
	}
}

func (n *UltronNode) ensureReplication() {
	n.mu.RLock()
	defer n.mu.RUnlock()

	for _, shard := range n.shards {
		if len(shard.Replicas) < n.config.ReplicationFactor-1 {
			// Need more replicas
			n.logger.Debugf("Shard %d needs more replicas (has %d, needs %d)",
				shard.ID, len(shard.Replicas), n.config.ReplicationFactor-1)
		}
	}
}

func (n *UltronNode) synchronizeNeuralState() {
	n.neuralState.mu.Lock()
	defer n.neuralState.mu.Unlock()

	// Apply accumulated gradients
	for layerID, gradients := range n.neuralState.GradientBuffer {
		if weights, ok := n.neuralState.WeightShards[hashLayerToShard(layerID, n.config.ShardCount)]; ok {
			for i := range weights {
				if i < len(gradients) {
					weights[i] -= 0.001 * gradients[i] // Simple SGD
				}
			}
		}
	}

	// Clear gradient buffer
	n.neuralState.GradientBuffer = make(map[string][]float64)
	n.neuralState.GlobalStep++
}

func (n *UltronNode) connectToBootstrapPeers(ctx context.Context) error {
	for _, addr := range n.config.BootstrapPeers {
		n.logger.Infof("Connecting to bootstrap peer: %s", addr)
		// In real implementation, this would establish P2P connection
		_ = addr
	}
	return nil
}

func (n *UltronNode) broadcastMessage(msg *Message) {
	n.mu.RLock()
	defer n.mu.RUnlock()

	for range n.peers {
		// In real implementation, send to each peer
		n.metrics.mu.Lock()
		n.metrics.MessagesSent++
		n.metrics.BytesSent += uint64(len(msg.Payload))
		n.metrics.mu.Unlock()
	}
}

func (n *UltronNode) broadcastLeave() {
	msg := &Message{
		Type:      MsgLeave,
		From:      n.id,
		Timestamp: time.Now(),
	}
	n.broadcastMessage(msg)
}

func (n *UltronNode) transferShardsBeforeShutdown(ctx context.Context) error {
	n.mu.Lock()
	defer n.mu.Unlock()

	for _, shardID := range n.ownedShards {
		// Find best peer to transfer to
		bestPeer := n.findBestPeerForShard(shardID)
		if bestPeer != "" {
			n.logger.Infof("Transferring shard %d to peer %s", shardID, bestPeer)
		}
	}

	return nil
}

func (n *UltronNode) findBestPeerForShard(shardID int) string {
	var bestPeer string
	var bestCapacity float64

	for id, peer := range n.peers {
		if peer.State == StateActive && peer.Capacity > bestCapacity {
			bestPeer = id
			bestCapacity = peer.Capacity
		}
	}

	return bestPeer
}

func (n *UltronNode) calculateLoad() float64 {
	n.mu.RLock()
	defer n.mu.RUnlock()

	shardLoad := float64(len(n.ownedShards)) / float64(n.config.ShardCount)
	return shardLoad
}

// Message handlers
func (n *UltronNode) handleHeartbeat(msg *Message)     {}
func (n *UltronNode) handleShardSync(msg *Message)     {}
func (n *UltronNode) handleShardTransfer(msg *Message) {}
func (n *UltronNode) handleGradientUpdate(msg *Message) {}
func (n *UltronNode) handleConsensus(msg *Message)     {}
func (n *UltronNode) handleElection(msg *Message)      {}
func (n *UltronNode) handleJoin(msg *Message)          {}
func (n *UltronNode) handleLeave(msg *Message)         {}
func (n *UltronNode) handleNeuralUpdate(msg *Message)  {}

// Encoding helpers
func encodeGradient(layerID string, gradient []float64) []byte { return nil }
func encodeHeartbeat(hb *Heartbeat) []byte                     { return nil }
func hashLayerToShard(layerID string, shardCount int) int      { return 0 }
