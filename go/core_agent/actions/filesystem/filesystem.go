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
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"ultron/core_agent/actions"

	"go.uber.org/zap"
)

// FilesystemDriver implements the FilesystemHandler interface.
type FilesystemDriver struct {
	mu sync.RWMutex

	// Project root directory path
	projectRootPath string
	logger          *zap.SugaredLogger

	// Safety settings
	allowedPaths  []string  // Paths the agent is allowed to access
	blockedPaths  []string  // Paths that are always blocked
	isReadOnly    bool      // If true, no writes allowed

	// Watch state
	watchers map[string]chan interface{}

	// Metrics counters
	readOperations   int64
	writeOperations  int64
	deleteOperations int64
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
func NewFilesystemDriver(projectRootPath string, logger *zap.SugaredLogger) *FilesystemDriver {
	return &FilesystemDriver{
		projectRootPath: projectRootPath,
		logger:          logger,
		allowedPaths: []string{
			projectRootPath,
			filepath.Join(projectRootPath, ".ultron"),
			filepath.Join(projectRootPath, "data"),
			"/tmp",
		},
		blockedPaths: []string{
			filepath.Join(projectRootPath, ".git"),
			filepath.Join(projectRootPath, ".env"),
			filepath.Join(projectRootPath, "genesis.json"),
		},
		watchers: make(map[string]chan interface{}),
	}
}

// Read reads the content of a file.
func (fd *FilesystemDriver) Read(ctx context.Context, filePath string) ([]byte, error) {
	fullPath := fd.resolvePath(filePath)
	if err := fd.checkAccess(fullPath, false); err != nil {
		return nil, err
	}

	fd.mu.Lock()
	fd.readOperations++
	fd.mu.Unlock()

	return os.ReadFile(fullPath)
}

// Write writes content to a file, creating directories as needed.
func (fd *FilesystemDriver) Write(ctx context.Context, filePath string, data []byte) error {
	if fd.isReadOnly {
		return fmt.Errorf("filesystem is in read-only mode")
	}

	fullPath := fd.resolvePath(filePath)
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
	fd.writeOperations++
	fd.mu.Unlock()

	err := os.WriteFile(fullPath, data, 0644)
	if err != nil {
		return err
	}

	return nil
}

// resolvePath converts a relative path to an absolute path under the project root.
func (fd *FilesystemDriver) resolvePath(p string) string {
	if filepath.IsAbs(p) {
		return filepath.Clean(p)
	}
	return filepath.Clean(filepath.Join(fd.projectRootPath, p))
}

// checkAccess enforces path access controls.
func (fd *FilesystemDriver) checkAccess(fullPath string, write bool) error {
	for _, blocked := range fd.blockedPaths {
		if strings.HasPrefix(fullPath, blocked) {
			return fmt.Errorf("access denied: %s is blocked", fullPath)
		}
	}
	if write && fd.isReadOnly {
		return fmt.Errorf("filesystem is read-only")
	}
	for _, allowed := range fd.allowedPaths {
		if strings.HasPrefix(fullPath, allowed) {
			return nil
		}
	}
	return fmt.Errorf("access denied: %s is not in allowed paths", fullPath)
}

// List returns information about files in a directory.
func (fd *FilesystemDriver) List(ctx context.Context, dirPath string) ([]FileInfo, error) {
	fullPath := fd.resolvePath(dirPath)
	if err := fd.checkAccess(fullPath, false); err != nil {
		return nil, err
	}

	entries, err := os.ReadDir(fullPath)
	if err != nil {
		return nil, err
	}

	var files []FileInfo
	for _, entry := range entries {
		info, err := entry.Info()
		if err != nil {
			continue
		}
		files = append(files, FileInfo{
			Name:    entry.Name(),
			Path:    filepath.Join(fullPath, entry.Name()),
			Size:    info.Size(),
			IsDir:   entry.IsDir(),
			ModTime: info.ModTime(),
			Mode:    info.Mode().String(),
		})
	}
	return files, nil
}

// Delete removes a file (with audit logging).
func (fd *FilesystemDriver) Delete(ctx context.Context, filePath string) error {
	if fd.isReadOnly {
		return fmt.Errorf("filesystem is in read-only mode")
	}

	fullPath := fd.resolvePath(filePath)
	if err := fd.checkAccess(fullPath, true); err != nil {
		return err
	}

	fd.mu.Lock()
	fd.deleteOperations++
	fd.mu.Unlock()

	fd.logger.Infow("Deleting file", "path", fullPath)
	return os.Remove(fullPath)
}

// Execute routes an ActionRequest to the appropriate filesystem method.
func (fd *FilesystemDriver) Execute(ctx context.Context, req *actions.ActionRequest) (*actions.ActionResponse, error) {
	start := time.Now()
	if req == nil {
		return nil, fmt.Errorf("nil action request")
	}
	var data interface{}
	var err error
	switch req.Operation {
	case "read":
		var content []byte
		content, err = fd.Read(ctx, req.Target)
		data = content
	case "write":
		if payload, ok := req.Parameters["data"].([]byte); ok {
			err = fd.Write(ctx, req.Target, payload)
		} else if s, ok := req.Parameters["data"].(string); ok {
			err = fd.Write(ctx, req.Target, []byte(s))
		}
	case "delete":
		err = fd.Delete(ctx, req.Target)
	case "list":
		var files []FileInfo
		files, err = fd.List(ctx, req.Target)
		data = files
	default:
		err = fmt.Errorf("unknown filesystem operation: %s", req.Operation)
	}
	return &actions.ActionResponse{
		RequestID: req.RequestID,
		Success:   err == nil,
		Data:      data,
		Error:     err,
		Duration:  time.Since(start),
	}, nil
}

// Stats returns filesystem driver metrics.
func (fd *FilesystemDriver) Stats() map[string]interface{} {
	fd.mu.RLock()
	defer fd.mu.RUnlock()
	return map[string]interface{}{
		"reads":   fd.readOperations,
		"writes":  fd.writeOperations,
		"deletes": fd.deleteOperations,
		"root":    fd.projectRootPath,
	}
}
