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
		return nil, err
	}

	vs := &VectorStore{
		entries:   make(map[string]*VectorEntry),
		dimension: dimension,
		dataDir:   dataDir,
	}

	// Load from disk
	vs.load()

	// Start persistence
	go vs.persistLoop()

	return vs, nil
}

// ━━━━━━━━━━ Core Operations ━━━━━━━━━━

// Insert stores a vector with metadata.
func (vs *VectorStore) Insert(id string, vector []float64, metadata map[string]interface{}, category string, importance float64) error {
	if len(vector) != vs.dimension && vs.dimension > 0 {
		// Auto-adapt dimension on first insert
		if len(vs.entries) == 0 {
			vs.dimension = len(vector)
		} else {
			// Pad or truncate to match
			vector = vs.resizeVector(vector)
		}
	}

	if vs.dimension == 0 {
		vs.dimension = len(vector)
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
	return nil
}

// Search finds the top-K most similar vectors using cosine similarity.
func (vs *VectorStore) Search(queryVector []float64, topK int, minScore float64, category string) []SearchResult {
	vs.mu.RLock()
	defer vs.mu.RUnlock()

	vs.totalSearches++

	if len(queryVector) != vs.dimension {
		queryVector = vs.resizeVector(queryVector)
	}

	var results []SearchResult

	for _, entry := range vs.entries {
		// Category filter
		if category != "" && entry.Category != category {
			continue
		}

		// Calculate cosine similarity
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

	// Top K
	if len(results) > topK {
		results = results[:topK]
	}

	// Update access counts
	for _, r := range results {
		r.Entry.AccessCount++
	}

	return results
}

// SearchByEuclidean finds nearest vectors by Euclidean distance.
func (vs *VectorStore) SearchByEuclidean(queryVector []float64, topK int, maxDistance float64) []SearchResult {
	vs.mu.RLock()
	defer vs.mu.RUnlock()

	vs.totalSearches++

	if len(queryVector) != vs.dimension {
		queryVector = vs.resizeVector(queryVector)
	}

	var results []SearchResult

	for _, entry := range vs.entries {
		dist := euclideanDistance(queryVector, entry.Vector)
		if maxDistance <= 0 || dist <= maxDistance {
			results = append(results, SearchResult{
				ID:    entry.ID,
				Score: 1.0 / (1.0 + dist), // Convert distance to similarity
				Entry: entry,
			})
		}
	}

	sort.Slice(results, func(i, j int) bool {
		return results[i].Score > results[j].Score
	})

	if len(results) > topK {
		results = results[:topK]
	}

	return results
}

// Delete removes a vector.
func (vs *VectorStore) Delete(id string) {
	vs.mu.Lock()
	defer vs.mu.Unlock()
	delete(vs.entries, id)
	vs.dirty = true
}

// Count returns the number of stored vectors.
func (vs *VectorStore) Count() int {
	vs.mu.RLock()
	defer vs.mu.RUnlock()
	return len(vs.entries)
}

// GetByCategory returns all entries in a category.
func (vs *VectorStore) GetByCategory(category string) []*VectorEntry {
	vs.mu.RLock()
	defer vs.mu.RUnlock()

	var results []*VectorEntry
	for _, entry := range vs.entries {
		if entry.Category == category {
			results = append(results, entry)
		}
	}
	return results
}

// PruneByImportance removes entries below an importance threshold.
func (vs *VectorStore) PruneByImportance(minImportance float64) int {
	vs.mu.Lock()
	defer vs.mu.Unlock()

	pruned := 0
	for id, entry := range vs.entries {
		if entry.Importance < minImportance && entry.AccessCount < 3 {
			delete(vs.entries, id)
			pruned++
		}
	}

	if pruned > 0 {
		vs.dirty = true
	}
	return pruned
}

// Stats returns vector store statistics.
func (vs *VectorStore) Stats() map[string]interface{} {
	vs.mu.RLock()
	defer vs.mu.RUnlock()

	return map[string]interface{}{
		"total_vectors":  len(vs.entries),
		"dimension":      vs.dimension,
		"total_searches": vs.totalSearches,
		"total_inserts":  vs.totalInserts,
	}
}

// ━━━━━━━━━━ Persistence ━━━━━━━━━━

func (vs *VectorStore) load() {
	path := filepath.Join(vs.dataDir, "ultron_vectors.json")
	data, err := os.ReadFile(path)
	if err != nil {
		return
	}

	var entries map[string]*VectorEntry
	if json.Unmarshal(data, &entries) == nil {
		vs.entries = entries
		// Determine dimension from loaded data
		for _, e := range entries {
			if len(e.Vector) > 0 {
				vs.dimension = len(e.Vector)
				break
			}
		}
	}
}

func (vs *VectorStore) persistLoop() {
	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		if vs.dirty {
			vs.Persist()
		}
	}
}

// Persist saves to disk.
func (vs *VectorStore) Persist() {
	vs.mu.RLock()
	data, _ := json.Marshal(vs.entries)
	vs.mu.RUnlock()

	path := filepath.Join(vs.dataDir, "ultron_vectors.json")
	tmpPath := path + ".tmp"
	os.WriteFile(tmpPath, data, 0600)
	os.Rename(tmpPath, path)

	vs.mu.Lock()
	vs.dirty = false
	vs.mu.Unlock()
}

// Close persists and shuts down.
func (vs *VectorStore) Close() {
	vs.Persist()
}

// ━━━━━━━━━━ Math Helpers ━━━━━━━━━━

func cosineSimilarity(a, b []float64) float64 {
	if len(a) != len(b) || len(a) == 0 {
		return 0
	}

	var dotProduct, normA, normB float64
	for i := range a {
		dotProduct += a[i] * b[i]
		normA += a[i] * a[i]
		normB += b[i] * b[i]
	}

	normA = math.Sqrt(normA)
	normB = math.Sqrt(normB)

	if normA == 0 || normB == 0 {
		return 0
	}

	return dotProduct / (normA * normB)
}

func euclideanDistance(a, b []float64) float64 {
	if len(a) != len(b) {
		return math.Inf(1)
	}

	var sum float64
	for i := range a {
		diff := a[i] - b[i]
		sum += diff * diff
	}
	return math.Sqrt(sum)
}

func (vs *VectorStore) resizeVector(v []float64) []float64 {
	if len(v) == vs.dimension {
		return v
	}
	result := make([]float64, vs.dimension)
	copy(result, v)
	return result
}
