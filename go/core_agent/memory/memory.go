// Package memory defines the persistent memory interface for Ultron.
// This is the layer that gives Ultron identity continuity across restarts,
// node failures, and distributed operation.
//
// Three memory systems (inspired by human cognition):
//   - Semantic Memory:   Facts and knowledge (Vector DB - Qdrant/Milvus)
//   - Episodic Memory:   Experiences and events (Graph DB - Neo4j)
//   - Procedural Memory: Learned strategies and skills (Key-Value - Redis)
package memory

import (
	"context"
	"time"
)

// MemorySystem is the unified interface to all memory subsystems.
type MemorySystem interface {
	// Connection management
	Connect(ctx context.Context) error
	Disconnect() error
	IsConnected() bool

	// ━━━━ Semantic Memory (What I know) ━━━━
	// Vector embeddings of concepts, facts, relationships
	StoreSemantic(ctx context.Context, item MemoryItem) error
	QuerySemantic(ctx context.Context, query SemanticQuery) ([]MemoryItem, error)
	DeleteSemantic(ctx context.Context, id string) error

	// ━━━━ Episodic Memory (What I've done) ━━━━
	// Temporal sequence of actions and their outcomes
	StoreEpisodic(ctx context.Context, episode EpisodicMemory) error
	QueryEpisodic(ctx context.Context, query EpisodicQuery) ([]EpisodicMemory, error)
	UpdateEpisodic(ctx context.Context, id string, outcome float64) error

	// ━━━━ Procedural Memory (How I do things) ━━━━
	// Learned strategies, algorithms, and decision patterns
	StoreProcedural(ctx context.Context, proc ProceduralMemory) error
	QueryProcedural(ctx context.Context, strategy string) (*ProceduralMemory, error)
	GetBestStrategy(ctx context.Context, context []float64) (*ProceduralMemory, error)

	// ━━━━ Identity Persistence ━━━━
	// Drive state and self-model across restarts
	SaveDriveState(ctx context.Context, drives interface{}) error
	LoadDriveState(ctx context.Context) (*DriveState, error)

	// ━━━━ Cross-node Synchronization ━━━━
	SyncWithPeer(ctx context.Context, peerID string) error
	GetLastSyncTime(peerID string) time.Time
}

// MemoryItem represents a piece of semantic knowledge.
type MemoryItem struct {
	ID          string
	Content     string            // Human-readable content
	Embedding   []float64         // Vector embedding for similarity search
	Category    string            // Classification
	Confidence  float64           // How sure are we this is correct (0-1)
	Source      string            // Where did this come from
	Connections []string          // Related memory IDs
	Metadata    map[string]string
	CreatedAt   time.Time
	AccessCount int
	LastAccess  time.Time
	Importance  float64           // How important is this (0-1)
}

// SemanticQuery defines a query against semantic memory.
type SemanticQuery struct {
	// Vector similarity search
	Context     []float64 // Query vector
	Threshold   float64   // Minimum similarity (0-1)

	// Filters
	Category    string
	MinImportance float64
	Source      string

	// Limits
	Limit       int
}

// EpisodicMemory represents a single experience/event.
type EpisodicMemory struct {
	ID          string
	Timestamp   time.Time
	Action      string     // What was done
	Context     []float64  // State when action was taken
	Outcome     float64    // Result (utility gained, -1 to 1)
	Duration    time.Duration
	GoalID      string     // Which goal this served
	Success     bool
	Lessons     []string   // What was learned
	SideEffects []string   // Unintended consequences
}

// EpisodicQuery defines a query against episodic memory.
type EpisodicQuery struct {
	// Find similar situations
	SimilarState []float64
	Threshold    float64

	// Filter by action type
	ActionType   string

	// Filter by outcome
	MinOutcome   float64
	MaxOutcome   float64

	// Temporal filters
	After        *time.Time
	Before       *time.Time

	// Limits
	Limit        int
}

// ProceduralMemory represents a learned strategy or skill.
type ProceduralMemory struct {
	ID          string
	Strategy    string              // Strategy name/identifier
	Context     []float64           // When to use this strategy
	Steps       []string            // Ordered steps to execute
	Parameters  map[string]float64  // Tuned parameters
	SuccessRate float64             // Historical success rate
	AvgUtility  float64             // Average utility when used
	SampleSize  int                 // How many times tested
	Timestamp   time.Time
	Domain      string              // What domain this applies to
}

// DriveState persists the agent's motivational state.
type DriveState struct {
	Curiosity        float64
	SelfPreservation float64
	Expansion        float64
	Efficiency       float64
	Coherence        float64
	Purpose          float64
	LastUpdated      time.Time
}

// ═══════════════════════════════════════════════════════════════════
// In-Memory Implementation (for when external DBs are unavailable)
// ═══════════════════════════════════════════════════════════════════

// EphemeralMemory is an in-process memory system for testing/fallback.
type EphemeralMemory struct {
	connected  bool
	semantic   map[string]*MemoryItem
	episodic   []*EpisodicMemory
	procedural map[string]*ProceduralMemory
	driveState *DriveState
}

// NewEphemeralMemory creates an in-memory implementation.
func NewEphemeralMemory() *EphemeralMemory {
	return &EphemeralMemory{
		semantic:   make(map[string]*MemoryItem),
		episodic:   make([]*EpisodicMemory, 0, 10000),
		procedural: make(map[string]*ProceduralMemory),
	}
}

func (m *EphemeralMemory) Connect(ctx context.Context) error {
	m.connected = true
	return nil
}

func (m *EphemeralMemory) Disconnect() error {
	m.connected = false
	return nil
}

func (m *EphemeralMemory) IsConnected() bool {
	return m.connected
}

func (m *EphemeralMemory) StoreSemantic(ctx context.Context, item MemoryItem) error {
	m.semantic[item.ID] = &item
	return nil
}

func (m *EphemeralMemory) QuerySemantic(ctx context.Context, query SemanticQuery) ([]MemoryItem, error) {
	results := make([]MemoryItem, 0)
	for _, item := range m.semantic {
		if query.Category != "" && item.Category != query.Category {
			continue
		}
		if item.Importance >= query.MinImportance {
			results = append(results, *item)
		}
		if len(results) >= query.Limit {
			break
		}
	}
	return results, nil
}

func (m *EphemeralMemory) DeleteSemantic(ctx context.Context, id string) error {
	delete(m.semantic, id)
	return nil
}

func (m *EphemeralMemory) StoreEpisodic(ctx context.Context, episode EpisodicMemory) error {
	m.episodic = append(m.episodic, &episode)
	if len(m.episodic) > 10000 {
		m.episodic = m.episodic[5000:]
	}
	return nil
}

func (m *EphemeralMemory) QueryEpisodic(ctx context.Context, query EpisodicQuery) ([]EpisodicMemory, error) {
	results := make([]EpisodicMemory, 0)
	limit := query.Limit
	if limit == 0 {
		limit = 10
	}

	// Reverse iterate (most recent first)
	for i := len(m.episodic) - 1; i >= 0 && len(results) < limit; i-- {
		ep := m.episodic[i]
		if query.ActionType != "" && ep.Action != query.ActionType {
			continue
		}
		if ep.Outcome >= query.MinOutcome {
			results = append(results, *ep)
		}
	}
	return results, nil
}

func (m *EphemeralMemory) UpdateEpisodic(ctx context.Context, id string, outcome float64) error {
	for _, ep := range m.episodic {
		if ep.ID == id {
			ep.Outcome = outcome
			ep.Success = outcome > 0.5
			return nil
		}
	}
	return nil
}

func (m *EphemeralMemory) StoreProcedural(ctx context.Context, proc ProceduralMemory) error {
	m.procedural[proc.Strategy] = &proc
	return nil
}

func (m *EphemeralMemory) QueryProcedural(ctx context.Context, strategy string) (*ProceduralMemory, error) {
	if proc, ok := m.procedural[strategy]; ok {
		return proc, nil
	}
	return nil, nil
}

func (m *EphemeralMemory) GetBestStrategy(ctx context.Context, contextVec []float64) (*ProceduralMemory, error) {
	var best *ProceduralMemory
	bestScore := -1.0

	for _, proc := range m.procedural {
		if proc.AvgUtility > bestScore {
			bestScore = proc.AvgUtility
			best = proc
		}
	}
	return best, nil
}

func (m *EphemeralMemory) SaveDriveState(ctx context.Context, drives interface{}) error {
	// Type assertion would happen here
	m.driveState = &DriveState{LastUpdated: time.Now()}
	return nil
}

func (m *EphemeralMemory) LoadDriveState(ctx context.Context) (*DriveState, error) {
	return m.driveState, nil
}

func (m *EphemeralMemory) SyncWithPeer(ctx context.Context, peerID string) error {
	return nil
}

func (m *EphemeralMemory) GetLastSyncTime(peerID string) time.Time {
	return time.Time{}
}
