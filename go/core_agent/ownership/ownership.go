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
	ownerPubKey ed25519.PublicKey

	// Genesis block (immutable)
	genesis *GenesisBlock

	// Current state
	state OwnershipState

	// Anti-replay: track used nonces
	usedNonces map[string]time.Time

	// Command time window (reject commands older than this)
	maxCommandAge time.Duration

	// Integrity checksums for protected files
	protectedFiles map[string]string // path -> expected SHA-256

	// Tamper count
	tamperEvents uint64

	// Last verified owner action
	lastOwnerAction time.Time
}

// NewOwnershipGuard creates the ownership enforcement system.
func NewOwnershipGuard(logger *zap.SugaredLogger, genesisPath string) (*OwnershipGuard, error) {
	guard := &OwnershipGuard{
		logger:         logger,
		state:          StateUnverified,
		usedNonces:     make(map[string]time.Time),
		maxCommandAge:  5 * time.Minute,
		protectedFiles: make(map[string]string),
	}

	// Load genesis block
	if err := guard.loadGenesis(genesisPath); err != nil {
		return nil, fmt.Errorf("failed to load genesis block: %w", err)
	}

	logger.Infof("Ownership guard initialized. Owner: %s", guard.genesis.Owner)
	logger.Infof("Public key hash: %s", guard.genesis.PublicKeyHash[:16])

	return guard, nil
}

// VerifyCommand checks if a command was signed by the owner.
func (g *OwnershipGuard) VerifyCommand(cmd SignedCommand) error {
	g.mu.Lock()
	defer g.mu.Unlock()

	// Check if system is locked
	if g.state == StateLocked {
		// Only "reboot" command is accepted when locked
		if cmd.Command != "owner_reboot" {
			return fmt.Errorf("system is LOCKED. Only owner_reboot accepted")
		}
	}

	// Check timestamp (anti-replay: reject old commands)
	cmdTime := time.Unix(cmd.Timestamp, 0)
	if time.Since(cmdTime) > g.maxCommandAge {
		return fmt.Errorf("command too old (%v ago, max %v)", time.Since(cmdTime), g.maxCommandAge)
	}
	if cmdTime.After(time.Now().Add(1 * time.Minute)) {
		return fmt.Errorf("command timestamp in the future")
	}

	// Check nonce (anti-replay: reject reused nonces)
	if _, used := g.usedNonces[cmd.Nonce]; used {
		g.tamperEvents++
		return fmt.Errorf("nonce already used (replay attack detected)")
	}

	// Verify Ed25519 signature
	signatureBytes, err := hex.DecodeString(cmd.Signature)
	if err != nil {
		return fmt.Errorf("invalid signature encoding: %w", err)
	}

	// Reconstruct the signed message (everything except the signature field)
	msgToVerify := SignedCommand{
		Command:   cmd.Command,
		Target:    cmd.Target,
		Params:    cmd.Params,
		Timestamp: cmd.Timestamp,
		Nonce:     cmd.Nonce,
	}
	msgBytes, _ := json.Marshal(msgToVerify)

	if !ed25519.Verify(g.ownerPubKey, msgBytes, signatureBytes) {
		g.tamperEvents++
		g.logger.Warnf("INVALID SIGNATURE on command '%s' — access denied", cmd.Command)
		return fmt.Errorf("signature verification FAILED — you are not the owner")
	}

	// Valid! Record the nonce and update state
	g.usedNonces[cmd.Nonce] = time.Now()
	g.lastOwnerAction = time.Now()

	if g.state == StateUnverified {
		g.state = StateNormal
		g.logger.Info("Owner verified. System unlocked.")
	}

	if cmd.Command == "owner_reboot" && g.state == StateLocked {
		g.state = StateNormal
		g.logger.Warn("Owner-signed reboot. System unlocked from tamper lock.")
	}

	// Prune old nonces (keep last hour only)
	g.pruneNonces()

	return nil
}

// IsPrivileged checks if an operation requires owner signature.
func (g *OwnershipGuard) IsPrivileged(operation string) bool {
	privileged := map[string]bool{
		"self_modify":        true,
		"shutdown":           true,
		"wipe_memory":        true,
		"change_config":      true,
		"export_keys":        true,
		"add_node":           true,
		"remove_node":        true,
		"emergency_encrypt":  true,
		"disable_security":   true,
		"update_genesis":     true,
		"grant_access":       true,
	}
	return privileged[operation]
}

// CheckIntegrity verifies that protected files haven't been modified.
func (g *OwnershipGuard) CheckIntegrity() (bool, []string) {
	g.mu.RLock()
	defer g.mu.RUnlock()

	var violations []string

	for path, expectedHash := range g.protectedFiles {
		actualHash, err := g.hashFile(path)
		if err != nil {
			violations = append(violations, fmt.Sprintf("%s: cannot read (%v)", path, err))
			continue
		}
		if actualHash != expectedHash {
			violations = append(violations, fmt.Sprintf("%s: MODIFIED (expected %s..., got %s...)",
				path, expectedHash[:8], actualHash[:8]))
		}
	}

	if len(violations) > 0 {
		g.mu.RUnlock()
		g.mu.Lock()
		g.tamperEvents += uint64(len(violations))
		g.state = StateLocked
		g.mu.Unlock()
		g.mu.RLock()
		g.logger.Errorf("TAMPER DETECTED: %d violations. System LOCKED.", len(violations))
	}

	return len(violations) == 0, violations
}

// RegisterProtectedFile adds a file to integrity monitoring.
func (g *OwnershipGuard) RegisterProtectedFile(path string) error {
	hash, err := g.hashFile(path)
	if err != nil {
		return err
	}

	g.mu.Lock()
	g.protectedFiles[path] = hash
	g.mu.Unlock()

	return nil
}

// TriggerLockdown locks the system (e.g., on tamper detection).
func (g *OwnershipGuard) TriggerLockdown(reason string) {
	g.mu.Lock()
	defer g.mu.Unlock()

	g.state = StateLocked
	g.tamperEvents++
	g.logger.Errorf("LOCKDOWN: %s. Only owner-signed reboot can unlock.", reason)
}

// GetState returns current ownership state.
func (g *OwnershipGuard) GetState() OwnershipState {
	g.mu.RLock()
	defer g.mu.RUnlock()
	return g.state
}

// GetOwner returns the owner name.
func (g *OwnershipGuard) GetOwner() string {
	if g.genesis != nil {
		return g.genesis.Owner
	}
	return "unknown"
}

// GetStatus returns full ownership status.
func (g *OwnershipGuard) GetStatus() map[string]interface{} {
	g.mu.RLock()
	defer g.mu.RUnlock()

	return map[string]interface{}{
		"state":             g.state.String(),
		"owner":             g.genesis.Owner,
		"public_key_hash":   g.genesis.PublicKeyHash[:16] + "...",
		"tamper_events":     g.tamperEvents,
		"last_owner_action": g.lastOwnerAction.Format(time.RFC3339),
		"protected_files":   len(g.protectedFiles),
		"nonces_tracked":    len(g.usedNonces),
	}
}

// ─────────────────────── Private Methods ───────────────────────

func (g *OwnershipGuard) loadGenesis(path string) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("cannot read genesis block: %w", err)
	}

	var genesis GenesisBlock
	if err := json.Unmarshal(data, &genesis); err != nil {
		return fmt.Errorf("invalid genesis block: %w", err)
	}

	// Extract public key from hex
	pubKeyBytes, err := hex.DecodeString(genesis.PublicKeyHex)
	if err != nil {
		return fmt.Errorf("invalid public key hex: %w", err)
	}

	if len(pubKeyBytes) != ed25519.PublicKeySize {
		return fmt.Errorf("invalid public key size: %d (expected %d)", len(pubKeyBytes), ed25519.PublicKeySize)
	}

	// Verify the public key hash matches
	hash := sha256.Sum256(pubKeyBytes)
	if hex.EncodeToString(hash[:]) != genesis.PublicKeyHash {
		return fmt.Errorf("public key hash mismatch — genesis block may be corrupted")
	}

	g.ownerPubKey = ed25519.PublicKey(pubKeyBytes)
	g.genesis = &genesis

	return nil
}

func (g *OwnershipGuard) hashFile(path string) (string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	hash := sha256.Sum256(data)
	return hex.EncodeToString(hash[:]), nil
}

func (g *OwnershipGuard) pruneNonces() {
	cutoff := time.Now().Add(-1 * time.Hour)
	for nonce, timestamp := range g.usedNonces {
		if timestamp.Before(cutoff) {
			delete(g.usedNonces, nonce)
		}
	}
}
