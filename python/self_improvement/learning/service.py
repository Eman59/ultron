"""
Unified Learning Service — The Central Nervous System Endpoint.

This is the gRPC service that all Ultron components connect to for
reporting experience and receiving learning directives. It's the
single point of integration between:

  - Go Core Agent (autonomy loop decisions and outcomes)
  - Rust Neural Mesh (evolution metrics and activation patterns)
  - Python Meta-Learning (algorithm generation and strategy)
  - Self-Improvement Engine (patches and their results)

The service exposes three main capabilities:
  1. EVENT INGESTION — Accept events from all components
  2. DIRECTIVE DISPATCH — Send optimization directives back
  3. STATUS REPORTING — Provide system-wide learning status

Architecture:
  ┌──────────────┐     ┌──────────────────────┐     ┌──────────────────┐
  │  Go Core     │────▶│                      │────▶│ Experience       │
  │  Agent       │◀────│   Learning Service   │     │ Collector        │
  ├──────────────┤     │   (this file)        │     ├──────────────────┤
  │  Rust Neural │────▶│                      │────▶│ Pattern          │
  │  Mesh        │◀────│   Port: 50060        │     │ Recognizer       │
  ├──────────────┤     │                      │     ├──────────────────┤
  │  Python Meta │────▶│                      │────▶│ Adaptive         │
  │  Learning    │◀────│                      │     │ Optimizer        │
  └──────────────┘     └──────────────────────┘     ├──────────────────┤
                                                     │ Knowledge        │
                                                     │ Distiller        │
                                                     ├──────────────────┤
                                                     │ Code             │
                                                     │ Introspector     │
                                                     ├──────────────────┤
                                                     │ Evolution        │
                                                     │ Controller       │
                                                     └──────────────────┘

Protocol: gRPC with protobuf (definitions below in comments)
Fallback: JSON-over-HTTP for components that can't use gRPC

The service is intentionally designed to be NON-BLOCKING for event
ingestion. Components fire events and don't wait. Directives are
polled or streamed back asynchronously.
"""

import asyncio
import json
import time
import threading
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from concurrent import futures
from pathlib import Path

from .experience_collector import ExperienceCollector, EventType, TraceEvent
from .pattern_recognizer import PatternRecognizer
from .code_introspector import CodeIntrospector
from .adaptive_optimizer import AdaptiveOptimizer
from .knowledge_distiller import KnowledgeDistiller
from .evolution_controller import EvolutionController, EvolutionSpeed
from .codebase_agent import CodebaseAgent
from .llm_brain import LLMBrain, ThinkingMode, Priority
from .intelligent_patcher import IntelligentPatcher, PatchIntent
from .bootstrap import Bootstrap


# ═══════════════════════════════════════════════════════════════════
# PROTOBUF DEFINITION (would normally be in .proto file)
# Included here as documentation + Python dataclasses
# ═══════════════════════════════════════════════════════════════════

"""
Proto definition (learning_service.proto):

syntax = "proto3";
package ultron.learning;

service LearningService {
    // Event Ingestion
    rpc SubmitEvents(EventBatch) returns (SubmitResponse);
    rpc StreamEvents(stream LearningEvent) returns (StreamResponse);
    
    // Directive Dispatch  
    rpc GetDirectives(DirectiveRequest) returns (DirectiveBatch);
    rpc StreamDirectives(DirectiveRequest) returns (stream LearningDirective);
    
    // Status
    rpc GetStatus(StatusRequest) returns (SystemStatus);
    rpc GetRecommendations(RecommendationRequest) returns (RecommendationList);
    
    // Knowledge
    rpc QueryRules(RuleQuery) returns (RuleList);
    rpc SubmitValidation(ValidationFeedback) returns (ValidationResponse);
    
    // Control
    rpc SetEvolutionSpeed(SpeedRequest) returns (SpeedResponse);
    rpc RollbackGeneration(RollbackRequest) returns (RollbackResponse);
    rpc FreezeEvolution(FreezeRequest) returns (FreezeResponse);
}

message LearningEvent {
    string id = 1;
    int64 timestamp_ns = 2;
    string event_type = 3;
    string component = 4;
    bytes data_json = 5;
    optional double outcome = 6;
    repeated string caused_by = 7;
    repeated string tags = 8;
    optional int64 duration_us = 9;
}

message LearningDirective {
    string id = 1;
    string directive_type = 2;
    int32 priority = 3;
    bytes payload_json = 4;
    string source = 5;
    double confidence = 6;
    optional int64 expires_at = 7;
}
"""


# ═══════════════════════════════════════════════════════════════════
# SERVICE DATA TYPES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class IncomingEvent:
    """An event received from any component."""
    id: str
    timestamp_ns: int
    event_type: str
    component: str
    data: Dict[str, Any]
    outcome: Optional[float] = None
    caused_by: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    duration_us: Optional[int] = None


@dataclass
class OutgoingDirective:
    """A directive to send back to a component."""
    id: str
    directive_type: str
    priority: int
    payload: Dict[str, Any]
    source: str
    confidence: float
    target_component: str
    expires_at: Optional[int] = None


@dataclass
class ServiceMetrics:
    """Metrics for the learning service itself."""
    events_received: int = 0
    events_processed: int = 0
    events_dropped: int = 0
    directives_sent: int = 0
    active_connections: int = 0
    uptime_seconds: float = 0.0
    start_time: float = field(default_factory=time.time)

    # Per-component counters
    events_by_component: Dict[str, int] = field(default_factory=dict)
    directives_by_component: Dict[str, int] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════
# UNIFIED LEARNING SERVICE
# ═══════════════════════════════════════════════════════════════════

class UnifiedLearningService:
    """
    The central gRPC service for Ultron's self-learning system.

    All components connect here to:
    1. Report what they're doing (events)
    2. Receive instructions on what to do differently (directives)
    3. Query the system's accumulated knowledge (rules)

    This service bridges the gap between languages (Go, Rust, Python)
    by providing a language-agnostic gRPC interface.
    """

    def __init__(self,
                 project_root: str,
                 port: int = 50052,
                 knowledge_path: str = None,
                 evolution_path: str = None):
        """
        Args:
            project_root: Root directory of the Ultron project
            port: gRPC service port
            knowledge_path: Path for persistent knowledge storage
            evolution_path: Path for evolution history
        """
        self.project_root = Path(project_root)
        self.port = port
        self.knowledge_path = knowledge_path or str(self.project_root / "data" / "knowledge")
        self.evolution_path = evolution_path or str(self.project_root / "data" / "evolution")

        # Initialize the codebase agent FIRST (other subsystems need it)
        self.codebase = CodebaseAgent(
            project_root=project_root,
            auto_validate=True,
            auto_backup=True,
        )

        # Initialize all subsystems
        self._init_subsystems()

        # Service state
        self._metrics = ServiceMetrics()
        self._running = False
        self._server = None

        # Directive queues (per component)
        self._directive_queues: Dict[str, List[OutgoingDirective]] = {
            "core_agent": [],
            "neural_mesh": [],
            "meta_learning": [],
            "self_improvement": [],
        }
        self._directive_lock = threading.Lock()

        # Directive generation (background)
        self._directive_thread: Optional[threading.Thread] = None

    def _init_subsystems(self):
        """Initialize all learning subsystems."""
        # 1. Experience Collector — captures everything
        self.collector = ExperienceCollector(
            max_buffer_size=200_000,
            max_traces=20_000,
            long_term_path=str(Path(self.knowledge_path) / "traces"),
            importance_threshold=0.7,
            auto_trace_timeout=30.0,
        )

        # 2. Pattern Recognizer — finds meaning in experience
        self.recognizer = PatternRecognizer(
            experience_collector=self.collector,
            min_pattern_occurrences=3,
            min_confidence=0.6,
            max_patterns=5000,
            analysis_interval=30.0,
        )

        # 3. Code Introspector — understands the codebase
        self.introspector = CodeIntrospector(
            project_root=str(self.project_root),
            scan_interval=300.0,
        )

        # 4. Adaptive Optimizer — generates and tests improvements
        self.optimizer = AdaptiveOptimizer(
            experience_collector=self.collector,
            pattern_recognizer=self.recognizer,
            code_introspector=self.introspector,
            project_root=str(self.project_root),
            max_concurrent_tests=5,
            min_test_samples=50,
            optimization_interval=60.0,
        )

        # 5. Knowledge Distiller — permanent learning
        self.distiller = KnowledgeDistiller(
            knowledge_path=self.knowledge_path,
            min_evidence_for_rule=10,
            min_confidence_for_promotion=0.8,
            max_rules=5000,
            distillation_interval=120.0,
            save_interval=300.0,
        )

        # 6. Evolution Controller — master orchestrator
        self.controller = EvolutionController(
            project_root=str(self.project_root),
            experience_collector=self.collector,
            pattern_recognizer=self.recognizer,
            code_introspector=self.introspector,
            adaptive_optimizer=self.optimizer,
            knowledge_distiller=self.distiller,
            evolution_path=self.evolution_path,
            initial_speed=EvolutionSpeed.NORMAL,
            generation_duration_hours=1.0,
        )

        # 7. LLM Brain — real intelligence engine (connects to Ollama/OpenAI/Claude)
        import os as _os
        self.brain = LLMBrain(
            config_path=str(self.project_root / "configs" / "llm_config.json"),
            daily_budget_usd=float(_os.environ.get("ULTRON_DAILY_BUDGET_USD", "10.0")),
            prefer_local=_os.environ.get("ULTRON_PREFER_LOCAL_LLM", "true").lower() == "true",
        )

        # 8. Intelligent Patcher — LLM-powered code evolution
        self.patcher = IntelligentPatcher(
            brain=self.brain,
            codebase=self.codebase,
            introspector=self.introspector,
            collector=self.collector,
            auto_apply=True,
            self_review=True,
            min_confidence=0.6,
            max_patches_per_hour=10,
        )

        # 9. Continuous Learner — brain retraining loop
        try:
            from ..brain.continuous_learner import ContinuousLearner
            self.learner = ContinuousLearner(
                project_root=str(self.project_root),
                models_dir=str(self.project_root / "models"),
                retrain_interval_hours=2.0,    # retrain every 2h instead of 24h
                min_new_examples=10,           # trigger after 10 interactions, not 500
                auto_retrain=True,
            )
        except ImportError:
            self.learner = None

        # 10. Interaction Learner — adapts responses to user
        try:
            sys_path = str(self.project_root)
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "interaction_learner",
                str(self.project_root / "python" / "interface" / "interaction_learner.py")
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self.interaction = mod.InteractionLearner(
                data_dir=str(self.project_root / "data" / "interaction"),
            )
        except Exception:
            self.interaction = None

        # 11. Adaptive UI — evolving visual interface
        try:
            spec = importlib.util.spec_from_file_location(
                "adaptive_ui",
                str(self.project_root / "python" / "interface" / "adaptive_ui.py")
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self.ui = mod.AdaptiveUIController(
                data_dir=str(self.project_root / "data" / "ui"),
            )
        except Exception:
            self.ui = None

        # 12. Voice Evolution — improving voice over time
        try:
            spec = importlib.util.spec_from_file_location(
                "voice_evolution",
                str(self.project_root / "python" / "interface" / "voice_evolution.py")
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self.voice = mod.VoiceEvolutionEngine(
                data_dir=str(self.project_root / "data" / "voice"),
            )
        except Exception:
            self.voice = None

        # ═══════════════════════════════════════════════════════════
        # 13-16: NEW MODULES — Wired into the learning service
        # ═══════════════════════════════════════════════════════════

        # 13. Consciousness — Self-Model, Theory of Mind, Soul
        try:
            import sys as _sys
            _sys.path.insert(0, str(self.project_root / "python"))
            from consciousness import SelfModel, TheoryOfMind, Soul
            
            consciousness_dir = str(self.project_root / "data" / "consciousness")
            self.self_model = SelfModel(data_dir=consciousness_dir)
            self.theory_of_mind = TheoryOfMind(data_dir=consciousness_dir)
            self.soul = Soul(data_dir=consciousness_dir, llm_client=self.brain)
            self.soul.start()
            print("[LearningService] ✓ Consciousness module LIVE (Self-Model + ToM + Soul)")
        except Exception as e:
            self.self_model = None
            self.theory_of_mind = None
            self.soul = None
            print(f"[LearningService] ⚠ Consciousness module failed: {e}")

        # 14. Global Reach — Supply Chain + Cyber-Physical Engine
        try:
            from global_reach import SupplyChainAgent, CyberPhysicalEngine
            
            global_reach_dir = str(self.project_root / "data" / "global_reach")
            self.supply_chain = SupplyChainAgent(data_dir=global_reach_dir)
            self.cyber_physical = CyberPhysicalEngine(data_dir=global_reach_dir)
            print("[LearningService] ✓ Global Reach module LIVE (Supply Chain + Cyber-Physical)")
        except Exception as e:
            self.supply_chain = None
            self.cyber_physical = None
            print(f"[LearningService] ⚠ Global Reach module failed: {e}")

        # 15. Energy Grid Controller
        try:
            from global_reach.energy_grid import EnergyGridController
            
            energy_dir = str(self.project_root / "data" / "energy")
            self.energy_grid = EnergyGridController(data_dir=energy_dir)
            print("[LearningService] ✓ Energy Grid LIVE")
        except Exception as e:
            self.energy_grid = None
            print(f"[LearningService] ⚠ Energy Grid failed: {e}")

        # 16. Universal Transfer Agent
        try:
            from meta_learning.transfer_agent import UniversalTransferAgent
            
            transfer_dir = str(self.project_root / "data" / "transfer")
            self.transfer_agent = UniversalTransferAgent(data_dir=transfer_dir, llm_client=self.brain)
            print("[LearningService] ✓ Transfer Agent LIVE")
        except Exception as e:
            self.transfer_agent = None
            print(f"[LearningService] ⚠ Transfer Agent failed: {e}")

    # ═══════════════════════════════════════════════════════════════
    # SERVICE LIFECYCLE
    # ═══════════════════════════════════════════════════════════════

    def start(self):
        """Start the unified learning service."""
        self._running = True
        self._metrics.start_time = time.time()

        # Start the evolution controller (which starts all subsystems)
        self.controller.start()

        # Start the continuous learner (brain retraining)
        if self.learner: self.learner.start()


        # Start directive generation thread
        self._directive_thread = threading.Thread(
            target=self._directive_generation_loop,
            daemon=True,
            name="LearningService-Directives"
        )
        self._directive_thread.start()

        # Start the gRPC server
        self._start_grpc_server()

        print("=" * 70)
        print("  ULTRON UNIFIED LEARNING SERVICE — ONLINE")
        print("=" * 70)
        print(f"  gRPC Port: {self.port}")
        print(f"  Knowledge Path: {self.knowledge_path}")
        print(f"  Evolution Path: {self.evolution_path}")
        print(f"  Subsystems: ALL ACTIVE")
        print("=" * 70)

    def stop(self):
        """Stop the learning service."""
        self._running = False
        
        # Stop gRPC server
        if self._server:
            self._server.stop(grace=5.0)

        # Stop evolution controller (stops all subsystems)
        self.controller.stop()

        if self._directive_thread:
            self._directive_thread.join(timeout=5.0)

        print("[LearningService] Stopped")

    def _start_grpc_server(self):
        """Start the gRPC server (simplified — actual impl uses grpc library)."""
        # In production, this would use grpc.aio.server() with the
        # generated protobuf servicer. For now, we run a lightweight
        # JSON-over-TCP fallback that accepts the same message formats.
        self._server_thread = threading.Thread(
            target=self._run_json_server,
            daemon=True,
            name="LearningService-Server"
        )
        self._server_thread.start()

    def _run_json_server(self):
        """Fallback JSON-over-TCP server for components that can't use gRPC."""
        import socket
        import select

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.settimeout(1.0)

        try:
            server_socket.bind(('0.0.0.0', self.port + 1))  # JSON port = gRPC port + 1
            server_socket.listen(20)
        except OSError as e:
            print(f"[LearningService] JSON server bind failed: {e}")
            return

        while self._running:
            try:
                client, addr = server_socket.accept()
                threading.Thread(
                    target=self._handle_json_client,
                    args=(client, addr),
                    daemon=True,
                ).start()
                self._metrics.active_connections += 1
            except socket.timeout:
                continue
            except OSError:
                break

        server_socket.close()

    def _handle_json_client(self, client_socket, addr):
        """Handle a JSON client connection."""
        try:
            client_socket.settimeout(5.0)
            data = b""
            while True:
                chunk = client_socket.recv(65536)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break

            if data:
                request = json.loads(data.decode('utf-8'))
                response = self._handle_request(request)
                client_socket.sendall(json.dumps(response).encode('utf-8') + b"\n")
        except (json.JSONDecodeError, socket.timeout, ConnectionResetError):
            pass
        finally:
            client_socket.close()
            self._metrics.active_connections = max(0, self._metrics.active_connections - 1)

    def _handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Route a JSON request to the appropriate handler."""
        method = request.get("method", "")
        params = request.get("params", {})

        handlers = {
            "submit_events": self._handle_submit_events,
            "get_directives": self._handle_get_directives,
            "get_status": self._handle_get_status,
            "get_recommendations": self._handle_get_recommendations,
            "query_rules": self._handle_query_rules,
            "submit_validation": self._handle_submit_validation,
            "set_speed": self._handle_set_speed,
            "rollback": self._handle_rollback,
            "freeze": self._handle_freeze,
            "unfreeze": self._handle_unfreeze,
            # Codebase interaction
            "list_dir": self._handle_list_dir,
            "read_file": self._handle_read_file,
            "search_code": self._handle_search_code,
            "write_file": self._handle_write_file,
            "replace_code": self._handle_replace_code,
            "delete_file": self._handle_delete_file,
            "run_command": self._handle_run_command,
            "rollback_change": self._handle_rollback_change,
            "get_changes": self._handle_get_changes,
            "project_structure": self._handle_project_structure,
            "find_usages": self._handle_find_usages,
            "find_definitions": self._handle_find_definitions,
        }

        handler = handlers.get(method)
        if not handler:
            return {"error": f"Unknown method: {method}"}

        try:
            return handler(params)
        except Exception as e:
            return {"error": str(e)}

    # ═══════════════════════════════════════════════════════════════
    # REQUEST HANDLERS
    # ═══════════════════════════════════════════════════════════════

    def _handle_submit_events(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle event submission from any component."""
        events = params.get("events", [])
        processed = 0

        for event_data in events:
            try:
                # Map string event type to enum
                event_type = self._map_event_type(event_data.get("event_type", ""))
                
                # Submit to experience collector
                self.collector.record_event(
                    event_type=event_type,
                    component=event_data.get("component", "unknown"),
                    data=event_data.get("data", {}),
                    duration_us=event_data.get("duration_us"),
                    caused_by=event_data.get("caused_by"),
                    outcome=event_data.get("outcome"),
                    tags=set(event_data.get("tags", [])),
                )
                processed += 1
                self._metrics.events_received += 1
                self._metrics.events_processed += 1

                # ── Feed interactions directly into ContinuousLearner ──────
                if event_data.get("event_type") == "interaction" and self.learner:
                    d = event_data.get("data", {})
                    ui = d.get("user_input", "")
                    resp = d.get("response", "")
                    if ui and resp:
                        try:
                            self.learner.ingest_interaction(ui, resp, quality_score=0.75)
                        except Exception:
                            pass

                # Track per-component
                component = event_data.get("component", "unknown")
                self._metrics.events_by_component[component] = \
                    self._metrics.events_by_component.get(component, 0) + 1

            except Exception:
                self._metrics.events_dropped += 1

        return {"processed": processed, "total": len(events)}

    def _handle_get_directives(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return pending directives for a component."""
        component = params.get("component", "")
        
        with self._directive_lock:
            directives = self._directive_queues.get(component, [])
            self._directive_queues[component] = []

        # Serialize directives
        result = []
        for d in directives:
            result.append({
                "id": d.id,
                "directive_type": d.directive_type,
                "priority": d.priority,
                "payload": d.payload,
                "source": d.source,
                "confidence": d.confidence,
                "expires_at": d.expires_at,
            })
            self._metrics.directives_sent += 1
            self._metrics.directives_by_component[component] = \
                self._metrics.directives_by_component.get(component, 0) + 1

        return {"directives": result, "count": len(result)}

    def _handle_get_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return comprehensive system status."""
        return {
            "service": {
                "uptime_seconds": time.time() - self._metrics.start_time,
                "events_received": self._metrics.events_received,
                "events_processed": self._metrics.events_processed,
                "directives_sent": self._metrics.directives_sent,
                "active_connections": self._metrics.active_connections,
                "events_by_component": self._metrics.events_by_component,
            },
            "evolution": self.controller.get_status(),
            "system_health": self.collector.get_system_health(),
            "learning_signal": self.collector.get_learning_signal(),
        }

    def _handle_get_recommendations(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return actionable recommendations."""
        recommendations = self.recognizer.get_recommendations()
        return {"recommendations": recommendations}

    def _handle_query_rules(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Query the knowledge base for applicable rules."""
        context = params.get("context", {})
        rules = self.distiller.query_rules(context)
        return {
            "rules": [
                {
                    "id": r.id,
                    "type": r.rule_type.value,
                    "name": r.name,
                    "description": r.description,
                    "action": r.action_readable,
                    "confidence": r.confidence.value,
                    "reliability": r.reliability,
                }
                for r in rules[:20]
            ],
            "total": len(rules),
        }

    def _handle_submit_validation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Submit validation feedback for a rule."""
        rule_id = params.get("rule_id", "")
        was_correct = params.get("was_correct", True)
        outcome = params.get("outcome", 0.0)

        self.distiller.submit_validation(rule_id, was_correct, outcome)
        return {"accepted": True}

    def _handle_set_speed(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set evolution speed."""
        speed_str = params.get("speed", "normal")
        try:
            speed = EvolutionSpeed(speed_str)
            self.controller.set_speed(speed)
            return {"speed": speed.value, "applied": True}
        except ValueError:
            return {"error": f"Invalid speed: {speed_str}"}

    def _handle_rollback(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Rollback a generation."""
        gen_id = params.get("generation_id")
        success = self.controller.rollback_generation(gen_id)
        return {"success": success}

    def _handle_freeze(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Freeze evolution."""
        self.controller.freeze()
        return {"frozen": True}

    def _handle_unfreeze(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Unfreeze evolution."""
        speed_str = params.get("speed", "normal")
        try:
            speed = EvolutionSpeed(speed_str)
            self.controller.unfreeze(speed)
            return {"unfrozen": True, "speed": speed.value}
        except ValueError:
            self.controller.unfreeze()
            return {"unfrozen": True, "speed": "normal"}

    # ═══════════════════════════════════════════════════════════════
    # DIRECTIVE GENERATION — Background loop
    # ═══════════════════════════════════════════════════════════════

    def _directive_generation_loop(self):
        """Background: generate directives based on learning insights."""
        while self._running:
            time.sleep(10.0)  # Generate directives every 10 seconds
            self._generate_directives()

    def _generate_directives(self):
        """Generate directives for all components based on current state."""
        # Get recommendations from pattern recognizer
        recommendations = self.recognizer.get_recommendations()
        
        # Get applicable rules from knowledge base
        system_context = {
            "state": "running",
            "metrics": {
                "error_rate": self.collector.get_system_health().get("error_rate", 0),
            },
        }
        rules = self.distiller.query_rules(system_context)

        # Get optimizer's current parameter suggestions
        optimizer_status = self.optimizer.get_status()

        with self._directive_lock:
            # Generate directives for Core Agent (Go)
            self._generate_core_agent_directives(recommendations, rules)

            # Generate directives for Neural Mesh (Rust)
            self._generate_neural_directives(recommendations, rules)

            # Generate directives for Meta-Learning (Python)
            self._generate_meta_learning_directives(recommendations, rules)

    def _generate_core_agent_directives(self, recommendations: List, rules: List):
        """Generate directives for the Go core agent."""
        directives = []

        # From pattern recommendations
        for rec in recommendations[:5]:
            if rec.get("type") == "avoid":
                # Tell agent to avoid a sequence
                directives.append(OutgoingDirective(
                    id=f"dir_avoid_{int(time.time())}",
                    directive_type="avoid_sequence",
                    priority=7,
                    payload={
                        "sequence": rec.get("components", []),
                        "severity": rec.get("expected_improvement", 0.5),
                        "reason": rec.get("description", ""),
                        "duration_seconds": 3600,
                    },
                    source="pattern_recognizer",
                    confidence=rec.get("priority", 0.5),
                    target_component="core_agent",
                ))
            elif rec.get("type") == "amplify":
                # Tell agent to prefer certain actions
                directives.append(OutgoingDirective(
                    id=f"dir_bias_{int(time.time())}",
                    directive_type="action_bias",
                    priority=5,
                    payload={
                        "action_type": "Learn",  # Default to learning
                        "multiplier": 1.3,
                        "reason": rec.get("description", ""),
                        "duration_seconds": 1800,
                    },
                    source="pattern_recognizer",
                    confidence=rec.get("priority", 0.5),
                    target_component="core_agent",
                ))

        # From knowledge base instincts
        instincts = self.distiller.get_instincts()
        for instinct in instincts[:3]:
            directives.append(OutgoingDirective(
                id=f"dir_instinct_{instinct.id}",
                directive_type="instinct_rule",
                priority=9,
                payload={
                    "condition_type": instinct.condition.get("type", "threat_above"),
                    "threshold": instinct.condition.get("threshold", 0.8),
                    "action_type": instinct.action.get("action", "Defend"),
                    "target": instinct.action.get("target", ""),
                    "priority": 9,
                },
                source="knowledge_distiller",
                confidence=instinct.reliability,
                target_component="core_agent",
            ))

        # Exploration rate from optimizer
        strategy_eff = self.optimizer.get_strategy_effectiveness()
        if strategy_eff:
            # If strategies are succeeding, reduce exploration (exploit)
            # If strategies are failing, increase exploration
            avg_effectiveness = sum(
                v.get("effectiveness", 0.5) for v in strategy_eff.values()
            ) / max(1, len(strategy_eff))

            exploration_rate = 0.3 - avg_effectiveness * 0.2  # 0.1 to 0.3
            directives.append(OutgoingDirective(
                id=f"dir_explore_{int(time.time())}",
                directive_type="exploration_set",
                priority=3,
                payload={
                    "exploration_rate": max(0.05, min(0.4, exploration_rate)),
                },
                source="adaptive_optimizer",
                confidence=0.7,
                target_component="core_agent",
            ))

        self._directive_queues["core_agent"].extend(directives)

    def _generate_neural_directives(self, recommendations: List, rules: List):
        """Generate directives for the Rust neural mesh."""
        directives = []

        # Check if neural component has performance issues
        neural_recs = [r for r in recommendations if "neural" in str(r.get("components", []))]

        for rec in neural_recs[:3]:
            if rec.get("type") == "optimize":
                # Suggest architecture adjustment
                directives.append(OutgoingDirective(
                    id=f"dir_neural_{int(time.time())}",
                    directive_type="adjust_evolution_params",
                    priority=5,
                    payload={
                        "mutation_rate": 0.15,  # Increase exploration
                        "novelty_weight": 0.2,
                    },
                    source="adaptive_optimizer",
                    confidence=0.6,
                    target_component="neural_mesh",
                ))

        # From knowledge base: neural-specific rules
        neural_rules = [r for r in rules if "neural" in str(r.tags)]
        for rule in neural_rules[:2]:
            if rule.action.get("type") == "apply_optimization":
                params = rule.action.get("parameters", {})
                directives.append(OutgoingDirective(
                    id=f"dir_neural_rule_{rule.id}",
                    directive_type="adjust_fitness_weights",
                    priority=4,
                    payload=params,
                    source="knowledge_distiller",
                    confidence=rule.reliability,
                    target_component="neural_mesh",
                ))

        self._directive_queues["neural_mesh"].extend(directives)

    def _generate_meta_learning_directives(self, recommendations: List, rules: List):
        """Generate directives for the Python meta-learning system."""
        directives = []

        # Feed optimizer parameters back to meta-learning
        current_params = self.optimizer.get_strategy_effectiveness()
        if current_params:
            best_strategies = sorted(
                current_params.items(),
                key=lambda x: x[1].get("effectiveness", 0),
                reverse=True
            )[:3]

            directives.append(OutgoingDirective(
                id=f"dir_meta_{int(time.time())}",
                directive_type="parameter_set",
                priority=4,
                payload={
                    "best_strategies": [s[0] for s in best_strategies],
                    "strategy_effectiveness": {s[0]: s[1] for s in best_strategies},
                },
                source="adaptive_optimizer",
                confidence=0.7,
                target_component="meta_learning",
            ))

        self._directive_queues["meta_learning"].extend(directives)

    # ═══════════════════════════════════════════════════════════════
    # CODEBASE INTERACTION HANDLERS
    # ═══════════════════════════════════════════════════════════════

    def _handle_list_dir(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List directory contents."""
        path = params.get("path", "")
        recursive = params.get("recursive", False)
        max_depth = params.get("max_depth", 3)
        extensions = set(params.get("extensions", [])) or None
        return self.codebase.list_directory(path, recursive=recursive,
                                           max_depth=max_depth, extensions=extensions)

    def _handle_read_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Read a file's contents."""
        path = params.get("path", "")
        start_line = params.get("start_line")
        end_line = params.get("end_line")
        function_name = params.get("function")

        if function_name:
            content = self.codebase.read_function(path, function_name)
            return {"path": path, "function": function_name, "content": content}

        if start_line:
            lines = self.codebase.read_lines(path, start=start_line, end=end_line)
            return {"path": path, "lines": lines, "start": start_line, "end": end_line}

        content = self.codebase.read_file(path)
        if content is None:
            return {"error": f"File not found: {path}"}
        
        info = self.codebase.get_file_info(path)
        return {"path": path, "content": content, "info": info}

    def _handle_search_code(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Search for patterns in the codebase."""
        pattern = params.get("pattern", "")
        extensions = set(params.get("extensions", [])) or None
        directories = params.get("directories")
        max_results = params.get("max_results", 50)
        regex = params.get("regex", False)

        results = self.codebase.search(
            pattern, file_extensions=extensions, directories=directories,
            max_results=max_results, regex=regex,
        )

        return {
            "pattern": pattern,
            "total_results": len(results),
            "results": [
                {
                    "file": r.file_path,
                    "line": r.line_number,
                    "content": r.line_content,
                    "context_before": r.context_before,
                    "context_after": r.context_after,
                }
                for r in results
            ],
        }

    def _handle_write_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Write/create a file."""
        path = params.get("path", "")
        content = params.get("content", "")
        reason = params.get("reason", "self_learning_system")
        source = params.get("source", "learning_service")

        record = self.codebase.write_file(path, content, reason=reason, source=source)
        return record.to_dict()

    def _handle_replace_code(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Replace code in a file."""
        path = params.get("path", "")
        old_text = params.get("old_text", "")
        new_text = params.get("new_text", "")
        reason = params.get("reason", "optimization")
        source = params.get("source", "adaptive_optimizer")

        record = self.codebase.replace_in_file(path, old_text, new_text,
                                               reason=reason, source=source)
        return record.to_dict()

    def _handle_delete_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a file."""
        path = params.get("path", "")
        reason = params.get("reason", "dead_code_removal")
        record = self.codebase.delete_file(path, reason=reason)
        return record.to_dict()

    def _handle_run_command(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run a shell command."""
        command = params.get("command", "")
        cwd = params.get("cwd")
        timeout = params.get("timeout", 60.0)
        return self.codebase.run_command(command, cwd=cwd, timeout=timeout)

    def _handle_rollback_change(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Rollback a specific change or last N changes."""
        change_id = params.get("change_id")
        count = params.get("count", 1)

        if change_id:
            success = self.codebase.rollback_change(change_id)
            return {"success": success, "change_id": change_id}
        else:
            rolled_back = self.codebase.rollback_last(count)
            return {"rolled_back": rolled_back, "count": len(rolled_back)}

    def _handle_get_changes(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get change history."""
        last_n = params.get("last_n", 50)
        return {
            "changes": self.codebase.get_change_history(last_n),
            "stats": self.codebase.get_stats(),
        }

    def _handle_project_structure(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get project structure overview."""
        max_depth = params.get("max_depth", 3)
        return self.codebase.get_project_structure(max_depth=max_depth)

    def _handle_find_usages(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Find all usages of a symbol."""
        symbol = params.get("symbol", "")
        extensions = set(params.get("extensions", [])) or None
        results = self.codebase.find_usages(symbol, file_extensions=extensions)
        return {
            "symbol": symbol,
            "total": len(results),
            "usages": [
                {"file": r.file_path, "line": r.line_number, "content": r.line_content}
                for r in results
            ],
        }

    def _handle_find_definitions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Find where a symbol is defined."""
        name = params.get("name", "")
        results = self.codebase.find_definitions(name)
        return {
            "name": name,
            "total": len(results),
            "definitions": [
                {"file": r.file_path, "line": r.line_number, "content": r.line_content}
                for r in results
            ],
        }

    # ═══════════════════════════════════════════════════════════════
    # EVENT TYPE MAPPING
    # ═══════════════════════════════════════════════════════════════

    def _map_event_type(self, event_type_str: str) -> EventType:
        """Map string event type to EventType enum."""
        mapping = {
            "decision_made": EventType.DECISION_MADE,
            "action_executed": EventType.ACTION_EXECUTED,
            "action_outcome": EventType.ACTION_OUTCOME,
            "drive_change": EventType.DRIVE_CHANGE,
            "state_transition": EventType.STATE_TRANSITION,
            "goal_created": EventType.GOAL_CREATED,
            "goal_completed": EventType.GOAL_COMPLETED,
            "goal_failed": EventType.GOAL_FAILED,
            "neural_activation": EventType.NEURAL_ACTIVATION,
            "plasticity_update": EventType.PLASTICITY_UPDATE,
            "neural_evolution": EventType.NEURAL_EVOLUTION,
            "architecture_change": EventType.ARCHITECTURE_CHANGE,
            "algorithm_generated": EventType.ALGORITHM_GENERATED,
            "algorithm_evaluated": EventType.ALGORITHM_EVALUATED,
            "strategy_switch": EventType.STRATEGY_SWITCH,
            "transfer_performed": EventType.TRANSFER_PERFORMED,
            "patch_generated": EventType.PATCH_GENERATED,
            "patch_tested": EventType.PATCH_TESTED,
            "patch_applied": EventType.PATCH_APPLIED,
            "patch_reverted": EventType.PATCH_REVERTED,
            "performance_measured": EventType.PERFORMANCE_MEASURED,
            "resource_spike": EventType.RESOURCE_SPIKE,
            "error_occurred": EventType.ERROR_OCCURRED,
            "recovery_started": EventType.RECOVERY_STARTED,
            "recovery_completed": EventType.RECOVERY_COMPLETED,
            "pattern_discovered": EventType.PATTERN_DISCOVERED,
            "rule_distilled": EventType.RULE_DISTILLED,
            "optimization_applied": EventType.OPTIMIZATION_APPLIED,
            "performance_tick": EventType.PERFORMANCE_MEASURED,
            "reflection": EventType.PERFORMANCE_MEASURED,
        }
        return mapping.get(event_type_str, EventType.PERFORMANCE_MEASURED)


# ═══════════════════════════════════════════════════════════════════
# ENTRY POINT — Run the service standalone
# ═══════════════════════════════════════════════════════════════════

def run_learning_service(project_root: str = ".", port: int = 50052):
    """
    Run the unified learning service.
    
    This is the main entry point for starting the self-learning system.
    All components initialize and begin their work immediately.
    
    Usage:
        from self_improvement.learning.service import run_learning_service
        run_learning_service("/path/to/ultron", port=50052)
    """
    service = UnifiedLearningService(
        project_root=project_root,
        port=port,
    )

    try:
        service.start()
        
        # Keep running until interrupted
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[LearningService] Shutting down...")
        service.stop()


if __name__ == "__main__":
    import sys
    project_root = sys.argv[1] if len(sys.argv) > 1 else "."
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 50052
    run_learning_service(project_root, port)
