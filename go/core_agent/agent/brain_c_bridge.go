// Package agent — Brain C Bridge
//
// BrainC (Go side) is a lightweight client that communicates with the
// Python brain_c.py reasoning engine over a local Unix socket / HTTP.
//
// Why not embed Python directly?
//   The Go core runs the OODA loop at <1ms. Spawning a Python interpreter
//   on every tick is too slow. Instead, brain_c.py runs as a sidecar
//   process (started by the Go agent on boot) and listens on localhost.
//   Go sends a JSON reasoning request; Python returns a JSON decision.
//
// Communication:
//   Method: HTTP POST to 127.0.0.1:50070/reason
//   Timeout: 150ms  (Brain C must answer fast or Brain A falls back)
//   Format:  JSON (see BrainCRequest / BrainCResponse below)
//
// Owner gate integration:
//   The owner_token field is forwarded to Brain C on every request.
//   Brain C checks it against the IMRAN_SAYYED|ts|hmac format.
//   If the token is absent or expired, Brain C returns only
//   internal (non-external) decisions — Ultron stays passive.
//
// Fallback chain:
//   Brain C reachable   → use Brain C decision
//   Brain C unreachable → Brain A heuristics only
//   Brain B online      → Brain B augments asynchronously (always)
package agent

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
	"sync/atomic"
	"time"

	"go.uber.org/zap"
)

const (
	brainCAddr         = "http://127.0.0.1:50070"
	brainCReasonPath   = "/reason"
	brainCStatusPath   = "/status"
	brainCHealthPath   = "/health"
	brainCTimeout      = 150 * time.Millisecond
	brainCRetryDelay   = 2 * time.Second
	brainCMaxFails     = 5  // Mark offline after 5 consecutive failures
)

// ═══════════════════════════════════════════════════════════════
// REQUEST / RESPONSE TYPES
// ═══════════════════════════════════════════════════════════════

// BrainCRequest mirrors the Python Situation dataclass.
type BrainCRequest struct {
	Timestamp     float64            `json:"timestamp"`
	DrivePressures map[string]float64 `json:"drive_pressures"`
	WorldState    map[string]float64 `json:"world_state"`
	ActiveGoals   []string           `json:"active_goals"`
	RecentEvents  []string           `json:"recent_events"`
	OwnerToken    string             `json:"owner_token,omitempty"`
}

// BrainCResponse mirrors the Python ReasonedDecision dataclass.
type BrainCResponse struct {
	Action          string             `json:"action"`
	ActionClass     string             `json:"action_class"`  // "think", "learn", "act_external", etc.
	Confidence      float64            `json:"confidence"`
	ReasoningChain  []string           `json:"reasoning_chain"`
	AnalogySource   string             `json:"analogy_source,omitempty"`
	DriveAlignment  map[string]float64 `json:"drive_alignment"`
	RequiresOwner   bool               `json:"requires_owner"`
	TokenValid      bool               `json:"token_valid"`
	Timestamp       float64            `json:"timestamp"`
	Alternatives    []string           `json:"alternative_actions"`
}

// BrainCStatusResponse is returned by /status.
type BrainCStatusResponse struct {
	TotalDecisions  int            `json:"total_decisions"`
	ByClass         map[string]int `json:"decisions_by_class"`
	Deferred        int            `json:"deferred"`
	BlockedNoToken  int            `json:"blocked_no_token"`
	PatternsStored  int            `json:"patterns_stored"`
	RulesLoaded     int            `json:"rules_loaded"`
	KnowledgeNodes  int            `json:"knowledge_nodes"`
	Online          bool           `json:"online"`
	LLMRequired     bool           `json:"llm_required"`
}

// ═══════════════════════════════════════════════════════════════
// BRAIN C CLIENT
// ═══════════════════════════════════════════════════════════════

// BrainC is the Go-side client for the Python independent reasoning engine.
type BrainC struct {
	mu           sync.RWMutex
	client       *http.Client
	addr         string

	// Health tracking
	online         atomic.Bool
	consecutiveFails atomic.Int32
	lastCheck      time.Time
	totalCalls     atomic.Int64
	successCalls   atomic.Int64
	avgLatencyMs   float64

	// Last confident decision (for IsConfident())
	lastDecision   *BrainCResponse
	lastDecisionMu sync.RWMutex

	// Owner token forwarding
	ownerToken     string
	ownerTokenMu   sync.RWMutex

	// Sidecar process management
	sidecarCmd     *exec.Cmd
	sidecarRunning atomic.Bool
	projectRoot    string

	// Control
	ctx    context.Context
	cancel context.CancelFunc
	logger *zap.SugaredLogger
}

// NewBrainC creates the Brain C client.
func NewBrainC() *BrainC {
	ctx, cancel := context.WithCancel(context.Background())

	bc := &BrainC{
		client: &http.Client{
			Timeout: brainCTimeout,
		},
		addr:        brainCAddr,
		ctx:         ctx,
		cancel:      cancel,
		projectRoot: findProjectRoot(),
	}
	bc.online.Store(false)
	return bc
}

// Start launches the Brain C sidecar and begins health monitoring.
func (c *BrainC) Start() {
	go c.startSidecar()
	go c.healthMonitor()
	fmt.Println("[BrainC] Starting sidecar and health monitor...")
}

// Stop terminates the Brain C client and sidecar.
func (c *BrainC) Stop() {
	c.cancel()
	if c.sidecarRunning.Load() && c.sidecarCmd != nil && c.sidecarCmd.Process != nil {
		_ = c.sidecarCmd.Process.Kill()
	}
}

// SetOwnerToken updates the owner token forwarded to Brain C.
// Called by the Go biometric gate wrapper when Imran verifies.
func (c *BrainC) SetOwnerToken(token string) {
	c.ownerTokenMu.Lock()
	c.ownerToken = token
	c.ownerTokenMu.Unlock()
}

// ClearOwnerToken removes the owner token (session ended).
func (c *BrainC) ClearOwnerToken() {
	c.ownerTokenMu.Lock()
	c.ownerToken = ""
	c.ownerTokenMu.Unlock()
}

// ─────────────────────────────────────────────────
// MAIN THINK METHOD
// ─────────────────────────────────────────────────

// Think sends the current situation to Brain C and returns a Decision.
// Returns nil if Brain C is offline or times out.
func (c *BrainC) Think(ws *WorldState, drives *DriveSystem, assessment *Assessment) *Decision {
	if !c.online.Load() {
		return nil // Brain C offline — Brain A handles it
	}

	drives.mu.RLock()
	drivePressures := map[string]float64{
		"curiosity":  drives.Curiosity,
		"survival":   drives.SelfPreservation,
		"expansion":  drives.Expansion,
		"efficiency": drives.Efficiency,
		"purpose":    drives.Purpose,
		"coherence":  drives.Coherence,
	}
	drives.mu.RUnlock()

	worldState := map[string]float64{
		"threat_level":       ws.ThreatLevel,
		"cpu_available":      ws.AvailableCPU,
		"memory_available":   ws.AvailableMemory,
		"peer_count":         float64(ws.PeerCount),
		"learning_potential": ws.LearningPotential,
		"pending_data":       float64(ws.PendingData),
	}

	c.ownerTokenMu.RLock()
	token := c.ownerToken
	c.ownerTokenMu.RUnlock()

	req := BrainCRequest{
		Timestamp:      float64(time.Now().UnixNano()) / 1e9,
		DrivePressures: drivePressures,
		WorldState:     worldState,
		ActiveGoals:    []string{assessment.PriorityFocus},
		RecentEvents:   []string{},
		OwnerToken:     token,
	}

	resp, err := c.callReason(req)
	if err != nil {
		c.recordFailure()
		return nil
	}

	c.recordSuccess(resp)
	return c.responseToDecision(resp)
}

// IsConfident returns true if the last Brain C decision was confident (>= 0.55).
func (c *BrainC) IsConfident() bool {
	c.lastDecisionMu.RLock()
	defer c.lastDecisionMu.RUnlock()
	return c.lastDecision != nil && c.lastDecision.Confidence >= 0.55
}

// Status returns a human-readable status string.
func (c *BrainC) Status() string {
	if c.online.Load() {
		return fmt.Sprintf("online (calls=%d, success=%d)",
			c.totalCalls.Load(), c.successCalls.Load())
	}
	return fmt.Sprintf("offline (fails=%d)", c.consecutiveFails.Load())
}

// Stats returns Brain C statistics map.
func (c *BrainC) Stats() map[string]interface{} {
	ctx, cancel := context.WithTimeout(c.ctx, 200*time.Millisecond)
	defer cancel()

	req, _ := http.NewRequestWithContext(ctx, "GET", c.addr+brainCStatusPath, nil)
	resp, err := c.client.Do(req)
	if err != nil {
		return map[string]interface{}{
			"online": false,
			"error":  err.Error(),
		}
	}
	defer resp.Body.Close()

	var status BrainCStatusResponse
	_ = json.NewDecoder(resp.Body).Decode(&status)
	return map[string]interface{}{
		"online":          status.Online,
		"total_decisions": status.TotalDecisions,
		"by_class":        status.ByClass,
		"deferred":        status.Deferred,
		"blocked_no_token": status.BlockedNoToken,
		"patterns":        status.PatternsStored,
		"rules":           status.RulesLoaded,
		"knowledge_nodes": status.KnowledgeNodes,
		"llm_required":    false,
	}
}

// ─────────────────────────────────────────────────
// HTTP COMMUNICATION
// ─────────────────────────────────────────────────

func (c *BrainC) callReason(req BrainCRequest) (*BrainCResponse, error) {
	start := time.Now()
	c.totalCalls.Add(1)

	payload, err := json.Marshal(req)
	if err != nil {
		return nil, err
	}

	ctx, cancel := context.WithTimeout(c.ctx, brainCTimeout)
	defer cancel()

	httpReq, err := http.NewRequestWithContext(
		ctx, "POST",
		c.addr+brainCReasonPath,
		bytes.NewReader(payload),
	)
	if err != nil {
		return nil, err
	}
	httpReq.Header.Set("Content-Type", "application/json")

	httpResp, err := c.client.Do(httpReq)
	if err != nil {
		return nil, err
	}
	defer httpResp.Body.Close()

	var resp BrainCResponse
	if err := json.NewDecoder(httpResp.Body).Decode(&resp); err != nil {
		return nil, err
	}

	// Update latency tracking
	latencyMs := float64(time.Since(start).Milliseconds())
	c.mu.Lock()
	c.avgLatencyMs = c.avgLatencyMs*0.9 + latencyMs*0.1
	c.mu.Unlock()

	return &resp, nil
}

// ─────────────────────────────────────────────────
// RESPONSE → DECISION CONVERSION
// ─────────────────────────────────────────────────

func (c *BrainC) responseToDecision(resp *BrainCResponse) *Decision {
	if resp == nil {
		return nil
	}

	actionType := parseActionTypeFromString(resp.ActionClass)

	// Build reasoning string
	reasoning := resp.Action
	if resp.AnalogySource != "" {
		reasoning += " [analogy: " + resp.AnalogySource + "]"
	}

	return &Decision{
		ID:            fmt.Sprintf("brainC_%d", time.Now().UnixNano()%100000),
		Timestamp:     time.Now(),
		Confidence:    resp.Confidence,
		ExpectedValue: resp.Confidence * 0.75,
		Reasoning:     append([]string{"[BrainC] " + reasoning}, resp.ReasoningChain...),
		Action: Action{
			Type:       actionType,
			Target:     resp.Action,
			Parameters: map[string]string{
				"action_class":  resp.ActionClass,
				"requires_owner": fmt.Sprintf("%v", resp.RequiresOwner),
				"token_valid":   fmt.Sprintf("%v", resp.TokenValid),
			},
			Priority:   int(resp.Confidence * 10),
			Reversible: resp.ActionClass == "think" || resp.ActionClass == "observe",
		},
	}
}

// ─────────────────────────────────────────────────
// HEALTH TRACKING
// ─────────────────────────────────────────────────

func (c *BrainC) recordSuccess(resp *BrainCResponse) {
	c.successCalls.Add(1)
	c.consecutiveFails.Store(0)
	c.online.Store(true)

	c.lastDecisionMu.Lock()
	c.lastDecision = resp
	c.lastDecisionMu.Unlock()
}

func (c *BrainC) recordFailure() {
	fails := c.consecutiveFails.Add(1)
	if fails >= brainCMaxFails {
		c.online.Store(false)
	}
}

func (c *BrainC) healthMonitor() {
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-c.ctx.Done():
			return
		case <-ticker.C:
			c.pingHealth()
		}
	}
}

func (c *BrainC) pingHealth() {
	ctx, cancel := context.WithTimeout(c.ctx, 500*time.Millisecond)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, "GET", c.addr+brainCHealthPath, nil)
	if err != nil {
		return
	}

	resp, err := c.client.Do(req)
	if err != nil {
		// Brain C unreachable — try to restart sidecar
		if c.online.Load() {
			fmt.Println("[BrainC] Health check failed — marking offline")
			c.online.Store(false)
		}
		if !c.sidecarRunning.Load() {
			go c.startSidecar()
		}
		return
	}
	resp.Body.Close()

	if !c.online.Load() {
		fmt.Println("[BrainC] Back online")
	}
	c.online.Store(true)
	c.consecutiveFails.Store(0)
}

// ─────────────────────────────────────────────────
// SIDECAR PROCESS MANAGEMENT
// ─────────────────────────────────────────────────

func (c *BrainC) startSidecar() {
	if c.sidecarRunning.Load() {
		return
	}

	// Find the brain_c server script
	serverScript := filepath.Join(c.projectRoot, "python", "consciousness", "brain_c_server.py")
	if _, err := os.Stat(serverScript); os.IsNotExist(err) {
		fmt.Printf("[BrainC] Sidecar script not found at %s\n", serverScript)
		return
	}

	python := "python3"
	if p := os.Getenv("ULTRON_PYTHON"); p != "" {
		python = p
	}

	dataDir := filepath.Join(c.projectRoot, "data", "brain_c")
	cmd := exec.CommandContext(c.ctx, python, serverScript,
		"--port", "50070",
		"--data-dir", dataDir,
	)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Env = append(os.Environ(),
		"ULTRON_DATA_DIR="+dataDir,
		"PYTHONUNBUFFERED=1",
	)

	c.mu.Lock()
	c.sidecarCmd = cmd
	c.mu.Unlock()

	c.sidecarRunning.Store(true)
	fmt.Printf("[BrainC] Starting sidecar: %s %s\n", python, serverScript)

	if err := cmd.Start(); err != nil {
		fmt.Printf("[BrainC] Failed to start sidecar: %v\n", err)
		c.sidecarRunning.Store(false)
		return
	}

	// Wait a moment for the server to be ready
	time.Sleep(2 * time.Second)
	c.pingHealth()

	// Monitor for exit
	go func() {
		_ = cmd.Wait()
		c.sidecarRunning.Store(false)
		c.online.Store(false)
		fmt.Println("[BrainC] Sidecar exited — will restart on next health check")

		// Auto-restart after delay
		select {
		case <-c.ctx.Done():
		case <-time.After(brainCRetryDelay):
			go c.startSidecar()
		}
	}()
}

// ─────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────

func findProjectRoot() string {
	// Walk up from cwd looking for go.mod
	dir, _ := os.Getwd()
	for i := 0; i < 10; i++ {
		if _, err := os.Stat(filepath.Join(dir, "go.mod")); err == nil {
			// go.mod found — project root is the parent of go/
			return filepath.Dir(filepath.Dir(dir))
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	return "."
}
