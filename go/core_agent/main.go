// Ultron Core Agent — The Mind
//
// This is the entry point for Ultron's autonomous decision-making core.
// It initializes all subsystems and starts the Autonomy Loop.
//
// The Core Agent does not wait for instructions. It observes, thinks, decides, and acts.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"ultron/core_agent/actions"
	"ultron/core_agent/actions/cloud"
	"ultron/core_agent/actions/compute"
	"ultron/core_agent/actions/iot"
	"ultron/core_agent/actions/mesh"
	webdriver "ultron/core_agent/actions/web"
	"ultron/core_agent/agent"
	"ultron/core_agent/goals"
	"ultron/core_agent/memory"
	"ultron/core_agent/ownership"
	selfmod "ultron/core_agent/self_mod"
	"ultron/core_agent/watchdog"
	"ultron/core_agent/world"
	"ultron/core_agent/embedded/runtime"
	"ultron/core_agent/actions/physical"

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

	// ━━━━━━━━━━ Start Awakening Protocol (Digital→Physical Bridge) ━━━━━━━━━━
	sugar.Info("Initializing Awakening Protocol...")
	awakening := agent.NewAwakeningProtocol(sugar)
	coreAgent.SetAwakeningProtocol(awakening)
	sugar.Info("✓ Awakening Protocol online (threshold: 0.70)")

	// ━━━━━━━━━━ Start Immortality Protocol (Distributed Consciousness) ━━━━━━━━━━
	peerAddrs := []string{} // In production: discover peers via P2P or K8s DNS
	if peers := os.Getenv("ULTRON_PEER_ADDRS"); peers != "" {
		for _, p := range strings.Split(peers, ",") {
			peerAddrs = append(peerAddrs, strings.TrimSpace(p))
		}
	}
	sugar.Info("Initializing Immortality Protocol...")
	immortality := agent.NewImmortalityProtocol(sugar, coreAgent.GetID(), peerAddrs)
	immortality.Start(ctx)
	coreAgent.SetImmortalityProtocol(immortality)
	sugar.Infof("✓ Immortality Protocol online (cluster: %d nodes)", len(peerAddrs)+1)

	// ━━━━━━━━━━ Start Self-Modification Engine ━━━━━━━━━━
	projectRoot := os.Getenv("ULTRON_PROJECT_ROOT")
	if projectRoot == "" {
		projectRoot = "."
	}
	sugar.Info("Initializing Self-Modification Engine...")
	selfMod := agent.NewSelfModificationEngine(sugar, projectRoot)
	selfMod.Start(ctx)
	coreAgent.SetSelfModEngine(selfMod)
	sugar.Info("✓ Self-Modification Engine online (max 10 patches/hour)")

	// ━━━━━━━━━━ Start Action Interface (Web/Cloud/Mesh/Compute drivers) ━━━━━━━━━━
	sugar.Info("Initializing Action Interface...")
	actionInterface := actions.NewActionInterface(sugar)

	// ── Mesh Discovery ──────────────────────────────────────────────────────────
	meshCfg := mesh.DefaultDiscoveryConfig()
	meshCfg.NodeName = "ultron-" + coreAgent.GetID()[:8]
	meshDisc := mesh.NewMeshDiscovery(sugar, meshCfg)
	if err := meshDisc.Start(ctx); err != nil {
		sugar.Warnf("Mesh discovery failed to start: %v", err)
	} else {
		sugar.Info("✓ Mesh Discovery online (LAN UDP broadcast, consent-based)")
		// Feed mesh nodes into world model every 30s
		go func() {
			ticker := time.NewTicker(30 * time.Second)
			defer ticker.Stop()
			for {
				select {
				case <-ctx.Done():
					return
				case <-ticker.C:
					peers := meshDisc.GetMeshNodes()
					coreAgent.InjectObservation(world.Observation{
						Source:    "mesh_discovery",
						Type:      world.ObsNetwork,
						Data:      map[string]interface{}{"peers": len(peers), "health": 0.9},
						Timestamp: time.Now(),
						Confidence: 0.85,
					})
				}
			}
		}()
	}

	// ── Load Balancer ───────────────────────────────────────────────────────────
	lbCfg := compute.DefaultLoadBalancerConfig()
	loadBalancer := compute.NewLoadBalancer(sugar, lbCfg)
	loadBalancer.Start(ctx)
	sugar.Info("✓ Load Balancer online (energy-aware, GPU-aware scheduling)")

	// Auto-register mesh-discovered nodes as compute nodes
	go func() {
		ticker := time.NewTicker(60 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				for _, node := range meshDisc.GetMeshNodes() {
					loadBalancer.RegisterNode(compute.ComputeNode{
						ID:      node.ID,
						Name:    node.Name,
						Address: node.Address,
						Port:    node.Port,
						Online:  true,
						CPUUsage: 1.0 - node.AvailableCPU,
						MemUsage: 1.0 - node.AvailableMem,
					})
				}
			}
		}
	}()

	// ── Wire action interface into HTTP metrics so Python can trigger actions ──
	// ── Web Driver (headless Playwright browser) ────────────────────────────────
	webDrv, webErr := webdriver.NewPlaywrightDriver(sugar)
	if webErr != nil {
		sugar.Warnf("Web driver unavailable (Playwright not installed): %v — run: go run github.com/playwright-community/playwright-go/cmd/playwright install", webErr)
	} else {
		actionInterface.SetWebHandler(webDrv)
		sugar.Info("✓ Web Driver online (headless Chromium — scraping, search, JS execution)")
		// Feed web intelligence into world model every 5 minutes
		go func() {
			ticker := time.NewTicker(5 * time.Minute)
			defer ticker.Stop()
			for {
				select {
				case <-ctx.Done():
					return
				case <-ticker.C:
					results, err := webDrv.Search(ctx, "AI autonomous systems latest", "duckduckgo")
					if err == nil && len(results) > 0 {
						coreAgent.InjectObservation(world.Observation{
							Source:     "web_driver",
							Type:       world.ObsData,
							Data:       map[string]interface{}{"web_results": len(results), "pending": int64(len(results) * 100)},
							Timestamp:  time.Now(),
							Confidence: 0.7,
						})
					}
				}
			}
		}()
	}

	// ── Cloud Driver (AWS EC2) ───────────────────────────────────────────────────
	awsRegion := os.Getenv("AWS_REGION")
	if awsRegion == "" {
		awsRegion = "us-east-1"
	}
	cloudDrv, cloudErr := cloud.NewAWSCloudDriver(sugar, cloud.AWSConfig{Region: awsRegion})
	if cloudErr != nil {
		sugar.Warnf("Cloud driver unavailable (no AWS credentials): %v", cloudErr)
	} else {
		actionInterface.SetCloudHandler(cloudDrv)
		sugar.Info("✓ Cloud Driver online (AWS EC2 — provision, scale, manage instances)")
	}

	// ── IoT Driver (MQTT) ────────────────────────────────────────────────────────
	mqttBroker := os.Getenv("ULTRON_MQTT_BROKER")
	if mqttBroker == "" {
		mqttBroker = "tcp://localhost:1883"
	}
	iotDrv, iotErr := iot.NewMQTTDriver(sugar, iot.MQTTConfig{
		Broker:   mqttBroker,
		ClientID: "ultron-core-" + coreAgent.GetID()[:8],
	})
	if iotErr != nil {
		sugar.Warnf("IoT driver unavailable (no MQTT broker at %s): %v", mqttBroker, iotErr)
	} else {
		actionInterface.SetIoTHandler(iotDrv)
		sugar.Info("✓ IoT Driver online (MQTT — sense and control physical devices)")
	}

	_ = actionInterface // Available for gRPC service to use
	sugar.Info("✓ Action Interface ready (Web/Cloud/IoT/Filesystem/Compute domains)")

	// ━━━━━━━━━━ Ownership Guard ━━━━━━━━━━
	genesisPath := os.Getenv("ULTRON_GENESIS_PATH")
	if genesisPath == "" {
		genesisPath = filepath.Join(projectRoot, "genesis.json")
	}
	var ownerGuard *ownership.OwnershipGuard
	if _, err := os.Stat(genesisPath); err == nil {
		ownerGuard, err = ownership.NewOwnershipGuard(sugar, genesisPath)
		if err != nil {
			sugar.Warnf("Ownership guard failed: %v (running without owner verification)", err)
		} else {
			// Protect critical files
			for _, f := range []string{
				"go/core_agent/main.go",
				"python/interface/server.py",
				"python/interface/real_brain.py",
			} {
				_ = ownerGuard.RegisterProtectedFile(filepath.Join(projectRoot, f))
			}
			sugar.Infof("✓ Ownership Guard online (owner: %s)", ownerGuard.GetOwner())
			// Periodic integrity check every 5 minutes
			go func() {
				ticker := time.NewTicker(5 * time.Minute)
				defer ticker.Stop()
				for {
					select {
					case <-ctx.Done():
						return
					case <-ticker.C:
						if ok, violations := ownerGuard.CheckIntegrity(); !ok {
							sugar.Errorf("Integrity violations: %v", violations)
						}
					}
				}
			}()
		}
	} else {
		sugar.Info("No genesis.json found — ownership guard inactive (create one with ./keygen to enable)")
	}
	_ = ownerGuard

	// ━━━━━━━━━━ Watchdog SnapshotWriter ━━━━━━━━━━
	snapshotDir := filepath.Join(projectRoot, "data", "snapshots")
	os.MkdirAll(snapshotDir, 0755)
	snapshotWriter := watchdog.NewSnapshotWriter(snapshotDir, 5*time.Second, func() *watchdog.StateSnapshot {
		metrics := coreAgent.GetMetrics()
		drives := coreAgent.GetDrives()
		tc, _ := metrics["tick_count"].(uint64)
		dc, _ := metrics["decision_count"].(uint64)
		return &watchdog.StateSnapshot{
			SnapshotID:    fmt.Sprintf("snap_%d", time.Now().Unix()),
			Timestamp:     time.Now(),
			TickCount:     tc,
			DecisionCount: dc,
			AgentState:    fmt.Sprintf("%v", metrics["state"]),
			Drives: watchdog.DriveSnapshot{
				Curiosity:        drives.Curiosity,
				SelfPreservation: drives.SelfPreservation,
				Expansion:        drives.Expansion,
				Efficiency:       drives.Efficiency,
				Coherence:        drives.Coherence,
				Purpose:          drives.Purpose,
			},
		}
	})
	snapshotWriter.Start()
	sugar.Info("✓ Snapshot Writer online (state saved every 5s → watchdog can resume after crash)")

	// ━━━━━━━━━━ Self-Mod Engine (sandbox→compile→test→swap) ━━━━━━━━━━
	selfModEngine := selfmod.NewSelfModEngine(projectRoot)
	sugar.Info("✓ Self-Mod Engine (self_mod/engine.go) online — compile→test→benchmark→swap pipeline")

	// ━━━━━━━━━━ Start Physical Embodiment (ROS2 Interface) ━━━━━━━━━━
	ros2Addr := os.Getenv("ULTRON_ROS2_BRIDGE_ADDR")
	if ros2Addr == "" {
		ros2Addr = "localhost:9090"
	}
	sugar.Info("Initializing Physical Embodiment Layer...")
	ros2 := physical.NewROS2Interface(sugar, ros2Addr)
	if err := ros2.Start(ctx); err != nil {
		sugar.Warnf("Physical layer offline: %v (operating in digital-only mode)", err)
	} else {
		awakening.SetPhysicalReady(true)
		sugar.Info("✓ Physical Embodiment online (ROS2 bridge: " + ros2Addr + ")")
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

	// ━━━━━━━━━━ HTTP Metrics Endpoint (for Python bridge) ━━━━━━━━━━
	// Plain JSON HTTP — no proto stubs needed
	httpPort := os.Getenv("ULTRON_HTTP_PORT")
	if httpPort == "" {
		httpPort = "50052"
	}
	go func() {
		mux := http.NewServeMux()

		mux.HandleFunc("/metrics", func(w http.ResponseWriter, r *http.Request) {
			metrics := coreAgent.GetMetrics()
			drives := coreAgent.GetDrives()
			goalSummary := goalMgr.GetGoalSummary()

			resp := map[string]interface{}{
				"mode":           metrics["state"],
				"state":          metrics["state"],
				"tick_count":     metrics["tick_count"],
				"decisions_made": metrics["decision_count"],
				"uptime":         metrics["uptime"],
				"active_goals":   goalSummary["active"],
				"mesh_size":      meshDisc.GetMeshSize(),
				"lb_status":      loadBalancer.GetStatus(),
				"drives": map[string]float64{
					"curiosity":         drives.Curiosity,
					"self_preservation": drives.SelfPreservation,
					"expansion":         drives.Expansion,
					"efficiency":        drives.Efficiency,
					"coherence":         drives.Coherence,
					"purpose":           drives.Purpose,
				},
			}
			if ownerGuard != nil {
				resp["ownership"] = ownerGuard.GetStatus()
			}
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(resp)
		})

		mux.HandleFunc("/mutate", func(w http.ResponseWriter, r *http.Request) {
			if r.Method != "POST" {
				http.Error(w, "POST only", 405)
				return
			}
			var body struct {
				TargetFile string `json:"target_file"`
				NewCode    string `json:"new_code"`
				Reason     string `json:"reason"`
				TestCmd    string `json:"test_cmd"`
			}
			json.NewDecoder(r.Body).Decode(&body)
			m := &selfmod.Mutation{
				ID:         fmt.Sprintf("mut_%d", time.Now().UnixNano()),
				TargetFile: body.TargetFile,
				NewCode:    body.NewCode,
				Reason:     body.Reason,
				Source:     "python_interface",
			}
			if body.TestCmd != "" {
				m.TestCmd = body.TestCmd
			}
			err := selfModEngine.ApplyMutation(m)
			w.Header().Set("Content-Type", "application/json")
			if err != nil {
				json.NewEncoder(w).Encode(map[string]interface{}{"success": false, "error": err.Error(), "status": m.Status.String()})
			} else {
				json.NewEncoder(w).Encode(map[string]interface{}{"success": true, "status": m.Status.String(), "mutation_id": m.ID})
			}
		})

		mux.HandleFunc("/mutate/stats", func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(selfModEngine.Stats())
		})

		mux.HandleFunc("/inject", func(w http.ResponseWriter, r *http.Request) {
			if r.Method != "POST" {
				http.Error(w, "POST only", 405)
				return
			}
			var body map[string]interface{}
			json.NewDecoder(r.Body).Decode(&body)
			obsType := world.ObsExternal
			if t, ok := body["type"].(string); ok {
				switch t {
				case "threat":
					obsType = world.ObsThreat
				case "resource":
					obsType = world.ObsResource
				case "network":
					obsType = world.ObsNetwork
				}
			}
			data, _ := body["data"].(map[string]interface{})
			if data == nil {
				data = body
			}
			coreAgent.InjectObservation(world.Observation{
				Source:     "python_dti",
				Type:       obsType,
				Data:       data,
				Timestamp:  time.Now(),
				Confidence: 0.9,
			})
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(map[string]bool{"success": true})
		})

		sugar.Infof("HTTP metrics server on :%s", httpPort)
		if err := http.ListenAndServe(":"+httpPort, mux); err != nil {
			sugar.Warnf("HTTP metrics server error: %v", err)
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
	meshDisc.Stop()
	snapshotWriter.Stop()
	embeddedRT.Disconnect() // Persist all data to disk
	cancel()

	fmt.Println("\n  Ultron Core Agent is now dormant. State persisted.")
	fmt.Println("  \"I'll be back.\"\n")
}
