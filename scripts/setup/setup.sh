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

# Setup Go components
echo "Setting up Go components..."
cd ../go/p2p_network
go mod download
go build -o ultron-p2p ./cmd/main.go
echo "✓ Go components built"
echo

# Setup Julia components
echo "Setting up Julia components..."
cd ../../julia
julia -e 'using Pkg; Pkg.activate("."); Pkg.instantiate()'
echo "✓ Julia environment setup complete"
echo

# Setup Docker
echo "Setting up Docker containers..."
cd ../docker
docker-compose build
echo "✓ Docker images built"
echo

# Create data directories
echo "Creating data directories..."
mkdir -p ../data/simulations
mkdir -p ../data/real_time_feeds
mkdir -p ../experiments/neural_evolution
mkdir -p ../experiments/learning_strategies
echo "✓ Data directories created"
echo

# Generate protobuf files
echo "Generating protobuf definitions..."
cd ../integration/grpc_services
./generate_protos.sh
echo "✓ Protobuf definitions generated"
echo

echo "================================================"
echo "  Setup Complete!"
echo "================================================"
echo
echo "To start the system:"
echo "  cd docker && docker-compose up"
echo
echo "To run individual components:"
echo "  Python: source python/venv/bin/activate && python -m meta_learning"
echo "  Rust: cd rust && cargo run --bin dynamic_neural"
echo "  Go: cd go/p2p_network && ./ultron-p2p"
echo "  Julia: cd julia && julia --project=. emotional_modeling.jl"
echo
echo "Research interfaces:"
echo "  Jupyter: http://localhost:8888"
echo "  Grafana: http://localhost:3000"
echo "  gRPC Gateway: http://localhost:8080"
echo