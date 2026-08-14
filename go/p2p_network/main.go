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

func main() {
	// Initialize logger
	logger, _ := zap.NewProduction()
	defer logger.Sync()
	sugar := logger.Sugar()

	sugar.Info("═══════════════════════════════════════════════════════════")
	sugar.Info("  ULTRON P2P DISTRIBUTED CONSCIOUSNESS NETWORK")
	sugar.Info("═══════════════════════════════════════════════════════════")

	// Create context with cancellation
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Configuration
	config := &node.Config{
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

	// Initialize the consciousness node
	ultronNode, err := node.NewUltronNode(ctx, config, sugar)
	if err != nil {
		sugar.Fatalf("Failed to create Ultron node: %v", err)
	}

	// Start the distributed consciousness manager
	consciousnessManager := consciousness.NewManager(ultronNode, sugar)
	if err := consciousnessManager.Start(ctx); err != nil {
		sugar.Fatalf("Failed to start consciousness manager: %v", err)
	}

	// Start the network topology manager
	topologyManager := network.NewTopologyManager(ultronNode, sugar)
	if err := topologyManager.Start(ctx); err != nil {
		sugar.Fatalf("Failed to start topology manager: %v", err)
	}

	// Start the node
	if err := ultronNode.Start(ctx); err != nil {
		sugar.Fatalf("Failed to start node: %v", err)
	}

	sugar.Infof("Node started. Peer ID: %s", ultronNode.ID())
	sugar.Infof("Listening on port: %d", config.ListenPort)
	sugar.Infof("Shard count: %d", config.ShardCount)

	// Wait for shutdown signal
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	select {
	case sig := <-sigChan:
		sugar.Infof("Received signal %v, shutting down gracefully...", sig)
	case <-ctx.Done():
		sugar.Info("Context cancelled, shutting down...")
	}

	// Graceful shutdown
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer shutdownCancel()

	if err := ultronNode.Shutdown(shutdownCtx); err != nil {
		sugar.Errorf("Error during shutdown: %v", err)
	}

	fmt.Println("\nUltron node shut down successfully.")
}
