# Generate gRPC code from protobuf definitions
# Prerequisites: protoc, protoc-gen-go, protoc-gen-go-grpc, grpcio-tools (Python)

.PHONY: all go python rust clean

PROTO_DIR := .
GO_OUT := ../go/core_agent/proto/gen
PYTHON_OUT := ../python/proto/gen
RUST_OUT := ../rust/proto/gen

all: go python

go:
	@mkdir -p $(GO_OUT)
	protoc \
		--proto_path=$(PROTO_DIR) \
		--go_out=$(GO_OUT) \
		--go_opt=paths=source_relative \
		--go-grpc_out=$(GO_OUT) \
		--go-grpc_opt=paths=source_relative \
		$(PROTO_DIR)/ultron_core.proto
	@echo "✓ Go gRPC code generated in $(GO_OUT)"

python:
	@mkdir -p $(PYTHON_OUT)
	python -m grpc_tools.protoc \
		--proto_path=$(PROTO_DIR) \
		--python_out=$(PYTHON_OUT) \
		--grpc_python_out=$(PYTHON_OUT) \
		$(PROTO_DIR)/ultron_core.proto
	@echo "✓ Python gRPC code generated in $(PYTHON_OUT)"

rust:
	@mkdir -p $(RUST_OUT)
	protoc \
		--proto_path=$(PROTO_DIR) \
		--rust_out=$(RUST_OUT) \
		$(PROTO_DIR)/ultron_core.proto
	@echo "✓ Rust protobuf code generated in $(RUST_OUT)"

clean:
	rm -rf $(GO_OUT) $(PYTHON_OUT) $(RUST_OUT)
	@echo "✓ Cleaned generated code"
