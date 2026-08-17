"""
Ultron TTS Engine — High-quality voice using macOS native neural voices.
Plays audio directly on the machine (no browser autoplay issues).
"""

import subprocess
import os
import tempfile
import time
import threading
from pathlib import Path


# Powerful deep male voice
ULTRON_VOICE: str = "Daniel"  # Deep British male - most powerful sounding
ULTRON_RATE: int = 170


def synthesize(text: str, voice: str | None = None, rate: int | None = None) -> str:
    """
    Synthesize text to WAV using macOS native TTS.
    Returns path to WAV file.
    """
    voice = voice or ULTRON_VOICE
    rate = rate or ULTRON_RATE

    output_dir: Path = Path(tempfile.gettempdir()) / "ultron_tts"
    output_dir.mkdir(exist_ok=True)

    # Clean old files
    existing: list[Path] = sorted(output_dir.glob("*.wav"), key=os.path.getmtime)
    for old in existing[:-10]:
        try:
            old.unlink()
        except Exception:
            pass

    aiff_path: Path = output_dir / f"ultron_{int(time.time() * 1000)}.aiff"
    wav_path: Path = aiff_path.with_suffix('.wav')

    try:
        result = subprocess.run(
            ["say", "-v", voice, "-r", str(rate), "-o", str(aiff_path), text],
            capture_output=True,
            timeout=30,
        )

        if result.returncode != 0 or not aiff_path.exists():
            return ""

        subprocess.run(
            ["afconvert", "-f", "WAVE", "-d", "LEI16@22050", str(aiff_path), str(wav_path)],
            capture_output=True,
            timeout=10,
        )

        aiff_path.unlink(missing_ok=True)

        if wav_path.exists() and wav_path.stat().st_size > 100:
            return str(wav_path)

    except Exception:
        pass

    return ""


def speak_directly(text: str, voice: str | None = None, rate: int | None = None):
    """
    Speak directly through Mac speakers. No file, no browser.
    This is the most reliable method — uses macOS `say` command live.
    """
    voice = voice or ULTRON_VOICE
    rate = rate or ULTRON_RATE

    def _speak():
        subprocess.run(
            ["say", "-v", voice, "-r", str(rate), text],
            capture_output=True,
            timeout=60,
        )

    # Run in thread so it doesn't block the server
    threading.Thread(target=_speak, daemon=True).start()


def stop_speaking() -> None:
    """Kill any running say process."""
    subprocess.run(["killall", "say"], capture_output=True)