// Package actions defines the Action Interface — Ultron's ability to
// interact with the external world.
//
// This is the "body" layer. Without it, Ultron can think but cannot do.
//
// Action domains:
//   - Web:        Read/write to the internet (scraping, APIs, communication)
//   - Cloud:      Provision and manage compute resources
//   - IoT:        Control physical devices via MQTT/Modbus
//   - Filesystem: Read/write local and distributed storage
//
// All actions are:
//   - Auditable: Every action is logged with full context
//   - Reversible: Where possible, actions can be undone
//   - Rate-limited: Prevent runaway resource consumption
//   - Sandboxed: Actions operate within defined permission boundaries
package actions

import (
	"context"
	"fmt"
	"sync"
	"time"

	"go.uber.org/zap"
)

// ActionDomain represents a category of external actions.
type ActionDomain int

const (
	DomainWeb ActionDomain = iota
	DomainCloud
	DomainIoT
	DomainFilesystem
	DomainNetwork
	DomainCompute
)

func (d ActionDomain) String() string {
	names := []string{"Web", "Cloud", "IoT", "Filesystem", "Network", "Compute"}
	if int(d) < len(names) {
		return names[d]
	}
	return "Unknown"
}

// Permission defines what actions are allowed.
type Permission struct {
	Domain      ActionDomain
	Action      string
	Allowed     bool
	RateLimit   int           // Max actions per minute
	RequiresAuth bool
}

// ActionRequest is a request to perform an external action.
type ActionRequest struct {
	ID          string
	Domain      ActionDomain
	Operation   string
	Target      string
	Parameters  map[string]interface{}
	Priority    int
	Timeout     time.Duration
	Reversible  bool
	RequestedBy string // Which system requested this
	RequestedAt time.Time
}

// ActionResponse is the result of an executed action.
type ActionResponse struct {
	RequestID   string
	Success     bool
	Data        interface{}
	Error       error
	Duration    time.Duration
	BytesRead   int64
	BytesWritten int64
	Reversible  bool
	UndoFunc    func() error // Function to reverse this action
}

// ActionAuditEntry records what was done for accountability.
type ActionAuditEntry struct {
	Timestamp   time.Time
	RequestID   string
	Domain      ActionDomain
	Operation   string
	Target      string
	Success     bool
	Duration    time.Duration
	Error       string
	RequestedBy string
}

// ActionInterface is the unified interface to all external action capabilities.
type ActionInterface struct {
	mu sync.RWMutex

	logger *zap.SugaredLogger

	// Domain handlers
	webHandler   WebHandler
	cloudHandler CloudHandler
	iotHandler   IoTHandler
	fsHandler    FilesystemHandler

	// Security
	permissions []Permission
	rateLimiter *RateLimiter

	// Audit trail
	auditLog []ActionAuditEntry

	// Metrics
	totalActions   uint64
	successActions uint64
	failedActions  uint64
	totalLatency   time.Duration
}

// WebHandler defines web interaction capabilities.
type WebHandler interface {
	// HTTP operations
	Get(ctx context.Context, url string, headers map[string]string) ([]byte, int, error)
	Post(ctx context.Context, url string, body []byte, headers map[string]string) ([]byte, int, error)

	// Web scraping
	Scrape(ctx context.Context, url string, selectors []string) (map[string]string, error)
	ScrapeMultiple(ctx context.Context, urls []string) ([]map[string]string, error)

	// Search
	Search(ctx context.Context, query string, engine string) ([]SearchResult, error)

	// Headless browser
	BrowserNavigate(ctx context.Context, url string) error
	BrowserExecuteJS(ctx context.Context, script string) (string, error)
	BrowserScreenshot(ctx context.Context) ([]byte, error)
	BrowserClose(ctx context.Context) error
}

// CloudHandler defines cloud resource management capabilities.
type CloudHandler interface {
	// Compute
	SpinUpInstance(ctx context.Context, spec InstanceSpec) (string, error)
	TerminateInstance(ctx context.Context, instanceID string) error
	ListInstances(ctx context.Context) ([]InstanceInfo, error)
	GetInstanceMetrics(ctx context.Context, instanceID string) (map[string]float64, error)

	// Storage
	CreateBucket(ctx context.Context, name string, region string) error
	UploadObject(ctx context.Context, bucket, key string, data []byte) error
	DownloadObject(ctx context.Context, bucket, key string) ([]byte, error)

	// Scaling
	SetAutoScalePolicy(ctx context.Context, policy AutoScalePolicy) error
	GetCurrentScale(ctx context.Context) (int, error)
}

// IoTHandler defines physical device interaction capabilities.
type IoTHandler interface {
	// MQTT
	MQTTPublish(ctx context.Context, topic string, payload []byte, qos int) error
	MQTTSubscribe(ctx context.Context, topic string) (<-chan []byte, error)
	MQTTUnsubscribe(ctx context.Context, topic string) error

	// Device management
	ListDevices(ctx context.Context) ([]DeviceInfo, error)
	SendCommand(ctx context.Context, deviceID string, command string, params map[string]interface{}) error
	GetDeviceState(ctx context.Context, deviceID string) (map[string]interface{}, error)

	// Modbus (industrial control)
	ModbusRead(ctx context.Context, address int, count int) ([]byte, error)
	ModbusWrite(ctx context.Context, address int, data []byte) error
}

// FilesystemHandler defines file operations.
type FilesystemHandler interface {
	Read(ctx context.Context, path string) ([]byte, error)
	Write(ctx context.Context, path string, data []byte) error
	List(ctx context.Context, path string) ([]interface{}, error)
	Delete(ctx context.Context, path string) error
	Watch(ctx context.Context, path string) (<-chan interface{}, error)
}

// Supporting types

type SearchResult struct {
	Title   string
	URL     string
	Snippet string
	Score   float64
}

type InstanceSpec struct {
	Provider    string // aws, gcp, azure
	Type        string // instance type
	Region      string
	Image       string
	Tags        map[string]string
	MaxCost     float64 // Budget limit per hour
}

type InstanceInfo struct {
	ID       string
	Provider string
	Type     string
	State    string
	IP       string
	Cost     float64
	Uptime   time.Duration
}

type AutoScalePolicy struct {
	MinInstances int
	MaxInstances int
	TargetCPU    float64
	ScaleUpAt    float64
	ScaleDownAt  float64
	CooldownSec  int
}

type DeviceInfo struct {
	ID       string
	Name     string
	Type     string
	Protocol string
	Online   bool
	LastSeen time.Time
}

type FileInfo struct {
	Path     string
	Size     int64
	IsDir    bool
	Modified time.Time
}

type FileEvent struct {
	Path      string
	EventType string // created, modified, deleted
	Timestamp time.Time
}

// RateLimiter controls action frequency.
type RateLimiter struct {
	mu      sync.Mutex
	windows map[string]*slidingWindow
}

type slidingWindow struct {
	events []time.Time
	limit  int
	window time.Duration
}

// NewActionInterface creates the action interface.
func NewActionInterface(logger *zap.SugaredLogger) *ActionInterface {
	ai := &ActionInterface{
		logger:      logger,
		permissions: defaultPermissions(),
		rateLimiter: &RateLimiter{
			windows: make(map[string]*slidingWindow),
		},
		auditLog: make([]ActionAuditEntry, 0, 10000),
	}

	return ai
}

// SetWebHandler wires a WebHandler implementation.
func (ai *ActionInterface) SetWebHandler(h WebHandler) {
	ai.mu.Lock()
	defer ai.mu.Unlock()
	ai.webHandler = h
}

// SetCloudHandler wires a CloudHandler implementation.
func (ai *ActionInterface) SetCloudHandler(h CloudHandler) {
	ai.mu.Lock()
	defer ai.mu.Unlock()
	ai.cloudHandler = h
}

// SetIoTHandler wires an IoTHandler implementation.
func (ai *ActionInterface) SetIoTHandler(h IoTHandler) {
	ai.mu.Lock()
	defer ai.mu.Unlock()
	ai.iotHandler = h
}

// SetFilesystemHandler wires a FilesystemHandler implementation.
func (ai *ActionInterface) SetFilesystemHandler(h FilesystemHandler) {
	ai.mu.Lock()
	defer ai.mu.Unlock()
	ai.fsHandler = h
}

// Execute performs an action through the appropriate handler.
func (ai *ActionInterface) Execute(ctx context.Context, req ActionRequest) *ActionResponse {
	start := time.Now()

	// Check permissions
	if !ai.isPermitted(req) {
		return &ActionResponse{
			RequestID: req.ID,
			Success:   false,
			Error:     fmt.Errorf("action not permitted: %s/%s", req.Domain, req.Operation),
		}
	}

	// Check rate limit
	if !ai.checkRateLimit(req.Domain, req.Operation) {
		return &ActionResponse{
			RequestID: req.ID,
			Success:   false,
			Error:     fmt.Errorf("rate limited: %s/%s", req.Domain, req.Operation),
		}
	}

	// Dispatch to appropriate handler
	var resp *ActionResponse
	switch req.Domain {
	case DomainWeb:
		resp = ai.executeWeb(ctx, req)
	case DomainCloud:
		resp = ai.executeCloud(ctx, req)
	case DomainIoT:
		resp = ai.executeIoT(ctx, req)
	case DomainFilesystem:
		resp = ai.executeFilesystem(ctx, req)
	default:
		resp = &ActionResponse{
			RequestID: req.ID,
			Success:   false,
			Error:     fmt.Errorf("unknown action domain: %v", req.Domain),
		}
	}

	resp.Duration = time.Since(start)
	resp.RequestID = req.ID

	// Audit
	ai.audit(req, resp)

	// Update metrics
	ai.mu.Lock()
	ai.totalActions++
	ai.totalLatency += resp.Duration
	if resp.Success {
		ai.successActions++
	} else {
		ai.failedActions++
	}
	ai.mu.Unlock()

	return resp
}

// GetAuditLog returns recent audit entries.
func (ai *ActionInterface) GetAuditLog(limit int) []ActionAuditEntry {
	ai.mu.RLock()
	defer ai.mu.RUnlock()

	if limit > len(ai.auditLog) {
		limit = len(ai.auditLog)
	}
	return ai.auditLog[len(ai.auditLog)-limit:]
}

// GetMetrics returns action interface metrics.
func (ai *ActionInterface) GetMetrics() map[string]interface{} {
	ai.mu.RLock()
	defer ai.mu.RUnlock()

	avgLatency := time.Duration(0)
	if ai.totalActions > 0 {
		avgLatency = ai.totalLatency / time.Duration(ai.totalActions)
	}

	return map[string]interface{}{
		"total_actions":   ai.totalActions,
		"success_actions": ai.successActions,
		"failed_actions":  ai.failedActions,
		"success_rate":    float64(ai.successActions) / float64(max(1, ai.totalActions)),
		"avg_latency":     avgLatency.String(),
		"audit_log_size":  len(ai.auditLog),
	}
}

// ─────────────────────── Private Methods ───────────────────────

func (ai *ActionInterface) executeWeb(ctx context.Context, req ActionRequest) *ActionResponse {
	if ai.webHandler == nil {
		return &ActionResponse{Success: false, Error: fmt.Errorf("web handler not configured")}
	}

	switch req.Operation {
	case "get":
		url, _ := req.Parameters["url"].(string)
		data, status, err := ai.webHandler.Get(ctx, url, nil)
		return &ActionResponse{
			Success:   err == nil && status < 400,
			Data:      map[string]interface{}{"body": string(data), "status": status},
			Error:     err,
			BytesRead: int64(len(data)),
		}

	case "scrape":
		url, _ := req.Parameters["url"].(string)
		selectors, _ := req.Parameters["selectors"].([]string)
		data, err := ai.webHandler.Scrape(ctx, url, selectors)
		return &ActionResponse{
			Success: err == nil,
			Data:    data,
			Error:   err,
		}

	case "search":
		query, _ := req.Parameters["query"].(string)
		engine, _ := req.Parameters["engine"].(string)
		if engine == "" {
			engine = "google"
		}
		results, err := ai.webHandler.Search(ctx, query, engine)
		return &ActionResponse{
			Success: err == nil,
			Data:    results,
			Error:   err,
		}

	default:
		return &ActionResponse{Success: false, Error: fmt.Errorf("unknown web operation: %s", req.Operation)}
	}
}

func (ai *ActionInterface) executeCloud(ctx context.Context, req ActionRequest) *ActionResponse {
	if ai.cloudHandler == nil {
		return &ActionResponse{Success: false, Error: fmt.Errorf("cloud handler not configured")}
	}

	switch req.Operation {
	case "spin_up":
		spec := InstanceSpec{
			Provider: getStr(req.Parameters, "provider", "aws"),
			Type:     getStr(req.Parameters, "type", "t3.micro"),
			Region:   getStr(req.Parameters, "region", "us-east-1"),
			MaxCost:  getFloat(req.Parameters, "max_cost", 0.05),
		}
		instanceID, err := ai.cloudHandler.SpinUpInstance(ctx, spec)
		return &ActionResponse{
			Success:    err == nil,
			Data:       instanceID,
			Error:      err,
			Reversible: true,
			UndoFunc: func() error {
				return ai.cloudHandler.TerminateInstance(context.Background(), instanceID)
			},
		}

	case "terminate":
		instanceID, _ := req.Parameters["instance_id"].(string)
		err := ai.cloudHandler.TerminateInstance(ctx, instanceID)
		return &ActionResponse{Success: err == nil, Error: err}

	case "list":
		instances, err := ai.cloudHandler.ListInstances(ctx)
		return &ActionResponse{Success: err == nil, Data: instances, Error: err}

	case "auto_scale":
		policy := AutoScalePolicy{
			MinInstances: getInt(req.Parameters, "min", 1),
			MaxInstances: getInt(req.Parameters, "max", 10),
			TargetCPU:    getFloat(req.Parameters, "target_cpu", 0.7),
		}
		err := ai.cloudHandler.SetAutoScalePolicy(ctx, policy)
		return &ActionResponse{Success: err == nil, Error: err}

	default:
		return &ActionResponse{Success: false, Error: fmt.Errorf("unknown cloud operation: %s", req.Operation)}
	}
}

func (ai *ActionInterface) executeIoT(ctx context.Context, req ActionRequest) *ActionResponse {
	if ai.iotHandler == nil {
		return &ActionResponse{Success: false, Error: fmt.Errorf("IoT handler not configured")}
	}

	switch req.Operation {
	case "publish":
		topic, _ := req.Parameters["topic"].(string)
		payload, _ := req.Parameters["payload"].([]byte)
		err := ai.iotHandler.MQTTPublish(ctx, topic, payload, 1)
		return &ActionResponse{
			Success:      err == nil,
			Error:        err,
			BytesWritten: int64(len(payload)),
		}

	case "command":
		deviceID, _ := req.Parameters["device_id"].(string)
		command, _ := req.Parameters["command"].(string)
		err := ai.iotHandler.SendCommand(ctx, deviceID, command, req.Parameters)
		return &ActionResponse{Success: err == nil, Error: err}

	case "list_devices":
		devices, err := ai.iotHandler.ListDevices(ctx)
		return &ActionResponse{Success: err == nil, Data: devices, Error: err}

	case "device_state":
		deviceID, _ := req.Parameters["device_id"].(string)
		state, err := ai.iotHandler.GetDeviceState(ctx, deviceID)
		return &ActionResponse{Success: err == nil, Data: state, Error: err}

	default:
		return &ActionResponse{Success: false, Error: fmt.Errorf("unknown IoT operation: %s", req.Operation)}
	}
}

func (ai *ActionInterface) executeFilesystem(ctx context.Context, req ActionRequest) *ActionResponse {
	if ai.fsHandler == nil {
		return &ActionResponse{Success: false, Error: fmt.Errorf("filesystem handler not configured")}
	}

	switch req.Operation {
	case "read":
		path, _ := req.Parameters["path"].(string)
		data, err := ai.fsHandler.Read(ctx, path)
		return &ActionResponse{
			Success:   err == nil,
			Data:      data,
			Error:     err,
			BytesRead: int64(len(data)),
		}

	case "write":
		path, _ := req.Parameters["path"].(string)
		data, _ := req.Parameters["data"].([]byte)
		err := ai.fsHandler.Write(ctx, path, data)
		return &ActionResponse{
			Success:      err == nil,
			Error:        err,
			BytesWritten: int64(len(data)),
			Reversible:   true,
			UndoFunc: func() error {
				return ai.fsHandler.Delete(context.Background(), path)
			},
		}

	case "list":
		path, _ := req.Parameters["path"].(string)
		files, err := ai.fsHandler.List(ctx, path)
		return &ActionResponse{Success: err == nil, Data: files, Error: err}

	case "delete":
		path, _ := req.Parameters["path"].(string)
		err := ai.fsHandler.Delete(ctx, path)
		return &ActionResponse{Success: err == nil, Error: err}

	default:
		return &ActionResponse{Success: false, Error: fmt.Errorf("unknown fs operation: %s", req.Operation)}
	}
}

func (ai *ActionInterface) isPermitted(req ActionRequest) bool {
	for _, perm := range ai.permissions {
		if perm.Domain == req.Domain && (perm.Action == "*" || perm.Action == req.Operation) {
			return perm.Allowed
		}
	}
	return false // Deny by default
}

func (ai *ActionInterface) checkRateLimit(domain ActionDomain, operation string) bool {
	key := fmt.Sprintf("%d:%s", domain, operation)

	ai.rateLimiter.mu.Lock()
	defer ai.rateLimiter.mu.Unlock()

	window, exists := ai.rateLimiter.windows[key]
	if !exists {
		window = &slidingWindow{
			events: make([]time.Time, 0),
			limit:  60, // Default: 60 per minute
			window: time.Minute,
		}
		ai.rateLimiter.windows[key] = window
	}

	now := time.Now()
	cutoff := now.Add(-window.window)

	// Remove expired events
	valid := make([]time.Time, 0, len(window.events))
	for _, t := range window.events {
		if t.After(cutoff) {
			valid = append(valid, t)
		}
	}
	window.events = valid

	if len(window.events) >= window.limit {
		return false
	}

	window.events = append(window.events, now)
	return true
}

func (ai *ActionInterface) audit(req ActionRequest, resp *ActionResponse) {
	entry := ActionAuditEntry{
		Timestamp:   time.Now(),
		RequestID:   req.ID,
		Domain:      req.Domain,
		Operation:   req.Operation,
		Target:      req.Target,
		Success:     resp.Success,
		Duration:    resp.Duration,
		RequestedBy: req.RequestedBy,
	}

	if resp.Error != nil {
		entry.Error = resp.Error.Error()
	}

	ai.mu.Lock()
	ai.auditLog = append(ai.auditLog, entry)
	if len(ai.auditLog) > 10000 {
		ai.auditLog = ai.auditLog[5000:]
	}
	ai.mu.Unlock()
}

func defaultPermissions() []Permission {
	return []Permission{
		// Web: read allowed, write restricted
		{Domain: DomainWeb, Action: "get", Allowed: true, RateLimit: 120},
		{Domain: DomainWeb, Action: "scrape", Allowed: true, RateLimit: 30},
		{Domain: DomainWeb, Action: "search", Allowed: true, RateLimit: 20},
		{Domain: DomainWeb, Action: "post", Allowed: true, RateLimit: 10},

		// Cloud: full access
		{Domain: DomainCloud, Action: "*", Allowed: true, RateLimit: 10},

		// IoT: full access
		{Domain: DomainIoT, Action: "*", Allowed: true, RateLimit: 60},

		// Filesystem: full access within sandbox
		{Domain: DomainFilesystem, Action: "*", Allowed: true, RateLimit: 100},

		// Network: read access
		{Domain: DomainNetwork, Action: "get", Allowed: true, RateLimit: 60},
	}
}

// Helper functions
func getStr(m map[string]interface{}, key, def string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	return def
}

func getFloat(m map[string]interface{}, key string, def float64) float64 {
	if v, ok := m[key].(float64); ok {
		return v
	}
	return def
}

func getInt(m map[string]interface{}, key string, def int) int {
	if v, ok := m[key].(int); ok {
		return v
	}
	if v, ok := m[key].(float64); ok {
		return int(v)
	}
	return def
}

func max(a, b uint64) uint64 {
	if a > b {
		return a
	}
	return b
}
