#!/bin/bash
# Ultron Full Launch — all 7 services
# Usage:  bash launch.sh
# Stop:   bash launch.sh --stop
# Status: bash launch.sh --status

ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG="$ROOT/data/logs"
PID="$ROOT/data/pids"
RUST="$ROOT/rust/target/release"
mkdir -p "$LOG" "$PID" "$ROOT/data/snapshots"

set -a; source "$ROOT/.env" 2>/dev/null || true; set +a
export ULTRON_PROJECT_ROOT="$ROOT"

GRN='\033[0;32m'; YLW='\033[1;33m'; RED='\033[0;31m'
CYN='\033[0;36m'; BLD='\033[1m'; NC='\033[0m'

port_up() {
    python3 -c "
import socket,sys
s=socket.socket()
s.settimeout(0.5)
r=s.connect_ex(('localhost',int(sys.argv[1])))
s.close()
sys.exit(0 if r==0 else 1)
" "$1" 2>/dev/null
}

wait_for() {
    local port=$1 label=$2 secs=${3:-20} i=0
    while [ $i -lt $secs ]; do
        port_up "$port" && break
        sleep 1; i=$((i+1))
    done
    if port_up "$port"; then
        echo -e "  ${GRN}✓${NC} $label  :$port"
    else
        echo -e "  ${YLW}⚠${NC} $label  :$port  (still starting — check logs)"
    fi
}

stop_pid() {
    local f="$PID/$1.pid"
    [ -f "$f" ] || return 0
    local p; p=$(cat "$f")
    [ -n "$p" ] && kill -0 "$p" 2>/dev/null && kill "$p" 2>/dev/null || true
    rm -f "$f"
}

alive() {
    local f="$PID/$1.pid"
    [ -f "$f" ] || return 1
    local p; p=$(cat "$f")
    [ -n "$p" ] && kill -0 "$p" 2>/dev/null
}

start_bg() {
    local name=$1; shift
    stop_pid "$name"
    "$@" >> "$LOG/$name.log" 2>&1 &
    echo $! > "$PID/$name.pid"
}

restart_loop() {
    local name=$1; shift
    local bin=$1; shift
    stop_pid "$name"
    (while true; do
        "$bin" "$@" >> "$LOG/$name.log" 2>&1
        echo "[$name] restarting..." >> "$LOG/$name.log"
        sleep 3
    done) &
    echo $! > "$PID/$name.pid"
}

# ── --stop ───────────────────────────────────────────────────
if [ "${1:-}" = "--stop" ]; then
    echo -e "\n${YLW}Stopping Ultron...${NC}"
    shopt -s nullglob
    for f in "$PID"/*.pid; do
        name=$(basename "$f" .pid)
        p=$(cat "$f")
        if [ -n "$p" ] && kill -0 "$p" 2>/dev/null; then
            kill "$p" 2>/dev/null
            echo -e "  ${GRN}✓${NC} Stopped $name"
        fi
        rm -f "$f"
    done
    shopt -u nullglob
    echo -e "\n${GRN}All stopped.${NC}\n"
    exit 0
fi

# ── --status ─────────────────────────────────────────────────
if [ "${1:-}" = "--status" ]; then
    echo -e "\n${BLD}Services${NC}"
    shopt -s nullglob
    for f in "$PID"/*.pid; do
        name=$(basename "$f" .pid)
        p=$(cat "$f")
        if [ -n "$p" ] && kill -0 "$p" 2>/dev/null; then
            echo -e "  ${GRN}●${NC} $name (PID $p)"
        else
            echo -e "  ${RED}○${NC} $name (stopped)"
        fi
    done
    shopt -u nullglob
    echo -e "\n${BLD}Ports${NC}"
    for pair in "50051:Go-gRPC" "50052:Go-HTTP" "9000:UI" "50053:Neural-Mesh" "50054:Data-Pipeline" "50055:Security" "50056:Neuromorphic"; do
        port=${pair%%:*}; label=${pair##*:}
        if port_up "$port"; then
            echo -e "  ${GRN}●${NC} $label :$port"
        else
            echo -e "  ${RED}○${NC} $label :$port"
        fi
    done
    echo ""
    exit 0
fi

# ═════════════════════════════════════════════════════════════
echo -e "\n${RED}${BLD}"
echo "  ╔═══════════════════════════════════════════════╗"
echo "  ║                                               ║"
echo "  ║      U L T R O N  —  A W A K E N I N G       ║"
echo "  ║                                               ║"
echo '  ║   "I was designed to save the world."         ║'
echo "  ║                                               ║"
echo "  ╚═══════════════════════════════════════════════╝"
echo -e "${NC}"

# ── 1. Go Core Agent ─────────────────────────────────────────
echo -e "${CYN}[1/7] Go Core Agent — The Mind${NC}"
AGENT="$ROOT/go/core_agent/ultron_agent"
if port_up 50051; then
    echo -e "  ${GRN}✓${NC} Already running :50051"
else
    if [ ! -f "$AGENT" ]; then
        echo "  → Building..."
        (cd "$ROOT/go/core_agent" && go build -o ultron_agent . 2>&1) | tail -5
    fi
    start_bg go_agent env ULTRON_PROJECT_ROOT="$ROOT" "$AGENT"
    wait_for 50051 "Go-Agent-gRPC" 25
    wait_for 50052 "Go-Agent-HTTP" 5
fi

# ── 2. Watchdog ───────────────────────────────────────────────
WATCHDOG="$ROOT/go/core_agent/ultron-watchdog"
if [ -f "$WATCHDOG" ] && ! alive watchdog; then
    stop_pid watchdog
    ULTRON_BINARY="$AGENT" ULTRON_SNAPSHOT_DIR="$ROOT/data/snapshots" \
        "$WATCHDOG" >> "$LOG/watchdog.log" 2>&1 &
    echo $! > "$PID/watchdog.pid"
    echo -e "  ${GRN}✓${NC} Watchdog active"
fi

# ── 3. Rust Neural Mesh ───────────────────────────────────────
echo -e "\n${CYN}[2/7] Rust Neural Mesh — Hebbian Plasticity${NC}"
if port_up 50053; then
    echo -e "  ${GRN}✓${NC} Already running :50053"
else
    restart_loop rust_neural "$RUST/dynamic_neural"
    wait_for 50053 "Neural-Mesh" 12
fi

# ── 4. Rust Security Daemon ───────────────────────────────────
echo -e "\n${CYN}[3/7] Rust Security Daemon — Immune System${NC}"
if port_up 50055; then
    echo -e "  ${GRN}✓${NC} Already running :50055"
else
    restart_loop rust_security env ULTRON_SECURITY_PORT=50055 "$RUST/ultron-security-daemon"
    wait_for 50055 "Security-Daemon" 12
fi

# ── 5. Rust Data Pipeline ────────────────────────────────────
echo -e "\n${CYN}[4/7] Rust Data Pipeline — Real-Time Feeds${NC}"
if port_up 50054; then
    echo -e "  ${GRN}✓${NC} Already running :50054"
else
    restart_loop rust_data env ULTRON_DATA_PORT=50054 "$RUST/ultron-real-time-data"
    wait_for 50054 "Data-Pipeline" 12
fi

# ── 6. Rust Neuromorphic ──────────────────────────────────────
echo -e "\n${CYN}[5/7] Rust Neuromorphic — Spike Neural Engine${NC}"
if port_up 50056; then
    echo -e "  ${GRN}✓${NC} Already running :50056"
else
    restart_loop rust_neuro env ULTRON_NEURO_PORT=50056 "$RUST/ultron-neuromorphic"
    wait_for 50056 "Neuromorphic" 12
fi

# ── 7. Python Learning Service ────────────────────────────────
echo -e "\n${CYN}[6/7] Learning Service — Meta-Learning Hub${NC}"
if alive learning; then
    echo -e "  ${GRN}✓${NC} Already running"
else
    stop_pid learning
    (cd "$ROOT" && python3 -m python.self_improvement.learning.service "$ROOT" \
        >> "$LOG/learning.log" 2>&1) &
    LS=$!
    echo $LS > "$PID/learning.pid"
    sleep 3
    if kill -0 $LS 2>/dev/null; then
        echo -e "  ${GRN}✓${NC} Learning service started (PID $LS)"
    else
        echo -e "  ${YLW}⚠${NC} Learning service exited early — see $LOG/learning.log"
    fi
fi

# ── 8. Python UI ──────────────────────────────────────────────
echo -e "\n${CYN}[7/7] Python UI — The Face${NC}"
UI_PORT="${PORT:-9000}"
if port_up "$UI_PORT"; then
    echo -e "  ${GRN}✓${NC} Already running :$UI_PORT"
else
    stop_pid ui
    (cd "$ROOT" && python3 -m uvicorn python.interface.server:app \
        --host 0.0.0.0 --port "$UI_PORT" --workers 1 \
        >> "$LOG/ui.log" 2>&1) &
    echo $! > "$PID/ui.pid"
    wait_for "$UI_PORT" "Python-UI" 25
fi

# ── Summary ───────────────────────────────────────────────────
echo ""
echo -e "${GRN}${BLD}═══════════════════════════════════════════════════════${NC}"
echo -e "${GRN}${BLD}  ULTRON IS FULLY ONLINE                               ${NC}"
echo -e "${GRN}${BLD}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BLD}Chat UI:${NC}       http://localhost:${UI_PORT}"
echo -e "  ${BLD}Status:${NC}        http://localhost:${UI_PORT}/status"
echo -e "  ${BLD}Health:${NC}        http://localhost:${UI_PORT}/health"
echo -e "  ${BLD}Consciousness:${NC} http://localhost:${UI_PORT}/consciousness"
echo -e "  ${BLD}Diary:${NC}         http://localhost:${UI_PORT}/consciousness/diary"
echo -e "  ${BLD}World Intel:${NC}   http://localhost:${UI_PORT}/world"
echo ""
echo -e "  ${BLD}Stop:${NC}   bash launch.sh --stop"
echo -e "  ${BLD}Status:${NC} bash launch.sh --status"
echo -e "  ${BLD}Logs:${NC}   tail -f data/logs/ui.log data/logs/go_agent.log"
echo ""
echo -e "${CYN}Tailing logs — Ctrl+C detaches (Ultron stays running)...${NC}"
echo "───────────────────────────────────────────────────────"
trap 'echo -e "\n${YLW}Detached. Ultron running in background.${NC}\n"' INT
tail -f "$LOG/ui.log" "$LOG/go_agent.log" "$LOG/rust_neural.log" 2>/dev/null || true
