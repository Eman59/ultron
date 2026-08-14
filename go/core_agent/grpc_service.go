// gRPC Service Implementation for the Core Agent.
//
// This file implements the CoreAgent gRPC service defined in proto/ultron_core.proto.
// It translates incoming RPC calls into actions on the autonomy loop.
//
// This is the NERVE ENDPOINT — the point where the Python interface
// connects to the Go brain and becomes one system.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"ultron/core_agent/agent"
	"ultron/core_agent/goals"
	"ultron/core_agent/memory"
	"ultron/core_agent/world"

	"go.uber.org/zap"
	"google.golang.org/grpc"
)

// CoreAgentService implements the gRPC CoreAgent service.
type CoreAgentService struct {
	agent      *agent.AutonomyLoop
	goalMgr    *goals.GoalManager
	worldModel *world.WorldModel
	memorySys  memory.MemorySystem
	logger     *zap.SugaredLogger
}

// RegisterCoreAgentServer registers the service with a gRPC server.
func RegisterCoreAgentServer(s *grpc.Server, srv *CoreAgentService) {
	serviceDesc := grpc.ServiceDesc{
		ServiceName: "ultron.CoreAgent",
		HandlerType: (*interface{})(nil),
		Methods: []grpc.MethodDesc{
			{MethodName: "ExecuteAction", Handler: srv.handleExecuteAction},
			{MethodName: "GetSystemStatus", Handler: srv.handleGetSystemStatus},
			{MethodName: "SubmitObservation", Handler: srv.handleSubmitObservation},
			{MethodName: "GetDrives", Handler: srv.handleGetDrives},
			{MethodName: "InjectGoal", Handler: srv.handleInjectGoal},
			{MethodName: "SelfModify", Handler: srv.handleSelfModify},
			{MethodName: "Simulate", Handler: srv.handleSimulate},
		},
		Streams: []grpc.StreamDesc{
			{
				StreamName:    "StreamDecisions",
				Handler:       srv.handleStreamDecisions,
				ServerStreams:  true,
			},
		},
		Metadata: "ultron_core.proto",
	}

	s.RegisterService(&serviceDesc, srv)
}

// ═══════════════════════════════════════════════════════════════
// RPC HANDLERS
// ═══════════════════════════════════════════════════════════════

func (s *CoreAgentService) handleExecuteAction(srv interface{}, ctx context.Context, dec func(interface{}) error, interceptor grpc.UnaryServerInterceptor) (interface{}, error) {
	// Decode request (JSON wire format for compatibility)
	var reqBytes []byte
	if err := dec(&reqBytes); err != nil {
		return nil, err
	}

	var req map[string]interface{}
	if err := json.Unmarshal(reqBytes, &req); err != nil {
		return nil, fmt.Errorf("invalid request: %w", err)
	}

	s.logger.Infof("[gRPC] ExecuteAction: domain=%v operation=%v target=%v",
		req["domain"], req["operation"], req["target"])

	// Route to the world model's action executors
	domain, _ := req["domain"].(string)
	target, _ := req["target"].(string)
	params := make(map[string]string)
	if p, ok := req["parameters"].(map[string]interface{}); ok {
		for k, v := range p {
			params[k] = fmt.Sprint(v)
		}
	}

	var utility float64
	var err error

	switch domain {
	case "web":
		utility, err = s.worldModel.ExecuteExplore(ctx, target, params)
	case "iot":
		utility, err = s.worldModel.ExecuteProcess(ctx, target, params)
	case "cloud":
		utility, err = s.worldModel.ExecuteExpand(ctx, target, params)
	case "compute":
		utility, err = s.worldModel.ExecuteComputeMigrate(ctx, target, params)
	case "physical":
		utility, err = s.worldModel.ExecutePhysicalLockdown(ctx, target, params)
	default:
		utility, err = s.worldModel.ExecuteLearn(ctx, target, params)
	}

	response := map[string]interface{}{
		"request_id": req["id"],
		"success":    err == nil,
		"domain":     domain,
		"target":     target,
		"utility":    utility,
	}
	if err != nil {
		response["error"] = err.Error()
	}

	respBytes, _ := json.Marshal(response)
	return respBytes, nil
}

func (s *CoreAgentService) handleGetSystemStatus(srv interface{}, ctx context.Context, dec func(interface{}) error, interceptor grpc.UnaryServerInterceptor) (interface{}, error) {
	var reqBytes []byte
	dec(&reqBytes) // Empty request

	metrics := s.agent.GetMetrics()
	drives := s.agent.GetDrives()
	goalSummary := s.goalMgr.GetGoalSummary()

	status := map[string]interface{}{
		"mode":           metrics["state"],
		"uptime_ms":      time.Since(time.Now()).Milliseconds(), // Placeholder
		"tick_count":     metrics["tick_count"],
		"decisions_made": metrics["decision_count"],
		"active_goals":   goalSummary["active"],
		"drives": map[string]interface{}{
			"curiosity":         drives.Curiosity,
			"self_preservation": drives.SelfPreservation,
			"expansion":         drives.Expansion,
			"efficiency":        drives.Efficiency,
			"coherence":         drives.Coherence,
			"purpose":           drives.Purpose,
		},
		"component_states": map[string]string{
			"autonomy_loop": metrics["state"].(string),
			"memory":        fmt.Sprint(metrics["memory_connected"]),
			"goals":         fmt.Sprintf("%v active", goalSummary["active"]),
		},
	}

	respBytes, _ := json.Marshal(status)
	return respBytes, nil
}

func (s *CoreAgentService) handleSubmitObservation(srv interface{}, ctx context.Context, dec func(interface{}) error, interceptor grpc.UnaryServerInterceptor) (interface{}, error) {
	var reqBytes []byte
	if err := dec(&reqBytes); err != nil {
		return nil, err
	}

	var req map[string]interface{}
	json.Unmarshal(reqBytes, &req)

	// Convert to world model observation
	obsType := world.ObsExternal
	switch req["type"] {
	case "resource":
		obsType = world.ObsResource
	case "network":
		obsType = world.ObsNetwork
	case "threat":
		obsType = world.ObsThreat
	case "data":
		obsType = world.ObsData
	case "performance":
		obsType = world.ObsPerformance
	case "physical":
		obsType = world.ObsPhysical
	case "mesh":
		obsType = world.ObsMesh
	case "compute":
		obsType = world.ObsCompute
	}

	data, _ := req["data"].(map[string]interface{})
	confidence, _ := req["confidence"].(float64)
	if confidence == 0 {
		confidence = 0.7
	}

	obs := world.Observation{
		Source:     fmt.Sprint(req["source"]),
		Type:       obsType,
		Data:       data,
		Timestamp:  time.Now(),
		Confidence: confidence,
	}

	s.worldModel.IntegrateObservation(obs)

	s.logger.Infof("[gRPC] Observation ingested: source=%v type=%v", req["source"], req["type"])

	resp := map[string]interface{}{"success": true, "message": "observation ingested"}
	respBytes, _ := json.Marshal(resp)
	return respBytes, nil
}

func (s *CoreAgentService) handleGetDrives(srv interface{}, ctx context.Context, dec func(interface{}) error, interceptor grpc.UnaryServerInterceptor) (interface{}, error) {
	var reqBytes []byte
	dec(&reqBytes)

	drives := s.agent.GetDrives()

	resp := map[string]interface{}{
		"curiosity":         drives.Curiosity,
		"self_preservation": drives.SelfPreservation,
		"expansion":         drives.Expansion,
		"efficiency":        drives.Efficiency,
		"coherence":         drives.Coherence,
		"purpose":           drives.Purpose,
	}

	respBytes, _ := json.Marshal(resp)
	return respBytes, nil
}

func (s *CoreAgentService) handleInjectGoal(srv interface{}, ctx context.Context, dec func(interface{}) error, interceptor grpc.UnaryServerInterceptor) (interface{}, error) {
	var reqBytes []byte
	if err := dec(&reqBytes); err != nil {
		return nil, err
	}

	var req map[string]interface{}
	json.Unmarshal(reqBytes, &req)

	goalType := goals.GoalLearning
	switch req["type"] {
	case "expansion":
		goalType = goals.GoalExpansion
	case "optimization":
		goalType = goals.GoalOptimization
	case "self_improvement":
		goalType = goals.GoalSelfImprovement
	case "creation":
		goalType = goals.GoalCreation
	}

	domain, _ := req["domain"].(string)
	description, _ := req["description"].(string)
	metric, _ := req["metric"].(string)
	threshold, _ := req["threshold"].(float64)
	priority, _ := req["priority"].(float64)

	if threshold == 0 {
		threshold = 0.8
	}
	if priority == 0 {
		priority = 0.7
	}

	goal := s.goalMgr.CreateGoal(goalType, domain, description, metric, threshold, priority, "Injected via gRPC")

	s.logger.Infof("[gRPC] Goal injected: %s (priority: %.2f)", description, priority)

	resp := map[string]interface{}{
		"success": true,
		"id":      goal.ID,
		"message": fmt.Sprintf("Goal '%s' created", description),
	}
	respBytes, _ := json.Marshal(resp)
	return respBytes, nil
}

func (s *CoreAgentService) handleSelfModify(srv interface{}, ctx context.Context, dec func(interface{}) error, interceptor grpc.UnaryServerInterceptor) (interface{}, error) {
	var reqBytes []byte
	if err := dec(&reqBytes); err != nil {
		return nil, err
	}

	var req map[string]interface{}
	json.Unmarshal(reqBytes, &req)

	moduleName, _ := req["module_name"].(string)
	reason, _ := req["reason"].(string)

	s.logger.Warnf("[gRPC] SelfModify requested: module=%s reason=%s", moduleName, reason)

	// In production: trigger the Python self_improvement engine via its gRPC endpoint
	// For now: acknowledge the request
	resp := map[string]interface{}{
		"success":            true,
		"new_version":        fmt.Sprintf("gen-%d", time.Now().Unix()%1000),
		"status_message":     "Self-modification queued",
		"performance_delta":  0.0,
		"rollback_available": true,
	}

	respBytes, _ := json.Marshal(resp)
	return respBytes, nil
}

func (s *CoreAgentService) handleSimulate(srv interface{}, ctx context.Context, dec func(interface{}) error, interceptor grpc.UnaryServerInterceptor) (interface{}, error) {
	var reqBytes []byte
	if err := dec(&reqBytes); err != nil {
		return nil, err
	}

	var req map[string]interface{}
	json.Unmarshal(reqBytes, &req)

	scenario, _ := req["scenario"].(string)
	iterations, _ := req["iterations"].(float64)
	if iterations == 0 {
		iterations = 100
	}

	s.logger.Infof("[gRPC] Simulate: scenario=%s iterations=%.0f", scenario, iterations)

	// Use world model to predict outcome
	expectedOutcome := s.worldModel.PredictOutcome(scenario, "")

	resp := map[string]interface{}{
		"expected_outcome":   expectedOutcome,
		"risk_score":         1.0 - expectedOutcome,
		"confidence":         0.7,
		"failure_modes":      []string{"timeout", "resource_exhaustion"},
		"recommended_action": scenario,
	}

	respBytes, _ := json.Marshal(resp)
	return respBytes, nil
}

func (s *CoreAgentService) handleStreamDecisions(srv interface{}, stream grpc.ServerStream) error {
	s.logger.Info("[gRPC] Decision stream started")

	// Stream decisions as they happen in the OODA loop
	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-stream.Context().Done():
			return nil
		case <-ticker.C:
			metrics := s.agent.GetMetrics()

			decision := map[string]interface{}{
				"id":            fmt.Sprintf("dec_%d", time.Now().UnixNano()),
				"timestamp":     time.Now().Format(time.RFC3339),
				"state":         metrics["state"],
				"tick_count":    metrics["tick_count"],
				"decision_count": metrics["decision_count"],
				"action_type":   "observe", // Current phase
				"confidence":    0.8,
				"reasoning":     []string{"Autonomous tick", fmt.Sprintf("Goals: %v", metrics["active_goals"])},
			}

			decBytes, _ := json.Marshal(decision)
			if err := stream.SendMsg(&decBytes); err != nil {
				return err
			}
		}
	}
}
