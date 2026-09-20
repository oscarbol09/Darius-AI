"""
test_tts_cache.py — Tests Unitarios para el Módulo de Caché de Audio TTS
========================================================================
Valida la generación de hashes SHA-256, guardado atómico de archivos WAV,
y recuperación desde disco sin degradación.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from tts_cache import (
    compute_cache_key,
    get_cached_wav_path,
    is_cached,
    play_cached_wav,
    save_pcm_to_wav,
)


def test_compute_cache_key_consistency():
    """El hash SHA-256 debe ser determinista e insensible a espacios adicionales."""
    k1 = compute_cache_key("Hola Mundo", "voice1", "model1", "pcm_24000")
    k2 = compute_cache_key("  hola   mundo  ", "voice1", "model1", "pcm_24000")
    assert k1 == k2
    assert len(k1) == 24


def test_compute_cache_key_different_params():
    """Parámetros distintos deben generar hashes distintos."""
    k1 = compute_cache_key("Hola", "voice1", "model1", "pcm_24000")
    k2 = compute_cache_key("Hola", "voice2", "model1", "pcm_24000")
    k3 = compute_cache_key("Hola", "voice1", "model2", "pcm_24000")
    assert k1 != k2
    assert k1 != k3


def test_save_and_is_cached(tmp_path: Path, monkeypatch):
    """Guardado de audio PCM en formato WAV y verificación de existencia."""
    monkeypatch.setenv("DARIUS_TTS_CACHE_DIR", str(tmp_path))

    text = "Mensaje de prueba para caché"
    voice = "voice_es_1"
    model = "eleven_multilingual_v2"
    fmt = "pcm_24000"

    assert not is_cached(text, voice, model, fmt)

    target_path = get_cached_wav_path(text, voice, model, fmt)

    # Generar 1 segundo de audio sintético PCM 16-bit (24000 muestras)
    samples = (np.sin(np.linspace(0, 440 * 2 * np.pi, 24000)) * 16000).astype(np.int16)
    pcm_bytes = samples.tobytes()

    saved = save_pcm_to_wav(target_path, pcm_bytes, sample_rate=24000)
    assert saved is True
    assert target_path.exists()
    assert is_cached(text, voice, model, fmt)


def test_save_empty_pcm_returns_false(tmp_path: Path):
    """Guardar un buffer vacío debe retornar False sin crear archivo."""
    path = tmp_path / "empty.wav"
    assert save_pcm_to_wav(path, b"") is False
    assert not path.exists()


def test_play_cached_wav(tmp_path: Path):
    """Reproducción de audio cacheado con mocks."""
    wav_file = tmp_path / "test.wav"
    samples = np.zeros(1000, dtype=np.int16)
    save_pcm_to_wav(wav_file, samples.tobytes(), sample_rate=24000)

    with patch("sounddevice.play", MagicMock()) as mock_play, patch("sounddevice.wait", MagicMock()):
        assert play_cached_wav(wav_file) is True
        mock_play.assert_called_once()


def test_play_raw_pcm_with_odd_bytes():
    """El motor de reproducción ElevenLabs debe soportar buffers con número impar de bytes sin lanzar ValueError."""
    from elevenlabs_tts_engine import ElevenLabsTTS

    engine = ElevenLabsTTS(api_key="test", voice_id="test")
    odd_bytes = b"\x00\x01\x00\x02\x03"  # 5 bytes (impar)
    with patch("sounddevice.play", MagicMock()) as mock_play, patch("sounddevice.wait", MagicMock()):
        assert engine._play_raw_pcm(odd_bytes) is True
        mock_play.assert_called_once()
