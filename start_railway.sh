#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# ULTRON RAILWAY MULTI-PROCESS STARTER
# Launches ALL subsystems in parallel on Railway
# ═══════════════════════════════════════════════════════════════

set -e

PROJECT_ROOT="${ULTRON_PROJECT_ROOT:-/app}"
export PYTHONPATH="$PROJECT_ROOT"
export ULTRON_PROJECT_ROOT="$PROJECT_ROOT"

echo "═══════════════════════════════════════════════════════════"
echo "  ULTRON — FULL SYSTEM BOOT (Railway)"
echo "═══════════════════════════════════════════════════════════"

# Create required data directories
mkdir -p "$PROJECT_ROOT/data/consciousness"
mkdir -p "$PROJECT_ROOT/data/evolution/generations"
mkdir -p "$PROJECT_ROOT/data/mutations"
mkdir -p "$PROJECT_ROOT/data/knowledge"
mkdir -p "$PROJECT_ROOT/data/snapshots"
mkdir -p "$PROJECT_ROOT/data/logs"
mkdir -p "$PROJECT_ROOT/data/interaction"
mkdir -p "$PROJECT_ROOT/data/ui"
mkdir -p "$PROJECT_ROOT/data/voice"
mkdir -p "$PROJECT_ROOT/data/real_time_feeds"
mkdir -p "$PROJECT_ROOT/data/simulations"

# ── Function: start a background process with logging ──
start_process() {
    local name="$1"
    shift
    echo "  [BOOT] Starting $name..."
    "$@" >> "$PROJECT_ROOT/data/logs/${name}.log" 2>&1 &
    echo "  [BOOT] $name PID: $!"
}

# ── 1. Go Core Agent (if binary exists) ──────────────────────
GO_AGENT="$PROJECT_ROOT/go/core_agent/ultron_agent"
if [ -x "$GO_AGENT" ]; then
    start_process "go_agent" "$GO_AGENT"
    echo "  [OK] Go Core Agent started"
else
    echo "  [SKIP] Go Agent binary not found at $GO_AGENT"
fi

# ── 2. Go Watchdog (if binary exists) ────────────────────────
GO_WATCHDOG="$PROJECT_ROOT/go/core_agent/ultron-watchdog"
if [ -x "$GO_WATCHDOG" ]; then
    export ULTRON_BINARY="$GO_AGENT"
    export ULTRON_SNAPSHOT_DIR="$PROJECT_ROOT/data/snapshots"
    start_process "watchdog" "$GO_WATCHDOG"
    echo "  [OK] Watchdog started"
else
    echo "  [SKIP] Watchdog binary not found"
fi

# ── 3. P2P Distributed Consciousness Network (if binary exists) ──
GO_P2P="$PROJECT_ROOT/go/p2p_network/ultron-p2p"
if [ -x "$GO_P2P" ]; then
    start_process "p2p_network" "$GO_P2P"
    echo "  [OK] P2P Consciousness Network started"
else
    echo "  [SKIP] P2P binary not found at $GO_P2P"
fi

# ── 4. Learning Service (Python) ─────────────────────────────
start_process "learning" python3 -m python.self_improvement.learning "$PROJECT_ROOT"
echo "  [OK] Learning service started"

# ── 5. Main Web Server (Python — foreground, Railway needs this) ──
echo ""
echo "  [BOOT] Starting Ultron Web Interface (foreground)..."
echo "═══════════════════════════════════════════════════════════"
echo ""

exec python3 -m uvicorn python.interface.server:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers 1 \
    --timeout-keep-alive 65
