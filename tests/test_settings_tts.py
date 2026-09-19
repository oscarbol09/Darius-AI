"""
test_settings_tts.py — Pruebas Unitarias para Configuración de TTS y ElevenLabs en GUI
======================================================================================
Valida la persistencia, tipado y resolución de ajustes de TTS y ElevenLabs en config_loader.
"""

from pathlib import Path

from byok_settings import (
    ELEVENLABS_MODEL_PRESETS,
    ELEVENLABS_VOICE_PRESETS,
    TTS_ENGINES,
)
from config_loader import cfg, get_app_resource_dir, get_user_data_dir


def test_user_data_dir_and_resource_dir():
    """Valida la resolución de directorios de usuario y recursos."""
    data_dir = get_user_data_dir()
    res_dir = get_app_resource_dir()
    assert isinstance(data_dir, Path)
    assert isinstance(res_dir, Path)
    assert data_dir.exists()


def test_tts_engines_presets():
    """Verifica que los motores y presets de TTS contengan los elementos requeridos."""
    assert "sapi" in TTS_ENGINES
    assert "edge" in TTS_ENGINES
    assert "elevenlabs" in TTS_ENGINES

    assert len(ELEVENLABS_VOICE_PRESETS) >= 3
    assert "eleven_multilingual_v2" in ELEVENLABS_MODEL_PRESETS


def test_save_tts_config(tmp_path: Path, monkeypatch):
    """Verifica que cfg.set actualice y persista las propiedades de TTS y ElevenLabs."""
    fake_config = tmp_path / "config.json"
    fake_config.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("config_loader._CONFIG_FILE", fake_config)

    # Actualizar motor
    cfg.set("elevenlabs", "tts", "engine")
    assert cfg.tts_engine == "elevenlabs"

    # Actualizar ElevenLabs params
    cfg.set("test-api-key-123", "elevenlabs", "api_key")
    cfg.set("test-voice-id", "elevenlabs", "voice_id")
    cfg.set("eleven_turbo_v2_5", "elevenlabs", "model_id")
    cfg.set(True, "elevenlabs", "cache_enabled")

    assert cfg.elevenlabs_api_key == "test-api-key-123"
    assert cfg.elevenlabs_voice_id == "test-voice-id"
    assert cfg.elevenlabs_model_id == "eleven_turbo_v2_5"
    assert cfg.elevenlabs_cache_enabled is True

    # Verificar que el archivo en disco contenga los valores
    content = fake_config.read_text(encoding="utf-8")
    assert "test-api-key-123" in content
    assert "eleven_turbo_v2_5" in content


def test_frozen_user_data_dir(monkeypatch, tmp_path: Path):
    """Verifica que en modo frozen se use %APPDATA%."""
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))

    data_dir = get_user_data_dir()
    assert data_dir == tmp_path / "DariusAI"
    assert data_dir.exists()
