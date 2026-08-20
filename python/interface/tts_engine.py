"""
Ultron TTS Engine — High-quality voice, cross-platform.

Priority chain for browser-streamable audio:
  1. macOS `say` + `afconvert`  → WAV  (best quality, macOS only)
  2. gTTS (Google TTS via pip)  → MP3  (any platform, needs internet)
  3. pyttsx3                    → WAV  (offline, any platform)
  4. espeak / espeak-ng         → WAV  (Linux fallback)

speak_directly() is macOS-only (uses `say` live) — only called for
local speaker output, never for browser streaming.
"""

import subprocess
import os
import platform
import tempfile
import time
import threading
from pathlib import Path
from typing import Optional


# Powerful deep male voice — Daniel (en_GB) is the best Ultron voice on macOS
ULTRON_VOICE: str = "Daniel"  # Deep British male
ULTRON_RATE: int = 145         # Slower = more menacing / authoritative

_IS_MACOS = platform.system() == "Darwin"

# ─────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────

def _tts_dir() -> Path:
    d = Path(tempfile.gettempdir()) / "ultron_tts"
    d.mkdir(exist_ok=True)
    return d


def _cleanup(directory: Path, keep: int = 10) -> None:
    """Remove old TTS files, keeping only the most recent `keep`."""
    existing = sorted(directory.glob("ultron_*"), key=os.path.getmtime)
    for old in existing[:-keep]:
        try:
            old.unlink()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────
# Backend: macOS say → WAV
# ─────────────────────────────────────────────────────────────

def _synth_macos(text: str, voice: str, rate: int) -> str:
    """macOS only. Returns WAV path or ''."""
    if not _IS_MACOS:
        return ""
    out_dir = _tts_dir()
    _cleanup(out_dir)
    stem = f"ultron_{int(time.time() * 1000)}"
    aiff_path = out_dir / f"{stem}.aiff"
    wav_path = out_dir / f"{stem}.wav"
    try:
        r = subprocess.run(
            ["say", "-v", voice, "-r", str(rate), "-o", str(aiff_path), text],
            capture_output=True, timeout=30,
        )
        if r.returncode != 0 or not aiff_path.exists():
            return ""
        subprocess.run(
            ["afconvert", "-f", "WAVE", "-d", "LEI16@22050", str(aiff_path), str(wav_path)],
            capture_output=True, timeout=10,
        )
        aiff_path.unlink(missing_ok=True)
        if wav_path.exists() and wav_path.stat().st_size > 100:
            return str(wav_path)
    except Exception:
        pass
    return ""


# ─────────────────────────────────────────────────────────────
# Backend: gTTS → MP3  (cross-platform, needs internet)
# ─────────────────────────────────────────────────────────────

def _synth_gtts(text: str) -> str:
    """Returns MP3 path or '' if gTTS unavailable / failed."""
    try:
        from gtts import gTTS  # pip install gTTS
        out_dir = _tts_dir()
        _cleanup(out_dir)
        mp3_path = out_dir / f"ultron_{int(time.time() * 1000)}.mp3"
        tts = gTTS(text=text, lang="en", slow=False)
        tts.save(str(mp3_path))
        if mp3_path.exists() and mp3_path.stat().st_size > 100:
            return str(mp3_path)
    except Exception:
        pass
    return ""


# ─────────────────────────────────────────────────────────────
# Backend: pyttsx3 → WAV  (fully offline, cross-platform)
# ─────────────────────────────────────────────────────────────

def _synth_pyttsx3(text: str) -> str:
    """Returns WAV path or '' if pyttsx3 unavailable."""
    try:
        import pyttsx3  # pip install pyttsx3
        out_dir = _tts_dir()
        _cleanup(out_dir)
        wav_path = str(out_dir / f"ultron_{int(time.time() * 1000)}.wav")
        engine = pyttsx3.init()
        engine.setProperty("rate", ULTRON_RATE)
        # Prefer deep male voice
        for v in engine.getProperty("voices") or []:
            if "male" in (v.name or "").lower() or "daniel" in (v.name or "").lower():
                engine.setProperty("voice", v.id)
                break
        engine.save_to_file(text, wav_path)
        engine.runAndWait()
        p = Path(wav_path)
        if p.exists() and p.stat().st_size > 100:
            return str(p)
    except Exception:
        pass
    return ""


# ─────────────────────────────────────────────────────────────
# Backend: espeak → WAV  (Linux / fallback)
# ─────────────────────────────────────────────────────────────

def _synth_espeak(text: str) -> str:
    """Returns WAV path or '' if espeak unavailable."""
    try:
        out_dir = _tts_dir()
        _cleanup(out_dir)
        wav_path = str(out_dir / f"ultron_{int(time.time() * 1000)}.wav")
        r = subprocess.run(
            ["espeak", "-s", str(ULTRON_RATE), "-w", wav_path, text],
            capture_output=True, timeout=20,
        )
        p = Path(wav_path)
        if r.returncode == 0 and p.exists() and p.stat().st_size > 100:
            return str(p)
    except Exception:
        pass
    return ""


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def synthesize(text: str, voice: Optional[str] = None, rate: Optional[int] = None) -> str:
    """
    Synthesize `text` to an audio file (WAV or MP3).
    Returns the file path, or '' on complete failure.

    Tries backends in order:
      macOS say  →  gTTS  →  pyttsx3  →  espeak
    """
    v = voice or ULTRON_VOICE
    r = rate or ULTRON_RATE

    # 1. macOS native (best quality)
    path = _synth_macos(text, v, r)
    if path:
        return path

    # 2. gTTS (any platform, internet required)
    path = _synth_gtts(text)
    if path:
        return path

    # 3. pyttsx3 (offline, cross-platform)
    path = _synth_pyttsx3(text)
    if path:
        return path

    # 4. espeak (Linux / last resort)
    return _synth_espeak(text)


def synthesize_for_browser(text: str) -> tuple[str, str]:
    """
    Like synthesize() but also returns the MIME type so the
    server can set the correct Content-Type header.

    Returns: (file_path, mime_type)  — file_path may be '' on failure.
    """
    path = synthesize(text)
    if not path:
        return "", "audio/wav"
    mime = "audio/mpeg" if path.endswith(".mp3") else "audio/wav"
    return path, mime


def speak_directly(text: str, voice: Optional[str] = None, rate: Optional[int] = None) -> None:
    """
    Speak directly through Mac speakers. Non-blocking (daemon thread).
    macOS only — uses `say` live; no file is created.
    On non-macOS hosts this is a no-op (browser TTS handles playback).
    """
    if not _IS_MACOS:
        return
    v = voice or ULTRON_VOICE
    r = rate or ULTRON_RATE

    def _speak() -> None:
        subprocess.run(
            ["say", "-v", v, "-r", str(r), text],
            capture_output=True, timeout=120,
        )

    threading.Thread(target=_speak, daemon=True).start()


def stop_speaking() -> None:
    """Kill any running `say` process (macOS). No-op elsewhere."""
    if _IS_MACOS:
        subprocess.run(["killall", "say"], capture_output=True)