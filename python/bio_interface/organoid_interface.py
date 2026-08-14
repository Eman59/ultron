"""
Organoid Interface - Communication protocol with biological neural tissue.

This defines the data format and feedback loop for interfacing with
brain organoids (clusters of human neurons grown in vitro on MEA chips).

In production, this interfaces with:
  - Multi-Electrode Arrays (MEA) for reading/stimulating
  - Microfluidics controllers for nutrient/chemical delivery
  - Optical imaging systems for calcium signal monitoring
  - Temperature and pH sensors for organoid health
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import time


class OrganoidState(Enum):
    """Health state of the biological substrate."""
    HEALTHY = "healthy"
    STRESSED = "stressed"
    DORMANT = "dormant"
    DYING = "dying"
    DISCONNECTED = "disconnected"


class SignalType(Enum):
    """Types of biological signals."""
    SPIKE_TRAIN = "spike_train"       # Action potential sequences
    LOCAL_FIELD = "local_field"        # Population-level oscillations
    CALCIUM_WAVE = "calcium_wave"      # Slow intracellular signaling
    BURST = "burst"                    # Synchronized bursting activity
    INHIBITORY = "inhibitory"          # Suppressive signals


@dataclass
class OrganoidSignal:
    """A signal read from the biological substrate."""
    signal_id: str
    signal_type: SignalType
    channel: int                 # Which electrode/region
    timestamp: float
    
    # Raw electrical data
    voltage_trace: np.ndarray = field(default_factory=lambda: np.array([]))
    sampling_rate_hz: float = 30000.0  # Standard MEA rate
    
    # Extracted features
    spike_times: List[float] = field(default_factory=list)
    firing_rate_hz: float = 0.0
    burst_detected: bool = False
    oscillation_frequency: float = 0.0  # Dominant frequency in LFP
    
    # Interpreted signal
    strength: float = 0.0       # 0-1 normalized signal strength
    confidence: float = 0.0     # How reliable is this reading
    
    # Biological context
    neurotransmitter_levels: Dict[str, float] = field(default_factory=dict)


@dataclass
class StimulationCommand:
    """Command to stimulate the organoid (feedback from digital to biological)."""
    channel: int
    waveform: np.ndarray        # Voltage waveform to apply
    duration_ms: float
    amplitude_uv: float         # Microvolts
    frequency_hz: float
    pattern: str = "pulse"      # pulse, burst, ramp, custom


class OrganoidInterface:
    """
    Interface to biological neural organoids.
    
    This is the bridge between silicon and carbon-based computation.
    The organoid acts as an "intuition co-processor" — it receives
    high-level context and returns gut-level responses that the
    digital system cannot derive algorithmically.
    """

    def __init__(self, organoid_id: str, n_channels: int = 64):
        self.organoid_id = organoid_id
        self.n_channels = n_channels
        self.state = OrganoidState.DISCONNECTED
        
        # Signal buffer
        self.signal_buffer: List[OrganoidSignal] = []
        self.buffer_max = 10000
        
        # Health monitoring
        self.health_metrics = {
            "temperature_c": 37.0,
            "ph": 7.4,
            "viability": 1.0,
            "activity_level": 0.0,
            "last_burst_time": 0.0,
        }
        
        # Stimulation history
        self.stimulation_history: List[StimulationCommand] = []
        
        # Baseline activity (for anomaly detection)
        self.baseline_rates: np.ndarray = np.zeros(n_channels)
        self.baseline_established: bool = False
        
        # Connection status
        self.connected: bool = False
        self.last_signal_time: float = 0.0

    def connect(self) -> bool:
        """
        Connect to the organoid hardware.
        In simulation: always succeeds.
        In production: initializes MEA driver and health monitoring.
        """
        self.connected = True
        self.state = OrganoidState.HEALTHY
        
        # Simulate establishing baseline
        self._establish_baseline()
        
        return True

    def disconnect(self):
        """Safely disconnect from the organoid."""
        self.connected = False
        self.state = OrganoidState.DISCONNECTED

    def read_signals(self, duration_ms: float = 100.0) -> List[OrganoidSignal]:
        """
        Read signals from the organoid for a given duration.
        
        Returns processed signals from all active channels.
        """
        if not self.connected:
            return []
        
        signals = []
        current_time = time.time()
        
        for channel in range(self.n_channels):
            # Simulate biological neural activity
            signal = self._simulate_neural_activity(channel, duration_ms)
            
            if signal.strength > 0.1:  # Only report significant signals
                signals.append(signal)
        
        # Update buffer
        self.signal_buffer.extend(signals)
        if len(self.signal_buffer) > self.buffer_max:
            self.signal_buffer = self.signal_buffer[-self.buffer_max // 2:]
        
        self.last_signal_time = current_time
        return signals

    def stimulate(self, command: StimulationCommand) -> bool:
        """
        Send a stimulation signal to the organoid.
        
        This is how the digital system feeds back to the biological substrate,
        allowing bidirectional communication.
        """
        if not self.connected or self.state == OrganoidState.DYING:
            return False
        
        # Safety check: don't over-stimulate
        recent_stims = [s for s in self.stimulation_history 
                       if time.time() - s.duration_ms/1000 < 1.0]
        if len(recent_stims) > 10:
            return False  # Rate-limited for organoid safety
        
        self.stimulation_history.append(command)
        
        # Trim history
        if len(self.stimulation_history) > 1000:
            self.stimulation_history = self.stimulation_history[-500:]
        
        return True

    def get_intuition_signal(self, context_vector: np.ndarray) -> Dict[str, Any]:
        """
        The key function: get a "gut feeling" from the organoid.
        
        Feeds context to the organoid (via stimulation pattern) and
        reads back the emergent response. This captures patterns
        that pure logic cannot detect.
        
        Args:
            context_vector: High-level state representation fed to organoid
            
        Returns:
            Intuition signal with approach/avoid tendency and confidence
        """
        if not self.connected:
            return {"available": False}
        
        # 1. Encode context as stimulation pattern
        stim_pattern = self._encode_context_to_stimulation(context_vector)
        
        # 2. Stimulate the organoid
        for cmd in stim_pattern:
            self.stimulate(cmd)
        
        # 3. Wait for response (biological processing takes ~50-200ms)
        # In simulation: immediate
        
        # 4. Read response
        response_signals = self.read_signals(duration_ms=200.0)
        
        # 5. Decode response into intuition
        intuition = self._decode_biological_response(response_signals)
        
        return intuition

    def get_health_status(self) -> Dict[str, Any]:
        """Get organoid health metrics."""
        return {
            "state": self.state.value,
            "connected": self.connected,
            "health_metrics": self.health_metrics,
            "channels_active": sum(1 for r in self.baseline_rates if r > 1.0),
            "total_channels": self.n_channels,
            "signals_buffered": len(self.signal_buffer),
            "last_signal_age": time.time() - self.last_signal_time if self.last_signal_time > 0 else -1,
        }

    # ─────────────────────── Private Methods ───────────────────────

    def _establish_baseline(self):
        """Record baseline activity for anomaly detection."""
        # Simulate baseline recording
        self.baseline_rates = np.random.exponential(5.0, self.n_channels)  # ~5 Hz average
        self.baseline_established = True

    def _simulate_neural_activity(self, channel: int, duration_ms: float) -> OrganoidSignal:
        """Simulate biological neural activity on a channel."""
        
        # Base firing rate with biological variability
        base_rate = self.baseline_rates[channel] if self.baseline_established else 5.0
        rate = base_rate * np.random.lognormal(0, 0.3)  # Log-normal variability
        
        # Generate spike times (Poisson process)
        n_spikes = np.random.poisson(rate * duration_ms / 1000.0)
        spike_times = sorted(np.random.uniform(0, duration_ms, n_spikes).tolist())
        
        # Detect bursts (>3 spikes within 50ms)
        burst = False
        for i in range(len(spike_times) - 3):
            if spike_times[i + 3] - spike_times[i] < 50.0:
                burst = True
                break
        
        # Generate simplified voltage trace
        n_samples = int(duration_ms * 30.0)  # 30kHz sampling
        voltage = np.random.normal(0, 10, n_samples)  # Background noise (µV)
        
        # Add spikes to trace
        for t in spike_times:
            idx = int(t * 30.0)
            if idx < n_samples - 30:
                # Simplified action potential waveform
                spike_waveform = np.array([0, 50, 100, -30, -10, 0]) * np.random.uniform(0.8, 1.2)
                voltage[idx:idx+len(spike_waveform)] += spike_waveform
        
        # Oscillation (theta rhythm simulation: 4-8 Hz)
        t = np.linspace(0, duration_ms / 1000.0, n_samples)
        osc_freq = np.random.uniform(4, 8)
        voltage += 20 * np.sin(2 * np.pi * osc_freq * t)
        
        return OrganoidSignal(
            signal_id=f"{self.organoid_id}_ch{channel}_{int(time.time()*1000)}",
            signal_type=SignalType.BURST if burst else SignalType.SPIKE_TRAIN,
            channel=channel,
            timestamp=time.time(),
            voltage_trace=voltage,
            spike_times=spike_times,
            firing_rate_hz=rate,
            burst_detected=burst,
            oscillation_frequency=osc_freq,
            strength=min(1.0, rate / 20.0),  # Normalize to 0-1
            confidence=0.7 if self.baseline_established else 0.3,
            neurotransmitter_levels={
                "glutamate": np.random.uniform(0.3, 0.8),
                "gaba": np.random.uniform(0.2, 0.6),
                "dopamine": np.random.uniform(0.1, 0.5),
            }
        )

    def _encode_context_to_stimulation(self, context: np.ndarray) -> List[StimulationCommand]:
        """Convert digital context vector to stimulation commands."""
        commands = []
        
        # Map context dimensions to electrode channels
        n_dims = min(len(context), self.n_channels)
        
        for i in range(n_dims):
            if abs(context[i]) > 0.1:  # Only stimulate for significant values
                commands.append(StimulationCommand(
                    channel=i,
                    waveform=np.array([0, 1, 0, -0.3, 0]),  # Biphasic pulse
                    duration_ms=10.0,
                    amplitude_uv=abs(context[i]) * 100.0,  # Scale to µV
                    frequency_hz=max(1.0, context[i] * 50.0),
                    pattern="burst" if context[i] > 0.5 else "pulse",
                ))
        
        return commands

    def _decode_biological_response(self, signals: List[OrganoidSignal]) -> Dict[str, Any]:
        """
        Decode the organoid's response into an intuition signal.
        
        The key insight: we don't fully understand WHY the organoid
        responds a certain way. That's the point. It captures
        patterns that our digital algorithms miss.
        """
        if not signals:
            return {
                "available": True,
                "approach_tendency": 0.0,
                "confidence": 0.0,
                "arousal": 0.0,
                "novelty_detection": 0.0,
            }
        
        # Aggregate signal features
        avg_rate = np.mean([s.firing_rate_hz for s in signals])
        burst_ratio = sum(1 for s in signals if s.burst_detected) / max(1, len(signals))
        avg_strength = np.mean([s.strength for s in signals])
        
        # Decode as approach/avoid
        # High burst activity = "excited" = approach
        # Low activity = "inhibited" = avoid
        # This is a simplified model of the biological decision signal
        approach_tendency = (burst_ratio * 0.5 + avg_strength * 0.3 + 
                           (avg_rate / 20.0) * 0.2 - 0.3)
        approach_tendency = np.clip(approach_tendency, -1.0, 1.0)
        
        # Arousal from overall activity level
        arousal = min(1.0, avg_rate / 15.0)
        
        # Novelty detection: how different is this from baseline?
        deviation = abs(avg_rate - np.mean(self.baseline_rates)) / (np.std(self.baseline_rates) + 0.01)
        novelty = min(1.0, deviation / 3.0)
        
        return {
            "available": True,
            "approach_tendency": float(approach_tendency),  # -1 (avoid) to 1 (approach)
            "confidence": float(avg_strength),
            "arousal": float(arousal),
            "novelty_detection": float(novelty),
            "signal_count": len(signals),
            "burst_ratio": float(burst_ratio),
            "dominant_frequency": float(np.mean([s.oscillation_frequency for s in signals])),
        }
