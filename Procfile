# ═══════════════════════════════════════════════════════════════
# ULTRON PROCESS DEFINITIONS
# Start all: honcho start   OR   foreman start
# Start one: honcho start web
# ═══════════════════════════════════════════════════════════════

# ── Python UI Server ────────────────────────────────────────────
web: python3 -m uvicorn python.interface.server:app --host 0.0.0.0 --port ${PORT:-9000}

# ── Go Core Agent (OODA loop, Brain A+B, Immortality, Self-Mod) ─
agent: ULTRON_PROJECT_ROOT=$(pwd) go/core_agent/ultron_agent

# ── Watchdog (keeps agent alive after crashes, snapshots state) ─
watchdog: ULTRON_BINARY=$(pwd)/go/core_agent/ultron_agent ULTRON_SNAPSHOT_DIR=$(pwd)/data/snapshots go/core_agent/ultron-watchdog

# ── Unified Learning Service (pattern recognition, distillation) ─
learning: python3 -m python.self_improvement.learning.service $(pwd)

# ── P2P Distributed Consciousness Network (libp2p mesh) ─────────
p2p: go/p2p_network/ultron-p2p
