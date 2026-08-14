// Package memory — Structured Reasoning Memory
//
// This is NOT vector search. This is a THINKING memory system.
//
// Three interlocking structures:
//
//   1. EPISODIC LOG (What happened)
//      Append-only journal of every event, action, outcome.
//      "At 14:00, I did X, Y happened, I learned Z."
//      Queryable by time, action type, outcome, similarity.
//
//   2. KNOWLEDGE GRAPH (What I know)
//      Directed graph of concepts and their relationships.
//      "Component A" --depends_on--> "Component B"
//      "Action Learn" --leads_to--> "Higher Knowledge"
//      "High Threat" --requires--> "Defend Action"
//      Traversable: given a concept, find all related concepts.
//
//   3. RULE ENGINE (What I should do)
//      Forward-chaining inference rules.
//      IF condition THEN action WITH confidence.
//      Rules fire automatically when conditions are met.
//      Rules can create new rules (meta-learning).
//
// Integration:
//   - The episodic log FEEDS the knowledge graph (experience → knowledge)
//   - The knowledge graph FEEDS the rule engine (knowledge → decisions)
//   - The rule engine FEEDS the OODA loop (decisions → actions)
//   - Actions create new episodes (loop complete)
//
// Persistence:
//   - Episodic log: append-only file (never corrupts, survives crashes)
//   - Knowledge graph: periodic JSON dump (atomic write)
//   - Rules: loaded on start, updated by learning system
package memory

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"
)

// ═══════════════════════════════════════════════════════════════
// EPISODIC LOG — "What happened"
// ═══════════════════════════════════════════════════════════════

// Episode is a single event in Ultron's life.
type Episode struct {
	ID        string    `json:"id"`
	Timestamp time.Time `json:"timestamp"`

	// What happened
	Action    string  `json:"action"`     // What was done
	Target    string  `json:"target"`     // What it was done to
	Context   string  `json:"context"`    // Surrounding situation
	Outcome   float64 `json:"outcome"`    // How well it went (-1 to 1)
	Duration  int64   `json:"duration_us"` // How long it took

	// What was learned
	Lesson    string  `json:"lesson"`     // Extracted insight
	Surprise  float64 `json:"surprise"`   // How unexpected (0=expected, 1=shocking)

	// Links
	CausedBy  string  `json:"caused_by"`  // Previous episode that led to this
	LeadsTo   string  `json:"leads_to"`   // Next episode (set retrospectively)
	GoalID    string  `json:"goal_id"`    // Which goal this served
	Tags      []string `json:"tags"`
}

// EpisodicLog is the append-only journal.
type EpisodicLog struct {
	mu       sync.RWMutex
	episodes []Episode
	maxSize  int
	logFile  string

	// Indices for fast query
	byAction  map[string][]int // action → episode indices
	byTag     map[string][]int
	byOutcome [2][]int // [0]=negative, [1]=positive
}

// NewEpisodicLog creates the episodic memory.
func NewEpisodicLog(logFile string, maxSize int) *EpisodicLog {
	el := &EpisodicLog{
		episodes: make([]Episode, 0, maxSize),
		maxSize:  maxSize,
		logFile:  logFile,
		byAction: make(map[string][]int),
		byTag:    make(map[string][]int),
	}

	// Load existing log
	el.load()
	return el
}

// Record adds a new episode (append-only, never fails).
func (el *EpisodicLog) Record(ep Episode) {
	el.mu.Lock()
	defer el.mu.Unlock()

	if ep.ID == "" {
		ep.ID = fmt.Sprintf("ep_%d", time.Now().UnixNano())
	}
	if ep.Timestamp.IsZero() {
		ep.Timestamp = time.Now()
	}

	idx := len(el.episodes)
	el.episodes = append(el.episodes, ep)

	// Update indices
	el.byAction[ep.Action] = append(el.byAction[ep.Action], idx)
	for _, tag := range ep.Tags {
		el.byTag[tag] = append(el.byTag[tag], idx)
	}
	if ep.Outcome > 0 {
		el.byOutcome[1] = append(el.byOutcome[1], idx)
	} else if ep.Outcome < 0 {
		el.byOutcome[0] = append(el.byOutcome[0], idx)
	}

	// Append to file (crash-safe)
	el.appendToFile(ep)

	// Trim if over max
	if len(el.episodes) > el.maxSize {
		el.episodes = el.episodes[len(el.episodes)-el.maxSize:]
		// Rebuild indices (rare, only on overflow)
		el.rebuildIndices()
	}
}

// QueryByAction returns episodes where a specific action was taken.
func (el *EpisodicLog) QueryByAction(action string, limit int) []Episode {
	el.mu.RLock()
	defer el.mu.RUnlock()

	indices := el.byAction[action]
	return el.getByIndices(indices, limit)
}

// QueryByOutcome returns successful or failed episodes.
func (el *EpisodicLog) QueryByOutcome(positive bool, limit int) []Episode {
	el.mu.RLock()
	defer el.mu.RUnlock()

	bucket := 0
	if positive {
		bucket = 1
	}
	return el.getByIndices(el.byOutcome[bucket], limit)
}

// QueryRecent returns the N most recent episodes.
func (el *EpisodicLog) QueryRecent(limit int) []Episode {
	el.mu.RLock()
	defer el.mu.RUnlock()

	total := len(el.episodes)
	if limit > total {
		limit = total
	}
	result := make([]Episode, limit)
	copy(result, el.episodes[total-limit:])
	return result
}

// QuerySimilar finds episodes with similar action+context.
func (el *EpisodicLog) QuerySimilar(action, target string, limit int) []Episode {
	el.mu.RLock()
	defer el.mu.RUnlock()

	var matches []Episode
	for i := len(el.episodes) - 1; i >= 0 && len(matches) < limit; i-- {
		ep := el.episodes[i]
		if ep.Action == action || ep.Target == target {
			matches = append(matches, ep)
		}
	}
	return matches
}

// AverageOutcome returns the average outcome for a given action type.
func (el *EpisodicLog) AverageOutcome(action string) float64 {
	el.mu.RLock()
	defer el.mu.RUnlock()

	indices := el.byAction[action]
	if len(indices) == 0 {
		return 0
	}

	sum := 0.0
	for _, idx := range indices {
		if idx < len(el.episodes) {
			sum += el.episodes[idx].Outcome
		}
	}
	return sum / float64(len(indices))
}

func (el *EpisodicLog) getByIndices(indices []int, limit int) []Episode {
	total := len(indices)
	if limit > total {
		limit = total
	}
	result := make([]Episode, 0, limit)
	for i := total - 1; i >= total-limit && i >= 0; i-- {
		idx := indices[i]
		if idx < len(el.episodes) {
			result = append(result, el.episodes[idx])
		}
	}
	return result
}

func (el *EpisodicLog) appendToFile(ep Episode) {
	if el.logFile == "" {
		return
	}
	os.MkdirAll(filepath.Dir(el.logFile), 0755)
	f, err := os.OpenFile(el.logFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return
	}
	data, _ := json.Marshal(ep)
	f.Write(data)
	f.Write([]byte("\n"))
	f.Close()
}

func (el *EpisodicLog) load() {
	if el.logFile == "" {
		return
	}
	data, err := os.ReadFile(el.logFile)
	if err != nil {
		return
	}
	lines := strings.Split(strings.TrimSpace(string(data)), "\n")
	for _, line := range lines {
		if line == "" {
			continue
		}
		var ep Episode
		if json.Unmarshal([]byte(line), &ep) == nil {
			el.episodes = append(el.episodes, ep)
		}
	}
	el.rebuildIndices()
}

func (el *EpisodicLog) rebuildIndices() {
	el.byAction = make(map[string][]int)
	el.byTag = make(map[string][]int)
	el.byOutcome = [2][]int{}

	for i, ep := range el.episodes {
		el.byAction[ep.Action] = append(el.byAction[ep.Action], i)
		for _, tag := range ep.Tags {
			el.byTag[tag] = append(el.byTag[tag], i)
		}
		if ep.Outcome > 0 {
			el.byOutcome[1] = append(el.byOutcome[1], i)
		} else if ep.Outcome < 0 {
			el.byOutcome[0] = append(el.byOutcome[0], i)
		}
	}
}

// Size returns number of episodes.
func (el *EpisodicLog) Size() int {
	el.mu.RLock()
	defer el.mu.RUnlock()
	return len(el.episodes)
}

// ═══════════════════════════════════════════════════════════════
// KNOWLEDGE GRAPH — "What I know"
// ═══════════════════════════════════════════════════════════════

// KNode is a concept node in the knowledge graph.
type KNode struct {
	ID         string            `json:"id"`
	Label      string            `json:"label"`
	Type       string            `json:"type"` // "concept", "action", "component", "state", "goal"
	Properties map[string]string `json:"properties"`
	Weight     float64           `json:"weight"` // Importance (0-1)
	CreatedAt  time.Time         `json:"created_at"`
	AccessCount int              `json:"access_count"`
}

// KEdge is a directed relationship between nodes.
type KEdge struct {
	From     string  `json:"from"`
	To       string  `json:"to"`
	Relation string  `json:"relation"` // "causes", "requires", "improves", "conflicts", "part_of"
	Weight   float64 `json:"weight"`   // Strength of relationship (0-1)
	Evidence int     `json:"evidence"` // How many observations support this
}

// KnowledgeGraph is a directed graph of concepts and relationships.
type KnowledgeGraph struct {
	mu    sync.RWMutex
	nodes map[string]*KNode
	edges []KEdge

	// Adjacency indices
	outEdges map[string][]int // node_id → outgoing edge indices
	inEdges  map[string][]int // node_id → incoming edge indices

	// Persistence
	savePath string
}

// NewKnowledgeGraph creates the knowledge graph.
func NewKnowledgeGraph(savePath string) *KnowledgeGraph {
	kg := &KnowledgeGraph{
		nodes:    make(map[string]*KNode),
		edges:    make([]KEdge, 0),
		outEdges: make(map[string][]int),
		inEdges:  make(map[string][]int),
		savePath: savePath,
	}
	kg.load()
	return kg
}

// AddNode adds or updates a concept.
func (kg *KnowledgeGraph) AddNode(id, label, nodeType string, weight float64) {
	kg.mu.Lock()
	defer kg.mu.Unlock()

	if existing, ok := kg.nodes[id]; ok {
		existing.Weight = weight
		existing.AccessCount++
		return
	}

	kg.nodes[id] = &KNode{
		ID:         id,
		Label:      label,
		Type:       nodeType,
		Properties: make(map[string]string),
		Weight:     weight,
		CreatedAt:  time.Now(),
	}
}

// AddEdge adds or strengthens a relationship.
func (kg *KnowledgeGraph) AddEdge(from, to, relation string, weight float64) {
	kg.mu.Lock()
	defer kg.mu.Unlock()

	// Check if edge exists
	for i := range kg.edges {
		if kg.edges[i].From == from && kg.edges[i].To == to && kg.edges[i].Relation == relation {
			kg.edges[i].Weight = (kg.edges[i].Weight + weight) / 2 // Average
			kg.edges[i].Evidence++
			return
		}
	}

	// New edge
	idx := len(kg.edges)
	kg.edges = append(kg.edges, KEdge{
		From:     from,
		To:       to,
		Relation: relation,
		Weight:   weight,
		Evidence: 1,
	})
	kg.outEdges[from] = append(kg.outEdges[from], idx)
	kg.inEdges[to] = append(kg.inEdges[to], idx)
}

// Query finds all nodes reachable from a starting concept within N hops.
func (kg *KnowledgeGraph) Query(startID string, maxHops int) []*KNode {
	kg.mu.RLock()
	defer kg.mu.RUnlock()

	visited := make(map[string]bool)
	result := make([]*KNode, 0)
	queue := []struct {
		id   string
		hops int
	}{{startID, 0}}

	for len(queue) > 0 {
		current := queue[0]
		queue = queue[1:]

		if visited[current.id] || current.hops > maxHops {
			continue
		}
		visited[current.id] = true

		if node, ok := kg.nodes[current.id]; ok {
			node.AccessCount++
			result = append(result, node)
		}

		// Follow outgoing edges
		for _, edgeIdx := range kg.outEdges[current.id] {
			if edgeIdx < len(kg.edges) {
				edge := kg.edges[edgeIdx]
				if !visited[edge.To] {
					queue = append(queue, struct {
						id   string
						hops int
					}{edge.To, current.hops + 1})
				}
			}
		}
	}

	return result
}

// FindPath finds the shortest path between two concepts.
func (kg *KnowledgeGraph) FindPath(from, to string) []string {
	kg.mu.RLock()
	defer kg.mu.RUnlock()

	visited := make(map[string]bool)
	parent := make(map[string]string)
	queue := []string{from}
	visited[from] = true

	for len(queue) > 0 {
		current := queue[0]
		queue = queue[1:]

		if current == to {
			// Reconstruct path
			path := []string{to}
			for path[len(path)-1] != from {
				path = append(path, parent[path[len(path)-1]])
			}
			// Reverse
			for i, j := 0, len(path)-1; i < j; i, j = i+1, j-1 {
				path[i], path[j] = path[j], path[i]
			}
			return path
		}

		for _, edgeIdx := range kg.outEdges[current] {
			if edgeIdx < len(kg.edges) {
				neighbor := kg.edges[edgeIdx].To
				if !visited[neighbor] {
					visited[neighbor] = true
					parent[neighbor] = current
					queue = append(queue, neighbor)
				}
			}
		}
	}

	return nil // No path
}

// GetRelated returns nodes related by a specific relation type.
func (kg *KnowledgeGraph) GetRelated(nodeID, relation string) []*KNode {
	kg.mu.RLock()
	defer kg.mu.RUnlock()

	var result []*KNode
	for _, edgeIdx := range kg.outEdges[nodeID] {
		if edgeIdx < len(kg.edges) {
			edge := kg.edges[edgeIdx]
			if edge.Relation == relation {
				if node, ok := kg.nodes[edge.To]; ok {
					result = append(result, node)
				}
			}
		}
	}
	return result
}

// Save persists the graph to disk (atomic write).
func (kg *KnowledgeGraph) Save() error {
	kg.mu.RLock()
	defer kg.mu.RUnlock()

	if kg.savePath == "" {
		return nil
	}

	data := struct {
		Nodes map[string]*KNode `json:"nodes"`
		Edges []KEdge           `json:"edges"`
	}{kg.nodes, kg.edges}

	content, err := json.MarshalIndent(data, "", "  ")
	if err != nil {
		return err
	}

	os.MkdirAll(filepath.Dir(kg.savePath), 0755)
	tmpPath := kg.savePath + ".tmp"
	if err := os.WriteFile(tmpPath, content, 0644); err != nil {
		return err
	}
	return os.Rename(tmpPath, kg.savePath)
}

func (kg *KnowledgeGraph) load() {
	if kg.savePath == "" {
		return
	}
	data, err := os.ReadFile(kg.savePath)
	if err != nil {
		return
	}

	var loaded struct {
		Nodes map[string]*KNode `json:"nodes"`
		Edges []KEdge           `json:"edges"`
	}
	if json.Unmarshal(data, &loaded) == nil {
		kg.nodes = loaded.Nodes
		kg.edges = loaded.Edges
		// Rebuild indices
		for i, edge := range kg.edges {
			kg.outEdges[edge.From] = append(kg.outEdges[edge.From], i)
			kg.inEdges[edge.To] = append(kg.inEdges[edge.To], i)
		}
	}
}

// Size returns node and edge counts.
func (kg *KnowledgeGraph) Size() (nodes int, edges int) {
	kg.mu.RLock()
	defer kg.mu.RUnlock()
	return len(kg.nodes), len(kg.edges)
}

// ═══════════════════════════════════════════════════════════════
// RULE ENGINE — "What I should do" (forward-chaining inference)
// ═══════════════════════════════════════════════════════════════

// InferenceRule is a forward-chaining rule.
// IF conditions are met THEN perform action WITH confidence.
type InferenceRule struct {
	ID         string   `json:"id"`
	Name       string   `json:"name"`
	Conditions []string `json:"conditions"` // Concept IDs that must exist in context
	Action     string   `json:"action"`     // What to do
	Target     string   `json:"target"`     // What to do it to
	Confidence float64  `json:"confidence"` // 0-1
	Priority   int      `json:"priority"`   // Higher = fires first
	Source     string   `json:"source"`     // "learned", "hardcoded", "distilled"
	FireCount  int      `json:"fire_count"`
	SuccessRate float64 `json:"success_rate"`
}

// RuleEngine evaluates rules against current context.
type RuleEngine struct {
	mu    sync.RWMutex
	rules []InferenceRule
}

// NewRuleEngine creates the inference engine.
func NewRuleEngine() *RuleEngine {
	return &RuleEngine{
		rules: make([]InferenceRule, 0, 200),
	}
}

// AddRule adds an inference rule.
func (re *RuleEngine) AddRule(rule InferenceRule) {
	re.mu.Lock()
	defer re.mu.Unlock()
	re.rules = append(re.rules, rule)
}

// Evaluate fires all rules whose conditions are met.
// Returns matching rules sorted by priority × confidence.
type RuleFiring struct {
	Rule       InferenceRule
	Score      float64 // priority × confidence
}

func (re *RuleEngine) Evaluate(activeContext []string) []RuleFiring {
	re.mu.RLock()
	defer re.mu.RUnlock()

	contextSet := make(map[string]bool, len(activeContext))
	for _, c := range activeContext {
		contextSet[c] = true
	}

	var firings []RuleFiring

	for i := range re.rules {
		rule := &re.rules[i]
		// Check if ALL conditions are met
		allMet := true
		for _, cond := range rule.Conditions {
			if !contextSet[cond] {
				allMet = false
				break
			}
		}

		if allMet {
			rule.FireCount++
			firings = append(firings, RuleFiring{
				Rule:  *rule,
				Score: float64(rule.Priority) * rule.Confidence,
			})
		}
	}

	// Sort by score descending
	sort.Slice(firings, func(i, j int) bool {
		return firings[i].Score > firings[j].Score
	})

	return firings
}

// UpdateSuccess records whether a rule firing led to a good outcome.
func (re *RuleEngine) UpdateSuccess(ruleID string, success bool) {
	re.mu.Lock()
	defer re.mu.Unlock()

	for i := range re.rules {
		if re.rules[i].ID == ruleID {
			// Exponential moving average
			outcome := 0.0
			if success {
				outcome = 1.0
			}
			re.rules[i].SuccessRate = re.rules[i].SuccessRate*0.9 + outcome*0.1
			break
		}
	}
}

// PruneWeakRules removes rules with low success rate.
func (re *RuleEngine) PruneWeakRules(minFireCount int, minSuccessRate float64) int {
	re.mu.Lock()
	defer re.mu.Unlock()

	kept := make([]InferenceRule, 0, len(re.rules))
	pruned := 0

	for _, rule := range re.rules {
		if rule.FireCount >= minFireCount && rule.SuccessRate < minSuccessRate {
			pruned++
			continue
		}
		kept = append(kept, rule)
	}

	re.rules = kept
	return pruned
}

// Size returns number of rules.
func (re *RuleEngine) Size() int {
	re.mu.RLock()
	defer re.mu.RUnlock()
	return len(re.rules)
}

// ═══════════════════════════════════════════════════════════════
// REASONING MEMORY — Integrates all three systems
// ═══════════════════════════════════════════════════════════════

// ReasoningMemory is the complete structured memory system.
type ReasoningMemory struct {
	Episodes *EpisodicLog
	Graph    *KnowledgeGraph
	Rules    *RuleEngine

	// Auto-learning: episodes automatically create knowledge
	autoLearn bool
}

// NewReasoningMemory creates the full reasoning memory.
func NewReasoningMemory(dataDir string) *ReasoningMemory {
	os.MkdirAll(dataDir, 0755)

	return &ReasoningMemory{
		Episodes: NewEpisodicLog(
			filepath.Join(dataDir, "episodes.jsonl"),
			50000, // Keep last 50K episodes
		),
		Graph: NewKnowledgeGraph(
			filepath.Join(dataDir, "knowledge_graph.json"),
		),
		Rules:     NewRuleEngine(),
		autoLearn: true,
	}
}

// RecordAndLearn records an episode AND extracts knowledge from it.
func (rm *ReasoningMemory) RecordAndLearn(ep Episode) {
	// Record the episode
	rm.Episodes.Record(ep)

	if !rm.autoLearn {
		return
	}

	// Extract knowledge: action → outcome relationship
	rm.Graph.AddNode(ep.Action, ep.Action, "action", 0.5)
	if ep.Target != "" {
		rm.Graph.AddNode(ep.Target, ep.Target, "target", 0.3)
		if ep.Outcome > 0.3 {
			rm.Graph.AddEdge(ep.Action, ep.Target, "improves", ep.Outcome)
		} else if ep.Outcome < -0.3 {
			rm.Graph.AddEdge(ep.Action, ep.Target, "harms", -ep.Outcome)
		}
	}

	// If we've seen this action enough times with good outcomes, create a rule
	avgOutcome := rm.Episodes.AverageOutcome(ep.Action)
	episodes := rm.Episodes.QueryByAction(ep.Action, 100)
	if len(episodes) >= 5 && avgOutcome > 0.5 {
		rule := InferenceRule{
			ID:         fmt.Sprintf("learned_%s_%d", ep.Action, len(episodes)),
			Name:       fmt.Sprintf("Repeat %s (avg outcome: %.2f)", ep.Action, avgOutcome),
			Conditions: ep.Tags,
			Action:     ep.Action,
			Target:     ep.Target,
			Confidence: avgOutcome,
			Priority:   int(avgOutcome * 5),
			Source:     "episodic_learning",
		}
		rm.Rules.AddRule(rule)
	}
}

// Reason takes current context and returns the best action to take.
func (rm *ReasoningMemory) Reason(context []string) *RuleFiring {
	firings := rm.Rules.Evaluate(context)
	if len(firings) == 0 {
		return nil
	}
	return &firings[0]
}

// Save persists all memory to disk.
func (rm *ReasoningMemory) Save() {
	rm.Graph.Save()
}

// Stats returns memory statistics.
func (rm *ReasoningMemory) Stats() map[string]interface{} {
	nodes, edges := rm.Graph.Size()
	return map[string]interface{}{
		"episodes":   rm.Episodes.Size(),
		"graph_nodes": nodes,
		"graph_edges": edges,
		"rules":      rm.Rules.Size(),
		"auto_learn": rm.autoLearn,
	}
}
