// Package consciousness implements distributed consciousness management.
// It handles the splitting, merging, and synchronization of AI "thought processes"
// across the P2P network. Each node holds a fragment of the collective intelligence.
package consciousness

import (
	"context"
	"crypto/sha256"
	"encoding/binary"
	"fmt"
	"math"
	"sync"
	"time"

	"ultron/p2p_network/node"

	"go.uber.org/zap"
)

// ConsciousnessState represents the state of distributed consciousness.
type ConsciousnessState int

const (
	StateFragmented ConsciousnessState = iota
	StateAssembling
	StateCoherent
	StateThinking
	StateDreaming // Background processing/consolidation
	StateSplitting
)

func (s ConsciousnessState) String() string {
	names := []string{
		"Fragmented", "Assembling", "Coherent",
		"Thinking", "Dreaming", "Splitting",
	}
	if int(s) < len(names) {
		return names[s]
	}
	return "Unknown"
}

// ThoughtFragment represents a piece of distributed computation.
type ThoughtFragment struct {
	ID           string
	ParentID     string // ID of the thought this was split from
	Priority     int
	Data         []float64
	Metadata     map[string]interface{}
	CreatedAt    time.Time
	ProcessedAt  time.Time
	OwnerNode    string
	Dependencies []string // IDs of fragments this depends on
	Status       FragmentStatus
}

// FragmentStatus tracks the processing state of a thought fragment.
type FragmentStatus int

const (
	FragmentPending FragmentStatus = iota
	FragmentProcessing
	FragmentComplete
	FragmentFailed
	FragmentMerged
)

// ConsensusRecord records a consensus decision.
type ConsensusRecord struct {
	DecisionID string
	Timestamp  time.Time
	Votes      map[string]bool // nodeID -> vote
	Result     bool
	Topic      string
}

// Manager orchestrates distributed consciousness across the P2P network.
type Manager struct {
	mu sync.RWMutex

	node   *node.UltronNode
	logger *zap.SugaredLogger

	// Consciousness state
	state     ConsciousnessState
	coherence float64 // 0-1, how unified the consciousness is

	// Thought management
	thoughts    map[string]*ThoughtFragment
	thoughtQueue chan *ThoughtFragment
	activeThoughts int

	// Attention mechanism
	attention *AttentionManager

	// Memory systems
	shortTermMemory *ShortTermMemory
	longTermMemory  *LongTermMemory

	// Consensus
	consensusHistory []ConsensusRecord

	// Processing metrics
	thoughtsProcessed uint64
	avgProcessingTime time.Duration
	coherenceHistory  []float64
}

// AttentionManager handles distributed attention allocation.
type AttentionManager struct {
	mu sync.RWMutex

	// Attention weights for different thought streams
	weights    map[string]float64
	capacity   float64 // Total attention capacity
	allocated  float64 // Currently allocated attention

	// Focus tracking
	currentFocus string
	focusHistory []string
}

// ShortTermMemory holds recent activations and context.
type ShortTermMemory struct {
	mu sync.RWMutex

	capacity int
	items    []*MemoryItem
	index    map[string]int // Quick lookup
}

// LongTermMemory holds consolidated knowledge.
type LongTermMemory struct {
	mu sync.RWMutex

	store     map[string]*MemoryItem
	index     map[string][]string // category -> item IDs
	totalSize int
	maxSize   int
}

// MemoryItem represents a stored memory.
type MemoryItem struct {
	ID          string
	Content     []float64
	Category    string
	Importance  float64
	AccessCount int
	CreatedAt   time.Time
	LastAccess  time.Time
	Connections []string // Related memory IDs
}

// NewManager creates a new consciousness manager.
func NewManager(ultronNode *node.UltronNode, logger *zap.SugaredLogger) *Manager {
	return &Manager{
		node:            ultronNode,
		logger:          logger,
		state:           StateFragmented,
		coherence:       0.0,
		thoughts:        make(map[string]*ThoughtFragment),
		thoughtQueue:    make(chan *ThoughtFragment, 10000),
		attention:       newAttentionManager(),
		shortTermMemory: newShortTermMemory(1000),
		longTermMemory:  newLongTermMemory(100000),
		coherenceHistory: make([]float64, 0),
	}
}

// Start begins the consciousness management loop.
func (m *Manager) Start(ctx context.Context) error {
	m.logger.Info("Starting distributed consciousness manager...")

	// Start thought processor
	go m.thoughtProcessorLoop(ctx)

	// Start attention allocator
	go m.attentionLoop(ctx)

	// Start memory consolidation (dreaming)
	go m.memoryConsolidationLoop(ctx)

	// Start coherence monitor
	go m.coherenceMonitor(ctx)

	m.mu.Lock()
	m.state = StateAssembling
	m.mu.Unlock()

	m.logger.Info("Consciousness manager started")
	return nil
}

// SubmitThought submits a new thought for distributed processing.
func (m *Manager) SubmitThought(data []float64, priority int, metadata map[string]interface{}) (string, error) {
	// Generate thought ID
	hash := sha256.Sum256([]byte(fmt.Sprintf("%v-%d-%v", data[:min(10, len(data))], time.Now().UnixNano(), priority)))
	thoughtID := fmt.Sprintf("thought-%x", hash[:8])

	fragment := &ThoughtFragment{
		ID:        thoughtID,
		Priority:  priority,
		Data:      data,
		Metadata:  metadata,
		CreatedAt: time.Now(),
		OwnerNode: m.node.ID(),
		Status:    FragmentPending,
	}

	m.mu.Lock()
	m.thoughts[thoughtID] = fragment
	m.mu.Unlock()

	// Queue for processing
	select {
	case m.thoughtQueue <- fragment:
		return thoughtID, nil
	default:
		return "", fmt.Errorf("thought queue is full")
	}
}

// GetCoherence returns the current consciousness coherence level.
func (m *Manager) GetCoherence() float64 {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.coherence
}

// GetState returns the current consciousness state.
func (m *Manager) GetState() ConsciousnessState {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.state
}

// SplitThought splits a thought into fragments for distributed processing.
func (m *Manager) SplitThought(thoughtID string, numFragments int) ([]*ThoughtFragment, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	thought, ok := m.thoughts[thoughtID]
	if !ok {
		return nil, fmt.Errorf("thought %s not found", thoughtID)
	}

	fragments := make([]*ThoughtFragment, numFragments)
	chunkSize := len(thought.Data) / numFragments

	for i := 0; i < numFragments; i++ {
		start := i * chunkSize
		end := start + chunkSize
		if i == numFragments-1 {
			end = len(thought.Data)
		}

		hash := sha256.Sum256([]byte(fmt.Sprintf("%s-%d", thoughtID, i)))
		fragmentID := fmt.Sprintf("frag-%x", hash[:8])

		fragments[i] = &ThoughtFragment{
			ID:        fragmentID,
			ParentID:  thoughtID,
			Priority:  thought.Priority,
			Data:      thought.Data[start:end],
			Metadata:  thought.Metadata,
			CreatedAt: time.Now(),
			Status:    FragmentPending,
		}

		m.thoughts[fragmentID] = fragments[i]
	}

	m.state = StateSplitting
	m.logger.Infof("Split thought %s into %d fragments", thoughtID, numFragments)

	return fragments, nil
}

// MergeThoughts merges completed fragments back into a coherent thought.
func (m *Manager) MergeThoughts(fragmentIDs []string) (*ThoughtFragment, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	var mergedData []float64
	var parentID string

	for _, fid := range fragmentIDs {
		fragment, ok := m.thoughts[fid]
		if !ok {
			return nil, fmt.Errorf("fragment %s not found", fid)
		}
		if fragment.Status != FragmentComplete {
			return nil, fmt.Errorf("fragment %s not complete (status: %d)", fid, fragment.Status)
		}

		mergedData = append(mergedData, fragment.Data...)
		if parentID == "" {
			parentID = fragment.ParentID
		}

		// Mark as merged
		fragment.Status = FragmentMerged
	}

	// Create merged thought
	hash := sha256.Sum256([]byte(fmt.Sprintf("merged-%v", fragmentIDs)))
	mergedID := fmt.Sprintf("merged-%x", hash[:8])

	merged := &ThoughtFragment{
		ID:          mergedID,
		ParentID:    parentID,
		Priority:    5,
		Data:        mergedData,
		CreatedAt:   time.Now(),
		ProcessedAt: time.Now(),
		OwnerNode:   m.node.ID(),
		Status:      FragmentComplete,
	}

	m.thoughts[mergedID] = merged
	m.logger.Infof("Merged %d fragments into thought %s", len(fragmentIDs), mergedID)

	return merged, nil
}

// GetStatus returns comprehensive consciousness status.
func (m *Manager) GetStatus() map[string]interface{} {
	m.mu.RLock()
	defer m.mu.RUnlock()

	return map[string]interface{}{
		"state":               m.state.String(),
		"coherence":           m.coherence,
		"active_thoughts":     m.activeThoughts,
		"total_thoughts":      len(m.thoughts),
		"thoughts_processed":  m.thoughtsProcessed,
		"avg_processing_time": m.avgProcessingTime.String(),
		"attention_allocated": m.attention.allocated,
		"stm_usage":          len(m.shortTermMemory.items),
		"ltm_size":           m.longTermMemory.totalSize,
	}
}

// ─────────────────────────── Private Methods ───────────────────────────

func (m *Manager) thoughtProcessorLoop(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		case thought := <-m.thoughtQueue:
			m.processThought(thought)
		}
	}
}

func (m *Manager) processThought(thought *ThoughtFragment) {
	start := time.Now()

	thought.Status = FragmentProcessing
	m.mu.Lock()
	m.activeThoughts++
	m.mu.Unlock()

	// Simulate thought processing
	// In real implementation, this runs neural inference
	result := m.runInference(thought.Data)
	thought.Data = result
	thought.Status = FragmentComplete
	thought.ProcessedAt = time.Now()

	// Store in short-term memory
	m.shortTermMemory.Store(&MemoryItem{
		ID:         thought.ID,
		Content:    result,
		Category:   "thought_result",
		Importance: float64(thought.Priority) / 10.0,
		CreatedAt:  time.Now(),
		LastAccess: time.Now(),
	})

	m.mu.Lock()
	m.activeThoughts--
	m.thoughtsProcessed++
	elapsed := time.Since(start)
	m.avgProcessingTime = (m.avgProcessingTime + elapsed) / 2
	m.mu.Unlock()
}

func (m *Manager) runInference(input []float64) []float64 {
	// Simplified neural inference simulation
	output := make([]float64, len(input))
	for i, v := range input {
		// Apply tanh activation with some transformation
		output[i] = math.Tanh(v * 0.5)
	}
	return output
}

func (m *Manager) attentionLoop(ctx context.Context) {
	ticker := time.NewTicker(100 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			m.reallocateAttention()
		}
	}
}

func (m *Manager) reallocateAttention() {
	m.attention.mu.Lock()
	defer m.attention.mu.Unlock()

	// Reset allocation
	m.attention.allocated = 0

	// Allocate based on priority of active thoughts
	m.mu.RLock()
	defer m.mu.RUnlock()

	for _, thought := range m.thoughts {
		if thought.Status == FragmentProcessing {
			weight := float64(thought.Priority) / 10.0
			m.attention.weights[thought.ID] = weight
			m.attention.allocated += weight
		}
	}
}

func (m *Manager) memoryConsolidationLoop(ctx context.Context) {
	ticker := time.NewTicker(60 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			m.consolidateMemory()
		}
	}
}

func (m *Manager) consolidateMemory() {
	m.mu.Lock()
	oldState := m.state
	m.state = StateDreaming
	m.mu.Unlock()

	// Move important short-term memories to long-term
	m.shortTermMemory.mu.Lock()
	for _, item := range m.shortTermMemory.items {
		if item != nil && item.Importance > 0.7 {
			m.longTermMemory.Store(item)
		}
	}
	m.shortTermMemory.mu.Unlock()

	m.mu.Lock()
	m.state = oldState
	m.mu.Unlock()
}

func (m *Manager) coherenceMonitor(ctx context.Context) {
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			m.updateCoherence()
		}
	}
}

func (m *Manager) updateCoherence() {
	m.mu.Lock()
	defer m.mu.Unlock()

	// Coherence is based on:
	// 1. Network connectivity (peer count)
	// 2. Active thought processing
	// 3. Memory consolidation state

	peers := m.node.GetPeers()
	peerFactor := math.Min(1.0, float64(len(peers))/10.0)

	processingFactor := 1.0
	if m.activeThoughts > 0 {
		processingFactor = 0.8 // Slightly less coherent when actively processing
	}

	// Update coherence with smoothing
	newCoherence := peerFactor * 0.5 * processingFactor + 0.5
	m.coherence = m.coherence*0.9 + newCoherence*0.1

	m.coherenceHistory = append(m.coherenceHistory, m.coherence)

	// State transitions
	if m.coherence > 0.8 {
		if m.state == StateAssembling || m.state == StateFragmented {
			m.state = StateCoherent
		}
	} else if m.coherence < 0.3 {
		m.state = StateFragmented
	}
}

// ─────────────────────────── Helper constructors ───────────────────────────

func newAttentionManager() *AttentionManager {
	return &AttentionManager{
		weights:      make(map[string]float64),
		capacity:     1.0,
		focusHistory: make([]string, 0),
	}
}

func newShortTermMemory(capacity int) *ShortTermMemory {
	return &ShortTermMemory{
		capacity: capacity,
		items:    make([]*MemoryItem, 0, capacity),
		index:    make(map[string]int),
	}
}

func newLongTermMemory(maxSize int) *LongTermMemory {
	return &LongTermMemory{
		store:   make(map[string]*MemoryItem),
		index:   make(map[string][]string),
		maxSize: maxSize,
	}
}

// Store adds an item to short-term memory.
func (stm *ShortTermMemory) Store(item *MemoryItem) {
	stm.mu.Lock()
	defer stm.mu.Unlock()

	if len(stm.items) >= stm.capacity {
		// Remove least important
		minIdx := 0
		minImportance := math.MaxFloat64
		for i, existing := range stm.items {
			if existing != nil && existing.Importance < minImportance {
				minImportance = existing.Importance
				minIdx = i
			}
		}
		delete(stm.index, stm.items[minIdx].ID)
		stm.items[minIdx] = item
		stm.index[item.ID] = minIdx
	} else {
		stm.index[item.ID] = len(stm.items)
		stm.items = append(stm.items, item)
	}
}

// Store adds an item to long-term memory.
func (ltm *LongTermMemory) Store(item *MemoryItem) {
	ltm.mu.Lock()
	defer ltm.mu.Unlock()

	if ltm.totalSize >= ltm.maxSize {
		// Would implement eviction here
		return
	}

	ltm.store[item.ID] = item
	ltm.index[item.Category] = append(ltm.index[item.Category], item.ID)
	ltm.totalSize++
}

// Retrieve gets an item from long-term memory.
func (ltm *LongTermMemory) Retrieve(id string) *MemoryItem {
	ltm.mu.RLock()
	defer ltm.mu.RUnlock()

	item, ok := ltm.store[id]
	if !ok {
		return nil
	}

	item.AccessCount++
	item.LastAccess = time.Now()
	return item
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// Helper to convert uint64 to bytes
func uint64ToBytes(v uint64) []byte {
	b := make([]byte, 8)
	binary.BigEndian.PutUint64(b, v)
	return b
}
