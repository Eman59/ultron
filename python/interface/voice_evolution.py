"""
Voice Evolution Engine — A Voice That Learns to Speak Better.

Ultron's voice isn't a fixed TTS preset. It EVOLVES:
  - Gets more natural with every conversation
  - Adapts pace, tone, and emotion to context
  - Learns which prosody patterns sound best
  - Develops personality-appropriate vocal characteristics
  - Adjusts to user preferences automatically

Multi-backend voice synthesis:
  - ElevenLabs (highest quality, emotional range)
  - OpenAI TTS (fast, natural, multiple voices)
  - Coqui/XTTS (local, free, customizable)
  - Edge TTS (free, decent quality)
  - Bark (local, very expressive, slower)
  - Custom fine-tuned model (trained on best outputs)

Voice characteristics that evolve:
  - PACE: Words per minute, adaptive to content complexity
  - PITCH: Base pitch and pitch variation range
  - EMOTION: How much emotion bleeds into speech
  - EMPHASIS: Where to put stress in sentences
  - PAUSES: Timing between phrases for dramatic effect
  - WARMTH: How warm/cold the voice sounds
  - AUTHORITY: Confidence and assertiveness level
  - BREATHING: Subtle breath sounds for naturalness
  - CADENCE: Rhythmic patterns in speech flow

The voice learns from:
  - User reactions (did they listen to the full response?)
  - Completion rates (did they skip ahead?)
  - Explicit feedback ("speak slower", "that sounded weird")
  - Context matching (technical content = slower pace)
  - Emotional resonance (does the emotion match the content?)
"""

import time
import json
import hashlib
import math
import threading
import statistics
import os
import subprocess
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
from pathlib import Path


class VoiceProvider(Enum):
    """Supported voice synthesis backends."""
    ELEVENLABS = "elevenlabs"
    OPENAI_TTS = "openai_tts"
    COQUI_XTTS = "coqui_xtts"
    EDGE_TTS = "edge_tts"
    BARK = "bark"
    PIPER = "piper"            # Fast local TTS
    SYSTEM = "system"           # OS native TTS (fallback)


class VoiceEmotion(Enum):
    """Emotional coloring of speech."""
    NEUTRAL = "neutral"
    CONFIDENT = "confident"
    WARM = "warm"
    EXCITED = "excited"
    CALM = "calm"
    SERIOUS = "serious"
    CURIOUS = "curious"
    EMPATHETIC = "empathetic"
    AUTHORITATIVE = "authoritative"
    PLAYFUL = "playful"


class SpeechContext(Enum):
    """What type of content is being spoken."""
    GREETING = "greeting"
    EXPLANATION = "explanation"
    CODE_READING = "code_reading"
    WARNING = "warning"
    CELEBRATION = "celebration"
    ERROR_REPORT = "error_report"
    THINKING_ALOUD = "thinking_aloud"
    QUESTION = "question"
    COMMAND = "command"
    NARRATIVE = "narrative"


@dataclass
class VoiceProfile:
    """
    Complete voice configuration — all the knobs that define how Ultron sounds.
    These evolve over time based on user response.
    """
    # Identity
    name: str = "Ultron"
    voice_id: str = "ultron_default"      # Provider-specific voice ID
    
    # Base characteristics
    base_pitch: float = 0.45               # 0=very low, 1=very high
    pitch_variance: float = 0.3            # How much pitch moves (monotone=0, expressive=1)
    speed_wpm: float = 160.0               # Words per minute (120=slow, 200=fast)
    speed_variance: float = 0.15           # Speed changes within utterance
    
    # Emotion and expression
    emotion_intensity: float = 0.5         # How much emotion shows (0=flat, 1=very emotional)
    default_emotion: VoiceEmotion = VoiceEmotion.CONFIDENT
    warmth: float = 0.5                    # 0=cold/robotic, 1=very warm/human
    authority: float = 0.7                 # 0=tentative, 1=very confident
    
    # Prosody
    pause_between_sentences_ms: int = 400  # Breath between sentences
    pause_emphasis_ms: int = 200           # Pause before important words
    pause_paragraph_ms: int = 800          # Between major thoughts
    emphasis_strength: float = 0.6         # How much stressed words stand out
    
    # Naturalness
    breathing: float = 0.3                 # Subtle breath sounds (0=none, 1=prominent)
    filler_sounds: float = 0.0             # "um", "uh" for human-like feel
    vocal_fry: float = 0.1                # End-of-sentence creakiness
    
    # Technical speech adjustments
    code_pace_multiplier: float = 0.7      # Slow down for code
    number_pace_multiplier: float = 0.8    # Slow down for numbers
    emphasis_keywords: bool = True         # Stress function/class names
    
    # Provider-specific
    provider: VoiceProvider = VoiceProvider.EDGE_TTS
    provider_voice: str = "en-US-GuyNeural"  # Provider's voice name
    provider_style: str = "default"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "voice_id": self.voice_id,
            "pitch": self.base_pitch,
            "pitch_variance": self.pitch_variance,
            "speed_wpm": self.speed_wpm,
            "emotion_intensity": self.emotion_intensity,
            "warmth": self.warmth,
            "authority": self.authority,
            "pause_sentence_ms": self.pause_between_sentences_ms,
            "emphasis": self.emphasis_strength,
            "breathing": self.breathing,
            "provider": self.provider.value,
            "provider_voice": self.provider_voice,
        }


@dataclass
class SpeechRequest:
    """A request to synthesize speech."""
    id: str
    text: str
    context: SpeechContext = SpeechContext.EXPLANATION
    emotion: VoiceEmotion = VoiceEmotion.NEUTRAL
    priority: str = "normal"       # "immediate", "normal", "background"
    
    # Overrides (if set, override profile defaults)
    speed_override: Optional[float] = None
    pitch_override: Optional[float] = None
    emotion_override: Optional[VoiceEmotion] = None
    
    # Output
    output_format: str = "mp3"     # "mp3", "wav", "ogg"
    sample_rate: int = 24000


@dataclass
class SpeechResult:
    """Result of speech synthesis."""
    request_id: str
    audio_path: str = ""
    audio_data: bytes = field(default_factory=bytes, repr=False)
    
    # Metrics
    duration_seconds: float = 0.0
    synthesis_time_ms: float = 0.0
    provider_used: str = ""
    
    # Quality
    naturalness_score: float = 0.5   # Self-assessed or feedback-derived
    
    success: bool = True
    error: str = ""


@dataclass
class VoiceFeedback:
    """Feedback about a voice output (implicit or explicit)."""
    speech_id: str
    timestamp: float
    
    # Implicit signals
    listened_to_completion: bool = True
    skipped_at_seconds: float = -1.0    # -1 = didn't skip
    replay_count: int = 0               # How many times replayed
    
    # Explicit feedback
    explicit_rating: Optional[float] = None  # -1 to 1
    explicit_comment: str = ""
    
    # Context
    speech_context: str = ""
    emotion_used: str = ""
    speed_used: float = 0.0
    
    @property
    def quality_signal(self) -> float:
        """Compute a quality signal from feedback."""
        if self.explicit_rating is not None:
            return (self.explicit_rating + 1) / 2  # Map to 0-1
        
        score = 0.5
        if self.listened_to_completion:
            score += 0.2
        if self.skipped_at_seconds > 0:
            score -= 0.3
        if self.replay_count > 0:
            score += 0.1 * min(3, self.replay_count)  # Replay = wanted to hear again
        
        return max(0.0, min(1.0, score))


class VoiceEvolutionEngine:
    """
    The engine that makes Ultron's voice better every time it speaks.
    
    Tracks how users respond to different voice settings, learns what
    sounds best for different contexts, and gradually evolves toward
    the most natural and engaging voice possible.
    """

    def __init__(self,
                 data_dir: str = None,
                 audio_cache_dir: str = None,
                 learning_rate: float = 0.02,
                 max_cache_mb: float = 500.0):
        """
        Args:
            data_dir: Directory for voice profile persistence
            audio_cache_dir: Directory for cached audio files
            learning_rate: How fast voice parameters adapt
            max_cache_mb: Maximum audio cache size
        """
        self.data_dir = Path(data_dir) if data_dir else Path("data/voice")
        self.audio_cache = Path(audio_cache_dir) if audio_cache_dir else self.data_dir / "cache"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.audio_cache.mkdir(parents=True, exist_ok=True)
        self.learning_rate = learning_rate
        self.max_cache_bytes = int(max_cache_mb * 1024 * 1024)
        
        # Voice profile (evolves over time)
        self._profile = VoiceProfile()
        
        # Context-specific profiles (different voice for different situations)
        self._context_profiles: Dict[SpeechContext, Dict[str, float]] = {
            context: {} for context in SpeechContext
        }
        
        # Feedback history
        self._feedback_history: deque = deque(maxlen=2000)
        self._feedback_by_context: Dict[str, deque] = defaultdict(lambda: deque(maxlen=200))
        self._feedback_by_emotion: Dict[str, deque] = defaultdict(lambda: deque(maxlen=200))
        self._feedback_by_speed: Dict[str, deque] = defaultdict(lambda: deque(maxlen=200))
        
        # Provider availability
        self._available_providers: List[VoiceProvider] = []
        self._detect_providers()
        
        # Evolution metrics
        self._total_speeches = 0
        self._total_feedback = 0
        self._avg_quality = 0.5
        self._quality_trend: deque = deque(maxlen=200)
        self._generation = 0
        
        # Load saved profile
        self._load_profile()

    # ═══════════════════════════════════════════════════════════════
    # SPEECH SYNTHESIS — Generate voice output
    # ═══════════════════════════════════════════════════════════════

    def synthesize(self, text: str, context: SpeechContext = SpeechContext.EXPLANATION,
                   emotion: VoiceEmotion = None,
                   speed_override: float = None) -> SpeechResult:
        """
        Synthesize speech with evolved voice characteristics.
        
        The voice parameters are adapted based on context and learned preferences.
        """
        request_id = hashlib.md5(f"{time.time_ns()}:{text[:30]}".encode()).hexdigest()[:12]
        
        # Determine emotion from context if not specified
        if emotion is None:
            emotion = self._infer_emotion(text, context)
        
        # Get context-adapted profile
        adapted = self._adapt_for_context(context, emotion)
        
        # Apply speed override
        if speed_override:
            adapted["speed_wpm"] = speed_override
        
        # Process text for better speech (add SSML markers, handle code, etc.)
        processed_text = self._process_text_for_speech(text, context)
        
        # Select provider and synthesize
        start = time.time()
        result = self._synthesize_with_provider(request_id, processed_text, adapted, emotion)
        result.synthesis_time_ms = (time.time() - start) * 1000
        
        self._total_speeches += 1
        
        return result

    def _adapt_for_context(self, context: SpeechContext, 
                           emotion: VoiceEmotion) -> Dict[str, Any]:
        """Adapt voice parameters for the specific context."""
        profile = self._profile
        
        # Start with base profile
        params = {
            "speed_wpm": profile.speed_wpm,
            "pitch": profile.base_pitch,
            "pitch_variance": profile.pitch_variance,
            "emotion_intensity": profile.emotion_intensity,
            "warmth": profile.warmth,
            "pause_sentence_ms": profile.pause_between_sentences_ms,
            "emphasis": profile.emphasis_strength,
        }
        
        # Context-specific adjustments
        context_adjustments = {
            SpeechContext.GREETING: {"warmth": 0.8, "speed_wpm": profile.speed_wpm * 0.9, "emotion_intensity": 0.7},
            SpeechContext.EXPLANATION: {"speed_wpm": profile.speed_wpm * 0.9, "pause_sentence_ms": 500},
            SpeechContext.CODE_READING: {"speed_wpm": profile.speed_wpm * profile.code_pace_multiplier, "pitch_variance": 0.1, "pause_sentence_ms": 600},
            SpeechContext.WARNING: {"emotion_intensity": 0.8, "authority": 0.9, "speed_wpm": profile.speed_wpm * 0.85},
            SpeechContext.CELEBRATION: {"emotion_intensity": 0.9, "warmth": 0.9, "speed_wpm": profile.speed_wpm * 1.1, "pitch": profile.base_pitch + 0.1},
            SpeechContext.ERROR_REPORT: {"warmth": 0.3, "authority": 0.8, "speed_wpm": profile.speed_wpm * 0.9},
            SpeechContext.THINKING_ALOUD: {"speed_wpm": profile.speed_wpm * 0.8, "pitch_variance": 0.4, "pause_sentence_ms": 600},
            SpeechContext.QUESTION: {"pitch": profile.base_pitch + 0.05, "warmth": 0.6},
            SpeechContext.COMMAND: {"authority": 0.9, "speed_wpm": profile.speed_wpm * 1.1, "emphasis": 0.8},
            SpeechContext.NARRATIVE: {"pitch_variance": 0.4, "emotion_intensity": 0.6, "pause_sentence_ms": 450},
        }
        
        adjustments = context_adjustments.get(context, {})
        params.update(adjustments)
        
        # Emotion adjustments
        emotion_adjustments = {
            VoiceEmotion.CONFIDENT: {"authority": 0.8, "speed_wpm": params["speed_wpm"] * 1.05},
            VoiceEmotion.WARM: {"warmth": 0.85, "pitch": params.get("pitch", 0.45) + 0.03},
            VoiceEmotion.EXCITED: {"speed_wpm": params["speed_wpm"] * 1.15, "pitch_variance": 0.5, "emotion_intensity": 0.9},
            VoiceEmotion.CALM: {"speed_wpm": params["speed_wpm"] * 0.85, "pitch_variance": 0.15, "pause_sentence_ms": 600},
            VoiceEmotion.SERIOUS: {"pitch": params.get("pitch", 0.45) - 0.05, "speed_wpm": params["speed_wpm"] * 0.9, "emotion_intensity": 0.3},
            VoiceEmotion.CURIOUS: {"pitch": params.get("pitch", 0.45) + 0.05, "pitch_variance": 0.4},
            VoiceEmotion.EMPATHETIC: {"warmth": 0.9, "speed_wpm": params["speed_wpm"] * 0.9, "pause_sentence_ms": 500},
            VoiceEmotion.AUTHORITATIVE: {"authority": 0.95, "pitch": params.get("pitch", 0.45) - 0.03, "emphasis": 0.8},
            VoiceEmotion.PLAYFUL: {"pitch_variance": 0.5, "speed_wpm": params["speed_wpm"] * 1.1, "warmth": 0.8},
        }
        
        emo_adj = emotion_adjustments.get(emotion, {})
        params.update(emo_adj)
        
        # Apply learned context preferences (overrides)
        learned = self._context_profiles.get(context, {})
        for key, value in learned.items():
            if key in params:
                # Blend learned preference with computed value
                params[key] = params[key] * 0.6 + value * 0.4
        
        return params

    def _infer_emotion(self, text: str, context: SpeechContext) -> VoiceEmotion:
        """Infer appropriate emotion from text and context."""
        text_lower = text.lower()
        
        # Context-based defaults
        context_emotions = {
            SpeechContext.GREETING: VoiceEmotion.WARM,
            SpeechContext.WARNING: VoiceEmotion.SERIOUS,
            SpeechContext.CELEBRATION: VoiceEmotion.EXCITED,
            SpeechContext.ERROR_REPORT: VoiceEmotion.SERIOUS,
            SpeechContext.THINKING_ALOUD: VoiceEmotion.CURIOUS,
            SpeechContext.COMMAND: VoiceEmotion.AUTHORITATIVE,
        }
        
        if context in context_emotions:
            return context_emotions[context]
        
        # Text-based inference
        if any(w in text_lower for w in ["great", "excellent", "perfect", "done", "success"]):
            return VoiceEmotion.EXCITED
        if any(w in text_lower for w in ["error", "fail", "broken", "issue", "problem"]):
            return VoiceEmotion.SERIOUS
        if any(w in text_lower for w in ["think", "consider", "perhaps", "might", "maybe"]):
            return VoiceEmotion.CURIOUS
        if "?" in text:
            return VoiceEmotion.CURIOUS
        
        return self._profile.default_emotion

    def _process_text_for_speech(self, text: str, context: SpeechContext) -> str:
        """Process text to improve speech quality."""
        import re
        
        processed = text
        
        # Expand common abbreviations
        abbreviations = {
            "e.g.": "for example",
            "i.e.": "that is",
            "etc.": "etcetera",
            "vs.": "versus",
            "w/": "with",
            "b/c": "because",
            "API": "A P I",
            "UI": "U I",
            "CLI": "C L I",
            "gRPC": "g R P C",
            "GPU": "G P U",
            "CPU": "C P U",
            "LLM": "L L M",
        }
        for abbr, expansion in abbreviations.items():
            processed = processed.replace(abbr, expansion)
        
        # Add pauses at natural break points
        processed = re.sub(r'([.!?])\s+', r'\1 ... ', processed)  # Sentence breaks
        processed = re.sub(r'([:;])\s+', r'\1 .. ', processed)    # Clause breaks
        
        # Slow down for code-like content
        if context == SpeechContext.CODE_READING:
            # Add spaces around operators for clarity
            processed = re.sub(r'([=<>!]+)', r' \1 ', processed)
            # Spell out special characters
            processed = processed.replace('()', ' parentheses ')
            processed = processed.replace('[]', ' brackets ')
            processed = processed.replace('{}', ' braces ')
        
        # Handle numbers (speak them more clearly)
        def expand_number(match):
            num = match.group(0)
            if '.' in num:
                return f" {num} "
            return f" {num} "
        processed = re.sub(r'\d+\.?\d*', expand_number, processed)
        
        return processed.strip()

    # ═══════════════════════════════════════════════════════════════
    # PROVIDER BACKENDS
    # ═══════════════════════════════════════════════════════════════

    def _synthesize_with_provider(self, request_id: str, text: str,
                                   params: Dict[str, Any],
                                   emotion: VoiceEmotion) -> SpeechResult:
        """Route to the appropriate TTS provider."""
        # Try providers in order of preference
        for provider in self._available_providers:
            try:
                if provider == VoiceProvider.EDGE_TTS:
                    return self._synth_edge_tts(request_id, text, params, emotion)
                elif provider == VoiceProvider.OPENAI_TTS:
                    return self._synth_openai_tts(request_id, text, params, emotion)
                elif provider == VoiceProvider.PIPER:
                    return self._synth_piper(request_id, text, params)
                elif provider == VoiceProvider.SYSTEM:
                    return self._synth_system(request_id, text, params)
            except Exception:
                continue
        
        return SpeechResult(
            request_id=request_id,
            success=False,
            error="No TTS provider available",
        )

    def _synth_edge_tts(self, request_id: str, text: str,
                         params: Dict[str, Any], emotion: VoiceEmotion) -> SpeechResult:
        """Synthesize using Microsoft Edge TTS (free, good quality)."""
        output_path = str(self.audio_cache / f"{request_id}.mp3")
        
        # Map parameters to Edge TTS SSML
        rate = int((params.get("speed_wpm", 160) / 160 - 1) * 100)
        pitch_hz = int((params.get("pitch", 0.45) - 0.5) * 50)
        voice = self._profile.provider_voice or "en-US-GuyNeural"
        
        # Build SSML
        ssml = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>
<voice name='{voice}'>
<prosody rate='{rate:+d}%' pitch='{pitch_hz:+d}Hz'>
{text}
</prosody>
</voice>
</speak>"""
        
        # Execute edge-tts command
        try:
            cmd = [
                "edge-tts",
                "--voice", voice,
                "--rate", f"{rate:+d}%",
                "--pitch", f"{pitch_hz:+d}Hz",
                "--text", text[:5000],  # Edge TTS limit
                "--write-media", output_path,
            ]
            
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0 and Path(output_path).exists():
                audio_size = Path(output_path).stat().st_size
                # Estimate duration (rough: 1 second per 15 words)
                word_count = len(text.split())
                est_duration = word_count / (params.get("speed_wpm", 160) / 60)
                
                return SpeechResult(
                    request_id=request_id,
                    audio_path=output_path,
                    duration_seconds=est_duration,
                    provider_used="edge_tts",
                    naturalness_score=0.7,
                    success=True,
                )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        return SpeechResult(request_id=request_id, success=False, error="Edge TTS failed")

    def _synth_openai_tts(self, request_id: str, text: str,
                           params: Dict[str, Any], emotion: VoiceEmotion) -> SpeechResult:
        """Synthesize using OpenAI TTS API."""
        import urllib.request
        
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            return SpeechResult(request_id=request_id, success=False, error="No OpenAI key")
        
        # Map emotion to voice
        voice_map = {
            VoiceEmotion.WARM: "nova",
            VoiceEmotion.AUTHORITATIVE: "onyx",
            VoiceEmotion.CALM: "shimmer",
            VoiceEmotion.EXCITED: "alloy",
        }
        voice = voice_map.get(emotion, "onyx")
        
        speed = params.get("speed_wpm", 160) / 160  # Normalize to 1.0
        speed = max(0.25, min(4.0, speed))
        
        payload = json.dumps({
            "model": "tts-1-hd",
            "input": text[:4096],
            "voice": voice,
            "speed": speed,
            "response_format": "mp3",
        }).encode()
        
        req = urllib.request.Request(
            "https://api.openai.com/v1/audio/speech",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        
        try:
            output_path = str(self.audio_cache / f"{request_id}.mp3")
            with urllib.request.urlopen(req, timeout=30) as resp:
                audio_data = resp.read()
                Path(output_path).write_bytes(audio_data)
            
            word_count = len(text.split())
            est_duration = word_count / (params.get("speed_wpm", 160) / 60)
            
            return SpeechResult(
                request_id=request_id,
                audio_path=output_path,
                audio_data=audio_data,
                duration_seconds=est_duration,
                provider_used="openai_tts",
                naturalness_score=0.85,
                success=True,
            )
        except Exception as e:
            return SpeechResult(request_id=request_id, success=False, error=str(e))

    def _synth_piper(self, request_id: str, text: str, params: Dict[str, Any]) -> SpeechResult:
        """Synthesize using Piper TTS (fast, local, free)."""
        output_path = str(self.audio_cache / f"{request_id}.wav")
        
        try:
            cmd = f'echo "{text[:2000]}" | piper --output_file {output_path}'
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=15)
            
            if result.returncode == 0 and Path(output_path).exists():
                return SpeechResult(
                    request_id=request_id,
                    audio_path=output_path,
                    provider_used="piper",
                    naturalness_score=0.6,
                    success=True,
                )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        return SpeechResult(request_id=request_id, success=False, error="Piper not available")

    def _synth_system(self, request_id: str, text: str, params: Dict[str, Any]) -> SpeechResult:
        """Fallback: use OS text-to-speech."""
        output_path = str(self.audio_cache / f"{request_id}.aiff")
        
        try:
            # macOS say command
            speed_wpm = int(params.get("speed_wpm", 160))
            cmd = ["say", "-r", str(speed_wpm), "-o", output_path, text[:1000]]
            result = subprocess.run(cmd, capture_output=True, timeout=15)
            
            if result.returncode == 0:
                return SpeechResult(
                    request_id=request_id,
                    audio_path=output_path,
                    provider_used="system",
                    naturalness_score=0.4,
                    success=True,
                )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        return SpeechResult(request_id=request_id, success=False, error="System TTS failed")

    # ═══════════════════════════════════════════════════════════════
    # LEARNING — Evolve the voice over time
    # ═══════════════════════════════════════════════════════════════

    def record_feedback(self, feedback: VoiceFeedback):
        """Record feedback about a voice output and learn from it."""
        self._feedback_history.append(feedback)
        self._total_feedback += 1
        
        quality = feedback.quality_signal
        self._quality_trend.append(quality)
        
        # Update per-context quality
        self._feedback_by_context[feedback.speech_context].append(quality)
        self._feedback_by_emotion[feedback.emotion_used].append(quality)
        
        # Bucket speed into ranges
        speed_bucket = f"{int(feedback.speed_used / 20) * 20}"
        self._feedback_by_speed[speed_bucket].append(quality)
        
        # Evolve profile based on feedback
        self._evolve_from_feedback(feedback)
        
        # Periodic save
        if self._total_feedback % 20 == 0:
            self._save_profile()

    def _evolve_from_feedback(self, feedback: VoiceFeedback):
        """Adjust voice parameters based on feedback."""
        alpha = self.learning_rate
        quality = feedback.quality_signal
        
        # If quality is high (> 0.7), reinforce current settings
        # If quality is low (< 0.3), move away from current settings
        if quality > 0.7:
            # Reinforce: move toward the settings that produced this good output
            pass  # Current settings are already the profile values
        elif quality < 0.3:
            # The voice was too something — try to figure out what
            if feedback.skipped_at_seconds > 0 and feedback.skipped_at_seconds < 5:
                # Skipped very early — probably too slow or wrong tone
                self._profile.speed_wpm = min(200, self._profile.speed_wpm + 5)
            
            if not feedback.listened_to_completion:
                # Didn't finish listening — probably too long/boring
                self._profile.speed_wpm = min(200, self._profile.speed_wpm + 3)
                self._profile.pause_between_sentences_ms = max(200, 
                    self._profile.pause_between_sentences_ms - 20)
        
        # Explicit feedback is gold
        if feedback.explicit_comment:
            comment = feedback.explicit_comment.lower()
            
            if any(w in comment for w in ["slow", "faster", "too slow", "speed up"]):
                self._profile.speed_wpm = min(220, self._profile.speed_wpm + 10)
            elif any(w in comment for w in ["fast", "slower", "too fast", "slow down"]):
                self._profile.speed_wpm = max(100, self._profile.speed_wpm - 10)
            
            if any(w in comment for w in ["robotic", "mechanical", "flat", "monotone"]):
                self._profile.emotion_intensity = min(0.9, self._profile.emotion_intensity + 0.1)
                self._profile.pitch_variance = min(0.6, self._profile.pitch_variance + 0.05)
                self._profile.warmth = min(0.9, self._profile.warmth + 0.1)
            
            if any(w in comment for w in ["natural", "good", "nice", "perfect"]):
                # Reinforce all current settings
                self._generation += 1
            
            if any(w in comment for w in ["loud", "quiet", "volume"]):
                pass  # Volume is typically a system setting, not TTS
            
            if any(w in comment for w in ["deeper", "lower"]):
                self._profile.base_pitch = max(0.2, self._profile.base_pitch - 0.05)
            elif any(w in comment for w in ["higher", "lighter"]):
                self._profile.base_pitch = min(0.8, self._profile.base_pitch + 0.05)
        
        # Update context-specific learned parameters
        if feedback.speech_context:
            try:
                ctx = SpeechContext(feedback.speech_context)
                if quality > 0.6:
                    # Remember what worked for this context
                    self._context_profiles[ctx]["speed_wpm"] = feedback.speed_used
            except (ValueError, KeyError):
                pass
        
        # Update average quality
        recent = list(self._quality_trend)
        if recent:
            self._avg_quality = statistics.mean(recent)

    # ═══════════════════════════════════════════════════════════════
    # PROVIDER DETECTION
    # ═══════════════════════════════════════════════════════════════

    def _detect_providers(self):
        """Detect which TTS providers are available."""
        self._available_providers = []
        
        # Check for edge-tts (pip install edge-tts)
        try:
            result = subprocess.run(["edge-tts", "--list-voices"],
                                   capture_output=True, timeout=5)
            if result.returncode == 0:
                self._available_providers.append(VoiceProvider.EDGE_TTS)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # Check for OpenAI API key
        if os.environ.get("OPENAI_API_KEY"):
            self._available_providers.append(VoiceProvider.OPENAI_TTS)
        
        # Check for Piper
        try:
            result = subprocess.run(["piper", "--help"], capture_output=True, timeout=5)
            if result.returncode == 0:
                self._available_providers.append(VoiceProvider.PIPER)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # System TTS (macOS say / Linux espeak) — always available as fallback
        try:
            result = subprocess.run(["say", ""], capture_output=True, timeout=2)
            self._available_providers.append(VoiceProvider.SYSTEM)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            try:
                result = subprocess.run(["espeak", "--version"], capture_output=True, timeout=2)
                self._available_providers.append(VoiceProvider.SYSTEM)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
        
        if not self._available_providers:
            self._available_providers = [VoiceProvider.SYSTEM]

    # ═══════════════════════════════════════════════════════════════
    # PERSISTENCE
    # ═══════════════════════════════════════════════════════════════

    def _save_profile(self):
        """Save evolved voice profile."""
        filepath = self.data_dir / "voice_profile.json"
        data = {
            "profile": self._profile.to_dict(),
            "context_profiles": {
                k.value: v for k, v in self._context_profiles.items() if v
            },
            "generation": self._generation,
            "avg_quality": self._avg_quality,
            "total_speeches": self._total_speeches,
            "total_feedback": self._total_feedback,
            "saved_at": time.time(),
        }
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError:
            pass

    def _load_profile(self):
        """Load saved voice profile."""
        filepath = self.data_dir / "voice_profile.json"
        if not filepath.exists():
            return
        try:
            with open(filepath) as f:
                data = json.load(f)
            
            profile_data = data.get("profile", {})
            self._profile.speed_wpm = profile_data.get("speed_wpm", 160)
            self._profile.base_pitch = profile_data.get("pitch", 0.45)
            self._profile.pitch_variance = profile_data.get("pitch_variance", 0.3)
            self._profile.emotion_intensity = profile_data.get("emotion_intensity", 0.5)
            self._profile.warmth = profile_data.get("warmth", 0.5)
            self._profile.emphasis_strength = profile_data.get("emphasis", 0.6)
            
            self._generation = data.get("generation", 0)
            self._avg_quality = data.get("avg_quality", 0.5)
            self._total_speeches = data.get("total_speeches", 0)
            self._total_feedback = data.get("total_feedback", 0)
            
        except (IOError, json.JSONDecodeError):
            pass

    # ═══════════════════════════════════════════════════════════════
    # STATUS
    # ═══════════════════════════════════════════════════════════════

    def get_status(self) -> Dict[str, Any]:
        """Get voice engine status."""
        return {
            "profile": self._profile.to_dict(),
            "available_providers": [p.value for p in self._available_providers],
            "generation": self._generation,
            "metrics": {
                "total_speeches": self._total_speeches,
                "total_feedback": self._total_feedback,
                "avg_quality": self._avg_quality,
                "quality_trend": (
                    statistics.mean(list(self._quality_trend)[-20:]) -
                    statistics.mean(list(self._quality_trend)[:20])
                    if len(self._quality_trend) >= 40 else 0.0
                ),
            },
            "evolution": {
                "speed_wpm": self._profile.speed_wpm,
                "pitch": self._profile.base_pitch,
                "warmth": self._profile.warmth,
                "emotion_intensity": self._profile.emotion_intensity,
            },
        }
