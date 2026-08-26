// Package web implements the WebHandler interface using Playwright for
// headless browser automation — Ultron's eyes on the internet.
package web

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"sync"
	"time"

	"ultron/core_agent/actions"
	"github.com/mxschmitt/playwright-go"
	"go.uber.org/zap"
)

// SearchResult — use canonical type from parent package
type SearchResult = actions.SearchResult

// ScrapedArticle is a structured news article.
type ScrapedArticle struct {
	Headline    string    `json:"headline"`
	Summary     string    `json:"summary"`
	Source      string    `json:"source"`
	URL         string    `json:"url"`
	PublishedAt string    `json:"published_at"`
	ScrapedAt   time.Time `json:"scraped_at"`
}

// PlaywrightDriver implements WebHandler using a headless Chromium browser.
type PlaywrightDriver struct {
	mu sync.Mutex

	logger  *zap.SugaredLogger
	pw      *playwright.Playwright
	browser playwright.Browser
	active  bool

	// Configuration
	headless    bool
	timeout     time.Duration
	userAgent   string
	maxRetries  int

	// Metrics
	requestCount  uint64
	errorCount    uint64
	captchaCount  uint64
}

// NewPlaywrightDriver creates and initializes the web driver.
func NewPlaywrightDriver(logger *zap.SugaredLogger) (*PlaywrightDriver, error) {
	if logger == nil {
		return nil, fmt.Errorf("logger cannot be nil")
	}

	driver := &PlaywrightDriver{
		logger:     logger,
		headless:   true,
		timeout:    30 * time.Second,
		userAgent:  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
		maxRetries: 3,
	}

	if err := driver.init(); err != nil {
		return nil, err
	}

	return driver, nil
}

func (d *PlaywrightDriver) init() error {
	if d.pw != nil {
		return fmt.Errorf("playwright is already initialized")
	}

	pw, err := playwright.Run()
	if err != nil {
		return fmt.Errorf("failed to start playwright: %w", err)
	}
	d.pw = pw

	browser, err := pw.Chromium.Launch(playwright.BrowserTypeLaunchOptions{
		Headless: playwright.Bool(d.headless),
	})
	if err != nil {
		return fmt.Errorf("failed to launch browser: %w", err)
	}
	d.browser = browser
	d.active = true

	d.logger.Info("Playwright web driver initialized (headless Chromium)")
	return nil
}

// ═══════════════════════════════════════════════════════════════
// WebHandler Interface Implementation
// ═══════════════════════════════════════════════════════════════

// Get performs an HTTP GET via the browser and returns the page content.
func (d *PlaywrightDriver) Get(ctx context.Context, url string, headers map[string]string) ([]byte, int, error) {
	if ctx == nil {
		return nil, 0, fmt.Errorf("context cannot be nil")
	}

	if url == "" {
		return nil, 0, fmt.Errorf("url cannot be empty")
	}

	if headers == nil {
		headers = make(map[string]string)
	}

	d.mu.Lock()
	defer d.mu.Unlock()
	d.requestCount++

	page, err := d.newPage(headers)
	if err != nil {
		d.errorCount++
		return nil, 0, err
	}
	defer func() {
		if err := page.Close(); err != nil {
			d.logger.Warnf("failed to close page: %v", err)
		}
	}()

	resp, err := page.Goto(url, playwright.PageGotoOptions{
		WaitUntil: playwright.WaitUntilStateNetworkidle,
		Timeout:   playwright.Float(float64(d.timeout.Milliseconds())),
	})
	if err != nil {
		d.errorCount++
		return nil, 0, fmt.Errorf("navigation failed: %w", err)
	}

	// Check for CAPTCHA
	if d.detectCaptcha(page) {
		d.captchaCount++
		d.logger.Warn("CAPTCHA detected")
		return nil, 0, fmt.Errorf("CAPTCHA detected")
	}

	// Check for timeout
	if ctx.Err() != nil {
		d.errorCount++
		return nil, 0, fmt.Errorf("request timed out: %w", ctx.Err())
	}

	// Get page content
	content, err := page.Content()
	if err != nil {
		d.errorCount++
		return nil, 0, fmt.Errorf("failed to get page content: %w", err)
	}

	// Get status code
	statusCode, err := resp.Status()
	if err != nil {
		d.errorCount++
		return nil, 0, fmt.Errorf("failed to get status code: %w", err)
	}

	return []byte(content), statusCode, nil
}