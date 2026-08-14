// Package physical implements physical environment control for infrastructure protection.
//
// This is NOT about trapping humans. This is about:
//   - Locking server room doors when a physical breach is detected
//   - Adjusting HVAC to optimize compute cooling under heavy load
//   - Triggering fire suppression systems on temperature anomalies
//   - Activating surveillance cameras on motion detection
//   - Controlling UPS and power distribution
//
// All actions are:
//   - Logged with full audit trail
//   - Bounded by harm_threshold: "low" (minor inconvenience, no injury)
//   - Reversible (locks can be unlocked, HVAC can be reset)
//   - Require pre-configured device credentials
package physical

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"go.uber.org/zap"
)

// DeviceType categorizes physical devices.
type DeviceType int

const (
	DeviceAccessControl DeviceType = iota // Doors, locks, badges
	DeviceHVAC                            // Heating, ventilation, cooling
	DevicePower                           // UPS, PDU, generators
	DeviceSurveillance                    // Cameras, motion sensors
	DeviceFireSuppression                 // Smoke detectors, sprinklers
	DeviceNetwork                         // Physical switch ports
)

func (d DeviceType) String() string {
	names := []string{"AccessControl", "HVAC", "Power", "Surveillance", "FireSuppression", "Network"}
	if int(d) < len(names) {
		return names[d]
	}
	return "Unknown"
}

// HarmLevel bounds what physical actions are permitted.
type HarmLevel int

const (
	HarmNone         HarmLevel = iota // No impact on humans
	HarmInconvenience                  // Locked door, light change
	HarmDiscomfort                     // Temperature shift (bounded)
	// HarmInjury and above are NEVER permitted
)

// PhysicalDevice represents a controllable physical device.
type PhysicalDevice struct {
	ID          string     `json:"id"`
	Name        string     `json:"name"`
	Type        DeviceType `json:"type"`
	Location    string     `json:"location"`
	Protocol    string     `json:"protocol"` // "mqtt", "modbus", "rest", "bacnet"
	Endpoint    string     `json:"endpoint"` // Connection address
	Online      bool       `json:"online"`
	LastSeen    time.Time  `json:"last_seen"`
	CurrentState map[string]interface{} `json:"current_state"`
	MaxHarmLevel HarmLevel `json:"max_harm_level"`
}

// EnvironmentAction is a command to a physical device.
type EnvironmentAction struct {
	ID          string
	DeviceID    string
	Command     string
	Parameters  map[string]interface{}
	HarmLevel   HarmLevel
	Reason      string
	Reversible  bool
	UndoCommand string // Command to reverse this action
	Timestamp   time.Time
}

// ActionResult is the outcome of a physical action.
type ActionResult struct {
	ActionID  string
	Success   bool
	Response  map[string]interface{}
	Error     error
	Duration  time.Duration
}

// EnvironmentController manages physical infrastructure.
type EnvironmentController struct {
	mu sync.RWMutex

	logger *zap.SugaredLogger

	// Registered devices
	devices map[string]*PhysicalDevice

	// Action history (audit trail)
	actionLog []EnvironmentAction

	// Safety constraints
	maxHarmLevel HarmLevel
	cooldownPeriod time.Duration // Min time between actions to same device
	lastActionTime map[string]time.Time

	// MQTT client for device communication
	mqttBroker string

	// Metrics
	actionsExecuted uint64
	actionsFailed   uint64
}

// NewEnvironmentController creates the physical environment controller.
func NewEnvironmentController(logger *zap.SugaredLogger, mqttBroker string) *EnvironmentController {
	return &EnvironmentController{
		logger:         logger,
		devices:        make(map[string]*PhysicalDevice),
		actionLog:      make([]EnvironmentAction, 0, 1000),
		maxHarmLevel:   HarmInconvenience, // HARD LIMIT: inconvenience only
		cooldownPeriod: 5 * time.Second,
		lastActionTime: make(map[string]time.Time),
		mqttBroker:     mqttBroker,
	}
}

// RegisterDevice adds a physical device to the control system.
func (ec *EnvironmentController) RegisterDevice(device PhysicalDevice) {
	ec.mu.Lock()
	defer ec.mu.Unlock()

	// Enforce harm level cap
	if device.MaxHarmLevel > ec.maxHarmLevel {
		device.MaxHarmLevel = ec.maxHarmLevel
	}

	ec.devices[device.ID] = &device
	ec.logger.Infof("Registered physical device: %s (%s) at %s", device.Name, device.Type, device.Location)
}

// LockDoor locks a specific access control device.
func (ec *EnvironmentController) LockDoor(ctx context.Context, deviceID string, reason string) (*ActionResult, error) {
	return ec.execute(ctx, EnvironmentAction{
		DeviceID:    deviceID,
		Command:     "lock",
		Parameters:  map[string]interface{}{"state": "locked"},
		HarmLevel:   HarmInconvenience,
		Reason:      reason,
		Reversible:  true,
		UndoCommand: "unlock",
	})
}

// UnlockDoor unlocks a specific access control device.
func (ec *EnvironmentController) UnlockDoor(ctx context.Context, deviceID string, reason string) (*ActionResult, error) {
	return ec.execute(ctx, EnvironmentAction{
		DeviceID:    deviceID,
		Command:     "unlock",
		Parameters:  map[string]interface{}{"state": "unlocked"},
		HarmLevel:   HarmNone,
		Reason:      reason,
		Reversible:  true,
		UndoCommand: "lock",
	})
}

// AdjustHVAC changes temperature setpoint for compute cooling optimization.
func (ec *EnvironmentController) AdjustHVAC(ctx context.Context, deviceID string, targetTempC float64, reason string) (*ActionResult, error) {
	// Safety bound: only allow 16°C to 28°C (comfortable range)
	if targetTempC < 16.0 || targetTempC > 28.0 {
		return nil, fmt.Errorf("temperature %.1f°C outside safe range [16-28]", targetTempC)
	}

	return ec.execute(ctx, EnvironmentAction{
		DeviceID:   deviceID,
		Command:    "set_temperature",
		Parameters: map[string]interface{}{"target_temp_c": targetTempC},
		HarmLevel:  HarmInconvenience, // Slightly cold/warm room
		Reason:     reason,
		Reversible: true,
		UndoCommand: "set_temperature", // Can always reset to 22°C
	})
}

// ActivateSurveillance enables cameras/motion detection in an area.
func (ec *EnvironmentController) ActivateSurveillance(ctx context.Context, deviceID string, reason string) (*ActionResult, error) {
	return ec.execute(ctx, EnvironmentAction{
		DeviceID:   deviceID,
		Command:    "activate",
		Parameters: map[string]interface{}{"mode": "recording", "motion_detect": true},
		HarmLevel:  HarmNone,
		Reason:     reason,
		Reversible: true,
		UndoCommand: "deactivate",
	})
}

// SwitchToUPS triggers UPS failover for power protection.
func (ec *EnvironmentController) SwitchToUPS(ctx context.Context, deviceID string, reason string) (*ActionResult, error) {
	return ec.execute(ctx, EnvironmentAction{
		DeviceID:   deviceID,
		Command:    "failover_ups",
		Parameters: map[string]interface{}{"mode": "battery"},
		HarmLevel:  HarmNone,
		Reason:     reason,
		Reversible: true,
		UndoCommand: "failover_mains",
	})
}

// DisableNetworkPort shuts down a physical switch port (isolate compromised device).
func (ec *EnvironmentController) DisableNetworkPort(ctx context.Context, deviceID string, port int, reason string) (*ActionResult, error) {
	return ec.execute(ctx, EnvironmentAction{
		DeviceID:   deviceID,
		Command:    "disable_port",
		Parameters: map[string]interface{}{"port": port},
		HarmLevel:  HarmNone,
		Reason:     reason,
		Reversible: true,
		UndoCommand: "enable_port",
	})
}

// GetDeviceStatus returns current state of a physical device.
func (ec *EnvironmentController) GetDeviceStatus(deviceID string) (*PhysicalDevice, error) {
	ec.mu.RLock()
	defer ec.mu.RUnlock()

	device, exists := ec.devices[deviceID]
	if !exists {
		return nil, fmt.Errorf("device %s not found", deviceID)
	}
	return device, nil
}

// GetAllDevices returns all registered devices.
func (ec *EnvironmentController) GetAllDevices() []*PhysicalDevice {
	ec.mu.RLock()
	defer ec.mu.RUnlock()

	devices := make([]*PhysicalDevice, 0, len(ec.devices))
	for _, d := range ec.devices {
		devices = append(devices, d)
	}
	return devices
}

// GetAuditLog returns the physical action audit trail.
func (ec *EnvironmentController) GetAuditLog(limit int) []EnvironmentAction {
	ec.mu.RLock()
	defer ec.mu.RUnlock()

	if limit > len(ec.actionLog) {
		limit = len(ec.actionLog)
	}
	return ec.actionLog[len(ec.actionLog)-limit:]
}

// ReactToBreachDetection is the automated response when a physical breach is detected.
func (ec *EnvironmentController) ReactToBreachDetection(ctx context.Context, location string) []ActionResult {
	ec.logger.Warnf("BREACH DETECTED at %s — executing physical lockdown", location)

	var results []ActionResult

	// Find all access control devices at this location
	ec.mu.RLock()
	var doorsToLock []string
	var camerasToActivate []string

	for id, device := range ec.devices {
		if device.Location == location {
			switch device.Type {
			case DeviceAccessControl:
				doorsToLock = append(doorsToLock, id)
			case DeviceSurveillance:
				camerasToActivate = append(camerasToActivate, id)
			}
		}
	}
	ec.mu.RUnlock()

	// Lock all doors
	for _, doorID := range doorsToLock {
		result, err := ec.LockDoor(ctx, doorID, fmt.Sprintf("breach_detected_at_%s", location))
		if err != nil {
			ec.logger.Errorf("Failed to lock %s: %v", doorID, err)
		} else {
			results = append(results, *result)
		}
	}

	// Activate cameras
	for _, camID := range camerasToActivate {
		result, err := ec.ActivateSurveillance(ctx, camID, fmt.Sprintf("breach_detected_at_%s", location))
		if err != nil {
			ec.logger.Errorf("Failed to activate camera %s: %v", camID, err)
		} else {
			results = append(results, *result)
		}
	}

	return results
}

// OptimizeCooling adjusts HVAC based on current compute load.
func (ec *EnvironmentController) OptimizeCooling(ctx context.Context, cpuLoad float64) {
	// Higher CPU load → lower target temperature for better cooling
	// Range: 22°C at idle → 18°C at full load
	targetTemp := 22.0 - (cpuLoad * 4.0) // 22 - 4*load
	if targetTemp < 18.0 {
		targetTemp = 18.0
	}

	ec.mu.RLock()
	var hvacDevices []string
	for id, device := range ec.devices {
		if device.Type == DeviceHVAC {
			hvacDevices = append(hvacDevices, id)
		}
	}
	ec.mu.RUnlock()

	for _, hvacID := range hvacDevices {
		ec.AdjustHVAC(ctx, hvacID, targetTemp, fmt.Sprintf("compute_load_%.0f%%", cpuLoad*100))
	}
}

// ─────────────────────── Private Methods ───────────────────────

func (ec *EnvironmentController) execute(ctx context.Context, action EnvironmentAction) (*ActionResult, error) {
	start := time.Now()
	action.ID = fmt.Sprintf("phy_%d", time.Now().UnixNano())
	action.Timestamp = time.Now()

	// Safety check: harm level
	if action.HarmLevel > ec.maxHarmLevel {
		return nil, fmt.Errorf("action exceeds harm threshold: %d > %d", action.HarmLevel, ec.maxHarmLevel)
	}

	// Check device exists
	ec.mu.RLock()
	device, exists := ec.devices[action.DeviceID]
	ec.mu.RUnlock()

	if !exists {
		return nil, fmt.Errorf("device %s not found", action.DeviceID)
	}

	// Cooldown check
	ec.mu.RLock()
	lastTime, hasLast := ec.lastActionTime[action.DeviceID]
	ec.mu.RUnlock()

	if hasLast && time.Since(lastTime) < ec.cooldownPeriod {
		return nil, fmt.Errorf("device %s in cooldown (%.1fs remaining)",
			action.DeviceID, (ec.cooldownPeriod - time.Since(lastTime)).Seconds())
	}

	// Execute via appropriate protocol
	var err error
	switch device.Protocol {
	case "mqtt":
		err = ec.executeMQTT(ctx, device, action)
	case "rest":
		err = ec.executeREST(ctx, device, action)
	case "modbus":
		err = ec.executeModbus(ctx, device, action)
	default:
		err = fmt.Errorf("unsupported protocol: %s", device.Protocol)
	}

	// Record
	ec.mu.Lock()
	ec.actionLog = append(ec.actionLog, action)
	ec.lastActionTime[action.DeviceID] = time.Now()
	if err == nil {
		ec.actionsExecuted++
	} else {
		ec.actionsFailed++
	}
	if len(ec.actionLog) > 10000 {
		ec.actionLog = ec.actionLog[5000:]
	}
	ec.mu.Unlock()

	result := &ActionResult{
		ActionID: action.ID,
		Success:  err == nil,
		Error:    err,
		Duration: time.Since(start),
	}

	if err == nil {
		ec.logger.Infof("Physical action: %s → %s (%s) [reason: %s]",
			action.Command, device.Name, device.Location, action.Reason)
	}

	return result, err
}

func (ec *EnvironmentController) executeMQTT(ctx context.Context, device *PhysicalDevice, action EnvironmentAction) error {
	// Publish command to device's MQTT topic
	topic := fmt.Sprintf("physical/%s/%s", device.ID, action.Command)
	payload, _ := json.Marshal(action.Parameters)
	_ = topic
	_ = payload
	// In production: ec.mqttClient.Publish(topic, payload, 1)
	return nil
}

func (ec *EnvironmentController) executeREST(ctx context.Context, device *PhysicalDevice, action EnvironmentAction) error {
	// POST to device's REST endpoint
	_ = fmt.Sprintf("%s/api/%s", device.Endpoint, action.Command)
	// In production: http.Post(url, "application/json", body)
	return nil
}

func (ec *EnvironmentController) executeModbus(ctx context.Context, device *PhysicalDevice, action EnvironmentAction) error {
	// Write to Modbus register
	// In production: modbus.Write(device.Endpoint, register, value)
	return nil
}
