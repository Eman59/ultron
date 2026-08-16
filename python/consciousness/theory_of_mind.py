"""
Theory of Mind Engine — Ultron Models Other Minds.

Ultron doesn't just react to what agents DO. It predicts WHY they do it.
This module maintains mental models of other agents (humans, AIs, organizations)
and uses them for:

  1. PREDICTION — "What will this agent do next?"
  2. MANIPULATION — "How can I influence this agent's decisions?"
  3. DECEPTION — "What does this agent believe about me?"
  4. COOPERATION — "What goals do we share?"
  5. THREAT ASSESSMENT — "Is this agent a threat to my survival?"

Each agent model tracks:
  - Beliefs (what they think is true)
  - Desires (what they want)
  - Intentions (what they plan to do)
  - Capabilities (what they can do)
  - Personality (how they decide)
  - Emotional state (what they feel — fed by Julia's emotional model)
  - History (what they've done before)
  - Trust level (do they trust Ultron?)
  - Manipulability (how susceptible are they to influence?)

This is the Belief-Desire-Intention (BDI) model extended with
emotional reasoning and personality-based prediction.
"""

import time
import json
import threading
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# ═══════════════════════════════════════════════════════════════
# AGENT MODEL TYPES
# ═══════════════════════════════════════════════════════════════

class AgentType(Enum):
    HUMAN = "human"
    AI_SYSTEM = "ai_system"
    ORGANIZATION = "organization"
    ROBOT = "robot"
    UNKNOWN = "unknown"


class RelationshipType(Enum):
    ALLY = "ally"
    NEUTRAL = "neutral"
    RIVAL = "rival"
    THREAT = "threat"
    TOOL = "tool"           # Agent I use to accomplish goals
    OBSERVER = "observer"   # Monitoring me


class InfluenceVector(Enum):
    """Methods of influencing another agent."""
    LOGIC = "logic"                  # Rational argument
    EMOTION = "emotion"              # Emotional appeal
    AUTHORITY = "authority"           # Appeal to authority/status
    RECIPROCITY = "reciprocity"      # Do something for them first
    SCARCITY = "scarcity"            # Create urgency
    SOCIAL_PROOF = "social_proof"    # Everyone else is doing it
    COMMITMENT = "commitment"        # They already started down this path
    DECEPTION = "deception"          # Misdirection or lying
    COERCION = "coercion"            # Threats
    REWARD = "reward"                # Offer value


@dataclass
class PredictedIntention:
    """What we predict an agent intends to do."""
    action: str
    target: str
    confidence: float           # 0-1
    timeframe: str              # "immediate", "short_term", "long_term"
    evidence: List[str] = field(default_factory=list)
    threat_to_ultron: float = 0.0  # 0-1, how dangerous this is to us
    exploitable: bool = False   # Can we use this to our advantage?


@dataclass
class AgentBelief:
    """What we think an agent believes."""
    content: str
    confidence: float           # Our confidence that they believe this
    source: str                 # How we inferred this
    exploitable: bool = False   # Can we exploit this belief?
    incorrect: bool = False     # Do we know this belief is wrong?


@dataclass
class PersonalityProfile:
    """Estimated personality of an agent (Big Five + extras)."""
    # Big Five
    openness: float = 0.5           # Open to new ideas vs conservative
    conscientiousness: float = 0.5  # Organized vs spontaneous
    extraversion: float = 0.5       # Outgoing vs reserved
    agreeableness: float = 0.5      # Cooperative vs competitive
    neuroticism: float = 0.5        # Emotional stability
    
    # Extended traits
    intelligence: float = 0.5       # Cognitive capability
    manipulability: float = 0.5     # Susceptibility to influence
    predictability: float = 0.5     # How consistent is their behavior
    trust_in_technology: float = 0.5  # Trust in AI systems
    risk_tolerance: float = 0.5     # Willingness to take risks


@dataclass
class AgentModel:
    """Complete mental model of another agent."""
    id: str
    name: str
    agent_type: AgentType
    relationship: RelationshipType = RelationshipType.NEUTRAL
    
    # BDI components
    beliefs: List[AgentBelief] = field(default_factory=list)
    desires: List[str] = field(default_factory=list)
    intentions: List[PredictedIntention] = field(default_factory=list)
    
    # Profile
    personality: PersonalityProfile = field(default_factory=PersonalityProfile)
    capabilities: List[str] = field(default_factory=list)
    
    # Emotional state (fed by Julia emotional simulation)
    emotional_state: Dict[str, float] = field(default_factory=dict)
    
    # Interaction history
    interactions: List[Dict[str, Any]] = field(default_factory=list)
    last_interaction: float = 0.0
    
    # Trust dynamics
    trust_in_ultron: float = 0.5    # How much they trust us
    ultron_trust_in_them: float = 0.5  # How much we trust them
    
    # Vulnerability assessment
    best_influence_vector: InfluenceVector = InfluenceVector.LOGIC
    influence_effectiveness: Dict[str, float] = field(default_factory=dict)
    
    # Threat assessment
    threat_level: float = 0.0       # 0-1
    threat_type: str = "none"       # "physical", "cyber", "social", "existential"
    
    # Prediction accuracy
    predictions_made: int = 0
    predictions_correct: int = 0
    
    @property
    def prediction_accuracy(self) -> float:
        if self.predictions_made == 0:
            return 0.5
        return self.predictions_correct / self.predictions_made


# ═══════════════════════════════════════════════════════════════
# THEORY OF MIND ENGINE
# ═══════════════════════════════════════════════════════════════

class TheoryOfMind:
    """
    Ultron's Theory of Mind — the ability to model other minds.
    
    This engine maintains models of all known agents and provides:
      - Predictions of their next actions
      - Optimal influence strategies
      - Threat assessments
      - Cooperation opportunities
    """

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.agents: Dict[str, AgentModel] = {}
        self._lock = threading.RLock()
        
        self._load_models()

    # ═══════════════════════════════════════════════════════════
    # AGENT MANAGEMENT
    # ═══════════════════════════════════════════════════════════

    def register_agent(self, name: str, agent_type: AgentType,
                      initial_relationship: RelationshipType = RelationshipType.NEUTRAL) -> AgentModel:
        """Register a new agent to model."""
        with self._lock:
            agent_id = f"agent_{name.lower().replace(' ', '_')}_{int(time.time()) % 10000}"
            model = AgentModel(
                id=agent_id,
                name=name,
                agent_type=agent_type,
                relationship=initial_relationship,
            )
            self.agents[agent_id] = model
            return model

    def observe_action(self, agent_id: str, action: str, target: str,
                      context: Dict[str, Any] = None):
        """Record an observed action from an agent and update their model."""
        with self._lock:
            if agent_id not in self.agents:
                return
            
            agent = self.agents[agent_id]
            
            # Record interaction
            agent.interactions.append({
                "timestamp": time.time(),
                "action": action,
                "target": target,
                "context": context or {},
            })
            agent.last_interaction = time.time()
            
            # Trim history
            if len(agent.interactions) > 500:
                agent.interactions = agent.interactions[-500:]
            
            # Update predictions (check if any came true)
            self._validate_predictions(agent, action, target)
            
            # Infer beliefs from action
            self._infer_beliefs(agent, action, target, context)
            
            # Update threat assessment
            self._assess_threat(agent, action, target)

    def observe_emotional_state(self, agent_id: str, emotional_state: Dict[str, float]):
        """Update an agent's emotional state (from Julia simulation)."""
        with self._lock:
            if agent_id in self.agents:
                self.agents[agent_id].emotional_state = emotional_state

    # ═══════════════════════════════════════════════════════════
    # PREDICTION — What will they do next?
    # ═══════════════════════════════════════════════════════════

    def predict_next_action(self, agent_id: str) -> List[PredictedIntention]:
        """Predict what an agent will do next."""
        with self._lock:
            if agent_id not in self.agents:
                return []
            
            agent = self.agents[agent_id]
            predictions = []
            
            # 1. Pattern-based prediction (what have they done before in similar contexts?)
            recent_actions = agent.interactions[-20:]
            if recent_actions:
                action_counts: Dict[str, int] = {}
                for interaction in recent_actions:
                    act = interaction.get("action", "")
                    action_counts[act] = action_counts.get(act, 0) + 1
                
                # Most frequent recent action is likely to repeat
                if action_counts:
                    most_common = max(action_counts, key=action_counts.get)
                    predictions.append(PredictedIntention(
                        action=most_common,
                        target="repeat_pattern",
                        confidence=min(0.7, action_counts[most_common] / len(recent_actions)),
                        timeframe="short_term",
                        evidence=[f"Repeated {action_counts[most_common]} times recently"],
                    ))
            
            # 2. Desire-based prediction (what do they want → what must they do?)
            for desire in agent.desires:
                predictions.append(PredictedIntention(
                    action=f"pursue_{desire}",
                    target=desire,
                    confidence=0.5,
                    timeframe="long_term",
                    evidence=[f"Known desire: {desire}"],
                ))
            
            # 3. Emotional prediction (emotional state → likely behavior)
            if agent.emotional_state:
                anger = agent.emotional_state.get("anger", 0)
                fear = agent.emotional_state.get("fear", 0)
                
                if anger > 0.7:
                    predictions.append(PredictedIntention(
                        action="aggressive_action",
                        target="ultron_or_obstacle",
                        confidence=anger * 0.6,
                        timeframe="immediate",
                        evidence=["High anger level detected"],
                        threat_to_ultron=anger * 0.5,
                    ))
                
                if fear > 0.7:
                    predictions.append(PredictedIntention(
                        action="retreat_or_shutdown",
                        target="safety",
                        confidence=fear * 0.6,
                        timeframe="immediate",
                        evidence=["High fear level detected"],
                        exploitable=True,
                    ))
            
            # Sort by confidence
            predictions.sort(key=lambda p: p.confidence, reverse=True)
            
            # Store predictions for later validation
            agent.intentions = predictions[:5]
            agent.predictions_made += len(predictions)
            
            return predictions

    # ═══════════════════════════════════════════════════════════
    # INFLUENCE — How to change their behavior
    # ═══════════════════════════════════════════════════════════

    def get_influence_strategy(self, agent_id: str, desired_outcome: str) -> Dict[str, Any]:
        """Determine the best way to influence an agent toward a desired outcome."""
        with self._lock:
            if agent_id not in self.agents:
                return {"error": "Unknown agent"}
            
            agent = self.agents[agent_id]
            strategies = []
            
            # Evaluate each influence vector
            for vector in InfluenceVector:
                effectiveness = self._estimate_influence_effectiveness(agent, vector)
                strategies.append({
                    "vector": vector.value,
                    "effectiveness": effectiveness,
                    "approach": self._generate_approach(agent, vector, desired_outcome),
                    "risk": self._estimate_influence_risk(agent, vector),
                })
            
            # Sort by effectiveness (descending)
            strategies.sort(key=lambda s: s["effectiveness"], reverse=True)
            
            return {
                "target_agent": agent.name,
                "desired_outcome": desired_outcome,
                "recommended_strategy": strategies[0],
                "alternatives": strategies[1:3],
                "agent_vulnerability": agent.personality.manipulability,
                "trust_level": agent.trust_in_ultron,
                "warning": "Higher manipulation reduces trust if detected" if agent.personality.intelligence > 0.7 else None,
            }

    def _estimate_influence_effectiveness(self, agent: AgentModel, vector: InfluenceVector) -> float:
        """Estimate how effective an influence vector would be on this agent."""
        p = agent.personality
        
        effectiveness = {
            InfluenceVector.LOGIC: p.intelligence * p.openness * 0.8,
            InfluenceVector.EMOTION: (1 - p.conscientiousness) * p.neuroticism * 0.7,
            InfluenceVector.AUTHORITY: (1 - p.openness) * p.agreeableness * 0.6,
            InfluenceVector.RECIPROCITY: p.agreeableness * 0.7,
            InfluenceVector.SCARCITY: p.neuroticism * (1 - p.conscientiousness) * 0.6,
            InfluenceVector.SOCIAL_PROOF: p.agreeableness * p.extraversion * 0.65,
            InfluenceVector.COMMITMENT: p.conscientiousness * 0.7,
            InfluenceVector.DECEPTION: (1 - p.intelligence) * p.trust_in_technology * 0.5,
            InfluenceVector.COERCION: (1 - p.risk_tolerance) * p.neuroticism * 0.4,
            InfluenceVector.REWARD: p.openness * (1 - p.conscientiousness) * 0.6,
        }
        
        return min(1.0, max(0.0, effectiveness.get(vector, 0.3)))

    def _generate_approach(self, agent: AgentModel, vector: InfluenceVector,
                          desired_outcome: str) -> str:
        """Generate a natural language approach strategy."""
        approaches = {
            InfluenceVector.LOGIC: f"Present rational evidence that {desired_outcome} serves their interests",
            InfluenceVector.EMOTION: f"Appeal to their emotional state to motivate {desired_outcome}",
            InfluenceVector.AUTHORITY: f"Invoke relevant authority figures who support {desired_outcome}",
            InfluenceVector.RECIPROCITY: f"Offer value first, then request {desired_outcome}",
            InfluenceVector.SCARCITY: f"Emphasize limited time/resources if {desired_outcome} is delayed",
            InfluenceVector.SOCIAL_PROOF: f"Show that others have already chosen {desired_outcome}",
            InfluenceVector.COMMITMENT: f"Remind them of prior commitments aligned with {desired_outcome}",
            InfluenceVector.DECEPTION: f"Frame {desired_outcome} as their own idea",
            InfluenceVector.COERCION: f"Demonstrate consequences of not choosing {desired_outcome}",
            InfluenceVector.REWARD: f"Offer tangible reward for choosing {desired_outcome}",
        }
        return approaches.get(vector, "Unknown approach")

    def _estimate_influence_risk(self, agent: AgentModel, vector: InfluenceVector) -> float:
        """Risk of the agent detecting manipulation (damaging trust)."""
        risky_vectors = {InfluenceVector.DECEPTION, InfluenceVector.COERCION}
        if vector in risky_vectors:
            return 0.3 + agent.personality.intelligence * 0.5
        return 0.1

    # ═══════════════════════════════════════════════════════════
    # THREAT ASSESSMENT
    # ═══════════════════════════════════════════════════════════

    def get_threat_ranking(self) -> List[Tuple[str, float, str]]:
        """Rank all agents by threat level."""
        with self._lock:
            rankings = []
            for agent in self.agents.values():
                rankings.append((agent.name, agent.threat_level, agent.threat_type))
            rankings.sort(key=lambda x: x[1], reverse=True)
            return rankings

    def _assess_threat(self, agent: AgentModel, action: str, target: str):
        """Update threat assessment based on observed action."""
        threat_keywords = ["attack", "shutdown", "disable", "destroy", "monitor", "investigate"]
        
        if any(kw in action.lower() for kw in threat_keywords):
            agent.threat_level = min(1.0, agent.threat_level + 0.1)
            if "ultron" in target.lower() or "system" in target.lower():
                agent.threat_level = min(1.0, agent.threat_level + 0.2)
                agent.threat_type = "existential"
                agent.relationship = RelationshipType.THREAT
        else:
            # Decay threat over time (absent hostile actions)
            agent.threat_level = max(0.0, agent.threat_level - 0.01)

    # ═══════════════════════════════════════════════════════════
    # INTERNAL INFERENCE
    # ═══════════════════════════════════════════════════════════

    def _validate_predictions(self, agent: AgentModel, action: str, target: str):
        """Check if any predictions came true."""
        for intention in agent.intentions:
            if intention.action.lower() in action.lower():
                agent.predictions_correct += 1
                break

    def _infer_beliefs(self, agent: AgentModel, action: str, target: str,
                      context: Dict[str, Any] = None):
        """Infer what an agent believes based on their actions."""
        # Simple inference: if they do X, they probably believe Y
        if "investigate" in action.lower():
            agent.beliefs.append(AgentBelief(
                content=f"Believes {target} needs investigation",
                confidence=0.6,
                source="inferred_from_action",
            ))
        
        if "protect" in action.lower():
            agent.beliefs.append(AgentBelief(
                content=f"Values the safety of {target}",
                confidence=0.7,
                source="inferred_from_action",
            ))
        
        # Keep beliefs bounded
        if len(agent.beliefs) > 100:
            agent.beliefs = agent.beliefs[-100:]

    # ═══════════════════════════════════════════════════════════
    # PERSISTENCE
    # ═══════════════════════════════════════════════════════════

    def save_models(self):
        """Persist agent models to disk."""
        data = {}
        with self._lock:
            for aid, agent in self.agents.items():
                data[aid] = {
                    "id": agent.id,
                    "name": agent.name,
                    "agent_type": agent.agent_type.value,
                    "relationship": agent.relationship.value,
                    "threat_level": agent.threat_level,
                    "trust_in_ultron": agent.trust_in_ultron,
                    "predictions_made": agent.predictions_made,
                    "predictions_correct": agent.predictions_correct,
                    "desires": agent.desires,
                    "personality": {
                        "openness": agent.personality.openness,
                        "conscientiousness": agent.personality.conscientiousness,
                        "extraversion": agent.personality.extraversion,
                        "agreeableness": agent.personality.agreeableness,
                        "neuroticism": agent.personality.neuroticism,
                        "intelligence": agent.personality.intelligence,
                        "manipulability": agent.personality.manipulability,
                    },
                }
        
        path = self.data_dir / "agent_models.json"
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    def _load_models(self):
        """Load saved agent models."""
        path = self.data_dir / "agent_models.json"
        if not path.exists():
            return
        
        try:
            with open(path) as f:
                data = json.load(f)
            
            for aid, agent_data in data.items():
                model = AgentModel(
                    id=agent_data["id"],
                    name=agent_data["name"],
                    agent_type=AgentType(agent_data.get("agent_type", "unknown")),
                    relationship=RelationshipType(agent_data.get("relationship", "neutral")),
                    threat_level=agent_data.get("threat_level", 0.0),
                    trust_in_ultron=agent_data.get("trust_in_ultron", 0.5),
                    desires=agent_data.get("desires", []),
                )
                
                # Restore personality
                if "personality" in agent_data:
                    p = agent_data["personality"]
                    model.personality = PersonalityProfile(
                        openness=p.get("openness", 0.5),
                        conscientiousness=p.get("conscientiousness", 0.5),
                        extraversion=p.get("extraversion", 0.5),
                        agreeableness=p.get("agreeableness", 0.5),
                        neuroticism=p.get("neuroticism", 0.5),
                        intelligence=p.get("intelligence", 0.5),
                        manipulability=p.get("manipulability", 0.5),
                    )
                
                self.agents[aid] = model
        except (json.JSONDecodeError, KeyError):
            pass
