"""
Ultron Quantum Communication Layer

Simulates quantum key distribution (QKD) and entanglement-based
secure communication between distributed nodes.

NOTE: This is a SIMULATION of quantum protocols, not actual quantum hardware.
Real quantum communication requires physical qubits and optical channels.
What this provides:
  - Information-theoretically secure key exchange (BB84 protocol simulation)
  - Entanglement-based node pairing for tamper-evident channels
  - Quantum random number generation for cryptographic operations
  - Near-zero latency abstraction for critical decision synchronization
"""

__version__ = "0.1.0"

from .qkd import QuantumKeyDistribution, BB84Protocol
from .entanglement import EntanglementPair, QuantumChannel
from .qrng import QuantumRandomGenerator

def _validate_input(input_data):
    if input_data is None or not isinstance(input_data, (str, list, dict)) or not input_data:
        raise ValueError("Input cannot be empty, None, or an unsupported type")

# ── Wiring note ─────────────────────────────────────────────────────────────
# This module is currently standalone (simulations only).
# To use it: import and instantiate QKDProtocol or EntanglementSimulator
# in server.py's lifespan or in the security daemon.
# Example: from python.quantum_comms.qkd import QKDProtocol
