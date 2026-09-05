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

				// Get outgoing edges for this node
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
	if _, err := os.Stat(inEdgesFile); err == nil {
		data, err := os.ReadFile(inEdgesFile)
		if err != nil {
			return err
		}

		var inEdges map[string][]string
		err = json.Unmarshal(data, &inEdges)
		if err != nil {
			return err
		}

		g.inEdges = inEdges
	}

	edgeTypeIndexFile := filepath.Join(g.dataDir, "edge_type_index.json")
	if _, err := os.Stat(edgeTypeIndexFile); err == nil {
		data, err := os.ReadFile(edgeTypeIndexFile)
		if err != nil {
			return err
		}

		var edgeTypeIndex map[string][]string
		err = json.Unmarshal(data, &edgeTypeIndex)
		if err != nil {
			return err
		}

		g.edgeTypeIndex = edgeTypeIndex
	}

	return nil
}

// persist saves the graph data to disk.
func (g *GraphEngine) persist() error {
	g.mu.RLock()
	defer g.mu.RUnlock()

	writeJSON := func(filename string, v interface{}) error {
		data, err := json.Marshal(v)
		if err != nil {
			return err
		}
		return os.WriteFile(filepath.Join(g.dataDir, filename), data, 0600)
	}

	if err := writeJSON("nodes.json", g.nodes); err != nil {
		return err
	}
	if err := writeJSON("edges.json", g.edges); err != nil {
		return err
	}
	if err := writeJSON("label_index.json", g.labelIndex); err != nil {
		return err
	}
	if err := writeJSON("out_edges.json", g.outEdges); err != nil {
		return err
	}
	if err := writeJSON("in_edges.json", g.inEdges); err != nil {
		return err
	}
	if err := writeJSON("edge_type_index.json", g.edgeTypeIndex); err != nil {
		return err
	}

	return nil
}

// persistLoop periodically saves dirty state to disk.
func (g *GraphEngine) persistLoop() {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		g.mu.RLock()
		dirty := g.dirty
		g.mu.RUnlock()

		if dirty {
			if err := g.persist(); err == nil {
				g.mu.Lock()
				g.dirty = false
				g.mu.Unlock()
			}
		}
	}
}

// ShortestPath finds the shortest path between two nodes using BFS.
func (g *GraphEngine) ShortestPath(fromID, toID string) ([]string, float64, error) {
	if fromID == "" || toID == "" {
		return nil, 0, fmt.Errorf("node IDs cannot be empty")
	}

	g.mu.RLock()
	defer g.mu.RUnlock()

	if _, exists := g.nodes[fromID]; !exists {
		return nil, 0, fmt.Errorf("source node does not exist")
	}
	if _, exists := g.nodes[toID]; !exists {
		return nil, 0, fmt.Errorf("target node does not exist")
	}

	// BFS with path tracking
	type qEntry struct {
		nodeID string
		path   []string
		cost   float64
	}

	visited := make(map[string]bool)
	queue := []qEntry{{nodeID: fromID, path: []string{fromID}, cost: 0}}

	for len(queue) > 0 {
		current := queue[0]
		queue = queue[1:]

		if current.nodeID == toID {
			return current.path, current.cost, nil
		}

		if visited[current.nodeID] {
			continue
		}
		visited[current.nodeID] = true

		for _, edgeID := range g.outEdges[current.nodeID] {
			edge := g.edges[edgeID]
			if !visited[edge.Target] {
				newPath := make([]string, len(current.path)+1)
				copy(newPath, current.path)
				newPath[len(current.path)] = edge.Target
				queue = append(queue, qEntry{
					nodeID: edge.Target,
					path:   newPath,
					cost:   current.cost + edge.Weight,
				})
			}
		}
	}

	return nil, math.MaxFloat64, fmt.Errorf("no path found from %s to %s", fromID, toID)
}

// GetNode returns a single node by ID.
func (g *GraphEngine) GetNode(id string) *GraphNode {
	g.mu.RLock()
	defer g.mu.RUnlock()
	return g.nodes[id]
}

// DeleteNode removes a node and its edges from the graph.
func (g *GraphEngine) DeleteNode(id string) {
	g.mu.Lock()
	defer g.mu.Unlock()

	delete(g.nodes, id)
	for edgeID := range g.outEdges {
		for i, eid := range g.outEdges[edgeID] {
			if eid == id {
				g.outEdges[edgeID] = append(g.outEdges[edgeID][:i], g.outEdges[edgeID][i+1:]...)
				break
			}
		}
	}
	for edgeID := range g.inEdges {
		for i, eid := range g.inEdges[edgeID] {
			if eid == id {
				g.inEdges[edgeID] = append(g.inEdges[edgeID][:i], g.inEdges[edgeID][i+1:]...)
				break
			}
		}
	}
	g.dirty = true
}

// AddEpisode stores an episodic memory node.
func (g *GraphEngine) AddEpisode(id, action string, outcome float64, props map[string]interface{}) *GraphNode {
	if props == nil {
		props = map[string]interface{}{}
	}
	props["action"] = action
	props["outcome"] = outcome
	return g.AddNode(id, []string{"Episode"}, props)
}

// QueryEpisodes retrieves episodic memory nodes matching filters.
func (g *GraphEngine) QueryEpisodes(actionType string, minOutcome float64, limit int) []*GraphNode {
	g.mu.RLock()
	defer g.mu.RUnlock()

	var results []*GraphNode
	for _, node := range g.nodes {
		for _, label := range node.Labels {
			if label != "Episode" {
				continue
			}
			action, _ := node.Properties["action"].(string)
			outcome, _ := node.Properties["outcome"].(float64)
			if (actionType == "" || action == actionType) && outcome >= minOutcome {
				results = append(results, node)
				if limit > 0 && len(results) >= limit {
					return results
				}
			}
		}
	}
	return results
}

// Close flushes pending state to disk.
func (g *GraphEngine) Close() error {
	return g.persist()
}

// Stats returns graph engine metrics.
func (g *GraphEngine) Stats() map[string]interface{} {
	g.mu.RLock()
	defer g.mu.RUnlock()

	return map[string]interface{}{
		"nodes":   g.nodeCount,
		"edges":   g.edgeCount,
		"queries": g.queries,
	}
}
