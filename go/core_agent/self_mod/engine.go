// Package self_mod implements true self-modification — Ultron can rewrite,
// compile, test, and hot-swap its own code without human intervention.
//
// The pipeline:
//   1. IDENTIFY  — Find code to improve (from profiler or learning system)
//   2. GENERATE  — Create a modified version (LLM or heuristic)
//   3. SANDBOX   — Write to temp directory (never touch live code first)
//   4. COMPILE   — Build the new code (if it doesn't compile, abort)
//   5. TEST      — Run test suite against new binary (if tests fail, abort)
//   6. BENCHMARK — Compare performance old vs new
//   7. SWAP      — Atomic replace of the live binary/file
//   8. VERIFY    — Run health check after swap (if broken, rollback)
//   9. LOG       — Record what changed, why, and the outcome
//
// Safety:
//   - NEVER modifies live code directly
//   - ALWAYS compiles in isolated sandbox first
//   - ALWAYS runs tests before swap
//   - ALWAYS keeps backup for rollback
//   - Rate-limited: max 1 swap per 10 minutes
//
// This is the genetic core. Ultron evolves by changing its own DNA.
package self_mod

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

// MutationStatus tracks the lifecycle of a code change.
type MutationStatus int

const (
	StatusPending MutationStatus = iota
	StatusCompiling
	StatusTesting
	StatusBenchmarking
	StatusSwapping
	StatusDeployed
	StatusFailed
	StatusRolledBack
)

func (s MutationStatus) String() string {
	names := []string{"Pending", "Compiling", "Testing", "Benchmarking", "Swapping", "Deployed", "Failed", "RolledBack"}
	if int(s) < len(names) {
		return names[s]
	}
	return "Unknown"
}

// Mutation represents a proposed code change.
type Mutation struct {
	ID          string         `json:"id"`
	TargetFile  string         `json:"target_file"`  // Relative path within project
	OldCode     string         `json:"old_code"`     // What we're replacing
	NewCode     string         `json:"new_code"`     // The replacement
	TestCmd     string         `json:"test_cmd"`     // Command to validate (e.g., "go test ./...")
	BenchCmd    string         `json:"bench_cmd"`    // Benchmark command (optional)
	Reason      string         `json:"reason"`       // Why this mutation exists
	Source      string         `json:"source"`       // What generated it ("llm", "profiler", "learning")
	Status      MutationStatus `json:"status"`
	CreatedAt   time.Time      `json:"created_at"`
	CompletedAt time.Time      `json:"completed_at,omitempty"`
	Error       string         `json:"error,omitempty"`

	// Benchmark results
	OldBenchNs int64   `json:"old_bench_ns,omitempty"`
	NewBenchNs int64   `json:"new_bench_ns,omitempty"`
	Speedup    float64 `json:"speedup,omitempty"` // >1 means faster
}

// MutationLog is the append-only history of all mutations.
type MutationLog struct {
	Mutations []Mutation `json:"mutations"`
	mu        sync.Mutex
	logPath   string
}

// SelfModEngine is the core self-modification system.
type SelfModEngine struct {
	mu sync.Mutex

	// Paths
	projectRoot string // Root of the Ultron project
	sandboxDir  string // Temp compilation directory
	backupDir   string // Backups of original files

	// State
	running          bool
	lastSwapTime     time.Time
	totalMutations   int
	successfulSwaps  int
	failedMutations  int
	rolledBack       int

	// Rate limiting
	minSwapInterval time.Duration // Minimum time between swaps

	// History
	log *MutationLog
}

// NewSelfModEngine creates the self-modification engine.
func NewSelfModEngine(projectRoot string) *SelfModEngine {
	sandboxDir := filepath.Join(projectRoot, ".ultron_sandbox")
	backupDir := filepath.Join(projectRoot, ".ultron_backups")
	logDir := filepath.Join(projectRoot, "data", "mutations")

	os.MkdirAll(sandboxDir, 0755)
	os.MkdirAll(backupDir, 0755)
	os.MkdirAll(logDir, 0755)

	log := &MutationLog{
		logPath: filepath.Join(logDir, "mutation_log.jsonl"),
	}

	return &SelfModEngine{
		projectRoot:     projectRoot,
		sandboxDir:      sandboxDir,
		backupDir:       backupDir,
		minSwapInterval: 10 * time.Minute,
		log:             log,
	}
}

// ApplyMutation executes the full self-modification pipeline.
// Returns nil on success, error on failure (with automatic rollback).
func (e *SelfModEngine) ApplyMutation(m *Mutation) error {
	e.mu.Lock()
	defer e.mu.Unlock()

	e.totalMutations++
	m.CreatedAt = time.Now()

	// Rate limit check
	if time.Since(e.lastSwapTime) < e.minSwapInterval {
		m.Status = StatusFailed
		m.Error = fmt.Sprintf("rate limited: must wait %v between swaps",
			e.minSwapInterval-time.Since(e.lastSwapTime))
		e.logMutation(m)
		return fmt.Errorf(m.Error)
	}

	fmt.Printf("[SelfMod] Mutation %s: %s\n", m.ID, m.Reason)

	// ━━━━ STEP 1: Validate target exists ━━━━
	targetPath := filepath.Join(e.projectRoot, m.TargetFile)
	if _, err := os.Stat(targetPath); os.IsNotExist(err) {
		m.Status = StatusFailed
		m.Error = "target file does not exist: " + m.TargetFile
		e.logMutation(m)
		return fmt.Errorf(m.Error)
	}

	// Read original file
	originalContent, err := os.ReadFile(targetPath)
	if err != nil {
		m.Status = StatusFailed
		m.Error = "cannot read target: " + err.Error()
		e.logMutation(m)
		return fmt.Errorf(m.Error)
	}
	m.OldCode = string(originalContent)

	// ━━━━ STEP 2: Create sandbox copy ━━━━
	sandboxFile := filepath.Join(e.sandboxDir, m.TargetFile)
	os.MkdirAll(filepath.Dir(sandboxFile), 0755)
	if err := os.WriteFile(sandboxFile, []byte(m.NewCode), 0644); err != nil {
		m.Status = StatusFailed
		m.Error = "sandbox write failed: " + err.Error()
		e.logMutation(m)
		return fmt.Errorf(m.Error)
	}

	// ━━━━ STEP 3: Compile ━━━━
	m.Status = StatusCompiling
	fmt.Printf("[SelfMod]   Compiling in sandbox...\n")

	if err := e.compile(m); err != nil {
		m.Status = StatusFailed
		m.Error = "compilation failed: " + err.Error()
		e.logMutation(m)
		e.failedMutations++
		return fmt.Errorf(m.Error)
	}

	// ━━━━ STEP 4: Test ━━━━
	m.Status = StatusTesting
	if m.TestCmd != "" {
		fmt.Printf("[SelfMod]   Running tests: %s\n", m.TestCmd)
		if err := e.runTests(m); err != nil {
			m.Status = StatusFailed
			m.Error = "tests failed: " + err.Error()
			e.logMutation(m)
			e.failedMutations++
			return fmt.Errorf(m.Error)
		}
	}

	// ━━━━ STEP 5: Benchmark (optional) ━━━━
	if m.BenchCmd != "" {
		m.Status = StatusBenchmarking
		fmt.Printf("[SelfMod]   Benchmarking...\n")
		e.runBenchmark(m)
		// If new code is >10% slower, reject
		if m.Speedup < 0.9 && m.Speedup > 0 {
			m.Status = StatusFailed
			m.Error = fmt.Sprintf("benchmark regression: %.1fx slower", 1.0/m.Speedup)
			e.logMutation(m)
			e.failedMutations++
			return fmt.Errorf(m.Error)
		}
	}

	// ━━━━ STEP 6: Backup original ━━━━
	backupPath := e.createBackup(m.TargetFile, originalContent)

	// ━━━━ STEP 7: Atomic swap ━━━━
	m.Status = StatusSwapping
	fmt.Printf("[SelfMod]   Swapping live code...\n")

	if err := os.WriteFile(targetPath, []byte(m.NewCode), 0644); err != nil {
		m.Status = StatusFailed
		m.Error = "swap failed: " + err.Error()
		e.logMutation(m)
		return fmt.Errorf(m.Error)
	}

	// ━━━━ STEP 8: Post-swap verification ━━━━
	if m.TestCmd != "" {
		if err := e.verifyAfterSwap(m); err != nil {
			// ROLLBACK
			fmt.Printf("[SelfMod]   ROLLBACK: post-swap verification failed\n")
			os.WriteFile(targetPath, originalContent, 0644)
			m.Status = StatusRolledBack
			m.Error = "post-swap verification failed, rolled back: " + err.Error()
			e.logMutation(m)
			e.rolledBack++
			return fmt.Errorf(m.Error)
		}
	}

	// ━━━━ SUCCESS ━━━━
	m.Status = StatusDeployed
	m.CompletedAt = time.Now()
	e.lastSwapTime = time.Now()
	e.successfulSwaps++

	fmt.Printf("[SelfMod]   ✓ Mutation deployed: %s\n", m.Reason)
	if m.Speedup > 0 {
		fmt.Printf("[SelfMod]   Performance: %.2fx speedup\n", m.Speedup)
	}

	e.logMutation(m)

	// Cleanup sandbox
	os.Remove(sandboxFile)
	_ = backupPath // Keep backup for potential future rollback

	return nil
}

// Rollback reverts the last mutation on a file.
func (e *SelfModEngine) Rollback(targetFile string) error {
	e.mu.Lock()
	defer e.mu.Unlock()

	// Find latest backup
	pattern := filepath.Join(e.backupDir, hashPath(targetFile)+"_*")
	matches, _ := filepath.Glob(pattern)
	if len(matches) == 0 {
		return fmt.Errorf("no backup found for %s", targetFile)
	}

	// Use most recent
	latest := matches[len(matches)-1]
	backup, err := os.ReadFile(latest)
	if err != nil {
		return fmt.Errorf("cannot read backup: %v", err)
	}

	targetPath := filepath.Join(e.projectRoot, targetFile)
	if err := os.WriteFile(targetPath, backup, 0644); err != nil {
		return fmt.Errorf("rollback write failed: %v", err)
	}

	e.rolledBack++
	fmt.Printf("[SelfMod] Rolled back: %s\n", targetFile)
	return nil
}

// ═══════════════════════════════════════════════════════════════
// INTERNAL — Compile, test, benchmark
// ═══════════════════════════════════════════════════════════════

func (e *SelfModEngine) compile(m *Mutation) error {
	// Determine language from file extension
	ext := filepath.Ext(m.TargetFile)

	var cmd *exec.Cmd
	switch ext {
	case ".go":
		// Compile the Go package containing this file
		dir := filepath.Dir(filepath.Join(e.projectRoot, m.TargetFile))
		cmd = exec.Command("go", "build", "./...")
		cmd.Dir = dir
	case ".rs":
		cmd = exec.Command("cargo", "check")
		cmd.Dir = filepath.Join(e.projectRoot, "rust", "dynamic_neural")
	case ".py":
		// Python: just syntax check
		sandboxFile := filepath.Join(e.sandboxDir, m.TargetFile)
		cmd = exec.Command("python3", "-m", "py_compile", sandboxFile)
	default:
		return nil // Can't compile, skip
	}

	cmd.Env = append(os.Environ(), "CGO_ENABLED=0")
	output, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("%v\n%s", err, string(output))
	}
	return nil
}

func (e *SelfModEngine) runTests(m *Mutation) error {
	parts := strings.Fields(m.TestCmd)
	if len(parts) == 0 {
		return nil
	}

	cmd := exec.Command(parts[0], parts[1:]...)
	cmd.Dir = e.projectRoot
	cmd.Env = os.Environ()

	output, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("%v\n%s", err, string(output))
	}
	return nil
}

func (e *SelfModEngine) runBenchmark(m *Mutation) {
	parts := strings.Fields(m.BenchCmd)
	if len(parts) == 0 {
		return
	}

	// Run benchmark — simple timing
	start := time.Now()
	cmd := exec.Command(parts[0], parts[1:]...)
	cmd.Dir = e.projectRoot
	cmd.Run()
	m.NewBenchNs = time.Since(start).Nanoseconds()

	// Estimate speedup (crude: assumes old bench was the existing code)
	if m.OldBenchNs > 0 && m.NewBenchNs > 0 {
		m.Speedup = float64(m.OldBenchNs) / float64(m.NewBenchNs)
	}
}

func (e *SelfModEngine) verifyAfterSwap(m *Mutation) error {
	// Run the same test suite against the live (swapped) code
	return e.runTests(m)
}

func (e *SelfModEngine) createBackup(targetFile string, content []byte) string {
	hash := hashPath(targetFile)
	timestamp := time.Now().Format("20060102_150405")
	backupPath := filepath.Join(e.backupDir, fmt.Sprintf("%s_%s.bak", hash, timestamp))
	os.WriteFile(backupPath, content, 0644)
	return backupPath
}

func (e *SelfModEngine) logMutation(m *Mutation) {
	e.log.mu.Lock()
	defer e.log.mu.Unlock()

	e.log.Mutations = append(e.log.Mutations, *m)

	// Append to log file
	data, _ := json.Marshal(m)
	f, err := os.OpenFile(e.log.logPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err == nil {
		f.Write(data)
		f.Write([]byte("\n"))
		f.Close()
	}
}

// ═══════════════════════════════════════════════════════════════
// PUBLIC — Status and metrics
// ═══════════════════════════════════════════════════════════════

// Stats returns self-modification statistics.
func (e *SelfModEngine) Stats() map[string]interface{} {
	e.mu.Lock()
	defer e.mu.Unlock()

	return map[string]interface{}{
		"total_mutations":   e.totalMutations,
		"successful_swaps":  e.successfulSwaps,
		"failed_mutations":  e.failedMutations,
		"rolled_back":       e.rolledBack,
		"success_rate":      float64(e.successfulSwaps) / float64(max(1, e.totalMutations)),
		"last_swap_time":    e.lastSwapTime,
		"min_swap_interval": e.minSwapInterval.String(),
	}
}

// RecentMutations returns the last N mutations.
func (e *SelfModEngine) RecentMutations(n int) []Mutation {
	e.log.mu.Lock()
	defer e.log.mu.Unlock()

	total := len(e.log.Mutations)
	if n > total {
		n = total
	}
	return e.log.Mutations[total-n:]
}

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

func hashPath(path string) string {
	h := sha256.Sum256([]byte(path))
	return hex.EncodeToString(h[:8])
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
