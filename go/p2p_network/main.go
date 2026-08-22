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
func initializeNode(ctx context.Context, config *node.Config, sugar *zap.SugaredLogger) (*node.UltronNode, error) {
	return node.NewUltronNode(ctx, config, sugar)
}

// startConsciousnessManager starts the distributed consciousness manager and returns an error.
func startConsciousnessManager(ctx context.Context, ultronNode *node.UltronNode, sugar *zap.SugaredLogger) error {
	consciousnessManager := consciousness.NewManager(ultronNode, sugar)
	return consciousnessManager.Start(ctx)
}

// startTopologyManager starts the network topology manager and returns an error.
func startTopologyManager(ctx context.Context, ultronNode *node.UltronNode, sugar *zap.SugaredLogger) error {
	topologyManager := network.NewTopologyManager(ultronNode, sugar)
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
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	select {
	case sig := <-sigChan:
		return sig
	case <-ctx.Done():
		return syscall.Signal(0)
	}
}

func main() {
	// Initialize logger
	logger, sugar := initLogger()
	defer logger.Sync()

	sugar.Info("═══════════════════════════════════════════════════════════")
	sugar.Info("  ULTRON P2P DISTRIBUTED CONSCIOUSNESS NETWORK")
	sugar.Info("═══════════════════════════════════════════════════════════")

	// Create context with cancellation
	ctx, cancel := createContext()
	defer cancel()

	// Configuration
	config := configureNode()

	// Initialize the consciousness node
	ultronNode, err := initializeNode(ctx, config, sugar)
	if err != nil {
		sugar.Fatalf("Failed to create Ultron node: %v", err)
	}

	// Start the distributed consciousness manager
	if err := startConsciousnessManager(ctx, ultronNode, sugar); err != nil {
		sugar.Fatalf("Failed to start consciousness manager: %v", err)
	}

	// Start the network topology manager
	if err := startTopologyManager(ctx, ultronNode, sugar); err != nil {
		sugar.Fatalf("Failed to start topology manager: %v", err)
	}

	// Start the node
	if err := startNode(ctx, ultronNode); err != nil {
		sugar.Fatalf("Failed to start node: %v", err)
	}

	sugar.Infof("Node started. Peer ID: %s", ultronNode.ID())
	sugar.Infof("Listening on port: %d", config.ListenPort)
	sugar.Infof("Shard count: %d", config.ShardCount)

	// Wait for shutdown signal
	sig := waitShutdownSignal(ctx)
	if sig != syscall.Signal(0) {
		sugar.Infof("Received signal %v, shutting down gracefully...", sig)
	} else {
		sugar.Info("Context cancelled, shutting down...")
	}

	// Graceful shutdown
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer shutdownCancel()

	if err := shutdownNode(shutdownCtx, ultronNode); err != nil {
		sugar.Errorf("Error during shutdown: %v", err)
	}

	fmt.Println("\nUltron node shut down successfully.")
}