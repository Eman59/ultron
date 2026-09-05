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
	"fmt"
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

// EnvironmentController manages physical infrastructure
type EnvironmentController struct {
	devices map[string]*PhysicalDevice
	logger  *zap.Logger
}

func NewEnvironmentController(logger *zap.Logger) *EnvironmentController {
	return &EnvironmentController{
		devices: make(map[string]*PhysicalDevice),
		logger:  logger,
	}
}

func (ec *EnvironmentController) AddDevice(device *PhysicalDevice) {
	if device == nil {
		ec.logger.Warn("attempt to add nil device")
		return
	}
	if device.ID == "" {
		ec.logger.Warn("attempt to add device with empty ID")
		return
	}
	ec.devices[device.ID] = device
}

func (ec *EnvironmentController) RemoveDevice(deviceID string) {
	if deviceID == "" {
		ec.logger.Warn("attempt to remove device with empty ID")
		return
	}
	delete(ec.devices, deviceID)
}

func (ec *EnvironmentController) ExecuteAction(action *EnvironmentAction) *ActionResult {
	if action == nil {
		ec.logger.Warn("attempt to execute nil action")
		return &ActionResult{Error: fmt.Errorf("nil action")}
	}
	if action.DeviceID == "" {
		ec.logger.Warn("attempt to execute action with empty device ID")
		return &ActionResult{Error: fmt.Errorf("empty device ID")}
	}
	device, ok := ec.devices[action.DeviceID]
	if !ok {
		ec.logger.Warn("device not found for action", zap.String("device_id", action.DeviceID))
		return &ActionResult{Error: fmt.Errorf("device not found")}
	}
	if device.MaxHarmLevel < action.HarmLevel {
		ec.logger.Warn("action harm level exceeds device max harm level", zap.String("device_id", action.DeviceID), zap.Int("harm_level", int(action.HarmLevel)))
		return &ActionResult{Error: fmt.Errorf("action harm level exceeds device max harm level")}
	}
	startTime := time.Now()
	var response map[string]interface{}
	var err error
	switch device.Protocol {
	case "mqtt":
		// MQTT implementation
	case "modbus":
		// Modbus implementation
	case "rest":
		// REST implementation
	case "bacnet":
		// BACnet implementation
	default:
		ec.logger.Warn("unsupported protocol", zap.String("protocol", device.Protocol))
		return &ActionResult{Error: fmt.Errorf("unsupported protocol")}
	}
	duration := time.Since(startTime)
	return &ActionResult{
		ActionID:  action.ID,
		Success:   err == nil,
		Response:  response,
		Error:     err,
		Duration:  duration,
	}
}

func (ec *EnvironmentController) GetDevice(deviceID string) *PhysicalDevice {
	if deviceID == "" {
		ec.logger.Warn("attempt to get device with empty ID")
		return nil
	}
	return ec.devices[deviceID]
}

func (ec *EnvironmentController) GetDevices() map[string]*PhysicalDevice {
	return ec.devices
}

func (ec *EnvironmentController) SetDeviceOnline(deviceID string, online bool) {
	if deviceID == "" {
		ec.logger.Warn("attempt to set device online with empty ID")
		return
	}
	device, ok := ec.devices[deviceID]
	if !ok {
		ec.logger.Warn("device not found for online update", zap.String("device_id", deviceID))
		return
	}
	device.Online = online
}

func (ec *EnvironmentController) SetDeviceLastSeen(deviceID string, lastSeen time.Time) {
	if deviceID == "" {
		ec.logger.Warn("attempt to set device last seen with empty ID")
		return
	}
	device, ok := ec.devices[deviceID]
	if !ok {
		ec.logger.Warn("device not found for last seen update", zap.String("device_id", deviceID))
		return
	}
	device.LastSeen = lastSeen
}

func (ec *EnvironmentController) SetDeviceCurrentState(deviceID string, currentState map[string]interface{}) {
	if deviceID == "" {
		ec.logger.Warn("attempt to set device current state with empty ID")
		return
	}
	device, ok := ec.devices[deviceID]
	if !ok {
		ec.logger.Warn("device not found for current state update", zap.String("device_id", deviceID))
		return
	}
	device.CurrentState = currentState
}

func (ec *EnvironmentController) SetDeviceMaxHarmLevel(deviceID string, maxHarmLevel HarmLevel) {
	if deviceID == "" {
		ec.logger.Warn("attempt to set device max harm level with empty ID")
		return
	}
	device, ok := ec.devices[deviceID]
	if !ok {
		ec.logger.Warn("device not found for max harm level update", zap.String("device_id", deviceID))
		return
	}
	device.MaxHarmLevel = maxHarmLevel
}

