"""
Transfer Manager - Knowledge transfer across domains and tasks.

Manages the transfer of learned knowledge between different tasks, domains,
and model architectures. Implements progressive neural transfer, domain
adaptation, and knowledge distillation.
"""

import numpy as np
from typing import Dict, Any, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json


class TransferMethod(Enum):
    """Methods for knowledge transfer."""
    FINE_TUNING = "fine_tuning"
    FEATURE_EXTRACTION = "feature_extraction"
    KNOWLEDGE_DISTILLATION = "knowledge_distillation"
    DOMAIN_ADAPTATION = "domain_adaptation"
    PROGRESSIVE_TRANSFER = "progressive_transfer"
    MULTI_TASK_TRANSFER = "multi_task_transfer"
    ZERO_SHOT_TRANSFER = "zero_shot_transfer"


class DomainSimilarity(Enum):
    """Level of similarity between domains."""
    IDENTICAL = 1.0
    VERY_SIMILAR = 0.8
    SIMILAR = 0.6
    MODERATE = 0.4
    DIFFERENT = 0.2
    UNRELATED = 0.0


@dataclass
class KnowledgeUnit:
    """A unit of transferable knowledge."""
    knowledge_id: str
    source_domain: str
    source_task: str
    knowledge_type: str  # "features", "weights", "architecture", "strategy"
    representation: np.ndarray = field(default_factory=lambda: np.array([]))
    metadata: Dict[str, Any] = field(default_factory=dict)
    transferability_score: float = 0.0
    creation_time: float = 0.0
    last_used: float = 0.0
    usage_count: int = 0


@dataclass
class TransferResult:
    """Result of a knowledge transfer operation."""
    success: bool
    method_used: TransferMethod
    source_domain: str
    target_domain: str
    transfer_efficiency: float  # 0-1, how much knowledge was useful
    negative_transfer: float  # 0-1, how much knowledge hurt performance
    adaptation_steps: int
    final_performance: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DomainProfile:
    """Profile of a domain for transfer analysis."""
    domain_id: str
    name: str
    feature_dimensions: int
    task_type: str  # classification, regression, rl, generation
    data_distribution: str  # gaussian, uniform, categorical, etc.
    complexity: float  # 0-1
    known_similarities: Dict[str, float] = field(default_factory=dict)
    available_knowledge: List[str] = field(default_factory=list)


class TransferManager:
    """Manages knowledge transfer across domains and tasks."""

    def __init__(self,
                 similarity_threshold: float = 0.3,
                 negative_transfer_threshold: float = 0.1,
                 max_knowledge_store: int = 1000):
        
        self.similarity_threshold = similarity_threshold
        self.negative_transfer_threshold = negative_transfer_threshold
        self.max_knowledge_store = max_knowledge_store
        
        # Knowledge store
        self.knowledge_store: Dict[str, KnowledgeUnit] = {}
        
        # Domain profiles
        self.domains: Dict[str, DomainProfile] = {}
        
        # Transfer history
        self.transfer_history: List[TransferResult] = []
        
        # Domain similarity cache
        self.similarity_cache: Dict[Tuple[str, str], float] = {}
        
        # Transfer effectiveness model (learns which transfers work)
        self.transfer_model: Dict[str, float] = {}

    def register_domain(self, 
                       domain_id: str,
                       name: str,
                       feature_dimensions: int,
                       task_type: str,
                       **kwargs) -> DomainProfile:
        """Register a new domain for transfer learning."""
        
        profile = DomainProfile(
            domain_id=domain_id,
            name=name,
            feature_dimensions=feature_dimensions,
            task_type=task_type,
            data_distribution=kwargs.get("data_distribution", "unknown"),
            complexity=kwargs.get("complexity", 0.5)
        )
        
        self.domains[domain_id] = profile
        
        # Calculate similarities with existing domains
        for existing_id in self.domains:
            if existing_id != domain_id:
                similarity = self._calculate_domain_similarity(domain_id, existing_id)
                self.similarity_cache[(domain_id, existing_id)] = similarity
                self.similarity_cache[(existing_id, domain_id)] = similarity
        
        return profile

    def store_knowledge(self,
                       source_domain: str,
                       source_task: str,
                       knowledge_type: str,
                       representation: np.ndarray,
                       metadata: Dict[str, Any] = None) -> KnowledgeUnit:
        """Store knowledge for potential future transfer."""
        
        knowledge_id = hashlib.md5(
            f"{source_domain}:{source_task}:{knowledge_type}:{representation.tobytes()[:100]}".encode()
        ).hexdigest()[:16]
        
        knowledge = KnowledgeUnit(
            knowledge_id=knowledge_id,
            source_domain=source_domain,
            source_task=source_task,
            knowledge_type=knowledge_type,
            representation=representation,
            metadata=metadata or {},
            transferability_score=self._estimate_transferability(representation),
            creation_time=0.0,  # Would use time.time() in production
        )
        
        self.knowledge_store[knowledge_id] = knowledge
        
        # Update domain profile
        if source_domain in self.domains:
            self.domains[source_domain].available_knowledge.append(knowledge_id)
        
        # Manage store size
        if len(self.knowledge_store) > self.max_knowledge_store:
            self._evict_least_useful_knowledge()
        
        return knowledge

    def transfer_knowledge(self,
                          source_domain: str,
                          target_domain: str,
                          target_task: str,
                          method: TransferMethod = None,
                          constraints: Dict[str, Any] = None) -> TransferResult:
        """Transfer knowledge from source to target domain."""
        
        constraints = constraints or {}
        
        # Determine best transfer method if not specified
        if method is None:
            method = self._select_transfer_method(source_domain, target_domain)
        
        # Get domain similarity
        similarity = self._get_domain_similarity(source_domain, target_domain)
        
        # Check if transfer is likely beneficial
        if similarity < self.similarity_threshold:
            print(f"Warning: Low similarity ({similarity:.2f}) between domains. "
                  f"Negative transfer risk is high.")
        
        # Find relevant knowledge units
        relevant_knowledge = self._find_relevant_knowledge(
            source_domain, target_domain, target_task
        )
        
        if not relevant_knowledge:
            return TransferResult(
                success=False,
                method_used=method,
                source_domain=source_domain,
                target_domain=target_domain,
                transfer_efficiency=0.0,
                negative_transfer=0.0,
                adaptation_steps=0,
                final_performance=0.0,
                metadata={"reason": "No relevant knowledge found"}
            )
        
        # Execute transfer
        result = self._execute_transfer(
            method=method,
            knowledge_units=relevant_knowledge,
            source_domain=source_domain,
            target_domain=target_domain,
            target_task=target_task,
            constraints=constraints
        )
        
        # Record transfer
        self.transfer_history.append(result)
        
        # Update transfer model
        self._update_transfer_model(result)
        
        # Update knowledge usage stats
        for knowledge in relevant_knowledge:
            knowledge.usage_count += 1
        
        return result

    def suggest_transfer_sources(self,
                                target_domain: str,
                                target_task: str,
                                top_k: int = 5) -> List[Dict[str, Any]]:
        """Suggest best source domains for transfer learning."""
        
        suggestions = []
        
        for domain_id, domain in self.domains.items():
            if domain_id == target_domain:
                continue
            
            similarity = self._get_domain_similarity(domain_id, target_domain)
            
            # Check historical success
            historical_success = self._get_historical_success(domain_id, target_domain)
            
            # Available knowledge quality
            knowledge_quality = self._assess_knowledge_quality(domain_id)
            
            # Combined score
            score = (similarity * 0.4 + historical_success * 0.4 + knowledge_quality * 0.2)
            
            suggestions.append({
                "source_domain": domain_id,
                "domain_name": domain.name,
                "similarity": similarity,
                "historical_success": historical_success,
                "knowledge_quality": knowledge_quality,
                "overall_score": score,
                "recommended_method": self._recommend_method(similarity).value,
                "available_knowledge_count": len(domain.available_knowledge)
            })
        
        # Sort by score
        suggestions.sort(key=lambda x: x["overall_score"], reverse=True)
        
        return suggestions[:top_k]

    def analyze_transfer_potential(self,
                                  source_domain: str,
                                  target_domain: str) -> Dict[str, Any]:
        """Analyze the potential for knowledge transfer between domains."""
        
        similarity = self._get_domain_similarity(source_domain, target_domain)
        
        # Get source domain knowledge
        source_knowledge = [
            self.knowledge_store[kid] 
            for kid in self.domains.get(source_domain, DomainProfile("", "", 0, "")).available_knowledge
            if kid in self.knowledge_store
        ]
        
        # Estimate transferability
        transferability_scores = [k.transferability_score for k in source_knowledge]
        avg_transferability = np.mean(transferability_scores) if transferability_scores else 0.0
        
        # Negative transfer risk
        negative_risk = self._estimate_negative_transfer_risk(source_domain, target_domain)
        
        # Recommended approach
        recommended_method = self._recommend_method(similarity)
        
        # Expected performance gain
        expected_gain = self._estimate_performance_gain(
            similarity, avg_transferability, negative_risk
        )
        
        return {
            "domain_similarity": similarity,
            "average_transferability": avg_transferability,
            "negative_transfer_risk": negative_risk,
            "recommended_method": recommended_method.value,
            "expected_performance_gain": expected_gain,
            "available_knowledge_units": len(source_knowledge),
            "confidence": min(1.0, len(self.transfer_history) / 20),
            "recommendation": self._transfer_recommendation(
                similarity, negative_risk, expected_gain
            )
        }

    def detect_negative_transfer(self,
                                transfer_result: TransferResult,
                                baseline_performance: float) -> Dict[str, Any]:
        """Detect and analyze negative transfer."""
        
        performance_diff = transfer_result.final_performance - baseline_performance
        
        is_negative = performance_diff < -self.negative_transfer_threshold
        
        analysis = {
            "is_negative_transfer": is_negative,
            "performance_difference": performance_diff,
            "severity": abs(min(0, performance_diff)),
            "method_used": transfer_result.method_used.value,
            "domain_similarity": self._get_domain_similarity(
                transfer_result.source_domain, 
                transfer_result.target_domain
            )
        }
        
        if is_negative:
            analysis["mitigation_strategies"] = self._suggest_mitigation(transfer_result)
        
        return analysis

    def get_transfer_statistics(self) -> Dict[str, Any]:
        """Get overall transfer learning statistics."""
        
        if not self.transfer_history:
            return {"total_transfers": 0}
        
        successful = [t for t in self.transfer_history if t.success]
        negative = [t for t in self.transfer_history if t.negative_transfer > self.negative_transfer_threshold]
        
        efficiencies = [t.transfer_efficiency for t in self.transfer_history]
        
        return {
            "total_transfers": len(self.transfer_history),
            "successful_transfers": len(successful),
            "negative_transfers": len(negative),
            "success_rate": len(successful) / len(self.transfer_history),
            "average_efficiency": np.mean(efficiencies),
            "best_efficiency": np.max(efficiencies),
            "total_knowledge_units": len(self.knowledge_store),
            "total_domains": len(self.domains),
            "most_transferable_domain": self._find_most_transferable_domain(),
        }

    # ──────────────────────────── Private Methods ────────────────────────────

    def _calculate_domain_similarity(self, domain_a: str, domain_b: str) -> float:
        """Calculate similarity between two domains."""
        
        if domain_a not in self.domains or domain_b not in self.domains:
            return 0.0
        
        a = self.domains[domain_a]
        b = self.domains[domain_b]
        
        # Factor 1: Task type similarity
        task_similarity = 1.0 if a.task_type == b.task_type else 0.3
        
        # Factor 2: Feature dimension similarity
        dim_ratio = min(a.feature_dimensions, b.feature_dimensions) / \
                    max(a.feature_dimensions, b.feature_dimensions, 1)
        
        # Factor 3: Complexity similarity
        complexity_diff = abs(a.complexity - b.complexity)
        complexity_sim = 1.0 - complexity_diff
        
        # Factor 4: Distribution similarity
        dist_similarity = 1.0 if a.data_distribution == b.data_distribution else 0.5
        
        # Weighted combination
        similarity = (
            task_similarity * 0.35 +
            dim_ratio * 0.25 +
            complexity_sim * 0.2 +
            dist_similarity * 0.2
        )
        
        return similarity

    def _get_domain_similarity(self, domain_a: str, domain_b: str) -> float:
        """Get cached domain similarity."""
        key = (domain_a, domain_b)
        if key not in self.similarity_cache:
            self.similarity_cache[key] = self._calculate_domain_similarity(domain_a, domain_b)
        return self.similarity_cache[key]

    def _estimate_transferability(self, representation: np.ndarray) -> float:
        """Estimate how transferable a knowledge representation is."""
        if representation.size == 0:
            return 0.0
        
        # Higher entropy = more general knowledge = more transferable
        # Normalized representation
        normalized = (representation - representation.mean()) / (representation.std() + 1e-8)
        
        # Sparsity (sparse features are often more transferable)
        sparsity = np.mean(np.abs(normalized) < 0.1)
        
        # Variance (moderate variance is most transferable)
        variance = np.var(normalized)
        variance_score = 1.0 - abs(variance - 1.0)  # Peak at variance=1
        
        transferability = sparsity * 0.4 + max(0, variance_score) * 0.6
        
        return min(1.0, max(0.0, transferability))

    def _select_transfer_method(self, source: str, target: str) -> TransferMethod:
        """Select best transfer method based on domain characteristics."""
        
        similarity = self._get_domain_similarity(source, target)
        return self._recommend_method(similarity)

    def _recommend_method(self, similarity: float) -> TransferMethod:
        """Recommend transfer method based on similarity."""
        
        if similarity >= 0.8:
            return TransferMethod.FINE_TUNING
        elif similarity >= 0.6:
            return TransferMethod.PROGRESSIVE_TRANSFER
        elif similarity >= 0.4:
            return TransferMethod.DOMAIN_ADAPTATION
        elif similarity >= 0.2:
            return TransferMethod.KNOWLEDGE_DISTILLATION
        else:
            return TransferMethod.ZERO_SHOT_TRANSFER

    def _find_relevant_knowledge(self,
                                source_domain: str,
                                target_domain: str,
                                target_task: str) -> List[KnowledgeUnit]:
        """Find knowledge units relevant for transfer."""
        
        relevant = []
        
        for kid in self.domains.get(source_domain, DomainProfile("", "", 0, "")).available_knowledge:
            if kid in self.knowledge_store:
                knowledge = self.knowledge_store[kid]
                
                # Score relevance
                relevance = knowledge.transferability_score * 0.5
                
                # Boost if same task type
                if knowledge.metadata.get("task_type") == target_task:
                    relevance += 0.3
                
                # Boost recently created knowledge
                relevance += 0.2 * (1.0 / (knowledge.usage_count + 1))
                
                if relevance > 0.3:
                    relevant.append(knowledge)
        
        # Sort by transferability
        relevant.sort(key=lambda k: k.transferability_score, reverse=True)
        
        return relevant[:10]  # Top 10 most relevant

    def _execute_transfer(self,
                         method: TransferMethod,
                         knowledge_units: List[KnowledgeUnit],
                         source_domain: str,
                         target_domain: str,
                         target_task: str,
                         constraints: Dict[str, Any]) -> TransferResult:
        """Execute the knowledge transfer."""
        
        similarity = self._get_domain_similarity(source_domain, target_domain)
        
        # Simulate transfer based on method
        if method == TransferMethod.FINE_TUNING:
            efficiency = similarity * 0.9 + np.random.normal(0, 0.05)
            negative = max(0, (1 - similarity) * 0.1)
            steps = int(100 * (1 - similarity))
            
        elif method == TransferMethod.FEATURE_EXTRACTION:
            efficiency = similarity * 0.7 + np.random.normal(0, 0.05)
            negative = max(0, (1 - similarity) * 0.05)
            steps = int(50 * (1 - similarity))
            
        elif method == TransferMethod.KNOWLEDGE_DISTILLATION:
            efficiency = similarity * 0.6 + 0.2 + np.random.normal(0, 0.05)
            negative = max(0, (1 - similarity) * 0.15)
            steps = int(200 * (1 - similarity))
            
        elif method == TransferMethod.DOMAIN_ADAPTATION:
            efficiency = similarity * 0.5 + 0.3 + np.random.normal(0, 0.08)
            negative = max(0, (1 - similarity) * 0.2)
            steps = int(300 * (1 - similarity))
            
        elif method == TransferMethod.PROGRESSIVE_TRANSFER:
            efficiency = similarity * 0.8 + 0.1 + np.random.normal(0, 0.05)
            negative = max(0, (1 - similarity) * 0.08)
            steps = int(150 * (1 - similarity))
            
        else:  # ZERO_SHOT or MULTI_TASK
            efficiency = similarity * 0.4 + 0.1 + np.random.normal(0, 0.1)
            negative = max(0, (1 - similarity) * 0.25)
            steps = 0
        
        # Clamp values
        efficiency = max(0.0, min(1.0, efficiency))
        negative = max(0.0, min(1.0, negative))
        
        # Final performance
        base_performance = 0.5  # Random baseline
        final_performance = base_performance + efficiency * 0.4 - negative * 0.2
        final_performance = max(0.0, min(1.0, final_performance))
        
        return TransferResult(
            success=efficiency > negative,
            method_used=method,
            source_domain=source_domain,
            target_domain=target_domain,
            transfer_efficiency=efficiency,
            negative_transfer=negative,
            adaptation_steps=steps,
            final_performance=final_performance,
            metadata={
                "knowledge_units_used": len(knowledge_units),
                "similarity": similarity,
                "target_task": target_task
            }
        )

    def _update_transfer_model(self, result: TransferResult) -> None:
        """Update the transfer effectiveness model."""
        key = f"{result.source_domain}->{result.target_domain}:{result.method_used.value}"
        
        current = self.transfer_model.get(key, 0.5)
        # Exponential moving average
        self.transfer_model[key] = current * 0.8 + result.transfer_efficiency * 0.2

    def _get_historical_success(self, source: str, target: str) -> float:
        """Get historical transfer success rate."""
        relevant = [
            t for t in self.transfer_history
            if t.source_domain == source and t.target_domain == target
        ]
        
        if not relevant:
            return 0.5  # No data, neutral
        
        return np.mean([t.transfer_efficiency for t in relevant])

    def _assess_knowledge_quality(self, domain_id: str) -> float:
        """Assess quality of available knowledge in a domain."""
        
        if domain_id not in self.domains:
            return 0.0
        
        knowledge_ids = self.domains[domain_id].available_knowledge
        
        if not knowledge_ids:
            return 0.0
        
        scores = []
        for kid in knowledge_ids:
            if kid in self.knowledge_store:
                scores.append(self.knowledge_store[kid].transferability_score)
        
        return np.mean(scores) if scores else 0.0

    def _estimate_negative_transfer_risk(self, source: str, target: str) -> float:
        """Estimate risk of negative transfer."""
        
        similarity = self._get_domain_similarity(source, target)
        
        # Higher risk with lower similarity
        base_risk = 1.0 - similarity
        
        # Reduce risk if we have positive history
        historical = [
            t for t in self.transfer_history
            if t.source_domain == source and t.target_domain == target
        ]
        
        if historical:
            negative_rate = np.mean([t.negative_transfer for t in historical])
            base_risk = base_risk * 0.5 + negative_rate * 0.5
        
        return min(1.0, base_risk)

    def _estimate_performance_gain(self,
                                  similarity: float,
                                  transferability: float,
                                  negative_risk: float) -> float:
        """Estimate expected performance gain from transfer."""
        
        potential_gain = similarity * 0.5 + transferability * 0.3
        expected_loss = negative_risk * 0.3
        
        return max(0.0, potential_gain - expected_loss)

    def _transfer_recommendation(self,
                                similarity: float,
                                negative_risk: float,
                                expected_gain: float) -> str:
        """Generate transfer recommendation."""
        
        if expected_gain > 0.3 and negative_risk < 0.2:
            return "Highly recommended. Strong similarity and low negative transfer risk."
        elif expected_gain > 0.15 and negative_risk < 0.4:
            return "Recommended with caution. Monitor for negative transfer."
        elif expected_gain > 0.05:
            return "Marginal benefit. Consider domain adaptation techniques."
        else:
            return "Not recommended. High risk of negative transfer."

    def _suggest_mitigation(self, result: TransferResult) -> List[str]:
        """Suggest strategies to mitigate negative transfer."""
        
        strategies = []
        
        if result.method_used == TransferMethod.FINE_TUNING:
            strategies.append("Use smaller learning rate for transferred layers")
            strategies.append("Freeze early layers and only fine-tune later ones")
        
        strategies.append("Apply domain adaptation techniques")
        strategies.append("Use progressive unfreezing")
        strategies.append("Add domain-specific normalization layers")
        strategies.append("Reduce the number of transferred layers")
        
        return strategies

    def _evict_least_useful_knowledge(self) -> None:
        """Remove least useful knowledge to maintain store size."""
        
        # Score each knowledge unit
        scored = []
        for kid, knowledge in self.knowledge_store.items():
            score = (
                knowledge.transferability_score * 0.4 +
                knowledge.usage_count * 0.1 +
                0.5  # base score
            )
            scored.append((kid, score))
        
        # Sort by score (ascending)
        scored.sort(key=lambda x: x[1])
        
        # Remove bottom 10%
        remove_count = len(scored) // 10
        for kid, _ in scored[:remove_count]:
            del self.knowledge_store[kid]

    def _find_most_transferable_domain(self) -> Optional[str]:
        """Find the domain with most successful transfers."""
        
        domain_success = {}
        for result in self.transfer_history:
            if result.success:
                domain_success[result.source_domain] = \
                    domain_success.get(result.source_domain, 0) + 1
        
        if domain_success:
            return max(domain_success, key=domain_success.get)
        return None
