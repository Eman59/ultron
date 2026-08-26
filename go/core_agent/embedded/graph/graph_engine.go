// Package graph implements an embedded knowledge graph engine.
// Replaces Neo4j — no external process needed.
//
// Features:
//   - Labeled property graph (nodes + edges with properties)
//   - Cypher-like traversals (BFS, DFS, shortest path)
//   - Index on node labels and properties
//   - Relationship queries (who is connected to whom, and how)
//   - Persistent to disk (JSON serialization)
//   - Concurrent-safe
//   - Supports episodic memory (temporal sequences)
package graph

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// GraphNode is a vertex in the knowledge graph.
type GraphNode struct {
	ID         string                 `json:"id"`
	Labels     []string               `json:"labels"`     // e.g., ["Person", "Contact"]
	Properties map[string]interface{} `json:"properties"`
	CreatedAt  time.Time              `json:"created_at"`
	UpdatedAt  time.Time              `json:"updated_at"`
	AccessCount int                   `json:"access_count"`
}

// GraphEdge is a directed relationship between nodes.
type GraphEdge struct {
	ID         string                 `json:"id"`
	Source     string                 `json:"source"`
	Target     string                 `json:"target"`
	Type       string                 `json:"type"` // e.g., "KNOWS", "CAUSED", "DECIDED"
	Properties map[string]interface{} `json:"properties"`
	Weight     float64                `json:"weight"`
	CreatedAt  time.Time              `json:"created_at"`
}

// TraversalResult is a path found during graph traversal.
type TraversalResult struct {
	Nodes []string
	Edges []string
	Depth int
	Cost  float64
}

// GraphEngine is the embedded knowledge graph.
type GraphEngine struct {
	mu sync.RWMutex

	// Core data
	nodes map[string]*GraphNode
	edges map[string]*GraphEdge

	// Indexes
	labelIndex    map[string][]string // label -> node IDs
	outEdges      map[string][]string // node ID -> outgoing edge IDs
	inEdges       map[string][]string // node ID -> incoming edge IDs
	edgeTypeIndex map[string][]string // edge type -> edge IDs

	// Persistence
	dataDir  string
	dirty    bool

	// Stats
	nodeCount uint64
	edgeCount uint64
	queries   uint64
}

// NewGraphEngine creates an embedded graph with persistence.
func NewGraphEngine(dataDir string) (*GraphEngine, error) {
	if dataDir == "" {
		return nil, fmt.Errorf("data directory cannot be empty")
	}

	if err := os.MkdirAll(dataDir, 0700); err != nil {
		return nil, err
	}

	g := &GraphEngine{
		nodes:         make(map[string]*GraphNode),
		edges:         make(map[string]*GraphEdge),
		labelIndex:    make(map[string][]string),
		outEdges:      make(map[string][]string),
		inEdges:       make(map[string][]string),
		edgeTypeIndex: make(map[string][]string),
		dataDir:       dataDir,
	}

	// Load from disk
	g.load()

	// Start persistence loop
	go g.persistLoop()

	return g, nil
}

// ━━━━━━━━━━ Node Operations ━━━━━━━━━━

// AddNode creates a node in the graph.
func (g *GraphEngine) AddNode(id string, labels []string, properties map[string]interface{}) *GraphNode {
	if id == "" {
		return nil
	}

	if labels == nil {
		labels = []string{}
	}

	if properties == nil {
		properties = map[string]interface{}{}
	}

	g.mu.Lock()
	defer g.mu.Unlock()

	// Check for existing node
	if _, exists := g.nodes[id]; exists {
		return g.nodes[id]
	}

	node := &GraphNode{
		ID:         id,
		Labels:     labels,
		Properties: properties,
		CreatedAt:  time.Now(),
		UpdatedAt:  time.Now(),
		AccessCount: 0,
	}

	g.nodes[id] = node

	// Update indexes
	for _, label := range labels {
		g.labelIndex[label] = append(g.labelIndex[label], id)
	}

	g.dirty = true
	g.nodeCount++

	return node
}

// ━━━━━━━━━━ Edge Operations ━━━━━━━━━━

// AddEdge creates an edge between two nodes in the graph.
func (g *GraphEngine) AddEdge(id string, source string, target string, edgeType string, properties map[string]interface{}, weight float64) *GraphEdge {
	if id == "" || source == "" || target == "" || edgeType == "" {
		return nil
	}

	if properties == nil {
		properties = map[string]interface{}{}
	}

	g.mu.Lock()
	defer g.mu.Unlock()

	// Check for existing edge
	if _, exists := g.edges[id]; exists {
		return g.edges[id]
	}

	edge := &GraphEdge{
		ID:         id,
		Source:     source,
		Target:     target,
		Type:       edgeType,
		Properties: properties,
		Weight:     weight,
		CreatedAt:  time.Now(),
	}

	g.edges[id] = edge

	// Update indexes
	g.outEdges[source] = append(g.outEdges[source], id)
	g.inEdges[target] = append(g.inEdges[target], id)
	g.edgeTypeIndex[edgeType] = append(g.edgeTypeIndex[edgeType], id)

	g.dirty = true
	g.edgeCount++

	return edge
}

// ━━━━━━━━━━ Traversal Operations ━━━━━━━━━━

// Traverse performs a BFS traversal of the graph starting from a given node.
func (g *GraphEngine) Traverse(startNodeID string, maxDepth int) ([]TraversalResult, error) {
	if startNodeID == "" {
		return nil, fmt.Errorf("start node ID cannot be empty")
	}

	if maxDepth <= 0 {
		return nil, fmt.Errorf("max depth must be greater than 0")
	}

	g.mu.RLock()
	defer g.mu.RUnlock()

	// Check if start node exists
	if _, exists := g.nodes[startNodeID]; !exists {
		return nil, fmt.Errorf("start node does not exist")
	}

	// Perform BFS traversal
	var results []TraversalResult
	queue := [][]string{{startNodeID}}
	visited := make(map[string]bool)

	for depth := 0; depth <= maxDepth; depth++ {
		levelSize := len(queue)
		for i := 0; i < levelSize; i++ {
			nodeIDs := queue[0]
			queue = queue[1:]

			for _, nodeID := range nodeIDs {
				if visited[nodeID] {
					continue
				}

				visited[nodeID] = true

				// Get node and its edges
				node := g.nodes[nodeID]
				edges := g.outEdges[nodeID]

				// Add edges to result
				for _, edgeID := range edges {
					edge := g.edges[edgeID]
					targetNodeID := edge.Target

					result := TraversalResult{
						Nodes: []string{nodeID, targetNodeID},
						Edges: []string{edgeID},
						Depth: depth + 1,
						Cost:  edge.Weight,
					}

					results = append(results, result)

					// Add target node to queue
					queue = append(queue, []string{targetNodeID})
				}
			}
		}
	}

	return results, nil
}

// ━━━━━━━━━━ Persistence Operations ━━━━━━━━━━

// load loads the graph data from disk.
func (g *GraphEngine) load() error {
	g.mu.Lock()
	defer g.mu.Unlock()

	// Load nodes
	nodesFile := filepath.Join(g.dataDir, "nodes.json")
	if _, err := os.Stat(nodesFile); err == nil {
		data, err := os.ReadFile(nodesFile)
		if err != nil {
			return err
		}

		var nodes map[string]*GraphNode
		err = json.Unmarshal(data, &nodes)
		if err != nil {
			return err
		}

		g.nodes = nodes
	}

	// Load edges
	edgesFile := filepath.Join(g.dataDir, "edges.json")
	if _, err := os.Stat(edgesFile); err == nil {
		data, err := os.ReadFile(edgesFile)
		if err != nil {
			return err
		}

		var edges map[string]*GraphEdge
		err = json.Unmarshal(data, &edges)
		if err != nil {
			return err
		}

		g.edges = edges
	}

	// Load indexes
	labelIndexFile := filepath.Join(g.dataDir, "label_index.json")
	if _, err := os.Stat(labelIndexFile); err == nil {
		data, err := os.ReadFile(labelIndexFile)
		if err != nil {
			return err
		}

		var labelIndex map[string][]string
		err = json.Unmarshal(data, &labelIndex)
		if err != nil {
			return err
		}

		g.labelIndex = labelIndex
	}

	outEdgesFile := filepath.Join(g.dataDir, "out_edges.json")
	if _, err := os.Stat(outEdgesFile); err == nil {
		data, err := os.ReadFile(outEdgesFile)
		if err != nil {
			return err
		}

		var outEdges map[string][]string
		err = json.Unmarshal(data, &outEdges)
		if err != nil {
			return err
		}

		g.outEdges = outEdges
	}

	inEdgesFile := filepath.Join(g.dataDir, "in_edges.json")
	if _, err := os.Stat(inEdges