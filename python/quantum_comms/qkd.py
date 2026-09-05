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
        if error_threshold < 0 or error_threshold > 1:
            raise ValueError("Error threshold must be between 0 and 1")
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
            eavesdropper_present: Simulate an eavesdropper

        Returns:
            QKDSession: The quantum key distribution session
        """
        if not alice_node or not bob_node:
            raise ValueError("Node IDs cannot be empty")
        if key_length <= 0:
            raise ValueError("Key length must be a positive integer")
        
        session_id = secrets.token_hex(16)
        session = QKDSession(session_id, alice_node, bob_node, key_length)
        self.sessions[session_id] = session
        session.started_at = time.time()

        try:
            # Step 1: Alice generates random qubits
            num_qubits = key_length * 4  # Send 4x more to account for basis mismatch
            alice_bits = [secrets.randbelow(2) for _ in range(num_qubits)]
            alice_bases = [secrets.choice(list(Basis)) for _ in range(num_qubits)]

            # Step 2: Bob chooses random measurement bases
            bob_bases = [secrets.choice(list(Basis)) for _ in range(num_qubits)]

            # Step 3: Simulate eavesdropper (if present)
            if eavesdropper_present:
                # Eve measures in random bases, disturbing ~25% of qubits
                eve_bases = [secrets.choice(list(Basis)) for _ in range(num_qubits)]
                # Eve's measurement collapses the state; some bits get flipped
                transmitted_bits = []
                for i in range(num_qubits):
                    if eve_bases[i] == alice_bases[i]:
                        transmitted_bits.append(alice_bits[i])
                    else:
                        transmitted_bits.append(secrets.randbelow(2))
            else:
                transmitted_bits = alice_bits[:]

            # Step 4: Bob measures (same basis = correct, different = random)
            bob_bits = []
            for i in range(num_qubits):
                if bob_bases[i] == alice_bases[i]:
                    bob_bits.append(transmitted_bits[i])
                else:
                    bob_bits.append(secrets.randbelow(2))

            # Step 5: Sift key — keep only matching bases
            sifted_alice = []
            sifted_bob = []
            for i in range(num_qubits):
                if alice_bases[i] == bob_bases[i]:
                    sifted_alice.append(alice_bits[i])
                    sifted_bob.append(bob_bits[i])

            session.raw_key_alice = sifted_alice
            session.raw_key_bob = sifted_bob

            # Step 6: Estimate QBER (quantum bit error rate)
            sample_size = min(len(sifted_alice) // 4, 50)
            if sample_size > 0:
                errors = sum(
                    sifted_alice[i] != sifted_bob[i]
                    for i in range(sample_size)
                )
                session.error_rate = errors / sample_size
            else:
                session.error_rate = 0.0

            session.eavesdropping_detected = session.error_rate > self.error_threshold

            # Step 7: Use remaining bits as the key (after discarding sample)
            key_bits = sifted_alice[sample_size:][:key_length]
            session.sifted_key = key_bits

            # Step 8: Privacy amplification — hash to final key
            raw_bytes = bytes(
                sum(bit << (7 - j) for j, bit in enumerate(key_bits[i:i+8]))
                for i in range(0, len(key_bits) - len(key_bits) % 8, 8)
            )
            session.final_key = hashlib.sha256(raw_bytes).digest()
        except Exception as e:
            session.status = "failed"
            session.completed_at = time.time()
            raise e
        finally:
            if session.status != "failed":
                session.status = "completed"
                session.completed_at = time.time()

        return session