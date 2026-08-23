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
	// HTTP operations
	Get(ctx context.Context, url string) (interface{}, error)
}