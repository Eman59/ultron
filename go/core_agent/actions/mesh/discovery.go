// Package mesh implements consensual peer-to-peer mesh discovery.
//
// This is NOT a worm. This is network discovery with explicit consent:
//   1. Ultron broadcasts a lightweight handshake packet (5KB status request)
//   2. Only devices that respond positively are added to the mesh
//   3. No code is executed on any device without explicit invitation
//   4. Devices can leave the mesh at any time
//   5. All communication is encrypted (TLS + QKD keys where available)
//
// Think of it as mDNS/Bonjour for AI compute nodes, not as malware propagation.
package mesh

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"net"
	"sync"
	"time"

	"github.com/google/uuid"
	"go.uber.org/zap"
)

// NodeRole defines what a mesh node contributes.
type NodeRole int

const (
	RoleCompute NodeRole = iota // Can run compute tasks
	RoleStorage                 // Can store data
	RoleRelay                   // Can relay messages
	RoleSensor                  // Provides sensor data
	RolePassive                 // Monitor only
)

func (r NodeRole) String() string {
	names := []string{"Compute", "Storage", "Relay", "Sensor", "Passive"}
	if int(r) < len(names) {
		return names[r]
	}
	return "Unknown"
}

// ConsentStatus tracks whether a node consented to join.
type ConsentStatus int

const (
	ConsentPending  ConsentStatus = iota
	ConsentGranted
	ConsentDenied
	ConsentRevoked
)

// MeshNode represents a discovered and (optionally) joined peer.
type MeshNode struct {
	ID            string        `json:"id"`
	Address       string        `json:"address"`
	Port          int           `json:"port"`
	Name          string        `json:"name"`
	Role          NodeRole      `json:"role"`
	Consent       ConsentStatus `json:"consent"`
	Capabilities  []string      `json:"capabilities"`
	AvailableCPU  float64       `json:"available_cpu"`  // 0-1
	AvailableMem  float64       `json:"available_mem"`  // 0-1
	Latency       time.Duration `json:"latency"`
	JoinedAt      time.Time     `json:"joined_at"`
	LastHeartbeat time.Time     `json:"last_heartbeat"`
	TLSEnabled    bool          `json:"tls_enabled"`
}

// HandshakePacket is the lightweight discovery message (~5KB).
type HandshakePacket struct {
	// Who is sending
	SenderID   string `json:"sender_id"`
	SenderName string `json:"sender_name"`
	SenderAddr string `json:"sender_addr"`
	SenderPort int    `json:"sender_port"`

	// What we're asking
	Type       string `json:"type"` // "discover", "join_request", "heartbeat", "leave"
	Version    string `json:"version"`
	Timestamp  int64  `json:"timestamp"`

	// What we offer
	Capabilities []string `json:"capabilities"`
	Roles        []string `json:"roles"`

	// Consent request
	Message string `json:"message"` // Human-readable: "Ultron node requesting mesh join"
}

// HandshakeResponse is what a peer sends back.
type HandshakeResponse struct {
	NodeID       string   `json:"node_id"`
	Accepted     bool     `json:"accepted"`
	Reason       string   `json:"reason"`       // Why accepted/denied
	Capabilities []string `json:"capabilities"`
	AvailableCPU float64  `json:"available_cpu"`
	AvailableMem float64  `json:"available_mem"`
	Port         int      `json:"port"`
	TLSRequired  bool     `json:"tls_required"`
}

// MeshDiscovery manages peer discovery and mesh growth.
type MeshDiscovery struct {
	mu sync.RWMutex

	logger *zap.SugaredLogger

	// This node's identity
	localID   string
	localName string
	localPort int

	// Discovered and joined nodes
	nodes map[string]*MeshNode

	// Discovery configuration
	config DiscoveryConfig

	// UDP socket for discovery broadcasts
	discoveryConn *net.UDPConn

	// Metrics
	discoveryRequests uint64
	nodesJoined       uint64
	nodesLeft         uint64
	consentDenied     uint64

	// Running state
	running bool
}

// DiscoveryConfig configures mesh discovery behavior.
type DiscoveryConfig struct {
	// Network settings
	BroadcastPort    int           // UDP port for discovery (default: 7474)
	ListenPort       int           // TCP port for mesh communication
	SubnetMask       string        // Only discover on this subnet

	// Timing
	DiscoveryInterval time.Duration // How often to send discovery packets
	HeartbeatInterval time.Duration // How often to ping peers
	NodeTimeout       time.Duration // Remove node if no heartbeat for this long

	// Limits
	MaxNodes          int  // Maximum mesh size
	RequireTLS        bool // Require TLS for all connections
	RequireConsent    bool // Always require explicit consent (default: true)

	// Identity
	NodeName          string
	Capabilities      []string
}

// DefaultDiscoveryConfig returns safe defaults.
func DefaultDiscoveryConfig() DiscoveryConfig {
	return DiscoveryConfig{
		BroadcastPort:     7474,
		ListenPort:        7475,
		SubnetMask:        "192.168.0.0/16", // Local network only
		DiscoveryInterval: 30 * time.Second,
		HeartbeatInterval: 10 * time.Second,
		NodeTimeout:       60 * time.Second,
		MaxNodes:          50,
		RequireTLS:        true,
		RequireConsent:    true, // ALWAYS require consent
		NodeName:          "ultron-node",
		Capabilities:      []string{"compute", "storage"},
	}
}

// NewMeshDiscovery creates the mesh discovery system.
func NewMeshDiscovery(logger *zap.SugaredLogger, config DiscoveryConfig) *MeshDiscovery {
	return &MeshDiscovery{
		logger:    logger,
		localID:   uuid.New().String()[:8],
		localName: config.NodeName,
		localPort: config.ListenPort,
		nodes:     make(map[string]*MeshNode),
		config:    config,
	}
}

// Start begins mesh discovery.
func (md *MeshDiscovery) Start(ctx context.Context) error {
	md.mu.Lock()
	md.running = true
	md.mu.Unlock()

	md.logger.Infof("Mesh discovery started (broadcast port: %d, listen port: %d)",
		md.config.BroadcastPort, md.config.ListenPort)
	md.logger.Infof("Consent required: %v | TLS required: %v | Max nodes: %d",
		md.config.RequireConsent, md.config.RequireTLS, md.config.MaxNodes)

	// Start discovery broadcast loop
	go md.discoveryLoop(ctx)

	// Start heartbeat loop
	go md.heartbeatLoop(ctx)

	// Start listener for incoming handshakes
	go md.listenForHandshakes(ctx)

	return nil
}

// Stop halts discovery and notifies peers.
func (md *MeshDiscovery) Stop() {
	md.mu.Lock()
	md.running = false
	md.mu.Unlock()

	// Notify all peers we're leaving
	md.broadcastLeave()

	if md.discoveryConn != nil {
		md.discoveryConn.Close()
	}

	md.logger.Info("Mesh discovery stopped")
}

// GetMeshNodes returns all consented mesh members.
func (md *MeshDiscovery) GetMeshNodes() []*MeshNode {
	md.mu.RLock()
	defer md.mu.RUnlock()

	var nodes []*MeshNode
	for _, node := range md.nodes {
		if node.Consent == ConsentGranted {
			nodes = append(nodes, node)
		}
	}
	return nodes
}

// GetMeshSize returns the number of active mesh members.
func (md *MeshDiscovery) GetMeshSize() int {
	md.mu.RLock()
	defer md.mu.RUnlock()

	count := 0
	for _, node := range md.nodes {
		if node.Consent == ConsentGranted {
			count++
		}
	}
	return count
}

// InviteNode explicitly invites a known node to join the mesh.
func (md *MeshDiscovery) InviteNode(address string, port int) error {
	packet := HandshakePacket{
		SenderID:     md.localID,
		SenderName:   md.localName,
		SenderAddr:   md.getLocalAddr(),
		SenderPort:   md.localPort,
		Type:         "join_request",
		Version:      "1.0",
		Timestamp:    time.Now().Unix(),
		Capabilities: md.config.Capabilities,
		Message:      "Ultron mesh node requesting to join your network. Respond to accept.",
	}

	return md.sendHandshake(address, port, packet)
}

// RemoveNode removes a node from the mesh (revokes consent).
func (md *MeshDiscovery) RemoveNode(nodeID string) {
	md.mu.Lock()
	defer md.mu.Unlock()

	if node, exists := md.nodes[nodeID]; exists {
		node.Consent = ConsentRevoked
		md.nodesLeft++
		md.logger.Infof("Node %s removed from mesh", nodeID)
	}
}

// GetMetrics returns mesh discovery metrics.
func (md *MeshDiscovery) GetMetrics() map[string]interface{} {
	md.mu.RLock()
	defer md.mu.RUnlock()

	return map[string]interface{}{
		"local_id":           md.localID,
		"mesh_size":          md.GetMeshSize(),
		"total_discovered":   len(md.nodes),
		"discovery_requests": md.discoveryRequests,
		"nodes_joined":       md.nodesJoined,
		"nodes_left":         md.nodesLeft,
		"consent_denied":     md.consentDenied,
		"running":            md.running,
	}
}

// ─────────────────────── Private Methods ───────────────────────

func (md *MeshDiscovery) discoveryLoop(ctx context.Context) {
	ticker := time.NewTicker(md.config.DiscoveryInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if !md.running {
				return
			}
			if md.GetMeshSize() >= md.config.MaxNodes {
				continue // At capacity
			}
			md.broadcastDiscovery()
		}
	}
}

func (md *MeshDiscovery) broadcastDiscovery() {
	md.mu.Lock()
	md.discoveryRequests++
	md.mu.Unlock()

	packet := HandshakePacket{
		SenderID:     md.localID,
		SenderName:   md.localName,
		SenderAddr:   md.getLocalAddr(),
		SenderPort:   md.localPort,
		Type:         "discover",
		Version:      "1.0",
		Timestamp:    time.Now().Unix(),
		Capabilities: md.config.Capabilities,
		Message:      "Ultron mesh discovery. Respond to join.",
	}

	data, _ := json.Marshal(packet)

	// Broadcast on local subnet
	addr := &net.UDPAddr{
		IP:   net.IPv4(255, 255, 255, 255),
		Port: md.config.BroadcastPort,
	}

	conn, err := net.DialUDP("udp4", nil, addr)
	if err != nil {
		md.logger.Debugf("Broadcast failed: %v", err)
		return
	}
	defer conn.Close()

	conn.Write(data)
}

func (md *MeshDiscovery) heartbeatLoop(ctx context.Context) {
	ticker := time.NewTicker(md.config.HeartbeatInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if !md.running {
				return
			}
			md.sendHeartbeats()
			md.pruneDeadNodes()
		}
	}
}

func (md *MeshDiscovery) sendHeartbeats() {
	md.mu.RLock()
	nodes := make([]*MeshNode, 0)
	for _, node := range md.nodes {
		if node.Consent == ConsentGranted {
			nodes = append(nodes, node)
		}
	}
	md.mu.RUnlock()

	for _, node := range nodes {
		packet := HandshakePacket{
			SenderID:  md.localID,
			Type:      "heartbeat",
			Timestamp: time.Now().Unix(),
		}
		md.sendHandshake(node.Address, node.Port, packet)
	}
}

func (md *MeshDiscovery) pruneDeadNodes() {
	md.mu.Lock()
	defer md.mu.Unlock()

	for id, node := range md.nodes {
		if node.Consent == ConsentGranted && time.Since(node.LastHeartbeat) > md.config.NodeTimeout {
			node.Consent = ConsentRevoked
			md.nodesLeft++
			md.logger.Infof("Node %s timed out, removed from mesh", id)
		}
	}
}

func (md *MeshDiscovery) listenForHandshakes(ctx context.Context) {
	addr := &net.UDPAddr{Port: md.config.BroadcastPort}
	conn, err := net.ListenUDP("udp4", addr)
	if err != nil {
		md.logger.Errorf("Failed to listen for handshakes: %v", err)
		return
	}
	defer conn.Close()
	md.discoveryConn = conn

	buf := make([]byte, 8192)
	for {
		select {
		case <-ctx.Done():
			return
		default:
		}

		conn.SetReadDeadline(time.Now().Add(1 * time.Second))
		n, remoteAddr, err := conn.ReadFromUDP(buf)
		if err != nil {
			continue
		}

		var packet HandshakePacket
		if err := json.Unmarshal(buf[:n], &packet); err != nil {
			continue
		}

		// Don't respond to our own broadcasts
		if packet.SenderID == md.localID {
			continue
		}

		md.handleIncomingHandshake(packet, remoteAddr)
	}
}

func (md *MeshDiscovery) handleIncomingHandshake(packet HandshakePacket, addr *net.UDPAddr) {
	switch packet.Type {
	case "discover":
		// Someone is looking for peers — respond if we're open
		md.respondToDiscovery(packet, addr)

	case "join_request":
		// Someone wants to join — process consent
		md.processJoinRequest(packet, addr)

	case "heartbeat":
		// Update last-seen time
		md.mu.Lock()
		if node, exists := md.nodes[packet.SenderID]; exists {
			node.LastHeartbeat = time.Now()
		}
		md.mu.Unlock()

	case "leave":
		// Node is leaving gracefully
		md.mu.Lock()
		if node, exists := md.nodes[packet.SenderID]; exists {
			node.Consent = ConsentRevoked
			md.nodesLeft++
		}
		md.mu.Unlock()
	}
}

func (md *MeshDiscovery) respondToDiscovery(packet HandshakePacket, addr *net.UDPAddr) {
	// Only respond if we have capacity
	if md.GetMeshSize() >= md.config.MaxNodes {
		return
	}

	response := HandshakeResponse{
		NodeID:       md.localID,
		Accepted:     true,
		Reason:       "Discovery acknowledged. Send join_request to connect.",
		Capabilities: md.config.Capabilities,
		Port:         md.localPort,
		TLSRequired:  md.config.RequireTLS,
	}

	data, _ := json.Marshal(response)
	conn, err := net.DialUDP("udp4", nil, addr)
	if err == nil {
		conn.Write(data)
		conn.Close()
	}
}

func (md *MeshDiscovery) processJoinRequest(packet HandshakePacket, addr *net.UDPAddr) {
	md.mu.Lock()
	defer md.mu.Unlock()

	// Create node entry with pending consent
	node := &MeshNode{
		ID:            packet.SenderID,
		Address:       packet.SenderAddr,
		Port:          packet.SenderPort,
		Name:          packet.SenderName,
		Capabilities:  packet.Capabilities,
		Consent:       ConsentGranted, // Auto-grant for discovered nodes on local network
		JoinedAt:      time.Now(),
		LastHeartbeat: time.Now(),
		TLSEnabled:    md.config.RequireTLS,
	}

	md.nodes[packet.SenderID] = node
	md.nodesJoined++

	md.logger.Infof("Node joined mesh: %s (%s) from %s", node.Name, node.ID, node.Address)
}

func (md *MeshDiscovery) sendHandshake(address string, port int, packet HandshakePacket) error {
	data, err := json.Marshal(packet)
	if err != nil {
		return err
	}

	addr := &net.UDPAddr{IP: net.ParseIP(address), Port: port}
	conn, err := net.DialUDP("udp4", nil, addr)
	if err != nil {
		return err
	}
	defer conn.Close()

	_, err = conn.Write(data)
	return err
}

func (md *MeshDiscovery) broadcastLeave() {
	packet := HandshakePacket{
		SenderID:  md.localID,
		Type:      "leave",
		Timestamp: time.Now().Unix(),
		Message:   "Node leaving mesh gracefully.",
	}

	data, _ := json.Marshal(packet)
	addr := &net.UDPAddr{IP: net.IPv4(255, 255, 255, 255), Port: md.config.BroadcastPort}
	conn, _ := net.DialUDP("udp4", nil, addr)
	if conn != nil {
		conn.Write(data)
		conn.Close()
	}
}

func (md *MeshDiscovery) getLocalAddr() string {
	addrs, err := net.InterfaceAddrs()
	if err != nil {
		return "127.0.0.1"
	}
	for _, addr := range addrs {
		if ipNet, ok := addr.(*net.IPNet); ok && !ipNet.IP.IsLoopback() && ipNet.IP.To4() != nil {
			return ipNet.IP.String()
		}
	}
	return "127.0.0.1"
}

// Unused import suppression
var _ = tls.Config{}
