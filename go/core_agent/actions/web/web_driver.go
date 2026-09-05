// Package web implements the WebHandler interface using Playwright for
// headless browser automation — Ultron's eyes on the internet.
package web

import (
	"context"
	"encoding/json"
	"fmt"
	"regexp"
	"strings"
	"sync"
	"time"
	"unicode/utf8"

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

// BrowseResult holds the result of a full browser action.
type BrowseResult struct {
	URL        string            `json:"url"`
	Title      string            `json:"title"`
	Content    string            `json:"content"`   // plain text
	HTML       string            `json:"html"`      // raw HTML (truncated)
	StatusCode int               `json:"status_code"`
	Links      []string          `json:"links"`
	Meta       map[string]string `json:"meta"`
	Error      string            `json:"error,omitempty"`
}

// PlaywrightDriver implements WebHandler using a headless Chromium browser.
type PlaywrightDriver struct {
	mu sync.Mutex

	logger  *zap.SugaredLogger
	pw      *playwright.Playwright
	browser playwright.Browser
	active  bool

	// Persistent context (preserves cookies/sessions across requests)
	ctx playwright.BrowserContext

	// Configuration
	headless   bool
	timeout    time.Duration
	userAgent  string
	maxRetries int

	// Metrics
	requestCount uint64
	errorCount   uint64
	captchaCount uint64
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
		Args: []string{
			"--no-sandbox",
			"--disable-blink-features=AutomationControlled",
			"--disable-infobars",
		},
	})
	if err != nil {
		return fmt.Errorf("failed to launch browser: %w", err)
	}
	d.browser = browser

	// Create a persistent context that stores cookies/sessions
	ctx, err := browser.NewContext(playwright.BrowserNewContextOptions{
		UserAgent: playwright.String(d.userAgent),
		Viewport: &playwright.Size{Width: 1280, Height: 800},
	})
	if err != nil {
		return fmt.Errorf("failed to create browser context: %w", err)
	}
	d.ctx = ctx
	d.active = true

	d.logger.Info("Playwright web driver initialized (headless Chromium, persistent session)")
	return nil
}

// ═══════════════════════════════════════════════════════════════
// CORE PAGE FACTORY
// ═══════════════════════════════════════════════════════════════

func (d *PlaywrightDriver) newPage(headers map[string]string) (playwright.Page, error) {
	page, err := d.ctx.NewPage()
	if err != nil {
		return nil, fmt.Errorf("failed to create page: %w", err)
	}
	if len(headers) > 0 {
		if err := page.SetExtraHTTPHeaders(headers); err != nil {
			page.Close()
			return nil, fmt.Errorf("failed to set headers: %w", err)
		}
	}
	return page, nil
}

// ═══════════════════════════════════════════════════════════════
// NAVIGATE — load a URL and return full content
// ═══════════════════════════════════════════════════════════════

// Get performs an HTTP GET via the browser and returns the page content.
func (d *PlaywrightDriver) Get(ctx context.Context, url string, headers map[string]string) ([]byte, int, error) {
	result, err := d.Browse(ctx, url)
	if err != nil {
		return nil, 0, err
	}
	return []byte(result.Content), result.StatusCode, nil
}

// Browse navigates to a URL and returns a structured BrowseResult with
// plain text, links, title, and meta tags — what a human would read.
func (d *PlaywrightDriver) Browse(ctx context.Context, url string) (*BrowseResult, error) {
	if url == "" {
		return nil, fmt.Errorf("url cannot be empty")
	}
	d.mu.Lock()
	defer d.mu.Unlock()
	d.requestCount++

	page, err := d.newPage(nil)
	if err != nil {
		d.errorCount++
		return nil, err
	}
	defer page.Close()

	resp, err := page.Goto(url, playwright.PageGotoOptions{
		WaitUntil: playwright.WaitUntilStateDomcontentloaded,
		Timeout:   playwright.Float(float64(d.timeout.Milliseconds())),
	})
	if err != nil {
		d.errorCount++
		return &BrowseResult{URL: url, Error: err.Error()}, nil
	}

	statusCode := 200
	if resp != nil {
		statusCode = resp.Status()
	}

	// Get title
	title, _ := page.Title()

	// Extract plain text via JS
	textContent, _ := page.Evaluate(`() => {
		// Remove script/style/nav/footer elements
		['script','style','nav','footer','aside','noscript'].forEach(t =>
			document.querySelectorAll(t).forEach(e => e.remove())
		);
		return document.body ? document.body.innerText : document.documentElement.innerText;
	}`)
	text := ""
	if textContent != nil {
		text = fmt.Sprintf("%v", textContent)
	}

	// Extract all links
	linksRaw, _ := page.Evaluate(`() => {
		return Array.from(document.querySelectorAll('a[href]'))
			.map(a => a.href)
			.filter(h => h.startsWith('http'))
			.slice(0, 50);
	}`)
	var links []string
	if linksRaw != nil {
		if arr, ok := linksRaw.([]interface{}); ok {
			for _, l := range arr {
				links = append(links, fmt.Sprintf("%v", l))
			}
		}
	}

	// Extract meta tags
	meta := map[string]string{}
	metaRaw, _ := page.Evaluate(`() => {
		const m = {};
		document.querySelectorAll('meta[name],meta[property]').forEach(el => {
			const k = el.getAttribute('name') || el.getAttribute('property');
			const v = el.getAttribute('content');
			if (k && v) m[k] = v;
		});
		return m;
	}`)
	if metaRaw != nil {
		if mm, ok := metaRaw.(map[string]interface{}); ok {
			for k, v := range mm {
				meta[k] = fmt.Sprintf("%v", v)
			}
		}
	}

	// Truncate text to reasonable length
	if len(text) > 8000 {
		text = text[:8000] + "\n...[truncated]"
	}

	return &BrowseResult{
		URL:        url,
		Title:      title,
		Content:    text,
		StatusCode: statusCode,
		Links:      links,
		Meta:       meta,
	}, nil
}

// ═══════════════════════════════════════════════════════════════
// SEARCH — real web search results (DuckDuckGo HTML, no API key)
// ═══════════════════════════════════════════════════════════════

// Search performs a real web search and returns ranked results.
func (d *PlaywrightDriver) Search(ctx context.Context, query string, engine string) ([]SearchResult, error) {
	if query == "" {
		return nil, fmt.Errorf("query cannot be empty")
	}
	d.mu.Lock()
	defer d.mu.Unlock()

	page, err := d.newPage(nil)
	if err != nil {
		return nil, err
	}
	defer page.Close()

	// Build search URL — DuckDuckGo HTML (no JS needed, privacy-friendly)
	searchURL := fmt.Sprintf("https://html.duckduckgo.com/html/?q=%s", strings.ReplaceAll(query, " ", "+"))
	if engine == "google" {
		searchURL = fmt.Sprintf("https://www.google.com/search?q=%s&num=10", strings.ReplaceAll(query, " ", "+"))
	} else if engine == "bing" {
		searchURL = fmt.Sprintf("https://www.bing.com/search?q=%s", strings.ReplaceAll(query, " ", "+"))
	}

	_, err = page.Goto(searchURL, playwright.PageGotoOptions{
		WaitUntil: playwright.WaitUntilStateDomcontentloaded,
		Timeout:   playwright.Float(20000),
	})
	if err != nil {
		return nil, fmt.Errorf("search navigation failed: %w", err)
	}

	// Extract results via JS — works for DuckDuckGo HTML and Google
	resultsRaw, err := page.Evaluate(`() => {
		const results = [];
		// DuckDuckGo HTML selectors
		const ddgResults = document.querySelectorAll('.result');
		if (ddgResults.length > 0) {
			ddgResults.forEach((r, i) => {
				if (i >= 10) return;
				const titleEl = r.querySelector('.result__title a');
				const snippetEl = r.querySelector('.result__snippet');
				const urlEl = r.querySelector('.result__url');
				if (titleEl) results.push({
					title: titleEl.textContent.trim(),
					url: titleEl.href || (urlEl ? urlEl.textContent.trim() : ''),
					snippet: snippetEl ? snippetEl.textContent.trim() : '',
					rank: i + 1
				});
			});
		}
		// Google selectors (fallback)
		if (results.length === 0) {
			document.querySelectorAll('div.g').forEach((r, i) => {
				if (i >= 10) return;
				const titleEl = r.querySelector('h3');
				const snippetEl = r.querySelector('.VwiC3b, .IsZvec, span[data-sncf]');
				const linkEl = r.querySelector('a');
				if (titleEl && linkEl) results.push({
					title: titleEl.textContent.trim(),
					url: linkEl.href,
					snippet: snippetEl ? snippetEl.textContent.trim() : '',
					rank: i + 1
				});
			});
		}
		return results;
	}`)
	if err != nil {
		return nil, fmt.Errorf("failed to extract results: %w", err)
	}

	var searchResults []SearchResult
	if arr, ok := resultsRaw.([]interface{}); ok {
		for _, item := range arr {
			if m, ok := item.(map[string]interface{}); ok {
				r := SearchResult{
					Title:   fmt.Sprintf("%v", m["title"]),
					URL:     fmt.Sprintf("%v", m["url"]),
					Snippet: fmt.Sprintf("%v", m["snippet"]),
				}
				if rank, ok := m["rank"].(float64); ok {
					r.Rank = int(rank)
				}
				searchResults = append(searchResults, r)
			}
		}
	}

	return searchResults, nil
}

// ═══════════════════════════════════════════════════════════════
// CLICK — click any element by CSS selector or text
// ═══════════════════════════════════════════════════════════════

// Click clicks an element on the current page (uses a persistent page).
func (d *PlaywrightDriver) Click(ctx context.Context, url string, selector string) (*BrowseResult, error) {
	d.mu.Lock()
	defer d.mu.Unlock()

	page, err := d.newPage(nil)
	if err != nil {
		return nil, err
	}
	defer page.Close()

	if _, err := page.Goto(url, playwright.PageGotoOptions{
		WaitUntil: playwright.WaitUntilStateDomcontentloaded,
		Timeout:   playwright.Float(float64(d.timeout.Milliseconds())),
	}); err != nil {
		return nil, err
	}

	// Try CSS selector first, then text content
	if err := page.Click(selector, playwright.PageClickOptions{
		Timeout: playwright.Float(5000),
	}); err != nil {
		// Try as text
		textSelector := fmt.Sprintf("text=%s", selector)
		if err2 := page.Click(textSelector, playwright.PageClickOptions{
			Timeout: playwright.Float(5000),
		}); err2 != nil {
			return nil, fmt.Errorf("click failed — selector '%s' not found: %v", selector, err)
		}
	}

	// Wait for any navigation
	page.WaitForLoadState(playwright.PageWaitForLoadStateOptions{
		State:   playwright.LoadStateDomcontentloaded,
		Timeout: playwright.Float(5000),
	})

	title, _ := page.Title()
	currentURL := page.URL()
	textContent, _ := page.Evaluate(`() => document.body ? document.body.innerText.slice(0,4000) : ''`)
	text := fmt.Sprintf("%v", textContent)

	return &BrowseResult{URL: currentURL, Title: title, Content: text, StatusCode: 200}, nil
}

// ═══════════════════════════════════════════════════════════════
// FILL FORM — type into input fields and optionally submit
// ═══════════════════════════════════════════════════════════════

// FillForm navigates to a URL, fills inputs, and optionally submits.
func (d *PlaywrightDriver) FillForm(ctx context.Context, url string, fields map[string]string, submit bool) (*BrowseResult, error) {
	d.mu.Lock()
	defer d.mu.Unlock()

	page, err := d.newPage(nil)
	if err != nil {
		return nil, err
	}
	defer page.Close()

	if _, err := page.Goto(url, playwright.PageGotoOptions{
		WaitUntil: playwright.WaitUntilStateDomcontentloaded,
		Timeout:   playwright.Float(float64(d.timeout.Milliseconds())),
	}); err != nil {
		return nil, err
	}

	// Fill each field
	for selector, value := range fields {
		if err := page.Fill(selector, value, playwright.PageFillOptions{
			Timeout: playwright.Float(5000),
		}); err != nil {
			// Try by placeholder or label
			altSelector := fmt.Sprintf("[placeholder*='%s'],[aria-label*='%s']", selector, selector)
			if err2 := page.Fill(altSelector, value, playwright.PageFillOptions{
				Timeout: playwright.Float(3000),
			}); err2 != nil {
				d.logger.Warnf("Could not fill field '%s': %v", selector, err)
			}
		}
	}

	if submit {
		// Try submit button, then Enter key
		if err := page.Click("[type='submit'],button[type='submit'],input[type='submit']", playwright.PageClickOptions{
			Timeout: playwright.Float(3000),
		}); err != nil {
			page.Keyboard().Press("Enter")
		}
		page.WaitForLoadState(playwright.PageWaitForLoadStateOptions{
			State:   playwright.LoadStateDomcontentloaded,
			Timeout: playwright.Float(8000),
		})
	}

	title, _ := page.Title()
	currentURL := page.URL()
	textContent, _ := page.Evaluate(`() => document.body ? document.body.innerText.slice(0,4000) : ''`)
	text := fmt.Sprintf("%v", textContent)

	return &BrowseResult{URL: currentURL, Title: title, Content: text, StatusCode: 200}, nil
}

// ═══════════════════════════════════════════════════════════════
// SCROLL — scroll and get more content
// ═══════════════════════════════════════════════════════════════

// Scroll loads a page, scrolls to bottom (loads lazy content), returns all text.
func (d *PlaywrightDriver) Scroll(ctx context.Context, url string, scrolls int) (*BrowseResult, error) {
	d.mu.Lock()
	defer d.mu.Unlock()

	page, err := d.newPage(nil)
	if err != nil {
		return nil, err
	}
	defer page.Close()

	if _, err := page.Goto(url, playwright.PageGotoOptions{
		WaitUntil: playwright.WaitUntilStateDomcontentloaded,
		Timeout:   playwright.Float(float64(d.timeout.Milliseconds())),
	}); err != nil {
		return nil, err
	}

	if scrolls <= 0 {
		scrolls = 3
	}
	for i := 0; i < scrolls; i++ {
		page.Evaluate(`() => window.scrollBy(0, window.innerHeight)`)
		page.WaitForTimeout(500)
	}

	title, _ := page.Title()
	textContent, _ := page.Evaluate(`() => {
		['script','style','nav','footer','aside'].forEach(t =>
			document.querySelectorAll(t).forEach(e => e.remove())
		);
		return document.body ? document.body.innerText.slice(0, 10000) : '';
	}`)
	text := fmt.Sprintf("%v", textContent)

	return &BrowseResult{URL: url, Title: title, Content: text, StatusCode: 200}, nil
}

// ═══════════════════════════════════════════════════════════════
// EVALUATE JS — run arbitrary JavaScript on a page
// ═══════════════════════════════════════════════════════════════

// EvaluateJS loads a URL and runs JavaScript, returning the result.
func (d *PlaywrightDriver) EvaluateJS(ctx context.Context, url string, script string) (interface{}, error) {
	d.mu.Lock()
	defer d.mu.Unlock()

	page, err := d.newPage(nil)
	if err != nil {
		return nil, err
	}
	defer page.Close()

	if url != "" {
		if _, err := page.Goto(url, playwright.PageGotoOptions{
			WaitUntil: playwright.WaitUntilStateDomcontentloaded,
			Timeout:   playwright.Float(float64(d.timeout.Milliseconds())),
		}); err != nil {
			return nil, err
		}
	}

	result, err := page.Evaluate(script)
	if err != nil {
		return nil, fmt.Errorf("JS evaluation failed: %w", err)
	}
	return result, nil
}

// ═══════════════════════════════════════════════════════════════
// SCREENSHOT — take a screenshot of a page
// ═══════════════════════════════════════════════════════════════

// ScreenshotURL navigates to a URL and takes a screenshot, saving to path.
func (d *PlaywrightDriver) ScreenshotURL(ctx context.Context, url string, path string) error {
	d.mu.Lock()
	defer d.mu.Unlock()

	page, err := d.newPage(nil)
	if err != nil {
		return err
	}
	defer page.Close()

	if _, err := page.Goto(url, playwright.PageGotoOptions{
		WaitUntil: playwright.WaitUntilStateDomcontentloaded,
		Timeout:   playwright.Float(float64(d.timeout.Milliseconds())),
	}); err != nil {
		return err
	}

	_, err = page.Screenshot(playwright.PageScreenshotOptions{
		Path:     playwright.String(path),
		FullPage: playwright.Bool(false),
	})
	return err
}

// ═══════════════════════════════════════════════════════════════
// WAIT FOR ELEMENT — wait until selector appears
// ═══════════════════════════════════════════════════════════════

// WaitForSelector waits for a CSS selector to appear on the page.
func (d *PlaywrightDriver) WaitForSelector(page playwright.Page, selector string, timeout float64) error {
	if timeout <= 0 {
		timeout = 10000
	}
	_, err := page.WaitForSelector(selector, playwright.PageWaitForSelectorOptions{
		Timeout: playwright.Float(timeout),
	})
	return err
}

// ═══════════════════════════════════════════════════════════════
// EXECUTE — OODA action dispatch (ActionRequest → BrowseResult)
// ═══════════════════════════════════════════════════════════════

// Execute routes an ActionRequest to the appropriate browser method.
// This wires PlaywrightDriver into the OODA loop via ActionInterface.
func (d *PlaywrightDriver) Execute(ctx context.Context, req *actions.ActionRequest) (*actions.ActionResponse, error) {
	start := time.Now()

	if req == nil {
		return nil, fmt.Errorf("nil action request")
	}

	var resultData interface{}
	var execErr error

	switch req.Operation {
	case "browse", "get", "fetch", "navigate":
		result, err := d.Browse(ctx, req.Target)
		execErr = err
		if result != nil {
			resultData = result
		}

	case "search":
		query := req.Target
		if q, ok := req.Parameters["query"].(string); ok && q != "" {
			query = q
		}
		engine := "duckduckgo"
		if e, ok := req.Parameters["engine"].(string); ok {
			engine = e
		}
		results, err := d.Search(ctx, query, engine)
		execErr = err
		resultData = results

	case "click":
		selector := ""
		if s, ok := req.Parameters["selector"].(string); ok {
			selector = s
		}
		result, err := d.Click(ctx, req.Target, selector)
		execErr = err
		resultData = result

	case "fill", "form":
		fields := map[string]string{}
		if f, ok := req.Parameters["fields"].(map[string]interface{}); ok {
			for k, v := range f {
				fields[k] = fmt.Sprintf("%v", v)
			}
		}
		submit := false
		if s, ok := req.Parameters["submit"].(bool); ok {
			submit = s
		}
		result, err := d.FillForm(ctx, req.Target, fields, submit)
		execErr = err
		resultData = result

	case "scroll":
		scrolls := 3
		if s, ok := req.Parameters["scrolls"].(float64); ok {
			scrolls = int(s)
		}
		result, err := d.Scroll(ctx, req.Target, scrolls)
		execErr = err
		resultData = result

	case "js", "eval", "javascript":
		script := ""
		if s, ok := req.Parameters["script"].(string); ok {
			script = s
		}
		result, err := d.EvaluateJS(ctx, req.Target, script)
		execErr = err
		resultData = result

	case "screenshot":
		path := "/tmp/ultron_screenshot.png"
		if p, ok := req.Parameters["path"].(string); ok {
			path = p
		}
		err := d.ScreenshotURL(ctx, req.Target, path)
		execErr = err
		if err == nil {
			resultData = map[string]string{"path": path, "url": req.Target}
		}

	default:
		// Default: browse the URL
		result, err := d.Browse(ctx, req.Target)
		execErr = err
		resultData = result
	}

	duration := time.Since(start)
	success := execErr == nil

	resp := &actions.ActionResponse{
		RequestID:  req.RequestID,
		Success:    success,
		Data:       resultData,
		Duration:   duration,
		Reversible: false,
	}
	if execErr != nil {
		resp.Error = execErr
	}

	return resp, nil
}

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

// detectCaptcha checks if the page is showing a CAPTCHA.
func (d *PlaywrightDriver) detectCaptcha(page playwright.Page) bool {
	content, err := page.Content()
	if err != nil {
		return false
	}
	captchaSignals := []string{
		"captcha", "CAPTCHA", "recaptcha", "hCaptcha",
		"challenge-form", "cf-challenge", "verify you are human",
		"bot detection", "security check",
	}
	lower := strings.ToLower(content)
	for _, signal := range captchaSignals {
		if strings.Contains(lower, strings.ToLower(signal)) {
			return true
		}
	}
	return false
}

// stripHTML removes HTML tags and returns plain text.
func stripHTML(html string) string {
	re := regexp.MustCompile(`<[^>]+>`)
	text := re.ReplaceAllString(html, " ")
	text = strings.Join(strings.Fields(text), " ")
	if !utf8.ValidString(text) {
		text = strings.ToValidUTF8(text, "")
	}
	return text
}

// ToJSON serialises any value to a compact JSON string.
func ToJSON(v interface{}) string {
	b, err := json.Marshal(v)
	if err != nil {
		return fmt.Sprintf("%v", v)
	}
	return string(b)
}

// Close shuts down the browser cleanly.
func (d *PlaywrightDriver) Close() {
	d.mu.Lock()
	defer d.mu.Unlock()
	if d.ctx != nil {
		d.ctx.Close()
	}
	if d.browser != nil {
		d.browser.Close()
	}
	if d.pw != nil {
		d.pw.Stop()
	}
	d.active = false
}

// Stats returns driver metrics.
func (d *PlaywrightDriver) Stats() map[string]interface{} {
	d.mu.Lock()
	defer d.mu.Unlock()
	return map[string]interface{}{
		"active":        d.active,
		"requests":      d.requestCount,
		"errors":        d.errorCount,
		"captchas":      d.captchaCount,
		"headless":      d.headless,
		"user_agent":    d.userAgent,
	}
}
