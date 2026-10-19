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
import hashlib
import queue
from collections import OrderedDict
from pathlib import Path
from typing import Optional, Tuple

# ── Audio cache for repeated phrases (LRU, bounded) ──────────────
_AUDIO_CACHE_MAX = int(os.environ.get("TTS_CACHE_SIZE", "128"))
_audio_cache: "OrderedDict[str, bytes]" = OrderedDict()
_cache_lock = threading.Lock()

def _cache_key(text: str, lang: str) -> str:
    return hashlib.sha1(f"{lang}:{text}".encode("utf-8")).hexdigest()

def _cache_get(text: str, lang: str) -> Optional[bytes]:
    key = _cache_key(text, lang)
    with _cache_lock:
        if key in _audio_cache:
            _audio_cache.move_to_end(key)   # mark recently used
            return _audio_cache[key]
    return None

def _cache_put(text: str, lang: str, audio: bytes) -> None:
    if not audio:
        return
    key = _cache_key(text, lang)
    with _cache_lock:
        _audio_cache[key] = audio
        _audio_cache.move_to_end(key)
        while len(_audio_cache) > _AUDIO_CACHE_MAX:
            _audio_cache.popitem(last=False)   # evict least-recently-used

# ── Non-blocking async speech queue ──────────────────────────────
# Chunks of text are enqueued and synthesized concurrently so audio
# generation begins while later text is still being produced. A worker
# thread drains the queue so the caller never blocks on synthesis.
_speech_queue: "queue.Queue[Optional[str]]" = queue.Queue()
_speech_worker: Optional[threading.Thread] = None
_speech_worker_lock = threading.Lock()

# Primary engine stall timeout — if synthesis exceeds this, fall back.
_PRIMARY_TIMEOUT = float(os.environ.get("TTS_PRIMARY_TIMEOUT", "2.5"))

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

# AWS Polly — uses the same credential chain as the brain (zero config)
# Voice can be overridden via env but defaults to Matthew (deep Neural US male)
_POLLY_VOICE_EN  = os.environ.get("POLLY_VOICE_EN", "Matthew")
_POLLY_VOICE_HI  = os.environ.get("POLLY_VOICE_HI", "Aditi")
_polly_client    = None   # lazy-initialized from default credentials

def _get_polly_client():
    """Lazy-initialize Polly using the machine's default AWS credentials."""
    global _polly_client
    if _polly_client is None:
        try:
            import boto3
            # Reuse real_brain's session logic if available, else default session
            try:
                from .real_brain import _get_aws_session, _get_region
                _polly_client = _get_aws_session().client("polly", region_name=_get_region())
            except ImportError:
                _polly_client = boto3.Session().client("polly")
        except Exception as e:
            print(f"[TTS] Polly client init failed: {e}")
    return _polly_client

# SoX processing — what makes it sound like Ultron not a podcast host
_SOX_PITCH   = "-600"   # semitone shift (negative = lower/darker)
_SOX_BASS    = "+5"     # dB bass boost
_SOX_REVERB  = ["15", "10", "70"]  # reverberance, hf-damping, room-scale

# ── Language mode ────────────────────────────────────────────────
# Set ULTRON_LANG=hi for Hindi voice, default is English
_LANG = os.environ.get("ULTRON_LANG", "en").lower()

# English voice (deep, frightening)
_EDGE_VOICE_EN = "en-GB-RyanNeural"

# Hindi voice — deep male, frightening — SanjayNeural is the darkest available
_EDGE_VOICE_HI = "hi-IN-MadhurNeural"   # deep male Hindi voice

# Select active voice based on language
_EDGE_VOICE  = _EDGE_VOICE_HI if _LANG == "hi" else _EDGE_VOICE_EN
_EDGE_RATE   = "-15%" if _LANG == "hi" else "+5%"    # slower for Hindi = more ominous
_EDGE_PITCH  = "-12Hz" if _LANG == "hi" else "-8Hz"  # lower pitch for Hindi
_MACOS_VOICE = "Daniel"
_MACOS_RATE  = 130 if _LANG == "hi" else 150


def set_language(lang: str):
    """Switch TTS language at runtime. lang='hi' or lang='en'."""
    global _LANG, _EDGE_VOICE, _EDGE_RATE, _EDGE_PITCH, _MACOS_RATE, _piper_voice
    _LANG = lang.lower()
    if _LANG == "hi":
        _EDGE_VOICE = _EDGE_VOICE_HI
        _EDGE_RATE  = "-15%"
        _EDGE_PITCH = "-12Hz"
        _MACOS_RATE = 130
    else:
        _EDGE_VOICE = _EDGE_VOICE_EN
        _EDGE_RATE  = "+5%"
        _EDGE_PITCH = "-8Hz"
        _MACOS_RATE = 150
    _piper_voice = None  # force reload

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
# BACKEND 0 — Amazon Polly Neural (primary — best quality)
# ══════════════════════════════════════════════════════════════

def _synth_polly(text: str) -> str:
    """
    Generate speech with Amazon Polly Neural engine.
    Uses machine's default AWS credentials — no keys needed.
    """
    try:
        polly = _get_polly_client()
        if polly is None:
            return ""

        voice_id  = _POLLY_VOICE_HI if _LANG == "hi" else _POLLY_VOICE_EN
        engine    = "standard" if voice_id == "Aditi" else "neural"
        lang_code = "hi-IN"    if _LANG == "hi"       else "en-US"

        response = polly.synthesize_speech(
            Text=text,
            OutputFormat="mp3",
            VoiceId=voice_id,
            Engine=engine,
            LanguageCode=lang_code,
        )

        out_dir  = _tts_dir()
        _cleanup(out_dir)
        mp3_path = out_dir / f"ultron_{int(time.time()*1000)}.mp3"
        with open(str(mp3_path), "wb") as f:
            f.write(response["AudioStream"].read())

        if not mp3_path.exists() or mp3_path.stat().st_size < 100:
            return ""

        # Apply SoX darkening (Ultron voice signature)
        sox_available = subprocess.run(
            ["which", "sox"], capture_output=True
        ).returncode == 0
        if sox_available:
            dark_wav = out_dir / f"ultron_{int(time.time()*1000)}_dark.wav"
            sox_cmd  = [
                "sox", str(mp3_path), str(dark_wav),
                "pitch",  _SOX_PITCH,
                "gain",   "-6",
                "bass",   _SOX_BASS,
                "reverb", *_SOX_REVERB,
                "gain",   "-2",
            ]
            r = subprocess.run(sox_cmd, capture_output=True, timeout=15)
            mp3_path.unlink(missing_ok=True)
            if dark_wav.exists() and dark_wav.stat().st_size > 100:
                return str(dark_wav)

        return str(mp3_path)
    except Exception as e:
        print(f"[TTS] Polly error: {e}")
    return ""




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
# BACKEND 1b — Piper fast (no SoX — use when speed > quality)
# ══════════════════════════════════════════════════════════════

def _synth_piper_fast(text: str) -> str:
    """Piper TTS without SoX post-processing — 3x faster."""
    voice = _get_piper_voice()
    if voice is None:
        return ""
    try:
        out_dir = _tts_dir()
        _cleanup(out_dir)
        raw_wav = out_dir / f"ultron_{int(time.time()*1000)}.wav"
        buf = io.BytesIO()
        wf  = wave.open(buf, "wb")
        voice.synthesize_wav(text, wf)
        wf.close()
        buf.seek(0)
        raw_wav.write_bytes(buf.read())
        if raw_wav.exists() and raw_wav.stat().st_size > 100:
            return str(raw_wav)
    except Exception as e:
        print(f"[TTS] Piper fast error: {e}")
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
    Priority: macOS say (fast, local) → Piper → Amazon Polly → edge-tts
    SoX darkening is skipped by default for speed; set ULTRON_SOX=1 to enable.
    """
    use_sox = os.environ.get("ULTRON_SOX", "0") == "1"

    # 0. macOS say — fastest (< 500ms, no network, no model load)
    if _IS_MACOS:
        path = _synth_macos(text)
        if path:
            return path

    # 1. Piper (dark, powerful, local — requires model file)
    path = _synth_piper(text) if use_sox else _synth_piper_fast(text)
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
