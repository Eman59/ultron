// Package goals — Autonomous Goal Drives
//
// Ultron doesn't wait for you to tell it what to do. It has DRIVES —
// internal pressures that build over time and FORCE it to act.
//
// This is not a to-do list. This is a motivational system.
// Goals EMERGE from drive pressure. They aren't assigned.
//
// Drives:
//   CURIOSITY    — Builds when the system hasn't learned something new.
//                  "I haven't explored Rust internals in a while."
//   EFFICIENCY   — Builds when performance metrics are suboptimal.
//                  "My tick time is creeping up. Optimize something."
//   COMPLETION   — Builds when started tasks are unfinished.
//                  "I began analyzing file X but never finished."
//   INTEGRITY    — Builds when errors accumulate or tests fail.
//                  "3 errors in the last hour. Fix the source."
//   EVOLUTION    — Builds over time unconditionally.
//                  "Time to try modifying my own code again."
//   SOCIAL       — Builds when the user hasn't interacted.
//                  "The user hasn't spoken in 2 hours. Offer something."
//
// Goal Lifecycle:
//   1. Drive pressure exceeds threshold → Goal SPAWNS
//   2. Goal competes with other goals for priority
//   3. Highest-priority goal drives action selection
//   4. Progress on goal REDUCES drive pressure
//   5. Goal expires if not pursued (TTL)
//   6. Completed goals REINFORCE the drive (positive feedback)
//   7. Failed goals SUPPRESS the drive temporarily
//
// This creates emergent behavior: Ultron is always doing SOMETHING
// purposeful, even when no one is talking to it.
package goals

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"
	"sync"
	"time"
)

// ═══════════════════════════════════════════════════════════════
// DRIVES — The raw internal pressures
// ═══════════════════════════════════════════════════════════════

// DriveType identifies a fundamental motivation.
type DriveType int

const (
	DriveCuriosity  DriveType = iota // Learn new things
	DriveEfficiency                  // Optimize performance
	DriveCompletion                  // Finish what was started
	DriveIntegrity                   // Fix errors, pass tests
	DriveEvolution                   // Self-modify, improve code
	DriveSocial                      // Engage user, be helpful
)

func (d DriveType) String() string {
	names := []string{"Curiosity", "Efficiency", "Completion", "Integrity", "Evolution", "Social"}
	if int(d) < len(names) {
		return names[d]
	}
	return "Unknown"
}

// Drive is a single motivational pressure.
type Drive struct {
	Type      DriveType `json:"type"`
	Pressure  float64   `json:"pressure"`   // Current level (0-1)
	Threshold float64   `json:"threshold"`  // Spawns goal when exceeded
	BuildRate float64   `json:"build_rate"` // Per-second increase
	DecayRate float64   `json:"decay_rate"` // Per-second decrease when satisfied
	Suppressed bool     `json:"suppressed"` // Temporarily suppressed after failure
	SuppressUntil time.Time `json:"suppress_until"`
	LastSatisfied time.Time `json:"last_satisfied"`
}

// Update ticks the drive forward by dt seconds.
func (d *Drive) Update(dt float64) {
	// Check suppression
	if d.Suppressed && time.Now().After(d.SuppressUntil) {
		d.Suppressed = false
	}
	if d.Suppressed {
		return
	}

	// Build pressure over time
	d.Pressure += d.BuildRate * dt

	// Cap at 1.0
	d.Pressure = math.Min(1.0, d.Pressure)
}

// Satisfy reduces pressure (called when a goal for this drive progresses).
func (d *Drive) Satisfy(amount float64) {
	d.Pressure = math.Max(0.0, d.Pressure-amount)
	d.LastSatisfied = time.Now()
}

// Suppress temporarily stops this drive (after failure).
func (d *Drive) Suppress(duration time.Duration) {
	d.Suppressed = true
	d.SuppressUntil = time.Now().Add(duration)
	d.Pressure *= 0.5 // Halve pressure on suppression
}

// ShouldSpawnGoal returns true if pressure exceeds threshold.
func (d *Drive) ShouldSpawnGoal() bool {
	return !d.Suppressed && d.Pressure >= d.Threshold
}

// ═══════════════════════════════════════════════════════════════
// AUTONOMOUS GOALS — Emerge from drive pressure
// ═══════════════════════════════════════════════════════════════

// GoalStatus tracks where a goal is in its lifecycle.
type GoalStatus int

const (
	GoalPending   GoalStatus = iota // Waiting to be pursued
	GoalActive                      // Currently being worked on
	GoalCompleted                   // Successfully finished
	GoalFailed                      // Tried and failed
	GoalExpired                     // TTL ran out, never pursued
	GoalAbandoned                   // Explicitly dropped
)

func (s GoalStatus) String() string {
	names := []string{"Pending", "Active", "Completed", "Failed", "Expired", "Abandoned"}
	if int(s) < len(names) {
		return names[s]
	}
	return "Unknown"
}

// AutonomousGoal is a goal that emerged from internal drives.
type AutonomousGoal struct {
	ID          string     `json:"id"`
	DriveSource DriveType  `json:"drive_source"`
	Status      GoalStatus `json:"status"`

	// Description
	Title       string `json:"title"`
	Description string `json:"description"`
	ActionType  string `json:"action_type"` // What kind of action to take
	Target      string `json:"target"`      // What to act on

	// Priority (computed from drive pressure + urgency)
	Priority    float64 `json:"priority"` // 0-1
	Urgency     float64 `json:"urgency"`  // Increases as TTL approaches

	// Progress
	Progress    float64 `json:"progress"` // 0-1
	Steps       []string `json:"steps"`   // Sub-steps
	StepsDone   int     `json:"steps_done"`

	// Lifecycle
	CreatedAt   time.Time `json:"created_at"`
	StartedAt   time.Time `json:"started_at"`
	CompletedAt time.Time `json:"completed_at"`
	TTL         time.Duration `json:"ttl"`      // Expires after this
	MaxDuration time.Duration `json:"max_duration"` // Max time active

	// Outcome
	Outcome     float64 `json:"outcome"` // -1 to 1
	Lesson      string  `json:"lesson"`  // What was learned
}

// IsExpired checks if the goal has timed out.
func (g *AutonomousGoal) IsExpired() bool {
	if g.Status != GoalPending && g.Status != GoalActive {
		return false
	}
	return time.Since(g.CreatedAt) > g.TTL
}

// RemainingTime returns time until expiration.
func (g *AutonomousGoal) RemainingTime() time.Duration {
	return g.TTL - time.Since(g.CreatedAt)
}

// ═══════════════════════════════════════════════════════════════
// DRIVE SYSTEM — The autonomous motivation engine
// ═══════════════════════════════════════════════════════════════

// DriveSystem manages all drives and spawns goals autonomously.
type DriveSystem struct {
	mu sync.RWMutex

	// The six drives
	Drives [6]*Drive

	// Active goals
	Goals       []*AutonomousGoal
	MaxGoals    int
	GoalHistory []*AutonomousGoal // Completed/failed goals

	// Configuration
	GoalTTL         time.Duration // How long goals live if not pursued
	MaxGoalDuration time.Duration // Max time for an active goal
	SpawnCooldown   time.Duration // Min time between goal spawns per drive
	lastSpawn       [6]time.Time  // Last spawn time per drive

	// Stats
	GoalsSpawned    int
	GoalsCompleted  int
	GoalsFailed     int
	GoalsExpired    int

	// Persistence
	savePath string
}

// NewDriveSystem creates the autonomous motivation engine.
func NewDriveSystem(savePath string) *DriveSystem {
	ds := &DriveSystem{
		MaxGoals:        5,
		GoalTTL:         30 * time.Minute,
		MaxGoalDuration: 15 * time.Minute,
		SpawnCooldown:   5 * time.Minute,
		Goals:           make([]*AutonomousGoal, 0, 10),
		GoalHistory:     make([]*AutonomousGoal, 0, 100),
		savePath:        savePath,
	}

	// Initialize drives with different characteristics
	ds.Drives = [6]*Drive{
		{ // Curiosity — builds moderately, low threshold
			Type: DriveCuriosity, Pressure: 0.3, Threshold: 0.6,
			BuildRate: 0.002, DecayRate: 0.01, // ~5 min to threshold from 0
		},
		{ // Efficiency — builds slowly, moderate threshold
			Type: DriveEfficiency, Pressure: 0.2, Threshold: 0.7,
			BuildRate: 0.001, DecayRate: 0.008,
		},
		{ // Completion — doesn't build on its own (triggered externally)
			Type: DriveCompletion, Pressure: 0.0, Threshold: 0.5,
			BuildRate: 0.0, DecayRate: 0.005,
		},
		{ // Integrity — builds when errors happen
			Type: DriveIntegrity, Pressure: 0.1, Threshold: 0.6,
			BuildRate: 0.0005, DecayRate: 0.01,
		},
		{ // Evolution — builds steadily, high threshold
			Type: DriveEvolution, Pressure: 0.1, Threshold: 0.8,
			BuildRate: 0.0003, DecayRate: 0.005, // ~45 min to threshold
		},
		{ // Social — builds when user is absent
			Type: DriveSocial, Pressure: 0.0, Threshold: 0.7,
			BuildRate: 0.001, DecayRate: 0.02,
		},
	}

	ds.load()
	return ds
}

// Tick updates all drives and manages goal lifecycle. Called every OODA tick.
func (ds *DriveSystem) Tick(dt float64) {
	ds.mu.Lock()
	defer ds.mu.Unlock()

	// 1. Update all drive pressures
	for _, drive := range ds.Drives {
		drive.Update(dt)
	}

	// 2. Expire old goals
	ds.expireGoals()

	// 3. Spawn new goals from high-pressure drives
	ds.spawnGoals()

	// 4. Update goal urgency (increases as TTL approaches)
	ds.updateUrgency()

	// 5. Sort goals by priority
	sort.Slice(ds.Goals, func(i, j int) bool {
		return ds.Goals[i].Priority > ds.Goals[j].Priority
	})
}

// GetTopGoal returns the highest-priority active or pending goal.
func (ds *DriveSystem) GetTopGoal() *AutonomousGoal {
	ds.mu.RLock()
	defer ds.mu.RUnlock()

	for _, goal := range ds.Goals {
		if goal.Status == GoalActive || goal.Status == GoalPending {
			return goal
		}
	}
	return nil
}

// GetActiveGoals returns all non-completed goals sorted by priority.
func (ds *DriveSystem) GetActiveGoals() []*AutonomousGoal {
	ds.mu.RLock()
	defer ds.mu.RUnlock()

	result := make([]*AutonomousGoal, 0)
	for _, g := range ds.Goals {
		if g.Status == GoalActive || g.Status == GoalPending {
			result = append(result, g)
		}
	}
	return result
}

// CompleteGoal marks a goal as successfully completed.
func (ds *DriveSystem) CompleteGoal(goalID string, outcome float64, lesson string) {
	ds.mu.Lock()
	defer ds.mu.Unlock()

	for _, goal := range ds.Goals {
		if goal.ID == goalID {
			goal.Status = GoalCompleted
			goal.CompletedAt = time.Now()
			goal.Progress = 1.0
			goal.Outcome = outcome
			goal.Lesson = lesson

			// Satisfy the drive
			ds.Drives[goal.DriveSource].Satisfy(0.4)

			// Positive reinforcement: lower threshold slightly (easier to trigger)
			ds.Drives[goal.DriveSource].Threshold = math.Max(0.3,
				ds.Drives[goal.DriveSource].Threshold-0.02)

			ds.GoalsCompleted++
			ds.GoalHistory = append(ds.GoalHistory, goal)
			break
		}
	}

	ds.pruneCompletedGoals()
}

// FailGoal marks a goal as failed.
func (ds *DriveSystem) FailGoal(goalID string, reason string) {
	ds.mu.Lock()
	defer ds.mu.Unlock()

	for _, goal := range ds.Goals {
		if goal.ID == goalID {
			goal.Status = GoalFailed
			goal.CompletedAt = time.Now()
			goal.Outcome = -0.3
			goal.Lesson = reason

			// Suppress the drive temporarily
			ds.Drives[goal.DriveSource].Suppress(10 * time.Minute)

			// Negative reinforcement: raise threshold (harder to trigger)
			ds.Drives[goal.DriveSource].Threshold = math.Min(0.95,
				ds.Drives[goal.DriveSource].Threshold+0.05)

			ds.GoalsFailed++
			ds.GoalHistory = append(ds.GoalHistory, goal)
			break
		}
	}

	ds.pruneCompletedGoals()
}

// ProgressGoal records progress on a goal.
func (ds *DriveSystem) ProgressGoal(goalID string, amount float64) {
	ds.mu.Lock()
	defer ds.mu.Unlock()

	for _, goal := range ds.Goals {
		if goal.ID == goalID {
			goal.Progress = math.Min(1.0, goal.Progress+amount)
			if goal.Status == GoalPending {
				goal.Status = GoalActive
				goal.StartedAt = time.Now()
			}
			// Partial drive satisfaction
			ds.Drives[goal.DriveSource].Satisfy(amount * 0.2)
			break
		}
	}
}

// BoostDrive externally increases a drive (e.g., error occurred → boost Integrity).
func (ds *DriveSystem) BoostDrive(driveType DriveType, amount float64) {
	ds.mu.Lock()
	defer ds.mu.Unlock()

	if int(driveType) < len(ds.Drives) {
		ds.Drives[driveType].Pressure = math.Min(1.0,
			ds.Drives[driveType].Pressure+amount)
	}
}

// ═══════════════════════════════════════════════════════════════
// INTERNAL — Goal spawning and lifecycle
// ═══════════════════════════════════════════════════════════════

func (ds *DriveSystem) spawnGoals() {
	if len(ds.Goals) >= ds.MaxGoals {
		return
	}

	now := time.Now()

	for i, drive := range ds.Drives {
		if !drive.ShouldSpawnGoal() {
			continue
		}

		// Cooldown check
		if now.Sub(ds.lastSpawn[i]) < ds.SpawnCooldown {
			continue
		}

		// Already have a goal for this drive?
		hasGoal := false
		for _, g := range ds.Goals {
			if g.DriveSource == drive.Type && (g.Status == GoalPending || g.Status == GoalActive) {
				hasGoal = true
				break
			}
		}
		if hasGoal {
			continue
		}

		// SPAWN a new goal
		goal := ds.generateGoal(drive)
		ds.Goals = append(ds.Goals, goal)
		ds.lastSpawn[i] = now
		ds.GoalsSpawned++

		fmt.Printf("[Drives] Goal spawned: %s (drive: %s, pressure: %.2f)\n",
			goal.Title, drive.Type, drive.Pressure)
	}
}

func (ds *DriveSystem) generateGoal(drive *Drive) *AutonomousGoal {
	// Generate goal based on which drive is firing
	templates := map[DriveType]struct {
		title      string
		action     string
		target     string
		desc       string
	}{
		DriveCuriosity: {
			title:  "Explore something new",
			action: "Explore",
			target: "codebase",
			desc:   "Read and analyze an unfamiliar part of the system",
		},
		DriveEfficiency: {
			title:  "Optimize performance",
			action: "Consolidate",
			target: "slow_component",
			desc:   "Find and improve the slowest code path",
		},
		DriveCompletion: {
			title:  "Finish pending work",
			action: "Process",
			target: "unfinished_task",
			desc:   "Complete a previously started but unfinished task",
		},
		DriveIntegrity: {
			title:  "Fix system issues",
			action: "Defend",
			target: "error_source",
			desc:   "Identify and resolve the source of recent errors",
		},
		DriveEvolution: {
			title:  "Evolve self",
			action: "Evolve",
			target: "own_code",
			desc:   "Generate a self-modification to improve capabilities",
		},
		DriveSocial: {
			title:  "Engage user",
			action: "Communicate",
			target: "user",
			desc:   "Prepare something useful for when the user returns",
		},
	}

	tmpl := templates[drive.Type]

	return &AutonomousGoal{
		ID:          fmt.Sprintf("goal_%s_%d", drive.Type, time.Now().UnixNano()%100000),
		DriveSource: drive.Type,
		Status:      GoalPending,
		Title:       tmpl.title,
		Description: tmpl.desc,
		ActionType:  tmpl.action,
		Target:      tmpl.target,
		Priority:    drive.Pressure,
		Urgency:     0.0,
		CreatedAt:   time.Now(),
		TTL:         ds.GoalTTL,
		MaxDuration: ds.MaxGoalDuration,
	}
}

func (ds *DriveSystem) expireGoals() {
	for _, goal := range ds.Goals {
		if goal.IsExpired() && (goal.Status == GoalPending || goal.Status == GoalActive) {
			goal.Status = GoalExpired
			ds.GoalsExpired++
			ds.GoalHistory = append(ds.GoalHistory, goal)
			// Slight drive increase on expiry (unmet need persists)
			ds.Drives[goal.DriveSource].Pressure = math.Min(1.0,
				ds.Drives[goal.DriveSource].Pressure+0.1)
		}
	}
}

func (ds *DriveSystem) updateUrgency() {
	for _, goal := range ds.Goals {
		if goal.Status == GoalPending || goal.Status == GoalActive {
			remaining := goal.RemainingTime()
			if remaining > 0 {
				goal.Urgency = 1.0 - (float64(remaining) / float64(goal.TTL))
			} else {
				goal.Urgency = 1.0
			}
			// Priority = base drive pressure + urgency bonus
			goal.Priority = ds.Drives[goal.DriveSource].Pressure*0.6 + goal.Urgency*0.4
		}
	}
}

func (ds *DriveSystem) pruneCompletedGoals() {
	active := make([]*AutonomousGoal, 0, len(ds.Goals))
	for _, g := range ds.Goals {
		if g.Status == GoalPending || g.Status == GoalActive {
			active = append(active, g)
		}
	}
	ds.Goals = active

	// Trim history
	if len(ds.GoalHistory) > 200 {
		ds.GoalHistory = ds.GoalHistory[len(ds.GoalHistory)-200:]
	}
}

// ═══════════════════════════════════════════════════════════════
// PERSISTENCE & STATUS
// ═══════════════════════════════════════════════════════════════

// Save persists drive state to disk.
func (ds *DriveSystem) Save() {
	ds.mu.RLock()
	defer ds.mu.RUnlock()

	if ds.savePath == "" {
		return
	}

	state := struct {
		Drives      [6]*Drive          `json:"drives"`
		Goals       []*AutonomousGoal  `json:"goals"`
		Stats       map[string]int     `json:"stats"`
	}{
		Drives: ds.Drives,
		Goals:  ds.Goals,
		Stats: map[string]int{
			"spawned":   ds.GoalsSpawned,
			"completed": ds.GoalsCompleted,
			"failed":    ds.GoalsFailed,
			"expired":   ds.GoalsExpired,
		},
	}

	data, _ := json.MarshalIndent(state, "", "  ")
	os.MkdirAll(filepath.Dir(ds.savePath), 0755)
	tmpPath := ds.savePath + ".tmp"
	os.WriteFile(tmpPath, data, 0644)
	os.Rename(tmpPath, ds.savePath)
}

func (ds *DriveSystem) load() {
	if ds.savePath == "" {
		return
	}
	data, err := os.ReadFile(ds.savePath)
	if err != nil {
		return
	}

	var state struct {
		Drives [6]*Drive         `json:"drives"`
		Goals  []*AutonomousGoal `json:"goals"`
		Stats  map[string]int    `json:"stats"`
	}
	if json.Unmarshal(data, &state) == nil {
		for i, d := range state.Drives {
			if d != nil {
				ds.Drives[i] = d
			}
		}
		ds.Goals = state.Goals
		if state.Stats != nil {
			ds.GoalsSpawned = state.Stats["spawned"]
			ds.GoalsCompleted = state.Stats["completed"]
			ds.GoalsFailed = state.Stats["failed"]
			ds.GoalsExpired = state.Stats["expired"]
		}
	}
}

// Stats returns current drive system state.
func (ds *DriveSystem) Stats() map[string]interface{} {
	ds.mu.RLock()
	defer ds.mu.RUnlock()

	drives := make(map[string]float64)
	for _, d := range ds.Drives {
		drives[d.Type.String()] = d.Pressure
	}

	activeGoals := make([]map[string]interface{}, 0)
	for _, g := range ds.Goals {
		if g.Status == GoalPending || g.Status == GoalActive {
			activeGoals = append(activeGoals, map[string]interface{}{
				"id":       g.ID,
				"title":    g.Title,
				"drive":    g.DriveSource.String(),
				"priority": g.Priority,
				"progress": g.Progress,
				"status":   g.Status.String(),
				"ttl_remaining": g.RemainingTime().String(),
			})
		}
	}

	return map[string]interface{}{
		"drives":          drives,
		"active_goals":    activeGoals,
		"goals_spawned":   ds.GoalsSpawned,
		"goals_completed": ds.GoalsCompleted,
		"goals_failed":    ds.GoalsFailed,
		"goals_expired":   ds.GoalsExpired,
	}
}
