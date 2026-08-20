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
    local pid=$!
    echo "  [BOOT] $name PID: $pid"
    echo "$pid" >> "$PROJECT_ROOT/data/logs/pids.txt"
}

# ── Rust binary directory (cargo release output) ──────────────
RUST_BIN="$PROJECT_ROOT/rust/target/release"

# ── 1. Rust Neural Mesh Service (port 50053) ─────────────────
# Binary name: ultron-neural-service  (from ultron_neural_service crate)
NEURAL_BIN="$RUST_BIN/ultron-neural-service"
if [ -x "$NEURAL_BIN" ]; then
    start_process "neural_mesh" "$NEURAL_BIN"
    echo "  [OK] Rust Neural Mesh started (port 50053)"
else
    echo "  [SKIP] Rust Neural Mesh binary not found ($NEURAL_BIN)"
fi

# ── 2. Rust Security Daemon (port 50055) ─────────────────────
# Binary name: ultron-security-daemon  (from security_daemon crate)
SEC_BIN="$RUST_BIN/ultron-security-daemon"
if [ -x "$SEC_BIN" ]; then
    start_process "security_daemon" "$SEC_BIN"
    echo "  [OK] Rust Security Daemon started (port 50055)"
else
    echo "  [SKIP] Rust Security Daemon binary not found ($SEC_BIN)"
fi

# ── 3. Rust Real-Time Data Pipeline (port 50054) ─────────────
# Binary name: ultron-real-time-data  (from real_time_data crate)
DATA_BIN="$RUST_BIN/ultron-real-time-data"
if [ -x "$DATA_BIN" ]; then
    start_process "data_pipeline" "$DATA_BIN"
    echo "  [OK] Rust Data Pipeline started (port 50054)"
else
    echo "  [SKIP] Rust Data Pipeline binary not found ($DATA_BIN)"
fi

# ── 4. Rust Neuromorphic Engine (port 50056) ─────────────────
# Binary name: ultron-neuromorphic  (from neuromorphic crate)
NEURO_BIN="$RUST_BIN/ultron-neuromorphic"
if [ -x "$NEURO_BIN" ]; then
    start_process "neuromorphic" "$NEURO_BIN"
    echo "  [OK] Rust Neuromorphic started (port 50056)"
else
    echo "  [SKIP] Rust Neuromorphic binary not found ($NEURO_BIN)"
fi

# ── 5. Go Core Agent (if binary exists) ──────────────────────
GO_AGENT="$PROJECT_ROOT/go/core_agent/ultron_agent"
if [ -x "$GO_AGENT" ]; then
    start_process "go_agent" "$GO_AGENT"
    echo "  [OK] Go Core Agent started"
else
    echo "  [SKIP] Go Agent binary not found at $GO_AGENT"
fi

# ── 6. Go Watchdog (if binary exists) ────────────────────────
GO_WATCHDOG="$PROJECT_ROOT/go/core_agent/ultron-watchdog"
if [ -x "$GO_WATCHDOG" ]; then
    export ULTRON_BINARY="$GO_AGENT"
    export ULTRON_SNAPSHOT_DIR="$PROJECT_ROOT/data/snapshots"
    start_process "watchdog" "$GO_WATCHDOG"
    echo "  [OK] Watchdog started"
else
    echo "  [SKIP] Watchdog binary not found"
fi

# ── 7. P2P Network (if binary exists) ────────────────────────
GO_P2P="$PROJECT_ROOT/go/p2p_network/ultron-p2p"
if [ -x "$GO_P2P" ]; then
    start_process "p2p_network" "$GO_P2P"
    echo "  [OK] P2P Consciousness Network started"
else
    echo "  [SKIP] P2P binary not found"
fi

# ── 8. Learning Service (Python) ─────────────────────────────
start_process "learning" python3 -m python.self_improvement.learning "$PROJECT_ROOT"
echo "  [OK] Learning service started"

# Give background processes a moment to bind their ports
sleep 2

# ── 9. Main Web Server (Python — foreground, Railway needs this) ──
echo ""
echo "  [BOOT] Starting Ultron Web Interface (foreground)..."
echo "═══════════════════════════════════════════════════════════"
echo ""

exec python3 -m uvicorn python.interface.server:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers 1 \
    --timeout-keep-alive 65