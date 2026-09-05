"""
Quantum Random Number Generator - True randomness for cryptographic operations.

Classical computers can only produce pseudo-random numbers (deterministic algorithms).
Quantum randomness is fundamentally unpredictable — no algorithm can predict the output.

This module simulates quantum randomness using the measurement uncertainty principle.
In production, this would interface with a hardware QRNG chip.
"""

import secrets
import hashlib
import time
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class RandomnessPool:
    """A pool of quantum-generated random bytes."""
    random_bytes_pool: bytes
    generation_timestamp: float
    randomness_source: str  # "simulated" or "hardware"
    entropy_bits: int


class QuantumRandomGenerator:
    """
    Quantum random number generator.
    
    Provides true randomness for:
    - Encryption key generation
    - Nonce generation (prevents replay attacks)
    - Decision noise (exploration in the autonomy loop)
    - Decoy placement randomization
    """

    def __init__(self, initial_entropy: Optional[bytes] = None):
        self.randomness_source = "simulated"  # Would be "hardware" with real QRNG
        self.total_bits_generated = 0
        self.generation_count = 0
        
        # Mix in any additional entropy
        self.additional_entropy = initial_entropy or b""

    def generate_random_bytes(self, num_bytes: int) -> bytes:
        """Generate n random bytes with quantum-grade randomness."""
        # In simulation: use secrets module (OS-level CSPRNG)
        # In production: read from hardware QRNG
        result = secrets.token_bytes(num_bytes)
        
        # Mix with timing entropy for additional unpredictability
        timing_entropy = str(time.time_ns()).encode()
        mixed_entropy = hashlib.sha512(result + timing_entropy + self.additional_entropy).digest()
        
        self.total_bits_generated += num_bytes * 8
        self.generation_count += 1
        
        return mixed_entropy[:num_bytes]

    def generate_random_integer(self, min_value: int = 0, max_value: int = 2**32 - 1) -> int:
        """Generate a random integer in [min_val, max_val]."""
        range_size = max_value - min_value + 1
        # Determine bytes needed
        num_bytes = (range_size.bit_length() + 7) // 8 + 1  # Extra byte to avoid modulo bias
        
        raw_value = int.from_bytes(self.generate_random_bytes(num_bytes), 'big')
        return min_value + (raw_value % range_size)

    def generate_random_float(self) -> float:
        """Generate a random float in [0.0, 1.0) with 53 bits of precision."""
        # 53 bits = double precision mantissa
        raw_value = int.from_bytes(self.generate_random_bytes(7), 'big') & ((1 << 53) - 1)
        return raw_value / (1 << 53)

    def generate_random_bits(self, num_bits: int) -> List[int]:
        """Generate n random bits."""
        num_bytes = (num_bits + 7) // 8
        raw_bytes = self.generate_random_bytes(num_bytes)
        bits = []
        for byte in raw_bytes:
            for i in range(7, -1, -1):
                bits.append((byte >> i) & 1)
                if len(bits) >= num_bits:
                    return bits
        return bits

    def random_gauss(self, mean: float = 0.0, std: float = 1.0) -> float:
        """Generate a Gaussian random number using Box-Muller transform."""
        u1 = self.generate_random_float()
        u2 = self.generate_random_float()
        import math
        z = math.sqrt(-2 * math.log(max(u1, 1e-10))) * math.cos(2 * math.pi * u2)
        return mean + std * z