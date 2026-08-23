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
	ExperienceId string
	// ... (rest of the code remains the same)