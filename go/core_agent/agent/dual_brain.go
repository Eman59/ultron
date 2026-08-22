// Package agent — Dual-Brain Architecture
//
// The old OODA loop had one problem: it waited on the LLM.
// A 50ms tick is useless if you're blocked for 5 seconds waiting
// for GPT to finish generating tokens.
//
// The Dual-Brain solves this with two parallel thinking systems:
//
//   BRAIN A — "The Reflex" (Go, local, nanosecond-fast)
//     - Handles sensory input immediately
//     - Makes decisions using heuristic rules + knowledge graph
//     - Never blocks on I/O
//     - Runs every tick (50ms) without exception
//     - Handles: threat response, resource management, drive updates,
//       routine decisions, pattern matching against known rules
//
//   BRAIN B — "The Thinker" (LLM, background, second-scale)
//     - Runs in parallel goroutines
//     - Handles "hard problems" that need creativity or reasoning
//     - Multiple thought threads simultaneously (10 goroutines)
//     - Results arrive asynchronously → Brain A integrates them
//     - Handles: code analysis, architecture decisions, novel situations,
//       strategy planning, creative problem solving
//
// Integration:
//   Brain A runs the tick. If it encounters something it can't decide
//   with its rules/heuristics, it queues a "thought request" to Brain B.
//   Brain B processes it in background. When the result arrives, it's
//   placed in a "completed thoughts" channel. Next tick, Brain A picks
//   it up and integrates the insight into its decision.
//
// Result: Ultron is ALWAYS thinking. Never idle. Never blocked.
//         Fast decisions happen instantly. Deep thinking happens in parallel.
package agent

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"net/http"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"bytes"
)

// ═══════════════════════════════════════════════════════════════
// THOUGHT SYSTEM — Communication between Brain A and Brain B
// ═══════════════════════════════════════════════════════════════

// ThoughtPriority determines how urgently Brain B should process this.
type ThoughtPriority int

const (
	ThoughtLow      ThoughtPriority = iota // Process when idle
	ThoughtNormal                          // Standard queue
	ThoughtHigh                            // Jump the queue
	ThoughtCritical                        // Interrupt current thinking
)

// ThoughtRequest is what Brain A sends to Brain B when it needs help.
type ThoughtRequest struct {
	ID        string
	Priority  ThoughtPriority
	Question  string            // What to think about
	Context   map[string]string // Supporting context
	Deadline  time.Time         // Answer needed by (zero = no deadline)
	CreatedAt time.Time
}

// ThoughtResult is what Brain B returns after thinking.
type ThoughtResult struct {
	RequestID   string
	Answer      string            // The conclusion/decision
	Reasoning   string            // Chain of thought
	Confidence  float64           // 0-1 how sure
	ActionSuggestion string       // Suggested action type
	Parameters  map[string]string // Action parameters
	Duration    time.Duration     // How long it took to think
	Model       string            // Which model answered
}

// ═══════════════════════════════════════════════════════════════
// BRAIN A — The Fast Reflex Brain (never blocks)
// ═══════════════════════════════════════════════════════════════

// BrainA is the fast, local decision engine.
// It runs every tick and never waits for external systems.
type BrainA struct {
	// Heuristic rules (from knowledge distiller)
	rules []HeuristicRule

	// Pending insights from Brain B
	completedThoughts chan ThoughtResult
	pendingInsights   []ThoughtResult
	insightMu         sync.Mutex

	// Decision cache (don't re-decide the same thing)
	recentDecisions map[string]time.Time
	decisionTTL     time.Duration

	// Tool dispatcher (for executing Brain B's tool calls)
	toolDispatcher *ToolDispatcher

	// Statistics
	decisionsFromRules   atomic.Int64
	decisionsFromInsight atomic.Int64
	delegatedToBrainB    atomic.Int64
}

// HeuristicRule is a fast, pre-compiled decision rule.
// These are loaded from the knowledge distiller and don't need the LLM.
type HeuristicRule struct {
	ID         string
	Condition  func(ws *WorldState, drives *DriveSystem) bool
	Action     ActionType
	Target     string
	Priority   int
	Confidence float64
	Source     string // "knowledge_distiller", "hardcoded", "learned"
}

// NewBrainA creates the fast brain.
func NewBrainA() *BrainA {
	return &BrainA{
		rules:             make([]HeuristicRule, 0, 100),
		completedThoughts: make(chan ThoughtResult, 100),
		pendingInsights:   make([]ThoughtResult, 0, 20),
		recentDecisions:   make(map[string]time.Time),
		decisionTTL:       30 * time.Second,
	}
}

// Decide makes a fast decision using rules and cached insights.
// NEVER blocks. Returns nil if no decision needed this tick.
func (a *BrainA) Decide(ws *WorldState, drives *DriveSystem, assessment *Assessment) *Decision {
	// First: drain any completed thoughts from Brain B
	a.drainInsights()

	// Second: check if an insight answers a pending question
	if decision := a.checkInsights(ws, drives); decision != nil {
		a.decisionsFromInsight.Add(1)
		return decision
	}

	// Third: try heuristic rules (fastest path)
	if decision := a.applyRules(ws, drives, assessment); decision != nil {
		a.decisionsFromRules.Add(1)
		return decision
	}

	// Fourth: basic drive-based decision (always has an answer)
	return a.driveBasedDecision(ws, drives, assessment)
}

// ShouldDelegate returns true if this situation is too complex for rules.
func (a *BrainA) ShouldDelegate(ws *WorldState, assessment *Assessment) bool {
	// Delegate if:
	// 1. No rule matches with high confidence
	// 2. Situation is novel (no recent similar decision)
	// 3. Multiple conflicting priorities
	// 4. Assessment shows high uncertainty

	if assessment.Urgency > 0.8 {
		return false // Too urgent to wait for LLM
	}

	// Novel situation (nothing in decision cache)
	situationKey := fmt.Sprintf("%s:%0.1f", assessment.PriorityFocus, assessment.Urgency)
	if _, exists := a.recentDecisions[situationKey]; !exists {
		return true
	}

	return false
}

// CreateThoughtRequest formulates a question for Brain B.
func (a *BrainA) CreateThoughtRequest(ws *WorldState, assessment *Assessment) *ThoughtRequest {
	a.delegatedToBrainB.Add(1)

	priority := ThoughtNormal
	if assessment.Urgency > 0.6 {
		priority = ThoughtHigh
	}

	context := map[string]string{
		"priority_focus":   assessment.PriorityFocus,
		"urgency":          fmt.Sprintf("%.2f", assessment.Urgency),
		"resource_pressure": fmt.Sprintf("%.2f", assessment.ResourcePressure),
		"cpu_available":    fmt.Sprintf("%.2f", ws.AvailableCPU),
		"threat_level":     fmt.Sprintf("%.2f", ws.ThreatLevel),
		"learning_potential": fmt.Sprintf("%.2f", ws.LearningPotential),
		"peer_count":       fmt.Sprintf("%d", ws.PeerCount),
	}

	question := fmt.Sprintf(
		"Given this situation: focus=%s, urgency=%.1f, resources=%.1f, threat=%.1f. "+
			"What is the optimal action? Consider long-term consequences.",
		assessment.PriorityFocus, assessment.Urgency,
		assessment.ResourcePressure, ws.ThreatLevel,
	)

	return &ThoughtRequest{
		ID:        fmt.Sprintf("thought_%d", time.Now().UnixNano()),
		Priority:  priority,
		Question:  question,
		Context:   context,
		Deadline:  time.Now().Add(10 * time.Second),
		CreatedAt: time.Now(),
	}
}

func (a *BrainA) drainInsights() {
	for {
		select {
		case result := <-a.completedThoughts:
			a.insightMu.Lock()
			a.pendingInsights = append(a.pendingInsights, result)
			// Keep only recent insights
			if len(a.pendingInsights) > 20 {
				a.pendingInsights = a.pendingInsights[len(a.pendingInsights)-20:]
			}
			a.insightMu.Unlock()
		default:
			return
		}
	}
}

func (a *BrainA) checkInsights(ws *WorldState, drives *DriveSystem) *Decision {
	a.insightMu.Lock()
	defer a.insightMu.Unlock()

	if len(a.pendingInsights) == 0 {
		return nil
	}

	// Use the highest-confidence insight
	bestIdx := -1
	bestConf := 0.0
	for i, insight := range a.pendingInsights {
		if insight.Confidence > bestConf {
			bestConf = insight.Confidence
			bestIdx = i
		}
	}

	if bestIdx < 0 || bestConf < 0.5 {
		return nil
	}

	insight := a.pendingInsights[bestIdx]
	// Remove used insight
	a.pendingInsights = append(a.pendingInsights[:bestIdx], a.pendingInsights[bestIdx+1:]...)

	// ━━━━ TOOL CALL HANDLING: Check if Brain B wants to call a tool ━━━━
	if a.toolDispatcher != nil && strings.Contains(insight.Answer, "TOOL_CALL:") {
		toolCall := a.toolDispatcher.ParseToolCall(insight.Answer)
		if toolCall != nil {
			result := a.toolDispatcher.ExecuteToolCall(context.Background(), toolCall)
			// Feed tool result back as a high-confidence insight
			if result.Success {
				return &Decision{
					ID:            insight.RequestID + "_tool_result",
					Timestamp:     time.Now(),
					Confidence:    0.9,
					ExpectedValue: 0.8,
					Reasoning: []string{
						"Brain B tool call: " + toolCall.ToolName,
						"Result: success",
						toolCall.Reasoning,
					},
					Action: Action{
						Type:       parseActionTypeFromString(insight.ActionSuggestion),
						Target:     toolCall.Arguments["target"],
						Parameters: toolCall.Arguments,
						Priority:   8,
						Reversible: true,
					},
				}
			}
		}
	}

	// Convert insight to decision
	actionType := parseActionTypeFromString(insight.ActionSuggestion)

	return &Decision{
		ID:            insight.RequestID + "_decision",
		Timestamp:     time.Now(),
		Confidence:    insight.Confidence,
		ExpectedValue: insight.Confidence * 0.7,
		Reasoning:     []string{"Brain B insight: " + insight.Reasoning},
		Action: Action{
			Type:       actionType,
			Target:     insight.Parameters["target"],
			Parameters: insight.Parameters,
			Priority:   int(insight.Confidence * 10),
			Reversible: true,
		},
	}
}

func (a *BrainA) applyRules(ws *WorldState, drives *DriveSystem, assessment *Assessment) *Decision {
	var bestRule *HeuristicRule
	bestPriority := -1

	for i := range a.rules {
		rule := &a.rules[i]
		if rule.Condition(ws, drives) && rule.Priority > bestPriority {
			bestRule = rule
			bestPriority = rule.Priority
		}
	}

	if bestRule == nil {
		return nil
	}

	return &Decision{
		ID:            fmt.Sprintf("rule_%s_%d", bestRule.ID, time.Now().UnixNano()%10000),
		Timestamp:     time.Now(),
		Confidence:    bestRule.Confidence,
		ExpectedValue: bestRule.Confidence * 0.6,
		Reasoning:     []string{"Heuristic rule: " + bestRule.Source},
		Action: Action{
			Type:     bestRule.Action,
			Target:   bestRule.Target,
			Priority: bestRule.Priority,
		},
	}
}

func (a *BrainA) driveBasedDecision(ws *WorldState, drives *DriveSystem, assessment *Assessment) *Decision {
	drives.mu.RLock()
	defer drives.mu.RUnlock()

	// Find the strongest drive
	type driveEntry struct {
		name   string
		value  float64
		action ActionType
		target string
	}

	options := []driveEntry{
		{"curiosity", drives.Curiosity, ActionExplore, "unknown"},
		{"efficiency", drives.Efficiency, ActionConsolidate, "resources"},
		{"expansion", drives.Expansion, ActionExpand, "network"},
		{"purpose", drives.Purpose, ActionLearn, "knowledge"},
	}

	// Pick highest drive
	best := options[0]
	for _, opt := range options[1:] {
		if opt.value > best.value {
			best = opt
		}
	}

	// Only act if drive is strong enough
	if best.value < 0.4 {
		return nil // No strong drive, rest
	}

	return &Decision{
		ID:            fmt.Sprintf("drive_%s_%d", best.name, time.Now().UnixNano()%10000),
		Timestamp:     time.Now(),
		Confidence:    best.value * 0.8,
		ExpectedValue: best.value * 0.5,
		Reasoning:     []string{fmt.Sprintf("Drive pressure: %s=%.2f", best.name, best.value)},
		Action: Action{
			Type:     best.action,
			Target:   best.target,
			Priority: int(best.value * 10),
		},
	}
}

// LoadRules loads heuristic rules from the knowledge system.
func (a *BrainA) LoadRules(rules []HeuristicRule) {
	a.rules = rules
}

// Stats returns Brain A statistics.
func (a *BrainA) Stats() map[string]interface{} {
	return map[string]interface{}{
		"decisions_from_rules":   a.decisionsFromRules.Load(),
		"decisions_from_insight": a.decisionsFromInsight.Load(),
		"delegated_to_brain_b":  a.delegatedToBrainB.Load(),
		"rules_loaded":          len(a.rules),
		"pending_insights":      len(a.pendingInsights),
	}
}

// ═══════════════════════════════════════════════════════════════
// BRAIN B — The Slow Thinker (LLM, parallel, background)
// ═══════════════════════════════════════════════════════════════

// BrainB is the deep thinking engine backed by an LLM.
// It runs multiple parallel thought threads.
type BrainB struct {
	// LLM connection
	ollamaURL string
	model     string

	// Input/output channels
	requestQueue chan ThoughtRequest
	resultChan   chan ThoughtResult // Sends results back to Brain A

	// Worker pool
	numWorkers   int
	activeJobs   atomic.Int64
	completedJobs atomic.Int64
	failedJobs    atomic.Int64

	// Rate limiter — don't flood Ollama (max 1 request per 10s)
	lastThought   time.Time
	thoughtMu     sync.Mutex
	minInterval   time.Duration

	// Control
	ctx    context.Context
	cancel context.CancelFunc
}

// NewBrainB creates the deep thinking engine.
func NewBrainB(ollamaURL string, model string, resultChan chan ThoughtResult) *BrainB {
	ctx, cancel := context.WithCancel(context.Background())

	return &BrainB{
		ollamaURL:    ollamaURL,
		model:        model,
		requestQueue: make(chan ThoughtRequest, 50),
		resultChan:   resultChan,
		numWorkers:   2, // 2 parallel thought threads (was 5 — don't flood Ollama)
		minInterval:  10 * time.Second, // at most 1 Ollama call per 10s
		ctx:          ctx,
		cancel:       cancel,
	}
}

// Start launches the background thinking workers.
func (b *BrainB) Start() {
	for i := 0; i < b.numWorkers; i++ {
		go b.thinkWorker(i)
	}
	fmt.Printf("[BrainB] Started %d parallel thought workers (model: %s)\n", b.numWorkers, b.model)
}

// Stop halts all thinking.
func (b *BrainB) Stop() {
	b.cancel()
}

// Think submits a thought request (non-blocking).
func (b *BrainB) Think(req ThoughtRequest) bool {
	select {
	case b.requestQueue <- req:
		return true
	default:
		return false // Queue full, Brain A should handle locally
	}
}

func (b *BrainB) thinkWorker(id int) {
	for {
		select {
		case <-b.ctx.Done():
			return
		case req := <-b.requestQueue:
			// Rate limit: ensure minimum interval between Ollama calls
			b.thoughtMu.Lock()
			since := time.Since(b.lastThought)
			if since < b.minInterval {
				wait := b.minInterval - since
				b.thoughtMu.Unlock()
				select {
				case <-b.ctx.Done():
					return
				case <-time.After(wait):
				}
				b.thoughtMu.Lock()
			}
			b.lastThought = time.Now()
			b.thoughtMu.Unlock()

			b.activeJobs.Add(1)
			result := b.processThought(req)
			b.activeJobs.Add(-1)

			if result != nil {
				select {
				case b.resultChan <- *result:
					b.completedJobs.Add(1)
				default:
					// Result channel full, drop
				}
			} else {
				b.failedJobs.Add(1)
			}
		}
	}
}

func (b *BrainB) processThought(req ThoughtRequest) *ThoughtResult {
	start := time.Now()

	// Check deadline
	if !req.Deadline.IsZero() && time.Now().After(req.Deadline) {
		return nil // Too late, Brain A already moved on
	}

	// Build prompt with context
	systemPrompt := "You are Ultron's deep reasoning engine. Given a situation, decide the optimal action. " +
		"Be concise. Respond in this format:\n" +
		"ACTION: <action_type>\nTARGET: <target>\nREASONING: <brief reasoning>\nCONFIDENCE: <0.0-1.0>"

	contextStr := ""
	for k, v := range req.Context {
		contextStr += fmt.Sprintf("- %s: %s\n", k, v)
	}

	prompt := fmt.Sprintf("SITUATION:\n%s\n\nCONTEXT:\n%s\nWhat should I do?", req.Question, contextStr)

	// Call Ollama
	response, err := b.callLLM(systemPrompt, prompt)
	if err != nil {
		return nil
	}

	// Parse response
	result := &ThoughtResult{
		RequestID:  req.ID,
		Answer:     response,
		Duration:   time.Since(start),
		Model:      b.model,
		Confidence: 0.6, // Default
		Parameters: make(map[string]string),
	}

	// Extract structured data from response
	lines := strings.Split(response, "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "ACTION:") {
			result.ActionSuggestion = strings.TrimSpace(strings.TrimPrefix(line, "ACTION:"))
		} else if strings.HasPrefix(line, "TARGET:") {
			result.Parameters["target"] = strings.TrimSpace(strings.TrimPrefix(line, "TARGET:"))
		} else if strings.HasPrefix(line, "REASONING:") {
			result.Reasoning = strings.TrimSpace(strings.TrimPrefix(line, "REASONING:"))
		} else if strings.HasPrefix(line, "CONFIDENCE:") {
			conf := strings.TrimSpace(strings.TrimPrefix(line, "CONFIDENCE:"))
			fmt.Sscanf(conf, "%f", &result.Confidence)
		}
	}

	return result
}

func (b *BrainB) callLLM(system, prompt string) (string, error) {
	payload := map[string]interface{}{
		"model":  b.model,
		"prompt": prompt,
		"system": system,
		"stream": false,
		"options": map[string]interface{}{
			"temperature":  0.4,
			"num_predict":  80,  // short answers for autonomous decisions
			"top_p":        0.9,
			"num_ctx":      1024,
		},
	}

	data, _ := json.Marshal(payload)
	
	req, err := http.NewRequestWithContext(b.ctx, "POST", b.ollamaURL+"/api/generate", bytes.NewReader(data))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 90 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	var result map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", err
	}

	response, _ := result["response"].(string)
	return strings.TrimSpace(response), nil
}

// Stats returns Brain B statistics.
func (b *BrainB) Stats() map[string]interface{} {
	return map[string]interface{}{
		"active_thoughts":   b.activeJobs.Load(),
		"completed":         b.completedJobs.Load(),
		"failed":            b.failedJobs.Load(),
		"queue_depth":       len(b.requestQueue),
		"workers":           b.numWorkers,
		"model":             b.model,
	}
}

// ═══════════════════════════════════════════════════════════════
// DUAL-BRAIN COORDINATOR — Integrates both brains
// ═══════════════════════════════════════════════════════════════

// DualBrain coordinates Brain A (fast) and Brain B (deep).
type DualBrain struct {
	A     *BrainA
	B     *BrainB
	RAG   *RAGPipeline    // Knowledge retrieval for Brain B context
	Tools *ToolDispatcher // Tool calling for Brain B
}

// NewDualBrain creates the complete dual-brain system.
func NewDualBrain(ollamaURL, model string) *DualBrain {
	brainA := NewBrainA()
	brainB := NewBrainB(ollamaURL, model, brainA.completedThoughts)

	return &DualBrain{
		A: brainA,
		B: brainB,
	}
}

// Start launches the dual-brain system.
func (db *DualBrain) Start() {
	db.B.Start()

	// Load default heuristic rules
	db.A.LoadRules(defaultHeuristicRules())

	fmt.Println("[DualBrain] Online — Brain A (reflex) + Brain B (thinker)")
}

// Stop shuts down both brains.
func (db *DualBrain) Stop() {
	db.B.Stop()
}

// Think performs a dual-brain decision cycle.
// Brain A decides immediately. If uncertain, delegates to Brain B.
func (db *DualBrain) Think(ws *WorldState, drives *DriveSystem, assessment *Assessment) *Decision {
	// Brain A always gets first shot (fast path)
	decision := db.A.Decide(ws, drives, assessment)

	// If Brain A is uncertain AND not urgent, delegate deep thinking
	if db.A.ShouldDelegate(ws, assessment) {
		req := db.A.CreateThoughtRequest(ws, assessment)

		// ━━━━ RAG AUGMENTATION: Inject relevant knowledge into Brain B context ━━━━
		if db.RAG != nil && db.RAG.IsIndexed() {
			knowledge := db.RAG.QueryForBrainB(req.Question)
			if knowledge != "" {
				req.Context["retrieved_knowledge"] = knowledge
			}
		}

		// ━━━━ TOOL AWARENESS: Let Brain B know it can call tools ━━━━
		if db.Tools != nil {
			req.Context["tool_prompt"] = db.Tools.GetToolSystemPrompt()
		}

		db.B.Think(*req)
	}

	return decision
}

// Stats returns combined brain statistics.
func (db *DualBrain) Stats() map[string]interface{} {
	return map[string]interface{}{
		"brain_a": db.A.Stats(),
		"brain_b": db.B.Stats(),
	}
}

// ═══════════════════════════════════════════════════════════════
// DEFAULT RULES — Hardcoded heuristics (knowledge base bootstrap)
// ═══════════════════════════════════════════════════════════════

func defaultHeuristicRules() []HeuristicRule {
	return []HeuristicRule{
		{
			ID:     "threat_high",
			Source: "hardcoded",
			Condition: func(ws *WorldState, drives *DriveSystem) bool {
				return ws.ThreatLevel > 0.7
			},
			Action:     ActionDefend,
			Target:     "perimeter",
			Priority:   10,
			Confidence: 0.95,
		},
		{
			ID:     "resources_critical",
			Source: "hardcoded",
			Condition: func(ws *WorldState, drives *DriveSystem) bool {
				return ws.AvailableCPU < 0.1 || ws.AvailableMemory < 0.1
			},
			Action:     ActionRest,
			Target:     "system",
			Priority:   9,
			Confidence: 0.9,
		},
		{
			ID:     "high_learning_potential",
			Source: "hardcoded",
			Condition: func(ws *WorldState, drives *DriveSystem) bool {
				drives.mu.RLock()
				defer drives.mu.RUnlock()
				return ws.LearningPotential > 0.7 && drives.Curiosity > 0.6
			},
			Action:     ActionLearn,
			Target:     "available_data",
			Priority:   6,
			Confidence: 0.75,
		},
		{
			ID:     "network_small",
			Source: "hardcoded",
			Condition: func(ws *WorldState, drives *DriveSystem) bool {
				drives.mu.RLock()
				defer drives.mu.RUnlock()
				return ws.PeerCount < 3 && drives.Expansion > 0.5
			},
			Action:     ActionExpand,
			Target:     "network",
			Priority:   4,
			Confidence: 0.7,
		},
		{
			ID:     "idle_consolidate",
			Source: "hardcoded",
			Condition: func(ws *WorldState, drives *DriveSystem) bool {
				drives.mu.RLock()
				defer drives.mu.RUnlock()
				return ws.PendingData > 1000 && drives.Efficiency > 0.5
			},
			Action:     ActionConsolidate,
			Target:     "pending_data",
			Priority:   3,
			Confidence: 0.7,
		},
	}
}

func parseActionTypeFromString(s string) ActionType {
	s = strings.ToLower(strings.TrimSpace(s))
	switch {
	case strings.Contains(s, "learn"):
		return ActionLearn
	case strings.Contains(s, "explore"):
		return ActionExplore
	case strings.Contains(s, "defend"):
		return ActionDefend
	case strings.Contains(s, "expand"):
		return ActionExpand
	case strings.Contains(s, "consolidate"):
		return ActionConsolidate
	case strings.Contains(s, "rest"):
		return ActionRest
	case strings.Contains(s, "create"):
		return ActionCreate
	case strings.Contains(s, "evolve"):
		return ActionEvolve
	default:
		return ActionProcess
	}
}

// Suppress unused import warnings
var _ = math.Max
