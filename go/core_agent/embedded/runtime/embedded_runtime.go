// Package runtime provides the single-binary runtime that replaces all external services.
//
// This module initializes ALL embedded subsystems and exposes them as the
// MemorySystem interface that the autonomy loop already uses.
//
// Result: go build → ./ultron → fully autonomous, zero dependencies.
package runtime

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"ultron/core_agent/embedded/graph"
	"ultron/core_agent/embedded/store"
	"ultron/core_agent/embedded/vector"
	"ultron/core_agent/memory"

	"go.uber.org/zap"
)

// EmbeddedRuntime is the self-contained storage backend.
// It implements memory.MemorySystem using embedded engines.
type EmbeddedRuntime struct {
	// Embedded engines
	KV     *store.KVStore
	Graph  *graph.GraphEngine
	Vector *vector.VectorStore

	// Configuration
	dataDir string
	logger  *zap.SugaredLogger

	// State
	connected bool
}

// NewEmbeddedRuntime initializes all embedded storage engines.
func NewEmbeddedRuntime(logger *zap.SugaredLogger) (*EmbeddedRuntime, error) {
	// Default data directory: ~/.ultron/data
	home, _ := os.UserHomeDir()
	dataDir := filepath.Join(home, ".ultron", "data")

	// Allow override via env
	if dir := os.Getenv("ULTRON_DATA_DIR"); dir != "" {
		dataDir = dir
	}

	logger.Infof("Embedded runtime initializing in: %s", dataDir)

	// Initialize KV store (replaces Redis)
	kv, err := store.NewKVStore(filepath.Join(dataDir, "kv"))
	if err != nil {
		return nil, fmt.Errorf("KV store init failed: %w", err)
	}

	// Initialize Graph engine (replaces Neo4j)
	g, err := graph.NewGraphEngine(filepath.Join(dataDir, "graph"))
	if err != nil {
		return nil, fmt.Errorf("graph engine init failed: %w", err)
	}

	// Initialize Vector store (replaces Qdrant)
	v, err := vector.NewVectorStore(filepath.Join(dataDir, "vectors"), 128)
	if err != nil {
		return nil, fmt.Errorf("vector store init failed: %w", err)
	}

	runtime := &EmbeddedRuntime{
		KV:      kv,
		Graph:   g,
		Vector:  v,
		dataDir: dataDir,
		logger:  logger,
		connected: true,
	}

	logger.Info("Embedded runtime ready:")
	logger.Infof("  KV Store:     %s", filepath.Join(dataDir, "kv"))
	logger.Infof("  Graph Engine: %s", filepath.Join(dataDir, "graph"))
	logger.Infof("  Vector Store: %s", filepath.Join(dataDir, "vectors"))

	return runtime, nil
}

// ═══════════════════════════════════════════════════════════════
// memory.MemorySystem Interface Implementation
// ═══════════════════════════════════════════════════════════════

func (r *EmbeddedRuntime) Connect(ctx context.Context) error {
	r.connected = true
	return nil // Already connected — it's embedded
}

func (r *EmbeddedRuntime) Disconnect() error {
	r.KV.Close()
	r.Graph.Close()
	r.Vector.Close()
	r.connected = false
	return nil
}

func (r *EmbeddedRuntime) IsConnected() bool {
	return r.connected
}

// ━━━━ Semantic Memory (Vector Store) ━━━━

func (r *EmbeddedRuntime) StoreSemantic(ctx context.Context, item memory.MemoryItem) error {
	return r.Vector.Insert(
		item.ID,
		item.Embedding,
		map[string]interface{}{
			"content":    item.Content,
			"source":     item.Source,
			"confidence": item.Confidence,
		},
		item.Category,
		item.Importance,
	)
}

func (r *EmbeddedRuntime) QuerySemantic(ctx context.Context, query memory.SemanticQuery) ([]memory.MemoryItem, error) {
	results := r.Vector.Search(query.Context, query.Limit, query.Threshold, query.Category)

	var items []memory.MemoryItem
	for _, res := range results {
		content, _ := res.Entry.Metadata["content"].(string)
		source, _ := res.Entry.Metadata["source"].(string)
		confidence, _ := res.Entry.Metadata["confidence"].(float64)

		items = append(items, memory.MemoryItem{
			ID:         res.Entry.ID,
			Content:    content,
			Embedding:  res.Entry.Vector,
			Category:   res.Entry.Category,
			Confidence: confidence,
			Source:     source,
			Importance: res.Entry.Importance,
			CreatedAt:  res.Entry.CreatedAt,
		})
	}
	return items, nil
}

func (r *EmbeddedRuntime) DeleteSemantic(ctx context.Context, id string) error {
	r.Vector.Delete(id)
	return nil
}

// ━━━━ Episodic Memory (Graph Engine) ━━━━

func (r *EmbeddedRuntime) StoreEpisodic(ctx context.Context, episode memory.EpisodicMemory) error {
	r.Graph.AddEpisode(episode.ID, episode.Action, episode.Outcome, nil)
	return nil
}

func (r *EmbeddedRuntime) QueryEpisodic(ctx context.Context, query memory.EpisodicQuery) ([]memory.EpisodicMemory, error) {
	nodes := r.Graph.QueryEpisodes(query.ActionType, query.MinOutcome, query.Limit)

	var episodes []memory.EpisodicMemory
	for _, node := range nodes {
		action, _ := node.Properties["action"].(string)
		outcome, _ := node.Properties["outcome"].(float64)

		episodes = append(episodes, memory.EpisodicMemory{
			ID:        node.ID,
			Timestamp: node.CreatedAt,
			Action:    action,
			Outcome:   outcome,
		})
	}
	return episodes, nil
}

func (r *EmbeddedRuntime) UpdateEpisodic(ctx context.Context, id string, outcome float64) error {
	node := r.Graph.GetNode(id)
	if node != nil {
		node.Properties["outcome"] = outcome
	}
	return nil
}

// ━━━━ Procedural Memory (KV Store) ━━━━

func (r *EmbeddedRuntime) StoreProcedural(ctx context.Context, proc memory.ProceduralMemory) error {
	return r.KV.SetJSON("proc:"+proc.Strategy, proc)
}

func (r *EmbeddedRuntime) QueryProcedural(ctx context.Context, strategy string) (*memory.ProceduralMemory, error) {
	var proc memory.ProceduralMemory
	err := r.KV.GetJSON("proc:"+strategy, &proc)
	if err != nil {
		return nil, err
	}
	return &proc, nil
}

func (r *EmbeddedRuntime) GetBestStrategy(ctx context.Context, contextVec []float64) (*memory.ProceduralMemory, error) {
	// Find all procedural memories and return the one with highest success rate
	keys := r.KV.Keys("proc:")

	var best *memory.ProceduralMemory
	bestScore := -1.0

	for _, key := range keys {
		var proc memory.ProceduralMemory
		if err := r.KV.GetJSON(key, &proc); err == nil {
			if proc.AvgUtility > bestScore {
				bestScore = proc.AvgUtility
				best = &proc
			}
		}
	}
	return best, nil
}

// ━━━━ Identity Persistence ━━━━

func (r *EmbeddedRuntime) SaveDriveState(ctx context.Context, drives interface{}) error {
	return r.KV.SetJSON("identity:drives", drives)
}

func (r *EmbeddedRuntime) LoadDriveState(ctx context.Context) (*memory.DriveState, error) {
	var drives memory.DriveState
	err := r.KV.GetJSON("identity:drives", &drives)
	if err != nil {
		return nil, err
	}
	return &drives, nil
}

// ━━━━ Cross-node Sync ━━━━

func (r *EmbeddedRuntime) SyncWithPeer(ctx context.Context, peerID string) error {
	// In embedded mode: sync via P2P mesh if available
	r.KV.Set("sync:"+peerID, []byte(time.Now().Format(time.RFC3339)))
	return nil
}

func (r *EmbeddedRuntime) GetLastSyncTime(peerID string) time.Time {
	data, ok := r.KV.Get("sync:" + peerID)
	if !ok {
		return time.Time{}
	}
	t, _ := time.Parse(time.RFC3339, string(data))
	return t
}

// ═══════════════════════════════════════════════════════════════
// STATUS
// ═══════════════════════════════════════════════════════════════

// GetStatus returns the runtime status.
func (r *EmbeddedRuntime) GetStatus() map[string]interface{} {
	return map[string]interface{}{
		"mode":         "embedded_single_binary",
		"data_dir":     r.dataDir,
		"kv_stats":     r.KV.Stats(),
		"graph_stats":  r.Graph.Stats(),
		"vector_stats": r.Vector.Stats(),
		"connected":    r.connected,
	}
}
