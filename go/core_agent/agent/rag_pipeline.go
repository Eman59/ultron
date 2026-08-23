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
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"
	"unicode"

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
	// ... rest of the code remains the same ...