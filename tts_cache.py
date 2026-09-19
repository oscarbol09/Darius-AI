"""
tts_cache.py — Sistema de Caché Local de Audio (Zero-Latency TTS)
================================================================
Almacena y reproduce archivos WAV cacheados en disco basados en un
hash SHA-256 de (texto + voice_id + model_id + output_format).

Ventajas:
  - 0ms de latencia de red en frases recurrentes (bienvenidas, avisos, etc.)
  - 0 consumo de créditos o cuota de API en repeticiones
  - Almacenamiento seguro en .cache/darius_tts/
"""

from __future__ import annotations

import hashlib
import logging
import os
import wave
from pathlib import Path

import numpy as np

log = logging.getLogger("DARIUS.TTSCache")

_BASE_DIR = Path(__file__).resolve().parent


def get_tts_cache_dir() -> Path:
    """Retorna el directorio de caché de audio, creándolo si no existe."""
    override = (os.environ.get("DARIUS_TTS_CACHE_DIR") or "").strip()
    cache_dir = Path(override).expanduser().resolve() if override else _BASE_DIR / ".cache" / "darius_tts"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def compute_cache_key(text: str, voice_id: str = "", model_id: str = "", output_format: str = "") -> str:
    """Genera un hash SHA-256 consistente de 24 caracteres a partir de los parámetros de voz."""
    normalized_text = " ".join(text.strip().lower().split())
    raw_key = f"{normalized_text}|{voice_id.strip()}|{model_id.strip()}|{output_format.strip()}".encode()
    return hashlib.sha256(raw_key).hexdigest()[:24]


def get_cached_wav_path(text: str, voice_id: str = "", model_id: str = "", output_format: str = "") -> Path:
    """Retorna la ruta del archivo WAV en caché para los parámetros dados."""
    key = compute_cache_key(text, voice_id, model_id, output_format)
    return get_tts_cache_dir() / f"{key}.wav"


def is_cached(text: str, voice_id: str = "", model_id: str = "", output_format: str = "") -> bool:
    """Verifica si ya existe un archivo de audio cacheado y válido."""
    path = get_cached_wav_path(text, voice_id, model_id, output_format)
    return path.is_file() and path.stat().st_size > 44  # Cabecera WAV mínima


def save_pcm_to_wav(path: Path, pcm_bytes: bytes, sample_rate: int = 24000, channels: int = 1) -> bool:
    """Guarda un buffer PCM de 16 bits en formato WAV estándar de forma atómica."""
    if not pcm_bytes:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f".{os.getpid()}.tmp")
    try:
        with wave.open(str(tmp_path), "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)  # 16-bit PCM
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        tmp_path.replace(path)
        log.debug(f"Audio guardado en caché: {path.name}")
        return True
    except Exception as e:
        log.warning(f"No se pudo guardar audio en caché: {e}")
        if tmp_path.is_file():
            tmp_path.unlink(missing_ok=True)
        return False


def play_cached_wav(path: Path) -> bool:
    """
    Reproduce un archivo WAV cacheado usando sounddevice o winsound nativo.
    Retorna True si la reproducción fue exitosa.
    """
    if not path.is_file():
        return False

    # Intento 1: sounddevice para reproducción fluida sin bloqueos
    try:
        import sounddevice as sd

        with wave.open(str(path), "rb") as wf:
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            raw_frames = wf.readframes(wf.getnframes())

        if sampwidth == 2 and raw_frames:
            pcm_i16 = np.frombuffer(raw_frames, dtype=np.int16)
            pcm_f = pcm_i16.astype(np.float32) / 32768.0
            if channels > 1:
                pcm_f = pcm_f.reshape(-1, channels)
            sd.play(pcm_f, framerate)
            sd.wait()
            return True
    except Exception as exc:
        log.debug(f"sounddevice playback fallback: {exc}")

    # Intento 2: winsound en Windows como fallback de bajo nivel
    try:
        import winsound

        winsound.PlaySound(str(path), winsound.SND_FILENAME)
        return True
    except Exception as exc:
        log.warning(f"Error al reproducir audio cacheado {path}: {exc}")
        return False
