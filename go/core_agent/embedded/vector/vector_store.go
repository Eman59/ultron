// Package vector implements an embedded vector similarity search engine.
// Replaces Qdrant — no external process needed.
//
// Features:
//   - Cosine similarity search
//   - Euclidean distance search
//   - HNSW-like approximate nearest neighbor (simplified)
//   - Persistent to disk
//   - Supports high-dimensional embeddings (768, 1536, etc.)
//   - Concurrent-safe
//   - Used for semantic memory (find similar concepts/memories)
package vector

import (
	"encoding/json"
	"log"
	"math"
	"os"
	"path/filepath"
	"sort"
	"sync"
	"time"
)

// VectorEntry is a stored embedding with metadata.
type VectorEntry struct {
	ID         string                 `json:"id"`
	Vector     []float64              `json:"vector"`
	Metadata   map[string]interface{} `json:"metadata"`
	Category   string                 `json:"category"`
	Importance float64                `json:"importance"`
	CreatedAt  time.Time              `json:"created_at"`
	AccessCount int                   `json:"access_count"`
}

// SearchResult is a single search match.
type SearchResult struct {
	ID         string
	Score      float64 // Similarity score (0-1 for cosine)
	Entry      *VectorEntry
}

// VectorStore is the embedded vector search engine.
type VectorStore struct {
	mu sync.RWMutex

	// All stored vectors
	entries map[string]*VectorEntry

	// Dimension of vectors (all must match)
	dimension int

	// Persistence
	dataDir string
	dirty   bool

	// Stats
	totalSearches uint64
	totalInserts  uint64
}

// NewVectorStore creates an embedded vector store.
func NewVectorStore(dataDir string, dimension int) (*VectorStore, error) {
	if err := os.MkdirAll(dataDir, 0700); err != nil {
		log.Printf("Error creating directory: %v", err)
		return nil, err
	}

	vs := &VectorStore{
		entries:   make(map[string]*VectorEntry),
		dimension: dimension,
		dataDir:   dataDir,
	}

	// Load from disk
	if err := vs.load(); err != nil {
		log.Printf("Error loading from disk: %v", err)
	}

	// Start persistence
	go vs.persistLoop()

	log.Println("Vector store initialized")
	return vs, nil
}

// ━━━━━━━━━━ Core Operations ━━━━━━━━━━

// Insert stores a vector with metadata.
func (vs *VectorStore) Insert(id string, vector []float64, metadata map[string]interface{}, category string, importance float64) error {
	if len(vector) != vs.dimension && vs.dimension > 0 {
		// Auto-adapt dimension on first insert
		if len(vs.entries) == 0 {
			vs.dimension = len(vector)
			log.Printf("Auto-adapted dimension to %d", vs.dimension)
		} else {
			// Pad or truncate to match
			vector = vs.resizeVector(vector)
			log.Printf("Resized vector to dimension %d", vs.dimension)
		}
	}

	if vs.dimension == 0 {
		vs.dimension = len(vector)
		log.Printf("Set dimension to %d", vs.dimension)
	}

	vs.mu.Lock()
	defer vs.mu.Unlock()

	vs.entries[id] = &VectorEntry{
		ID:         id,
		Vector:     vector,
		Metadata:   metadata,
		Category:   category,
		Importance: importance,
		CreatedAt:  time.Now(),
	}

	vs.totalInserts++
	vs.dirty = true
	log.Printf("Inserted vector with ID %s", id)
	return nil
}

// Search finds the top-K most similar vectors using cosine similarity.
func (vs *VectorStore) Search(queryVector []float64, topK int, minScore float64, category string) []SearchResult {
	vs.mu.RLock()
	defer vs.mu.RUnlock()

	vs.totalSearches++
	log.Printf("Search query received with topK=%d, minScore=%f, category=%s", topK, minScore, category)

	if len(queryVector) != vs.dimension {
		queryVector = vs.resizeVector(queryVector)
		log.Printf("Resized query vector to dimension %d", vs.dimension)
	}

	// ... (rest of the function remains the same)
}

// persistLoop persists the vector store to disk.
func (vs *VectorStore) persistLoop() {
	ticker := time.NewTicker(time.Minute)
	defer ticker.Stop()

	for range ticker.C {
		vs.mu.RLock()
		if vs.dirty {
			vs.mu.RUnlock()
			if err := vs.persist(); err != nil {
				log.Printf("Error persisting vector store: %v", err)
			} else {
				vs.dirty = false
				log.Println("Vector store persisted")
			}
		} else {
			vs.mu.RUnlock()
		}
	}
}

// load loads the vector store from disk.
func (vs *VectorStore) load() error {
	// ... (rest of the function remains the same)
}

// resizeVector resizes a vector to match the store's dimension.
func (vs *VectorStore) resizeVector(vector []float64) []float64 {
	// ... (rest of the function remains the same)
}

// persist persists the vector store to disk.
func (vs *VectorStore) persist() error {
	// ... (rest of the function remains the same)
}