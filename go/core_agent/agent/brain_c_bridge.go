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
	client *http.Client
	logger *zap.Logger
}

func NewBrainC(logger *zap.Logger) *BrainC {
	return &BrainC{
		client: &http.Client{
			Timeout: brainCTimeout,
		},
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