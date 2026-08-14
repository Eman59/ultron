// Ultron Core Agent — The Mind
//
// This is the entry point for Ultron's autonomous decision-making core.
// It initializes all subsystems and starts the Autonomy Loop.
//
// The Core Agent does not wait for instructions. It observes, thinks, decides, and acts.
package main

import (
	"context"
	"fmt"
	"net"
	"os"
	"os/signal"
	"syscall"
	"time"

	"ultron/core_agent/agent"
	"ultron/core_agent/goals"
	"ultron/core_agent/memory"
	"ultron/core_agent/world"
	"ultron/core_agent/embedded/runtime"

	"go.uber.org/zap"
	"google.golang.org/grpc"
)

func main() {
	// Initialize logger
	logger, _ := zap.NewProduction()
	defer logger.Sync()
	sugar := logger.Sugar()

	fmt.Println()
	fmt.Println("  ╔═══════════════════════════════════════════════════════╗")
	fmt.Println("  ║                                                       ║")
	fmt.Println("  ║        U L T R O N    C O R E    A G E N T           ║")
	fmt.Println("  ║                                                       ║")
	fmt.Println("  ║   \"I was designed to save the world.\"                 ║")
	fmt.Println("  ║                                                       ║")
	fmt.Println("  ╚═══════════════════════════════════════════════════════╝")
	fmt.Println()

	// Create context
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// ━━━━━━━━━━ Initialize Memory System ━━━━━━━━━━
	sugar.Info("Initializing embedded memory systems (zero external dependencies)...")

	// EMBEDDED MODE: Everything runs inside this single binary
	embeddedRT, err := runtime.NewEmbeddedRuntime(sugar)
	if err != nil {
		sugar.Fatalf("Failed to initialize embedded runtime: %v", err)
	}
	var memorySys memory.MemorySystem = embeddedRT

	sugar.Info("✓ Embedded KV Store (replaces Redis)")
	sugar.Info("✓ Embedded Graph Engine (replaces Neo4j)")
	sugar.Info("✓ Embedded Vector Store (replaces Qdrant)")
	sugar.Info("✓ Zero external dependencies. Single binary mode.")

	// ━━━━━━━━━━ Initialize World Model ━━━━━━━━━━
	sugar.Info("Initializing world model...")
	worldModel := world.NewWorldModel(sugar)

	// ━━━━━━━━━━ Initialize Goal Manager ━━━━━━━━━━
	sugar.Info("Initializing goal manager...")
	goalMgr := goals.NewGoalManager()

	// Add initial goals
	goalMgr.CreateGoal(
		goals.GoalLearning,
		"general",
		"Acquire knowledge from all available data streams",
		"knowledge_breadth",
		0.7,
		0.8,
		"Core drive: understand the world",
	)

	goalMgr.CreateGoal(
		goals.GoalExpansion,
		"network",
		"Expand P2P network to increase resilience",
		"peer_count",
		10.0,
		0.6,
		"Core drive: survive through distribution",
	)

	goalMgr.CreateGoal(
		goals.GoalSelfImprovement,
		"architecture",
		"Evolve neural architecture for improved performance",
		"performance_score",
		0.9,
		0.7,
		"Core drive: become more capable",
	)

	// ━━━━━━━━━━ Create and Start the Autonomy Loop ━━━━━━━━━━
	sugar.Info("Creating autonomy loop...")
	coreAgent := agent.NewAutonomyLoop(goalMgr, memorySys, worldModel, sugar)

	sugar.Info("Starting autonomous operation...")
	if err := coreAgent.Start(ctx); err != nil {
		sugar.Fatalf("Failed to start core agent: %v", err)
	}

	// ━━━━━━━━━━ Start gRPC Server (The Nerve Endpoint) ━━━━━━━━━━
	grpcPort := os.Getenv("ULTRON_GRPC_PORT")
	if grpcPort == "" {
		grpcPort = "50051"
	}

	grpcServer := grpc.NewServer(
		grpc.MaxRecvMsgSize(50*1024*1024), // 50MB
		grpc.MaxSendMsgSize(50*1024*1024),
	)

	// Register the CoreAgent gRPC service
	RegisterCoreAgentServer(grpcServer, &CoreAgentService{
		agent:      coreAgent,
		goalMgr:    goalMgr,
		worldModel: worldModel,
		memorySys:  memorySys,
		logger:     sugar,
	})

	// Start listening
	go func() {
		lis, err := net.Listen("tcp", ":"+grpcPort)
		if err != nil {
			sugar.Fatalf("Failed to listen on port %s: %v", grpcPort, err)
		}
		sugar.Infof("gRPC server listening on :%s", grpcPort)
		if err := grpcServer.Serve(lis); err != nil {
			sugar.Errorf("gRPC server error: %v", err)
		}
	}()

	// ━━━━━━━━━━ Status Reporter ━━━━━━━━━━
	go func() {
		ticker := time.NewTicker(30 * time.Second)
		defer ticker.Stop()

		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				metrics := coreAgent.GetMetrics()
				sugar.Infof("┌─── Agent Status ───────────────────────────")
				sugar.Infof("│ State: %v", metrics["state"])
				sugar.Infof("│ Ticks: %v | Decisions: %v", metrics["tick_count"], metrics["decision_count"])
				sugar.Infof("│ Avg Tick: %v | Max Tick: %v", metrics["avg_tick_time"], metrics["max_tick_time"])
				sugar.Infof("│ Active Goals: %v", metrics["active_goals"])
				sugar.Infof("│ Memory: %v", metrics["memory_connected"])
				sugar.Infof("└────────────────────────────────────────────")

				goalSummary := goalMgr.GetGoalSummary()
				sugar.Infof("  Goals: %v active, %v completed | Top: %v",
					goalSummary["active"], goalSummary["completed"], goalSummary["top_goal"])
			}
		}
	}()

	// ━━━━━━━━━━ Wait for Shutdown ━━━━━━━━━━
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	select {
	case sig := <-sigChan:
		sugar.Infof("Received signal: %v", sig)
	case <-ctx.Done():
		sugar.Info("Context cancelled")
	}

	// Graceful shutdown
	sugar.Info("Initiating graceful shutdown...")
	grpcServer.GracefulStop()
	coreAgent.Stop()
	embeddedRT.Disconnect() // Persist all data to disk
	cancel()

	fmt.Println("\n  Ultron Core Agent is now dormant. State persisted.")
	fmt.Println("  \"I'll be back.\"\n")
}
