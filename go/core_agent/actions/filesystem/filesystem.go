// Package filesystem provides file system operations for Ultron.
//
// This gives the agent the ability to:
//   - Read files from the project and system
//   - Write files (with backup)
//   - Watch directories for changes
//   - List and search files
//   - Manage the .ultron data directory
//
// All operations are audited and respect the ownership guard.
package filesystem

import (
	"context"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"go.uber.org/zap"
)

// FilesystemDriver implements the FilesystemHandler interface.
type FilesystemDriver struct {
	mu sync.RWMutex

	projectRoot string
	logger      *zap.SugaredLogger

	// Safety
	allowedPaths  []string  // Paths the agent is allowed to access
	blockedPaths  []string  // Paths that are always blocked
	readOnly      bool      // If true, no writes allowed

	// Watch state
	watchers map[string]chan interface{}

	// Metrics
	reads   int64
	writes  int64
	deletes int64
}

// FileInfo represents information about a file.
type FileInfo struct {
	Name    string    `json:"name"`
	Path    string    `json:"path"`
	Size    int64     `json:"size"`
	IsDir   bool      `json:"is_dir"`
	ModTime time.Time `json:"mod_time"`
	Mode    string    `json:"mode"`
}

// FileEvent represents a filesystem change.
type FileEvent struct {
	Type      string    `json:"type"` // created, modified, deleted
	Path      string    `json:"path"`
	Timestamp time.Time `json:"timestamp"`
}

// NewFilesystemDriver creates the filesystem action handler.
func NewFilesystemDriver(projectRoot string, logger *zap.SugaredLogger) *FilesystemDriver {
	return &FilesystemDriver{
		projectRoot: projectRoot,
		logger:      logger,
		allowedPaths: []string{
			projectRoot,
			filepath.Join(projectRoot, ".ultron"),
			filepath.Join(projectRoot, "data"),
			"/tmp",
		},
		blockedPaths: []string{
			filepath.Join(projectRoot, ".git"),
			filepath.Join(projectRoot, ".env"),
			filepath.Join(projectRoot, "genesis.json"),
		},
		watchers: make(map[string]chan interface{}),
	}
}

// Read reads the content of a file.
func (fd *FilesystemDriver) Read(ctx context.Context, path string) ([]byte, error) {
	fullPath := fd.resolvePath(path)
	if err := fd.checkAccess(fullPath, false); err != nil {
		return nil, err
	}

	fd.mu.Lock()
	fd.reads++
	fd.mu.Unlock()

	return os.ReadFile(fullPath)
}

// Write writes content to a file, creating directories as needed.
func (fd *FilesystemDriver) Write(ctx context.Context, path string, data []byte) error {
	if fd.readOnly {
		return fmt.Errorf("filesystem is in read-only mode")
	}

	fullPath := fd.resolvePath(path)
	if err := fd.checkAccess(fullPath, true); err != nil {
		return err
	}

	// Create parent directory
	if err := os.MkdirAll(filepath.Dir(fullPath), 0755); err != nil {
		return err
	}

	// Backup existing file
	if _, err := os.Stat(fullPath); err == nil {
		backupPath := fullPath + ".bak"
		os.Rename(fullPath, backupPath)
	}

	fd.mu.Lock()
	fd.writes++
	fd.mu.Unlock()

	err := os.WriteFile(fullPath, data, 0644)
	if err != nil {
		return err
	}

	// Notify watchers
	dir := filepath.Dir(fullPath)
	fd.mu.RLock()
	if ch, exists := fd.watchers[dir]; exists {
		select {
		case ch <- FileEvent{Type: "modified", Path: fullPath, Timestamp: time.Now()}:
		default:
		}
	}
	fd.mu.RUnlock()

	return nil
}

// List returns files in a directory.
func (fd *FilesystemDriver) List(ctx context.Context, path string) ([]interface{}, error) {
	fullPath := fd.resolvePath(path)
	if err := fd.checkAccess(fullPath, false); err != nil {
		return nil, err
	}

	entries, err := os.ReadDir(fullPath)
	if err != nil {
		return nil, err
	}

	results := make([]interface{}, 0, len(entries))
	for _, entry := range entries {
		info, err := entry.Info()
		if err != nil {
			continue
		}
		results = append(results, FileInfo{
			Name:    entry.Name(),
			Path:    filepath.Join(fullPath, entry.Name()),
			Size:    info.Size(),
			IsDir:   entry.IsDir(),
			ModTime: info.ModTime(),
			Mode:    info.Mode().String(),
		})
	}

	return results, nil
}

// Delete removes a file (with safety checks).
func (fd *FilesystemDriver) Delete(ctx context.Context, path string) error {
	if fd.readOnly {
		return fmt.Errorf("filesystem is in read-only mode")
	}

	fullPath := fd.resolvePath(path)
	if err := fd.checkAccess(fullPath, true); err != nil {
		return err
	}

	// Never delete directories recursively
	info, err := os.Stat(fullPath)
	if err != nil {
		return err
	}
	if info.IsDir() {
		return fmt.Errorf("cannot delete directories (safety constraint)")
	}

	fd.mu.Lock()
	fd.deletes++
	fd.mu.Unlock()

	return os.Remove(fullPath)
}

// Watch starts monitoring a directory for changes.
func (fd *FilesystemDriver) Watch(ctx context.Context, path string) (<-chan interface{}, error) {
	fullPath := fd.resolvePath(path)
	if err := fd.checkAccess(fullPath, false); err != nil {
		return nil, err
	}

	ch := make(chan interface{}, 100)

	fd.mu.Lock()
	fd.watchers[fullPath] = ch
	fd.mu.Unlock()

	// Start polling-based watcher
	go fd.pollWatch(ctx, fullPath, ch)

	return ch, nil
}

// Search finds files matching a pattern.
func (fd *FilesystemDriver) Search(ctx context.Context, rootPath string, pattern string) ([]FileInfo, error) {
	fullPath := fd.resolvePath(rootPath)
	if err := fd.checkAccess(fullPath, false); err != nil {
		return nil, err
	}

	results := make([]FileInfo, 0)
	filepath.WalkDir(fullPath, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return nil
		}
		if ctx.Err() != nil {
			return ctx.Err()
		}

		matched, _ := filepath.Match(pattern, d.Name())
		if matched || strings.Contains(d.Name(), pattern) {
			info, _ := d.Info()
			if info != nil {
				results = append(results, FileInfo{
					Name:    d.Name(),
					Path:    path,
					Size:    info.Size(),
					IsDir:   d.IsDir(),
					ModTime: info.ModTime(),
					Mode:    info.Mode().String(),
				})
			}
		}
		return nil
	})

	return results, nil
}

// Stats returns filesystem driver metrics.
func (fd *FilesystemDriver) Stats() map[string]interface{} {
	fd.mu.RLock()
	defer fd.mu.RUnlock()

	return map[string]interface{}{
		"reads":        fd.reads,
		"writes":       fd.writes,
		"deletes":      fd.deletes,
		"watchers":     len(fd.watchers),
		"project_root": fd.projectRoot,
		"read_only":    fd.readOnly,
	}
}

// ═══════════════════════════════════════════════════════════════
// SAFETY — Access control
// ═══════════════════════════════════════════════════════════════

func (fd *FilesystemDriver) resolvePath(path string) string {
	if filepath.IsAbs(path) {
		return filepath.Clean(path)
	}
	return filepath.Join(fd.projectRoot, filepath.Clean(path))
}

func (fd *FilesystemDriver) checkAccess(path string, write bool) error {
	// Check blocked paths
	for _, blocked := range fd.blockedPaths {
		if strings.HasPrefix(path, blocked) {
			return fmt.Errorf("access denied: %s is protected", path)
		}
	}

	// Check allowed paths
	allowed := false
	for _, allowedPath := range fd.allowedPaths {
		if strings.HasPrefix(path, allowedPath) {
			allowed = true
			break
		}
	}

	if !allowed {
		return fmt.Errorf("access denied: %s is outside allowed paths", path)
	}

	return nil
}

func (fd *FilesystemDriver) pollWatch(ctx context.Context, path string, ch chan interface{}) {
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	// Initial state
	lastState := make(map[string]time.Time)
	entries, _ := os.ReadDir(path)
	for _, e := range entries {
		info, _ := e.Info()
		if info != nil {
			lastState[e.Name()] = info.ModTime()
		}
	}

	for {
		select {
		case <-ctx.Done():
			fd.mu.Lock()
			delete(fd.watchers, path)
			fd.mu.Unlock()
			close(ch)
			return
		case <-ticker.C:
			entries, err := os.ReadDir(path)
			if err != nil {
				continue
			}

			currentState := make(map[string]time.Time)
			for _, e := range entries {
				info, _ := e.Info()
				if info == nil {
					continue
				}
				currentState[e.Name()] = info.ModTime()

				if lastMod, exists := lastState[e.Name()]; exists {
					if info.ModTime().After(lastMod) {
						ch <- FileEvent{Type: "modified", Path: filepath.Join(path, e.Name()), Timestamp: time.Now()}
					}
				} else {
					ch <- FileEvent{Type: "created", Path: filepath.Join(path, e.Name()), Timestamp: time.Now()}
				}
			}

			// Check for deletions
			for name := range lastState {
				if _, exists := currentState[name]; !exists {
					ch <- FileEvent{Type: "deleted", Path: filepath.Join(path, name), Timestamp: time.Now()}
				}
			}

			lastState = currentState
		}
	}
}
