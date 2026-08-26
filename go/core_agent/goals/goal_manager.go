// Package goals implements hierarchical goal management for the Core Agent.
// Goals are not hard-coded — they emerge from drives and are self-generated.
package goals

import (
	"fmt"
	"log"
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

	log.Println("GoalManager initialized")

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
	currentValue float64,
	reasoning string,
) *Goal {
	gm.mu.Lock()
	defer gm.mu.Unlock()

	if goalType < 0 || goalType >= GoalType(len([]GoalType{GoalSurvival, GoalLearning, GoalOptimization, GoalExpansion, GoalCreation, GoalSelfImprovement, GoalMission})) {
		log.Println("Invalid goal type")
		return nil
	}

	if domain == "" {
		log.Println("Domain cannot be empty")
		return nil
	}

	if description == "" {
		log.Println("Description cannot be empty")
		return nil
	}

	if metric == "" {
		log.Println("Metric cannot be empty")
		return nil
	}

	if threshold < 0 || threshold > 1 {
		log.Println("Threshold must be between 0 and 1")
		return nil
	}

	if currentValue < 0 || currentValue > 1 {
		log.Println("Current value must be between 0 and 1")
		return nil
	}

	if reasoning == "" {
		log.Println("Reasoning cannot be empty")
		return nil
	}

	id := uuid.New().String()
	goal := &Goal{
		ID:               id,
		Type:             goalType,
		Domain:           domain,
		Description:      description,
		Status:           GoalStatus(0),
		Priority:         1.0,
		Progress:         0.0,
		CreatedAt:        time.Now(),
		LastProgressTime: time.Now(),
		SuccessMetric:    metric,
		SuccessThreshold: threshold,
		CurrentValue:     currentValue,
		Reasoning:        reasoning,
	}

	gm.goals[id] = goal
	gm.activeGoals = append(gm.activeGoals, goal)
	sort.Slice(gm.activeGoals, func(i, j int) bool {
		return gm.activeGoals[i].Priority > gm.activeGoals[j].Priority
	})

	if len(gm.activeGoals) > gm.maxActiveGoals {
		gm.activeGoals = gm.activeGoals[:gm.maxActiveGoals]
	}

	return goal
}

// UpdateGoal updates an existing goal.
func (gm *GoalManager) UpdateGoal(id string, priority float64, progress float64) {
	gm.mu.Lock()
	defer gm.mu.Unlock()

	goal, ok := gm.goals[id]
	if !ok {
		log.Println("Goal not found")
		return
	}

	if priority < 0 || priority > 1 {
		log.Println("Priority must be between 0 and 1")
		return
	}

	if progress < 0 || progress > 1 {
		log.Println("Progress must be between 0 and 1")
		return
	}

	goal.Priority = priority
	goal.Progress = progress
	goal.LastProgressTime = time.Now()

	sort.Slice(gm.activeGoals, func(i, j int) bool {
		return gm.activeGoals[i].Priority > gm.activeGoals[j].Priority
	})
}

// DeleteGoal deletes a goal.
func (gm *GoalManager) DeleteGoal(id string) {
	gm.mu.Lock()
	defer gm.mu.Unlock()

	goal, ok := gm.goals[id]
	if !ok {
		log.Println("Goal not found")
		return
	}

	delete(gm.goals, id)

	for i, g := range gm.activeGoals {
		if g.ID == id {
			gm.activeGoals = append(gm.activeGoals[:i], gm.activeGoals[i+1:]...)
			break
		}
	}
}

// GetGoal returns a goal by ID.
func (gm *GoalManager) GetGoal(id string) *Goal {
	gm.mu.RLock()
	defer gm.mu.RUnlock()

	goal, ok := gm.goals[id]
	if !ok {
		return nil
	}

	return goal
}

// GetActiveGoals returns the active goals.
func (gm *GoalManager) GetActiveGoals() []*Goal {
	gm.mu.RLock()
	defer gm.mu.RUnlock()

	return gm.activeGoals
}

// AbandonGoal abandons a goal.
func (gm *GoalManager) AbandonGoal(id string) {
	gm.mu.Lock()
	defer gm.mu.Unlock()

	goal, ok := gm.goals[id]
	if !ok {
		log.Println("Goal not found")
		return
	}

	goal.Status = GoalStatus(-1)
	goal.CompletedAt = &time.Time{}

	for i, g := range gm.activeGoals {
		if g.ID == id {
			gm.activeGoals = append(gm.activeGoals[:i], gm.activeGoals[i+1:]...)
			break
		}
	}
}

// Timeout checks for timed out goals.
func (gm *GoalManager) Timeout() {
	gm.mu.Lock()
	defer gm.mu.Unlock()

	for _, goal := range gm.goals {
		if goal.Deadline != nil && time.Now().After(*goal.Deadline) {
			gm.AbandonGoal(goal.ID)
		}
	}
}