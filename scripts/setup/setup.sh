#!/bin/bash

set -e

echo "================================================"
echo "  Ultron AI Research System - Setup Script"
echo "================================================"
echo

# Check prerequisites
echo "Checking prerequisites..."
command -v python3 >/dev/null 2>&1 || { echo "Python3 is required but not installed. Aborting." >&2; exit 1; }
command -v rustc >/dev/null 2>&1 || { echo "Rust is required but not installed. Aborting." >&2; exit 1; }
command -v go >/dev/null 2>&1 || { echo "Go is required but not installed. Aborting." >&2; exit 1; }
command -v julia >/dev/null 2>&1 || { echo "Julia is required but not installed. Aborting." >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "Docker is required but not installed. Aborting." >&2; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "Docker Compose is required but not installed. Aborting." >&2; exit 1; }

echo "✓ All prerequisites found"
echo

# Create Python virtual environment
echo "Setting up Python environment..."
cd ../python
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "✓ Python environment setup complete"
echo

# Setup Rust components
echo "Setting up Rust components..."
cd ../../rust
cargo build --release
echo "✓ Rust components built"
echo

# Setup Go components (core_agent only — p2p_network directory does not exist yet)
echo "Setting up Go core agent..."
cd ../go/core_agent
go mod download
go build -o ultron-agent ./
echo "✓ Go core agent built"
echo

# Setup Docker
echo "Setting up Docker containers..."
cd ../../docker
docker-compose build
echo "✓ Docker images built"
echo

# Create data directories
echo "Creating data directories..."
mkdir -p ../data/simulations
mkdir -p ../data/real_time_feeds
mkdir -p ../data/consciousness
mkdir -p ../data/knowledge
mkdir -p ../data/snapshots
echo "✓ Data directories created"
echo

# Generate protobuf files (learning_service only — others require manual setup)
echo "Generating protobuf definitions..."
if [ -f "../proto/generate.sh" ]; then
    cd ../proto && bash generate.sh
    echo "✓ Protobuf definitions generated"
else
    echo "⚠ proto/generate.sh not found — skipping proto generation"
fi
echo

echo "================================================"
echo "  Setup Complete!"
echo "================================================"
echo
echo "To start the system:"
echo "  cd docker && docker-compose up"
echo
echo "To run individual components:"
echo "  Python: source python/venv/bin/activate && python -m python.interface.server"
echo "  Rust: cd rust && cargo run --bin dynamic_neural"
echo "  Go: cd go/core_agent && ./ultron-agent"
echo
echo "Research interfaces:"
echo "  Grafana:  http://localhost:3000"
echo "  Neo4j:    http://localhost:7474"
echo "  gRPC:     localhost:50051"
echo "  HTTP:     http://localhost:8080"
echo