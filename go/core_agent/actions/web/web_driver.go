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
	d.mu.Lock()
	defer d.mu.Unlock()
	d.requestCount++

	page, err := d.newPage(headers)
	if err != nil {
		d.errorCount++
		return nil, 0, err
	}
	defer page.Close()

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
		d.logger.Warn("CAPTCHA detected, returning partial content")
		return nil, 403, fmt.Errorf("CAPTCHA detected on %s", url)
	}

	content, err := page.Content()
	if err != nil {
		d.errorCount++
		return nil, 0, fmt.Errorf("failed to get content: %w", err)
	}

	status := 200
	if resp != nil {
		status = resp.Status()
	}

	return []byte(content), status, nil
}

// Post performs an HTTP POST via fetch() inside the browser context.
func (d *PlaywrightDriver) Post(ctx context.Context, url string, body []byte, headers map[string]string) ([]byte, int, error) {
	d.mu.Lock()
	defer d.mu.Unlock()
	d.requestCount++

	page, err := d.newPage(headers)
	if err != nil {
		d.errorCount++
		return nil, 0, err
	}
	defer page.Close()

	// Navigate to a blank page first, then use fetch
	if _, err := page.Goto("about:blank"); err != nil {
		return nil, 0, err
	}

	// Build headers JSON
	headersJSON, _ := json.Marshal(headers)

	// Execute fetch in browser context
	script := fmt.Sprintf(`
		async () => {
			const resp = await fetch(%q, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json', ...%s },
				body: %q
			});
			const text = await resp.text();
			return JSON.stringify({ status: resp.status, body: text });
		}
	`, url, string(headersJSON), string(body))

	result, err := page.Evaluate(script)
	if err != nil {
		d.errorCount++
		return nil, 0, fmt.Errorf("POST failed: %w", err)
	}

	// Parse result
	var fetchResult struct {
		Status int    `json:"status"`
		Body   string `json:"body"`
	}
	if resultStr, ok := result.(string); ok {
		json.Unmarshal([]byte(resultStr), &fetchResult)
	}

	return []byte(fetchResult.Body), fetchResult.Status, nil
}

// Scrape extracts structured data from a page using CSS selectors.
func (d *PlaywrightDriver) Scrape(ctx context.Context, url string, selectors []string) (map[string]string, error) {
	d.mu.Lock()
	defer d.mu.Unlock()
	d.requestCount++

	page, err := d.newPage(nil)
	if err != nil {
		d.errorCount++
		return nil, err
	}
	defer page.Close()

	if _, err := page.Goto(url, playwright.PageGotoOptions{
		WaitUntil: playwright.WaitUntilStateNetworkidle,
		Timeout:   playwright.Float(float64(d.timeout.Milliseconds())),
	}); err != nil {
		d.errorCount++
		return nil, fmt.Errorf("navigation failed: %w", err)
	}

	if d.detectCaptcha(page) {
		d.captchaCount++
		return nil, fmt.Errorf("CAPTCHA detected")
	}

	results := make(map[string]string)
	for _, selector := range selectors {
		elements, err := page.QuerySelectorAll(selector)
		if err != nil {
			results[selector] = ""
			continue
		}

		var texts []string
		for _, el := range elements {
			text, err := el.TextContent()
			if err == nil && text != "" {
				texts = append(texts, strings.TrimSpace(text))
			}
		}
		results[selector] = strings.Join(texts, " | ")
	}

	return results, nil
}

// ScrapeMultiple scrapes multiple URLs concurrently.
func (d *PlaywrightDriver) ScrapeMultiple(ctx context.Context, urls []string) ([]map[string]string, error) {
	results := make([]map[string]string, len(urls))
	var wg sync.WaitGroup

	for i, url := range urls {
		wg.Add(1)
		go func(idx int, u string) {
			defer wg.Done()
			data, err := d.Scrape(ctx, u, []string{"h1", "h2", "p", "article"})
			if err != nil {
				results[idx] = map[string]string{"error": err.Error()}
			} else {
				results[idx] = data
			}
		}(i, url)
	}

	wg.Wait()
	return results, nil
}

// Search performs a web search and returns structured results.
func (d *PlaywrightDriver) Search(ctx context.Context, query string, engine string) ([]SearchResult, error) {
	d.mu.Lock()
	defer d.mu.Unlock()
	d.requestCount++

	page, err := d.newPage(nil)
	if err != nil {
		d.errorCount++
		return nil, err
	}
	defer page.Close()

	// Use DuckDuckGo (no CAPTCHA, no login required)
	searchURL := fmt.Sprintf("https://html.duckduckgo.com/html/?q=%s", strings.ReplaceAll(query, " ", "+"))

	if _, err := page.Goto(searchURL, playwright.PageGotoOptions{
		WaitUntil: playwright.WaitUntilStateNetworkidle,
		Timeout:   playwright.Float(float64(d.timeout.Milliseconds())),
	}); err != nil {
		d.errorCount++
		return nil, fmt.Errorf("search navigation failed: %w", err)
	}

	// Extract results from DuckDuckGo HTML
	resultElements, err := page.QuerySelectorAll(".result")
	if err != nil {
		return nil, fmt.Errorf("failed to query results: %w", err)
	}

	var results []SearchResult
	for i, el := range resultElements {
		if i >= 10 {
			break // Top 10 results
		}

		titleEl, _ := el.QuerySelector(".result__a")
		snippetEl, _ := el.QuerySelector(".result__snippet")

		title := ""
		url := ""
		snippet := ""

		if titleEl != nil {
			title, _ = titleEl.TextContent()
			url, _ = titleEl.GetAttribute("href")
		}
		if snippetEl != nil {
			snippet, _ = snippetEl.TextContent()
		}

		if title != "" {
			results = append(results, SearchResult{
				Title:   strings.TrimSpace(title),
				URL:     url,
				Snippet: strings.TrimSpace(snippet),
				Score:   1.0 - float64(i)*0.1,
			})
		}
	}

	d.logger.Infof("Search '%s': %d results", query, len(results))
	return results, nil
}

// BrowserNavigate navigates the active page to a URL.
func (d *PlaywrightDriver) BrowserNavigate(ctx context.Context, url string) error {
	d.mu.Lock()
	defer d.mu.Unlock()

	page, err := d.newPage(nil)
	if err != nil {
		return err
	}

	_, err = page.Goto(url, playwright.PageGotoOptions{
		WaitUntil: playwright.WaitUntilStateNetworkidle,
	})
	return err
}

// BrowserExecuteJS runs JavaScript on the current page.
func (d *PlaywrightDriver) BrowserExecuteJS(ctx context.Context, script string) (string, error) {
	d.mu.Lock()
	defer d.mu.Unlock()

	page, err := d.newPage(nil)
	if err != nil {
		return "", err
	}
	defer page.Close()

	result, err := page.Evaluate(script)
	if err != nil {
		return "", err
	}

	resultJSON, _ := json.Marshal(result)
	return string(resultJSON), nil
}

// BrowserScreenshot captures a screenshot of the current page.
func (d *PlaywrightDriver) BrowserScreenshot(ctx context.Context) ([]byte, error) {
	d.mu.Lock()
	defer d.mu.Unlock()

	page, err := d.newPage(nil)
	if err != nil {
		return nil, err
	}
	defer page.Close()

	return page.Screenshot(playwright.PageScreenshotOptions{
		FullPage: playwright.Bool(true),
	})
}

// BrowserClose shuts down the browser instance.
func (d *PlaywrightDriver) BrowserClose(ctx context.Context) error {
	d.mu.Lock()
	defer d.mu.Unlock()

	d.active = false
	if d.browser != nil {
		d.browser.Close()
	}
	if d.pw != nil {
		d.pw.Stop()
	}

	d.logger.Info("Playwright web driver shut down")
	return nil
}

// ═══════════════════════════════════════════════════════════════
// SPECIALIZED METHODS
// ═══════════════════════════════════════════════════════════════

// ScrapeHeadlines scrapes news headlines and returns structured articles.
func (d *PlaywrightDriver) ScrapeHeadlines(ctx context.Context, source string) ([]ScrapedArticle, error) {
	d.mu.Lock()
	defer d.mu.Unlock()
	d.requestCount++

	page, err := d.newPage(nil)
	if err != nil {
		return nil, err
	}
	defer page.Close()

	// Source URL mapping
	sourceURLs := map[string]string{
		"reuters": "https://www.reuters.com/",
		"bbc":     "https://www.bbc.com/news",
		"hn":      "https://news.ycombinator.com/",
	}

	url, ok := sourceURLs[source]
	if !ok {
		url = source // Treat as direct URL
	}

	if _, err := page.Goto(url, playwright.PageGotoOptions{
		WaitUntil: playwright.WaitUntilStateNetworkidle,
		Timeout:   playwright.Float(float64(d.timeout.Milliseconds())),
	}); err != nil {
		return nil, fmt.Errorf("failed to load %s: %w", source, err)
	}

	if d.detectCaptcha(page) {
		d.captchaCount++
		return nil, fmt.Errorf("CAPTCHA on %s", source)
	}

	// Extract headlines using common article selectors
	selectors := []string{
		"article h3",
		"article h2",
		".story-card h3",
		".titleline a",
		"[data-testid='card-headline']",
		".gs-c-promo-heading__title",
	}

	var articles []ScrapedArticle

	for _, selector := range selectors {
		elements, err := page.QuerySelectorAll(selector)
		if err != nil || len(elements) == 0 {
			continue
		}

		for _, el := range elements {
			text, _ := el.TextContent()
			text = strings.TrimSpace(text)
			if text == "" || len(text) < 10 {
				continue
			}

			// Try to get link
			link := ""
			anchor, _ := el.QuerySelector("a")
			if anchor != nil {
				link, _ = anchor.GetAttribute("href")
			} else {
				// Check if element itself is a link
				link, _ = el.GetAttribute("href")
			}

			// Make relative URLs absolute
			if link != "" && !strings.HasPrefix(link, "http") {
				link = url + link
			}

			articles = append(articles, ScrapedArticle{
				Headline:  text,
				Source:    source,
				URL:       link,
				ScrapedAt: time.Now(),
			})
		}

		if len(articles) > 0 {
			break // Found articles with this selector
		}
	}

	d.logger.Infof("Scraped %d headlines from %s", len(articles), source)
	return articles, nil
}

// GetMetrics returns web driver metrics.
func (d *PlaywrightDriver) GetMetrics() map[string]interface{} {
	return map[string]interface{}{
		"active":        d.active,
		"requests":      d.requestCount,
		"errors":        d.errorCount,
		"captchas":      d.captchaCount,
		"success_rate":  float64(d.requestCount-d.errorCount) / float64(max64(1, d.requestCount)),
	}
}

// ═══════════════════════════════════════════════════════════════
// PRIVATE HELPERS
// ═══════════════════════════════════════════════════════════════

func (d *PlaywrightDriver) newPage(headers map[string]string) (playwright.Page, error) {
	if !d.active {
		return nil, fmt.Errorf("browser not active")
	}

	ctx, err := d.browser.NewContext(playwright.BrowserNewContextOptions{
		UserAgent: playwright.String(d.userAgent),
	})
	if err != nil {
		return nil, fmt.Errorf("failed to create context: %w", err)
	}

	page, err := ctx.NewPage()
	if err != nil {
		return nil, fmt.Errorf("failed to create page: %w", err)
	}

	// Set extra headers if provided
	if headers != nil {
		page.SetExtraHTTPHeaders(headers)
	}

	return page, nil
}

func (d *PlaywrightDriver) detectCaptcha(page playwright.Page) bool {
	// Common CAPTCHA indicators
	captchaSelectors := []string{
		"iframe[src*='captcha']",
		"iframe[src*='recaptcha']",
		"#captcha",
		".g-recaptcha",
		"[data-sitekey]",
		"#challenge-form",
		".cf-turnstile",
	}

	for _, selector := range captchaSelectors {
		el, _ := page.QuerySelector(selector)
		if el != nil {
			d.logger.Warnf("CAPTCHA detected via selector: %s", selector)
			return true
		}
	}

	// Check page title for challenge pages
	title, _ := page.Title()
	lowerTitle := strings.ToLower(title)
	if strings.Contains(lowerTitle, "captcha") ||
		strings.Contains(lowerTitle, "verify") ||
		strings.Contains(lowerTitle, "challenge") {
		return true
	}

	return false
}

func max64(a, b uint64) uint64 {
	if a > b {
		return a
	}
	return b
}
