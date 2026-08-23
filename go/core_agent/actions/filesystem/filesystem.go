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