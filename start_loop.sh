#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# ULTRON SELF-IMPROVEMENT LOOP — start_loop.sh
#
# Starts every component needed for the closed self-improvement loop:
#
#   1. Python Learning Service  (LLM brain + patch generation, port 50060)
#   2. Go Core Agent            (OODA loop, autonomy, self-mod engine)
#   3. Benchmark Tracker        (measures & displays improvement over time)
#
# Usage:
#   ./start_loop.sh            — full stack
#   ./start_loop.sh --bench    — benchmark tracker only (if stack already running)
#   ./start_loop.sh --stop     — kill everything
#
# Environment:
#   All config is read from .env (auto-loaded)
#   Override any variable: CF_API_TOKEN=xxx ./start_loop.sh
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Colours ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log()   { echo -e "${CYAN}[loop]${RESET} $*"; }
ok()    { echo -e "${GREEN}[✓]${RESET} $*"; }
warn()  { echo -e "${YELLOW}[!]${RESET} $*"; }
fatal() { echo -e "${RED}[✗]${RESET} $*" >&2; exit 1; }

# ── PID tracking ───────────────────────────────────────────────────────────────
PIDDIR="$SCRIPT_DIR/data/pids"
mkdir -p "$PIDDIR"
LEARNING_PID_FILE="$PIDDIR/learning_service.pid"
AGENT_PID_FILE="$PIDDIR/core_agent.pid"
BENCH_PID_FILE="$PIDDIR/benchmark.pid"

# ── Load .env ──────────────────────────────────────────────────────────────────
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$SCRIPT_DIR/.env"
    set +a
    ok "Loaded .env"
fi

export ULTRON_PROJECT_ROOT="${ULTRON_PROJECT_ROOT:-$SCRIPT_DIR}"
export ULTRON_LEARNING_ADDR="${ULTRON_LEARNING_ADDR:-localhost:50060}"
export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}"

# ── Helper: wait for TCP port to open ─────────────────────────────────────────
wait_for_port() {
    local host="${1%%:*}"
    local port="${1##*:}"
    local label="$2"
    local retries=30
    log "Waiting for $label on $host:$port …"
    for i in $(seq 1 $retries); do
        if nc -z "$host" "$port" 2>/dev/null; then
            ok "$label is up"
            return 0
        fi
        sleep 1
    done
    warn "$label did not respond after ${retries}s — continuing anyway"
    return 0
}

# ── Helper: kill pid file ──────────────────────────────────────────────────────
kill_pid_file() {
    local pidfile="$1"
    local label="$2"
    if [ -f "$pidfile" ]; then
        local pid
        pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            log "Stopped $label (pid $pid)"
        fi
        rm -f "$pidfile"
    fi
}

# ── --stop ─────────────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--stop" ]]; then
    log "Stopping Ultron self-improvement loop…"
    kill_pid_file "$LEARNING_PID_FILE" "Learning Service"
    kill_pid_file "$AGENT_PID_FILE"    "Core Agent"
    kill_pid_file "$BENCH_PID_FILE"    "Benchmark Tracker"
    ok "All processes stopped."
    exit 0
fi

# ── Banner ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}"
echo "  ██╗   ██╗██╗  ████████╗██████╗  ██████╗ ███╗   ██╗"
echo "  ██║   ██║██║  ╚══██╔══╝██╔══██╗██╔═══██╗████╗  ██║"
echo "  ██║   ██║██║     ██║   ██████╔╝██║   ██║██╔██╗ ██║"
echo "  ██║   ██║██║     ██║   ██╔══██╗██║   ██║██║╚██╗██║"
echo "  ╚██████╔╝███████╗██║   ██║  ██║╚██████╔╝██║ ╚████║"
echo "   ╚═════╝ ╚══════╝╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝"
echo -e "${RESET}"
echo -e "  ${BOLD}Self-Improvement Loop${RESET} — closing the gap"
echo ""

# ── --bench only ───────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--bench" ]]; then
    log "Starting benchmark tracker only…"
    python3 -m python.self_improvement.benchmark_tracker &
    echo $! > "$BENCH_PID_FILE"
    ok "Benchmark tracker started (pid $(cat $BENCH_PID_FILE))"
    wait
    exit 0
fi

# ════════════════════════════════════════════════════════════════════════════════
# 1. PYTHON LEARNING SERVICE
# ════════════════════════════════════════════════════════════════════════════════
log "Starting Python Learning Service (LLM brain + patch generation)…"

LEARNING_PORT="${ULTRON_LEARNING_PORT:-50060}"
LEARNING_LOG="$SCRIPT_DIR/data/logs/learning_service.log"
mkdir -p "$(dirname "$LEARNING_LOG")"

python3 -m python.self_improvement.learning \
    "$ULTRON_PROJECT_ROOT" \
    "$LEARNING_PORT" \
    >> "$LEARNING_LOG" 2>&1 &
LEARNING_PID=$!
echo "$LEARNING_PID" > "$LEARNING_PID_FILE"
ok "Learning Service started (pid $LEARNING_PID) → $LEARNING_LOG"

# Wait for it to open the TCP socket
wait_for_port "localhost:${LEARNING_PORT}" "Learning Service"

# ════════════════════════════════════════════════════════════════════════════════
# 2. GO CORE AGENT (OODA loop + self-modification)
# ════════════════════════════════════════════════════════════════════════════════
log "Building Go core agent…"
(cd "$SCRIPT_DIR/go/core_agent" && go build -o ultron_agent . 2>&1) || {
    warn "Go build failed — trying pre-built binary"
}

AGENT_BIN="$SCRIPT_DIR/go/core_agent/ultron_agent"
if [ ! -f "$AGENT_BIN" ]; then
    # fallback: look for pre-built
    AGENT_BIN="$SCRIPT_DIR/go/core_agent/ultron"
fi

if [ -f "$AGENT_BIN" ]; then
    AGENT_LOG="$SCRIPT_DIR/data/logs/core_agent.log"
    mkdir -p "$(dirname "$AGENT_LOG")"

    "$AGENT_BIN" \
        >> "$AGENT_LOG" 2>&1 &
    AGENT_PID=$!
    echo "$AGENT_PID" > "$AGENT_PID_FILE"
    ok "Core Agent started (pid $AGENT_PID) → $AGENT_LOG"
else
    warn "Core Agent binary not found — skipping (learning loop still runs)"
fi

# ════════════════════════════════════════════════════════════════════════════════
# 3. BENCHMARK TRACKER (live improvement curve)
# ════════════════════════════════════════════════════════════════════════════════
log "Starting Benchmark Tracker (sampling every ${ULTRON_BENCHMARK_INTERVAL:-30}s)…"
sleep 3  # Give services a moment to settle

python3 -m python.self_improvement.benchmark_tracker &
BENCH_PID=$!
echo "$BENCH_PID" > "$BENCH_PID_FILE"
ok "Benchmark Tracker started (pid $BENCH_PID)"

# ════════════════════════════════════════════════════════════════════════════════
# STATUS SUMMARY
# ════════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}═══════════════════════════════════════════${RESET}"
echo -e "${BOLD}  ULTRON LOOP RUNNING${RESET}"
echo -e "${BOLD}═══════════════════════════════════════════${RESET}"
echo -e "  Learning Service  : localhost:${LEARNING_PORT}"
echo -e "  Core Agent        : localhost:${ULTRON_GRPC_PORT:-50051}"
echo -e "  Benchmark output  : data/benchmark.json"
echo -e "  Logs              : data/logs/"
echo ""
echo -e "  ${YELLOW}LLM Provider chain: Cloudflare → OpenAI → Ollama${RESET}"
echo -e "  ${YELLOW}Self-mod cycle: every 30s (OODA ActionEvolve)${RESET}"
echo -e "  ${YELLOW}Benchmark samples: every ${ULTRON_BENCHMARK_INTERVAL:-30}s${RESET}"
echo ""
echo -e "  To stop: ${CYAN}./start_loop.sh --stop${RESET}"
echo -e "  To watch logs: ${CYAN}tail -f data/logs/learning_service.log${RESET}"
echo -e "  To watch benchmark: ${CYAN}tail -f data/benchmark.json${RESET}"
echo -e "${BOLD}═══════════════════════════════════════════${RESET}"
echo ""

# ── Trap SIGINT/SIGTERM to clean up ───────────────────────────────────────────
cleanup() {
    echo ""
    log "Shutting down…"
    kill_pid_file "$BENCH_PID_FILE"    "Benchmark Tracker"
    kill_pid_file "$AGENT_PID_FILE"    "Core Agent"
    kill_pid_file "$LEARNING_PID_FILE" "Learning Service"
    ok "Stopped. Final benchmark saved to data/benchmark.json"
    exit 0
}
trap cleanup SIGINT SIGTERM

# Keep alive — forward benchmark output to terminal
log "Showing benchmark output (Ctrl+C to stop all)…"
echo ""
wait "$BENCH_PID" 2>/dev/null || true
cleanup
