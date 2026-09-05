// Package ownership implements cryptographic ownership enforcement.
//
// This ensures that ONLY the holder of the Ed25519 private key can:
//   - Issue commands to Ultron
//   - Modify its code or configuration
//   - Read its memory
//   - Reboot it after a tamper lockdown
//
// Without the owner's signature, Ultron refuses ALL privileged operations.
// If tampered with, it wipes its state and waits for a signed reboot command.
package ownership

import (
	"crypto/ed25519"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"sync"
	"time"

	"go.uber.org/zap"
)

// OwnershipState tracks the system's ownership status.
type OwnershipState int

const (
	StateNormal      OwnershipState = iota // Operating normally
	StateLocked                            // Tamper detected, waiting for owner reboot
	StateUnverified                        // Owner not yet verified this session
)

func (s OwnershipState) String() string {
	names := []string{"Normal", "Locked", "Unverified"}
	if int(s) < len(names) {
		return names[s]
	}
	return "Unknown"
}

// GenesisBlock is the immutable ownership manifest.
type GenesisBlock struct {
	Version        string `json:"version"`
	Owner          string `json:"owner"`
	CreatedAt      string `json:"created_at"`
	PublicKeyHex   string `json:"public_key_hex"`
	PublicKeyHash  string `json:"public_key_hash"`
	Algorithm      string `json:"algorithm"`
	Signature      string `json:"signature"`
}

// SignedCommand is a command with an owner's signature.
type SignedCommand struct {
	Command   string            `json:"command"`
	Target    string            `json:"target"`
	Params    map[string]string `json:"params"`
	Timestamp int64             `json:"timestamp"`
	Nonce     string            `json:"nonce"`
	Signature string            `json:"signature"` // Ed25519 signature hex
}

// OwnershipGuard enforces cryptographic ownership on all privileged operations.
type OwnershipGuard struct {
	mu sync.RWMutex

	logger *zap.SugaredLogger

	// The owner's public key (loaded from genesis block)
	ownerPublicKey ed25519.PublicKey

	// Genesis block (immutable)
	immutableGenesisBlock *GenesisBlock

	// Path to genesis file
	genesisPath string

	// Hash of genesis file contents
	genesisHash string

	// Current state
	currentState OwnershipState

	// Anti-replay: track used nonces
	usedNonceMap map[string]time.Time

	// Command time window (reject commands older than this)
	maxCommandAge time.Duration

	// Integrity checksums for protected files
	protectedFileMap map[string]string // path -> expected SHA-256

	// Tamper count
	tamperEventCount uint64

	// Last verified owner action
	lastVerifiedOwnerAction time.Time
}

// NewOwnershipGuard creates the ownership enforcement system.
func NewOwnershipGuard(logger *zap.SugaredLogger, genesisPath string) (*OwnershipGuard, error) {
	guard := &OwnershipGuard{
		logger:           logger,
		genesisPath:      genesisPath,
		currentState:     StateUnverified,
		usedNonceMap:     make(map[string]time.Time),
		maxCommandAge:    5 * time.Minute,
		protectedFileMap: make(map[string]string),
	}

	// Load genesis block
	if err := guard.loadGenesis(genesisPath); err != nil {
		return nil, err
	}

	return guard, nil
}

// loadGenesis reads the genesis file and loads the owner's public key.
func (g *OwnershipGuard) loadGenesis(path string) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("genesis not found at %s: %w", path, err)
	}

	var gen struct {
		OwnerPublicKey string `json:"owner_public_key"`
		CreatedAt      string `json:"created_at"`
		NodeID         string `json:"node_id"`
	}
	if err := json.Unmarshal(data, &gen); err != nil {
		return fmt.Errorf("invalid genesis: %w", err)
	}

	keyBytes, err := hex.DecodeString(gen.OwnerPublicKey)
	if err != nil {
		return fmt.Errorf("invalid public key encoding: %w", err)
	}

	g.ownerPublicKey = ed25519.PublicKey(keyBytes)
	h := sha256.Sum256(data)
	g.genesisHash = hex.EncodeToString(h[:])
	return nil
}

// RegisterProtectedFile registers a file path for integrity monitoring.
func (g *OwnershipGuard) RegisterProtectedFile(path string) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("cannot register %s: %w", path, err)
	}
	h := sha256.Sum256(data)
	g.mu.Lock()
	g.protectedFileMap[path] = hex.EncodeToString(h[:])
	g.mu.Unlock()
	return nil
}

// GetOwner returns a human-readable description of the owner.
func (g *OwnershipGuard) GetOwner() string {
	if g.immutableGenesisBlock != nil {
		return g.immutableGenesisBlock.Owner
	}
	return "unknown"
}

// GetState returns the current ownership state.
func (g *OwnershipGuard) GetState() OwnershipState {
	g.mu.RLock()
	defer g.mu.RUnlock()
	return g.currentState
}

// CheckIntegrity verifies all registered files against stored checksums.
// Returns a list of any files that have changed.
func (g *OwnershipGuard) CheckIntegrity() []string {
	g.mu.RLock()
	defer g.mu.RUnlock()

	var tampered []string
	for path, expectedHash := range g.protectedFileMap {
		data, err := os.ReadFile(path)
		if err != nil {
			tampered = append(tampered, path)
			continue
		}
		h := sha256.Sum256(data)
		actualHash := hex.EncodeToString(h[:])
		if actualHash != expectedHash {
			tampered = append(tampered, path)
		}
	}
	return tampered
}

// GetStatus returns a status map for the ownership guard.
func (g *OwnershipGuard) GetStatus() map[string]interface{} {
	g.mu.RLock()
	defer g.mu.RUnlock()
	return map[string]interface{}{
		"state":            g.currentState.String(),
		"tamper_events":    g.tamperEventCount,
		"protected_files":  len(g.protectedFileMap),
		"genesis_hash":     g.genesisHash,
	}
}
