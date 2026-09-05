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
	domainNames := []string{"Web", "Cloud", "IoT", "Filesystem", "Network", "Compute"}
	if int(d) < len(domainNames) {
		return domainNames[d]
	}
	return "Unknown"
}

// Permission defines what actions are allowed.
type Permission struct {
	Domain      ActionDomain
	Action      string
	Allowed     bool
	MaxActions  int           // Max actions per minute
	RequiresAuth bool
}

// ActionRequest is a request to perform an external action.
type ActionRequest struct {
	RequestID    string
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
	UndoFunction func() error // Function to reverse this action
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
	successfulActions uint64
	failedActions  uint64
	totalLatency   time.Duration
}

// WebHandler defines web interaction capabilities.
type WebHandler interface {
	Execute(ctx context.Context, req *ActionRequest) (*ActionResponse, error)
}

// CloudHandler defines cloud resource management capabilities.
type CloudHandler interface {
	Execute(ctx context.Context, req *ActionRequest) (*ActionResponse, error)
}

// IoTHandler defines IoT device control capabilities.
type IoTHandler interface {
	Execute(ctx context.Context, req *ActionRequest) (*ActionResponse, error)
}

// FilesystemHandler defines filesystem operation capabilities.
type FilesystemHandler interface {
	Execute(ctx context.Context, req *ActionRequest) (*ActionResponse, error)
}

// RateLimiter enforces per-request rate limits.
type RateLimiter struct {
	mu       sync.Mutex
	counters map[string]int
	limit    int
}

// Allow returns true if the given ID is within its rate limit.
func (r *RateLimiter) Allow(id string) bool {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.counters[id]++
	return r.counters[id] <= r.limit
}

// ━━━━━━━━━━ Shared domain types used by sub-packages ━━━━━━━━━━

// SearchResult is a single web search result.
type SearchResult struct {
	Title   string `json:"title"`
	URL     string `json:"url"`
	Snippet string `json:"snippet"`
	Rank    int    `json:"rank"`
}

// DeviceInfo describes an IoT device.
type DeviceInfo struct {
	ID       string    `json:"id"`
	Name     string    `json:"name"`
	Type     string    `json:"type"`
	Online   bool      `json:"online"`
	LastSeen time.Time `json:"last_seen"`
}

// InstanceSpec describes a cloud instance to launch.
type InstanceSpec struct {
	Type     string            `json:"type"`    // e.g. "t3.micro"
	Image    string            `json:"image"`   // AMI ID
	Tags     map[string]string `json:"tags"`
	MaxCost  float64           `json:"max_cost"` // $/hr budget cap
}

// InstanceInfo describes a running cloud instance.
type InstanceInfo struct {
	ID     string        `json:"id"`
	Type   string        `json:"type"`
	State  string        `json:"state"`
	IP     string        `json:"ip"`
	Uptime time.Duration `json:"uptime"`
}

// AutoScalePolicy defines auto-scaling parameters.
type AutoScalePolicy struct {
	MinInstances int     `json:"min_instances"`
	MaxInstances int     `json:"max_instances"`
	TargetCPU    float64 `json:"target_cpu"` // 0-1
}

// ExecuteAction performs an external action based on the request.
func (a *ActionInterface) ExecuteAction(ctx context.Context, req *ActionRequest) (*ActionResponse, error) {
	if req == nil {
		return nil, fmt.Errorf("action request is nil")
	}
	if req.RequestID == "" {
		return nil, fmt.Errorf("request ID is empty")
	}
	if req.Domain == 0 {
		return nil, fmt.Errorf("action domain is unknown")
	}
	if req.Operation == "" {
		return nil, fmt.Errorf("operation is empty")
	}
	if req.Target == "" {
		return nil, fmt.Errorf("target is empty")
	}
	if req.Parameters == nil {
		req.Parameters = make(map[string]interface{})
	}
	if req.Priority < 0 {
		req.Priority = 0
	}
	if req.Timeout <= 0 {
		req.Timeout = 10 * time.Second
	}

	a.mu.RLock()
	defer a.mu.RUnlock()

	// Check rate limit
	if a.rateLimiter != nil {
		if !a.rateLimiter.Allow(req.RequestID) {
			return nil, fmt.Errorf("rate limit exceeded")
		}
	}

	// Check permission
	for _, p := range a.permissions {
		if p.Domain == req.Domain && p.Action == req.Operation {
			if !p.Allowed {
				return nil, fmt.Errorf("permission denied")
			}
			break
		}
	}

	// Execute action
	var resp *ActionResponse
	var err error
	switch req.Domain {
	case DomainWeb:
		resp, err = a.webHandler.Execute(ctx, req)
	case DomainCloud:
		resp, err = a.cloudHandler.Execute(ctx, req)
	case DomainIoT:
		resp, err = a.iotHandler.Execute(ctx, req)
	case DomainFilesystem:
		resp, err = a.fsHandler.Execute(ctx, req)
	default:
		return nil, fmt.Errorf("unknown domain")
	}

	// Log audit entry
	a.logAuditEntry(req, resp)

	return resp, err
}

// logAuditEntry logs an action audit entry.
func (a *ActionInterface) logAuditEntry(req *ActionRequest, resp *ActionResponse) {
	a.mu.Lock()
	defer a.mu.Unlock()

	entry := ActionAuditEntry{
		Timestamp:   time.Now(),
		RequestID:   req.RequestID,
		Domain:      req.Domain,
		Operation:   req.Operation,
		Target:      req.Target,
		Success:     resp.Success,
		Duration:    resp.Duration,
		Error:       "",
		RequestedBy: req.RequestedBy,
	}

	if resp.Error != nil {
		entry.Error = resp.Error.Error()
	}

	a.auditLog = append(a.auditLog, entry)
}

// GetAuditLog returns the action audit log.
func (a *ActionInterface) GetAuditLog() []ActionAuditEntry {
	a.mu.RLock()
	defer a.mu.RUnlock()

	return a.auditLog
}

// GetMetrics returns the action metrics.
func (a *ActionInterface) GetMetrics() (uint64, uint64, uint64, time.Duration) {
	a.mu.RLock()
	defer a.mu.RUnlock()

	return a.totalActions, a.successfulActions, a.failedActions, a.totalLatency
}

// ExecuteActionWithTimeout executes an action with a timeout.
func (a *ActionInterface) ExecuteActionWithTimeout(ctx context.Context, req *ActionRequest, timeout time.Duration) (*ActionResponse, error) {
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	return a.ExecuteAction(ctx, req)
}

// NewActionInterface creates and returns a new ActionInterface.
func NewActionInterface(logger interface{}) *ActionInterface {
	return &ActionInterface{
		permissions: make([]Permission, 0),
		auditLog:    make([]ActionAuditEntry, 0),
	}
}

// SetWebHandler wires the web handler.
func (a *ActionInterface) SetWebHandler(h WebHandler) {
	a.mu.Lock()
	a.webHandler = h
	a.mu.Unlock()
}

// SetCloudHandler wires the cloud handler.
func (a *ActionInterface) SetCloudHandler(h CloudHandler) {
	a.mu.Lock()
	a.cloudHandler = h
	a.mu.Unlock()
}

// SetIoTHandler wires the IoT handler.
func (a *ActionInterface) SetIoTHandler(h IoTHandler) {
	a.mu.Lock()
	a.iotHandler = h
	a.mu.Unlock()
}

// SetFilesystemHandler wires the filesystem handler.
func (a *ActionInterface) SetFilesystemHandler(h FilesystemHandler) {
	a.mu.Lock()
	a.fsHandler = h
	a.mu.Unlock()
}
