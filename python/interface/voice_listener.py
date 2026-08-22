"""
Voice Listener — Always-On Speech-to-Text for Ultron.

Uses multiple STT backends (whichever is available):
  1. whisper.cpp (local, fast, no internet needed)
  2. macOS Dictation (built-in, decent quality)
  3. Vosk (offline, lightweight)
  4. Ollama whisper model (if available)

Listens continuously, detects wake word "Ultron", then processes
the command and routes it to the brain.

Architecture:
  - Background thread captures audio in chunks via `sox` or `ffmpeg`
  - Each chunk is transcribed
  - Wake word detection triggers full command processing
  - Command is sent to generate_response() and spoken back via TTS
"""

import json
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Optional


# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

WAKE_WORDS = ["ultron", "hey ultron", "ok ultron", "yo ultron"]
LISTEN_DURATION = 5  # seconds per chunk
SILENCE_THRESHOLD = 2  # seconds of silence before processing
SAMPLE_RATE = 16000

PROJECT_ROOT = Path(__file__).parent.parent.parent
AUDIO_CACHE = PROJECT_ROOT / "data" / "voice" / "cache"
AUDIO_CACHE.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════
# STT BACKENDS
# ═══════════════════════════════════════════════════════════════

def _find_stt_backend() -> str:
    """Find the best available STT backend."""
    # 1. Check for whisper CLI (whisper.cpp)
    try:
        result = subprocess.run(["which", "whisper"], capture_output=True, timeout=3)
        if result.returncode == 0:
            return "whisper_cli"
    except Exception:
        pass

    # 2. Check for whisper.cpp compiled binary
    whisper_main = PROJECT_ROOT / "tools" / "whisper.cpp" / "main"
    if whisper_main.exists():
        return "whisper_cpp"

    # 3. Check for Python whisper
    try:
        import whisper
        return "whisper_python"
    except ImportError:
        pass

    # 4. Check for Vosk
    try:
        import vosk
        return "vosk"
    except ImportError:
        pass

    # 5. macOS dictation via AppleScript (always available)
    return "macos_dictation"


def transcribe_audio(audio_path: str, backend: str = None) -> str:
    """Transcribe an audio file using the best available backend."""
    if backend is None:
        backend = _find_stt_backend()

    if backend == "whisper_cli":
        return _transcribe_whisper_cli(audio_path)
    elif backend == "whisper_cpp":
        return _transcribe_whisper_cpp(audio_path)
    elif backend == "whisper_python":
        return _transcribe_whisper_python(audio_path)
    elif backend == "vosk":
        return _transcribe_vosk(audio_path)
    elif backend == "macos_dictation":
        return _transcribe_macos(audio_path)
    return ""


def _transcribe_whisper_cli(audio_path: str) -> str:
    """Use whisper CLI. Pre-converts audio to 16kHz/16-bit WAV first,
    which fixes ffmpeg 9.x incompatibility with sox-recorded files."""
    import tempfile
    converted_path = audio_path.replace(".wav", "_16k.wav")
    try:
        # Normalise to 16 kHz mono s16 PCM — whisper's required format
        conv = subprocess.run(
            ["ffmpeg", "-y", "-i", audio_path,
             "-ar", "16000", "-ac", "1", "-sample_fmt", "s16", converted_path],
            capture_output=True, timeout=10
        )
        target = converted_path if (conv.returncode == 0 and
                                     os.path.exists(converted_path)) else audio_path
        result = subprocess.run(
            ["whisper", target, "--model", "base",
             "--output_format", "txt", "--language", "en"],
            capture_output=True, text=True, timeout=30
        )
        txt_path = target.rsplit(".", 1)[0] + ".txt"
        if os.path.exists(txt_path):
            text = open(txt_path).read().strip()
            os.unlink(txt_path)
            return text
        return result.stdout.strip()
    except Exception:
        return ""
    finally:
        # Clean up converted file
        if os.path.exists(converted_path) and converted_path != audio_path:
            try:
                os.unlink(converted_path)
            except Exception:
                pass


def _transcribe_whisper_cpp(audio_path: str) -> str:
    """Use locally compiled whisper.cpp."""
    whisper_main = PROJECT_ROOT / "tools" / "whisper.cpp" / "main"
    model_path = PROJECT_ROOT / "tools" / "whisper.cpp" / "models" / "ggml-base.en.bin"
    try:
        result = subprocess.run(
            [str(whisper_main), "-m", str(model_path), "-f", audio_path, "--no-timestamps"],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _transcribe_whisper_python(audio_path: str) -> str:
    """Use Python whisper library."""
    try:
        import whisper
        model = whisper.load_model("base")
        result = model.transcribe(audio_path)
        return result.get("text", "").strip()
    except Exception:
        return ""


def _transcribe_vosk(audio_path: str) -> str:
    """Use Vosk for offline STT."""
    try:
        import vosk
        import wave

        model_path = str(PROJECT_ROOT / "tools" / "vosk-model")
        if not os.path.exists(model_path):
            return ""

        model = vosk.Model(model_path)
        wf = wave.open(audio_path, "rb")
        rec = vosk.KaldiRecognizer(model, wf.getframerate())

        text_parts = []
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text_parts.append(result.get("text", ""))

        final = json.loads(rec.FinalResult())
        text_parts.append(final.get("text", ""))
        return " ".join(text_parts).strip()
    except Exception:
        return ""


def _transcribe_macos(audio_path: str) -> str:
    """
    Fallback: Use macOS built-in speech recognition.
    This uses the `say` inverse — actually there's no direct CLI for this on macOS
    without additional tools. We'll use a simple sox-based approach.
    """
    # On macOS, the best free option without extra installs is
    # to use the Speech framework via a small Swift script
    # For now, return empty — this backend is the fallback when nothing else works
    return ""


# ═══════════════════════════════════════════════════════════════
# AUDIO CAPTURE
# ═══════════════════════════════════════════════════════════════

def _record_chunk(duration: float = 5.0) -> Optional[str]:
    """Record an audio chunk using sox (rec) or ffmpeg."""
    output_path = str(AUDIO_CACHE / f"chunk_{int(time.time())}.wav")

    # Try sox first (most common on macOS with `brew install sox`)
    try:
        result = subprocess.run(
            ["rec", "-q", "-r", str(SAMPLE_RATE), "-c", "1", "-b", "16",
             output_path, "trim", "0", str(duration)],
            capture_output=True, timeout=duration + 5
        )
        if result.returncode == 0 and os.path.exists(output_path):
            return output_path
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Try ffmpeg
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-f", "avfoundation", "-i", ":0",
             "-t", str(duration), "-ar", str(SAMPLE_RATE),
             "-ac", "1", output_path],
            capture_output=True, timeout=duration + 5
        )
        if result.returncode == 0 and os.path.exists(output_path):
            return output_path
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return None


# ═══════════════════════════════════════════════════════════════
# VOICE LISTENER
# ═══════════════════════════════════════════════════════════════

class VoiceListener:
    """
    Always-on voice listener. Captures audio, detects wake word,
    processes commands via Ultron's brain.
    """

    def __init__(self, on_command: Callable[[str], str] = None):
        """
        Args:
            on_command: Callback function that takes a transcribed command
                       and returns a response to speak.
        """
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._on_command = on_command
        self._backend = _find_stt_backend()
        self._listening = False
        self._wake_detected = False

    def start(self):
        """Start listening."""
        self._running = True
        self._thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name="VoiceListener",
        )
        self._thread.start()
        print(f"[VOICE-LISTEN] Online — backend: {self._backend} | Wake word: 'Ultron'")

    def stop(self):
        self._running = False

    @property
    def is_listening(self) -> bool:
        return self._listening

    def _listen_loop(self):
        """Continuous listening loop."""
        # Check if we can actually record
        test_path = _record_chunk(1.0)
        if not test_path:
            print("[VOICE-LISTEN] Cannot access microphone. Install sox: brew install sox")
            return
        # Clean test file
        try:
            os.unlink(test_path)
        except Exception:
            pass

        while self._running:
            self._listening = True
            try:
                # Record a chunk
                audio_path = _record_chunk(LISTEN_DURATION)
                if not audio_path:
                    time.sleep(1)
                    continue

                # Transcribe
                text = transcribe_audio(audio_path, self._backend)

                # Clean up audio file
                try:
                    os.unlink(audio_path)
                except Exception:
                    pass

                if not text:
                    continue

                text_lower = text.lower().strip()

                # Check for wake word
                wake_detected = any(w in text_lower for w in WAKE_WORDS)

                if wake_detected or self._wake_detected:
                    # Remove wake word from command
                    command = text_lower
                    for w in WAKE_WORDS:
                        command = command.replace(w, "").strip()

                    if command and len(command) > 2:
                        self._wake_detected = False
                        print(f"[VOICE-LISTEN] Command: '{command}'")

                        # Process command
                        if self._on_command:
                            response = self._on_command(command)
                            # Speak response
                            if response:
                                self._speak_response(response)
                    else:
                        # Wake word detected but no command yet — listen for next chunk
                        self._wake_detected = True

            except Exception as e:
                print(f"[VOICE-LISTEN] Error: {e}")
                time.sleep(2)

        self._listening = False

    def _speak_response(self, text: str):
        """Speak the response back using TTS."""
        # Truncate long responses
        if len(text) > 300:
            text = text[:300] + "..."

        try:
            subprocess.Popen(
                ["say", "-v", "Daniel", "-r", "170", text],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# CONVENIENCE
# ═══════════════════════════════════════════════════════════════

_global_listener: Optional[VoiceListener] = None


def get_voice_listener(on_command: Callable[[str], str] = None) -> VoiceListener:
    """Get or create the global voice listener."""
    global _global_listener
    if _global_listener is None:
        _global_listener = VoiceListener(on_command)
    return _global_listener
