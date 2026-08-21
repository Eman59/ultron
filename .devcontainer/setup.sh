#!/bin/bash
# Ultron Codespace setup — runs once when the container is created
set -e
cd /workspaces/ultron

echo "══════════════════════════════════════════════"
echo "  ULTRON CODESPACE SETUP"
echo "══════════════════════════════════════════════"

# ── Write env vars to ~/.bashrc so they survive every terminal session ─────
# These are read from the Codespace secrets OR from the values below.
# Best practice: set CF_ACCOUNT_ID and CF_API_TOKEN as Codespace Secrets at
# https://github.com/settings/codespaces so they aren't in the file.
cat >> ~/.bashrc << 'ENVEOF'

# ── Ultron environment ─────────────────────────────────────────
export PYTHONPATH="/workspaces/ultron"
export ULTRON_PROJECT_ROOT="/workspaces/ultron"
export PORT="9000"
ENVEOF

# Also export for this session
export PYTHONPATH="/workspaces/ultron"
export ULTRON_PROJECT_ROOT="/workspaces/ultron"
export PORT="9000"

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

# ── Write a quick launch script ───────────────────────────────
cat > ~/launch_ultron.sh << 'LAUNCHEOF'
#!/bin/bash
# Quick launch — just run: bash ~/launch_ultron.sh
source ~/.bashrc
cd /workspaces/ultron
exec bash start.sh
LAUNCHEOF
chmod +x ~/launch_ultron.sh

echo ""
echo "══════════════════════════════════════════════"
echo "  SETUP COMPLETE"
echo ""
echo "  To start Ultron, run ONE of these:"
echo ""
echo "  Option A (with your CF keys):"
echo "  CF_ACCOUNT_ID=your_id CF_API_TOKEN=your_token bash start.sh"
echo ""
echo "  Option B (if secrets are set in GitHub Codespace Settings):"
echo "  bash start.sh"
echo ""
echo "  The UI will open automatically at port 9000."
echo "══════════════════════════════════════════════"
