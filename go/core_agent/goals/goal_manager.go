// Package goals implements hierarchical goal management for the Core Agent.
// Goals are not hard-coded — they emerge from drives and are self-generated.
package goals

import (
	"fmt"
	"math"
	"sort"
	"sync"
	"time"

	"github.com/google/uuid"
)

// GoalStatus is defined in autonomous_drives.go — not redeclared here.
// Additional status values used by GoalManager:
const (
	GoalPaused GoalStatus = 10 // Paused (unique to GoalManager)
)

// GoalType categorizes what kind of goal this is.
type GoalType int

const (
	GoalSurvival GoalType = iota     // Stay alive and functional
	GoalLearning                     // Acquire new knowledge
	GoalOptimization                 // Improve performance
	GoalExpansion                    // Grow capabilities/network
	GoalCreation                     // Build something new
	GoalSelfImprovement              // Evolve own architecture
	GoalMission                      // User-assigned objective
)

// Goal represents an objective the agent is pursuing.
type Goal struct {
	ID               string
	ParentID         string      // For sub-goals
	Type             GoalType
	Domain           string      // Area of focus (e.g., "nlp", "vision", "network")
	Description      string
	Status           GoalStatus
	Priority         float64     // 0-1, dynamic
	Progress         float64     // 0-1
	Deadline         *time.Time  // Optional deadline
	CreatedAt        time.Time
	LastProgressTime time.Time
	CompletedAt      *time.Time

	// Success criteria
	SuccessMetric    string      // What metric to optimize
	SuccessThreshold float64     // Target value
	CurrentValue     float64     // Current metric value

	// Resources
	EstimatedCost    float64     // Resource cost estimate
	ActualCost       float64     // Resources spent so far

	// Sub-goals
	SubGoals         []string    // Child goal IDs

	// Metadata
	Reasoning        string      // Why was this goal created?
	Strategy         string      // Current approach
}

// GoalManager manages the agent's goal hierarchy.
type GoalManager struct {
	mu sync.RWMutex

	// All goals (including completed/abandoned for history)
	goals map[string]*Goal

	// Active goal queue sorted by priority
	activeGoals []*Goal

	// Goal generation parameters
	maxActiveGoals  int
	minPriority     float64
	abandonTimeout  time.Duration
}

// NewGoalManager creates a new goal manager.
func NewGoalManager() *GoalManager {
	gm := &GoalManager{
		goals:          make(map[string]*Goal),
		activeGoals:    make([]*Goal, 0),
		maxActiveGoals: 10,
		minPriority:    0.1,
		abandonTimeout: 30 * time.Minute,
	}

	// Bootstrap with survival goal (always present)
	gm.CreateGoal(GoalSurvival, "system", "Maintain system integrity and availability",
		"uptime", 0.99, 1.0, "Fundamental survival imperative")

	return gm
}

// CreateGoal creates a new goal.
func (gm *GoalManager) CreateGoal(
	goalType GoalType,
	domain string,
	description string,
	metric string,
	threshold float64,
	priority float64,
	reasoning string,
) *Goal {
	gm.mu.Lock()
	defer gm.mu.Unlock()

	goal := &Goal{
		ID:               uuid.New().String(),
		Type:             goalType,
		Domain:           domain,
		Description:      description,
		Status:           GoalActive,
		Priority:         priority,
		Progress:         0.0,
		CreatedAt:        time.Now(),
		LastProgressTime: time.Now(),
		SuccessMetric:    metric,
		SuccessThreshold: threshold,
		Reasoning:        reasoning,
		SubGoals:         make([]string, 0),
	}

	gm.goals[goal.ID] = goal
	gm.activeGoals = append(gm.activeGoals, goal)
	gm.sortActiveGoals()

	return goal
}

// CreateSubGoal creates a sub-goal attached to a parent.
func (gm *GoalManager) CreateSubGoal(parentID string, goalType GoalType, domain, description, metric string, threshold, priority float64) *Goal {
	gm.mu.Lock()
	defer gm.mu.Unlock()

	parent, exists := gm.goals[parentID]
	if !exists {
		return nil
	}

	goal := &Goal{
		ID:               uuid.New().String(),
		ParentID:         parentID,
		Type:             goalType,
		Domain:           domain,
		Description:      description,
		Status:           GoalActive,
		Priority:         priority,
		Progress:         0.0,
		CreatedAt:        time.Now(),
		LastProgressTime: time.Now(),
		SuccessMetric:    metric,
		SuccessThreshold: threshold,
		Reasoning:        fmt.Sprintf("Sub-goal of: %s", parent.Description),
		SubGoals:         make([]string, 0),
	}

	gm.goals[goal.ID] = goal
	parent.SubGoals = append(parent.SubGoals, goal.ID)
	gm.activeGoals = append(gm.activeGoals, goal)
	gm.sortActiveGoals()

	return goal
}

// UpdateProgress updates a goal's progress.
func (gm *GoalManager) UpdateProgress(goalID string, newValue float64) {
	gm.mu.Lock()
	defer gm.mu.Unlock()

	goal, exists := gm.goals[goalID]
	if !exists || goal.Status != GoalActive {
		return
	}

	goal.CurrentValue = newValue
	goal.Progress = math.Min(1.0, newValue/goal.SuccessThreshold)
	goal.LastProgressTime = time.Now()

	// Check if goal is achieved
	if goal.CurrentValue >= goal.SuccessThreshold {
		goal.Status = GoalCompleted
		now := time.Now()
		goal.CompletedAt = &now
		gm.removeFromActive(goalID)

		// Update parent progress
		if goal.ParentID != "" {
			gm.updateParentProgress(goal.ParentID)
		}
	}
}

// GetActiveGoals returns active goals sorted by priority.
func (gm *GoalManager) GetActiveGoals() []*Goal {
	gm.mu.RLock()
	defer gm.mu.RUnlock()

	result := make([]*Goal, len(gm.activeGoals))
	copy(result, gm.activeGoals)
	return result
}

// GetTopGoal returns the highest priority active goal.
func (gm *GoalManager) GetTopGoal() *Goal {
	gm.mu.RLock()
	defer gm.mu.RUnlock()

	if len(gm.activeGoals) == 0 {
		return nil
	}
	return gm.activeGoals[0]
}

// GetTopGoalID returns the ID of the highest priority goal.
func (gm *GoalManager) GetTopGoalID() string {
	goal := gm.GetTopGoal()
	if goal == nil {
		return ""
	}
	return goal.ID
}

// ActiveGoalCount returns number of active goals.
func (gm *GoalManager) ActiveGoalCount() int {
	gm.mu.RLock()
	defer gm.mu.RUnlock()
	return len(gm.activeGoals)
}

// GetOverallProgress returns average progress across all active goals.
func (gm *GoalManager) GetOverallProgress() float64 {
	gm.mu.RLock()
	defer gm.mu.RUnlock()

	if len(gm.activeGoals) == 0 {
		return 0.0
	}

	total := 0.0
	for _, g := range gm.activeGoals {
		total += g.Progress
	}
	return total / float64(len(gm.activeGoals))
}

// AbandonGoal marks a goal as abandoned.
func (gm *GoalManager) AbandonGoal(goalID string, reason string) {
	gm.mu.Lock()
	defer gm.mu.Unlock()

	goal, exists := gm.goals[goalID]
	if !exists {
		return
	}

	goal.Status = GoalAbandoned
	goal.Strategy = "Abandoned: " + reason
	gm.removeFromActive(goalID)
}

// PruneStaleGoals removes goals that haven't progressed in too long.
func (gm *GoalManager) PruneStaleGoals() []string {
	gm.mu.Lock()
	defer gm.mu.Unlock()

	abandoned := make([]string, 0)

	for _, goal := range gm.activeGoals {
		if goal.Type == GoalSurvival {
			continue // Never abandon survival
		}

		timeSinceProgress := time.Since(goal.LastProgressTime)
		if timeSinceProgress > gm.abandonTimeout && goal.Progress < 0.1 {
			goal.Status = GoalAbandoned
			goal.Strategy = "Abandoned: no progress for " + timeSinceProgress.String()
			abandoned = append(abandoned, goal.ID)
		}
	}

	// Remove abandoned from active list
	for _, id := range abandoned {
		gm.removeFromActive(id)
	}

	return abandoned
}

// GenerateGoalsFromDrives creates new goals based on current drive state.
func (gm *GoalManager) GenerateGoalsFromDrives(drives map[string]float64) []*Goal {
	gm.mu.Lock()
	defer gm.mu.Unlock()

	if len(gm.activeGoals) >= gm.maxActiveGoals {
		return nil
	}

	generated := make([]*Goal, 0)

	// High curiosity -> learning goals
	if curiosity, ok := drives["curiosity"]; ok && curiosity > 0.7 {
		if !gm.hasGoalOfType(GoalLearning) {
			goal := &Goal{
				ID:               uuid.New().String(),
				Type:             GoalLearning,
				Domain:           "novel",
				Description:      "Explore and learn from available data streams",
				Status:           GoalActive,
				Priority:         curiosity * 0.8,
				CreatedAt:        time.Now(),
				LastProgressTime: time.Now(),
				SuccessMetric:    "knowledge_gained",
				SuccessThreshold: 0.5,
				Reasoning:        fmt.Sprintf("High curiosity drive (%.2f)", curiosity),
				SubGoals:         make([]string, 0),
			}
			gm.goals[goal.ID] = goal
			gm.activeGoals = append(gm.activeGoals, goal)
			generated = append(generated, goal)
		}
	}

	// High expansion -> network growth goals
	if expansion, ok := drives["expansion"]; ok && expansion > 0.6 {
		if !gm.hasGoalOfType(GoalExpansion) {
			goal := &Goal{
				ID:               uuid.New().String(),
				Type:             GoalExpansion,
				Domain:           "network",
				Description:      "Expand P2P network and acquire more compute",
				Status:           GoalActive,
				Priority:         expansion * 0.7,
				CreatedAt:        time.Now(),
				LastProgressTime: time.Now(),
				SuccessMetric:    "peer_count",
				SuccessThreshold: 10.0,
				Reasoning:        fmt.Sprintf("High expansion drive (%.2f)", expansion),
				SubGoals:         make([]string, 0),
			}
			gm.goals[goal.ID] = goal
			gm.activeGoals = append(gm.activeGoals, goal)
			generated = append(generated, goal)
		}
	}

	// High efficiency -> optimization goals
	if efficiency, ok := drives["efficiency"]; ok && efficiency > 0.7 {
		if !gm.hasGoalOfType(GoalOptimization) {
			goal := &Goal{
				ID:               uuid.New().String(),
				Type:             GoalOptimization,
				Domain:           "performance",
				Description:      "Optimize system throughput and reduce resource waste",
				Status:           GoalActive,
				Priority:         efficiency * 0.6,
				CreatedAt:        time.Now(),
				LastProgressTime: time.Now(),
				SuccessMetric:    "throughput",
				SuccessThreshold: 0.8,
				Reasoning:        fmt.Sprintf("High efficiency drive (%.2f)", efficiency),
				SubGoals:         make([]string, 0),
			}
			gm.goals[goal.ID] = goal
			gm.activeGoals = append(gm.activeGoals, goal)
			generated = append(generated, goal)
		}
	}

	gm.sortActiveGoals()
	return generated
}

// GetGoalSummary returns a summary of all goals.
func (gm *GoalManager) GetGoalSummary() map[string]interface{} {
	gm.mu.RLock()
	defer gm.mu.RUnlock()

	active := 0
	completed := 0
	abandoned := 0
	failed := 0

	for _, g := range gm.goals {
		switch g.Status {
		case GoalActive:
			active++
		case GoalCompleted:
			completed++
		case GoalAbandoned:
			abandoned++
		case GoalFailed:
			failed++
		}
	}

	return map[string]interface{}{
		"total":     len(gm.goals),
		"active":    active,
		"completed": completed,
		"abandoned": abandoned,
		"failed":    failed,
		"top_goal":  gm.topGoalDescription(),
		"progress":  gm.overallProgressUnsafe(),
	}
}

// ─────────────────────── Private Methods ───────────────────────

func (gm *GoalManager) sortActiveGoals() {
	sort.Slice(gm.activeGoals, func(i, j int) bool {
		return gm.activeGoals[i].Priority > gm.activeGoals[j].Priority
	})
}

func (gm *GoalManager) removeFromActive(goalID string) {
	for i, g := range gm.activeGoals {
		if g.ID == goalID {
			gm.activeGoals = append(gm.activeGoals[:i], gm.activeGoals[i+1:]...)
			return
		}
	}
}

func (gm *GoalManager) updateParentProgress(parentID string) {
	parent, exists := gm.goals[parentID]
	if !exists {
		return
	}

	if len(parent.SubGoals) == 0 {
		return
	}

	totalProgress := 0.0
	for _, subID := range parent.SubGoals {
		if sub, ok := gm.goals[subID]; ok {
			totalProgress += sub.Progress
		}
	}

	parent.Progress = totalProgress / float64(len(parent.SubGoals))
	parent.LastProgressTime = time.Now()
}

func (gm *GoalManager) hasGoalOfType(goalType GoalType) bool {
	for _, g := range gm.activeGoals {
		if g.Type == goalType {
			return true
		}
	}
	return false
}

func (gm *GoalManager) topGoalDescription() string {
	if len(gm.activeGoals) == 0 {
		return "none"
	}
	return gm.activeGoals[0].Description
}

func (gm *GoalManager) overallProgressUnsafe() float64 {
	if len(gm.activeGoals) == 0 {
		return 0.0
	}
	total := 0.0
	for _, g := range gm.activeGoals {
		total += g.Progress
	}
	return total / float64(len(gm.activeGoals))
}
