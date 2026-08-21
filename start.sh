#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║  ULTRON — Full Stack Launcher (single container)            ║
# ║  Starts all services, then runs Python server in foreground  ║
# ╚══════════════════════════════════════════════════════════════╝
set -e

export PYTHONPATH="${PYTHONPATH:-/app}"
export ULTRON_PROJECT_ROOT="${ULTRON_PROJECT_ROOT:-/app}"
PORT="${PORT:-8000}"

mkdir -p data/logs data/snapshots data/consciousness data/knowledge \
         data/memory data/voice data/uploads data/simulations

log() { echo "  [BOOT] $1"; }

# ── Helper: start background process with logging ─────────────
start() {
    local name="$1"; shift
    if [ -x "$1" ]; then
        log "Starting $name..."
        "$@" >> "data/logs/${name}.log" 2>&1 &
        echo $! > "data/logs/${name}.pid"
        log "$name started (PID $!)"
    else
        log "SKIP $name — binary not found: $1"
    fi
}

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   ULTRON — FULL SYSTEM BOOT                                  ║"
echo "╚══════════════════════════════════════════════════════════════╝"

# ── 1. Rust Neural Mesh (port 50053) ──────────────────────────
start "neural_mesh" \
    rust/target/release/ultron-neural-service

# ── 2. Rust Security Daemon (port 50055) ──────────────────────
start "security_daemon" \
    rust/target/release/ultron-security-daemon

# ── 3. Rust Data Pipeline (port 50054) ────────────────────────
start "data_pipeline" \
    rust/target/release/ultron-real-time-data

# ── 4. Rust Neuromorphic (port 50056) ─────────────────────────
start "neuromorphic" \
    rust/target/release/ultron-neuromorphic

# ── 5. Go Core Agent (OODA loop, port 50051/50052) ────────────
if [ -x "go/core_agent/ultron_agent" ]; then
    log "Starting Go Core Agent..."
    go/core_agent/ultron_agent \
        >> data/logs/go_agent.log 2>&1 &
    echo $! > data/logs/go_agent.pid
    log "Go Core Agent started (PID $!)"
fi

# ── 6. Go Watchdog (keeps agent alive) ────────────────────────
if [ -x "go/core_agent/ultron-watchdog" ] && \
   [ -x "go/core_agent/ultron_agent" ]; then
    export ULTRON_BINARY="/app/go/core_agent/ultron_agent"
    export ULTRON_SNAPSHOT_DIR="/app/data/snapshots"
    start "watchdog" go/core_agent/ultron-watchdog
fi

# ── 7. P2P Consciousness Network (port 4001) ──────────────────
start "p2p_network" \
    go/p2p_network/ultron-p2p

# ── 8. Python Learning Service ────────────────────────────────
if python3 -c "import python.self_improvement.learning" 2>/dev/null; then
    log "Starting Learning Service..."
    python3 -m python.self_improvement.learning /app \
        >> data/logs/learning.log 2>&1 &
    log "Learning Service started (PID $!)"
else
    log "SKIP Learning Service — module unavailable"
fi

# Give background processes 2s to bind their ports
sleep 2

echo ""
echo "  [BOOT] All background services launched"
echo "  [BOOT] Starting Python Web Interface on port $PORT..."
echo ""

# ── 9. Python Server (foreground — container stays alive) ─────
exec python3 -m uvicorn python.interface.server:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --workers 1 \
    --timeout-keep-alive 75
