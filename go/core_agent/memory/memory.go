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
	StoreSemanticKnowledge(ctx context.Context, knowledgeItem KnowledgeItem) error
	QuerySemanticKnowledge(ctx context.Context, query KnowledgeQuery) ([]KnowledgeItem, error)
	DeleteSemanticKnowledge(ctx context.Context, knowledgeId string) error

	// ━━━━ Episodic Memory (What I've done) ━━━━
	// Temporal sequence of actions and their outcomes
	StoreExperience(ctx context.Context, experience Experience) error
	QueryExperiences(ctx context.Context, query ExperienceQuery) ([]Experience, error)
	UpdateExperienceOutcome(ctx context.Context, experienceId string, outcome float64) error

	// ━━━━ Procedural Memory (How I do things) ━━━━
	// Learned strategies, algorithms, and decision patterns
	StoreStrategy(ctx context.Context, strategy Strategy) error
	QueryStrategy(ctx context.Context, strategyName string) (*Strategy, error)
	GetBestStrategyForContext(ctx context.Context, contextData []float64) (*Strategy, error)

	// ━━━━ Identity Persistence ━━━━
	// Drive state and self-model across restarts
	SaveDriveState(ctx context.Context, driveData interface{}) error
	LoadDriveState(ctx context.Context) (*DriveState, error)

	// ━━━━ Cross-node Synchronization ━━━━
	SyncWithPeerNode(ctx context.Context, peerNodeId string) error
	GetLastSyncTime(peerNodeId string) time.Time

	// ━━━━ Shorthand methods used by autonomy loop ━━━━
	QueryEpisodic(ctx context.Context, query EpisodicQuery) ([]EpisodicMemory, error)
	QuerySemantic(ctx context.Context, query SemanticQuery) ([]MemoryItem, error)
	StoreEpisodic(ctx context.Context, episode EpisodicMemory) error
	UpdateEpisodic(ctx context.Context, id string, outcome float64) error
	StoreProcedural(ctx context.Context, proc ProceduralMemory) error
}

// KnowledgeItem represents a piece of semantic knowledge.
type KnowledgeItem struct {
	KnowledgeId     string
	Content         string            // Human-readable content
	VectorEmbedding []float64         // Vector embedding for similarity search
	Category        string            // Classification
	ConfidenceLevel float64           // How sure are we this is correct (0-1)
	Source          string            // Where did this come from
	RelatedKnowledgeIds []string          // Related knowledge IDs
	Metadata        map[string]string
	CreatedAt       time.Time
	AccessCount     int
	LastAccess      time.Time
	ImportanceLevel float64           // How important is this (0-1)
}

// KnowledgeQuery defines a query against semantic knowledge.
type KnowledgeQuery struct {
	// Vector similarity search
	QueryVector     []float64 // Query vector
	SimilarityThreshold float64   // Minimum similarity (0-1)

	// Filters
	CategoryFilter    string
	MinImportanceLevel float64
	SourceFilter      string

	// Limits
	ResultLimit       int
}

// Experience represents a single experience or event.
type Experience struct {
	ExperienceId    string
	ActionType      string
	ActionTarget    string
	Context         map[string]interface{}
	Outcome         float64
	EmotionalImpact float64
	Timestamp       time.Time
	Duration        time.Duration
	Tags            []string
}

// ExperienceQuery defines a query against episodic memory.
type ExperienceQuery struct {
	ActionTypeFilter string
	MinOutcome       float64
	SinceTime        time.Time
	ResultLimit      int
	Tags             []string
}

// Strategy represents a learned procedural strategy.
type Strategy struct {
	StrategyId    string
	Name          string
	Description   string
	ContextVector []float64
	SuccessRate   float64
	UsageCount    int
	LastUsed      time.Time
	CreatedAt     time.Time
	Parameters    map[string]interface{}
}

// DriveState represents the persisted drive state across restarts.
type DriveState struct {
	DriveId          string
	DriveValues      map[string]float64
	Curiosity        float64
	SelfPreservation float64
	Expansion        float64
	Efficiency       float64
	Coherence        float64
	Purpose          float64
	UpdatedAt        time.Time
}

// ━━━━━━━━━━ Embedded Runtime Types ━━━━━━━━━━
// These types are used by embedded/runtime to bridge the memory interface.

// MemoryItem is a single item in semantic memory.
type MemoryItem struct {
	ID         string
	Content    string
	Embedding  []float64
	Category   string
	Confidence float64
	Source     string
	Importance float64
	CreatedAt  time.Time
}

// SemanticQuery is a query against semantic memory.
type SemanticQuery struct {
	Context   []float64 // Query embedding
	Limit     int
	Threshold float64
	Category  string
}

// EpisodicMemory is a single episodic memory record.
type EpisodicMemory struct {
	ID        string
	Timestamp time.Time
	Action    string
	Outcome   float64
	Context   map[string]interface{}
}

// EpisodicQuery is a query against episodic memory.
type EpisodicQuery struct {
	ActionType   string
	MinOutcome   float64
	Limit        int
	SimilarState []float64 // Optional: find episodes with similar state vector
}

// ProceduralMemory is a learned strategy stored in procedural memory.
type ProceduralMemory struct {
	Strategy    string
	Parameters  map[string]interface{}
	AvgUtility  float64
	SuccessRate float64
	SampleSize  int
	UsageCount  int
	UpdatedAt   time.Time
	Timestamp   time.Time
}
