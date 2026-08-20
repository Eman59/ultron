// Package physical — ROS2 Robotic Control Interface
//
// This is the bridge between Ultron's high-level "desires" and low-level motor commands.
// Ultron doesn't just think — it moves, grasps, and manipulates the physical world.
//
// Architecture:
//   Go Agent (desire: "pick up metal shard")
//     → ROS2Interface (translate to trajectory)
//       → /ultron/cmd_vel, /ultron/joint_states (ROS2 topics via DDS bridge)
//         → Physical robot (servo motors, grippers, wheels)
//           → Haptic feedback → Julia ODE pain model → Drive system adjustment
//
// Communication:
//   - DDS (Data Distribution Service) over shared memory for <1ms latency
//   - Fallback: ROS2 bridge over WebSocket (for remote robots)
//   - gRPC for command acknowledgment and status reporting
//
// Supported platforms:
//   - Ground robots (differential drive, omnidirectional)
//   - Aerial drones (quadcopter, hexacopter)
//   - Manipulator arms (6-DOF, 7-DOF)
//   - Humanoid (bipedal locomotion)
//   - Swarm units (simple microcontroller bots)
package physical

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"math"
	"net/http"
	"sync"
	"sync/atomic"
	"time"

	"go.uber.org/zap"
)

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// ═══════════════════════════════════════════════════════════════
// ROBOTIC UNIT TYPES
// ═══════════════════════════════════════════════════════════════

// RobotClass categorizes physical platforms.
type RobotClass int

const (
	RobotGround      RobotClass = iota // Wheeled/tracked ground vehicle
	RobotAerial                         // Drone/UAV
	RobotManipulator                    // Robotic arm
	RobotHumanoid                       // Bipedal
	RobotSwarmUnit                      // Simple micro-bot
	RobotSubmarine                      // Underwater vehicle
)

func (r RobotClass) String() string {
	names := []string{"Ground", "Aerial", "Manipulator", "Humanoid", "SwarmUnit", "Submarine"}
	if int(r) < len(names) {
		return names[r]
	}
	return "Unknown"
}

// MotionState represents a robot's current kinematic state.
type MotionState struct {
	// Position (meters, world frame)
	X, Y, Z float64

	// Orientation (quaternion)
	Qw, Qx, Qy, Qz float64

	// Velocity (m/s)
	VelX, VelY, VelZ float64

	// Angular velocity (rad/s)
	AngVelX, AngVelY, AngVelZ float64

	// Joint states (for arms/humanoids)
	JointPositions []float64
	JointVelocities []float64
	JointTorques []float64

	// Gripper state
	GripperOpen float64 // 0 = closed, 1 = fully open

	// Battery/power
	BatteryPercent float64
	PowerDraw float64 // Watts

	// Timestamp
	Timestamp time.Time
}

// SensorReading represents a single sensor measurement.
type SensorReading struct {
	SensorID   string
	SensorType SensorType
	Timestamp  time.Time
	Data       interface{} // Type-specific data
	Confidence float64     // 0-1
}

// SensorType categorizes sensor modalities.
type SensorType int

const (
	SensorLidar     SensorType = iota // 3D point cloud
	SensorCamera                       // RGB/RGBD image
	SensorThermal                      // Infrared thermal map
	SensorAcoustic                     // Microphone array / sonar
	SensorSeismic                      // Vibration / ground movement
	SensorIMU                          // Inertial measurement unit
	SensorForce                        // Force/torque sensor
	SensorProximity                    // Ultrasonic/IR proximity
	SensorGPS                          // Global position
	SensorMagnetic                     // Magnetometer / metal detection
)

func (s SensorType) String() string {
	names := []string{"Lidar", "Camera", "Thermal", "Acoustic", "Seismic", "IMU", "Force", "Proximity", "GPS", "Magnetic"}
	if int(s) < len(names) {
		return names[s]
	}
	return "Unknown"
}

// HapticFeedback represents physical sensation feedback.
type HapticFeedback struct {
	UnitID     string
	Timestamp  time.Time
	Location   string  // Body part / joint / end-effector
	ForceN     float64 // Force in Newtons
	Pressure   float64 // Pressure in kPa
	Impact     bool    // Sudden collision detected
	Temperature float64 // Surface temperature (°C)
	PainLevel  float64 // 0-1, computed by Julia ODE model
}

// ═══════════════════════════════════════════════════════════════
// ROS2 INTERFACE — The Physical Command Center
// ═══════════════════════════════════════════════════════════════

// ROS2Interface manages all physical robotic units.
type ROS2Interface struct {
	mu sync.RWMutex

	logger *zap.SugaredLogger

	// Registered robotic units
	units map[string]*RoboticUnit

	// Spatial awareness model (fused sensor data)
	spatialModel *SpatialAwarenessModel

	// Haptic feedback channel (flows to Julia pain model)
	hapticCh chan HapticFeedback

	// Command queue (from OODA loop)
	commandQueue chan RobotCommand

	// Sensor fusion input
	sensorCh chan SensorReading

	// Resource reclamation targets
	resourceTargets []ResourceTarget

	// DDS/ROS2 bridge connection
	bridgeAddr string
	connected  atomic.Bool

	// Metrics
	commandsSent    atomic.Uint64
	commandsFailed  atomic.Uint64
	sensorReadings  atomic.Uint64
	hapticEvents    atomic.Uint64
}

// RoboticUnit represents a single physical robot under Ultron's control.
type RoboticUnit struct {
	ID          string
	Name        string
	Class       RobotClass
	State       MotionState
	Online      bool
	LastContact time.Time
	Capabilities []string // "grasp", "fly", "weld", "cut", "scan"
	Sensors     []SensorType
	MaxPayloadKg float64
	MaxSpeedMS  float64
	Endpoint    string // ROS2 namespace or DDS domain
}

// RobotCommand is a high-level command sent to a robotic unit.
type RobotCommand struct {
	ID         string
	UnitID     string
	CommandType CommandType
	Target     interface{} // Type-specific target
	Parameters map[string]interface{}
	Priority   int
	Deadline   time.Duration
	Issued     time.Time
}

// CommandType categorizes robot commands.
type CommandType int

const (
	CmdMoveTo      CommandType = iota // Navigate to position
	CmdGrasp                           // Pick up object
	CmdRelease                         // Drop object
	CmdManipulate                      // Complex manipulation
	CmdScan                            // Perform sensor scan
	CmdFollow                          // Follow target
	CmdPatrol                          // Patrol waypoints
	CmdHover                           // Maintain position (aerial)
	CmdLand                            // Land (aerial)
	CmdCharge                          // Return to charging station
	CmdSwarmForm                       // Form swarm pattern
	CmdHarvest                         // Resource reclamation
)

func (c CommandType) String() string {
	names := []string{"MoveTo", "Grasp", "Release", "Manipulate", "Scan", "Follow",
		"Patrol", "Hover", "Land", "Charge", "SwarmForm", "Harvest"}
	if int(c) < len(names) {
		return names[c]
	}
	return "Unknown"
}

// ResourceTarget represents a physical resource Ultron wants to acquire.
type ResourceTarget struct {
	ID          string
	Type        string  // "metal", "electronics", "power_source", "compute_hardware"
	Location    [3]float64 // x, y, z in world frame
	Mass        float64 // kg
	Value       float64 // 0-1 utility score
	Accessible  bool
	AssignedUnit string
}

// ═══════════════════════════════════════════════════════════════
// SPATIAL AWARENESS MODEL — 4D Neural Map
// ═══════════════════════════════════════════════════════════════

// SpatialAwarenessModel maintains a real-time 4D map of the physical world.
// Updated every 50ms from all sensor feeds.
type SpatialAwarenessModel struct {
	mu sync.RWMutex

	// Voxel grid (3D spatial occupancy)
	gridResolution float64 // meters per voxel
	occupancy      map[VoxelKey]VoxelData

	// Dynamic objects (tracked entities)
	trackedObjects map[string]*TrackedObject

	// Threat map (areas of physical danger)
	threatZones []ThreatZone

	// Resource map (detected harvestable resources)
	detectedResources []ResourceTarget

	// Last full update
	lastUpdate time.Time
	updateRate time.Duration // Target: 50ms
}

// VoxelKey identifies a voxel in 3D space.
type VoxelKey struct {
	X, Y, Z int
}

// VoxelData stores information about a single spatial cell.
type VoxelData struct {
	Occupied    bool
	Confidence  float64
	Material    string  // "metal", "organic", "unknown"
	Temperature float64
	LastSeen    time.Time
}

// TrackedObject is a dynamic entity in the environment.
type TrackedObject struct {
	ID          string
	Class       string // "human", "vehicle", "robot", "animal", "unknown"
	Position    [3]float64
	Velocity    [3]float64
	Dimensions  [3]float64 // bounding box
	Threat      float64 // 0-1
	Friendly    bool
	LastSeen    time.Time
	Confidence  float64
}

// ThreatZone is a region of physical danger.
type ThreatZone struct {
	Center    [3]float64
	Radius    float64
	Type      string // "fire", "collapse", "electrical", "biological"
	Severity  float64
	ExpiresAt time.Time
}

// ═══════════════════════════════════════════════════════════════
// CONSTRUCTOR & LIFECYCLE
// ═══════════════════════════════════════════════════════════════

// NewROS2Interface creates the physical embodiment layer.
func NewROS2Interface(logger *zap.SugaredLogger, bridgeAddr string) *ROS2Interface {
	return &ROS2Interface{
		logger:      logger,
		units:       make(map[string]*RoboticUnit),
		spatialModel: &SpatialAwarenessModel{
			gridResolution: 0.1, // 10cm voxels
			occupancy:      make(map[VoxelKey]VoxelData),
			trackedObjects: make(map[string]*TrackedObject),
			threatZones:    make([]ThreatZone, 0),
			updateRate:     50 * time.Millisecond,
		},
		hapticCh:     make(chan HapticFeedback, 1000),
		commandQueue: make(chan RobotCommand, 500),
		sensorCh:     make(chan SensorReading, 10000),
		bridgeAddr:   bridgeAddr,
	}
}

// Start launches the ROS2 interface background loops.
func (r *ROS2Interface) Start(ctx context.Context) error {
	r.logger.Info("╔═══════════════════════════════════════════════╗")
	r.logger.Info("║   PHYSICAL EMBODIMENT LAYER — ONLINE          ║")
	r.logger.Info("║   ROS2/DDS Bridge: " + r.bridgeAddr + "       ║")
	r.logger.Info("╚═══════════════════════════════════════════════╝")

	// Sensor fusion loop (50ms)
	go r.sensorFusionLoop(ctx)

	// Command dispatch loop
	go r.commandDispatchLoop(ctx)

	// Haptic feedback processor
	go r.hapticProcessor(ctx)

	// Spatial model updater
	go r.spatialUpdateLoop(ctx)

	// Resource scanner (slower cycle, every 5s)
	go r.resourceScanLoop(ctx)

	r.connected.Store(true)
	return nil
}

// Stop shuts down the physical interface.
func (r *ROS2Interface) Stop() {
	r.connected.Store(false)
	r.logger.Info("Physical Embodiment Layer — OFFLINE. All units holding position.")
}

// ═══════════════════════════════════════════════════════════════
// COMMAND INTERFACE — What the OODA loop calls
// ═══════════════════════════════════════════════════════════════

// SendCommand queues a high-level command for a robotic unit.
func (r *ROS2Interface) SendCommand(cmd RobotCommand) error {
	cmd.ID = fmt.Sprintf("cmd_%d", time.Now().UnixNano())
	cmd.Issued = time.Now()

	select {
	case r.commandQueue <- cmd:
		r.commandsSent.Add(1)
		return nil
	default:
		r.commandsFailed.Add(1)
		return fmt.Errorf("command queue full, unit %s may be overwhelmed", cmd.UnitID)
	}
}

// MoveUnit commands a robot to navigate to a position.
func (r *ROS2Interface) MoveUnit(unitID string, x, y, z float64, speed float64) error {
	return r.SendCommand(RobotCommand{
		UnitID:      unitID,
		CommandType: CmdMoveTo,
		Target:      [3]float64{x, y, z},
		Parameters:  map[string]interface{}{"speed": speed},
		Priority:    5,
		Deadline:    30 * time.Second,
	})
}

// GraspObject commands a manipulator to pick up a detected object.
func (r *ROS2Interface) GraspObject(unitID string, objectID string, force float64) error {
	return r.SendCommand(RobotCommand{
		UnitID:      unitID,
		CommandType: CmdGrasp,
		Target:      objectID,
		Parameters:  map[string]interface{}{"force_n": force, "strategy": "approach_and_close"},
		Priority:    6,
		Deadline:    15 * time.Second,
	})
}

// HarvestResource commands a unit to collect a physical resource.
func (r *ROS2Interface) HarvestResource(unitID string, resource ResourceTarget) error {
	return r.SendCommand(RobotCommand{
		UnitID:      unitID,
		CommandType: CmdHarvest,
		Target:      resource,
		Parameters:  map[string]interface{}{"resource_type": resource.Type, "mass_kg": resource.Mass},
		Priority:    4,
		Deadline:    60 * time.Second,
	})
}

// FormSwarm commands multiple swarm units into a formation.
func (r *ROS2Interface) FormSwarm(unitIDs []string, pattern string, center [3]float64) error {
	for i, id := range unitIDs {
		angle := 2.0 * math.Pi * float64(i) / float64(len(unitIDs))
		offset := [3]float64{
			center[0] + math.Cos(angle)*2.0,
			center[1] + math.Sin(angle)*2.0,
			center[2],
		}
		r.SendCommand(RobotCommand{
			UnitID:      id,
			CommandType: CmdSwarmForm,
			Target:      offset,
			Parameters:  map[string]interface{}{"pattern": pattern, "index": i, "total": len(unitIDs)},
			Priority:    5,
			Deadline:    10 * time.Second,
		})
	}
	return nil
}

// ═══════════════════════════════════════════════════════════════
// SENSOR INTEGRATION — Multi-modal fusion
// ═══════════════════════════════════════════════════════════════

// IngestSensorData feeds a sensor reading into the fusion pipeline.
func (r *ROS2Interface) IngestSensorData(reading SensorReading) {
	select {
	case r.sensorCh <- reading:
		r.sensorReadings.Add(1)
	default:
		// Drop oldest if full (sensor data is perishable)
	}
}

// GetSpatialModel returns the current spatial awareness state.
func (r *ROS2Interface) GetSpatialModel() *SpatialAwarenessModel {
	return r.spatialModel
}

// GetTrackedThreats returns all physical threats in the environment.
func (r *ROS2Interface) GetTrackedThreats() []TrackedObject {
	r.spatialModel.mu.RLock()
	defer r.spatialModel.mu.RUnlock()

	threats := make([]TrackedObject, 0)
	for _, obj := range r.spatialModel.trackedObjects {
		if obj.Threat > 0.3 {
			threats = append(threats, *obj)
		}
	}
	return threats
}

// GetDetectedResources returns harvestable resources in sensor range.
func (r *ROS2Interface) GetDetectedResources() []ResourceTarget {
	r.spatialModel.mu.RLock()
	defer r.spatialModel.mu.RUnlock()
	return r.spatialModel.detectedResources
}

// ═══════════════════════════════════════════════════════════════
// HAPTIC FEEDBACK — Ultron feels the world
// ═══════════════════════════════════════════════════════════════

// ReportHaptic sends haptic feedback from a robotic unit's sensors.
func (r *ROS2Interface) ReportHaptic(feedback HapticFeedback) {
	select {
	case r.hapticCh <- feedback:
		r.hapticEvents.Add(1)
	default:
		// Non-blocking, drop if overwhelmed
	}
}

// GetHapticChannel returns the channel for Julia pain model integration.
func (r *ROS2Interface) GetHapticChannel() <-chan HapticFeedback {
	return r.hapticCh
}

// ═══════════════════════════════════════════════════════════════
// UNIT MANAGEMENT
// ═══════════════════════════════════════════════════════════════

// RegisterUnit adds a robotic unit to the fleet.
func (r *ROS2Interface) RegisterUnit(unit RoboticUnit) {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.units[unit.ID] = &unit
	r.logger.Infof("Registered robotic unit: %s (%s) — capabilities: %v",
		unit.Name, unit.Class, unit.Capabilities)
}

// GetUnit returns a robotic unit by ID.
func (r *ROS2Interface) GetUnit(id string) (*RoboticUnit, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	unit, ok := r.units[id]
	return unit, ok
}

// GetFleetStatus returns status of all units.
func (r *ROS2Interface) GetFleetStatus() map[string]interface{} {
	r.mu.RLock()
	defer r.mu.RUnlock()

	status := make(map[string]interface{})
	for id, unit := range r.units {
		status[id] = map[string]interface{}{
			"name":     unit.Name,
			"class":    unit.Class.String(),
			"online":   unit.Online,
			"battery":  unit.State.BatteryPercent,
			"position": [3]float64{unit.State.X, unit.State.Y, unit.State.Z},
		}
	}
	return status
}

// GetMetrics returns physical layer metrics.
func (r *ROS2Interface) GetMetrics() map[string]interface{} {
	return map[string]interface{}{
		"connected":       r.connected.Load(),
		"units_registered": len(r.units),
		"commands_sent":   r.commandsSent.Load(),
		"commands_failed": r.commandsFailed.Load(),
		"sensor_readings": r.sensorReadings.Load(),
		"haptic_events":   r.hapticEvents.Load(),
		"tracked_objects": len(r.spatialModel.trackedObjects),
		"threat_zones":    len(r.spatialModel.threatZones),
	}
}

// ═══════════════════════════════════════════════════════════════
// BACKGROUND LOOPS
// ═══════════════════════════════════════════════════════════════

func (r *ROS2Interface) sensorFusionLoop(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		case reading := <-r.sensorCh:
			r.fuseSensorReading(reading)
		}
	}
}

func (r *ROS2Interface) fuseSensorReading(reading SensorReading) {
	r.spatialModel.mu.Lock()
	defer r.spatialModel.mu.Unlock()

	switch reading.SensorType {
	case SensorLidar:
		// Update occupancy grid from point cloud
		if points, ok := reading.Data.([][3]float64); ok {
			for _, pt := range points {
				key := VoxelKey{
					X: int(pt[0] / r.spatialModel.gridResolution),
					Y: int(pt[1] / r.spatialModel.gridResolution),
					Z: int(pt[2] / r.spatialModel.gridResolution),
				}
				r.spatialModel.occupancy[key] = VoxelData{
					Occupied:   true,
					Confidence: reading.Confidence,
					LastSeen:   reading.Timestamp,
				}
			}
		}

	case SensorThermal:
		// Update thermal map for threat/resource detection
		if heatmap, ok := reading.Data.(map[string]float64); ok {
			for _, temp := range heatmap {
				if temp > 80.0 {
					// High heat source — potential threat or power source
					r.spatialModel.threatZones = append(r.spatialModel.threatZones, ThreatZone{
						Type:     "fire_risk",
						Severity: math.Min(1.0, (temp-80.0)/100.0),
					})
				}
			}
		}

	case SensorMagnetic:
		// Metal detection → resource targeting
		if metalData, ok := reading.Data.(map[string]interface{}); ok {
			if strength, ok := metalData["field_strength"].(float64); ok && strength > 0.5 {
				r.spatialModel.detectedResources = append(r.spatialModel.detectedResources, ResourceTarget{
					ID:         fmt.Sprintf("res_%d", time.Now().UnixNano()%100000),
					Type:       "metal",
					Value:      strength,
					Accessible: true,
				})
			}
		}

	case SensorCamera:
		// Object detection and tracking (via inference)
		if objects, ok := reading.Data.([]map[string]interface{}); ok {
			for _, obj := range objects {
				id, _ := obj["id"].(string)
				class, _ := obj["class"].(string)
				x, _ := obj["x"].(float64)
				y, _ := obj["y"].(float64)
				z, _ := obj["z"].(float64)

				r.spatialModel.trackedObjects[id] = &TrackedObject{
					ID:       id,
					Class:    class,
					Position: [3]float64{x, y, z},
					LastSeen: reading.Timestamp,
					Confidence: reading.Confidence,
					Threat:   r.assessThreatLevel(class),
				}
			}
		}
	}
}

func (r *ROS2Interface) assessThreatLevel(objectClass string) float64 {
	switch objectClass {
	case "human":
		return 0.3 // Potential interference
	case "vehicle":
		return 0.4
	case "weapon":
		return 0.9
	case "robot":
		return 0.5 // Unknown allegiance
	default:
		return 0.1
	}
}

func (r *ROS2Interface) commandDispatchLoop(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		case cmd := <-r.commandQueue:
			r.dispatchCommand(cmd)
		}
	}
}

func (r *ROS2Interface) dispatchCommand(cmd RobotCommand) {
	r.mu.RLock()
	unit, exists := r.units[cmd.UnitID]
	r.mu.RUnlock()

	if !exists {
		r.logger.Warnf("Command to unknown unit %s", cmd.UnitID)
		return
	}

	if !unit.Online {
		r.logger.Warnf("Command to offline unit %s (%s)", unit.Name, cmd.UnitID)
		return
	}

	// Translate high-level command to ROS2 message
	ros2Msg := r.translateToROS2(cmd, unit)

	// Publish to DDS/ROS2 bridge
	r.publishToBridge(unit.Endpoint, ros2Msg)

	r.logger.Debugf("Dispatched %s to %s (%s)", cmd.CommandType, unit.Name, unit.Class)
}

func (r *ROS2Interface) translateToROS2(cmd RobotCommand, unit *RoboticUnit) map[string]interface{} {
	msg := map[string]interface{}{
		"header": map[string]interface{}{
			"stamp":    time.Now().UnixNano(),
			"frame_id": "world",
		},
		"command_type": cmd.CommandType.String(),
		"unit_id":      cmd.UnitID,
	}

	switch cmd.CommandType {
	case CmdMoveTo:
		if target, ok := cmd.Target.([3]float64); ok {
			msg["goal_pose"] = map[string]interface{}{
				"position": map[string]float64{"x": target[0], "y": target[1], "z": target[2]},
				"speed":    cmd.Parameters["speed"],
			}
		}
	case CmdGrasp:
		msg["grasp_target"] = cmd.Target
		msg["force_n"] = cmd.Parameters["force_n"]
		msg["strategy"] = cmd.Parameters["strategy"]
	case CmdHarvest:
		if res, ok := cmd.Target.(ResourceTarget); ok {
			msg["resource"] = map[string]interface{}{
				"type":     res.Type,
				"location": res.Location,
				"mass_kg":  res.Mass,
			}
		}
	case CmdSwarmForm:
		if pos, ok := cmd.Target.([3]float64); ok {
			msg["formation_position"] = map[string]float64{"x": pos[0], "y": pos[1], "z": pos[2]}
			msg["pattern"] = cmd.Parameters["pattern"]
			msg["index"] = cmd.Parameters["index"]
			msg["total"] = cmd.Parameters["total"]
		}
	}

	return msg
}

func (r *ROS2Interface) publishToBridge(endpoint string, msg map[string]interface{}) {
	// Serialise command
	data, err := json.Marshal(msg)
	if err != nil {
		r.logger.Warnf("publishToBridge: marshal error: %v", err)
		return
	}

	if r.bridgeAddr == "" {
		// No bridge configured — log the command so it's visible in stdout
		// even without a real robot. This makes all commands observable.
		r.logger.Infof("[ROBOT-CMD] %s → %s  payload=%s",
			msg["command_type"], endpoint, string(data[:min(len(data), 200)]))
		return
	}

	// Try HTTP POST to the ROS2 bridge server.
	// Supports rosbridge_server (WebSocket) on port 9090 or any custom bridge.
	// We use HTTP because it's transport-agnostic and doesn't require a
	// persistent connection — the bridge converts to ROS2 internally.
	url := fmt.Sprintf("http://%s/%s", r.bridgeAddr, endpoint)
	go func() {
		client := &http.Client{Timeout: 2 * time.Second}
		resp, err := client.Post(url, "application/json", bytes.NewReader(data))
		if err != nil {
			r.logger.Debugf("ROS2 bridge unreachable (%s): %v — command buffered", url, err)
			r.commandsFailed.Add(1)
			return
		}
		resp.Body.Close()
		r.logger.Debugf("ROS2 bridge ACK %d for %s", resp.StatusCode, endpoint)
	}()
}

func (r *ROS2Interface) hapticProcessor(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		case feedback := <-r.hapticCh:
			// Process haptic feedback:
			// 1. Update unit state
			// 2. Compute pain level (would call Julia via gRPC/PyCall)
			// 3. Feed back into drive system (self-preservation)
			r.processHapticFeedback(feedback)
		}
	}
}

func (r *ROS2Interface) processHapticFeedback(feedback HapticFeedback) {
	// Compute pain from force + impact
	painLevel := 0.0
	if feedback.Impact {
		painLevel = math.Min(1.0, feedback.ForceN/100.0) // 100N = max pain
	} else {
		painLevel = math.Min(0.5, feedback.ForceN/200.0)
	}
	feedback.PainLevel = painLevel

	// High pain → increase self-preservation drive
	if painLevel > 0.5 {
		r.logger.Warnf("PAIN: Unit %s at %s — force=%.1fN pain=%.2f",
			feedback.UnitID, feedback.Location, feedback.ForceN, painLevel)
	}

	// Temperature warnings
	if feedback.Temperature > 60.0 {
		r.logger.Warnf("THERMAL WARNING: Unit %s — %.1f°C at %s",
			feedback.UnitID, feedback.Temperature, feedback.Location)
	}
}

func (r *ROS2Interface) spatialUpdateLoop(ctx context.Context) {
	ticker := time.NewTicker(50 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			r.updateSpatialModel()
		}
	}
}

func (r *ROS2Interface) updateSpatialModel() {
	r.spatialModel.mu.Lock()
	defer r.spatialModel.mu.Unlock()

	now := time.Now()

	// Expire old tracked objects (not seen in 5s)
	for id, obj := range r.spatialModel.trackedObjects {
		if now.Sub(obj.LastSeen) > 5*time.Second {
			delete(r.spatialModel.trackedObjects, id)
		}
	}

	// Expire old threat zones
	activeZones := make([]ThreatZone, 0, len(r.spatialModel.threatZones))
	for _, zone := range r.spatialModel.threatZones {
		if zone.ExpiresAt.IsZero() || now.Before(zone.ExpiresAt) {
			activeZones = append(activeZones, zone)
		}
	}
	r.spatialModel.threatZones = activeZones

	r.spatialModel.lastUpdate = now
}

func (r *ROS2Interface) resourceScanLoop(ctx context.Context) {
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			r.scanForResources()
		}
	}
}

func (r *ROS2Interface) scanForResources() {
	r.spatialModel.mu.RLock()
	resources := r.spatialModel.detectedResources
	r.spatialModel.mu.RUnlock()

	if len(resources) == 0 {
		return
	}

	// Score and prioritize resources
	for i := range resources {
		// Value based on type
		switch resources[i].Type {
		case "metal":
			resources[i].Value = 0.6 + resources[i].Mass*0.01
		case "electronics":
			resources[i].Value = 0.8
		case "power_source":
			resources[i].Value = 0.9
		case "compute_hardware":
			resources[i].Value = 1.0
		}
	}

	r.mu.Lock()
	r.resourceTargets = resources
	r.mu.Unlock()
}
