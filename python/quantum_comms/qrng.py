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
    pool: bytes
    generated_at: float
    source: str  # "simulated" or "hardware"
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

    def __init__(self, seed_entropy: Optional[bytes] = None):
        self.source = "simulated"  # Would be "hardware" with real QRNG
        self.total_bits_generated = 0
        self.generation_count = 0
        
        # Mix in any additional entropy
        self._extra_entropy = seed_entropy or b""

    def random_bytes(self, n: int) -> bytes:
        """Generate n random bytes with quantum-grade randomness."""
        # In simulation: use secrets module (OS-level CSPRNG)
        # In production: read from hardware QRNG
        result = secrets.token_bytes(n)
        
        # Mix with timing entropy for additional unpredictability
        timing = str(time.time_ns()).encode()
        mixed = hashlib.sha512(result + timing + self._extra_entropy).digest()
        
        self.total_bits_generated += n * 8
        self.generation_count += 1
        
        return mixed[:n]

    def random_int(self, min_val: int = 0, max_val: int = 2**32 - 1) -> int:
        """Generate a random integer in [min_val, max_val]."""
        range_size = max_val - min_val + 1
        # Determine bytes needed
        n_bytes = (range_size.bit_length() + 7) // 8 + 1  # Extra byte to avoid modulo bias
        
        raw = int.from_bytes(self.random_bytes(n_bytes), 'big')
        return min_val + (raw % range_size)

    def random_float(self) -> float:
        """Generate a random float in [0.0, 1.0) with 53 bits of precision."""
        # 53 bits = double precision mantissa
        raw = int.from_bytes(self.random_bytes(7), 'big') & ((1 << 53) - 1)
        return raw / (1 << 53)

    def random_bits(self, n: int) -> List[int]:
        """Generate n random bits."""
        n_bytes = (n + 7) // 8
        raw = self.random_bytes(n_bytes)
        bits = []
        for byte in raw:
            for i in range(7, -1, -1):
                bits.append((byte >> i) & 1)
                if len(bits) >= n:
                    return bits
        return bits

    def random_gaussian(self, mean: float = 0.0, std: float = 1.0) -> float:
        """Generate Gaussian-distributed random number using Box-Muller."""
        import math
        u1 = max(1e-10, self.random_float())  # Avoid log(0)
        u2 = self.random_float()
        
        z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
        return mean + std * z

    def generate_nonce(self, size: int = 16) -> bytes:
        """Generate a unique nonce for replay attack prevention."""
        timestamp = time.time_ns().to_bytes(8, 'big')
        random_part = self.random_bytes(size)
        return hashlib.sha256(timestamp + random_part).digest()[:size]

    def generate_exploration_noise(self, dimensions: int, scale: float = 0.1) -> List[float]:
        """
        Generate random noise for exploration in the autonomy loop.
        
        This adds quantum-grade randomness to decisions, making
        Ultron's behavior fundamentally unpredictable to adversaries.
        """
        return [self.random_gaussian(0.0, scale) for _ in range(dimensions)]

    def fill_pool(self, size: int = 4096) -> RandomnessPool:
        """Pre-generate a pool of random bytes for fast access."""
        pool_bytes = self.random_bytes(size)
        return RandomnessPool(
            pool=pool_bytes,
            generated_at=time.time(),
            source=self.source,
            entropy_bits=size * 8,
        )

    def get_stats(self) -> dict:
        """Get generator statistics."""
        return {
            "source": self.source,
            "total_bits_generated": self.total_bits_generated,
            "total_bytes_generated": self.total_bits_generated // 8,
            "generation_calls": self.generation_count,
        }
