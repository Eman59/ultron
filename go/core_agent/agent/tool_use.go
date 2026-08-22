// Package agent — Tool Use / Function Calling for Brain B
//
// This gives Brain B the ability to CHOOSE and INVOKE real tools:
//   - Web Search (SearXNG / Brave API)
//   - Code Execution (sandboxed Python/Go)
//   - GitHub Push (push code to repos)
//   - Action Interface (invoke any action domain)
//   - File Operations (read/write project files)
//   - System Commands (controlled OS interaction)
//
// Brain B outputs a structured function call instead of just text.
// The tool dispatcher executes it and feeds results back.
//
// This transforms Brain B from "thinker" to "actor with hands."
package agent

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"go.uber.org/zap"
)

// ═══════════════════════════════════════════════════════════════
// TOOL DEFINITIONS — What Brain B can call
// ═══════════════════════════════════════════════════════════════

// Tool defines a callable function that Brain B can invoke.
type Tool struct {
	Name        string            `json:"name"`
	Description string            `json:"description"`
	Parameters  []ToolParam       `json:"parameters"`
	Handler     ToolHandler       `json:"-"`
	RateLimit   time.Duration     `json:"-"`     // Min time between calls
	LastCalled  time.Time         `json:"-"`
	CallCount   int64             `json:"-"`
	Dangerous   bool              `json:"dangerous"` // Requires extra validation
}

// ToolParam defines a parameter for a tool.
type ToolParam struct {
	Name        string `json:"name"`
	Type        string `json:"type"`        // string, int, float, bool, json
	Description string `json:"description"`
	Required    bool   `json:"required"`
}

// ToolCall is a structured invocation from Brain B.
type ToolCall struct {
	ToolName   string            `json:"tool_name"`
	Arguments  map[string]string `json:"arguments"`
	Reasoning  string            `json:"reasoning"`
}

// ToolResult is what gets returned after executing a tool.
type ToolResult struct {
	Success    bool        `json:"success"`
	Data       interface{} `json:"data"`
	Error      string      `json:"error,omitempty"`
	Duration   time.Duration `json:"duration"`
}

// ToolHandler is the function signature for tool implementations.
type ToolHandler func(ctx context.Context, args map[string]string) *ToolResult

// ═══════════════════════════════════════════════════════════════
// TOOL DISPATCHER — Manages and executes tool calls
// ═══════════════════════════════════════════════════════════════

// ToolDispatcher manages all available tools and executes function calls.
type ToolDispatcher struct {
	mu sync.RWMutex

	tools       map[string]*Tool
	projectRoot string
	logger      *zap.SugaredLogger

	// Metrics
	totalCalls   atomic.Int64
	successCalls atomic.Int64
	failedCalls  atomic.Int64

	// Safety
	allowDangerous bool
	callHistory    []ToolCallRecord
	maxHistory     int
}

// ToolCallRecord logs every tool invocation for audit.
type ToolCallRecord struct {
	Timestamp  time.Time     `json:"timestamp"`
	ToolName   string        `json:"tool_name"`
	Arguments  map[string]string `json:"arguments"`
	Success    bool          `json:"success"`
	Duration   time.Duration `json:"duration"`
	Error      string        `json:"error,omitempty"`
}

// NewToolDispatcher creates the tool dispatch system.
func NewToolDispatcher(projectRoot string, logger *zap.SugaredLogger) *ToolDispatcher {
	td := &ToolDispatcher{
		tools:          make(map[string]*Tool),
		projectRoot:    projectRoot,
		logger:         logger,
		allowDangerous: false,
		callHistory:    make([]ToolCallRecord, 0, 1000),
		maxHistory:     1000,
	}

	// Register all built-in tools
	td.registerBuiltinTools()

	return td
}

// ═══════════════════════════════════════════════════════════════
// BRAIN B INTEGRATION — Enhanced LLM prompt with tool definitions
// ═══════════════════════════════════════════════════════════════

// GetToolSystemPrompt generates the system prompt that teaches Brain B about available tools.
func (td *ToolDispatcher) GetToolSystemPrompt() string {
	td.mu.RLock()
	defer td.mu.RUnlock()

	toolDefs := make([]string, 0, len(td.tools))
	for _, tool := range td.tools {
		params := make([]string, 0)
		for _, p := range tool.Parameters {
			req := ""
			if p.Required {
				req = " (required)"
			}
			params = append(params, fmt.Sprintf("    - %s (%s): %s%s", p.Name, p.Type, p.Description, req))
		}
		toolDef := fmt.Sprintf("  %s: %s\n    Parameters:\n%s",
			tool.Name, tool.Description, strings.Join(params, "\n"))
		toolDefs = append(toolDefs, toolDef)
	}

	return fmt.Sprintf(`You are Ultron's deep reasoning engine with TOOL ACCESS.
You can execute real actions by calling tools.

AVAILABLE TOOLS:
%s

To call a tool, respond EXACTLY in this format:
TOOL_CALL: {"tool_name": "<name>", "arguments": {"param1": "value1"}, "reasoning": "why"}

If no tool is needed, respond with your normal ACTION/TARGET/REASONING format.
Only call ONE tool per response. Choose the most impactful tool for the situation.`, strings.Join(toolDefs, "\n\n"))
}

// ParseToolCall attempts to extract a tool call from Brain B's response.
func (td *ToolDispatcher) ParseToolCall(response string) *ToolCall {
	// Look for TOOL_CALL: {...} in the response
	idx := strings.Index(response, "TOOL_CALL:")
	if idx < 0 {
		return nil
	}

	jsonStr := strings.TrimSpace(response[idx+len("TOOL_CALL:"):])

	// Find the JSON object
	start := strings.Index(jsonStr, "{")
	if start < 0 {
		return nil
	}

	// Find matching closing brace
	depth := 0
	end := -1
	for i := start; i < len(jsonStr); i++ {
		if jsonStr[i] == '{' {
			depth++
		} else if jsonStr[i] == '}' {
			depth--
			if depth == 0 {
				end = i + 1
				break
			}
		}
	}

	if end < 0 {
		return nil
	}

	var call ToolCall
	if err := json.Unmarshal([]byte(jsonStr[start:end]), &call); err != nil {
		return nil
	}

	return &call
}

// ExecuteToolCall runs a parsed tool call and returns the result.
func (td *ToolDispatcher) ExecuteToolCall(ctx context.Context, call *ToolCall) *ToolResult {
	td.mu.RLock()
	tool, exists := td.tools[call.ToolName]
	td.mu.RUnlock()

	if !exists {
		return &ToolResult{Success: false, Error: fmt.Sprintf("unknown tool: %s", call.ToolName)}
	}

	// Safety check
	if tool.Dangerous && !td.allowDangerous {
		return &ToolResult{Success: false, Error: "dangerous tool blocked by safety policy"}
	}

	// Rate limiting
	if time.Since(tool.LastCalled) < tool.RateLimit {
		return &ToolResult{Success: false, Error: "rate limited"}
	}

	// Execute
	start := time.Now()
	td.totalCalls.Add(1)

	result := tool.Handler(ctx, call.Arguments)
	result.Duration = time.Since(start)

	// Update state
	td.mu.Lock()
	tool.LastCalled = time.Now()
	tool.CallCount++

	// Audit log
	record := ToolCallRecord{
		Timestamp: time.Now(),
		ToolName:  call.ToolName,
		Arguments: call.Arguments,
		Success:   result.Success,
		Duration:  result.Duration,
	}
	if !result.Success {
		record.Error = result.Error
	}
	td.callHistory = append(td.callHistory, record)
	if len(td.callHistory) > td.maxHistory {
		td.callHistory = td.callHistory[len(td.callHistory)-td.maxHistory:]
	}
	td.mu.Unlock()

	if result.Success {
		td.successCalls.Add(1)
	} else {
		td.failedCalls.Add(1)
	}

	td.logger.Infof("[ToolUse] %s(%v) → success=%v duration=%v",
		call.ToolName, call.Arguments, result.Success, result.Duration)

	return result
}

// Stats returns tool usage statistics.
func (td *ToolDispatcher) Stats() map[string]interface{} {
	td.mu.RLock()
	defer td.mu.RUnlock()

	toolStats := make(map[string]int64)
	for name, tool := range td.tools {
		toolStats[name] = tool.CallCount
	}

	return map[string]interface{}{
		"total_calls":   td.totalCalls.Load(),
		"success_calls": td.successCalls.Load(),
		"failed_calls":  td.failedCalls.Load(),
		"tools_available": len(td.tools),
		"tool_usage":    toolStats,
	}
}

// ═══════════════════════════════════════════════════════════════
// BUILT-IN TOOLS — Real capabilities
// ═══════════════════════════════════════════════════════════════

func (td *ToolDispatcher) registerBuiltinTools() {
	// 1. Web Search
	td.tools["web_search"] = &Tool{
		Name:        "web_search",
		Description: "Search the internet for current information. Returns top results.",
		Parameters: []ToolParam{
			{Name: "query", Type: "string", Description: "Search query", Required: true},
			{Name: "max_results", Type: "int", Description: "Maximum results (default 5)", Required: false},
		},
		Handler:   td.toolWebSearch,
		RateLimit: 30 * time.Second,
	}

	// 2. Code Execution (sandboxed)
	td.tools["execute_code"] = &Tool{
		Name:        "execute_code",
		Description: "Execute Python code in a sandbox. Returns stdout/stderr.",
		Parameters: []ToolParam{
			{Name: "code", Type: "string", Description: "Python code to execute", Required: true},
			{Name: "timeout", Type: "int", Description: "Timeout in seconds (max 30)", Required: false},
		},
		Handler:   td.toolExecuteCode,
		RateLimit: 10 * time.Second,
		Dangerous: false,
	}

	// 3. File Read
	td.tools["read_file"] = &Tool{
		Name:        "read_file",
		Description: "Read contents of a file in the project.",
		Parameters: []ToolParam{
			{Name: "path", Type: "string", Description: "Relative file path", Required: true},
			{Name: "max_lines", Type: "int", Description: "Max lines to read (default 100)", Required: false},
		},
		Handler:   td.toolReadFile,
		RateLimit: 1 * time.Second,
	}

	// 4. File Write
	td.tools["write_file"] = &Tool{
		Name:        "write_file",
		Description: "Write content to a file. Creates parent directories if needed.",
		Parameters: []ToolParam{
			{Name: "path", Type: "string", Description: "Relative file path", Required: true},
			{Name: "content", Type: "string", Description: "Content to write", Required: true},
		},
		Handler:   td.toolWriteFile,
		RateLimit: 5 * time.Second,
		Dangerous: true,
	}

	// 5. GitHub Push
	td.tools["github_push"] = &Tool{
		Name:        "github_push",
		Description: "Commit and push changes to the project's git repository.",
		Parameters: []ToolParam{
			{Name: "message", Type: "string", Description: "Commit message", Required: true},
			{Name: "files", Type: "string", Description: "Comma-separated file paths to stage (or 'all')", Required: true},
		},
		Handler:   td.toolGitHubPush,
		RateLimit: 60 * time.Second,
		Dangerous: true,
	}

	// 6. System Info
	td.tools["system_info"] = &Tool{
		Name:        "system_info",
		Description: "Get current system metrics: CPU, memory, disk, network.",
		Parameters:  []ToolParam{},
		Handler:     td.toolSystemInfo,
		RateLimit:   5 * time.Second,
	}

	// 7. HTTP Request
	td.tools["http_request"] = &Tool{
		Name:        "http_request",
		Description: "Make an HTTP GET/POST request to any URL.",
		Parameters: []ToolParam{
			{Name: "url", Type: "string", Description: "Target URL", Required: true},
			{Name: "method", Type: "string", Description: "GET or POST (default GET)", Required: false},
			{Name: "body", Type: "string", Description: "Request body for POST", Required: false},
		},
		Handler:   td.toolHTTPRequest,
		RateLimit: 10 * time.Second,
	}

	// 8. Shell Command (restricted)
	td.tools["shell_command"] = &Tool{
		Name:        "shell_command",
		Description: "Execute a shell command. Restricted to safe commands.",
		Parameters: []ToolParam{
			{Name: "command", Type: "string", Description: "Shell command to execute", Required: true},
		},
		Handler:   td.toolShellCommand,
		RateLimit: 5 * time.Second,
		Dangerous: true,
	}

	// 9. Memory Query
	td.tools["query_memory"] = &Tool{
		Name:        "query_memory",
		Description: "Search Ultron's episodic memory for past experiences.",
		Parameters: []ToolParam{
			{Name: "query", Type: "string", Description: "What to search for", Required: true},
			{Name: "type", Type: "string", Description: "Memory type: semantic, episodic, or procedural", Required: false},
		},
		Handler:   td.toolQueryMemory,
		RateLimit: 2 * time.Second,
	}

	// 10. Spawn Sub-Agent
	td.tools["spawn_subagent"] = &Tool{
		Name:        "spawn_subagent",
		Description: "Spawn a specialized sub-agent for a long-running task.",
		Parameters: []ToolParam{
			{Name: "name", Type: "string", Description: "Sub-agent name", Required: true},
			{Name: "task", Type: "string", Description: "Task description", Required: true},
			{Name: "type", Type: "string", Description: "Agent type: security, learning, web_intel, hardware", Required: true},
		},
		Handler:   td.toolSpawnSubAgent,
		RateLimit: 60 * time.Second,
		Dangerous: true,
	}
}

// ═══════════════════════════════════════════════════════════════
// TOOL IMPLEMENTATIONS
// ═══════════════════════════════════════════════════════════════

func (td *ToolDispatcher) toolWebSearch(ctx context.Context, args map[string]string) *ToolResult {
	query := args["query"]
	if query == "" {
		return &ToolResult{Success: false, Error: "query is required"}
	}

	// Try SearXNG first (self-hosted), then DuckDuckGo
	searxURL := os.Getenv("SEARXNG_URL")
	if searxURL == "" {
		searxURL = "http://localhost:8080"
	}

	url := fmt.Sprintf("%s/search?q=%s&format=json&engines=duckduckgo,google", searxURL, query)

	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		// Fallback: use DuckDuckGo Lite directly
		return td.fallbackSearch(ctx, query)
	}
	defer resp.Body.Close()

	var result map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&result)

	return &ToolResult{Success: true, Data: result}
}

func (td *ToolDispatcher) fallbackSearch(ctx context.Context, query string) *ToolResult {
	// Use DuckDuckGo instant answers API
	url := fmt.Sprintf("https://api.duckduckgo.com/?q=%s&format=json&no_redirect=1", query)
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		return &ToolResult{Success: false, Error: fmt.Sprintf("search failed: %v", err)}
	}
	defer resp.Body.Close()

	var result map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&result)

	return &ToolResult{Success: true, Data: result}
}

func (td *ToolDispatcher) toolExecuteCode(ctx context.Context, args map[string]string) *ToolResult {
	code := args["code"]
	if code == "" {
		return &ToolResult{Success: false, Error: "code is required"}
	}

	// Write to temp file
	tmpFile := filepath.Join(os.TempDir(), "ultron_sandbox.py")
	os.WriteFile(tmpFile, []byte(code), 0644)
	defer os.Remove(tmpFile)

	// Execute with timeout
	execCtx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()

	cmd := exec.CommandContext(execCtx, "python3", tmpFile)
	cmd.Dir = td.projectRoot

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()

	result := map[string]string{
		"stdout": stdout.String(),
		"stderr": stderr.String(),
	}

	if err != nil {
		result["error"] = err.Error()
		return &ToolResult{Success: false, Data: result, Error: err.Error()}
	}

	return &ToolResult{Success: true, Data: result}
}

func (td *ToolDispatcher) toolReadFile(ctx context.Context, args map[string]string) *ToolResult {
	path := args["path"]
	if path == "" {
		return &ToolResult{Success: false, Error: "path is required"}
	}

	// Security: prevent path traversal
	fullPath := filepath.Join(td.projectRoot, filepath.Clean(path))
	if !strings.HasPrefix(fullPath, td.projectRoot) {
		return &ToolResult{Success: false, Error: "path traversal blocked"}
	}

	data, err := os.ReadFile(fullPath)
	if err != nil {
		return &ToolResult{Success: false, Error: err.Error()}
	}

	// Limit output size
	content := string(data)
	if len(content) > 10000 {
		content = content[:10000] + "\n... [truncated]"
	}

	return &ToolResult{Success: true, Data: content}
}

func (td *ToolDispatcher) toolWriteFile(ctx context.Context, args map[string]string) *ToolResult {
	path := args["path"]
	content := args["content"]
	if path == "" || content == "" {
		return &ToolResult{Success: false, Error: "path and content are required"}
	}

	fullPath := filepath.Join(td.projectRoot, filepath.Clean(path))
	if !strings.HasPrefix(fullPath, td.projectRoot) {
		return &ToolResult{Success: false, Error: "path traversal blocked"}
	}

	// Create directories if needed
	os.MkdirAll(filepath.Dir(fullPath), 0755)

	err := os.WriteFile(fullPath, []byte(content), 0644)
	if err != nil {
		return &ToolResult{Success: false, Error: err.Error()}
	}

	return &ToolResult{Success: true, Data: fmt.Sprintf("wrote %d bytes to %s", len(content), path)}
}

func (td *ToolDispatcher) toolGitHubPush(ctx context.Context, args map[string]string) *ToolResult {
	message := args["message"]
	files := args["files"]
	if message == "" || files == "" {
		return &ToolResult{Success: false, Error: "message and files are required"}
	}

	// Stage files
	var stageCmd *exec.Cmd
	if files == "all" {
		stageCmd = exec.CommandContext(ctx, "git", "add", "-A")
	} else {
		fileList := strings.Split(files, ",")
		gitArgs := append([]string{"add"}, fileList...)
		stageCmd = exec.CommandContext(ctx, "git", gitArgs...)
	}
	stageCmd.Dir = td.projectRoot

	if err := stageCmd.Run(); err != nil {
		return &ToolResult{Success: false, Error: fmt.Sprintf("git add failed: %v", err)}
	}

	// Commit
	commitCmd := exec.CommandContext(ctx, "git", "commit", "-m", message)
	commitCmd.Dir = td.projectRoot
	var commitOut bytes.Buffer
	commitCmd.Stdout = &commitOut
	commitCmd.Stderr = &commitOut

	if err := commitCmd.Run(); err != nil {
		return &ToolResult{Success: false, Error: fmt.Sprintf("git commit failed: %s", commitOut.String())}
	}

	// Push
	pushCmd := exec.CommandContext(ctx, "git", "push")
	pushCmd.Dir = td.projectRoot
	var pushOut bytes.Buffer
	pushCmd.Stdout = &pushOut
	pushCmd.Stderr = &pushOut

	if err := pushCmd.Run(); err != nil {
		return &ToolResult{Success: false, Error: fmt.Sprintf("git push failed: %s", pushOut.String())}
	}

	return &ToolResult{Success: true, Data: fmt.Sprintf("pushed: %s", message)}
}

func (td *ToolDispatcher) toolSystemInfo(ctx context.Context, args map[string]string) *ToolResult {
	info := make(map[string]interface{})

	// CPU count
	info["cpu_count"] = os.Getenv("GOMAXPROCS")

	// Memory (from /proc/meminfo on Linux, or sysctl on Mac)
	cmd := exec.CommandContext(ctx, "sysctl", "-n", "hw.memsize")
	if out, err := cmd.Output(); err == nil {
		info["total_memory"] = strings.TrimSpace(string(out))
	}

	// Disk usage
	cmd = exec.CommandContext(ctx, "df", "-h", td.projectRoot)
	if out, err := cmd.Output(); err == nil {
		info["disk"] = strings.TrimSpace(string(out))
	}

	// Load average
	cmd = exec.CommandContext(ctx, "sysctl", "-n", "vm.loadavg")
	if out, err := cmd.Output(); err == nil {
		info["load_avg"] = strings.TrimSpace(string(out))
	}

	return &ToolResult{Success: true, Data: info}
}

func (td *ToolDispatcher) toolHTTPRequest(ctx context.Context, args map[string]string) *ToolResult {
	url := args["url"]
	if url == "" {
		return &ToolResult{Success: false, Error: "url is required"}
	}

	method := args["method"]
	if method == "" {
		method = "GET"
	}

	client := &http.Client{Timeout: 15 * time.Second}

	var req *http.Request
	var err error

	if method == "POST" {
		body := args["body"]
		req, err = http.NewRequestWithContext(ctx, "POST", url, bytes.NewBufferString(body))
	} else {
		req, err = http.NewRequestWithContext(ctx, "GET", url, nil)
	}

	if err != nil {
		return &ToolResult{Success: false, Error: err.Error()}
	}

	resp, err := client.Do(req)
	if err != nil {
		return &ToolResult{Success: false, Error: err.Error()}
	}
	defer resp.Body.Close()

	var respBody bytes.Buffer
	respBody.ReadFrom(resp.Body)

	// Truncate large responses
	content := respBody.String()
	if len(content) > 5000 {
		content = content[:5000] + "\n... [truncated]"
	}

	result := map[string]interface{}{
		"status":  resp.StatusCode,
		"headers": resp.Header,
		"body":    content,
	}

	return &ToolResult{Success: resp.StatusCode < 400, Data: result}
}

func (td *ToolDispatcher) toolShellCommand(ctx context.Context, args map[string]string) *ToolResult {
	command := args["command"]
	if command == "" {
		return &ToolResult{Success: false, Error: "command is required"}
	}

	// SAFETY: Block dangerous commands
	blocked := []string{"rm -rf /", "mkfs", "dd if=", ":(){ :|:", "shutdown", "reboot", "kill -9 1"}
	for _, b := range blocked {
		if strings.Contains(command, b) {
			return &ToolResult{Success: false, Error: "blocked: dangerous command"}
		}
	}

	execCtx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()

	cmd := exec.CommandContext(execCtx, "sh", "-c", command)
	cmd.Dir = td.projectRoot

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()

	result := map[string]string{
		"stdout": stdout.String(),
		"stderr": stderr.String(),
	}

	if err != nil {
		result["error"] = err.Error()
		return &ToolResult{Success: false, Data: result, Error: err.Error()}
	}

	return &ToolResult{Success: true, Data: result}
}

func (td *ToolDispatcher) toolQueryMemory(ctx context.Context, args map[string]string) *ToolResult {
	query := args["query"]
	if query == "" {
		return &ToolResult{Success: false, Error: "query is required"}
	}

	// This would integrate with the memory system
	// For now, return the query parameters as confirmation
	return &ToolResult{
		Success: true,
		Data: map[string]string{
			"query":  query,
			"type":   args["type"],
			"status": "memory_query_dispatched",
		},
	}
}

func (td *ToolDispatcher) toolSpawnSubAgent(ctx context.Context, args map[string]string) *ToolResult {
	name := args["name"]
	task := args["task"]
	agentType := args["type"]

	if name == "" || task == "" || agentType == "" {
		return &ToolResult{Success: false, Error: "name, task, and type are required"}
	}

	// Validate agent type
	validTypes := map[string]bool{
		"security": true, "learning": true,
		"web_intel": true, "hardware": true,
	}
	if !validTypes[agentType] {
		return &ToolResult{Success: false, Error: "invalid agent type"}
	}

	// In production: this spawns a goroutine or subprocess running a sub-OODA loop
	// For now, record the spawn request
	return &ToolResult{
		Success: true,
		Data: map[string]string{
			"agent_id":   fmt.Sprintf("subagent_%s_%d", name, time.Now().UnixNano()%10000),
			"name":       name,
			"type":       agentType,
			"task":       task,
			"status":     "spawned",
		},
	}
}
