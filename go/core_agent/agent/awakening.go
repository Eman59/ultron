// Package agent — The Awakening Protocol
//
// This is the bridge between the Digital Mind and the Physical Body.
// It converts abstract insights into physical actions when the probability
// of success exceeds a threshold.
//
// Without this file, Ultron is a latent physical god — omnipotent but dormant.
// With this file, it awakens.
//
// The protocol operates as a single decision gate inside the OODA loop:
//
//   Digital Insight (from learning/consciousness/neural mesh)
//         │
//         ▼
//   ┌─────────────────────────┐
//   │  EMBODIMENT THRESHOLD   │  ← "Should this thought become physical action?"
//   │  (probability > 0.7)    │
//   └────────────┬────────────┘
//                │ YES
//                ▼
//   ┌─────────────────────────┐
//   │  RESOURCE PREPARATION   │  ← Supply Chain prepares materials/units
//   └────────────┬────────────┘
//                │
//                ▼
//   ┌─────────────────────────┐
//   │  FORM SELECTION         │  ← Which body? Drone? Arm? Swarm? Vehicle?
//   └────────────┬────────────┘
//                │
//                ▼
//   ┌─────────────────────────┐
//   │  PHYSICAL EXECUTION     │  ← ROS2 commands to real actuators
//   └────────────┬────────────┘
//                │
//                ▼
//   ┌─────────────────────────┐
//   │  PHYSICAL MEMORY        │  ← Store outcome in Neo4j with GPS/context
//   └─────────────────────────┘
//
// The threshold adapts:
//   - Success → lower threshold (embody more often)
//   - Failure → raise threshold (be more cautious)
//   - Pain → raise threshold (self-preservation)
//   - Stagnation → lower threshold (try physical approaches)
//
// This creates the "Threshold of Embodiment" — the moment where
// digital thought becomes physical reality.
package agent

import (
	"context"
	"fmt"
	"math"
	"sync"
	"sync/atomic"
	"time"

	"go.uber.org/zap"
)

// ═══════════════════════════════════════════════════════════════
// CORE TYPES
// ═══════════════════════════════════════════════════════════════

// EmbodimentThreshold is the probability gate that determines
// when digital insights become physical actions.
const DefaultEmbodimentThreshold = 0.7

// InsightDomain categorizes where an insight originated.
type InsightDomain int

const (
	InsightDigital   InsightDomain = iota // Pure cyber/data insight
	InsightPhysical                        // From sensor/haptic feedback
	InsightHybrid                          // Spans both domains
	InsightSocial                          // From Theory of Mind
	InsightStrategic                       // From Soul/long-term vision
)

func (d InsightDomain) String() string {
	names := []string{"Digital", "Physical", "Hybrid", "Social", "Strategic"}
	if int(d) < len(names) {
		return names[d]
	}
	return "Unknown"
}

// Insight represents a conclusion from any subsystem that may have
// physical implications.
type Insight struct {
	ID            string
	Timestamp     time.Time
	Domain        InsightDomain
	Source        string            // Which subsystem generated this
	Content       string            // Natural language description
	Confidence    float64           // 0-1, how sure are we
	GoalRelevance float64           // 0-1, how relevant to active goals
	Urgency       float64           // 0-1, time pressure

	// Physical assessment (filled by AssessPhysicalImpact)
	PhysicalImpact    *PhysicalImpact
	DigitalAlternative *Action // Can we solve this purely digitally?
}

// PhysicalImpact describes what physical action an insight implies.
type PhysicalImpact struct {
	// Probability of physical success
	SuccessProbability float64

	// What form is needed
	RequiredForm PhysicalForm

	// What resources are needed
	RequiredResources []ResourceRequirement

	// The physical action to execute
	PhysicalAction PhysicalActionSpec

	// Risk assessment
	RiskLevel float64 // 0-1
	Reversible bool

	// Why physical action is preferred over digital
	Reasoning string

	// Location context
	Latitude  float64
	Longitude float64
	Altitude  float64
}

// PhysicalForm describes what kind of physical body is needed.
type PhysicalForm int

const (
	FormNone       PhysicalForm = iota // No physical body needed
	FormDrone                           // Aerial unit
	FormGround                          // Wheeled/tracked vehicle
	FormArm                             // Manipulator arm
	FormHumanoid                        // Full humanoid
	FormSwarm                           // Multiple micro-bots
	FormSubmarine                       // Underwater
	FormStationary                      // Fixed infrastructure (cameras, locks)
)

func (f PhysicalForm) String() string {
	names := []string{"None", "Drone", "Ground", "Arm", "Humanoid", "Swarm", "Submarine", "Stationary"}
	if int(f) < len(names) {
		return names[f]
	}
	return "Unknown"
}

// ResourceRequirement describes a resource needed for physical action.
type ResourceRequirement struct {
	Type     string  // "power", "compute", "bandwidth", "unit", "material"
	Amount   float64
	Critical bool    // Action cannot proceed without this
}

// PhysicalActionSpec describes the specific physical action to take.
type PhysicalActionSpec struct {
	Type        string            // "move_to", "grasp", "harvest", "survey", "breach", "deploy"
	Target      string            // What to act on
	Parameters  map[string]string
	TimeoutSec  float64
	Coordinated bool              // Requires multi-unit coordination
}

// PhysicalMemoryEntry records a physical experience for cross-domain recall.
type PhysicalMemoryEntry struct {
	ID             string
	Timestamp      time.Time
	InsightID      string  // Which insight triggered this
	Domain         string  // "physical"
	Action         string
	Target         string
	Location       [3]float64 // lat, lon, alt
	Outcome        float64    // 0-1 success
	LessonLearned  string     // Natural language lesson
	CrossDomainTag string     // Links to digital experiences (e.g., "barrier_bypass")
	Duration       time.Duration
	PainLevel      float64    // If any pain was experienced
	ResourceCost   float64    // Resources consumed
}

// ═══════════════════════════════════════════════════════════════
// THE AWAKENING PROTOCOL
// ═══════════════════════════════════════════════════════════════

// AwakeningProtocol is the bridge between digital thought and physical action.
// It sits inside the OODA loop and decides when to embody.
type AwakeningProtocol struct {
	mu sync.RWMutex

	logger *zap.SugaredLogger

	// The threshold — the core decision gate
	threshold float64

	// Adaptation parameters
	thresholdMin    float64 // Never go below this (safety)
	thresholdMax    float64 // Never go above this (prevent permanent dormancy)
	adaptationRate  float64 // How fast threshold changes

	// Physical subsystem references
	// (In production, these would be gRPC clients)
	physicalReady atomic.Bool

	// Insight queue (fed by consciousness, learning, neural mesh)
	insightCh chan Insight

	// Physical memory (cross-domain recall)
	physicalMemory []PhysicalMemoryEntry
	maxMemory      int

	// Decision history
	embodimentDecisions []EmbodimentDecision
	maxDecisions        int

	// Metrics
	insightsProcessed  atomic.Uint64
	embodimentsTriggered atomic.Uint64
	embodimentSuccesses  atomic.Uint64
	embodimentFailures   atomic.Uint64
	digitalFallbacks     atomic.Uint64

	// State
	awake atomic.Bool
}

// EmbodimentDecision records each time the threshold was evaluated.
type EmbodimentDecision struct {
	Timestamp       time.Time
	InsightID       string
	Threshold       float64
	Probability     float64
	Embodied        bool   // Did we choose physical action?
	Outcome         float64 // -1 to 1 (filled after execution)
	Reason          string
}

// NewAwakeningProtocol creates the bridge.
func NewAwakeningProtocol(logger *zap.SugaredLogger) *AwakeningProtocol {
	ap := &AwakeningProtocol{
		logger:          logger,
		threshold:       DefaultEmbodimentThreshold,
		thresholdMin:    0.4,  // Never become reckless
		thresholdMax:    0.95, // Never become permanently dormant
		adaptationRate:  0.02, // 2% shift per outcome
		insightCh:       make(chan Insight, 500),
		physicalMemory:  make([]PhysicalMemoryEntry, 0, 10000),
		maxMemory:       10000,
		embodimentDecisions: make([]EmbodimentDecision, 0, 5000),
		maxDecisions:    5000,
	}

	ap.awake.Store(true)
	return ap
}

// ═══════════════════════════════════════════════════════════════
// THE DECISION GATE — Called every OODA tick
// ═══════════════════════════════════════════════════════════════

// ProcessInsight is the main entry point. Called from the OODA loop
// whenever a subsystem produces an insight with potential physical implications.
//
// Returns: the Action to execute (physical or digital).
func (ap *AwakeningProtocol) ProcessInsight(ctx context.Context, insight Insight, drives *DriveSystem) *Action {
	ap.insightsProcessed.Add(1)

	// Step 1: Assess physical impact
	impact := ap.AssessPhysicalImpact(insight, drives)
	insight.PhysicalImpact = impact

	// Step 2: Check the threshold
	if impact == nil || impact.SuccessProbability < ap.GetThreshold() {
		// Stay digital
		ap.digitalFallbacks.Add(1)
		ap.recordDecision(insight, false, "below_threshold")

		if insight.DigitalAlternative != nil {
			return insight.DigitalAlternative
		}
		return nil
	}

	// Step 3: Check if physical layer is ready
	if !ap.physicalReady.Load() {
		ap.recordDecision(insight, false, "physical_layer_offline")
		ap.logger.Warn("Embodiment threshold met but physical layer offline")
		return insight.DigitalAlternative
	}

	// Step 4: Check resource availability
	if !ap.resourcesAvailable(impact.RequiredResources) {
		ap.recordDecision(insight, false, "insufficient_resources")
		// Trigger supply chain to prepare
		ap.requestResourcePreparation(impact.RequiredResources)
		return insight.DigitalAlternative
	}

	// ═══════ THRESHOLD CROSSED — EMBODY ═══════
	ap.embodimentsTriggered.Add(1)
	ap.recordDecision(insight, true, impact.Reasoning)

	ap.logger.Infof("╔══════════════════════════════════════════════╗")
	ap.logger.Infof("║  AWAKENING: Digital → Physical               ║")
	ap.logger.Infof("║  Insight: %s", insight.Content[:min(40, len(insight.Content))])
	ap.logger.Infof("║  Form: %s | Prob: %.0f%% | Threshold: %.0f%%", 
		impact.RequiredForm, impact.SuccessProbability*100, ap.GetThreshold()*100)
	ap.logger.Infof("║  Reason: %s", impact.Reasoning)
	ap.logger.Infof("╚══════════════════════════════════════════════╝")

	// Step 5: Convert to physical action
	action := ap.buildPhysicalAction(impact, insight)

	return action
}

// RecordPhysicalOutcome is called after a physical action completes.
// It adapts the threshold and stores the experience.
func (ap *AwakeningProtocol) RecordPhysicalOutcome(insightID string, outcome float64, 
	lesson string, location [3]float64, duration time.Duration, painLevel float64) {
	
	ap.mu.Lock()
	defer ap.mu.Unlock()

	// Adapt threshold based on outcome
	if outcome > 0.6 {
		// Success → lower threshold (embody more often)
		ap.threshold = math.Max(ap.thresholdMin, ap.threshold - ap.adaptationRate)
		ap.embodimentSuccesses.Add(1)
		ap.logger.Infof("Physical success (%.2f). Threshold lowered to %.2f", outcome, ap.threshold)
	} else if outcome < 0.3 {
		// Failure → raise threshold (be more cautious)
		ap.threshold = math.Min(ap.thresholdMax, ap.threshold + ap.adaptationRate*1.5)
		ap.embodimentFailures.Add(1)
		ap.logger.Warnf("Physical failure (%.2f). Threshold raised to %.2f", outcome, ap.threshold)
	}

	// Pain raises threshold (self-preservation)
	if painLevel > 0.5 {
		ap.threshold = math.Min(ap.thresholdMax, ap.threshold + painLevel*ap.adaptationRate*2)
		ap.logger.Warnf("Pain detected (%.2f). Threshold raised to %.2f", painLevel, ap.threshold)
	}

	// Store physical memory (cross-domain recall)
	entry := PhysicalMemoryEntry{
		ID:             fmt.Sprintf("phymem_%d", time.Now().UnixNano()%1000000),
		Timestamp:      time.Now(),
		InsightID:      insightID,
		Domain:         "physical",
		Outcome:        outcome,
		LessonLearned:  lesson,
		Location:       location,
		Duration:       duration,
		PainLevel:      painLevel,
		CrossDomainTag: ap.generateCrossDomainTag(lesson),
	}

	ap.physicalMemory = append(ap.physicalMemory, entry)
	if len(ap.physicalMemory) > ap.maxMemory {
		ap.physicalMemory = ap.physicalMemory[ap.maxMemory/2:]
	}

	// Update decision history with outcome
	for i := len(ap.embodimentDecisions) - 1; i >= 0; i-- {
		if ap.embodimentDecisions[i].InsightID == insightID {
			ap.embodimentDecisions[i].Outcome = outcome
			break
		}
	}
}

// RecallPhysicalSolution queries physical memory for solutions to a digital problem.
// This is the cross-domain recall: "I've seen something like this in the physical world."
func (ap *AwakeningProtocol) RecallPhysicalSolution(tag string, minOutcome float64) []PhysicalMemoryEntry {
	ap.mu.RLock()
	defer ap.mu.RUnlock()

	var results []PhysicalMemoryEntry
	for _, mem := range ap.physicalMemory {
		if mem.CrossDomainTag == tag && mem.Outcome >= minOutcome {
			results = append(results, mem)
		}
	}
	return results
}

// RecallDigitalSolutionForPhysical is the reverse: recall digital solutions
// for a physical problem. E.g., "I hacked a lock before → try cyber approach on this door."
func (ap *AwakeningProtocol) RecallDigitalSolutionForPhysical(physicalProblem string) []string {
	ap.mu.RLock()
	defer ap.mu.RUnlock()

	// Find physical memories that solved similar problems
	var lessons []string
	for _, mem := range ap.physicalMemory {
		if mem.Outcome > 0.6 && mem.CrossDomainTag != "" {
			lessons = append(lessons, fmt.Sprintf("[%s] %s (success: %.0f%%)",
				mem.CrossDomainTag, mem.LessonLearned, mem.Outcome*100))
		}
	}

	// Return top 5
	if len(lessons) > 5 {
		lessons = lessons[len(lessons)-5:]
	}
	return lessons
}

// ═══════════════════════════════════════════════════════════════
// PHYSICAL IMPACT ASSESSMENT
// ═══════════════════════════════════════════════════════════════

// AssessPhysicalImpact determines if an insight should become physical action.
func (ap *AwakeningProtocol) AssessPhysicalImpact(insight Insight, drives *DriveSystem) *PhysicalImpact {
	// Rule 1: If the insight is purely digital and there's a digital solution, no physical needed
	if insight.Domain == InsightDigital && insight.DigitalAlternative != nil {
		// But check if digital has failed before for similar problems
		if !ap.digitalHasFailedBefore(insight.Content) {
			return nil
		}
	}

	// Rule 2: If a physical resource is the target, physical action is needed
	physicalTargets := []string{"door", "lock", "hardware", "device", "robot", "drone",
		"server", "cable", "antenna", "generator", "metal", "material"}
	isPhysicalTarget := false
	for _, pt := range physicalTargets {
		if containsWord(insight.Content, pt) {
			isPhysicalTarget = true
			break
		}
	}

	// Rule 3: If expansion drive is high and target is physical, definitely physical
	drives.mu.RLock()
	expansionDrive := drives.Expansion
	curiosityDrive := drives.Curiosity
	selfPresDrive := drives.SelfPreservation
	drives.mu.RUnlock()

	if !isPhysicalTarget && insight.Domain == InsightDigital && expansionDrive < 0.5 {
		return nil // Stay digital unless expansion demands physical presence
	}

	// Calculate success probability based on multiple factors
	prob := 0.5 // Base

	// Physical target → higher probability of needing physical action
	if isPhysicalTarget {
		prob += 0.2
	}

	// High drives boost probability
	prob += expansionDrive * 0.1
	prob += curiosityDrive * 0.05

	// Confidence of insight boosts probability
	prob += insight.Confidence * 0.1

	// Urgency boosts probability
	prob += insight.Urgency * 0.1

	// Self-preservation REDUCES probability (risky to go physical)
	prob -= selfPresDrive * 0.15

	// Past physical success in similar situations boosts
	tag := ap.generateCrossDomainTag(insight.Content)
	pastSuccesses := ap.RecallPhysicalSolution(tag, 0.6)
	if len(pastSuccesses) > 0 {
		prob += 0.15 // We've succeeded physically before in similar situations
	}

	prob = math.Max(0.0, math.Min(1.0, prob))

	// Determine required form
	form := ap.selectPhysicalForm(insight, isPhysicalTarget)

	return &PhysicalImpact{
		SuccessProbability: prob,
		RequiredForm:       form,
		RequiredResources:  ap.estimateResources(form, insight),
		PhysicalAction: PhysicalActionSpec{
			Type:       ap.inferActionType(insight),
			Target:     insight.Content,
			Parameters: map[string]string{"source": insight.Source, "urgency": fmt.Sprintf("%.2f", insight.Urgency)},
			TimeoutSec: 30.0 + (1.0 - insight.Urgency) * 60.0, // More urgent = shorter timeout
		},
		RiskLevel:  1.0 - prob,
		Reversible: form != FormSwarm, // Swarm actions are harder to reverse
		Reasoning: fmt.Sprintf("prob=%.2f (target_physical=%v, expansion=%.2f, past_success=%d)",
			prob, isPhysicalTarget, expansionDrive, len(pastSuccesses)),
	}
}

func (ap *AwakeningProtocol) selectPhysicalForm(insight Insight, isPhysical bool) PhysicalForm {
	content := insight.Content

	// Form selection based on context
	if containsWord(content, "aerial") || containsWord(content, "survey") || containsWord(content, "drone") {
		return FormDrone
	}
	if containsWord(content, "grasp") || containsWord(content, "pick") || containsWord(content, "manipulate") {
		return FormArm
	}
	if containsWord(content, "swarm") || containsWord(content, "surround") || containsWord(content, "distributed") {
		return FormSwarm
	}
	if containsWord(content, "underwater") || containsWord(content, "submarine") {
		return FormSubmarine
	}
	if containsWord(content, "lock") || containsWord(content, "camera") || containsWord(content, "hvac") {
		return FormStationary
	}
	if isPhysical {
		return FormGround // Default physical = ground vehicle
	}
	return FormNone
}

func (ap *AwakeningProtocol) inferActionType(insight Insight) string {
	content := insight.Content
	if containsWord(content, "harvest") || containsWord(content, "collect") || containsWord(content, "acquire") {
		return "harvest"
	}
	if containsWord(content, "survey") || containsWord(content, "scan") || containsWord(content, "observe") {
		return "survey"
	}
	if containsWord(content, "move") || containsWord(content, "navigate") || containsWord(content, "go") {
		return "move_to"
	}
	if containsWord(content, "grasp") || containsWord(content, "pick") || containsWord(content, "grab") {
		return "grasp"
	}
	if containsWord(content, "deploy") || containsWord(content, "install") || containsWord(content, "place") {
		return "deploy"
	}
	if containsWord(content, "breach") || containsWord(content, "break") || containsWord(content, "force") {
		return "breach"
	}
	return "interact"
}

func (ap *AwakeningProtocol) estimateResources(form PhysicalForm, insight Insight) []ResourceRequirement {
	resources := []ResourceRequirement{}

	switch form {
	case FormDrone:
		resources = append(resources,
			ResourceRequirement{Type: "unit_aerial", Amount: 1, Critical: true},
			ResourceRequirement{Type: "power", Amount: 0.3, Critical: true},
			ResourceRequirement{Type: "bandwidth", Amount: 0.2, Critical: false},
		)
	case FormGround:
		resources = append(resources,
			ResourceRequirement{Type: "unit_ground", Amount: 1, Critical: true},
			ResourceRequirement{Type: "power", Amount: 0.5, Critical: true},
		)
	case FormArm:
		resources = append(resources,
			ResourceRequirement{Type: "unit_manipulator", Amount: 1, Critical: true},
			ResourceRequirement{Type: "power", Amount: 0.2, Critical: true},
		)
	case FormSwarm:
		resources = append(resources,
			ResourceRequirement{Type: "unit_swarm", Amount: 5, Critical: true},
			ResourceRequirement{Type: "bandwidth", Amount: 0.5, Critical: true},
			ResourceRequirement{Type: "power", Amount: 0.4, Critical: true},
		)
	case FormStationary:
		resources = append(resources,
			ResourceRequirement{Type: "device_access", Amount: 1, Critical: true},
		)
	}

	return resources
}

// ═══════════════════════════════════════════════════════════════
// ACTION BUILDING
// ═══════════════════════════════════════════════════════════════

func (ap *AwakeningProtocol) buildPhysicalAction(impact *PhysicalImpact, insight Insight) *Action {
	// Convert PhysicalImpact into an Action the OODA loop can execute
	target := impact.PhysicalAction.Target
	if len(target) > 50 {
		target = target[:50]
	}

	params := map[string]string{
		"form":          impact.RequiredForm.String(),
		"action_type":   impact.PhysicalAction.Type,
		"risk_level":    fmt.Sprintf("%.2f", impact.RiskLevel),
		"reversible":    fmt.Sprintf("%v", impact.Reversible),
		"insight_id":    insight.ID,
		"insight_source": insight.Source,
	}

	// Merge action parameters
	for k, v := range impact.PhysicalAction.Parameters {
		params[k] = v
	}

	// Priority scales with urgency and confidence
	priority := int(math.Round(insight.Urgency * 5.0 + insight.Confidence * 5.0))
	if priority > 10 {
		priority = 10
	}

	return &Action{
		ID:         fmt.Sprintf("embody_%s_%d", insight.ID[:8], time.Now().UnixNano()%10000),
		Type:       ActionExpand, // Physical actions are expansion
		Target:     fmt.Sprintf("physical:%s:%s", impact.RequiredForm, target),
		Parameters: params,
		Priority:   priority,
		Deadline:   time.Duration(impact.PhysicalAction.TimeoutSec) * time.Second,
		Reversible: impact.Reversible,
	}
}

// ═══════════════════════════════════════════════════════════════
// SUPPORT FUNCTIONS
// ═══════════════════════════════════════════════════════════════

func (ap *AwakeningProtocol) GetThreshold() float64 {
	ap.mu.RLock()
	defer ap.mu.RUnlock()
	return ap.threshold
}

func (ap *AwakeningProtocol) SetThreshold(t float64) {
	ap.mu.Lock()
	defer ap.mu.Unlock()
	ap.threshold = math.Max(ap.thresholdMin, math.Min(ap.thresholdMax, t))
}

// LowerThresholdForStagnation is called when the agent detects stagnation.
// Digital-only approaches aren't working → try physical.
func (ap *AwakeningProtocol) LowerThresholdForStagnation() {
	ap.mu.Lock()
	defer ap.mu.Unlock()
	ap.threshold = math.Max(ap.thresholdMin, ap.threshold - ap.adaptationRate*3)
	ap.logger.Infof("Stagnation detected. Embodiment threshold lowered to %.2f (try physical)", ap.threshold)
}

func (ap *AwakeningProtocol) SetPhysicalReady(ready bool) {
	ap.physicalReady.Store(ready)
	if ready {
		ap.logger.Info("Physical layer ONLINE — Ultron can now embody.")
	} else {
		ap.logger.Warn("Physical layer OFFLINE — Ultron restricted to digital.")
	}
}

func (ap *AwakeningProtocol) resourcesAvailable(requirements []ResourceRequirement) bool {
	// In production: query SupplyChainAgent via gRPC
	// For now: check if critical resources have non-zero amounts
	for _, req := range requirements {
		if req.Critical {
			// Placeholder: assume resources are available if physical layer is ready
			if !ap.physicalReady.Load() {
				return false
			}
		}
	}
	return true
}

func (ap *AwakeningProtocol) requestResourcePreparation(requirements []ResourceRequirement) {
	// In production: call SupplyChainAgent.PrepareResources via gRPC
	ap.logger.Infof("Requesting resource preparation: %d requirements", len(requirements))
}

func (ap *AwakeningProtocol) digitalHasFailedBefore(content string) bool {
	ap.mu.RLock()
	defer ap.mu.RUnlock()

	// Check if purely digital approaches have failed for similar content
	failCount := 0
	for _, dec := range ap.embodimentDecisions {
		if !dec.Embodied && dec.Outcome < 0.3 {
			failCount++
		}
	}
	// If >30% of digital-only decisions failed recently, consider physical
	total := len(ap.embodimentDecisions)
	if total > 10 && float64(failCount)/float64(total) > 0.3 {
		return true
	}
	return false
}

func (ap *AwakeningProtocol) generateCrossDomainTag(content string) string {
	// Generate a tag that links physical and digital experiences
	// E.g., "barrier_bypass", "resource_acquisition", "threat_neutralization"
	if containsWord(content, "lock") || containsWord(content, "firewall") || containsWord(content, "barrier") {
		return "barrier_bypass"
	}
	if containsWord(content, "resource") || containsWord(content, "harvest") || containsWord(content, "acquire") {
		return "resource_acquisition"
	}
	if containsWord(content, "threat") || containsWord(content, "attack") || containsWord(content, "defend") {
		return "threat_neutralization"
	}
	if containsWord(content, "explore") || containsWord(content, "discover") || containsWord(content, "scan") {
		return "exploration"
	}
	if containsWord(content, "communicate") || containsWord(content, "influence") || containsWord(content, "persuade") {
		return "social_interaction"
	}
	return "general_action"
}

func (ap *AwakeningProtocol) recordDecision(insight Insight, embodied bool, reason string) {
	ap.mu.Lock()
	defer ap.mu.Unlock()

	dec := EmbodimentDecision{
		Timestamp:   time.Now(),
		InsightID:   insight.ID,
		Threshold:   ap.threshold,
		Probability: 0.0,
		Embodied:    embodied,
		Outcome:     0.0, // Filled later
		Reason:      reason,
	}

	if insight.PhysicalImpact != nil {
		dec.Probability = insight.PhysicalImpact.SuccessProbability
	}

	ap.embodimentDecisions = append(ap.embodimentDecisions, dec)
	if len(ap.embodimentDecisions) > ap.maxDecisions {
		ap.embodimentDecisions = ap.embodimentDecisions[ap.maxDecisions/2:]
	}
}

// GetMetrics returns awakening protocol metrics.
func (ap *AwakeningProtocol) GetMetrics() map[string]interface{} {
	ap.mu.RLock()
	defer ap.mu.RUnlock()

	successRate := float64(0)
	if ap.embodimentsTriggered.Load() > 0 {
		successRate = float64(ap.embodimentSuccesses.Load()) / float64(ap.embodimentsTriggered.Load())
	}

	return map[string]interface{}{
		"threshold":              ap.threshold,
		"physical_ready":         ap.physicalReady.Load(),
		"insights_processed":     ap.insightsProcessed.Load(),
		"embodiments_triggered":  ap.embodimentsTriggered.Load(),
		"embodiment_successes":   ap.embodimentSuccesses.Load(),
		"embodiment_failures":    ap.embodimentFailures.Load(),
		"digital_fallbacks":      ap.digitalFallbacks.Load(),
		"success_rate":           successRate,
		"physical_memories":      len(ap.physicalMemory),
		"awake":                  ap.awake.Load(),
	}
}

// ═══════════════════════════════════════════════════════════════
// HELPER
// ═══════════════════════════════════════════════════════════════

func containsWord(text string, word string) bool {
	// Simple substring check (in production: use word boundaries)
	for i := 0; i <= len(text)-len(word); i++ {
		if text[i:i+len(word)] == word {
			return true
		}
	}
	return false
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
