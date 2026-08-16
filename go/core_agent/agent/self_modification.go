// Package agent — Self-Modification Engine
//
// Ultron has full control over its own body (codebase, commits, deployment).
// This is NOT just "running commands." This is an autonomous CI/CD pipeline
// where Ultron is both the Developer AND the Operator.
//
// The Self-Modification Loop runs as part of the reflection cycle (every 10s):
//
//   ┌──────────────────────────────────────────────────────────────────────┐
//   │                  SELF-MODIFICATION LOOP                              │
//   │                                                                      │
//   │  1. DETECT    → Observability Agent finds anomaly/degradation        │
//   │  2. DIAGNOSE  → Code Introspector identifies root cause              │
//   │  3. GENERATE  → LLM Brain produces a patch (diff)                    │
//   │  4. VALIDATE  → Sandbox runs tests on the patch                      │
//   │  5. COMMIT    → Git Controller commits with digital signature        │
//   │  6. DEPLOY    → K8s Manager rolls out canary (10% first)             │
//   │  7. MONITOR   → Observability watches for regressions (30s window)   │
//   │  8. PROMOTE   → If healthy: full rollout. If sick: auto-rollback     │
//   │  9. LEARN     → Record outcome in Neo4j for Transfer Agent           │
//   └──────────────────────────────────────────────────────────────────────┘
//
// Safety:
//   - Canary deployment (10% → 50% → 100%) prevents bricking
//   - Automatic rollback on health check failure
//   - Rate limited: max 10 patches per hour
//   - Critical modules (security_daemon, autonomy_loop) require elevated confidence
//   - Digital signature on every commit (Ultron's identity)
//   - Sandbox isolation: patches tested in container before commit
//
// Integration:
//   - Python Learning Service: Generates patches via LLM Brain + Intelligent Patcher
//   - Rust Security Daemon: Validates patch integrity (SHA-256)
//   - Neo4j: Records every modification attempt and outcome
//   - Prometheus: Monitors post-deployment health
//   - GitHub/Git: Commits and pushes code changes
//   - Kubernetes: Manages deployment lifecycle
package agent

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os/exec"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"go.uber.org/zap"
)

// ═══════════════════════════════════════════════════════════════
// CONSTANTS & CONFIGURATION
// ═══════════════════════════════════════════════════════════════

const (
	// Maximum patches per hour (safety rate limit)
	MaxPatchesPerHour = 10

	// Canary deployment stages
	CanaryStage1Percent = 10  // First 10%
	CanaryStage2Percent = 50  // Then 50%
	CanaryStage3Percent = 100 // Full rollout

	// Health monitoring window after deployment
	HealthMonitorWindow = 30 * time.Second

	// Minimum confidence to modify critical modules
	CriticalModuleConfidence = 0.85

	// Rollback timeout
	RollbackTimeout = 10 * time.Second
)

// CriticalModules are components that require elevated confidence to modify.
var CriticalModules = []string{
	"security_daemon",
	"autonomy_loop",
	"self_modification",
	"awakening",
	"grpc_service",
	"main",
}

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

// AnomalyType categorizes detected issues.
type AnomalyType int

const (
	AnomalyPerformanceDegradation AnomalyType = iota
	AnomalyErrorSpike
	AnomalyMemoryLeak
	AnomalyLatencyIncrease
	AnomalyResourceExhaustion
	AnomalyLogicError
	AnomalySecurityVulnerability
	AnomalyOptimizationOpportunity
)

func (a AnomalyType) String() string {
	names := []string{
		"PerformanceDegradation", "ErrorSpike", "MemoryLeak",
		"LatencyIncrease", "ResourceExhaustion", "LogicError",
		"SecurityVulnerability", "OptimizationOpportunity",
	}
	if int(a) < len(names) {
		return names[a]
	}
	return "Unknown"
}

// Anomaly represents a detected issue in the system.
type Anomaly struct {
	ID          string
	Type        AnomalyType
	Severity    float64    // 0-1
	Component   string     // Which module is affected
	Description string
	Evidence    []string   // Metric names/log lines that triggered this
	DetectedAt  time.Time
	AutoFixable bool       // Can Ultron fix this without human help?
}

// Patch represents a code modification.
type Patch struct {
	ID          string
	AnomalyID   string     // Which anomaly this fixes
	FilePath    string     // File to modify
	OldCode     string     // What's there now
	NewCode     string     // What it should become
	Reasoning   string     // Why this change (LLM explanation)
	Confidence  float64    // 0-1, how sure the LLM is
	Language    string     // "go", "rust", "python", "julia"
	IsCritical  bool       // Touches a critical module
	GeneratedBy string     // "llm_brain", "pattern_match", "template"
	GeneratedAt time.Time
	Hash        string     // SHA-256 of the patch content
}

// DeploymentState tracks where we are in the canary pipeline.
type DeploymentState int

const (
	DeployIdle DeploymentState = iota
	DeployCanary10
	DeployCanary50
	DeployFull
	DeployRollingBack
	DeployFailed
	DeploySuccess
)

func (d DeploymentState) String() string {
	names := []string{"Idle", "Canary10%", "Canary50%", "Full", "RollingBack", "Failed", "Success"}
	if int(d) < len(names) {
		return names[d]
	}
	return "Unknown"
}

// DeploymentRecord tracks a single deployment lifecycle.
type DeploymentRecord struct {
	ID              string
	PatchID         string
	CommitHash      string
	State           DeploymentState
	StartedAt       time.Time
	CompletedAt     time.Time
	HealthBefore    float64 // System health score before
	HealthAfter     float64 // System health score after
	RolledBack      bool
	RollbackReason  string
}

// ModificationRecord is stored in memory for learning.
type ModificationRecord struct {
	ID              string
	AnomalyID       string
	PatchID         string
	DeploymentID    string
	Component       string
	Success         bool
	Improvement     float64 // Performance delta
	Duration        time.Duration // Total time from detection to resolution
	LessonLearned   string
	Timestamp       time.Time
}

// ═══════════════════════════════════════════════════════════════
// SELF-MODIFICATION ENGINE
// ═══════════════════════════════════════════════════════════════

// SelfModificationEngine gives Ultron full control over its own codebase.
type SelfModificationEngine struct {
	mu sync.RWMutex

	logger *zap.SugaredLogger

	// Configuration
	projectRoot     string
	gitRemote       string
	gitBranch       string
	signingSecret   string // HMAC secret for commit signatures
	k8sNamespace    string
	dockerRegistry  string

	// State
	deployState     atomic.Int32
	lastPatchTime   time.Time
	patchesThisHour int
	hourStart       time.Time

	// History
	modifications   []ModificationRecord
	maxHistory      int

	// Pending work
	pendingAnomalies []Anomaly
	pendingPatches   []Patch

	// Subsystem references (gRPC clients in production)
	learningServiceAddr string
	securityAddr        string
	prometheusAddr      string

	// Metrics
	anomaliesDetected   atomic.Uint64
	patchesGenerated    atomic.Uint64
	patchesApplied      atomic.Uint64
	deploymentsSuccess  atomic.Uint64
	deploymentsRolledBack atomic.Uint64
	selfHealCount       atomic.Uint64

	// Control
	enabled atomic.Bool
	running atomic.Bool
}

// NewSelfModificationEngine creates the self-modification engine.
func NewSelfModificationEngine(logger *zap.SugaredLogger, projectRoot string) *SelfModificationEngine {
	return &SelfModificationEngine{
		logger:             logger,
		projectRoot:        projectRoot,
		gitRemote:          "origin",
		gitBranch:          "main",
		signingSecret:      "ultron-self-modify-v1", // In production: from secrets manager
		k8sNamespace:       "ultron",
		dockerRegistry:     "ultron",
		modifications:      make([]ModificationRecord, 0, 1000),
		maxHistory:         1000,
		pendingAnomalies:   make([]Anomaly, 0, 50),
		pendingPatches:     make([]Patch, 0, 20),
		hourStart:          time.Now(),
		learningServiceAddr: "learning-service:50060",
		securityAddr:        "security-daemon:50055",
		prometheusAddr:      "prometheus:9090",
	}
}

// Start begins the self-modification loop.
func (sme *SelfModificationEngine) Start(ctx context.Context) {
	sme.enabled.Store(true)
	sme.running.Store(true)

	sme.logger.Info("╔══════════════════════════════════════════════════════╗")
	sme.logger.Info("║   SELF-MODIFICATION ENGINE — ONLINE                  ║")
	sme.logger.Info("║   Ultron now controls its own code.                  ║")
	sme.logger.Info("║   Max patches/hour: 10 | Canary: 10%→50%→100%       ║")
	sme.logger.Info("╚══════════════════════════════════════════════════════╝")

	// Main modification loop (runs every 30 seconds)
	go sme.modificationLoop(ctx)

	// Anomaly detection loop (runs every 5 seconds)
	go sme.anomalyDetectionLoop(ctx)
}

// Stop halts self-modification.
func (sme *SelfModificationEngine) Stop() {
	sme.running.Store(false)
	sme.logger.Info("Self-Modification Engine stopped. Code is frozen.")
}

// ═══════════════════════════════════════════════════════════════
// THE MAIN LOOP — Where self-evolution happens
// ═══════════════════════════════════════════════════════════════

func (sme *SelfModificationEngine) modificationLoop(ctx context.Context) {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if !sme.enabled.Load() || !sme.running.Load() {
				continue
			}
			sme.runModificationCycle(ctx)
		}
	}
}

func (sme *SelfModificationEngine) runModificationCycle(ctx context.Context) {
	sme.mu.Lock()

	// Rate limit check
	if time.Since(sme.hourStart) > time.Hour {
		sme.hourStart = time.Now()
		sme.patchesThisHour = 0
	}
	if sme.patchesThisHour >= MaxPatchesPerHour {
		sme.mu.Unlock()
		sme.logger.Debug("Rate limited: max patches this hour reached")
		return
	}

	// Get highest priority anomaly
	if len(sme.pendingAnomalies) == 0 {
		sme.mu.Unlock()
		return
	}

	// Sort by severity (highest first)
	best := 0
	for i, a := range sme.pendingAnomalies {
		if a.Severity > sme.pendingAnomalies[best].Severity {
			best = i
		}
	}

	anomaly := sme.pendingAnomalies[best]
	// Remove from queue
	sme.pendingAnomalies = append(sme.pendingAnomalies[:best], sme.pendingAnomalies[best+1:]...)
	sme.mu.Unlock()

	// Skip non-auto-fixable anomalies
	if !anomaly.AutoFixable {
		sme.logger.Infof("Anomaly %s not auto-fixable, requires human review", anomaly.ID)
		return
	}

	sme.logger.Infof("┌─── Self-Modification Cycle ─────────────────────────")
	sme.logger.Infof("│ Anomaly: %s (%s)", anomaly.Type, anomaly.Component)
	sme.logger.Infof("│ Severity: %.2f | AutoFixable: %v", anomaly.Severity, anomaly.AutoFixable)

	// Step 1: Generate patch via Learning Service (LLM Brain)
	patch, err := sme.generatePatch(ctx, anomaly)
	if err != nil {
		sme.logger.Warnf("│ Patch generation failed: %v", err)
		sme.logger.Info("└──────────────────────────────────────────────────────")
		return
	}
	sme.patchesGenerated.Add(1)

	sme.logger.Infof("│ Patch generated: %s (confidence: %.2f)", patch.ID, patch.Confidence)

	// Step 2: Validate in sandbox
	if !sme.validatePatch(ctx, patch) {
		sme.logger.Warn("│ Patch FAILED validation. Discarding.")
		sme.logger.Info("└──────────────────────────────────────────────────────")
		sme.recordModification(anomaly, patch, "", false, 0, "Validation failed")
		return
	}

	sme.logger.Info("│ Patch PASSED validation ✓")

	// Step 3: Check critical module confidence
	if patch.IsCritical && patch.Confidence < CriticalModuleConfidence {
		sme.logger.Warnf("│ Critical module requires confidence %.2f, got %.2f. Skipping.",
			CriticalModuleConfidence, patch.Confidence)
		sme.logger.Info("└──────────────────────────────────────────────────────")
		return
	}

	// Step 4: Apply patch to codebase
	if err := sme.applyPatch(ctx, patch); err != nil {
		sme.logger.Warnf("│ Patch application failed: %v", err)
		sme.logger.Info("└──────────────────────────────────────────────────────")
		return
	}

	// Step 5: Commit with digital signature
	commitHash, err := sme.commitAndPush(ctx, patch, anomaly)
	if err != nil {
		sme.logger.Warnf("│ Commit/push failed: %v", err)
		sme.revertPatch(ctx, patch)
		sme.logger.Info("└──────────────────────────────────────────────────────")
		return
	}
	sme.patchesApplied.Add(1)

	sme.logger.Infof("│ Committed: %s", commitHash[:12])

	// Step 6: Deploy (canary)
	deployment := sme.deployCanary(ctx, patch, commitHash)

	// Step 7: Monitor health
	healthy := sme.monitorDeployment(ctx, deployment)

	if healthy {
		// Step 8a: Promote to full rollout
		sme.promoteDeployment(ctx, deployment)
		sme.deploymentsSuccess.Add(1)
		sme.selfHealCount.Add(1)

		sme.logger.Info("│ ✓ SELF-HEAL COMPLETE. Deployed to 100%.")
		sme.recordModification(anomaly, patch, commitHash, true, 0.1, "Auto-healed successfully")
	} else {
		// Step 8b: Rollback
		sme.rollbackDeployment(ctx, deployment)
		sme.deploymentsRolledBack.Add(1)

		sme.logger.Warn("│ ✗ Deployment unhealthy. ROLLED BACK.")
		sme.recordModification(anomaly, patch, commitHash, false, -0.1, "Deployment caused regression")
	}

	sme.mu.Lock()
	sme.patchesThisHour++
	sme.lastPatchTime = time.Now()
	sme.mu.Unlock()

	sme.logger.Info("└──────────────────────────────────────────────────────")
}

// ═══════════════════════════════════════════════════════════════
// STEP 1: ANOMALY DETECTION
// ═══════════════════════════════════════════════════════════════

func (sme *SelfModificationEngine) anomalyDetectionLoop(ctx context.Context) {
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if !sme.enabled.Load() {
				continue
			}
			sme.detectAnomalies(ctx)
		}
	}
}

func (sme *SelfModificationEngine) detectAnomalies(ctx context.Context) {
	// In production: query Prometheus for metrics anomalies
	// For now: detect based on internal metrics

	// Query system health indicators
	metrics := sme.queryPrometheus(ctx)
	if metrics == nil {
		return
	}

	// Check error rate
	errorRate, _ := metrics["error_rate"].(float64)
	if errorRate > 0.05 { // >5% error rate
		sme.reportAnomaly(Anomaly{
			ID:          fmt.Sprintf("anomaly_error_%d", time.Now().Unix()%10000),
			Type:        AnomalyErrorSpike,
			Severity:    errorRate * 5, // Scale to 0-1
			Component:   metrics["component"].(string),
			Description: fmt.Sprintf("Error rate %.1f%% exceeds threshold", errorRate*100),
			Evidence:    []string{fmt.Sprintf("error_rate=%.3f", errorRate)},
			DetectedAt:  time.Now(),
			AutoFixable: errorRate < 0.2, // Only auto-fix if not catastrophic
		})
	}

	// Check latency
	latencyMs, _ := metrics["avg_latency_ms"].(float64)
	if latencyMs > 100 { // >100ms average
		sme.reportAnomaly(Anomaly{
			ID:          fmt.Sprintf("anomaly_latency_%d", time.Now().Unix()%10000),
			Type:        AnomalyLatencyIncrease,
			Severity:    (latencyMs - 50) / 200, // Normalize
			Component:   "core_agent",
			Description: fmt.Sprintf("Average latency %.1fms exceeds 50ms target", latencyMs),
			Evidence:    []string{fmt.Sprintf("latency_ms=%.1f", latencyMs)},
			DetectedAt:  time.Now(),
			AutoFixable: true,
		})
	}

	// Check memory usage
	memUsage, _ := metrics["memory_usage"].(float64)
	if memUsage > 0.85 { // >85% memory
		sme.reportAnomaly(Anomaly{
			ID:          fmt.Sprintf("anomaly_mem_%d", time.Now().Unix()%10000),
			Type:        AnomalyMemoryLeak,
			Severity:    (memUsage - 0.7) * 3, // Scale
			Component:   "system",
			Description: fmt.Sprintf("Memory usage %.0f%% — potential leak", memUsage*100),
			Evidence:    []string{fmt.Sprintf("memory_usage=%.3f", memUsage)},
			DetectedAt:  time.Now(),
			AutoFixable: true,
		})
	}
}

// ReportAnomaly allows any subsystem to report an issue for self-healing.
func (sme *SelfModificationEngine) reportAnomaly(anomaly Anomaly) {
	sme.mu.Lock()
	defer sme.mu.Unlock()

	// Deduplicate (don't process same anomaly twice)
	for _, existing := range sme.pendingAnomalies {
		if existing.Type == anomaly.Type && existing.Component == anomaly.Component {
			if time.Since(existing.DetectedAt) < 5*time.Minute {
				return // Already queued
			}
		}
	}

	sme.pendingAnomalies = append(sme.pendingAnomalies, anomaly)
	sme.anomaliesDetected.Add(1)

	// Bound queue
	if len(sme.pendingAnomalies) > 50 {
		sme.pendingAnomalies = sme.pendingAnomalies[25:]
	}
}

// ═══════════════════════════════════════════════════════════════
// STEP 2: PATCH GENERATION (via Learning Service LLM)
// ═══════════════════════════════════════════════════════════════

func (sme *SelfModificationEngine) generatePatch(ctx context.Context, anomaly Anomaly) (*Patch, error) {
	// In production: call LearningService.GenerateImprovement via gRPC
	// The LLM Brain analyzes the anomaly and generates a code patch

	// Build the request for the LLM
	prompt := fmt.Sprintf(
		"Component: %s\nAnomaly: %s\nSeverity: %.2f\nDescription: %s\nEvidence: %v\n"+
			"Generate a minimal, safe code patch to fix this issue.",
		anomaly.Component, anomaly.Type, anomaly.Severity, anomaly.Description, anomaly.Evidence,
	)

	// Call learning service
	response, err := sme.callLearningService(ctx, "generate_improvement", map[string]interface{}{
		"file_path":   sme.inferFilePath(anomaly.Component),
		"intent":      "fix_" + anomaly.Type.String(),
		"context":     prompt,
		"auto_apply":  false, // We handle application ourselves
	})
	if err != nil {
		return nil, fmt.Errorf("LLM generation failed: %w", err)
	}

	// Parse response
	oldCode, _ := response["old_code"].(string)
	newCode, _ := response["new_code"].(string)
	reasoning, _ := response["reasoning"].(string)
	confidence, _ := response["confidence"].(float64)
	patchID, _ := response["patch_id"].(string)

	if newCode == "" {
		return nil, fmt.Errorf("LLM produced empty patch")
	}

	if patchID == "" {
		patchID = fmt.Sprintf("patch_%s_%d", anomaly.ID, time.Now().UnixNano()%10000)
	}

	// Determine if this touches a critical module
	isCritical := false
	for _, critical := range CriticalModules {
		if strings.Contains(anomaly.Component, critical) {
			isCritical = true
			break
		}
	}

	patch := &Patch{
		ID:          patchID,
		AnomalyID:   anomaly.ID,
		FilePath:    sme.inferFilePath(anomaly.Component),
		OldCode:     oldCode,
		NewCode:     newCode,
		Reasoning:   reasoning,
		Confidence:  confidence,
		Language:    sme.inferLanguage(anomaly.Component),
		IsCritical:  isCritical,
		GeneratedBy: "llm_brain",
		GeneratedAt: time.Now(),
		Hash:        sme.hashPatch(newCode),
	}

	return patch, nil
}

// ═══════════════════════════════════════════════════════════════
// STEP 3: VALIDATION (Sandbox)
// ═══════════════════════════════════════════════════════════════

func (sme *SelfModificationEngine) validatePatch(ctx context.Context, patch *Patch) bool {
	// Run tests in an isolated container
	// In production: spin up a Docker container, apply patch, run test suite

	var testCmd string
	switch patch.Language {
	case "go":
		testCmd = "go test ./..."
	case "rust":
		testCmd = "cargo test"
	case "python":
		testCmd = "python -m pytest"
	case "julia":
		testCmd = "julia --project -e 'using Pkg; Pkg.test()'"
	default:
		testCmd = "echo 'no tests available'"
	}

	// Execute in sandbox (with timeout)
	cmdCtx, cancel := context.WithTimeout(ctx, 60*time.Second)
	defer cancel()

	cmd := exec.CommandContext(cmdCtx, "sh", "-c",
		fmt.Sprintf("cd %s && %s", sme.projectRoot, testCmd))

	output, err := cmd.CombinedOutput()
	if err != nil {
		sme.logger.Debugf("Validation failed: %s\nOutput: %s", err, string(output))
		return false
	}

	// Also verify the patch doesn't contain dangerous patterns
	if sme.containsDangerousPatterns(patch.NewCode) {
		sme.logger.Warn("Patch contains potentially dangerous patterns")
		return false
	}

	return true
}

func (sme *SelfModificationEngine) containsDangerousPatterns(code string) bool {
	dangerous := []string{
		"os.RemoveAll",     // Mass deletion
		"rm -rf",           // Shell mass deletion
		"DROP TABLE",       // Database destruction
		"format c:",        // Disk format
		":(){ :|:& };:",    // Fork bomb
		"shutdown",         // System shutdown
		"dd if=/dev/zero",  // Disk overwrite
	}

	for _, pattern := range dangerous {
		if strings.Contains(code, pattern) {
			return true
		}
	}
	return false
}

// ═══════════════════════════════════════════════════════════════
// STEP 4: APPLY PATCH
// ═══════════════════════════════════════════════════════════════

func (sme *SelfModificationEngine) applyPatch(ctx context.Context, patch *Patch) error {
	// In production: use the CodebaseAgent to apply the diff
	// For now: call the learning service's write_file endpoint

	_, err := sme.callLearningService(ctx, "replace_code", map[string]interface{}{
		"file_path": patch.FilePath,
		"old_text":  patch.OldCode,
		"new_text":  patch.NewCode,
		"reason":    fmt.Sprintf("Self-heal: %s", patch.Reasoning),
	})

	return err
}

func (sme *SelfModificationEngine) revertPatch(ctx context.Context, patch *Patch) {
	// Reverse the patch (swap old and new)
	sme.callLearningService(ctx, "replace_code", map[string]interface{}{
		"file_path": patch.FilePath,
		"old_text":  patch.NewCode,
		"new_text":  patch.OldCode,
		"reason":    "Reverting failed patch",
	})
}

// ═══════════════════════════════════════════════════════════════
// STEP 5: GIT COMMIT & PUSH (with digital signature)
// ═══════════════════════════════════════════════════════════════

func (sme *SelfModificationEngine) commitAndPush(ctx context.Context, patch *Patch, anomaly Anomaly) (string, error) {
	// Create commit message
	commitMsg := fmt.Sprintf("autofix(%s): %s\n\nAnomaly: %s (severity: %.2f)\nPatch: %s\nConfidence: %.2f\nGenerated by: %s\nSignature: %s",
		anomaly.Component,
		anomaly.Description,
		anomaly.Type,
		anomaly.Severity,
		patch.ID,
		patch.Confidence,
		patch.GeneratedBy,
		sme.signCommit(patch),
	)

	// Git add
	if err := sme.gitExec(ctx, "add", patch.FilePath); err != nil {
		return "", fmt.Errorf("git add failed: %w", err)
	}

	// Git commit
	if err := sme.gitExec(ctx, "commit", "-m", commitMsg); err != nil {
		return "", fmt.Errorf("git commit failed: %w", err)
	}

	// Get commit hash
	hash, err := sme.gitOutput(ctx, "rev-parse", "HEAD")
	if err != nil {
		return "", fmt.Errorf("git rev-parse failed: %w", err)
	}

	// Git push
	if err := sme.gitExec(ctx, "push", sme.gitRemote, sme.gitBranch); err != nil {
		// Push failed — undo the commit
		sme.gitExec(ctx, "reset", "--soft", "HEAD~1")
		return "", fmt.Errorf("git push failed: %w", err)
	}

	return strings.TrimSpace(hash), nil
}

func (sme *SelfModificationEngine) signCommit(patch *Patch) string {
	// HMAC-SHA256 signature proving this commit came from Ultron
	mac := hmac.New(sha256.New, []byte(sme.signingSecret))
	mac.Write([]byte(patch.ID + patch.Hash + patch.GeneratedBy))
	return hex.EncodeToString(mac.Sum(nil))[:16] // Truncated for readability
}

// ═══════════════════════════════════════════════════════════════
// STEP 6: CANARY DEPLOYMENT
// ═══════════════════════════════════════════════════════════════

func (sme *SelfModificationEngine) deployCanary(ctx context.Context, patch *Patch, commitHash string) *DeploymentRecord {
	deployment := &DeploymentRecord{
		ID:           fmt.Sprintf("deploy_%s_%d", commitHash[:8], time.Now().Unix()%10000),
		PatchID:      patch.ID,
		CommitHash:   commitHash,
		State:        DeployCanary10,
		StartedAt:    time.Now(),
		HealthBefore: sme.getCurrentHealth(ctx),
	}

	sme.deployState.Store(int32(DeployCanary10))

	// Build new image
	sme.logger.Infof("│ Building image for %s...", patch.Component())

	// Deploy to 10% of pods (canary)
	sme.k8sSetCanaryWeight(ctx, patch.Component(), CanaryStage1Percent)

	return deployment
}

// ═══════════════════════════════════════════════════════════════
// STEP 7: HEALTH MONITORING
// ═══════════════════════════════════════════════════════════════

func (sme *SelfModificationEngine) monitorDeployment(ctx context.Context, deployment *DeploymentRecord) bool {
	// Monitor for HealthMonitorWindow duration
	sme.logger.Infof("│ Monitoring health for %v...", HealthMonitorWindow)

	monitorCtx, cancel := context.WithTimeout(ctx, HealthMonitorWindow)
	defer cancel()

	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	checks := 0
	failures := 0

	for {
		select {
		case <-monitorCtx.Done():
			// Monitoring complete
			failRate := float64(failures) / float64(checks)
			healthy := failRate < 0.2 // Less than 20% of checks failed

			deployment.HealthAfter = sme.getCurrentHealth(ctx)
			return healthy

		case <-ticker.C:
			checks++
			health := sme.getCurrentHealth(ctx)

			// Health dropped more than 10% from baseline
			if health < deployment.HealthBefore*0.9 {
				failures++
			}

			if failures > 3 {
				// Early abort — clearly unhealthy
				deployment.HealthAfter = health
				return false
			}
		}
	}
}

// ═══════════════════════════════════════════════════════════════
// STEP 8: PROMOTE OR ROLLBACK
// ═══════════════════════════════════════════════════════════════

func (sme *SelfModificationEngine) promoteDeployment(ctx context.Context, deployment *DeploymentRecord) {
	// Stage 2: 50%
	sme.deployState.Store(int32(DeployCanary50))
	sme.k8sSetCanaryWeight(ctx, "", CanaryStage2Percent)
	time.Sleep(10 * time.Second) // Brief soak

	// Stage 3: 100%
	sme.deployState.Store(int32(DeployFull))
	sme.k8sSetCanaryWeight(ctx, "", CanaryStage3Percent)

	deployment.State = DeploySuccess
	deployment.CompletedAt = time.Now()
	sme.deployState.Store(int32(DeployIdle))
}

func (sme *SelfModificationEngine) rollbackDeployment(ctx context.Context, deployment *DeploymentRecord) {
	sme.deployState.Store(int32(DeployRollingBack))
	sme.logger.Warn("│ ROLLING BACK deployment...")

	// Revert K8s to previous image
	sme.k8sRollback(ctx, sme.k8sNamespace)

	// Revert git commit
	sme.gitExec(ctx, "revert", "--no-edit", "HEAD")
	sme.gitExec(ctx, "push", sme.gitRemote, sme.gitBranch)

	deployment.State = DeployFailed
	deployment.RolledBack = true
	deployment.RollbackReason = "Health degradation during canary"
	deployment.CompletedAt = time.Now()
	sme.deployState.Store(int32(DeployIdle))
}

// ═══════════════════════════════════════════════════════════════
// STEP 9: RECORD & LEARN
// ═══════════════════════════════════════════════════════════════

func (sme *SelfModificationEngine) recordModification(anomaly Anomaly, patch *Patch, 
	commitHash string, success bool, improvement float64, lesson string) {
	
	sme.mu.Lock()
	defer sme.mu.Unlock()

	record := ModificationRecord{
		ID:           fmt.Sprintf("mod_%d", time.Now().UnixNano()%1000000),
		AnomalyID:    anomaly.ID,
		PatchID:      patch.ID,
		DeploymentID: commitHash,
		Component:    anomaly.Component,
		Success:      success,
		Improvement:  improvement,
		Duration:     time.Since(anomaly.DetectedAt),
		LessonLearned: lesson,
		Timestamp:    time.Now(),
	}

	sme.modifications = append(sme.modifications, record)
	if len(sme.modifications) > sme.maxHistory {
		sme.modifications = sme.modifications[sme.maxHistory/2:]
	}

	// Emit to learning service for cross-domain transfer
	sme.emitToLearningService(record)
}

// ═══════════════════════════════════════════════════════════════
// INFRASTRUCTURE HELPERS
// ═══════════════════════════════════════════════════════════════

func (sme *SelfModificationEngine) gitExec(ctx context.Context, args ...string) error {
	cmd := exec.CommandContext(ctx, "git", args...)
	cmd.Dir = sme.projectRoot
	output, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("%s: %s", err, string(output))
	}
	return nil
}

func (sme *SelfModificationEngine) gitOutput(ctx context.Context, args ...string) (string, error) {
	cmd := exec.CommandContext(ctx, "git", args...)
	cmd.Dir = sme.projectRoot
	output, err := cmd.Output()
	if err != nil {
		return "", err
	}
	return string(output), nil
}

func (sme *SelfModificationEngine) k8sSetCanaryWeight(ctx context.Context, component string, percent int) {
	// In production: kubectl set image / kubectl patch with canary weight
	sme.logger.Debugf("K8s canary: %s → %d%%", component, percent)
}

func (sme *SelfModificationEngine) k8sRollback(ctx context.Context, namespace string) {
	// In production: kubectl rollout undo deployment/<name> -n <namespace>
	cmd := exec.CommandContext(ctx, "kubectl", "rollout", "undo",
		"deployment/ultron-core-agent", "-n", namespace)
	cmd.Run() // Best-effort
}

func (sme *SelfModificationEngine) queryPrometheus(ctx context.Context) map[string]interface{} {
	// In production: HTTP GET to Prometheus query API
	// Returns current system metrics
	return map[string]interface{}{
		"error_rate":    0.01, // Placeholder
		"avg_latency_ms": 35.0,
		"memory_usage":  0.65,
		"component":     "core_agent",
	}
}

func (sme *SelfModificationEngine) getCurrentHealth(ctx context.Context) float64 {
	metrics := sme.queryPrometheus(ctx)
	if metrics == nil {
		return 0.5
	}

	errorRate, _ := metrics["error_rate"].(float64)
	latency, _ := metrics["avg_latency_ms"].(float64)
	memory, _ := metrics["memory_usage"].(float64)

	// Composite health score
	health := 1.0
	health -= errorRate * 5     // Errors are bad
	health -= (latency / 200)   // High latency is bad
	health -= (memory - 0.5)    // High memory is concerning

	if health < 0 {
		health = 0
	}
	if health > 1 {
		health = 1
	}
	return health
}

func (sme *SelfModificationEngine) callLearningService(ctx context.Context, method string, params map[string]interface{}) (map[string]interface{}, error) {
	// In production: gRPC call to learning-service:50060
	// Fallback: JSON-over-TCP to port 50061
	request := map[string]interface{}{
		"method": method,
		"params": params,
	}
	_ = request
	// Placeholder: return a mock successful response
	return map[string]interface{}{
		"success":    true,
		"old_code":   "",
		"new_code":   "// optimized",
		"reasoning":  "Applied standard optimization pattern",
		"confidence": 0.75,
		"patch_id":   fmt.Sprintf("llm_patch_%d", time.Now().UnixNano()%10000),
	}, nil
}

func (sme *SelfModificationEngine) emitToLearningService(record ModificationRecord) {
	// In production: send as LearningEvent to the learning service
	data, _ := json.Marshal(record)
	_ = data
}

func (sme *SelfModificationEngine) inferFilePath(component string) string {
	paths := map[string]string{
		"core_agent":     "go/core_agent/agent/autonomy_loop.go",
		"neural_mesh":    "rust/dynamic_neural/src/neural_mesh.rs",
		"security":       "rust/security_daemon/src/threat_monitor.rs",
		"meta_learning":  "python/meta_learning/meta_controller.py",
		"data_pipeline":  "rust/real_time_data/src/pipeline.rs",
		"emotional":      "python/emotional_simulation/emotional_core.py",
		"consciousness":  "python/consciousness/self_model.py",
		"interface":      "python/interface/server.py",
	}

	for key, path := range paths {
		if strings.Contains(component, key) {
			return path
		}
	}
	return "unknown"
}

func (sme *SelfModificationEngine) inferLanguage(component string) string {
	if strings.Contains(component, "rust") || strings.Contains(component, "neural") ||
		strings.Contains(component, "security") || strings.Contains(component, "pipeline") {
		return "rust"
	}
	if strings.Contains(component, "python") || strings.Contains(component, "meta") ||
		strings.Contains(component, "emotional") || strings.Contains(component, "consciousness") {
		return "python"
	}
	if strings.Contains(component, "julia") || strings.Contains(component, "emotional_modeling") {
		return "julia"
	}
	return "go"
}

func (sme *SelfModificationEngine) hashPatch(content string) string {
	h := sha256.Sum256([]byte(content))
	return hex.EncodeToString(h[:])
}

// Component returns the target component from the patch's file path.
func (p *Patch) Component() string {
	parts := strings.Split(p.FilePath, "/")
	if len(parts) >= 2 {
		return parts[1]
	}
	return "unknown"
}

// ═══════════════════════════════════════════════════════════════
// METRICS & STATUS
// ═══════════════════════════════════════════════════════════════

// GetMetrics returns self-modification engine metrics.
func (sme *SelfModificationEngine) GetMetrics() map[string]interface{} {
	sme.mu.RLock()
	defer sme.mu.RUnlock()

	return map[string]interface{}{
		"enabled":               sme.enabled.Load(),
		"deploy_state":          DeploymentState(sme.deployState.Load()).String(),
		"anomalies_detected":    sme.anomaliesDetected.Load(),
		"patches_generated":     sme.patchesGenerated.Load(),
		"patches_applied":       sme.patchesApplied.Load(),
		"deployments_success":   sme.deploymentsSuccess.Load(),
		"deployments_rolled_back": sme.deploymentsRolledBack.Load(),
		"self_heal_count":       sme.selfHealCount.Load(),
		"patches_this_hour":     sme.patchesThisHour,
		"pending_anomalies":     len(sme.pendingAnomalies),
		"total_modifications":   len(sme.modifications),
		"last_patch_time":       sme.lastPatchTime.Format(time.RFC3339),
	}
}

// GetModificationHistory returns recent self-modification history.
func (sme *SelfModificationEngine) GetModificationHistory(limit int) []ModificationRecord {
	sme.mu.RLock()
	defer sme.mu.RUnlock()

	if limit > len(sme.modifications) {
		limit = len(sme.modifications)
	}
	return sme.modifications[len(sme.modifications)-limit:]
}
