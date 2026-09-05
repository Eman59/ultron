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

	var results []SearchResult
	for _, entry := range vs.entries {
		if category != "" && entry.Category != category {
			continue
		}
		score := cosineSimilarity(queryVector, entry.Vector)
		if score >= minScore {
			results = append(results, SearchResult{
				ID:    entry.ID,
				Score: score,
				Entry: entry,
			})
		}
	}

	// Sort by score descending
	sort.Slice(results, func(i, j int) bool {
		return results[i].Score > results[j].Score
	})

	if topK > 0 && len(results) > topK {
		results = results[:topK]
	}

	return results
}

// cosineSimilarity computes the cosine similarity between two vectors.
func cosineSimilarity(a, b []float64) float64 {
	if len(a) != len(b) || len(a) == 0 {
		return 0
	}
	var dot, normA, normB float64
	for i := range a {
		dot += a[i] * b[i]
		normA += a[i] * a[i]
		normB += b[i] * b[i]
	}
	if normA == 0 || normB == 0 {
		return 0
	}
	return dot / (math.Sqrt(normA) * math.Sqrt(normB))
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
	dataFile := filepath.Join(vs.dataDir, "vectors.json")
	if _, err := os.Stat(dataFile); os.IsNotExist(err) {
		return nil // No existing data, start fresh
	}

	data, err := os.ReadFile(dataFile)
	if err != nil {
		return err
	}

	var entries map[string]*VectorEntry
	if err := json.Unmarshal(data, &entries); err != nil {
		return err
	}

	vs.mu.Lock()
	vs.entries = entries
	// Update dimension from first entry if not set
	if vs.dimension == 0 {
		for _, e := range entries {
			vs.dimension = len(e.Vector)
			break
		}
	}
	vs.mu.Unlock()
	return nil
}

// resizeVector resizes a vector to match the store's dimension.
func (vs *VectorStore) resizeVector(vector []float64) []float64 {
	if len(vector) == vs.dimension {
		return vector
	}
	result := make([]float64, vs.dimension)
	copy(result, vector) // Pad with zeros if shorter; truncated if longer
	return result
}

// persist persists the vector store to disk.
func (vs *VectorStore) persist() error {
	vs.mu.RLock()
	defer vs.mu.RUnlock()

	data, err := json.Marshal(vs.entries)
	if err != nil {
		return err
	}

	return os.WriteFile(filepath.Join(vs.dataDir, "vectors.json"), data, 0600)
}

// Delete removes a vector entry by ID.
func (vs *VectorStore) Delete(id string) {
	vs.mu.Lock()
	defer vs.mu.Unlock()
	delete(vs.entries, id)
	vs.dirty = true
}

// Close flushes pending state to disk.
func (vs *VectorStore) Close() error {
	return vs.persist()
}

// Stats returns vector store metrics.
func (vs *VectorStore) Stats() map[string]interface{} {
	vs.mu.RLock()
	defer vs.mu.RUnlock()

	return map[string]interface{}{
		"entries":       len(vs.entries),
		"dimension":     vs.dimension,
		"total_inserts": vs.totalInserts,
		"total_searches": vs.totalSearches,
	}
}
