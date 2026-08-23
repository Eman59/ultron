// Package agent — Real-Time World Data Feeds
//
// Feeds REAL data into the world model instead of synthetic observations:
//   - RSS/News: Global events, AI research, tech news
//   - System Metrics: CPU, memory, disk, network (real /proc data)
//   - GitHub Activity: Monitor repos, track issues, watch PRs
//   - Network Topology: Actual local network scanning
//   - Environment: Weather, time-of-day awareness
//
// Each feed runs on its own goroutine at the appropriate polling rate.
// Data flows into the WorldModel via the observation channel.
package agent

import (
	"context"
	"encoding/json"
	"encoding/xml"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"runtime"
	"strings"
	"sync"
	"time"

	"ultron/core_agent/world"

	"go.uber.org/zap"
)

// ═══════════════════════════════════════════════════════════════
// WORLD FEEDS MANAGER
// ═══════════════════════════════════════════════════════════════

// WorldFeedsManager manages all real-time data feeds.
type WorldFeedsManager struct {
	mu sync.RWMutex

	observeCh chan world.Observation
	logger    *zap.SugaredLogger
	ctx       context.Context
	cancel    context.CancelFunc

	// Feed configuration
	feeds     map[string]*FeedConfig
	active    map[string]bool

	// Metrics
	totalObservations int64
	feedErrors        map[string]int64
}

// FeedConfig defines a data feed.
type FeedConfig struct {
	Name      string
	Interval  time.Duration
	Enabled   bool
	FeedFunc  func(ctx context.Context) []world.Observation
}

// NewWorldFeedsManager creates the feeds manager.
func NewWorldFeedsManager(observeCh chan world.Observation, logger *zap.SugaredLogger) *WorldFeedsManager {
	ctx, cancel := context.WithCancel(context.Background())

	wfm := &WorldFeedsManager{
		observeCh: observeCh,
		logger:    logger,
		ctx:       ctx,
		cancel:    cancel,
		feeds:     make(map[string]*FeedConfig),
		active:    make(map[string]bool),
		feedErrors: make(map[string]int64),
	}

	// Register all feeds
	wfm.logger.Debugf("[WorldFeeds] Initializing feeds manager")
	wfm.registerFeeds()
	wfm.logger.Infof("[WorldFeeds] Initialized feeds manager with %d feeds", len(wfm.feeds))

	return wfm
}

// Start launches all enabled feeds.
func (wfm *WorldFeedsManager) Start() {
	wfm.mu.Lock()
	defer wfm.mu.Unlock()

	wfm.logger.Infof("[WorldFeeds] Starting feeds manager")
	for name, feed := range wfm.feeds {
		if feed.Enabled {
			wfm.active[name] = true
			wfm.logger.Debugf("[WorldFeeds] Starting feed: %s", name)
			go wfm.runFeed(name, feed)
		}
	}

	wfm.logger.Infof("[WorldFeeds] Started %d real-time data feeds", len(wfm.active))
}

// Stop shuts down all feeds.
func (wfm *WorldFeedsManager) Stop() {
	wfm.logger.Infof("[WorldFeeds] Stopping feeds manager")
	wfm.cancel()
	wfm.logger.Debugf("[WorldFeeds] Feeds manager stopped")
}

func (wfm *WorldFeedsManager) registerFeeds() {
	// 1. System Metrics (every 5 seconds)
	wfm.feeds["system_metrics"] = &FeedConfig{
		Name:     "system_metrics",
		Interval: 5 * time.Second,
		Enabled:  true,
		FeedFunc: wfm.feedSystemMetrics,
	}

	// 2. RSS/News (every 5 minutes)
	wfm.feeds["rss_news"] = &FeedConfig{
		Name:     "rss_news",
		Interval: 5 * time.Minute,
		Enabled:  true,
		FeedFunc: wfm.feedRSSNews,
	}

	// 3. GitHub Activity (every 10 minutes)
	wfm.feeds["github"] = &FeedConfig{
		Name:     "github",
		Interval: 10 * time.Minute,
		Enabled:  true,
		FeedFunc: wfm.feedGitHubActi,
	}
	wfm.logger.Debugf("[WorldFeeds] Registered %d feeds", len(wfm.feeds))
}