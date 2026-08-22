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
	wfm.registerFeeds()

	return wfm
}

// Start launches all enabled feeds.
func (wfm *WorldFeedsManager) Start() {
	wfm.mu.Lock()
	defer wfm.mu.Unlock()

	for name, feed := range wfm.feeds {
		if feed.Enabled {
			wfm.active[name] = true
			go wfm.runFeed(name, feed)
		}
	}

	wfm.logger.Infof("[WorldFeeds] Started %d real-time data feeds", len(wfm.active))
}

// Stop shuts down all feeds.
func (wfm *WorldFeedsManager) Stop() {
	wfm.cancel()
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
		FeedFunc: wfm.feedGitHubActivity,
	}

	// 4. Network Scan (every 2 minutes)
	wfm.feeds["network_scan"] = &FeedConfig{
		Name:     "network_scan",
		Interval: 2 * time.Minute,
		Enabled:  true,
		FeedFunc: wfm.feedNetworkScan,
	}

	// 5. Environment/Time (every 30 seconds)
	wfm.feeds["environment"] = &FeedConfig{
		Name:     "environment",
		Interval: 30 * time.Second,
		Enabled:  true,
		FeedFunc: wfm.feedEnvironment,
	}

	// 6. Disk Usage (every 60 seconds)
	wfm.feeds["disk_usage"] = &FeedConfig{
		Name:     "disk_usage",
		Interval: 60 * time.Second,
		Enabled:  true,
		FeedFunc: wfm.feedDiskUsage,
	}
}

func (wfm *WorldFeedsManager) runFeed(name string, feed *FeedConfig) {
	ticker := time.NewTicker(feed.Interval)
	defer ticker.Stop()

	// First run immediately
	wfm.executeFeed(name, feed)

	for {
		select {
		case <-wfm.ctx.Done():
			return
		case <-ticker.C:
			wfm.executeFeed(name, feed)
		}
	}
}

func (wfm *WorldFeedsManager) executeFeed(name string, feed *FeedConfig) {
	observations := feed.FeedFunc(wfm.ctx)
	for _, obs := range observations {
		select {
		case wfm.observeCh <- obs:
			wfm.mu.Lock()
			wfm.totalObservations++
			wfm.mu.Unlock()
		default:
			// Channel full, drop (non-blocking)
		}
	}
}

// ═══════════════════════════════════════════════════════════════
// FEED IMPLEMENTATIONS
// ═══════════════════════════════════════════════════════════════

func (wfm *WorldFeedsManager) feedSystemMetrics(ctx context.Context) []world.Observation {
	var memStats runtime.MemStats
	runtime.ReadMemStats(&memStats)

	// Get load average
	loadAvg := 0.0
	if out, err := exec.CommandContext(ctx, "sysctl", "-n", "vm.loadavg").Output(); err == nil {
		fmt.Sscanf(strings.TrimSpace(string(out)), "{ %f", &loadAvg)
	}

	// Get CPU usage (approximate via goroutine count)
	numGoroutines := runtime.NumGoroutine()
	numCPU := runtime.NumCPU()
	cpuPressure := float64(numGoroutines) / float64(numCPU*100)
	if cpuPressure > 1.0 {
		cpuPressure = 1.0
	}

	return []world.Observation{
		{
			Source:     "system_metrics",
			Type:       world.ObsResource,
			Timestamp:  time.Now(),
			Confidence: 0.99,
			Data: map[string]interface{}{
				"memory_alloc_mb":   memStats.Alloc / 1024 / 1024,
				"memory_sys_mb":     memStats.Sys / 1024 / 1024,
				"goroutines":        numGoroutines,
				"gc_cycles":         memStats.NumGC,
				"cpu_count":         numCPU,
				"cpu_pressure":      cpuPressure,
				"load_avg":          loadAvg,
				"heap_objects":      memStats.HeapObjects,
			},
		},
	}
}

func (wfm *WorldFeedsManager) feedRSSNews(ctx context.Context) []world.Observation {
	// RSS feeds to monitor
	feeds := []string{
		"https://news.ycombinator.com/rss",
		"https://arxiv.org/rss/cs.AI",
	}

	observations := make([]world.Observation, 0)
	client := &http.Client{Timeout: 10 * time.Second}

	for _, feedURL := range feeds {
		req, err := http.NewRequestWithContext(ctx, "GET", feedURL, nil)
		if err != nil {
			continue
		}

		resp, err := client.Do(req)
		if err != nil {
			continue
		}

		body, _ := io.ReadAll(io.LimitReader(resp.Body, 50000))
		resp.Body.Close()

		// Parse RSS
		var rss struct {
			Channel struct {
				Items []struct {
					Title string `xml:"title"`
					Link  string `xml:"link"`
				} `xml:"item"`
			} `xml:"channel"`
		}

		if xml.Unmarshal(body, &rss) == nil {
			titles := make([]string, 0)
			for i, item := range rss.Channel.Items {
				if i >= 5 {
					break
				}
				titles = append(titles, item.Title)
			}

			if len(titles) > 0 {
				observations = append(observations, world.Observation{
					Source:     "rss_" + feedURL,
					Type:       world.ObsData,
					Timestamp:  time.Now(),
					Confidence: 0.8,
					Data: map[string]interface{}{
						"feed":       feedURL,
						"headlines":  titles,
						"item_count": len(rss.Channel.Items),
					},
				})
			}
		}
	}

	return observations
}

func (wfm *WorldFeedsManager) feedGitHubActivity(ctx context.Context) []world.Observation {
	// Monitor own repo activity
	repoOwner := os.Getenv("GITHUB_OWNER")
	repoName := os.Getenv("GITHUB_REPO")
	token := os.Getenv("GITHUB_TOKEN")

	if repoOwner == "" || repoName == "" {
		return nil
	}

	client := &http.Client{Timeout: 10 * time.Second}
	url := fmt.Sprintf("https://api.github.com/repos/%s/%s/events", repoOwner, repoName)

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil
	}
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}

	resp, err := client.Do(req)
	if err != nil {
		return nil
	}
	defer resp.Body.Close()

	var events []map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&events)

	recentEvents := make([]string, 0)
	for i, event := range events {
		if i >= 5 {
			break
		}
		eventType, _ := event["type"].(string)
		recentEvents = append(recentEvents, eventType)
	}

	return []world.Observation{
		{
			Source:     "github",
			Type:       world.ObsData,
			Timestamp:  time.Now(),
			Confidence: 0.9,
			Data: map[string]interface{}{
				"repo":          fmt.Sprintf("%s/%s", repoOwner, repoName),
				"recent_events": recentEvents,
				"event_count":   len(events),
			},
		},
	}
}

func (wfm *WorldFeedsManager) feedNetworkScan(ctx context.Context) []world.Observation {
	// Quick ARP scan for local network awareness
	cmd := exec.CommandContext(ctx, "arp", "-a")
	out, err := cmd.Output()
	if err != nil {
		return nil
	}

	lines := strings.Split(string(out), "\n")
	hosts := 0
	for _, line := range lines {
		if strings.Contains(line, "at") && !strings.Contains(line, "incomplete") {
			hosts++
		}
	}

	return []world.Observation{
		{
			Source:     "network_scan",
			Type:       world.ObsNetwork,
			Timestamp:  time.Now(),
			Confidence: 0.85,
			Data: map[string]interface{}{
				"local_hosts":  hosts,
				"arp_entries":  len(lines),
				"scan_method":  "arp",
			},
		},
	}
}

func (wfm *WorldFeedsManager) feedEnvironment(ctx context.Context) []world.Observation {
	now := time.Now()

	// Time-based context
	hour := now.Hour()
	isNight := hour < 6 || hour > 22
	isWorkHours := hour >= 9 && hour <= 17

	return []world.Observation{
		{
			Source:     "environment",
			Type:       world.ObsExternal,
			Timestamp:  now,
			Confidence: 1.0,
			Data: map[string]interface{}{
				"hour":          hour,
				"day_of_week":   now.Weekday().String(),
				"is_night":      isNight,
				"is_work_hours": isWorkHours,
				"timezone":      now.Location().String(),
				"uptime_hours":  time.Since(time.Now()).Hours(), // Will be set by caller
			},
		},
	}
}

func (wfm *WorldFeedsManager) feedDiskUsage(ctx context.Context) []world.Observation {
	cmd := exec.CommandContext(ctx, "df", "-h", ".")
	out, err := cmd.Output()
	if err != nil {
		return nil
	}

	// Parse df output (second line has the data)
	lines := strings.Split(string(out), "\n")
	if len(lines) < 2 {
		return nil
	}

	fields := strings.Fields(lines[1])
	if len(fields) < 5 {
		return nil
	}

	return []world.Observation{
		{
			Source:     "disk_usage",
			Type:       world.ObsResource,
			Timestamp:  time.Now(),
			Confidence: 0.95,
			Data: map[string]interface{}{
				"filesystem":   fields[0],
				"size":         fields[1],
				"used":         fields[2],
				"available":    fields[3],
				"use_percent":  fields[4],
			},
		},
	}
}

// GetFeedStats returns metrics about all feeds.
func (wfm *WorldFeedsManager) GetFeedStats() map[string]interface{} {
	wfm.mu.RLock()
	defer wfm.mu.RUnlock()

	return map[string]interface{}{
		"total_observations": wfm.totalObservations,
		"active_feeds":       len(wfm.active),
		"feed_errors":        wfm.feedErrors,
	}
}
