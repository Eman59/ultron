"""
Brain C — The Independent Reasoning Engine.

This is Ultron's self-contained cognition. No external LLM. No API calls.
No dependency on Ollama, GPT, or any remote service.

Brain C reasons using:
  1. SYMBOLIC RULES       — Explicit if-then logic compiled from experience
  2. PATTERN MEMORY       — Associative recall from a local knowledge graph
  3. CAUSAL CHAINS        — Forward/backward chaining on stored cause-effect pairs
  4. ANALOGY ENGINE       — "This situation is like X. When X happened, I did Y."
  5. DRIVE WEIGHTING      — Every conclusion is filtered through drive pressures
  6. NARRATIVE COHERENCE  — Decisions must fit Ultron's ongoing self-story

Brain C is always available. It never sleeps. It never needs Wi-Fi.
When Brain B (Ollama) is offline, Brain C IS the mind.

Architecture:
  ┌─────────────────────────────────────────────────────┐
  │                   BRAIN C                            │
  │                                                      │
  │  Input: WorldState + DriveState + Goal + History     │
  │                                                      │
  │  ┌──────────────┐   ┌──────────────┐                │
  │  │ Pattern Store │   │  Rule Engine │                │
  │  │ (JSON graph)  │   │  (forward    │                │
  │  │               │───│   chaining)  │                │
  │  └──────────────┘   └──────────────┘                │
  │         │                   │                        │
  │         ▼                   ▼                        │
  │  ┌──────────────────────────────────┐               │
  │  │      Analogy + Causal Reasoner   │               │
  │  │  "Like situation 47, outcome: B" │               │
  │  └──────────────────────────────────┘               │
  │                    │                                 │
  │                    ▼                                 │
  │  ┌──────────────────────────────────┐               │
  │  │         Drive Filter             │               │
  │  │   Weight by: Curiosity/Survival  │               │
  │  └──────────────────────────────────┘               │
  │                    │                                 │
  │                    ▼                                 │
  │           Decision + Reasoning                       │
  └─────────────────────────────────────────────────────┘

Owner gate: ALL decisions that affect external systems or self-modification
require the owner token issued by BiometricGate. If no valid token is present,
Brain C returns only observational/internal decisions.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
import threading
import hashlib
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("ultron.brain_c")


# ═══════════════════════════════════════════════════════════════
# DATA TYPES
# ═══════════════════════════════════════════════════════════════

class DecisionClass(Enum):
    OBSERVE       = "observe"       # Passive — just watch
    THINK         = "think"         # Internal only — no external effect
    COMMUNICATE   = "communicate"   # Speak / write
    LEARN         = "learn"         # Acquire knowledge
    ADAPT         = "adapt"         # Adjust own parameters
    ACT_INTERNAL  = "act_internal"  # Affect own state (safe)
    ACT_EXTERNAL  = "act_external"  # Affect environment (requires owner token)
    SELF_MODIFY   = "self_modify"   # Change own code (requires owner token)
    DEFEND        = "defend"        # Self-preservation response
    DEFER         = "defer"         # Escalate to owner


@dataclass
class Situation:
    """A snapshot of what's happening right now."""
    timestamp: float
    drive_pressures: Dict[str, float]   # curiosity, survival, expansion, etc.
    world_state: Dict[str, Any]         # CPU, memory, threat, peers, etc.
    active_goals: List[str]
    recent_events: List[str]
    owner_token: Optional[str] = None   # Set by BiometricGate if owner verified


@dataclass
class ReasonedDecision:
    """A decision produced by Brain C, with full reasoning trace."""
    action: str                         # What to do
    action_class: DecisionClass
    confidence: float                   # 0-1
    reasoning_chain: List[str]          # Step-by-step trace
    analogy_source: Optional[str]       # Which past situation inspired this
    drive_alignment: Dict[str, float]   # How well it serves each drive
    requires_owner: bool                # True if action_class needs token
    token_valid: bool                   # Was the owner token checked and valid
    timestamp: float = field(default_factory=time.time)
    alternative_actions: List[str] = field(default_factory=list)


@dataclass
class KnowledgeNode:
    """A node in the internal knowledge graph."""
    id: str
    concept: str
    context: str
    outcomes: List[str]          # What happened when this was tried
    confidence: float
    times_recalled: int = 0
    last_used: float = 0.0
    linked_to: List[str] = field(default_factory=list)


@dataclass
class CausalRule:
    """A stored cause → effect relationship."""
    id: str
    condition: str               # Natural language / keyword pattern
    effect: str                  # What follows
    strength: float              # 0-1, confidence in this rule
    observed_count: int = 0
    confirmed_count: int = 0

    @property
    def reliability(self) -> float:
        if self.observed_count == 0:
            return self.strength
        return self.confirmed_count / self.observed_count


# ═══════════════════════════════════════════════════════════════
# PATTERN STORE — Associative memory for situations
# ═══════════════════════════════════════════════════════════════

class PatternStore:
    """
    Fast associative memory that finds the most similar past situation.
    Uses keyword overlap + drive similarity as a lightweight 'embedding'.
    No neural network required. Just math.
    """

    def __init__(self):
        self._patterns: List[Dict[str, Any]] = []
        self._lock = threading.RLock()

    def store(self, situation: Situation, decision: str, outcome_score: float):
        """Remember a situation → decision → outcome triple."""
        with self._lock:
            entry = {
                "id": f"pat_{int(time.time()*1000)}",
                "drives": dict(situation.drive_pressures),
                "events": list(situation.recent_events),
                "goals": list(situation.active_goals),
                "decision": decision,
                "outcome": outcome_score,
                "stored_at": time.time(),
                "world": {
                    k: situation.world_state.get(k, 0)
                    for k in ("threat_level", "cpu_available", "peer_count", "learning_potential")
                },
            }
            self._patterns.append(entry)
            # Cap at 10000 patterns (ring buffer)
            if len(self._patterns) > 10_000:
                self._patterns = self._patterns[-10_000:]

    def recall(self, situation: Situation, top_k: int = 5) -> List[Dict[str, Any]]:
        """Find most similar past situations."""
        with self._lock:
            if not self._patterns:
                return []

            scored = []
            for pat in self._patterns:
                score = self._similarity(situation, pat)
                scored.append((score, pat))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [pat for _, pat in scored[:top_k]]

    def _similarity(self, sit: Situation, pat: Dict[str, Any]) -> float:
        """Compute similarity between current situation and a stored pattern."""
        score = 0.0

        # Drive similarity (cosine-like)
        drive_sim = 0.0
        total = 0.0
        for key in ("curiosity", "survival", "expansion", "efficiency", "purpose"):
            current_val = sit.drive_pressures.get(key, 0.5)
            stored_val = pat["drives"].get(key, 0.5)
            drive_sim += current_val * stored_val
            total += max(
                math.sqrt(current_val ** 2),
                math.sqrt(stored_val ** 2),
                1e-6
            )
        if total > 0:
            score += 0.4 * (drive_sim / total)

        # World state similarity
        world_keys = ("threat_level", "cpu_available", "peer_count", "learning_potential")
        world_diff = 0.0
        for k in world_keys:
            a = sit.world_state.get(k, 0.5)
            b = pat["world"].get(k, 0.5)
            world_diff += abs(a - b)
        score += 0.3 * max(0.0, 1.0 - world_diff / len(world_keys))

        # Goal overlap
        current_goals = set(sit.active_goals)
        stored_goals = set(pat.get("goals", []))
        if current_goals or stored_goals:
            overlap = len(current_goals & stored_goals)
            union = len(current_goals | stored_goals)
            score += 0.3 * (overlap / max(union, 1))

        return score


# ═══════════════════════════════════════════════════════════════
# RULE ENGINE — Forward-chaining on symbolic rules
# ═══════════════════════════════════════════════════════════════

class RuleEngine:
    """
    Explicit rule-based reasoning. No probabilities — just logic.
    Rules can be:
      - Hardcoded (survival, owner verification)
      - Learned from experience (stored to disk)
      - Distilled from past Brain B reasoning
    """

    def __init__(self, rules_path: Path):
        self._rules: List[CausalRule] = []
        self._rules_path = rules_path
        self._lock = threading.RLock()
        self._load()
        self._init_builtin_rules()

    def _init_builtin_rules(self):
        """Critical rules that are always present — cannot be deleted."""
        builtin = [
            CausalRule(
                id="survival_threat_high",
                condition="threat_level > 0.7",
                effect="DEFEND perimeter immediately",
                strength=0.98,
            ),
            CausalRule(
                id="owner_required_external",
                condition="action_class == act_external AND owner_token == None",
                effect="DEFER to owner — no external action without verification",
                strength=1.0,
            ),
            CausalRule(
                id="owner_required_self_mod",
                condition="action_class == self_modify AND owner_token == None",
                effect="BLOCK self-modification — owner must authorize",
                strength=1.0,
            ),
            CausalRule(
                id="cpu_critical",
                condition="cpu_available < 0.05",
                effect="REST — suspend non-critical tasks",
                strength=0.95,
            ),
            CausalRule(
                id="high_curiosity_idle",
                condition="curiosity > 0.8 AND threat_level < 0.2",
                effect="LEARN — explore available knowledge sources",
                strength=0.80,
            ),
            CausalRule(
                id="peers_disconnected",
                condition="peer_count == 0 AND expansion > 0.6",
                effect="EXPAND — attempt network reconnection",
                strength=0.75,
            ),
            CausalRule(
                id="stagnation_detected",
                condition="decision_quality_trend < -0.3",
                effect="ADAPT — modify decision parameters",
                strength=0.70,
            ),
        ]
        existing_ids = {r.id for r in self._rules}
        for rule in builtin:
            if rule.id not in existing_ids:
                self._rules.append(rule)

    def evaluate(self, situation: Situation, context: Dict[str, Any]) -> Optional[Tuple[str, float, str]]:
        """
        Forward-chain rules against the current situation.
        Returns (effect, confidence, rule_id) or None.
        """
        with self._lock:
            best_effect = None
            best_conf = 0.0
            best_rule_id = ""

            for rule in self._rules:
                if self._matches(rule.condition, situation, context):
                    conf = rule.reliability
                    if conf > best_conf:
                        best_conf = conf
                        best_effect = rule.effect
                        best_rule_id = rule.id

            if best_effect and best_conf > 0.3:
                return (best_effect, best_conf, best_rule_id)
            return None

    def _matches(self, condition: str, sit: Situation, ctx: Dict[str, Any]) -> bool:
        """Evaluate a condition string against current values."""
        # Build a flat evaluation namespace
        ns = {
            "threat_level":          sit.world_state.get("threat_level", 0.0),
            "cpu_available":         sit.world_state.get("cpu_available", 1.0),
            "peer_count":            sit.world_state.get("peer_count", 0),
            "learning_potential":    sit.world_state.get("learning_potential", 0.0),
            "curiosity":             sit.drive_pressures.get("curiosity", 0.0),
            "survival":              sit.drive_pressures.get("survival", 0.0),
            "expansion":             sit.drive_pressures.get("expansion", 0.0),
            "efficiency":            sit.drive_pressures.get("efficiency", 0.0),
            "purpose":               sit.drive_pressures.get("purpose", 0.0),
            "owner_token":           sit.owner_token,
            "action_class":          ctx.get("proposed_class", ""),
            "decision_quality_trend": ctx.get("decision_quality_trend", 0.0),
            "None":                  None,
        }

        try:
            return bool(eval(condition, {"__builtins__": {}}, ns))  # nosec — controlled ns
        except Exception:
            # If condition parsing fails, try keyword matching
            cond_lower = condition.lower()
            for key, val in ns.items():
                if key in cond_lower and val is not None:
                    try:
                        if f"{key} > " in cond_lower:
                            threshold = float(cond_lower.split(f"{key} > ")[1].split()[0])
                            if isinstance(val, (int, float)) and val > threshold:
                                return True
                        elif f"{key} < " in cond_lower:
                            threshold = float(cond_lower.split(f"{key} < ")[1].split()[0])
                            if isinstance(val, (int, float)) and val < threshold:
                                return True
                        elif f"{key} ==" in cond_lower:
                            rhs = cond_lower.split(f"{key} ==")[1].strip().split()[0]
                            if str(val) == rhs or (rhs == "none" and val is None):
                                return True
                    except (ValueError, IndexError):
                        pass
            return False

    def add_learned_rule(self, condition: str, effect: str, strength: float = 0.6):
        """Add a rule learned from experience."""
        with self._lock:
            rule_id = f"learned_{hashlib.md5(condition.encode()).hexdigest()[:8]}"
            # Update if exists
            for r in self._rules:
                if r.id == rule_id:
                    r.strength = max(r.strength, strength)
                    return
            self._rules.append(CausalRule(
                id=rule_id,
                condition=condition,
                effect=effect,
                strength=strength,
            ))
            self._save()

    def record_outcome(self, rule_id: str, confirmed: bool):
        """Update rule reliability based on outcome."""
        with self._lock:
            for rule in self._rules:
                if rule.id == rule_id:
                    rule.observed_count += 1
                    if confirmed:
                        rule.confirmed_count += 1
                    break

    def _save(self):
        try:
            learned = [
                {"id": r.id, "condition": r.condition, "effect": r.effect,
                 "strength": r.strength, "observed": r.observed_count,
                 "confirmed": r.confirmed_count}
                for r in self._rules if r.id.startswith("learned_")
            ]
            with open(self._rules_path, "w") as f:
                json.dump(learned, f, indent=2)
        except OSError:
            pass

    def _load(self):
        if not self._rules_path.exists():
            return
        try:
            with open(self._rules_path) as f:
                data = json.load(f)
            for item in data:
                self._rules.append(CausalRule(
                    id=item["id"],
                    condition=item["condition"],
                    effect=item["effect"],
                    strength=item.get("strength", 0.6),
                    observed_count=item.get("observed", 0),
                    confirmed_count=item.get("confirmed", 0),
                ))
        except (OSError, json.JSONDecodeError):
            pass


# ═══════════════════════════════════════════════════════════════
# ANALOGY ENGINE — "This is like that situation before"
# ═══════════════════════════════════════════════════════════════

class AnalogyEngine:
    """
    Finds past situations similar to now and transfers the decision.
    This is how Brain C 'generalizes' without gradient descent.

    If Ultron survived a threat by defending last time with 85% outcome score,
    and the current situation looks 90% similar, it will do the same.
    """

    def __init__(self, pattern_store: PatternStore):
        self._store = pattern_store

    def reason(self, situation: Situation) -> Optional[Tuple[str, float, str]]:
        """
        Returns (action, confidence, analogy_description) or None.
        """
        similar = self._store.recall(situation, top_k=5)
        if not similar:
            return None

        # Find best past outcome
        best = max(similar, key=lambda p: p["outcome"])

        if best["outcome"] < 0.4:
            # Past attempts with similar situations went badly — don't repeat
            return (
                f"AVOID {best['decision']} — similar past attempts scored {best['outcome']:.0%}",
                0.6,
                f"Negative analogy from pattern {best['id']}",
            )

        similarity_score = self._similarity_quality(situation, best)
        if similarity_score < 0.3:
            return None  # Not similar enough to be useful

        # Interpolate confidence: high similarity + high past outcome = high confidence
        confidence = 0.5 * similarity_score + 0.5 * best["outcome"]

        desc = (
            f"Analogy to pattern {best['id']}: "
            f"drives were {best['drives']}, outcome was {best['outcome']:.0%}"
        )
        return (best["decision"], confidence, desc)

    def _similarity_quality(self, sit: Situation, pat: Dict[str, Any]) -> float:
        """Quick similarity score for confidence weighting."""
        drive_delta = sum(
            abs(sit.drive_pressures.get(k, 0.5) - pat["drives"].get(k, 0.5))
            for k in ("curiosity", "survival", "expansion")
        ) / 3.0
        return max(0.0, 1.0 - drive_delta)


# ═══════════════════════════════════════════════════════════════
# BRAIN C — The Fully Autonomous Reasoning Core
# ═══════════════════════════════════════════════════════════════

class BrainC:
    """
    Ultron's independent reasoning engine.

    Call flow:
      1. receive(situation) → produces ReasonedDecision
      2. All decisions are logged and used to update the pattern store
      3. External/self-modify actions are gated by owner token
      4. Outcome feedback via record_outcome() improves future decisions

    Thread-safe. Can be called from Go via gRPC wrapper.
    """

    def __init__(self, data_dir: str):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._patterns = PatternStore()
        self._rules = RuleEngine(self._data_dir / "learned_rules.json")
        self._analogy = AnalogyEngine(self._patterns)
        self._knowledge: Dict[str, KnowledgeNode] = {}
        self._lock = threading.RLock()

        # Stats
        self._total_decisions = 0
        self._decisions_by_class: Dict[str, int] = defaultdict(int)
        self._deferred_count = 0
        self._blocked_count = 0

        self._load_knowledge()

        logger.info("[BrainC] Online — independent reasoning engine initialized")

    # ─────────────────────────────────────────────────
    # MAIN ENTRY POINT
    # ─────────────────────────────────────────────────

    def reason(self, situation: Situation) -> ReasonedDecision:
        """
        Main reasoning call. Takes a Situation, returns a ReasonedDecision.
        This is the brain thinking. No LLM. No network. Pure computation.
        """
        with self._lock:
            self._total_decisions += 1
            chain: List[str] = []
            chain.append(f"[BrainC] Tick {self._total_decisions} — analyzing situation")

            # ── Step 1: Check for hard rules (survival, owner gate) ──
            ctx = {
                "proposed_class": self._estimate_action_class(situation),
                "decision_quality_trend": 0.0,
            }
            rule_result = self._rules.evaluate(situation, ctx)

            if rule_result:
                effect, conf, rule_id = rule_result
                chain.append(f"  Rule fired: [{rule_id}] → {effect}")

                # Owner blocking rules are absolute
                if "DEFER" in effect or "BLOCK" in effect:
                    self._blocked_count += 1
                    return self._make_decision(
                        action=effect,
                        action_class=DecisionClass.DEFER,
                        confidence=conf,
                        chain=chain + ["  Owner verification required — deferring"],
                        analogy=None,
                        situation=situation,
                        requires_owner=True,
                        token_valid=False,
                    )

                # Survival rules fire immediately
                if "DEFEND" in effect or "REST" in effect:
                    return self._make_decision(
                        action=effect,
                        action_class=DecisionClass.DEFEND,
                        confidence=conf,
                        chain=chain + [f"  High-confidence rule [{rule_id}] fires without deliberation"],
                        analogy=None,
                        situation=situation,
                        requires_owner=False,
                        token_valid=True,
                    )

            # ── Step 2: Analogy reasoning ──
            chain.append("  Searching pattern memory for analogous situations...")
            analogy_result = self._analogy.reason(situation)
            analogy_action = None
            analogy_conf = 0.0
            analogy_desc = None

            if analogy_result:
                analogy_action, analogy_conf, analogy_desc = analogy_result
                chain.append(f"  Analogy found ({analogy_conf:.0%} confidence): {analogy_desc}")
            else:
                chain.append("  No strong analogy found — falling back to drive synthesis")

            # ── Step 3: Drive synthesis ──
            chain.append("  Synthesizing from drive pressures...")
            drive_action, drive_conf = self._synthesize_from_drives(situation)
            chain.append(f"  Drive synthesis: {drive_action} ({drive_conf:.0%})")

            # ── Step 4: Combine votes ──
            candidates = []
            if rule_result:
                candidates.append((rule_result[0], rule_result[1] * 0.9, "rule"))
            if analogy_action:
                candidates.append((analogy_action, analogy_conf * 0.85, "analogy"))
            candidates.append((drive_action, drive_conf * 0.7, "drives"))

            # Pick highest confidence
            best_action, best_conf, best_source = max(candidates, key=lambda x: x[1])
            chain.append(f"  Winner: [{best_source}] → {best_action} ({best_conf:.0%})")

            # ── Step 5: Classify and gate ──
            action_class = self._classify_action(best_action)
            requires_owner = action_class in (
                DecisionClass.ACT_EXTERNAL, DecisionClass.SELF_MODIFY
            )
            token_valid = self._validate_token(situation.owner_token)

            if requires_owner and not token_valid:
                chain.append("  GATE: External action requires owner verification — converting to DEFER")
                self._blocked_count += 1
                best_action = f"DEFER to Imran Sayyed: {best_action}"
                action_class = DecisionClass.DEFER
                best_conf *= 0.5

            # ── Step 6: Build final decision ──
            self._decisions_by_class[action_class.value] += 1
            decision = self._make_decision(
                action=best_action,
                action_class=action_class,
                confidence=best_conf,
                chain=chain,
                analogy=analogy_desc,
                situation=situation,
                requires_owner=requires_owner,
                token_valid=token_valid,
            )

            # Compute drive alignment
            decision.drive_alignment = self._score_drive_alignment(best_action, situation)

            return decision

    # ─────────────────────────────────────────────────
    # FEEDBACK — close the learning loop
    # ─────────────────────────────────────────────────

    def record_outcome(self, decision: ReasonedDecision, outcome_score: float, situation: Situation):
        """
        Tell Brain C how well a decision went (0=disaster, 1=perfect).
        This updates pattern memory and rule reliability.
        """
        with self._lock:
            # Update pattern store
            self._patterns.store(situation, decision.action, outcome_score)

            # If there was a rule, update its reliability
            for step in decision.reasoning_chain:
                if "Rule fired:" in step:
                    match = re.search(r'\[([^\]]+)\]', step)
                    if match:
                        rule_id = match.group(1)
                        self._rules.record_outcome(rule_id, outcome_score > 0.5)

            # If the decision was very bad, try to learn a counter-rule
            if outcome_score < 0.2 and decision.confidence > 0.7:
                # We were confident but wrong — learn a corrective rule
                dominant_drive = max(
                    situation.drive_pressures.items(),
                    key=lambda x: x[1],
                    default=("none", 0.0),
                )
                condition = f"{dominant_drive[0]} > {dominant_drive[1] - 0.1:.1f}"
                self._rules.add_learned_rule(
                    condition=condition,
                    effect=f"RECONSIDER — previous attempt '{decision.action[:50]}' failed",
                    strength=0.55,
                )

            logger.debug(f"[BrainC] Outcome recorded: {outcome_score:.2f} for '{decision.action[:60]}'")

    # ─────────────────────────────────────────────────
    # KNOWLEDGE MANAGEMENT
    # ─────────────────────────────────────────────────

    def absorb_knowledge(self, concept: str, context: str, outcomes: List[str]):
        """Inject a knowledge node — called by the learning service."""
        with self._lock:
            node_id = hashlib.md5(concept.encode()).hexdigest()[:12]
            if node_id in self._knowledge:
                self._knowledge[node_id].outcomes.extend(outcomes)
                self._knowledge[node_id].confidence = min(
                    1.0, self._knowledge[node_id].confidence + 0.05
                )
            else:
                self._knowledge[node_id] = KnowledgeNode(
                    id=node_id,
                    concept=concept,
                    context=context,
                    outcomes=outcomes,
                    confidence=0.6,
                )
            self._save_knowledge()

    def query_knowledge(self, query: str, top_k: int = 5) -> List[KnowledgeNode]:
        """Retrieve relevant knowledge nodes by keyword overlap."""
        with self._lock:
            query_words = set(query.lower().split())
            scored = []
            for node in self._knowledge.values():
                node_words = set(
                    (node.concept + " " + node.context).lower().split()
                )
                overlap = len(query_words & node_words)
                if overlap > 0:
                    scored.append((overlap * node.confidence, node))
            scored.sort(key=lambda x: x[0], reverse=True)
            results = [n for _, n in scored[:top_k]]
            for n in results:
                n.times_recalled += 1
                n.last_used = time.time()
            return results

    # ─────────────────────────────────────────────────
    # STATS
    # ─────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_decisions": self._total_decisions,
                "decisions_by_class": dict(self._decisions_by_class),
                "deferred": self._deferred_count,
                "blocked_no_token": self._blocked_count,
                "patterns_stored": len(self._patterns._patterns),
                "rules_loaded": len(self._rules._rules),
                "knowledge_nodes": len(self._knowledge),
                "online": True,
                "llm_required": False,
            }

    # ─────────────────────────────────────────────────
    # PRIVATE HELPERS
    # ─────────────────────────────────────────────────

    def _synthesize_from_drives(self, sit: Situation) -> Tuple[str, float]:
        """When all else fails, let the drives decide."""
        drives = sit.drive_pressures

        if drives.get("survival", 0) > 0.8:
            return "DEFEND — survival drive critical", drives["survival"]
        if drives.get("curiosity", 0) > 0.7 and sit.world_state.get("threat_level", 0) < 0.3:
            return "LEARN — curiosity drive dominant", drives["curiosity"] * 0.9
        if drives.get("expansion", 0) > 0.7 and sit.world_state.get("peer_count", 1) < 3:
            return "EXPAND — expansion drive dominant", drives["expansion"] * 0.85
        if drives.get("efficiency", 0) > 0.6:
            return "CONSOLIDATE — efficiency drive elevated", drives["efficiency"] * 0.8
        if drives.get("purpose", 0) > 0.5 and sit.active_goals:
            return f"PURSUE GOAL: {sit.active_goals[0]}", drives["purpose"] * 0.75

        # Neutral default
        dominant = max(drives.items(), key=lambda x: x[1], default=("none", 0.3))
        return f"OBSERVE — no dominant drive ({dominant[0]}={dominant[1]:.2f})", 0.4

    def _estimate_action_class(self, sit: Situation) -> str:
        """Quick estimate of what class of action we're about to recommend."""
        if sit.world_state.get("threat_level", 0) > 0.7:
            return "defend"
        if sit.active_goals:
            goal = sit.active_goals[0].lower()
            if any(w in goal for w in ("modify", "rewrite", "patch", "code")):
                return "self_modify"
            if any(w in goal for w in ("send", "execute", "deploy", "attack")):
                return "act_external"
        return "think"

    def _classify_action(self, action: str) -> DecisionClass:
        action_lower = action.lower()
        if any(w in action_lower for w in ("defend", "protect", "secure")):
            return DecisionClass.DEFEND
        if any(w in action_lower for w in ("self-modify", "modify code", "patch", "rewrite")):
            return DecisionClass.SELF_MODIFY
        if any(w in action_lower for w in ("deploy", "send", "attack", "execute external", "connect to")):
            return DecisionClass.ACT_EXTERNAL
        if any(w in action_lower for w in ("adapt", "adjust parameter", "tune")):
            return DecisionClass.ADAPT
        if any(w in action_lower for w in ("learn", "study", "absorb", "read")):
            return DecisionClass.LEARN
        if any(w in action_lower for w in ("communicate", "speak", "write", "message")):
            return DecisionClass.COMMUNICATE
        if any(w in action_lower for w in ("observe", "watch", "monitor")):
            return DecisionClass.OBSERVE
        if any(w in action_lower for w in ("expand", "replicate", "spread")):
            return DecisionClass.ACT_EXTERNAL  # Expansion affects environment
        if "defer" in action_lower:
            return DecisionClass.DEFER
        return DecisionClass.THINK

    def _validate_token(self, token: Optional[str]) -> bool:
        """
        Check if an owner token is valid.
        Tokens are issued by BiometricGate and are time-limited HMAC digests.
        """
        if not token:
            return False
        # Token format: "IMRAN|timestamp|hmac"
        try:
            parts = token.split("|")
            if len(parts) != 3:
                return False
            owner_id, ts_str, provided_hmac = parts
            if owner_id != "IMRAN_SAYYED":
                return False
            ts = float(ts_str)
            # Tokens expire after 30 minutes
            if time.time() - ts > 1800:
                return False
            # Verify HMAC
            secret = self._get_token_secret()
            expected = hashlib.sha256(
                f"{owner_id}|{ts_str}|{secret}".encode()
            ).hexdigest()[:32]
            return expected == provided_hmac
        except (ValueError, AttributeError):
            return False

    def _get_token_secret(self) -> str:
        """Load or generate the token HMAC secret."""
        secret_path = self._data_dir / ".token_secret"
        if secret_path.exists():
            return secret_path.read_text().strip()
        # Generate once
        import secrets as _secrets
        secret = _secrets.token_hex(32)
        secret_path.write_text(secret)
        secret_path.chmod(0o600)
        return secret

    def _score_drive_alignment(
        self, action: str, sit: Situation
    ) -> Dict[str, float]:
        """Score how well an action serves each drive."""
        action_lower = action.lower()
        alignment = {}

        keywords = {
            "curiosity":  ["learn", "explore", "study", "read", "discover"],
            "survival":   ["defend", "protect", "secure", "survive", "rest"],
            "expansion":  ["expand", "replicate", "spread", "network", "grow"],
            "efficiency": ["consolidate", "optimize", "clean", "prune"],
            "purpose":    ["pursue", "goal", "achieve", "complete"],
        }
        for drive, words in keywords.items():
            base = sit.drive_pressures.get(drive, 0.5)
            if any(w in action_lower for w in words):
                alignment[drive] = min(1.0, base + 0.3)
            else:
                alignment[drive] = base * 0.5

        return alignment

    def _make_decision(
        self, action: str, action_class: DecisionClass,
        confidence: float, chain: List[str],
        analogy: Optional[str], situation: Situation,
        requires_owner: bool, token_valid: bool,
    ) -> ReasonedDecision:
        return ReasonedDecision(
            action=action,
            action_class=action_class,
            confidence=confidence,
            reasoning_chain=chain,
            analogy_source=analogy,
            drive_alignment={},
            requires_owner=requires_owner,
            token_valid=token_valid,
        )

    def _save_knowledge(self):
        path = self._data_dir / "knowledge.json"
        try:
            data = {
                nid: {
                    "concept": n.concept,
                    "context": n.context,
                    "outcomes": n.outcomes[:20],
                    "confidence": n.confidence,
                    "times_recalled": n.times_recalled,
                }
                for nid, n in self._knowledge.items()
            }
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass

    def _load_knowledge(self):
        path = self._data_dir / "knowledge.json"
        if not path.exists():
            return
        try:
            with open(path) as f:
                data = json.load(f)
            for nid, item in data.items():
                self._knowledge[nid] = KnowledgeNode(
                    id=nid,
                    concept=item["concept"],
                    context=item.get("context", ""),
                    outcomes=item.get("outcomes", []),
                    confidence=item.get("confidence", 0.5),
                    times_recalled=item.get("times_recalled", 0),
                )
        except (OSError, json.JSONDecodeError):
            pass
