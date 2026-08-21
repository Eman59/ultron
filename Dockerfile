# ╔══════════════════════════════════════════════════════════════╗
# ║  ULTRON — Full Stack Docker (Back4app $5/mo · 512 MB RAM)   ║
# ║                                                              ║
# ║  Stage 1: Build Go binaries   (golang:1.22)                  ║
# ║  Stage 2: Build Rust binaries (rust:1.78-slim)               ║
# ║  Stage 3: Final runtime image (python:3.11-slim)             ║
# ║                                                              ║
# ║  Final image contains:                                       ║
# ║   • Python server  (FastAPI + all modules)                   ║
# ║   • Go core agent  (OODA 50ms loop)                          ║
# ║   • Go watchdog    (immortality — restarts agent on crash)   ║
# ║   • Go P2P node    (distributed consciousness)               ║
# ║   • Rust neural    (Hebbian plasticity + hot-swap)           ║
# ║   • Rust security  (SHA-256 integrity monitoring)            ║
# ║   • Rust data pipe (live feeds: HN / crypto / weather)       ║
# ║   • Rust neuro     (LIF spiking neurons)                     ║
# ╚══════════════════════════════════════════════════════════════╝

# ──────────────────────────────────────────────────────────────
# STAGE 1 — Build Go binaries
# ──────────────────────────────────────────────────────────────
FROM golang:1.22-bookworm AS go-builder

WORKDIR /build

# Copy Go modules first for cache
COPY go/core_agent/go.mod go/core_agent/go.sum ./go/core_agent/
COPY go/p2p_network/go.mod go/p2p_network/go.sum ./go/p2p_network/

# Download deps
RUN cd go/core_agent && go mod download
RUN cd go/p2p_network && go mod download

# Copy source
COPY go/ ./go/
COPY proto/ ./proto/

# Build core agent
RUN cd go/core_agent && \
    CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -ldflags="-s -w" -o /out/ultron_agent . 2>&1 || \
    echo "[GO] core_agent build failed — continuing without it"

# Build watchdog
RUN cd go/core_agent && \
    CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -ldflags="-s -w" -o /out/ultron-watchdog ./cmd/watchdog/ 2>&1 || \
    echo "[GO] watchdog build failed — continuing"

# Build P2P network
RUN cd go/p2p_network && \
    CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -ldflags="-s -w" -o /out/ultron-p2p . 2>&1 || \
    echo "[GO] p2p build failed — continuing"


# ──────────────────────────────────────────────────────────────
# STAGE 2 — Build Rust binaries
# ──────────────────────────────────────────────────────────────
FROM rust:1.78-slim-bookworm AS rust-builder

# Rust deps: openssl for any TLS, pkg-config
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config libssl-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy Cargo workspace
COPY rust/Cargo.toml rust/Cargo.lock ./
COPY rust/dynamic_neural/        ./dynamic_neural/
COPY rust/real_time_data/        ./real_time_data/
COPY rust/security_daemon/       ./security_daemon/
COPY rust/neuromorphic/          ./neuromorphic/
COPY rust/ultron_neural_service/ ./ultron_neural_service/

# Build all Rust binaries — thin LTO for faster build, smaller bins
ENV CARGO_PROFILE_RELEASE_LTO=thin
ENV CARGO_INCREMENTAL=0
RUN cargo build --release --workspace 2>&1 | tail -5 || \
    echo "[RUST] Some binaries failed — continuing with what built"

# Collect built binaries
RUN mkdir -p /out && \
    for bin in ultron-neural-service ultron-security-daemon \
               ultron-real-time-data ultron-neuromorphic; do \
        if [ -f "target/release/$bin" ]; then \
            cp "target/release/$bin" /out/; \
            echo "  ✓ $bin"; \
        else \
            echo "  ✗ $bin (not built)"; \
        fi; \
    done


# ──────────────────────────────────────────────────────────────
# STAGE 3 — Final runtime image
# ──────────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS runtime

# System tools: ffmpeg (voice), curl (health), sox (voice listener)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl sox \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python deps ────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy compiled binaries ─────────────────────────────────────
# Go binaries → go/core_agent/ and go/p2p_network/ (paths the start script expects)
RUN mkdir -p go/core_agent go/p2p_network
COPY --from=go-builder   /out/ultron_agent     go/core_agent/ultron_agent
COPY --from=go-builder   /out/ultron-watchdog  go/core_agent/ultron-watchdog
COPY --from=go-builder   /out/ultron-p2p       go/p2p_network/ultron-p2p
RUN chmod +x go/core_agent/ultron_agent go/core_agent/ultron-watchdog go/p2p_network/ultron-p2p \
    2>/dev/null || true

# Rust binaries → rust/target/release/ (paths start_railway.sh expects)
RUN mkdir -p rust/target/release
COPY --from=rust-builder /out/ rust/target/release/
RUN chmod +x rust/target/release/* 2>/dev/null || true

# ── Copy Python project ────────────────────────────────────────
COPY python/  ./python/
COPY proto/   ./proto/
COPY integration/ ./integration/
COPY julia/   ./julia/
COPY data/    ./data/
COPY .env     ./.env 2>/dev/null || true

# ── Create runtime data directories ───────────────────────────
RUN mkdir -p data/consciousness data/knowledge data/memory \
    data/interaction data/ui data/voice data/logs \
    data/simulations data/uploads data/snapshots

# ── Copy the unified start script ─────────────────────────────
COPY start.sh ./start.sh
RUN chmod +x start.sh

EXPOSE 8000

CMD ["./start.sh"]
