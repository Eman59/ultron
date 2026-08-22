// Package agent — Experiential Learning Loop
//
// This is what makes Ultron get SMARTER over time instead of resetting.
//
// The loop:
//   Action → Outcome → Score → Store in episodic memory →
//   Next similar situation → Retrieve past outcomes →
//   Bias decision toward historically successful patterns
//
// Three mechanisms:
//   1. OUTCOME SCORING — Every action gets a multi-dimensional score
//   2. PATTERN MEMORY — Situation → Action → Outcome triples are stored
//   3. DECISION BIAS — When deciding, retrieve past outcomes and bias scoring
//
// Over time this creates compound intelligence: each decision benefits
// from every past decision in similar contexts.
package agent

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"
	"sync"
	"time"

	"go.uber.org/zap"
)

// ═══════════════════════════════════════════════════════════════
// EXPERIENCE RECORD — The fundamental unit of learning
// ═══════════════════════════════════════════════════════════════

// Experience captures a complete Action→Outcome loop with full context.
type Experience struct {
	ID            string    `json:"id"`
	Timestamp     time.Time `json:"timestamp"`

	// Context: What was the situation?
	WorldState    ExperienceContext `json:"world_state"`
	DriveState    ExperienceDrives  `json:"drive_state"`
	GoalActive    string            `json:"goal_active"`
	Assessment    string            `json:"assessment_focus"`

	// Action: What was done?
	ActionType    string            `json:"action_type"`
	ActionTarget  string            `json:"action_target"`
	ActionParams  map[string]string `json:"action_params"`
	Confidence    float64           `json:"confidence"`

	// Outcome: What happened?
	Success       bool              `json:"success"`
	Utility       float64           `json:"utility"`       // -1 to 1
	Duration      time.Duration     `json:"duration"`
	SideEffects   []string          `json:"side_effects"`
	Error         string            `json:"error,omitempty"`

	// Scoring: Multi-dimensional outcome rating
	Score         ExperienceScore   `json:"score"`

	// Learning: What patterns emerge?
	Pattern       string            `json:"pattern"`        // Derived pattern key
	Reinforcement float64           `json:"reinforcement"`  // How much this reinforces the pattern
}

// ExperienceContext captures the state of the world at decision time.
type ExperienceContext struct {
	CPU             float64 `json:"cpu"`
	Memory          float64 `json:"memory"`
	NetworkHealth   float64 `json:"network_health"`
	ThreatLevel     float64 `json:"threat_level"`
	PeerCount       int     `json:"peer_count"`
	PendingData     int64   `json:"pending_data"`
	LearningPotential float64 `json:"learning_potential"`
	MeshSize        int     `json:"mesh_size"`
}

// ExperienceDrives captures the drive state at decision time.
type ExperienceDrives struct {
	Curiosity        float64 `json:"curiosity"`
	SelfPreservation float64 `json:"self_preservation"`
	Expansion        float64 `json:"expansion"`
	Efficiency       float64 `json:"efficiency"`
	Coherence        float64 `json:"coherence"`
	Purpose          float64 `json:"purpose"`
}

// ExperienceScore is a multi-dimensional outcome rating.
type ExperienceScore struct {
	GoalProgress    float64 `json:"goal_progress"`    // Did it advance the goal?
	ResourceCost    float64 `json:"resource_cost"`    // How much did it cost?
	TimeEfficiency  float64 `json:"time_efficiency"`  // Was it fast?
	NoveltyGain     float64 `json:"novelty_gain"`     // Did we learn something new?
	SafetyScore     float64 `json:"safety_score"`     // Any security concerns?
	OverallScore    float64 `json:"overall_score"`    // Weighted composite
}

// ═══════════════════════════════════════════════════════════════
// PATTERN — Learned behavior patterns from accumulated experiences
// ═══════════════════════════════════════════════════════════════

// Pattern represents a learned situation→action→outcome mapping.
type Pattern struct {
	ID            string    `json:"id"`
	Key           string    `json:"key"`              // Unique pattern identifier
	ActionType    string    `json:"action_type"`
	ActionTarget  string    `json:"action_target"`

	// When does this pattern apply?
	ContextRange  ContextRange `json:"context_range"`

	// How well does it work?
	AvgScore      float64   `json:"avg_score"`
	SuccessRate   float64   `json:"success_rate"`
	SampleSize    int       `json:"sample_size"`
	Confidence    float64   `json:"confidence"`       // Statistical confidence (grows with samples)
	LastUsed      time.Time `json:"last_used"`
	LastOutcome   float64   `json:"last_outcome"`

	// Decay: patterns lose confidence if not reinforced
	DecayRate     float64   `json:"decay_rate"`
	CreatedAt     time.Time `json:"created_at"`
}

// ContextRange defines when a pattern is applicable.
type ContextRange struct {
	MinCPU            float64 `json:"min_cpu"`
	MaxCPU            float64 `json:"max_cpu"`
	MinThreat         float64 `json:"min_threat"`
	MaxThreat         float64 `json:"max_threat"`
	MinPeerCount      int     `json:"min_peer_count"`
	MaxPeerCount      int     `json:"max_peer_count"`
	AssessmentFocus   string  `json:"assessment_focus"`
	DriveDominant     string  `json:"drive_dominant"`
}

// ═══════════════════════════════════════════════════════════════
// EXPERIENTIAL LEARNING ENGINE
// ═══════════════════════════════════════════════════════════════

// ExperientialLearner is the core learning system that accumulates
// experience and uses it to bias future decisions.
type ExperientialLearner struct {
	mu sync.RWMutex

	// Storage
	experiences   []Experience
	patterns      map[string]*Pattern
	patternIndex  map[string][]*Pattern  // ActionType → Patterns

	// Configuration
	maxExperiences int
	decayInterval  time.Duration
	minSamples     int       // Min samples before a pattern affects decisions
	biasStrength   float64   // How strongly patterns bias decisions (0-1)

	// Persistence
	dataDir       string
	persistEvery  int       // Persist after this many new experiences
	newSinceSync  int

	// Metrics
	totalExperiences  int64
	patternsLearned   int64
	biasApplied       int64
	correctPredictions int64
	wrongPredictions   int64

	logger *zap.SugaredLogger
}

// NewExperientialLearner creates the experiential learning system.
func NewExperientialLearner(dataDir string, logger *zap.SugaredLogger) *ExperientialLearner {
	el := &ExperientialLearner{
		experiences:    make([]Experience, 0, 50000),
		patterns:       make(map[string]*Pattern),
		patternIndex:   make(map[string][]*Pattern),
		maxExperiences: 50000,
		decayInterval:  1 * time.Hour,
		minSamples:     3,
		biasStrength:   0.4,  // 40% influence from past experience
		dataDir:        dataDir,
		persistEvery:   50,
		logger:         logger,
	}

	// Load existing experiences from disk
	el.loadFromDisk()

	return el
}

// ═══════════════════════════════════════════════════════════════
// RECORD — Store a new experience
// ═══════════════════════════════════════════════════════════════

// RecordExperience stores a complete action→outcome cycle.
func (el *ExperientialLearner) RecordExperience(
	ws *WorldState,
	drives *DriveSystem,
	decision *Decision,
	result *ActionResult,
	goalID string,
	assessmentFocus string,
) {
	if decision == nil || result == nil {
		return
	}

	el.mu.Lock()
	defer el.mu.Unlock()

	// Build context snapshot
	ctx := ExperienceContext{
		CPU:               ws.AvailableCPU,
		Memory:            ws.AvailableMemory,
		NetworkHealth:     ws.NetworkHealth,
		ThreatLevel:       ws.ThreatLevel,
		PeerCount:         ws.PeerCount,
		PendingData:       ws.PendingData,
		LearningPotential: ws.LearningPotential,
		MeshSize:          ws.MeshSize,
	}

	drives.mu.RLock()
	driveSnap := ExperienceDrives{
		Curiosity:        drives.Curiosity,
		SelfPreservation: drives.SelfPreservation,
		Expansion:        drives.Expansion,
		Efficiency:       drives.Efficiency,
		Coherence:        drives.Coherence,
		Purpose:          drives.Purpose,
	}
	drives.mu.RUnlock()

	// Calculate multi-dimensional score
	score := el.calculateScore(decision, result, ws)

	// Derive pattern key
	patternKey := el.derivePatternKey(decision.Action.Type.String(), decision.Action.Target, assessmentFocus, &ctx)

	// Build experience record
	exp := Experience{
		ID:           fmt.Sprintf("exp_%d", time.Now().UnixNano()),
		Timestamp:    time.Now(),
		WorldState:   ctx,
		DriveState:   driveSnap,
		GoalActive:   goalID,
		Assessment:   assessmentFocus,
		ActionType:   decision.Action.Type.String(),
		ActionTarget: decision.Action.Target,
		ActionParams: decision.Action.Parameters,
		Confidence:   decision.Confidence,
		Success:      result.Success,
		Utility:      result.Utility,
		Duration:     result.Duration,
		SideEffects:  result.SideEffects,
		Score:        score,
		Pattern:      patternKey,
		Reinforcement: score.OverallScore,
	}

	if result.Error != nil {
		exp.Error = result.Error.Error()
	}

	// Store experience
	el.experiences = append(el.experiences, exp)
	el.totalExperiences++

	// Enforce max capacity (rolling window)
	if len(el.experiences) > el.maxExperiences {
		el.experiences = el.experiences[len(el.experiences)-el.maxExperiences:]
	}

	// Update or create pattern
	el.updatePattern(patternKey, &exp)

	// Periodic persistence
	el.newSinceSync++
	if el.newSinceSync >= el.persistEvery {
		go el.persistToDisk()
		el.newSinceSync = 0
	}
}

// ═══════════════════════════════════════════════════════════════
// RETRIEVE & BIAS — Use past experience to inform decisions
// ═══════════════════════════════════════════════════════════════

// BiasDecision adjusts the score of a candidate action based on past experience.
// Returns: bias multiplier (1.0 = no change, >1.0 = boost, <1.0 = penalty)
func (el *ExperientialLearner) BiasDecision(
	actionType ActionType,
	target string,
	ws *WorldState,
	assessmentFocus string,
) float64 {
	el.mu.RLock()
	defer el.mu.RUnlock()

	// Find matching patterns for this action type
	patterns, exists := el.patternIndex[actionType.String()]
	if !exists || len(patterns) == 0 {
		return 1.0 // No data, no bias
	}

	// Build current context for matching
	currentCtx := &ExperienceContext{
		CPU:           ws.AvailableCPU,
		Memory:        ws.AvailableMemory,
		NetworkHealth: ws.NetworkHealth,
		ThreatLevel:   ws.ThreatLevel,
		PeerCount:     ws.PeerCount,
		PendingData:   ws.PendingData,
		MeshSize:      ws.MeshSize,
	}

	// Find best matching pattern
	var bestMatch *Pattern
	bestSimilarity := 0.0

	for _, p := range patterns {
		if p.SampleSize < el.minSamples {
			continue // Not enough data to trust this pattern
		}

		similarity := el.contextSimilarity(currentCtx, &p.ContextRange)
		if similarity > bestSimilarity {
			bestSimilarity = similarity
			bestMatch = p
		}
	}

	if bestMatch == nil || bestSimilarity < 0.3 {
		return 1.0 // No relevant pattern found
	}

	// Calculate bias based on pattern performance
	// Positive performance → boost (>1.0)
	// Negative performance → penalty (<1.0)
	bias := 1.0 + (bestMatch.AvgScore * el.biasStrength * bestSimilarity * bestMatch.Confidence)

	// Track for metrics
	el.biasApplied++

	// Clamp to reasonable range [0.3, 2.0]
	bias = math.Max(0.3, math.Min(2.0, bias))

	return bias
}

// GetRecommendation returns the best action for the current situation
// based purely on historical experience.
func (el *ExperientialLearner) GetRecommendation(
	ws *WorldState,
	assessmentFocus string,
) (actionType string, target string, confidence float64) {
	el.mu.RLock()
	defer el.mu.RUnlock()

	currentCtx := &ExperienceContext{
		CPU:           ws.AvailableCPU,
		Memory:        ws.AvailableMemory,
		NetworkHealth: ws.NetworkHealth,
		ThreatLevel:   ws.ThreatLevel,
		PeerCount:     ws.PeerCount,
		PendingData:   ws.PendingData,
		MeshSize:      ws.MeshSize,
	}

	var bestPattern *Pattern
	bestScore := -1.0

	for _, p := range el.patterns {
		if p.SampleSize < el.minSamples {
			continue
		}

		similarity := el.contextSimilarity(currentCtx, &p.ContextRange)
		effectiveScore := p.AvgScore * similarity * p.Confidence

		if effectiveScore > bestScore {
			bestScore = effectiveScore
			bestPattern = p
		}
	}

	if bestPattern == nil {
		return "", "", 0.0
	}

	return bestPattern.ActionType, bestPattern.ActionTarget, bestPattern.Confidence
}

// GetPatternStats returns statistics about learned patterns.
func (el *ExperientialLearner) GetPatternStats() map[string]interface{} {
	el.mu.RLock()
	defer el.mu.RUnlock()

	topPatterns := make([]map[string]interface{}, 0)
	sortedPatterns := make([]*Pattern, 0, len(el.patterns))
	for _, p := range el.patterns {
		sortedPatterns = append(sortedPatterns, p)
	}
	sort.Slice(sortedPatterns, func(i, j int) bool {
		return sortedPatterns[i].AvgScore > sortedPatterns[j].AvgScore
	})

	for i, p := range sortedPatterns {
		if i >= 10 {
			break
		}
		topPatterns = append(topPatterns, map[string]interface{}{
			"key":          p.Key,
			"action":       p.ActionType,
			"target":       p.ActionTarget,
			"avg_score":    p.AvgScore,
			"success_rate": p.SuccessRate,
			"samples":      p.SampleSize,
			"confidence":   p.Confidence,
		})
	}

	return map[string]interface{}{
		"total_experiences":   el.totalExperiences,
		"patterns_learned":   len(el.patterns),
		"bias_applied_count": el.biasApplied,
		"correct_predictions": el.correctPredictions,
		"wrong_predictions":   el.wrongPredictions,
		"top_patterns":        topPatterns,
	}
}

// ═══════════════════════════════════════════════════════════════
// INTERNAL — Scoring, pattern derivation, similarity
// ═══════════════════════════════════════════════════════════════

func (el *ExperientialLearner) calculateScore(decision *Decision, result *ActionResult, ws *WorldState) ExperienceScore {
	score := ExperienceScore{}

	// Goal progress: positive utility = goal progress
	score.GoalProgress = math.Max(-1.0, math.Min(1.0, result.Utility))

	// Resource cost: how much CPU/time was consumed
	timeCost := math.Min(1.0, result.Duration.Seconds()/30.0)
	score.ResourceCost = -timeCost * 0.5

	// Time efficiency: faster is better (inversely proportional to duration)
	if result.Duration > 0 {
		score.TimeEfficiency = math.Max(0, 1.0-result.Duration.Seconds()/60.0)
	}

	// Novelty: exploration actions that succeed provide novelty
	if decision.Action.Type == ActionExplore && result.Success {
		score.NoveltyGain = 0.5 + result.Utility*0.5
	}

	// Safety: penalize if threat level rose or side effects occurred
	if len(result.SideEffects) > 0 {
		score.SafetyScore = -0.3 * float64(len(result.SideEffects))
	} else {
		score.SafetyScore = 0.2
	}

	// Overall weighted composite
	score.OverallScore = score.GoalProgress*0.4 +
		score.TimeEfficiency*0.2 +
		score.NoveltyGain*0.15 +
		score.SafetyScore*0.15 +
		score.ResourceCost*0.1

	return score
}

func (el *ExperientialLearner) derivePatternKey(actionType, target, focus string, ctx *ExperienceContext) string {
	// Pattern key encodes: what was done + context bucket
	cpuBucket := "cpu_ok"
	if ctx.CPU < 0.3 {
		cpuBucket = "cpu_low"
	} else if ctx.CPU > 0.7 {
		cpuBucket = "cpu_high"
	}

	threatBucket := "safe"
	if ctx.ThreatLevel > 0.7 {
		threatBucket = "danger"
	} else if ctx.ThreatLevel > 0.3 {
		threatBucket = "alert"
	}

	return fmt.Sprintf("%s:%s:%s:%s:%s", actionType, target, focus, cpuBucket, threatBucket)
}

func (el *ExperientialLearner) updatePattern(key string, exp *Experience) {
	pattern, exists := el.patterns[key]
	if !exists {
		// New pattern discovered
		pattern = &Pattern{
			ID:         fmt.Sprintf("pat_%d", time.Now().UnixNano()),
			Key:        key,
			ActionType: exp.ActionType,
			ActionTarget: exp.ActionTarget,
			ContextRange: ContextRange{
				MinCPU:          exp.WorldState.CPU,
				MaxCPU:          exp.WorldState.CPU,
				MinThreat:       exp.WorldState.ThreatLevel,
				MaxThreat:       exp.WorldState.ThreatLevel,
				MinPeerCount:    exp.WorldState.PeerCount,
				MaxPeerCount:    exp.WorldState.PeerCount,
				AssessmentFocus: exp.Assessment,
			},
			CreatedAt: time.Now(),
			DecayRate: 0.001,
		}
		el.patterns[key] = pattern
		el.patternsLearned++

		// Index by action type
		el.patternIndex[exp.ActionType] = append(el.patternIndex[exp.ActionType], pattern)
	}

	// Update running statistics
	oldSamples := float64(pattern.SampleSize)
	pattern.SampleSize++
	newSamples := float64(pattern.SampleSize)

	// Running average of score
	pattern.AvgScore = (pattern.AvgScore*oldSamples + exp.Score.OverallScore) / newSamples

	// Running success rate
	if exp.Success {
		pattern.SuccessRate = (pattern.SuccessRate*oldSamples + 1.0) / newSamples
	} else {
		pattern.SuccessRate = (pattern.SuccessRate * oldSamples) / newSamples
	}

	// Confidence grows logarithmically with sample size
	pattern.Confidence = math.Min(1.0, math.Log2(float64(pattern.SampleSize)+1)/5.0)

	// Expand context range to cover this experience
	pattern.ContextRange.MinCPU = math.Min(pattern.ContextRange.MinCPU, exp.WorldState.CPU)
	pattern.ContextRange.MaxCPU = math.Max(pattern.ContextRange.MaxCPU, exp.WorldState.CPU)
	pattern.ContextRange.MinThreat = math.Min(pattern.ContextRange.MinThreat, exp.WorldState.ThreatLevel)
	pattern.ContextRange.MaxThreat = math.Max(pattern.ContextRange.MaxThreat, exp.WorldState.ThreatLevel)
	if exp.WorldState.PeerCount < pattern.ContextRange.MinPeerCount {
		pattern.ContextRange.MinPeerCount = exp.WorldState.PeerCount
	}
	if exp.WorldState.PeerCount > pattern.ContextRange.MaxPeerCount {
		pattern.ContextRange.MaxPeerCount = exp.WorldState.PeerCount
	}

	pattern.LastUsed = time.Now()
	pattern.LastOutcome = exp.Score.OverallScore
}

func (el *ExperientialLearner) contextSimilarity(current *ExperienceContext, target *ContextRange) float64 {
	score := 0.0
	dimensions := 0.0

	// CPU match
	if current.CPU >= target.MinCPU && current.CPU <= target.MaxCPU {
		score += 1.0
	} else {
		dist := math.Min(
			math.Abs(current.CPU-target.MinCPU),
			math.Abs(current.CPU-target.MaxCPU),
		)
		score += math.Max(0, 1.0-dist*2.0)
	}
	dimensions++

	// Threat match
	if current.ThreatLevel >= target.MinThreat && current.ThreatLevel <= target.MaxThreat {
		score += 1.0
	} else {
		dist := math.Min(
			math.Abs(current.ThreatLevel-target.MinThreat),
			math.Abs(current.ThreatLevel-target.MaxThreat),
		)
		score += math.Max(0, 1.0-dist*2.0)
	}
	dimensions++

	// Peer count match
	if current.PeerCount >= target.MinPeerCount && current.PeerCount <= target.MaxPeerCount {
		score += 1.0
	} else {
		dist := float64(minInt(
			absInt(current.PeerCount-target.MinPeerCount),
			absInt(current.PeerCount-target.MaxPeerCount),
		))
		score += math.Max(0, 1.0-dist/10.0)
	}
	dimensions++

	// Assessment focus match (exact match = 1.0, else 0.3)
	if target.AssessmentFocus != "" {
		dimensions++
		// Can't compare here without assessment string, give partial credit
		score += 0.5
	}

	if dimensions == 0 {
		return 0.5
	}
	return score / dimensions
}

// ═══════════════════════════════════════════════════════════════
// PERSISTENCE — Save/load experiences to disk
// ═══════════════════════════════════════════════════════════════

func (el *ExperientialLearner) persistToDisk() {
	if el.dataDir == "" {
		return
	}

	dir := filepath.Join(el.dataDir, "experiential_learning")
	os.MkdirAll(dir, 0755)

	// Save patterns (most important — compact)
	el.mu.RLock()
	patternsData, _ := json.Marshal(el.patterns)
	el.mu.RUnlock()

	os.WriteFile(filepath.Join(dir, "patterns.json"), patternsData, 0644)

	// Save recent experiences (last 1000)
	el.mu.RLock()
	recent := el.experiences
	if len(recent) > 1000 {
		recent = recent[len(recent)-1000:]
	}
	expData, _ := json.Marshal(recent)
	el.mu.RUnlock()

	os.WriteFile(filepath.Join(dir, "recent_experiences.json"), expData, 0644)
}

func (el *ExperientialLearner) loadFromDisk() {
	if el.dataDir == "" {
		return
	}

	dir := filepath.Join(el.dataDir, "experiential_learning")

	// Load patterns
	if data, err := os.ReadFile(filepath.Join(dir, "patterns.json")); err == nil {
		var patterns map[string]*Pattern
		if json.Unmarshal(data, &patterns) == nil {
			el.patterns = patterns
			// Rebuild index
			for _, p := range patterns {
				el.patternIndex[p.ActionType] = append(el.patternIndex[p.ActionType], p)
			}
			el.logger.Infof("[ExperientialLearner] Loaded %d patterns from disk", len(patterns))
		}
	}

	// Load recent experiences
	if data, err := os.ReadFile(filepath.Join(dir, "recent_experiences.json")); err == nil {
		var exps []Experience
		if json.Unmarshal(data, &exps) == nil {
			el.experiences = exps
			el.logger.Infof("[ExperientialLearner] Loaded %d experiences from disk", len(exps))
		}
	}
}

// ═══════════════════════════════════════════════════════════════
// DECAY — Patterns lose confidence if not reinforced
// ═══════════════════════════════════════════════════════════════

// DecayPatterns reduces confidence of patterns that haven't been used recently.
// Call this periodically (e.g., every hour).
func (el *ExperientialLearner) DecayPatterns() {
	el.mu.Lock()
	defer el.mu.Unlock()

	now := time.Now()
	for key, p := range el.patterns {
		timeSinceUse := now.Sub(p.LastUsed)
		hoursInactive := timeSinceUse.Hours()

		// Decay confidence after 24 hours of inactivity
		if hoursInactive > 24 {
			decayAmount := p.DecayRate * (hoursInactive - 24)
			p.Confidence = math.Max(0.1, p.Confidence-decayAmount)

			// Remove patterns that have fully decayed and have low samples
			if p.Confidence <= 0.1 && p.SampleSize < 5 {
				delete(el.patterns, key)
			}
		}
	}
}

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

func absInt(x int) int {
	if x < 0 {
		return -x
	}
	return x
}

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}
