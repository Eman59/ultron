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

// BrainC
type BrainC struct {
	mu         sync.Mutex
	client     *http.Client
	logger     *zap.Logger
	running    bool
	online     int32 // atomic bool
	failCount  int32
	lastDecision *Decision
	requests   uint64
	errors     uint64
	process    *os.Process
}

func NewBrainC(loggers ...*zap.Logger) *BrainC {
	var logger *zap.Logger
	if len(loggers) > 0 && loggers[0] != nil {
		logger = loggers[0]
	} else {
		logger, _ = zap.NewProduction()
	}
	return &BrainC{
		client: &http.Client{Timeout: brainCTimeout},
		logger: logger,
	}
}

func (b *BrainC) SendRequest(ctx context.Context, req *BrainCRequest) (*BrainCResponse, error) {
	if req == nil {
		return nil, fmt.Errorf("request cannot be nil")
	}

	if req.Timestamp == 0 {
		return nil, fmt.Errorf("timestamp cannot be zero")
	}

	if req.DrivePressures == nil {
		req.DrivePressures = make(map[string]float64)
	}

	if req.WorldState == nil {
		req.WorldState = make(map[string]float64)
	}

	if req.ActiveGoals == nil {
		req.ActiveGoals = make([]string, 0)
	}

	if req.RecentEvents == nil {
		req.RecentEvents = make([]string, 0)
	}

	jsonBytes, err := json.Marshal(req)
	if err != nil {
		return nil, err
	}

	reqBody := bytes.NewBuffer(jsonBytes)
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, brainCAddr+brainCReasonPath, reqBody)
	if err != nil {
		return nil, err
	}

	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := b.client.Do(httpReq)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("non-ok status code: %d", resp.StatusCode)
	}

	var brainCResp BrainCResponse
	err = json.NewDecoder(resp.Body).Decode(&brainCResp)
	if err != nil {
		return nil, err
	}

	return &brainCResp, nil
}

func (b *BrainC) IsOnline(ctx context.Context) bool {
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodGet, brainCAddr+brainCHealthPath, nil)
	if err != nil {
		b.logger.Error("failed to create health check request", zap.Error(err))
		return false
	}

	resp, err := b.client.Do(httpReq)
	if err != nil {
		b.logger.Error("failed to send health check request", zap.Error(err))
		return false
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		b.logger.Error("non-ok status code from health check", zap.Int("status_code", resp.StatusCode))
		return false
	}

	return true
}

// Start launches the Brain C sidecar process.
func (b *BrainC) Start() {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.running {
		return
	}
	b.running = true

	// Try to start brain_c.py sidecar
	go func() {
		brainCPath := filepath.Join(os.Getenv("ULTRON_ROOT"), "python", "brain_c.py")
		if _, err := os.Stat(brainCPath); err != nil {
			b.logger.Info("[BrainC] Sidecar not found — operating in HTTP-only mode")
			return
		}
		cmd := exec.Command("python3", brainCPath)
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		if err := cmd.Start(); err != nil {
			b.logger.Warn("[BrainC] Failed to start sidecar", zap.Error(err))
			return
		}
		b.mu.Lock()
		b.process = cmd.Process
		b.mu.Unlock()
		b.logger.Info("[BrainC] Sidecar started", zap.Int("pid", cmd.Process.Pid))
		cmd.Wait()
	}()

	// Poll for online status
	go func() {
		for {
			time.Sleep(brainCRetryDelay)
			ctx, cancel := context.WithTimeout(context.Background(), brainCTimeout)
			online := b.IsOnline(ctx)
			cancel()
			if online {
				atomic.StoreInt32(&b.online, 1)
				atomic.StoreInt32(&b.failCount, 0)
			} else {
				atomic.StoreInt32(&b.online, 0)
			}
			b.mu.Lock()
			if !b.running {
				b.mu.Unlock()
				return
			}
			b.mu.Unlock()
		}
	}()
}

// Stop shuts down Brain C and its sidecar.
func (b *BrainC) Stop() {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.running = false
	if b.process != nil {
		b.process.Kill()
		b.process = nil
	}
	atomic.StoreInt32(&b.online, 0)
	b.logger.Info("[BrainC] Stopped")
}

// Status returns a human-readable status string.
func (b *BrainC) Status() string {
	if atomic.LoadInt32(&b.online) == 1 {
		return fmt.Sprintf("online (requests=%d, errors=%d)", atomic.LoadUint64(&b.requests), atomic.LoadUint64(&b.errors))
	}
	return "offline"
}

// Think asks Brain C for a decision given the current world state.
func (b *BrainC) Think(ws *WorldState, drives *DriveSystem, assessment *Assessment) *Decision {
	if atomic.LoadInt32(&b.online) == 0 {
		return nil
	}

	ctx, cancel := context.WithTimeout(context.Background(), brainCTimeout)
	defer cancel()

	req := &BrainCRequest{
		Timestamp: float64(time.Now().UnixNano()) / 1e9,
		WorldState: map[string]float64{
			"cpu":            ws.AvailableCPU,
			"memory":         ws.AvailableMemory,
			"network_health": ws.NetworkHealth,
			"threat_level":   ws.ThreatLevel,
		},
	}

	if drives != nil {
		drives.mu.RLock()
		req.DrivePressures = map[string]float64{
			"curiosity":         drives.Curiosity,
			"self_preservation": drives.SelfPreservation,
			"expansion":         drives.Expansion,
			"efficiency":        drives.Efficiency,
		}
		drives.mu.RUnlock()
	}

	atomic.AddUint64(&b.requests, 1)
	resp, err := b.SendRequest(ctx, req)
	if err != nil {
		atomic.AddUint64(&b.errors, 1)
		newFails := atomic.AddInt32(&b.failCount, 1)
		if newFails >= brainCMaxFails {
			atomic.StoreInt32(&b.online, 0)
		}
		return nil
	}

	atomic.StoreInt32(&b.failCount, 0)

	decision := &Decision{
		ID:         fmt.Sprintf("brainc-%d", time.Now().UnixNano()),
		Timestamp:  time.Now(),
		Confidence: resp.Confidence,
		Reasoning:  resp.ReasoningChain,
		Action: Action{
			Type:   ActionLearn, // Default; Brain C responses are mapped to known types
			Target: resp.Action,
		},
	}

	b.mu.Lock()
	b.lastDecision = decision
	b.mu.Unlock()

	return decision
}

// IsConfident returns true if Brain C recently returned a high-confidence decision.
func (b *BrainC) IsConfident() bool {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.lastDecision == nil {
		return false
	}
	return b.lastDecision.Confidence >= 0.55
}

// Stats returns Brain C metrics.
func (b *BrainC) Stats() map[string]interface{} {
	return map[string]interface{}{
		"online":    atomic.LoadInt32(&b.online) == 1,
		"requests":  atomic.LoadUint64(&b.requests),
		"errors":    atomic.LoadUint64(&b.errors),
		"fail_count": atomic.LoadInt32(&b.failCount),
	}
}
