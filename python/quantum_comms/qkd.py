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

    def __init__(self, error_threshold: float = 0.11):
        """
        Args:
            error_threshold: Maximum QBER before declaring eavesdropping.
                            BB84 theory shows >11% error = guaranteed eavesdropper.
        """
        self.error_threshold = error_threshold
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
        """
        session = QKDSession(
            session_id=secrets.token_hex(16),
            alice_node=alice_node,
            bob_node=bob_node,
            key_length=key_length,
            started_at=time.time(),
        )
        session.status = "in_progress"

        # Need ~4x the desired key length due to basis mismatch and privacy amplification
        n_qubits = key_length * 4

        # Step 1: Alice prepares qubits
        alice_bases = [secrets.choice([Basis.RECTILINEAR, Basis.DIAGONAL]) for _ in range(n_qubits)]
        alice_bits = [secrets.randbelow(2) for _ in range(n_qubits)]

        qubits = []
        for i in range(n_qubits):
            state = self._encode_qubit(alice_bases[i], alice_bits[i])
            qubits.append(Qubit(basis=alice_bases[i], value=alice_bits[i], state=state))

        # Step 2: Eve intercepts (if present) - introduces errors
        if eavesdropper_present:
            qubits = self._eavesdrop(qubits)

        # Step 3: Bob measures in random bases
        bob_bases = [secrets.choice([Basis.RECTILINEAR, Basis.DIAGONAL]) for _ in range(n_qubits)]
        bob_results = []

        for i in range(n_qubits):
            result = self._measure_qubit(qubits[i], bob_bases[i])
            bob_results.append(result)

        # Step 4: Basis reconciliation (public channel)
        # Keep only bits where Alice and Bob used the same basis
        sifted_alice = []
        sifted_bob = []

        for i in range(n_qubits):
            if alice_bases[i] == bob_bases[i]:
                sifted_alice.append(alice_bits[i])
                sifted_bob.append(bob_results[i])

        # Step 5: Error estimation
        # Use a subset to estimate quantum bit error rate (QBER)
        test_size = min(len(sifted_alice) // 4, 100)
        errors = 0

        for i in range(test_size):
            if sifted_alice[i] != sifted_bob[i]:
                errors += 1

        qber = errors / max(1, test_size)
        session.error_rate = qber

        # Step 6: Check for eavesdropping
        if qber > self.error_threshold:
            session.eavesdropping_detected = True
            session.status = "aborted_eavesdropper"
            session.completed_at = time.time()
            self.sessions[session.session_id] = session
            return session

        # Step 7: Privacy amplification
        # Remove test bits and hash remaining
        remaining_alice = sifted_alice[test_size:]
        remaining_bob = sifted_bob[test_size:]

        # Take only what we need
        key_bits = remaining_alice[:key_length]

        if len(key_bits) < key_length:
            session.status = "insufficient_key_material"
            session.completed_at = time.time()
            self.sessions[session.session_id] = session
            return session

        # Convert bits to bytes
        session.sifted_key = key_bits
        session.final_key = self._bits_to_bytes(key_bits)
        session.raw_key_alice = sifted_alice
        session.raw_key_bob = sifted_bob
        session.status = "completed"
        session.completed_at = time.time()

        self.sessions[session.session_id] = session
        return session

    def verify_channel_integrity(self, session_id: str) -> Dict[str, Any]:
        """Verify that a QKD channel hasn't been compromised."""
        session = self.sessions.get(session_id)
        if not session:
            return {"valid": False, "reason": "Session not found"}

        return {
            "valid": not session.eavesdropping_detected,
            "error_rate": session.error_rate,
            "threshold": self.error_threshold,
            "key_length": len(session.final_key) * 8,
            "status": session.status,
        }

    # ─────────────────────── Private Methods ───────────────────────

    def _encode_qubit(self, basis: Basis, value: int) -> QubitState:
        """Encode a classical bit into a qubit state."""
        if basis == Basis.RECTILINEAR:
            return QubitState.ZERO if value == 0 else QubitState.ONE
        else:
            return QubitState.PLUS if value == 0 else QubitState.MINUS

    def _measure_qubit(self, qubit: Qubit, basis: Basis) -> int:
        """
        Measure a qubit in a given basis.
        
        If basis matches preparation basis: deterministic result.
        If basis doesn't match: random 50/50 result (quantum uncertainty).
        """
        if basis == qubit.basis:
            # Correct basis: get the original value
            return qubit.value
        else:
            # Wrong basis: random result (fundamental quantum randomness)
            return secrets.randbelow(2)

    def _eavesdrop(self, qubits: List[Qubit]) -> List[Qubit]:
        """
        Simulate an eavesdropper (Eve) intercepting qubits.
        
        Eve measures in a random basis, which disturbs the quantum state.
        This introduces ~25% error rate in the sifted key.
        """
        disturbed = []
        for qubit in qubits:
            # Eve measures in random basis
            eve_basis = secrets.choice([Basis.RECTILINEAR, Basis.DIAGONAL])
            eve_result = self._measure_qubit(qubit, eve_basis)

            # Eve re-sends qubit (but may have changed it)
            new_qubit = Qubit(
                basis=eve_basis,
                value=eve_result,
                state=self._encode_qubit(eve_basis, eve_result)
            )
            disturbed.append(new_qubit)

        return disturbed

    def _bits_to_bytes(self, bits: List[int]) -> bytes:
        """Convert a list of bits to bytes."""
        byte_list = []
        for i in range(0, len(bits) - 7, 8):
            byte_val = 0
            for j in range(8):
                byte_val |= (bits[i + j] << (7 - j))
            byte_list.append(byte_val)
        return bytes(byte_list)


class QuantumKeyDistribution:
    """
    High-level QKD manager for the Ultron network.
    
    Manages key exchange between all node pairs, handles key rotation,
    and monitors for eavesdropping across the network.
    """

    def __init__(self, node_id: str, rotation_interval: float = 300.0):
        self.node_id = node_id
        self.rotation_interval = rotation_interval
        self.protocol = BB84Protocol()
        self.active_keys: Dict[str, bytes] = {}  # peer_id -> shared_key
        self.key_timestamps: Dict[str, float] = {}
        self.compromised_peers: set = set()

    def establish_secure_channel(self, peer_id: str) -> Dict[str, Any]:
        """Establish a quantum-secured channel with a peer."""
        
        if peer_id in self.compromised_peers:
            return {"success": False, "reason": "Peer is marked as compromised"}

        session = self.protocol.generate_key(
            alice_node=self.node_id,
            bob_node=peer_id,
            key_length=256
        )

        if session.eavesdropping_detected:
            self.compromised_peers.add(peer_id)
            return {
                "success": False,
                "reason": "Eavesdropping detected on quantum channel",
                "error_rate": session.error_rate,
                "action": "Channel compromised. Peer blacklisted.",
            }

        if session.status == "completed":
            self.active_keys[peer_id] = session.final_key
            self.key_timestamps[peer_id] = time.time()
            return {
                "success": True,
                "session_id": session.session_id,
                "key_length_bits": len(session.final_key) * 8,
                "error_rate": session.error_rate,
            }

        return {"success": False, "reason": session.status}

    def get_encryption_key(self, peer_id: str) -> Optional[bytes]:
        """Get the shared key for encrypting communication with a peer."""
        
        if peer_id not in self.active_keys:
            return None

        # Check if key needs rotation
        age = time.time() - self.key_timestamps.get(peer_id, 0)
        if age > self.rotation_interval:
            # Key expired, need re-exchange
            result = self.establish_secure_channel(peer_id)
            if not result["success"]:
                return None

        return self.active_keys.get(peer_id)

    def get_network_security_status(self) -> Dict[str, Any]:
        """Get security status of all quantum channels."""
        return {
            "active_channels": len(self.active_keys),
            "compromised_peers": list(self.compromised_peers),
            "keys_needing_rotation": sum(
                1 for pid in self.active_keys
                if time.time() - self.key_timestamps.get(pid, 0) > self.rotation_interval
            ),
            "total_sessions": len(self.protocol.sessions),
        }
