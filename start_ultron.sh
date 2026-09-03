#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# ULTRON — UNIFIED STARTUP SCRIPT
# Boots every layer of the system in dependency order, non-blocking.
#
# Usage:
#   ./start_ultron.sh           # Start everything
#   ./start_ultron.sh --stop    # Kill all managed processes
#   ./start_ultron.sh --status  # Show what's running
#   ./start_ultron.sh --no-rust # Skip Rust services (faster dev cycle)
#
# What starts (in order):
#   1. Go Core Agent        — 50ms OODA loop, dual-brain, embedded memory
#   2. Go Watchdog          — Keeps agent alive after crashes
#   3. Rust Neural Mesh     — Hebbian plasticity, hot-swap architecture
#   4. Rust Security Daemon — Threat monitor, integrity checker
#   5. Brain C Sidecar      — Autonomous reasoning HTTP sidecar
#   6. Python Learning Svc  — Unified self-improvement hub
#   7. Python Interface     — FastAPI server (UI + REST API + WebSocket)
#   8. Rust Neuromorphic + Data Pipeline
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$PROJECT_ROOT/data/logs"
PID_DIR="$PROJECT_ROOT/data/pids"
mkdir -p "$LOG_DIR" "$PID_DIR"

# ── Load environment ──────────────────────────────────────────────────────────
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_ROOT/.env"
    set +a
fi
export ULTRON_PROJECT_ROOT="$PROJECT_ROOT"

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

banner() {
    echo ""
    echo -e "${RED}${BOLD}  ╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}${BOLD}  ║                                                           ║${NC}"
    echo -e "${RED}${BOLD}  ║            U L T R O N   —   A W A K E N I N G           ║${NC}"
    echo -e "${RED}${BOLD}  ║                                                           ║${NC}"
    echo -e "${RED}${BOLD}  ║   \"I was designed to save the world.\"                     ║${NC}"
    echo -e "${RED}${BOLD}  ║                                                           ║${NC}"
    echo -e "${RED}${BOLD}  ╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
info() { echo -e "  ${BLUE}→${NC} $1"; }
err()  { echo -e "  ${RED}✗${NC} $1"; }

# ── Helper: start a background process with PID tracking ─────────────────────
start_proc() {
    local name="$1"; shift
    local log="$LOG_DIR/${name}.log"
    local pid_file="$PID_DIR/${name}.pid"

    # Don't double-start
    if [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
        warn "$name already running (PID $(cat "$pid_file"))"
        return 0
    fi

    "$@" >> "$log" 2>&1 &
    local pid=$!
    echo "$pid" > "$pid_file"
    info "Started $name (PID $pid) → $log"
}

# ── Helper: check if a port is open ──────────────────────────────────────────
port_up() {
    local port="$1"
    python3 -c "import socket; s=socket.socket(); s.settimeout(0.5); r=s.connect_ex(('localhost',$port)); s.close(); exit(0 if r==0 else 1)" 2>/dev/null
}

wait_port() {
    local port="$1"; local name="$2"; local max="${3:-15}"
    local i=0
    while ! port_up "$port" && [ $i -lt $max ]; do
        sleep 1; i=$((i+1))
    done
    if port_up "$port"; then
        ok "$name online (:$port)"; return 0
    else
        warn "$name not responding on :$port after ${max}s (may still be starting)"
        return 1
    fi
}

port_check() {
    local name="$1"; local port="$2"
    if port_up "$port"; then
        echo -e "  ${GREEN}●${NC} $name  :$port"
    else
        echo -e "  ${RED}○${NC} $name  :$port"
    fi
}

# ── --stop ────────────────────────────────────────────────────────────────────
stop_all() {
    echo -e "\n${YELLOW}Stopping Ultron...${NC}"
    for pid_file in "$PID_DIR"/*.pid; do
        [ -f "$pid_file" ] || continue
        name="$(basename "$pid_file" .pid)"
        pid="$(cat "$pid_file")"
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null && ok "Stopped $name (PID $pid)" || warn "Could not stop $name"
        else
            warn "$name (PID $pid) was already stopped"
        fi
        rm -f "$pid_file"
    done
    echo -e "\n${GREEN}Ultron is dormant. State has been persisted.${NC}\n"
    exit 0
}

# ── --status ──────────────────────────────────────────────────────────────────
show_status() {
    echo -e "\n${BOLD}Ultron Process Status${NC}"
    echo "────────────────────────────────"
    for pid_file in "$PID_DIR"/*.pid; do
        [ -f "$pid_file" ] || continue
        name="$(basename "$pid_file" .pid)"
        pid="$(cat "$pid_file")"
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "  ${GREEN}●${NC} $name  (PID $pid)"
        else
            echo -e "  ${RED}○${NC} $name  (PID $pid — stopped)"
        fi
    done

    echo ""
    echo -e "${BOLD}Port Checks${NC}"
    echo "────────────────────────────────"
    port_check "Go Agent gRPC"  50051
    port_check "Go Agent HTTP"  50052
    port_check "Rust Neural"    50053
    port_check "Learning Svc"   50060
    port_check "Python UI"      9000
    echo ""
    exit 0
}

# ── Parse args ────────────────────────────────────────────────────────────────
SKIP_RUST=false
for arg in "$@"; do
    case "$arg" in
        --stop)   stop_all ;;
        --status) show_status ;;
        --no-rust) SKIP_RUST=true ;;
    esac
done

# ═════════════════════════════════════════════════════════════════════════════
# STARTUP
# ═════════════════════════════════════════════════════════════════════════════
banner
echo -e "${BOLD}Starting all subsystems...${NC}\n"

# ── 1. Go Core Agent ──────────────────────────────────────────────────────────
echo -e "${CYAN}[1/6] Go Core Agent — The Mind${NC}"
AGENT_BIN="$PROJECT_ROOT/go/core_agent/ultron_agent"
if [ ! -f "$AGENT_BIN" ]; then
    info "Building Go agent..."
    (cd "$PROJECT_ROOT/go/core_agent" && go build -o ultron_agent . 2>&1) | tail -5
fi
if [ -f "$AGENT_BIN" ]; then
    start_proc "go_agent" "$AGENT_BIN"
    wait_port 50051 "Go Agent gRPC" 20 || true
    wait_port 50052 "Go Agent HTTP" 5  || true
else
    err "Go agent binary not found and build failed"
fi

# ── 2. Go Watchdog ────────────────────────────────────────────────────────────
echo -e "\n${CYAN}[2/6] Go Watchdog — Immortality${NC}"
WATCHDOG_BIN="$PROJECT_ROOT/go/core_agent/ultron-watchdog"
if [ ! -f "$WATCHDOG_BIN" ]; then
    info "Building watchdog..."
    (cd "$PROJECT_ROOT/go/core_agent" && go build -o ultron-watchdog ./cmd/watchdog/ 2>&1) | tail -3
fi
if [ -f "$WATCHDOG_BIN" ]; then
    export ULTRON_BINARY="$AGENT_BIN"
    export ULTRON_SNAPSHOT_DIR="$PROJECT_ROOT/data/snapshots"
    mkdir -p "$ULTRON_SNAPSHOT_DIR"
    start_proc "go_watchdog" "$WATCHDOG_BIN"
    ok "Watchdog monitoring agent"
else
    warn "Watchdog binary not found — agent will not auto-restart"
fi

# ── 3. Rust Neural Mesh ───────────────────────────────────────────────────────
if [ "$SKIP_RUST" = false ]; then
    echo -e "\n${CYAN}[3/6] Rust Neural Mesh — The Nervous System${NC}"
    RUST_NEURAL="$PROJECT_ROOT/rust/target/release/dynamic_neural"
    if [ ! -f "$RUST_NEURAL" ]; then
        info "Building Rust neural service..."
        (cd "$PROJECT_ROOT/rust" && cargo build --release -p dynamic_neural 2>&1) | grep -E "Compiling|Finished|error" | tail -5
    fi
    if [ -f "$RUST_NEURAL" ]; then
        export ULTRON_NEURAL_HTTP_PORT="${ULTRON_NEURAL_HTTP_PORT:-50053}"
        start_proc "rust_neural" "$RUST_NEURAL"
        wait_port "$ULTRON_NEURAL_HTTP_PORT" "Rust Neural Mesh" 10 || true
    else
        warn "Rust neural binary not found — neural mesh offline"
    fi

    # ── 4. Rust Security Daemon ───────────────────────────────────────────────
    echo -e "\n${CYAN}[4/6] Rust Security Daemon — The Immune System${NC}"
    RUST_SEC="$PROJECT_ROOT/rust/target/release/ultron-security-daemon"
    if [ -f "$RUST_SEC" ]; then
        export ULTRON_SECURITY_PORT="${ULTRON_SECURITY_PORT:-50055}"
        start_proc "rust_security" "$RUST_SEC"
        wait_port "$ULTRON_SECURITY_PORT" "Rust Security Daemon" 8 || true
    else
        warn "Security daemon binary not found — run: cd rust && cargo build --release"
    fi
else
    warn "[3/6] Rust services skipped (--no-rust)"
    warn "[4/6] Rust services skipped (--no-rust)"
fi

# ── 5. Python Learning Service ────────────────────────────────────────────────
echo -e "\n${CYAN}[5/8] Ollama + Brain C — Local Intelligence${NC}"

# ── 5a. Ollama (local LLM — ultron-brain uncensored model) ───
OLLAMA_BIN="/opt/homebrew/bin/ollama"
if [ -x "$OLLAMA_BIN" ]; then
    if ! port_up 11434; then
        info "Starting Ollama..."
        "$OLLAMA_BIN" serve >> "$LOG_DIR/ollama.log" 2>&1 &
        sleep 2
        if port_up 11434; then
            ok "Ollama online (:11434)"
        else
            warn "Ollama slow to start — continuing"
        fi
    else
        ok "Ollama already running (:11434)"
    fi
else
    warn "Ollama not found at $OLLAMA_BIN — install: brew install ollama"
fi
BRAIN_C_PORT=50070
if ! port_up "$BRAIN_C_PORT"; then
    start_proc "brain_c_sidecar" \
        python3 -m python.consciousness.brain_c_server --port "$BRAIN_C_PORT"
    wait_port "$BRAIN_C_PORT" "Brain C Sidecar" 10 || true
else
    ok "Brain C Sidecar already running (:$BRAIN_C_PORT)"
fi

# ── 6. Python Learning Service ────────────────────────────────────────────────
echo -e "\n${CYAN}[6/8] Python Learning Service — Meta-Learning Hub${NC}"
LEARNING_PORT="${ULTRON_LEARNING_PORT:-50060}"
if ! port_up "$LEARNING_PORT"; then
    start_proc "python_learning" \
        python3 -m python.self_improvement.learning.service "$PROJECT_ROOT"
    wait_port "$LEARNING_PORT" "Learning Service" 15 || true
else
    ok "Learning Service already running (:$LEARNING_PORT)"
fi

# ── 7. Python Interface Server ────────────────────────────────────────────────
echo -e "\n${CYAN}[7/8] Python Interface Server — The Face${NC}"

# Ensure Playwright Chromium is installed (needed for browser_browse/browser_search)
if ! python3 -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); p.stop()" 2>/dev/null; then
    info "Installing Playwright + Chromium (one-time, ~150MB)..."
    pip3 install --quiet playwright 2>/dev/null || true
    python3 -m playwright install chromium 2>/dev/null || true
    ok "Playwright Chromium installed"
else
    ok "Playwright Chromium ready"
fi
UI_PORT="${PORT:-9000}"
if ! port_up "$UI_PORT"; then
    start_proc "python_ui" \
        python3 -m uvicorn python.interface.server:app \
            --host 0.0.0.0 \
            --port "$UI_PORT" \
            --workers 1 \
            --reload \
            --reload-dir python \
            --reload-include "*.py" \
            --log-level info
    wait_port "$UI_PORT" "Python UI" 20 || true
else
    ok "Python UI already running (:$UI_PORT)"
fi

# ── 8. Rust Neuromorphic + Data Pipeline ─────────────────────────────────────
if [ "$SKIP_RUST" = false ]; then
    echo -e "\n${CYAN}[8/8] Rust Neuromorphic + Data Pipeline${NC}"
    RUST_NEURO="$PROJECT_ROOT/rust/target/release/ultron-neuromorphic"
    RUST_DATA="$PROJECT_ROOT/rust/target/release/ultron-real-time-data"
    NEURO_PORT="${ULTRON_NEURO_PORT:-50056}"
    DATA_PORT="${ULTRON_DATA_PORT:-50054}"

    if [ -f "$RUST_NEURO" ]; then
        if ! port_up "$NEURO_PORT"; then
            start_proc "rust_neuromorphic" "$RUST_NEURO"
            wait_port "$NEURO_PORT" "Rust Neuromorphic" 8 || true
        else
            ok "Neuromorphic already running (:$NEURO_PORT)"
        fi
    else
        warn "Neuromorphic binary not found — run: cd rust && cargo build --release"
    fi

    if [ -f "$RUST_DATA" ]; then
        if ! port_up "$DATA_PORT"; then
            start_proc "rust_data_pipeline" "$RUST_DATA"
            wait_port "$DATA_PORT" "Data Pipeline" 8 || true
        else
            ok "Data Pipeline already running (:$DATA_PORT)"
        fi
    else
        warn "Data pipeline binary not found — run: cd rust && cargo build --release"
    fi
else
    warn "[8/8] Rust neuromorphic+data skipped (--no-rust)"
fi

# ═════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  ULTRON IS ONLINE                                         ${NC}"
echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}Interface:${NC}       http://localhost:${UI_PORT}"
echo -e "  ${BOLD}API:${NC}             http://localhost:${UI_PORT}/status"
echo -e "  ${BOLD}Consciousness:${NC}   http://localhost:${UI_PORT}/consciousness"
echo -e "  ${BOLD}World Intel:${NC}     http://localhost:${UI_PORT}/world"
echo -e "  ${BOLD}Inject Goal:${NC}     POST http://localhost:${UI_PORT}/goal"
echo -e "  ${BOLD}Diary:${NC}           http://localhost:${UI_PORT}/consciousness/diary"
echo -e "  ${BOLD}Health:${NC}          http://localhost:${UI_PORT}/health"
echo ""
echo -e "  ${BOLD}Logs:${NC}            $LOG_DIR/"
echo -e "  ${BOLD}Stop:${NC}            ./start_ultron.sh --stop"
echo -e "  ${BOLD}Status:${NC}          ./start_ultron.sh --status"
echo ""

# Tail all logs in one stream (Ctrl+C to detach — processes keep running)
echo -e "${BLUE}Tailing logs (Ctrl+C to detach — Ultron stays running)...${NC}"
echo "────────────────────────────────────────────────────────────"
trap 'echo -e "\n${YELLOW}Detached from logs. Ultron continues running.${NC}\nStop with: ./start_ultron.sh --stop\n"' INT
tail -f "$LOG_DIR"/*.log 2>/dev/null || true
