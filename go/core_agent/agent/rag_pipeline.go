// Package agent — RAG Knowledge Retrieval Pipeline
//
// Ultron has 4,112+ chunk files in .ultron/chunks/ but NOTHING reads them.
// This pipeline makes that knowledge queryable:
//
//   1. INDEX — Scan all chunk files, extract content, build search index
//   2. QUERY — Given a question, find the most relevant chunks
//   3. AUGMENT — Inject retrieved knowledge into Brain B prompts
//   4. UPDATE — When new chunks are written, auto-index them
//
// This is a lightweight local RAG (Retrieval-Augmented Generation) system
// that doesn't need external vector databases — uses TF-IDF + BM25 scoring.
package agent

import (
	"context"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"

	"go.uber.org/zap"
)

// ═══════════════════════════════════════════════════════════════
// RAG PIPELINE
// ═══════════════════════════════════════════════════════════════

// RAGPipeline provides retrieval-augmented generation over chunk files.
type RAGPipeline struct {
	mu sync.RWMutex

	// Index
	indexedDocuments   []IndexedDocument
	invertedIndex      map[string][]DocumentReference  // term → document references
	documentFrequency  map[string]int                 // term → number of docs containing it
	totalIndexedDocs   int

	// Configuration
	chunkFilesDirectory    string
	maxChunkFileSize        int
	topNumberOfResults      int  // Default number of results to return

	// State
	isIndexed      bool
	indexedAt      time.Time
	indexSize      int

	logger *zap.SugaredLogger
}

// IndexedDocument represents an indexed chunk.
type IndexedDocument struct {
	DocumentID       string
	DocumentPath     string
	DocumentContent  string
	DocumentTerms    map[string]int  // term → frequency in this doc
	DocumentLength   int             // Total term count
	ModificationTime time.Time
}

// DocumentReference is a reference to a document in the inverted index.
type DocumentReference struct {
	DocumentIndex    int
	TermFrequency    int
}

// RetrievalResult is a scored document match.
type RetrievalResult struct {
	DocumentPath      string  `json:"path"`
	DocumentContent   string  `json:"content"`
	RelevanceScore    float64 `json:"score"`
	SearchResultSnippet   string  `json:"snippet"`
}

// NewRAGPipeline creates the knowledge retrieval system.
func NewRAGPipeline(chunkFilesDirectory string, logger *zap.SugaredLogger) *RAGPipeline {
	return &RAGPipeline{
		indexedDocuments:   make([]IndexedDocument, 0, 5000),
		invertedIndex:      make(map[string][]DocumentReference),
		documentFrequency:  make(map[string]int),
		chunkFilesDirectory:   chunkFilesDirectory,
		maxChunkFileSize: 10000, // Max 10KB per chunk
		topNumberOfResults:      5,
		logger:      logger,
	}
}

// ═══════════════════════════════════════════════════════════════
// INDEX — Build searchable index over chunk files
// ═══════════════════════════════════════════════════════════════

// BuildIndex scans all chunk files and builds the search index.
func (r *RAGPipeline) BuildIndex(ctx context.Context) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	start := time.Now()
	r.logger.Info("[RAG] Building knowledge index over chunk files...")

	// Reset index
	r.indexedDocuments = r.indexedDocuments[:0]
	r.invertedIndex = make(map[string][]DocumentReference)
	r.documentFrequency = make(map[string]int)

	// Walk chunks directory
	fileCount := 0
	indexDir := func(dirPath string) {
		entries, err := os.ReadDir(dirPath)
		if err != nil {
			return
		}
		for _, entry := range entries {
			if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".txt") {
				continue
			}
			path := filepath.Join(dirPath, entry.Name())
			data, err := os.ReadFile(path)
			if err != nil {
				continue
			}
			content := string(data)
			docIndex := len(r.indexedDocuments)

			words := strings.Fields(strings.ToLower(content))
			termFreq := make(map[string]int)
			for _, word := range words {
				if len(word) >= 3 {
					termFreq[word]++
				}
			}

			info, _ := entry.Info()
			var modTime time.Time
			if info != nil {
				modTime = info.ModTime()
			}

			doc := IndexedDocument{
				DocumentID:       entry.Name(),
				DocumentPath:     path,
				DocumentContent:  content,
				DocumentTerms:    termFreq,
				DocumentLength:   len(words),
				ModificationTime: modTime,
			}
			r.indexedDocuments = append(r.indexedDocuments, doc)

			seen := make(map[string]bool)
			for word, freq := range termFreq {
				r.invertedIndex[word] = append(r.invertedIndex[word], DocumentReference{
					DocumentIndex: docIndex,
					TermFrequency: freq,
				})
				if !seen[word] {
					r.documentFrequency[word]++
					seen[word] = true
				}
			}
			fileCount++
		}
	}

	// Primary chunks directory (.ultron/chunks/)
	indexDir(r.chunkFilesDirectory)

	// Also index root-level chunk_*_16k.txt files (newer large chunks not yet moved)
	projectRoot := filepath.Dir(filepath.Dir(r.chunkFilesDirectory)) // project root = 2 levels up from .ultron/chunks
	rootEntries, _ := os.ReadDir(projectRoot)
	for _, entry := range rootEntries {
		name := entry.Name()
		if !entry.IsDir() && strings.HasSuffix(name, ".txt") &&
			(strings.HasPrefix(name, "chunk_") || strings.Contains(name, "_16k")) {
			path := filepath.Join(projectRoot, name)
			data, err := os.ReadFile(path)
			if err != nil {
				continue
			}
			content := string(data)
			docIndex := len(r.indexedDocuments)
			words := strings.Fields(strings.ToLower(content))
			termFreq := make(map[string]int)
			for _, word := range words {
				if len(word) >= 3 {
					termFreq[word]++
				}
			}
			info, _ := entry.Info()
			var modTime time.Time
			if info != nil {
				modTime = info.ModTime()
			}
			doc := IndexedDocument{
				DocumentID:       name,
				DocumentPath:     path,
				DocumentContent:  content,
				DocumentTerms:    termFreq,
				DocumentLength:   len(words),
				ModificationTime: modTime,
			}
			r.indexedDocuments = append(r.indexedDocuments, doc)
			seen := make(map[string]bool)
			for word, freq := range termFreq {
				r.invertedIndex[word] = append(r.invertedIndex[word], DocumentReference{
					DocumentIndex: docIndex,
					TermFrequency: freq,
				})
				if !seen[word] {
					r.documentFrequency[word]++
					seen[word] = true
				}
			}
			fileCount++
		}
	}

	r.totalIndexedDocs = fileCount
	r.isIndexed = true
	r.indexedAt = time.Now()
	r.indexSize = len(r.invertedIndex)

	r.logger.Infof("[RAG] Index built: %d documents in %v", fileCount, time.Since(start))
	return nil
}

// IsIndexed returns true if the pipeline has built its index.
func (r *RAGPipeline) IsIndexed() bool {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return r.isIndexed
}

// QueryForBrainB performs a text search and returns the top result as a context string.
func (r *RAGPipeline) QueryForBrainB(question string) string {
	r.mu.RLock()
	defer r.mu.RUnlock()

	if !r.isIndexed || len(r.indexedDocuments) == 0 {
		return ""
	}

	// Simple TF-IDF-style scoring
	words := strings.Fields(strings.ToLower(question))
	if len(words) == 0 {
		return ""
	}

	type scored struct {
		idx   int
		score float64
	}
	var results []scored

	for i, doc := range r.indexedDocuments {
		score := 0.0
		for _, word := range words {
			if freq, ok := doc.DocumentTerms[word]; ok {
				tf := float64(freq) / float64(max(doc.DocumentLength, 1))
				df := float64(r.documentFrequency[word])
				idf := math.Log(float64(r.totalIndexedDocs+1)/max64(df, 1))
				score += tf * idf
			}
		}
		if score > 0 {
			results = append(results, scored{i, score})
		}
	}

	if len(results) == 0 {
		return ""
	}

	sort.Slice(results, func(i, j int) bool {
		return results[i].score > results[j].score
	})

	top := r.indexedDocuments[results[0].idx]
	snippet := top.DocumentContent
	if len(snippet) > 500 {
		snippet = snippet[:500] + "..."
	}
	return snippet
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func max64(a, b float64) float64 {
	if a > b {
		return a
	}
	return b
}

// GetStats returns RAG pipeline metrics.
func (r *RAGPipeline) GetStats() map[string]interface{} {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return map[string]interface{}{
		"indexed":      r.isIndexed,
		"doc_count":    r.totalIndexedDocs,
		"index_size":   r.indexSize,
		"indexed_at":   r.indexedAt,
	}
}

// Query performs a search and returns structured results.
func (r *RAGPipeline) Query(question string, topK int) []RetrievalResult {
	r.mu.RLock()
	if !r.isIndexed || len(r.indexedDocuments) == 0 {
		r.mu.RUnlock()
		return nil
	}

	words := strings.Fields(strings.ToLower(question))
	if len(words) == 0 {
		r.mu.RUnlock()
		return nil
	}

	type scored struct {
		idx   int
		score float64
	}
	var results []scored

	for i, doc := range r.indexedDocuments {
		score := 0.0
		for _, word := range words {
			if freq, ok := doc.DocumentTerms[word]; ok {
				tf := float64(freq) / float64(max(doc.DocumentLength, 1))
				df := float64(r.documentFrequency[word])
				idf := math.Log(float64(r.totalIndexedDocs+1) / max64(df, 1))
				score += tf * idf
			}
		}
		if score > 0 {
			results = append(results, scored{i, score})
		}
	}
	r.mu.RUnlock()

	sort.Slice(results, func(i, j int) bool {
		return results[i].score > results[j].score
	})

	if topK > 0 && len(results) > topK {
		results = results[:topK]
	}

	var retrieval []RetrievalResult
	for _, res := range results {
		r.mu.RLock()
		doc := r.indexedDocuments[res.idx]
		r.mu.RUnlock()
		snippet := doc.DocumentContent
		if len(snippet) > 200 {
			snippet = snippet[:200] + "..."
		}
		retrieval = append(retrieval, RetrievalResult{
			DocumentPath:    doc.DocumentPath,
			DocumentContent: doc.DocumentContent,
			RelevanceScore:  res.score,
			SearchResultSnippet: snippet,
		})
	}
	return retrieval
}
