#!/bin/bash
# Generate gRPC stubs from proto definitions for all languages.
#
# Prerequisites:
#   pip install grpcio-tools
#   go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
#   go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
#   cargo install protobuf-codegen grpcio-compiler  (or use tonic-build)
#
# Usage: ./proto/generate.sh

set -e

PROTO_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$PROTO_DIR")"

echo "=== Generating gRPC stubs ==="
echo "Proto dir: $PROTO_DIR"
echo "Project root: $PROJECT_ROOT"

# ━━━━ Python ━━━━
echo ""
echo "[Python] Generating stubs..."
PYTHON_OUT="$PROJECT_ROOT/python/self_improvement/learning/proto"
mkdir -p "$PYTHON_OUT"

python3 -m grpc_tools.protoc \
    --proto_path="$PROTO_DIR" \
    --python_out="$PYTHON_OUT" \
    --grpc_python_out="$PYTHON_OUT" \
    --pyi_out="$PYTHON_OUT" \
    "$PROTO_DIR/learning_service.proto"

# Fix imports in generated files (Python needs relative imports)
touch "$PYTHON_OUT/__init__.py"
echo "  Generated: $PYTHON_OUT/learning_service_pb2.py"
echo "  Generated: $PYTHON_OUT/learning_service_pb2_grpc.py"

# ━━━━ Go ━━━━
echo ""
echo "[Go] Generating stubs..."
GO_OUT="$PROJECT_ROOT/go/core_agent/proto/learning"
mkdir -p "$GO_OUT"

protoc \
    --proto_path="$PROTO_DIR" \
    --go_out="$GO_OUT" \
    --go_opt=paths=source_relative \
    --go-grpc_out="$GO_OUT" \
    --go-grpc_opt=paths=source_relative \
    "$PROTO_DIR/learning_service.proto"

echo "  Generated: $GO_OUT/learning_service.pb.go"
echo "  Generated: $GO_OUT/learning_service_grpc.pb.go"

# ━━━━ Rust (using tonic) ━━━━
echo ""
echo "[Rust] Proto configured for tonic-build (runs during cargo build)"
RUST_PROTO="$PROJECT_ROOT/rust/dynamic_neural/proto"
mkdir -p "$RUST_PROTO"
cp "$PROTO_DIR/learning_service.proto" "$RUST_PROTO/"
echo "  Copied proto to: $RUST_PROTO/learning_service.proto"

# Create build.rs for tonic
BUILD_RS="$PROJECT_ROOT/rust/dynamic_neural/build.rs"
if [ ! -f "$BUILD_RS" ]; then
cat > "$BUILD_RS" << 'EOF'
fn main() -> Result<(), Box<dyn std::error::Error>> {
    tonic_build::compile_protos("proto/learning_service.proto")?;
    Ok(())
}
EOF
echo "  Created: $BUILD_RS"
fi

echo ""
echo "=== Done ==="
echo "Python stubs: $PYTHON_OUT"
echo "Go stubs:     $GO_OUT"
echo "Rust proto:   $RUST_PROTO (compiled at build time by tonic)"
