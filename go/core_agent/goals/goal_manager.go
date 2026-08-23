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
	priority float64,
	reasoning string,
) *Goal {
	log.Printf("Creating new goal: type=%d, domain=%s, description=%s", goalType, domain, description)

	g := &Goal{
		ID:               uuid.New().String(),
		Type:             goalType,
		Domain:           domain,
		Description:      description,
		Status:           GoalStatus(0),
		Priority:         priority,
		Progress:         0.0,
		CreatedAt:        time.Now(),
		SuccessMetric:    metric,
		SuccessThreshold: threshold,
		CurrentValue:     0.0,
		Reasoning:        reasoning,
	}

	gm.mu.Lock()
	gm.goals[g.ID] = g
	gm.mu.Unlock()

	log.Printf("Goal created: id=%s, type=%d, domain=%s", g.ID, g.Type, g.Domain)

	return g
}