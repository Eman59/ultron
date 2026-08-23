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
    CF_ACCOUNT_ID           — Cloudflare account ID
    CF_API_TOKEN            — Cloudflare Workers AI API token
    CF_AI_MODEL             — Model to use (default: @cf/meta/llama-3.1-8b-instruct)
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
project_root_directory = os.environ.get("ULTRON_PROJECT_ROOT", os.getcwd())
sys.path.insert(0, project_root_directory)

from python.self_improvement.learning.service import UnifiedLearningService
from python.self_improvement.learning.bootstrap import Bootstrap


class HealthHandler(BaseHTTPRequestHandler):
    """Simple HTTP health check endpoint."""
    
    unified_learning_service: UnifiedLearningService = None  # Set by main()
    
    def do_GET(self) -> None:
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
                status = HealthHandler.unified_learning_service.controller.get_status() if HealthHandler.unified_learning_service else {}
                self.wfile.write(json.dumps(status, default=str).encode())
            except Exception as e:
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        
        elif self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()