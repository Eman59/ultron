// Package main provides the entry point for Ultron's P2P Distributed Consciousness Network.
// This system distributes AI computation across a decentralized network of nodes,
// providing fault tolerance, self-healing, and distributed intelligence.
package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"ultron/p2p_network/node"
	"ultron/p2p_network/consciousness"
	"ultron/p2p_network/network"

	"go.uber.org/zap"
)

// initLogger initializes the logger and returns the logger and its sugar.
func initLogger() (*zap.Logger, *zap.SugaredLogger) {
	logger, _ := zap.NewProduction()
	sugar := logger.Sugar()
	return logger, sugar
}

// createContext creates a context with cancellation and returns the context and its cancel function.
func createContext() (context.Context, context.CancelFunc) {
	return context.WithCancel(context.Background())
}

// configureNode creates a node configuration and returns it.
func configureNode() *node.Config {
	return &node.Config{
		ListenPort:       4001,
		BootstrapPeers:   []string{},
		MaxPeers:         100,
		ReplicationFactor: 3,
		HeartbeatInterval: 5 * time.Second,
		ConsensusTimeout:  10 * time.Second,
		ShardCount:        16,
		EnableDHT:         true,
		EnablePubSub:      true,
		EnableRelay:       true,
	}
}

// initializeNode initializes the Ultron node and returns it and an error.
func initializeNode(ctx context.Context, nodeConfig *node.Config, logger *zap.SugaredLogger) (*node.UltronNode, error) {
	return node.NewUltronNode(ctx, nodeConfig, logger)
}

// startConsciousnessManager starts the distributed consciousness manager and returns an error.
func startConsciousnessManager(ctx context.Context, ultronNode *node.UltronNode, logger *zap.SugaredLogger) error {
	consciousnessManager := consciousness.NewManager(ultronNode, logger)
	return consciousnessManager.Start(ctx)
}

// startTopologyManager starts the network topology manager and returns an error.
func startTopologyManager(ctx context.Context, ultronNode *node.UltronNode, logger *zap.SugaredLogger) error {
	topologyManager := network.NewTopologyManager(ultronNode, logger)
	return topologyManager.Start(ctx)
}

// startNode starts the Ultron node and returns an error.
func startNode(ctx context.Context, ultronNode *node.UltronNode) error {
	return ultronNode.Start(ctx)
}

// shutdownNode shuts down the Ultron node and returns an error.
func shutdownNode(ctx context.Context, ultronNode *node.UltronNode) error {
	return ultronNode.Shutdown(ctx)
}

// waitShutdownSignal waits for a shutdown signal and returns the signal.
func waitShutdownSignal(ctx context.Context) os.Signal {
	shutdownSignalChannel := make(chan os.Signal, 1)
	signal.Notify(shutdownSignalChannel, syscall.SIGINT, syscall.SIGTERM)

	select {
	case sig := <-shutdownSignalChannel:
		return sig
	case <-ctx.Done():
		return syscall.Signal(0)
	}
}

func main() {
	// Initialize logger
	logger, sugarLogger := initLogger()
	defer logger.Sync()

	sugarLogger.Info("═══════════════════════════════════════════════════════════")
	sugarLogger.Info("  ULTRON")

	// Initialize context
	ctx, cancel := createContext()
	defer cancel()

	// Configure node
	nodeConfig := configureNode()
	// Override port from env if set
	if p := os.Getenv("ULTRON_P2P_PORT"); p != "" {
		fmt.Sscanf(p, "%d", &nodeConfig.ListenPort)
	}
	// Bootstrap peers from env
	if bp := os.Getenv("ULTRON_P2P_BOOTSTRAP"); bp != "" {
		nodeConfig.BootstrapPeers = []string{bp}
	}

	// Initialize node
	ultronNode, err := initializeNode(ctx, nodeConfig, sugarLogger)
	if err != nil {
		sugarLogger.Fatalf("Failed to initialize node: %v", err)
	}

	// Start node
	if err := startNode(ctx, ultronNode); err != nil {
		sugarLogger.Fatalf("Failed to start node: %v", err)
	}
	sugarLogger.Infof("P2P node started on port %d", nodeConfig.ListenPort)

	// Start consciousness and topology managers
	go startConsciousnessManager(ctx, ultronNode, sugarLogger)
	go startTopologyManager(ctx, ultronNode, sugarLogger)

	// ── HTTP bridge so Python can talk to P2P node ──────────────────
	import_net_http_mux := func() {
		// Inline HTTP server — no extra imports needed (net/http is stdlib)
	}
	_ = import_net_http_mux

	httpPort := "6001"
	if hp := os.Getenv("ULTRON_P2P_HTTP_PORT"); hp != "" {
		httpPort = hp
	}
	go func() {
		mux := http.NewServeMux()

		mux.HandleFunc("/status", func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Content-Type", "application/json")
			peers := ultronNode.GetPeers()
			json.NewEncoder(w).Encode(map[string]interface{}{
				"node_id":    ultronNode.GetID(),
				"peer_count": len(peers),
				"port":       nodeConfig.ListenPort,
				"state":      "running",
			})
		})

		mux.HandleFunc("/peers", func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Content-Type", "application/json")
			peers := ultronNode.GetPeers()
			json.NewEncoder(w).Encode(map[string]interface{}{
				"peers": peers,
				"count": len(peers),
			})
		})

		mux.HandleFunc("/broadcast", func(w http.ResponseWriter, r *http.Request) {
			if r.Method != "POST" {
				http.Error(w, "POST only", 405)
				return
			}
			var body map[string]interface{}
			json.NewDecoder(r.Body).Decode(&body)
			msg, _ := json.Marshal(body)
			err := ultronNode.Broadcast(ctx, msg)
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(map[string]interface{}{
				"success": err == nil,
				"error":   fmt.Sprintf("%v", err),
			})
		})

		mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(map[string]string{"status": "alive", "service": "p2p_network"})
		})

		sugarLogger.Infof("P2P HTTP bridge on :%s", httpPort)
		http.ListenAndServe(":"+httpPort, mux)
	}()

	// Wait for shutdown
	sig := waitShutdownSignal(ctx)
	sugarLogger.Infof("Received signal %v, shutting down...", sig)
	shutdownNode(ctx, ultronNode)
	sugarLogger.Info("P2P node stopped")
}
