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
	"sync"
	"time"
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

var nodeRoleNames = [...]string{"Compute", "Storage", "Relay", "Sensor", "Passive"}

func (r NodeRole) String() string {
	if int(r) < len(nodeRoleNames) {
		return nodeRoleNames[r]
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

var consentStatusNames = [...]string{"Pending", "Granted", "Denied", "Revoked"}

func (c ConsentStatus) String() string {
	if int(c) < len(consentStatusNames) {
		return consentStatusNames[c]
	}
	return "Unknown"
}

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
	Capabilities []string `json:"capabilities"` // What the node offers
}

// Cache for node roles and consent status
var (
	nodeRoleCache = sync.Map{}
	consentStatusCache = sync.Map{}
)

func init() {
	for i, name := range nodeRoleNames {
		nodeRoleCache.Store(i, name)
	}
	for i, name := range consentStatusNames {
		consentStatusCache.Store(i, name)
	}
}

func getNodeRoleName(role NodeRole) string {
	if value, ok := nodeRoleCache.Load(int(role)); ok {
		return value.(string)
	}
	return "Unknown"
}

func getConsentStatusName(status ConsentStatus) string {
	if value, ok := consentStatusCache.Load(int(status)); ok {
		return value.(string)
	}
	return "Unknown"
}

// NewMeshNode returns a new MeshNode instance.
func NewMeshNode(id string, address string, port int, name string, role NodeRole, consent ConsentStatus) *MeshNode {
	return &MeshNode{
		ID:            id,
		Address:       address,
		Port:          port,
		Name:          name,
		Role:          role,
		Consent:       consent,
		Capabilities:  make([]string, 0),
		AvailableCPU:  0,
		AvailableMem:  0,
		Latency:       0,
		JoinedAt:      time.Time{},
		LastHeartbeat: time.Time{},
		TLSEnabled:    false,
	}
}

// NewHandshakePacket returns a new HandshakePacket instance.
func NewHandshakePacket(senderID string, senderName string, senderAddr string, senderPort int, packetType string, version string, timestamp int64, capabilities []string, roles []string, message string) *HandshakePacket {
	return &HandshakePacket{
		SenderID:   senderID,
		SenderName: senderName,
		SenderAddr: senderAddr,
		SenderPort: senderPort,
		Type:       packetType,
		Version:    version,
		Timestamp:  timestamp,
		Capabilities: capabilities,
		Roles:        roles,
		Message:      message,
	}
}

// NewHandshakeResponse returns a new HandshakeResponse instance.
func NewHandshakeResponse(nodeID string, accepted bool, reason string, capabilities []string) *HandshakeResponse {
	return &HandshakeResponse{
		NodeID:       nodeID,
		Accepted:     accepted,
		Reason:       reason,
		Capabilities: capabilities,
	}
}

// DiscoveryConfig holds configuration for mesh discovery.
type DiscoveryConfig struct {
	NodeName    string
	BroadcastPort int
	ScanInterval  time.Duration
	MaxNodes      int
}

// DefaultDiscoveryConfig returns sensible defaults.
func DefaultDiscoveryConfig() *DiscoveryConfig {
	return &DiscoveryConfig{
		NodeName:      "ultron-node",
		BroadcastPort: 47892,
		ScanInterval:  30 * time.Second,
		MaxNodes:      100,
	}
}

// MeshDiscovery manages peer discovery on the local network.
type MeshDiscovery struct {
	mu     sync.RWMutex
	cfg    *DiscoveryConfig
	nodes  []*MeshNode
	nodeMap sync.Map
}

// NewMeshDiscovery creates a new mesh discovery instance.
func NewMeshDiscovery(logger interface{}, cfg *DiscoveryConfig) *MeshDiscovery {
	return &MeshDiscovery{cfg: cfg}
}

// Start begins broadcasting and listening for peers.
func (md *MeshDiscovery) Start(ctx interface{}) error {
	return nil // Stub: real implementation uses UDP broadcast
}

// GetMeshNodes returns all currently known mesh nodes.
func (md *MeshDiscovery) GetMeshNodes() []*MeshNode {
	md.mu.RLock()
	defer md.mu.RUnlock()
	return md.nodes
}

// GetMeshSize returns the number of known mesh nodes.
func (md *MeshDiscovery) GetMeshSize() int {
	md.mu.RLock()
	defer md.mu.RUnlock()
	return len(md.nodes)
}

// Stop shuts down the mesh discovery service.
func (md *MeshDiscovery) Stop() {
	// Stub: real impl sends leave packet and closes UDP socket
}
