"""
Ultron Self-Learning System — Main Entry Point.

This is what gets executed when you run:
    python -m python.self_improvement.learning

It boots the ENTIRE self-learning stack:
  1. Experience Collector (captures everything)
  2. Pattern Recognizer (finds meaning)
  3. Code Introspector (understands the codebase)
  4. Adaptive Optimizer (generates improvements)
  5. Knowledge Distiller (permanent learning)
  6. LLM Brain (real intelligence)
  7. Intelligent Patcher (AI-powered code writing)
  8. Codebase Agent (filesystem access)
  9. Evolution Controller (orchestration)
  10. Bootstrap (cold-start data seeding)
  11. Continuous Learner (brain retraining)
  12. HTTP Health Server (monitoring)
  13. JSON API Server (cross-language communication)

Usage:
    python -m python.self_improvement.learning [project_root] [port]
    
Environment variables:
    ULTRON_PROJECT_ROOT     — Project directory (default: current dir)
    ULTRON_LEARNING_PORT    — gRPC/JSON port (default: 50060)
    OPENAI_API_KEY          — For GPT-4 (optional)
    ANTHROPIC_API_KEY       — For Claude (optional)
    OLLAMA_HOST             — Local LLM URL (default: http://localhost:11434)
"""

import sys
import os
import time
import signal
import threading
import json
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

# Add project root to path
PROJECT_ROOT = os.environ.get("ULTRON_PROJECT_ROOT", os.getcwd())
sys.path.insert(0, PROJECT_ROOT)

from python.self_improvement.learning.service import UnifiedLearningService
from python.self_improvement.learning.bootstrap import Bootstrap


class HealthHandler(BaseHTTPRequestHandler):
    """Simple HTTP health check endpoint."""
    
    service: UnifiedLearningService = None  # Set by main()
    
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {
                "status": "healthy",
                "uptime": time.time() - self.server.start_time,
                "service": "ultron-learning",
            }
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == "/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            try:
                status = HealthHandler.service.controller.get_status() if HealthHandler.service else {}
                self.wfile.write(json.dumps(status, default=str).encode())
            except Exception as e:
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        
        elif self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            try:
                metrics = {
                    "collector": HealthHandler.service.collector.get_system_health() if HealthHandler.service else {},
                    "recognizer": HealthHandler.service.recognizer.get_status() if HealthHandler.service else {},
                    "optimizer": HealthHandler.service.optimizer.get_status() if HealthHandler.service else {},
                }
                self.wfile.write(json.dumps(metrics, default=str).encode())
            except Exception as e:
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress access logs


def run_health_server(port: int, service: UnifiedLearningService):
    """Run the HTTP health check server."""
    HealthHandler.service = service
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.start_time = time.time()
    server.serve_forever()


def main():
    """Main entry point — boots the complete system."""
    # Parse arguments
    project_root = sys.argv[1] if len(sys.argv) > 1 else PROJECT_ROOT
    port = int(sys.argv[2]) if len(sys.argv) > 2 else int(os.environ.get("ULTRON_LEARNING_PORT", "50060"))
    health_port = int(os.environ.get("ULTRON_HEALTH_PORT", "8090"))
    
    # Resolve paths
    project_root = str(Path(project_root).resolve())
    
    print("")
    print("=" * 70)
    print("  ULTRON SELF-LEARNING SYSTEM")
    print("  Autonomous Code Evolution Engine")
    print("=" * 70)
    print(f"  Project Root:  {project_root}")
    print(f"  JSON API Port: {port + 1}")
    print(f"  Health Port:   {health_port}")
    print(f"  LLM Providers: ", end="")
    
    providers = []
    if os.environ.get("OPENAI_API_KEY"):
        providers.append("OpenAI")
    if os.environ.get("ANTHROPIC_API_KEY"):
        providers.append("Anthropic")
    if os.environ.get("DEEPSEEK_API_KEY"):
        providers.append("DeepSeek")
    if os.environ.get("GROQ_API_KEY"):
        providers.append("Groq")
    providers.append("Ollama (local)")
    print(", ".join(providers))
    print("=" * 70)
    
    # Initialize the service
    print("\n  Initializing subsystems...")
    service = UnifiedLearningService(
        project_root=project_root,
        port=port,
    )
    
    # Run bootstrap if this is a fresh start
    knowledge_path = Path(project_root) / "data" / "knowledge" / "knowledge_base.json"
    if not knowledge_path.exists():
        print("\n  First run detected — running bootstrap...")
        bootstrap = Bootstrap(
            project_root=project_root,
            collector=service.collector,
            introspector=service.introspector,
            distiller=service.distiller,
            codebase=service.codebase,
        )
        report = bootstrap.run_full_bootstrap()
        print(f"  Bootstrap complete: {report.events_seeded} events, {report.rules_pre_loaded} rules")
    else:
        print(f"  Knowledge base found — skipping bootstrap")
    
    # Start health server
    health_thread = threading.Thread(
        target=run_health_server,
        args=(health_port, service),
        daemon=True,
        name="HealthServer"
    )
    health_thread.start()
    print(f"  Health server: http://localhost:{health_port}/health")
    
    # Start the main service
    service.start()
    
    # Graceful shutdown on SIGINT/SIGTERM
    shutdown_event = threading.Event()
    
    def handle_shutdown(signum, frame):
        print("\n\n  Shutting down gracefully...")
        shutdown_event.set()
    
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    print("\n  System is LIVE. Press Ctrl+C to stop.\n")
    
    # Block until shutdown
    shutdown_event.wait()
    
    # Cleanup
    service.stop()
    print("\n  Ultron Self-Learning System stopped.\n")


if __name__ == "__main__":
    main()
