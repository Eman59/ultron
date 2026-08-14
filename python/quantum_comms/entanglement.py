"""
Quantum Entanglement Simulation - Paired node communication.

Simulates entangled qubit pairs for:
  - Tamper-evident communication channels
  - Distributed consensus (quantum voting)
  - Instantaneous state correlation between nodes

Physics note: Real entanglement cannot transmit information FTL.
What it CAN do: create correlated randomness that detects tampering.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
import secrets
import time
import hashlib


@dataclass
class EntanglementPair:
    """
    A simulated entangled qubit pair shared between two nodes.
    
    Properties:
    - Measuring one qubit instantly determines the other
    - Any interference with either qubit breaks the correlation
    - The pair can only be used ONCE (no-cloning theorem)
    """
    pair_id: str
    node_a: str
    node_b: str
    
    # Bell state type: |Φ+⟩, |Φ-⟩, |Ψ+⟩, |Ψ-⟩
    bell_state: str = "phi_plus"
    
    # Whether each qubit has been measured
    measured_a: bool = False
    measured_b: bool = False
    
    # Measurement results (None until measured)
    result_a: Optional[int] = None
    result_b: Optional[int] = None
    
    # Correlation verification
    correlation_verified: bool = False
    tampered: bool = False
    
    # Metadata
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0  # Decoherence time
    
    def __post_init__(self):
        if self.expires_at == 0.0:
            self.expires_at = self.created_at + 60.0  # 60s coherence time

    @property
    def is_valid(self) -> bool:
        """Check if the pair is still valid (not expired, not fully used)."""
        return (
            time.time() < self.expires_at and
            not (self.measured_a and self.measured_b) and
            not self.tampered
        )

    def measure_a(self, basis: str = "z") -> int:
        """Node A measures their qubit."""
        if self.measured_a:
            raise ValueError("Qubit A already measured")
        if time.time() > self.expires_at:
            raise ValueError("Entanglement pair has decohered")
        
        # Generate measurement outcome
        self.result_a = secrets.randbelow(2)
        self.measured_a = True
        
        # If B was already measured, determine correlation
        if self.measured_b:
            self._verify_correlation()
        
        return self.result_a

    def measure_b(self, basis: str = "z") -> int:
        """Node B measures their qubit."""
        if self.measured_b:
            raise ValueError("Qubit B already measured")
        if time.time() > self.expires_at:
            raise ValueError("Entanglement pair has decohered")
        
        if self.measured_a:
            # B's result is correlated with A's
            if self.bell_state in ("phi_plus", "phi_minus"):
                # Same outcome for Φ states
                self.result_b = self.result_a if self.bell_state == "phi_plus" else (1 - self.result_a)
            else:
                # Opposite for Ψ states
                self.result_b = (1 - self.result_a) if self.bell_state == "psi_plus" else self.result_a
        else:
            self.result_b = secrets.randbelow(2)
        
        self.measured_b = True
        
        if self.measured_a:
            self._verify_correlation()
        
        return self.result_b

    def _verify_correlation(self):
        """Verify that the correlation holds (detects tampering)."""
        if self.bell_state == "phi_plus":
            self.correlation_verified = (self.result_a == self.result_b)
        elif self.bell_state == "phi_minus":
            self.correlation_verified = (self.result_a != self.result_b)
        elif self.bell_state == "psi_plus":
            self.correlation_verified = (self.result_a != self.result_b)
        else:  # psi_minus
            self.correlation_verified = (self.result_a == self.result_b)
        
        self.tampered = not self.correlation_verified


class QuantumChannel:
    """
    A quantum communication channel between two nodes.
    
    Uses entanglement pairs for:
    1. Tamper detection (any interception breaks correlation)
    2. Quantum-secured key generation
    3. Distributed consensus primitive
    """

    def __init__(self, local_node: str, remote_node: str, pool_size: int = 100):
        self.local_node = local_node
        self.remote_node = remote_node
        self.pool_size = pool_size
        
        # Pre-generated entanglement pool
        self.pair_pool: List[EntanglementPair] = []
        self.used_pairs: List[EntanglementPair] = []
        
        # Channel statistics
        self.total_pairs_created = 0
        self.total_pairs_used = 0
        self.tampering_detected = 0
        
        # Refill the pool
        self._refill_pool()

    def _refill_pool(self):
        """Generate fresh entanglement pairs."""
        while len(self.pair_pool) < self.pool_size:
            pair = EntanglementPair(
                pair_id=secrets.token_hex(8),
                node_a=self.local_node,
                node_b=self.remote_node,
                bell_state=secrets.choice(["phi_plus", "phi_minus", "psi_plus", "psi_minus"]),
            )
            self.pair_pool.append(pair)
            self.total_pairs_created += 1

    def consume_pair(self) -> Optional[EntanglementPair]:
        """Get an entanglement pair from the pool."""
        # Remove expired pairs
        self.pair_pool = [p for p in self.pair_pool if p.is_valid]
        
        if not self.pair_pool:
            self._refill_pool()
        
        if self.pair_pool:
            pair = self.pair_pool.pop(0)
            self.total_pairs_used += 1
            self.used_pairs.append(pair)
            return pair
        
        return None

    def verify_channel_integrity(self, n_tests: int = 10) -> Dict[str, Any]:
        """
        Test channel integrity using entanglement correlations.
        
        Consumes n_tests pairs to check for eavesdropping.
        """
        violations = 0
        tested = 0
        
        for _ in range(n_tests):
            pair = self.consume_pair()
            if pair is None:
                break
            
            # Both sides measure
            pair.measure_a()
            pair.measure_b()
            tested += 1
            
            if pair.tampered:
                violations += 1
                self.tampering_detected += 1
        
        violation_rate = violations / max(1, tested)
        
        return {
            "tests_performed": tested,
            "violations": violations,
            "violation_rate": violation_rate,
            "channel_secure": violation_rate < 0.1,  # <10% = secure
            "pairs_remaining": len(self.pair_pool),
        }

    def generate_shared_randomness(self, n_bits: int) -> Tuple[List[int], str]:
        """
        Generate shared random bits using entanglement.
        
        Both nodes get the same random bits without any classical communication.
        This is useful for synchronized decisions in the distributed consciousness.
        """
        bits = []
        
        for _ in range(n_bits):
            pair = self.consume_pair()
            if pair is None:
                break
            
            # Local node measures
            bit = pair.measure_a()
            bits.append(bit)
        
        # Create verification hash
        verification = hashlib.sha256(bytes(bits)).hexdigest()[:16]
        
        return bits, verification

    def get_channel_stats(self) -> Dict[str, Any]:
        """Get channel statistics."""
        return {
            "local_node": self.local_node,
            "remote_node": self.remote_node,
            "pool_size": len(self.pair_pool),
            "total_created": self.total_pairs_created,
            "total_used": self.total_pairs_used,
            "tampering_events": self.tampering_detected,
            "channel_health": 1.0 - (self.tampering_detected / max(1, self.total_pairs_used)),
        }
