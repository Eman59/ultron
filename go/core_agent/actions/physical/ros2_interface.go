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

func calculateMinimumValue(minimumValueA, minimumValueB int) int {
	if minimumValueA < minimumValueB {
		return minimumValueA
	}
	return minimumValueB
}

// ═══════════════════════════════════════════════════════════════
// ROBOTIC UNIT TYPES
// ═══════════════════════════════════════════════════════════════

// RobotClassification categorizes physical platforms.
type RobotClassification int

const (
	RobotGroundVehicle      RobotClassification = iota // Wheeled/tracked ground vehicle
	RobotAerialVehicle                                 // Drone/UAV
	RobotManipulatorArm                               // Robotic arm
	RobotHumanoidRobot                                // Bipedal
	RobotSwarmUnitRobot                               // Simple micro-bot
	RobotSubmarineVehicle                             // Underwater vehicle
)

func (robotClassification RobotClassification) String() string {
	robotClassificationNames := []string{"Ground", "Aerial", "Manipulator", "Humanoid", "SwarmUnit", "Submarine"}
	if int(robotClassification) < len(robotClassificationNames) {
		return robotClassificationNames[robotClassification]
	}
	return "Unknown"
}

// RobotMotionState represents a robot's current kinematic state.
type RobotMotionState struct {
	// Position (meters, world frame)
	PositionX, PositionY, PositionZ float64

	// Orientation (quaternion)
	OrientationW, OrientationX, OrientationY, OrientationZ float64

	// Velocity (m/s)
	VelocityX, VelocityY, VelocityZ float64

	// Angular velocity (rad/s)
	AngularVelocityX, AngularVelocityY, AngularVelocityZ float64

	// Joint states (for arms/humanoids)
	JointPositions []float64
	JointVelocities []float64
	JointTorques []float64

	// Gripper state
	GripperOpenPercentage float64 // 0 = closed, 1 = fully open

	// Battery/power
	BatteryPercentage float64
	PowerDrawWatts float64 // Watts

	// Timestamp
	Timestamp time.Time
}

// SensorMeasurement represents a single sensor measurement.
type SensorMeasurement struct {
	SensorIdentifier   string
	SensorModality     SensorModality
	Timestamp          time.Time
	MeasurementData    interface{} // Type-specific data
	MeasurementConfidence float64     // 0-1
}

// SensorModality categorizes sensor modalities.
type SensorModality int

const (
	SensorLidar     SensorModality = iota // 3D point cloud
	SensorCamera