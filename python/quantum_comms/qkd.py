"""
Quantum Key Distribution - BB84 Protocol Simulation.

Provides information-theoretically secure key exchange between Ultron nodes.
Even if an adversary has unlimited computational power, they cannot break
a QKD-secured channel without detection.

The BB84 protocol:
  1. Alice sends qubits in random bases (rectilinear or diagonal)
  2. Bob measures in random bases
  3. They publicly compare bases (not values)
  4. Matching bases give the shared key
  5. Any eavesdropping disturbs the quantum state = detectable
"""

import numpy as np
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import secrets
import time


class Basis(Enum):
    """Measurement basis for qubits."""
    RECTILINEAR = "rectilinear"  # |0⟩, |1⟩
    DIAGONAL = "diagonal"        # |+⟩, |−⟩


class QubitState(Enum):
    """Possible qubit states in BB84."""
    ZERO = 0       # |0⟩ in rectilinear basis
    ONE = 1        # |1⟩ in rectilinear basis
    PLUS = 2       # |+⟩ in diagonal basis
    MINUS = 3      # |−⟩ in diagonal basis


@dataclass
class Qubit:
    """A single qubit with basis and value."""
    basis: Basis
    value: int  # 0 or 1
    state: QubitState
    measured: bool = False
    measurement_basis: Optional[Basis] = None
    measurement_result: Optional[int] = None


@dataclass
class QKDSession:
    """A quantum key distribution session between two nodes."""
    session_id: str
    alice_node: str
    bob_node: str
    key_length: int
    raw_key_alice: List[int] = field(default_factory=list)
    raw_key_bob: List[int] = field(default_factory=list)
    sifted_key: List[int] = field(default_factory=list)
    final_key: bytes = b""
    error_rate: float = 0.0
    eavesdropping_detected: bool = False
    started_at: float = 0.0
    completed_at: float = 0.0
    status: str = "pending"


class BB84Protocol:
    """
    Implementation of the BB84 quantum key distribution protocol.
    
    This simulates the quantum channel. In production with real quantum hardware,
    this would interface with photon sources and single-photon detectors.
    """

    def __init__(self, error_threshold: float = 0.11) -> None:
        """
        Args:
            error_threshold: Maximum QBER before declaring eavesdropping.
                            BB84 theory shows >11% error = guaranteed eavesdropper.
        """
        self.error_threshold: float = error_threshold
        self.sessions: Dict[str, QKDSession] = {}

    def generate_key(self, 
                     alice_node: str, 
                     bob_node: str, 
                     key_length: int = 256, 
                     eavesdropper_present: bool = False) -> QKDSession:
        """
        Execute full BB84 protocol to generate a shared secret key.
        
        Args:
            alice_node: Sender node ID
            bob_node: Receiver node ID
            key_length: Desired key length in bits
            eavesdropper_present: Simulate an eavesdropper (for testing)
        
        Returns:
            QKDSession: The quantum key distribution session.
        """