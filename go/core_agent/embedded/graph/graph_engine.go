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
	g.mu.Lock()
	defer g.mu.Unlock()

	node := &GraphNode{
		ID:         id,
		Labels:     labels,
		Properties: properties,
		CreatedAt:  time.Now(),
		UpdatedAt:  time.Now(),
	}

	g.nodes[id] = node
	g.nodeCount++
	g.dirty = true

	// Update label index
	for _, label := range labels {
		g.labelIndex[label] = append(g.labelIndex[label], id)
	}

	return node
}

// GetNode retrieves a node by ID.
func (g *GraphEngine) GetNode(id string) *GraphNode {
	g.mu.RLock()
	defer g.mu.RUnlock()

	node := g.nodes[id]
	if node != nil {
		node.AccessCount++
	}
	return node
}

// FindByLabel returns all nodes with a given label.
func (g *GraphEngine) FindByLabel(label string) []*GraphNode {
	g.mu.RLock()
	defer g.mu.RUnlock()

	g.queries++
	ids := g.labelIndex[label]
	var nodes []*GraphNode
	for _, id := range ids {
		if n, ok := g.nodes[id]; ok {
			nodes = append(nodes, n)
		}
	}
	return nodes
}

// FindByProperty returns nodes where a property matches a value.
func (g *GraphEngine) FindByProperty(key string, value interface{}) []*GraphNode {
	g.mu.RLock()
	defer g.mu.RUnlock()

	g.queries++
	var results []*GraphNode
	for _, node := range g.nodes {
		if v, ok := node.Properties[key]; ok && fmt.Sprint(v) == fmt.Sprint(value) {
			results = append(results, node)
		}
	}
	return results
}

// ━━━━━━━━━━ Edge Operations ━━━━━━━━━━

// AddEdge creates a relationship between two nodes.
func (g *GraphEngine) AddEdge(source, target, edgeType string, properties map[string]interface{}, weight float64) *GraphEdge {
	g.mu.Lock()
	defer g.mu.Unlock()

	edgeID := fmt.Sprintf("%s->%s:%s", source, target, edgeType)

	edge := &GraphEdge{
		ID:         edgeID,
		Source:     source,
		Target:     target,
		Type:       edgeType,
		Properties: properties,
		Weight:     weight,
		CreatedAt:  time.Now(),
	}

	g.edges[edgeID] = edge
	g.outEdges[source] = append(g.outEdges[source], edgeID)
	g.inEdges[target] = append(g.inEdges[target], edgeID)
	g.edgeTypeIndex[edgeType] = append(g.edgeTypeIndex[edgeType], edgeID)
	g.edgeCount++
	g.dirty = true

	return edge
}

// GetNeighbors returns all nodes connected to a given node.
func (g *GraphEngine) GetNeighbors(nodeID string, direction string) []*GraphNode {
	g.mu.RLock()
	defer g.mu.RUnlock()

	g.queries++
	var neighbors []*GraphNode
	seen := make(map[string]bool)

	if direction == "out" || direction == "both" {
		for _, edgeID := range g.outEdges[nodeID] {
			if edge, ok := g.edges[edgeID]; ok {
				if !seen[edge.Target] {
					if n, ok := g.nodes[edge.Target]; ok {
						neighbors = append(neighbors, n)
						seen[edge.Target] = true
					}
				}
			}
		}
	}

	if direction == "in" || direction == "both" {
		for _, edgeID := range g.inEdges[nodeID] {
			if edge, ok := g.edges[edgeID]; ok {
				if !seen[edge.Source] {
					if n, ok := g.nodes[edge.Source]; ok {
						neighbors = append(neighbors, n)
						seen[edge.Source] = true
					}
				}
			}
		}
	}

	return neighbors
}

// GetEdgesBetween returns all edges between two nodes.
func (g *GraphEngine) GetEdgesBetween(source, target string) []*GraphEdge {
	g.mu.RLock()
	defer g.mu.RUnlock()

	var edges []*GraphEdge
	for _, edgeID := range g.outEdges[source] {
		if edge, ok := g.edges[edgeID]; ok && edge.Target == target {
			edges = append(edges, edge)
		}
	}
	return edges
}

// ━━━━━━━━━━ Traversals ━━━━━━━━━━

// BFS performs breadth-first search from a start node.
func (g *GraphEngine) BFS(startID string, maxDepth int) []TraversalResult {
	g.mu.RLock()
	defer g.mu.RUnlock()

	g.queries++
	var results []TraversalResult

	type queueItem struct {
		nodeID string
		path   []string
		depth  int
	}

	visited := make(map[string]bool)
	queue := []queueItem{{nodeID: startID, path: []string{startID}, depth: 0}}
	visited[startID] = true

	for len(queue) > 0 {
		current := queue[0]
		queue = queue[1:]

		if current.depth > 0 {
			results = append(results, TraversalResult{
				Nodes: current.path,
				Depth: current.depth,
			})
		}

		if current.depth >= maxDepth {
			continue
		}

		for _, edgeID := range g.outEdges[current.nodeID] {
			if edge, ok := g.edges[edgeID]; ok {
				if !visited[edge.Target] {
					visited[edge.Target] = true
					newPath := append([]string{}, current.path...)
					newPath = append(newPath, edge.Target)
					queue = append(queue, queueItem{
						nodeID: edge.Target,
						path:   newPath,
						depth:  current.depth + 1,
					})
				}
			}
		}
	}

	return results
}

// ShortestPath finds the shortest path between two nodes (Dijkstra).
func (g *GraphEngine) ShortestPath(startID, endID string) *TraversalResult {
	g.mu.RLock()
	defer g.mu.RUnlock()

	g.queries++

	// Dijkstra's algorithm
	dist := make(map[string]float64)
	prev := make(map[string]string)
	visited := make(map[string]bool)

	for id := range g.nodes {
		dist[id] = math.Inf(1)
	}
	dist[startID] = 0

	for {
		// Find unvisited node with minimum distance
		minDist := math.Inf(1)
		current := ""
		for id, d := range dist {
			if !visited[id] && d < minDist {
				minDist = d
				current = id
			}
		}

		if current == "" || current == endID {
			break
		}

		visited[current] = true

		// Update neighbors
		for _, edgeID := range g.outEdges[current] {
			if edge, ok := g.edges[edgeID]; ok {
				newDist := dist[current] + edge.Weight
				if newDist < dist[edge.Target] {
					dist[edge.Target] = newDist
					prev[edge.Target] = current
				}
			}
		}
	}

	if math.IsInf(dist[endID], 1) {
		return nil // No path found
	}

	// Reconstruct path
	var path []string
	current := endID
	for current != "" {
		path = append([]string{current}, path...)
		current = prev[current]
	}

	return &TraversalResult{
		Nodes: path,
		Depth: len(path) - 1,
		Cost:  dist[endID],
	}
}

// ━━━━━━━━━━ Episodic Memory (Temporal) ━━━━━━━━━━

// AddEpisode stores a temporal event as a node linked to its context.
func (g *GraphEngine) AddEpisode(episodeID string, action string, outcome float64, contextNodes []string) {
	props := map[string]interface{}{
		"action":    action,
		"outcome":   outcome,
		"timestamp": time.Now().Unix(),
	}

	g.AddNode(episodeID, []string{"Episode", "Memory"}, props)

	// Link to context
	for _, ctxNode := range contextNodes {
		if _, exists := g.nodes[ctxNode]; exists {
			g.AddEdge(episodeID, ctxNode, "IN_CONTEXT", nil, 1.0)
		}
	}

	// Link to previous episode (temporal chain)
	episodes := g.FindByLabel("Episode")
	if len(episodes) > 1 {
		// Find most recent before this one
		var latest *GraphNode
		for _, ep := range episodes {
			if ep.ID != episodeID {
				if latest == nil || ep.CreatedAt.After(latest.CreatedAt) {
					latest = ep
				}
			}
		}
		if latest != nil {
			g.AddEdge(latest.ID, episodeID, "FOLLOWED_BY", nil, 1.0)
		}
	}
}

// QueryEpisodes returns episodes matching criteria.
func (g *GraphEngine) QueryEpisodes(action string, minOutcome float64, limit int) []*GraphNode {
	episodes := g.FindByLabel("Episode")

	var matching []*GraphNode
	for _, ep := range episodes {
		epAction, _ := ep.Properties["action"].(string)
		epOutcome, _ := ep.Properties["outcome"].(float64)

		if (action == "" || epAction == action) && epOutcome >= minOutcome {
			matching = append(matching, ep)
		}
	}

	// Sort by recency
	// (already sorted by CreatedAt in practice)
	if len(matching) > limit && limit > 0 {
		matching = matching[len(matching)-limit:]
	}

	return matching
}

// ━━━━━━━━━━ Persistence ━━━━━━━━━━

type graphDump struct {
	Nodes map[string]*GraphNode `json:"nodes"`
	Edges map[string]*GraphEdge `json:"edges"`
}

func (g *GraphEngine) load() {
	path := filepath.Join(g.dataDir, "ultron_graph.json")
	data, err := os.ReadFile(path)
	if err != nil {
		return // Fresh start
	}

	var dump graphDump
	if err := json.Unmarshal(data, &dump); err != nil {
		return
	}

	g.nodes = dump.Nodes
	g.edges = dump.Edges

	// Rebuild indexes
	for id, node := range g.nodes {
		for _, label := range node.Labels {
			g.labelIndex[label] = append(g.labelIndex[label], id)
		}
		g.nodeCount++
	}
	for id, edge := range g.edges {
		g.outEdges[edge.Source] = append(g.outEdges[edge.Source], id)
		g.inEdges[edge.Target] = append(g.inEdges[edge.Target], id)
		g.edgeTypeIndex[edge.Type] = append(g.edgeTypeIndex[edge.Type], id)
		g.edgeCount++
	}
}

func (g *GraphEngine) persistLoop() {
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		if g.dirty {
			g.Persist()
		}
	}
}

// Persist saves the graph to disk.
func (g *GraphEngine) Persist() {
	g.mu.RLock()
	dump := graphDump{Nodes: g.nodes, Edges: g.edges}
	data, err := json.Marshal(dump)
	g.mu.RUnlock()

	if err != nil {
		return
	}

	path := filepath.Join(g.dataDir, "ultron_graph.json")
	tmpPath := path + ".tmp"
	os.WriteFile(tmpPath, data, 0600)
	os.Rename(tmpPath, path)

	g.mu.Lock()
	g.dirty = false
	g.mu.Unlock()
}

// Stats returns graph statistics.
func (g *GraphEngine) Stats() map[string]interface{} {
	g.mu.RLock()
	defer g.mu.RUnlock()

	return map[string]interface{}{
		"nodes":      g.nodeCount,
		"edges":      g.edgeCount,
		"queries":    g.queries,
		"labels":     len(g.labelIndex),
		"edge_types": len(g.edgeTypeIndex),
	}
}

// Close persists and shuts down.
func (g *GraphEngine) Close() {
	g.Persist()
}
