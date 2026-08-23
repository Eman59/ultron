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
		logger:         logger,
		currentState:   StateUnverified,
		usedNonceMap:   make(map[string]time.Time),
		maxCommandAge:  5 * time.Minute,
		protectedFileMap: make(map[string]string),
	}

	// Load genesis block
	if err := guard.loadGenesis(genesisPath); err != nil {
		return nil, err
	}

	return guard, nil
}