"""
test_edge_tts.py — Tests Unitarios para el Motor Microsoft Edge TTS
===================================================================
Valida la inicialización, wrapper síncrono, reproducción limpia sin playsound
y manejo robusto de errores / dependencias ausentes.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.darius_ai.audio.edge_tts_engine import EdgeTTS, _play_audio_file


def test_edge_tts_init_defaults():
    tts = EdgeTTS()
    assert tts.voice == "es-MX-DaliaNeural"
    assert tts.rate == 50
    assert tts.volume == 100
    assert "es-MX-DaliaNeural" in EdgeTTS.VOICES


def test_edge_tts_init_custom():
    tts = EdgeTTS(voice="es-ES-AlvaroNeural", rate=60, volume=80)
    assert tts.voice == "es-ES-AlvaroNeural"
    assert tts.rate == 60
    assert tts.volume == 80


def test_play_audio_file_win32_success():
    with patch("sys.platform", "win32"), patch("ctypes.windll.winmm.mciSendStringW", return_value=0) as mock_mci:
        res = _play_audio_file("C:/fake/audio.mp3")
        assert res is True
        assert mock_mci.call_count >= 3  # open, play wait, close


def test_play_audio_file_fallback_failure():
    with (
        patch("sys.platform", "win32"),
        patch("ctypes.windll.winmm.mciSendStringW", side_effect=RuntimeError("MCI unavailable")),
    ):
        res = _play_audio_file("C:/fake/audio.mp3")
        assert res is False


def test_play_audio_file_sounddevice_fallback_success():
    import types

    fake_sd = types.ModuleType("sounddevice")
    fake_sd.play = MagicMock()  # type: ignore[attr-defined]
    fake_sd.wait = MagicMock()  # type: ignore[attr-defined]
    fake_sf = types.ModuleType("soundfile")
    fake_sf.read = MagicMock(return_value=([0.0, 0.1], 24000))  # type: ignore[attr-defined]

    with (
        patch("sys.platform", "linux"),
        patch.dict("sys.modules", {"sounddevice": fake_sd, "soundfile": fake_sf}),
    ):
        assert _play_audio_file("C:/fake/audio.mp3") is True
        fake_sd.play.assert_called_once()
        fake_sd.wait.assert_called_once()


@pytest.mark.asyncio
async def test_speak_async_mocked():
    tts = EdgeTTS()
    mock_communicate = MagicMock()
    mock_communicate.save = AsyncMock(return_value=None)

    with (
        patch("edge_tts.Communicate", return_value=mock_communicate),
        patch("src.darius_ai.audio.edge_tts_engine._play_audio_file", return_value=True) as mock_play,
    ):
        res = await tts._speak_async("Hola mundo")
        assert res is True
        mock_communicate.save.assert_called_once()
        mock_play.assert_called_once()


def test_speak_sync_wrapper():
    tts = EdgeTTS()
    with patch.object(tts, "_speak_async", new_callable=AsyncMock) as mock_speak_async:
        mock_speak_async.return_value = True
        res = tts.speak("Texto de prueba")
        assert res is True
        mock_speak_async.assert_called_once_with("Texto de prueba")
