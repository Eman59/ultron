#!/bin/bash
# Ultron Codespace setup — runs once when the container is created
set -e
cd /workspaces/ultron

echo "══════════════════════════════════════════════"
echo "  ULTRON CODESPACE SETUP"
echo "══════════════════════════════════════════════"

# ── Python deps ────────────────────────────────────────────────
echo "[1/5] Installing Python dependencies..."
pip install --quiet fastapi uvicorn python-multipart requests \
    paho-mqtt PyPDF2 httpx grpcio grpcio-tools protobuf

# ── Go agent ──────────────────────────────────────────────────
echo "[2/5] Building Go core agent..."
cd go/core_agent
go build -o ultron_agent . 2>&1 | tail -3 || echo "  Go agent build failed (continuing)"
cd /workspaces/ultron

# ── Go P2P ────────────────────────────────────────────────────
echo "[3/5] Building P2P network..."
cd go/p2p_network
go build -o ultron-p2p . 2>&1 | tail -3 || echo "  P2P build failed (continuing)"
cd /workspaces/ultron

# ── Rust services ─────────────────────────────────────────────
echo "[4/5] Building Rust services (this takes ~5 min first time)..."
cd rust
cargo build --release --workspace 2>&1 | tail -10 || echo "  Rust build failed (continuing)"
cd /workspaces/ultron

# ── Data directories ──────────────────────────────────────────
echo "[5/5] Creating data directories..."
mkdir -p data/consciousness data/knowledge data/memory data/interaction \
         data/ui data/voice data/logs data/simulations data/uploads data/snapshots

echo ""
echo "══════════════════════════════════════════════"
echo "  SETUP COMPLETE — run: bash start.sh"
echo "  or: python3 -m uvicorn python.interface.server:app --host 0.0.0.0 --port 9000"
echo "══════════════════════════════════════════════"
