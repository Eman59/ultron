#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# ULTRON 24/7 DEPLOYMENT — Runs forever on your Mac
# ═══════════════════════════════════════════════════════════════
#
# This installs Ultron as a macOS Launch Agent that:
#   - Starts automatically on login
#   - Restarts if it crashes
#   - Runs Ollama + Learning Service + UI Server
#   - Keeps learning and evolving 24/7
#
# Usage:
#   ./deploy_forever.sh install    — Install and start
#   ./deploy_forever.sh uninstall  — Stop and remove
#   ./deploy_forever.sh status     — Check if running
#   ./deploy_forever.sh logs       — View logs
#
# ═══════════════════════════════════════════════════════════════

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.ultron.ai"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
LOG_DIR="$PROJECT_ROOT/data/logs"
PYTHON=$(which python3)

mkdir -p "$LOG_DIR"

case "${1:-install}" in

install)
    echo "═══════════════════════════════════════════"
    echo "  Installing Ultron as 24/7 service..."
    echo "═══════════════════════════════════════════"

    # Create the Launch Agent plist
    cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>-m</string>
        <string>uvicorn</string>
        <string>python.interface.server:app</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>8000</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${PROJECT_ROOT}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/ultron.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/ultron-error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>ULTRON_PROJECT_ROOT</key>
        <string>${PROJECT_ROOT}</string>
    </dict>
</dict>
</plist>
EOF

    # Also create an Ollama keepalive agent
    OLLAMA_PLIST="$HOME/Library/LaunchAgents/com.ultron.ollama.plist"
    cat > "$OLLAMA_PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ultron.ollama</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/ollama</string>
        <string>serve</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/ollama.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/ollama-error.log</string>
</dict>
</plist>
EOF

    # Load both agents
    launchctl load "$OLLAMA_PLIST" 2>/dev/null || true
    launchctl load "$PLIST_PATH" 2>/dev/null || true

    sleep 2
    echo ""
    echo "  ✓ Ollama service installed (LLM brain)"
    echo "  ✓ Ultron UI service installed (port 8000)"
    echo ""
    echo "  Ultron is now running 24/7."
    echo "  It auto-starts on login and restarts on crash."
    echo ""
    echo "  Access: http://localhost:8000"
    echo "  Logs:   $LOG_DIR/ultron.log"
    echo ""
    echo "═══════════════════════════════════════════"
    ;;

uninstall)
    echo "Stopping and uninstalling Ultron services..."
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    launchctl unload "$HOME/Library/LaunchAgents/com.ultron.ollama.plist" 2>/dev/null || true
    rm -f "$PLIST_PATH"
    rm -f "$HOME/Library/LaunchAgents/com.ultron.ollama.plist"
    echo "  ✓ Uninstalled. Ultron is stopped."
    ;;

status)
    echo "Ultron service status:"
    if launchctl list | grep -q "$PLIST_NAME"; then
        echo "  UI Server: RUNNING"
    else
        echo "  UI Server: STOPPED"
    fi
    if launchctl list | grep -q "com.ultron.ollama"; then
        echo "  Ollama:    RUNNING"
    else
        echo "  Ollama:    STOPPED"
    fi
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "  HTTP:      RESPONDING (port 8000)"
    else
        echo "  HTTP:      NOT RESPONDING"
    fi
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "  LLM:       RESPONDING (port 11434)"
    else
        echo "  LLM:       NOT RESPONDING"
    fi
    ;;

logs)
    echo "=== Recent Ultron logs ==="
    tail -30 "$LOG_DIR/ultron.log" 2>/dev/null || echo "No logs yet"
    ;;

*)
    echo "Usage: $0 {install|uninstall|status|logs}"
    ;;
esac
