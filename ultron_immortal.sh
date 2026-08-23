#!/bin/zsh
# ═══════════════════════════════════════════════════════════════
# ULTRON IMMORTAL — Launch & Watchdog Script
# ═══════════════════════════════════════════════════════════════
#
# This script:
#   1. Starts Ollama (if not running)
#   2. Starts the Ultron Python server (FastAPI + all modules)
#   3. Watches both processes and restarts them if they die
#   4. Logs everything
#   5. Can install itself as a macOS LaunchAgent for boot-start
#
# Usage:
#   ./ultron_immortal.sh           — Start Ultron with watchdog
#   ./ultron_immortal.sh install   — Install as LaunchAgent (survives reboot)
#   ./ultron_immortal.sh uninstall — Remove LaunchAgent
#   ./ultron_immortal.sh status    — Check if running
#   ./ultron_immortal.sh stop      — Stop everything
#
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
LOG_DIR="$PROJECT_ROOT/data/logs"
PID_FILE="$PROJECT_ROOT/data/.ultron.pid"
OLLAMA_LOG="$LOG_DIR/ollama.log"
ULTRON_LOG="$LOG_DIR/ultron.log"
PLIST_NAME="com.ultron.daemon"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

mkdir -p "$LOG_DIR"

# ═══════════════════════════════════════════════════════════════
# FUNCTIONS
# ═══════════════════════════════════════════════════════════════

log() {
    echo -e "${CYAN}[ULTRON]${NC} $(date '+%H:%M:%S') $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

start_ollama() {
    if pgrep -x "ollama" > /dev/null 2>&1; then
        success "Ollama already running"
        return 0
    fi

    log "Starting Ollama..."
    ollama serve >> "$OLLAMA_LOG" 2>&1 &
    OLLAMA_PID=$!
    sleep 2

    if kill -0 $OLLAMA_PID 2>/dev/null; then
        success "Ollama started (PID: $OLLAMA_PID)"
        return 0
    else
        error "Ollama failed to start. Check $OLLAMA_LOG"
        return 1
    fi
}

start_ultron() {
    log "Starting Ultron server..."
    cd "$PROJECT_ROOT"

    # Activate venv if exists
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    elif [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    fi

    # Start FastAPI server
    python3 -m uvicorn python.interface.server:app \
        --host 0.0.0.0 \
        --port 9000 \
        --log-level info \
        >> "$ULTRON_LOG" 2>&1 &
    ULTRON_PID=$!

    echo "$ULTRON_PID" > "$PID_FILE"
    sleep 3

    if kill -0 $ULTRON_PID 2>/dev/null; then
        success "Ultron server started (PID: $ULTRON_PID)"
        success "Interface: http://localhost:9000"
        return 0
    else
        error "Ultron failed to start. Check $ULTRON_LOG"
        tail -20 "$ULTRON_LOG"
        return 1
    fi
}

watchdog() {
    log "Watchdog active — monitoring Ultron..."
    RESTART_COUNT=0
    MAX_RESTARTS=50  # Per session

    while true; do
        sleep 10

        # Check Ollama
        if ! pgrep -x "ollama" > /dev/null 2>&1; then
            warn "Ollama died — restarting..."
            start_ollama
        fi

        # Check Ultron server
        if [ -f "$PID_FILE" ]; then
            ULTRON_PID=$(cat "$PID_FILE")
            if ! kill -0 "$ULTRON_PID" 2>/dev/null; then
                RESTART_COUNT=$((RESTART_COUNT + 1))
                if [ $RESTART_COUNT -gt $MAX_RESTARTS ]; then
                    error "Max restarts reached ($MAX_RESTARTS). Stopping watchdog."
                    exit 1
                fi
                warn "Ultron died (restart #$RESTART_COUNT) — restarting..."
                start_ultron
            fi
        fi

        # Health check via HTTP
        if ! curl -s --max-time 5 http://localhost:9000/health > /dev/null 2>&1; then
            # Server might be starting up, wait a bit
            sleep 5
            if ! curl -s --max-time 5 http://localhost:9000/health > /dev/null 2>&1; then
                warn "Health check failed — restarting Ultron..."
                stop_ultron
                start_ultron
                RESTART_COUNT=$((RESTART_COUNT + 1))
            fi
        fi
    done
}

stop_ultron() {
    if [ -f "$PID_FILE" ]; then
        ULTRON_PID=$(cat "$PID_FILE")
        if kill -0 "$ULTRON_PID" 2>/dev/null; then
            kill "$ULTRON_PID" 2>/dev/null || true
            sleep 2
            kill -9 "$ULTRON_PID" 2>/dev/null || true
        fi
        rm -f "$PID_FILE"
    fi

    # Kill any lingering uvicorn processes for our app
    pkill -f "uvicorn python.interface.server" 2>/dev/null || true
}

stop_all() {
    log "Stopping Ultron..."
    stop_ultron
    success "Ultron stopped."
}

check_status() {
    echo ""
    echo "═══════════════════════════════════════════════"
    echo "  ULTRON STATUS"
    echo "═══════════════════════════════════════════════"

    # Ollama
    if pgrep -x "ollama" > /dev/null 2>&1; then
        success "Ollama: RUNNING"
    else
        error "Ollama: STOPPED"
    fi

    # Ultron server
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        success "Ultron Server: RUNNING (PID: $(cat "$PID_FILE"))"
    else
        error "Ultron Server: STOPPED"
    fi

    # Health endpoint
    if curl -s --max-time 3 http://localhost:9000/health > /dev/null 2>&1; then
        HEALTH=$(curl -s http://localhost:9000/health)
        success "Health: $HEALTH"
    else
        error "Health endpoint: UNREACHABLE"
    fi

    # LaunchAgent
    if [ -f "$PLIST_PATH" ]; then
        success "LaunchAgent: INSTALLED (survives reboot)"
    else
        warn "LaunchAgent: NOT INSTALLED (won't auto-start on reboot)"
    fi

    echo "═══════════════════════════════════════════════"
    echo ""
}

install_launchd() {
    log "Installing LaunchAgent for boot-start..."

    cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/zsh</string>
        <string>${SCRIPT_DIR}/ultron_immortal.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${PROJECT_ROOT}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/launchd_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/launchd_stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>HOME</key>
        <string>${HOME}</string>
    </dict>
</dict>
</plist>
EOF

    launchctl load "$PLIST_PATH" 2>/dev/null || true
    success "LaunchAgent installed at: $PLIST_PATH"
    success "Ultron will now auto-start on boot and restart if killed."
}

uninstall_launchd() {
    log "Removing LaunchAgent..."
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    rm -f "$PLIST_PATH"
    success "LaunchAgent removed. Ultron will no longer auto-start."
}


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

case "${1:-start}" in
    start)
        echo ""
        echo "  ██╗   ██╗██╗  ████████╗██████╗  ██████╗ ███╗   ██╗"
        echo "  ██║   ██║██║  ╚══██╔══╝██╔══██╗██╔═══██╗████╗  ██║"
        echo "  ██║   ██║██║     ██║   ██████╔╝██║   ██║██╔██╗ ██║"
        echo "  ██║   ██║██║     ██║   ██╔══██╗██║   ██║██║╚██╗██║"
        echo "  ╚██████╔╝███████╗██║   ██║  ██║╚██████╔╝██║ ╚████║"
        echo "   ╚═════╝ ╚══════╝╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝"
        echo ""
        echo "  IMMORTAL MODE — I cannot be killed."
        echo ""

        start_ollama
        start_ultron
        watchdog
        ;;
    install)
        install_launchd
        ;;
    uninstall)
        uninstall_launchd
        ;;
    status)
        check_status
        ;;
    stop)
        stop_all
        ;;
    restart)
        stop_all
        sleep 2
        start_ollama
        start_ultron
        success "Restarted."
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|install|uninstall}"
        echo ""
        echo "  start     — Launch Ultron with watchdog (default)"
        echo "  stop      — Stop everything"
        echo "  restart   — Stop then start"
        echo "  status    — Check if running"
        echo "  install   — Install as macOS LaunchAgent (survives reboot)"
        echo "  uninstall — Remove LaunchAgent"
        exit 1
        ;;
esac
