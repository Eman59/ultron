"""
Ultron TTS Engine — Piper Neural + SoX Dark Processing.

Pipeline:
  1. Piper TTS (en_US-ryan-high) — local neural voice, unlimited, free forever
  2. SoX post-processing         — pitch down, bass boost, reverb
     Result: deep, dark, powerful — not a voice assistant, an entity.

Fallback chain if Piper unavailable:
  3. edge-tts (Microsoft Neural) — still human, no processing
  4. macOS say                   — offline last resort

Works locally AND deployed in Docker/Railway — no API key, no limits.
"""

import io
import os
import platform
import subprocess
import asyncio
import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import Optional, Tuple

# ── Load .env ──────────────────────────────────────────────────
_env_path = Path(__file__).parent.parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        if "=" in _line and not _line.strip().startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# ── Config ─────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_MODEL_PATH   = _PROJECT_ROOT / "models" / "tts" / "en_US-ryan-high.onnx"

# SoX processing — what makes it sound like Ultron not a podcast host
_SOX_PITCH   = "-600"   # semitone shift (negative = lower/darker)
_SOX_BASS    = "+5"     # dB bass boost
_SOX_REVERB  = ["15", "10", "70"]  # reverberance, hf-damping, room-scale

# Fallback
_EDGE_VOICE  = "en-GB-RyanNeural"
_EDGE_RATE   = "+5%"
_EDGE_PITCH  = "-8Hz"
_MACOS_VOICE = "Daniel"
_MACOS_RATE  = 150

_IS_MACOS = platform.system() == "Darwin"

# Lazy-loaded Piper voice instance (load once, reuse)
_piper_voice = None
_piper_lock  = threading.Lock()


# ══════════════════════════════════════════════════════════════
# PIPER LOADER
# ══════════════════════════════════════════════════════════════

def _get_piper_voice():
    global _piper_voice
    if _piper_voice is not None:
        return _piper_voice
    with _piper_lock:
        if _piper_voice is not None:
            return _piper_voice
        if not _MODEL_PATH.exists():
            return None
        try:
            from piper.voice import PiperVoice
            _piper_voice = PiperVoice.load(str(_MODEL_PATH))
            return _piper_voice
        except Exception as e:
            print(f"[TTS] Piper load failed: {e}")
            return None


# ══════════════════════════════════════════════════════════════
# BACKEND 1 — Piper + SoX (the real Ultron voice)
# ══════════════════════════════════════════════════════════════

def _synth_piper(text: str, rate: float = 0.8) -> str:
    """
    Generate speech with Piper then darken it with SoX.
    Returns WAV path or '' on failure.
    """
    voice = _get_piper_voice()
    if voice is None:
        return ""

    try:
        out_dir  = _tts_dir()
        _cleanup(out_dir)
        raw_wav  = out_dir / f"ultron_raw_{int(time.time()*1000)}.wav"
        proc_wav = out_dir / f"ultron_{int(time.time()*1000)}.wav"

        # Generate raw speech
        buf = io.BytesIO()
        wf  = wave.open(buf, "wb")
        voice.synthesize_wav(text, wf)
        wf.close()
        buf.seek(0)
        raw_wav.write_bytes(buf.read())

        if not raw_wav.exists() or raw_wav.stat().st_size < 100:
            return ""

        # Apply SoX dark processing
        sox_cmd = [
            "sox", str(raw_wav), str(proc_wav),
            "pitch",  _SOX_PITCH,
            "gain",   "-6",
            "bass",   _SOX_BASS,
            "reverb", *_SOX_REVERB,
            "gain",   "-2",
        ]
        result = subprocess.run(sox_cmd, capture_output=True, timeout=15)

        # Clean up raw file
        raw_wav.unlink(missing_ok=True)

        if proc_wav.exists() and proc_wav.stat().st_size > 100:
            return str(proc_wav)

    except Exception as e:
        print(f"[TTS] Piper error: {e}")

    return ""


# ══════════════════════════════════════════════════════════════
# BACKEND 2 — edge-tts (free Microsoft Neural, no processing)
# ══════════════════════════════════════════════════════════════

def _synth_edge(text: str) -> str:
    try:
        import edge_tts
        out_dir  = _tts_dir()
        _cleanup(out_dir)
        mp3_path = str(out_dir / f"ultron_{int(time.time()*1000)}.mp3")

        async def _gen():
            comm = edge_tts.Communicate(
                text, voice=_EDGE_VOICE,
                rate=_EDGE_RATE, pitch=_EDGE_PITCH,
            )
            await comm.save(mp3_path)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_gen())
        finally:
            loop.close()

        p = Path(mp3_path)
        if p.exists() and p.stat().st_size > 500:
            return mp3_path
    except Exception as e:
        print(f"[TTS] edge-tts error: {e}")
    return ""


# ══════════════════════════════════════════════════════════════
# BACKEND 3 — macOS say (last resort, offline)
# ══════════════════════════════════════════════════════════════

def _synth_macos(text: str) -> str:
    if not _IS_MACOS:
        return ""
    out_dir   = _tts_dir()
    _cleanup(out_dir)
    stem      = f"ultron_{int(time.time()*1000)}"
    aiff_path = out_dir / f"{stem}.aiff"
    wav_path  = out_dir / f"{stem}.wav"
    try:
        r = subprocess.run(
            ["say", "-v", _MACOS_VOICE, "-r", str(_MACOS_RATE),
             "-o", str(aiff_path), text],
            capture_output=True, timeout=30,
        )
        if r.returncode != 0:
            return ""
        subprocess.run(
            ["afconvert", "-f", "WAVE", "-d", "LEI16@22050",
             str(aiff_path), str(wav_path)],
            capture_output=True, timeout=10,
        )
        aiff_path.unlink(missing_ok=True)
        if wav_path.exists() and wav_path.stat().st_size > 100:
            return str(wav_path)
    except Exception:
        pass
    return ""


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

def _tts_dir() -> Path:
    d = Path(tempfile.gettempdir()) / "ultron_tts"
    d.mkdir(exist_ok=True)
    return d


def _cleanup(directory: Path, keep: int = 10):
    existing = sorted(directory.glob("ultron_*"), key=os.path.getmtime)
    for old in existing[:-keep]:
        try:
            old.unlink()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════

def synthesize(text: str, **kwargs) -> str:
    """
    Convert text → audio file path.
    Priority: Piper+SoX → edge-tts → macOS say
    """
    # 1. Piper (dark, powerful, local)
    path = _synth_piper(text)
    if path:
        return path

    # 2. edge-tts (neural, human, fallback)
    path = _synth_edge(text)
    if path:
        return path

    # 3. macOS say (offline last resort)
    return _synth_macos(text)


def synthesize_for_browser(text: str) -> Tuple[str, str]:
    """Returns (file_path, mime_type) for browser streaming."""
    path = synthesize(text)
    if not path:
        return "", "audio/wav"
    mime = "audio/mpeg" if path.endswith(".mp3") else "audio/wav"
    return path, mime


def speak_directly(text: str, **kwargs) -> None:
    """Play through local Mac speakers. Non-blocking."""
    def _play():
        path = synthesize(text)
        if path and _IS_MACOS:
            subprocess.run(["afplay", path], capture_output=True, timeout=120)
        elif _IS_MACOS:
            subprocess.run(
                ["say", "-v", _MACOS_VOICE, "-r", str(_MACOS_RATE), text],
                capture_output=True, timeout=120,
            )
    threading.Thread(target=_play, daemon=True).start()


def stop_speaking() -> None:
    if _IS_MACOS:
        subprocess.run(["killall", "afplay"], capture_output=True)
        subprocess.run(["killall", "say"],    capture_output=True)


def active_engine() -> str:
    if _MODEL_PATH.exists():
        return "Piper (en_US-ryan-high) + SoX dark processing — LOCAL, unlimited, free"
    return "edge-tts (en-US-GuyNeural) — install piper-tts for full power"
