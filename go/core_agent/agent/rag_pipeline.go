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
	documents   []Document
	invertedIdx map[string][]DocRef  // term → document references
	docFreq     map[string]int       // term → number of docs containing it
	totalDocs   int

	// Configuration
	chunksDir    string
	maxChunkSize int
	topK         int  // Default number of results to return

	// State
	indexed      bool
	indexedAt    time.Time
	indexSize    int

	logger *zap.SugaredLogger
}

// Document represents an indexed chunk.
type Document struct {
	ID       string
	Path     string
	Content  string
	Terms    map[string]int  // term → frequency in this doc
	Length   int             // Total term count
	ModTime  time.Time
}

// DocRef is a reference to a document in the inverted index.
type DocRef struct {
	DocIdx    int
	TermFreq  int
}

// RetrievalResult is a scored document match.
type RetrievalResult struct {
	Path      string  `json:"path"`
	Content   string  `json:"content"`
	Score     float64 `json:"score"`
	Snippet   string  `json:"snippet"`
}

// NewRAGPipeline creates the knowledge retrieval system.
func NewRAGPipeline(chunksDir string, logger *zap.SugaredLogger) *RAGPipeline {
	return &RAGPipeline{
		documents:   make([]Document, 0, 5000),
		invertedIdx: make(map[string][]DocRef),
		docFreq:     make(map[string]int),
		chunksDir:   chunksDir,
		maxChunkSize: 10000, // Max 10KB per chunk
		topK:        5,
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
	r.documents = r.documents[:0]
	r.invertedIdx = make(map[string][]DocRef)
	r.docFreq = make(map[string]int)

	// Walk chunks directory
	count := 0
	err := filepath.Walk(r.chunksDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil // Skip errors
		}
		if info.IsDir() {
			return nil
		}
		if !strings.HasSuffix(path, ".txt") {
			return nil
		}
		if info.Size() > int64(r.maxChunkSize) {
			return nil // Skip oversized files
		}

		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		content, err := os.ReadFile(path)
		if err != nil {
			return nil
		}

		r.indexDocument(path, string(content), info.ModTime())
		count++

		return nil
	})

	if err != nil {
		return err
	}

	r.totalDocs = len(r.documents)
	r.indexed = true
	r.indexedAt = time.Now()
	r.indexSize = count

	r.logger.Infof("[RAG] Index built: %d documents, %d unique terms, took %v",
		count, len(r.invertedIdx), time.Since(start))

	return nil
}

func (r *RAGPipeline) indexDocument(path, content string, modTime time.Time) {
	// Tokenize
	terms := tokenize(content)
	termFreq := make(map[string]int)
	for _, term := range terms {
		termFreq[term]++
	}

	docIdx := len(r.documents)
	doc := Document{
		ID:      filepath.Base(path),
		Path:    path,
		Content: content,
		Terms:   termFreq,
		Length:  len(terms),
		ModTime: modTime,
	}
	r.documents = append(r.documents, doc)

	// Update inverted index
	seenTerms := make(map[string]bool)
	for term, freq := range termFreq {
		r.invertedIdx[term] = append(r.invertedIdx[term], DocRef{
			DocIdx:   docIdx,
			TermFreq: freq,
		})
		if !seenTerms[term] {
			r.docFreq[term]++
			seenTerms[term] = true
		}
	}
}

// ═══════════════════════════════════════════════════════════════
// QUERY — Find relevant chunks using BM25 scoring
// ═══════════════════════════════════════════════════════════════

// Query searches the index and returns the most relevant chunks.
func (r *RAGPipeline) Query(query string, topK int) []RetrievalResult {
	r.mu.RLock()
	defer r.mu.RUnlock()

	if !r.indexed || len(r.documents) == 0 {
		return nil
	}

	if topK <= 0 {
		topK = r.topK
	}

	// Tokenize query
	queryTerms := tokenize(query)
	if len(queryTerms) == 0 {
		return nil
	}

	// Score all documents using BM25
	scores := make([]float64, len(r.documents))
	avgDocLen := r.avgDocLength()

	// BM25 parameters
	k1 := 1.2
	b := 0.75

	for _, term := range queryTerms {
		refs, exists := r.invertedIdx[term]
		if !exists {
			continue
		}

		// IDF for this term
		idf := r.idf(term)

		for _, ref := range refs {
			doc := r.documents[ref.DocIdx]
			tf := float64(ref.TermFreq)
			docLen := float64(doc.Length)

			// BM25 scoring
			numerator := tf * (k1 + 1)
			denominator := tf + k1*(1-b+b*docLen/avgDocLen)
			scores[ref.DocIdx] += idf * (numerator / denominator)
		}
	}

	// Rank by score
	type scored struct {
		idx   int
		score float64
	}
	ranked := make([]scored, 0)
	for i, s := range scores {
		if s > 0 {
			ranked = append(ranked, scored{i, s})
		}
	}

	sort.Slice(ranked, func(i, j int) bool {
		return ranked[i].score > ranked[j].score
	})

	// Return top-K results
	results := make([]RetrievalResult, 0, topK)
	for i, item := range ranked {
		if i >= topK {
			break
		}
		doc := r.documents[item.idx]
		snippet := extractSnippet(doc.Content, queryTerms, 200)

		results = append(results, RetrievalResult{
			Path:    doc.Path,
			Content: doc.Content,
			Score:   item.score,
			Snippet: snippet,
		})
	}

	return results
}

// QueryForBrainB retrieves knowledge and formats it for Brain B's context.
func (r *RAGPipeline) QueryForBrainB(question string) string {
	results := r.Query(question, 3)
	if len(results) == 0 {
		return ""
	}

	var sb strings.Builder
	sb.WriteString("RELEVANT KNOWLEDGE FROM MEMORY:\n")
	for i, res := range results {
		sb.WriteString(fmt.Sprintf("--- Memory %d (relevance: %.2f) ---\n", i+1, res.Score))
		// Use snippet, not full content
		content := res.Snippet
		if len(content) > 500 {
			content = content[:500] + "..."
		}
		sb.WriteString(content)
		sb.WriteString("\n")
	}
	sb.WriteString("--- END MEMORY ---\n")

	return sb.String()
}

// ═══════════════════════════════════════════════════════════════
// HELPERS — BM25, tokenization, snippets
// ═══════════════════════════════════════════════════════════════

func (r *RAGPipeline) idf(term string) float64 {
	df := float64(r.docFreq[term])
	if df == 0 {
		return 0
	}
	n := float64(r.totalDocs)
	return math.Log(1 + (n-df+0.5)/(df+0.5))
}

func (r *RAGPipeline) avgDocLength() float64 {
	if len(r.documents) == 0 {
		return 1
	}
	total := 0
	for _, doc := range r.documents {
		total += doc.Length
	}
	return float64(total) / float64(len(r.documents))
}

// tokenize breaks text into lowercase terms, removes stopwords.
func tokenize(text string) []string {
	// Split on non-alphanumeric
	words := strings.FieldsFunc(strings.ToLower(text), func(r rune) bool {
		return !unicode.IsLetter(r) && !unicode.IsDigit(r)
	})

	// Remove stopwords and short terms
	filtered := make([]string, 0, len(words))
	for _, w := range words {
		if len(w) < 3 {
			continue
		}
		if stopwords[w] {
			continue
		}
		filtered = append(filtered, w)
	}

	return filtered
}

// extractSnippet finds the most relevant part of a document.
func extractSnippet(content string, queryTerms []string, maxLen int) string {
	if len(content) <= maxLen {
		return content
	}

	// Find the position with highest density of query terms
	lower := strings.ToLower(content)
	bestPos := 0
	bestScore := 0

	for i := 0; i < len(lower)-maxLen; i += 50 {
		window := lower[i : i+maxLen]
		score := 0
		for _, term := range queryTerms {
			score += strings.Count(window, term)
		}
		if score > bestScore {
			bestScore = score
			bestPos = i
		}
	}

	end := bestPos + maxLen
	if end > len(content) {
		end = len(content)
	}

	return content[bestPos:end]
}

// IsIndexed returns whether the index has been built.
func (r *RAGPipeline) IsIndexed() bool {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return r.indexed
}

// GetStats returns index statistics.
func (r *RAGPipeline) GetStats() map[string]interface{} {
	r.mu.RLock()
	defer r.mu.RUnlock()

	return map[string]interface{}{
		"indexed":      r.indexed,
		"indexed_at":   r.indexedAt,
		"total_docs":   r.totalDocs,
		"unique_terms": len(r.invertedIdx),
		"chunks_dir":   r.chunksDir,
	}
}

// Common English stopwords
var stopwords = map[string]bool{
	"the": true, "and": true, "for": true, "are": true, "but": true,
	"not": true, "you": true, "all": true, "can": true, "had": true,
	"her": true, "was": true, "one": true, "our": true, "out": true,
	"has": true, "have": true, "been": true, "this": true, "that": true,
	"with": true, "they": true, "from": true, "will": true, "what": true,
	"when": true, "make": true, "like": true, "time": true, "just": true,
	"know": true, "take": true, "come": true, "could": true, "than": true,
	"look": true, "only": true, "into": true, "year": true, "your": true,
	"some": true, "them": true, "then": true, "also": true, "about": true,
	"would": true, "there": true, "their": true, "which": true, "each": true,
}
