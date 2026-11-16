"""
test_elevenlabs_tts.py — Tests Unitarios para el Motor ElevenLabs TTS
====================================================================
Valida la inicialización, detección de configuración, consulta de caché,
reproducción de streams PCM y diagnóstico de conexión.
"""

import urllib.error
from unittest.mock import MagicMock, patch

from src.darius_ai.audio.elevenlabs_tts_engine import (
    ElevenLabsTTS,
)
from src.darius_ai.audio.elevenlabs_tts_engine import (
    test_elevenlabs_connection as check_elevenlabs_connection,
)


def test_elevenlabs_init_defaults():
    tts = ElevenLabsTTS()
    assert tts.model_id == "eleven_multilingual_v2"
    assert tts.output_format == "pcm_24000"
    assert tts.sample_rate == 24000


def test_elevenlabs_resolve_sample_rate():
    assert ElevenLabsTTS._resolve_sample_rate("pcm_16000") == 16000
    assert ElevenLabsTTS._resolve_sample_rate("pcm_44100") == 44100
    assert ElevenLabsTTS._resolve_sample_rate("invalid_format") == 24000


def test_elevenlabs_is_configured():
    tts_empty = ElevenLabsTTS(api_key="", voice_id="")
    assert tts_empty.is_configured() is False

    tts_valid = ElevenLabsTTS(api_key="sk-test", voice_id="v123")
    assert tts_valid.is_configured() is True


def test_elevenlabs_speak_empty_text():
    tts = ElevenLabsTTS(api_key="sk-test", voice_id="v123")
    assert tts.speak("") is False
    assert tts.speak("   ") is False


def test_elevenlabs_speak_from_cache():
    tts = ElevenLabsTTS(api_key="sk-test", voice_id="v123", cache_enabled=True)
    with (
        patch("src.darius_ai.audio.elevenlabs_tts_engine.is_cached", return_value=True),
        patch("src.darius_ai.audio.elevenlabs_tts_engine.get_cached_wav_path") as mock_path,
        patch("src.darius_ai.audio.elevenlabs_tts_engine.play_cached_wav", return_value=True) as mock_play,
    ):
        mock_path.return_value = MagicMock(name="cached.wav")
        res = tts.speak("Hola mundo")
        assert res is True
        mock_play.assert_called_once()


def test_elevenlabs_speak_not_configured_no_cache():
    tts = ElevenLabsTTS(api_key="", voice_id="", cache_enabled=False)
    assert tts.speak("Texto no en cache") is False


def test_elevenlabs_play_raw_pcm():
    tts = ElevenLabsTTS(api_key="sk-test", voice_id="v123")
    assert tts._play_raw_pcm(b"") is False

    # Datos PCM válidos (16-bit little-endian)
    dummy_pcm = b"\x00\x00\x10\x00\x20\x00\x00\x00"
    with patch("sounddevice.play") as mock_sd_play, patch("sounddevice.wait") as mock_sd_wait:
        res = tts._play_raw_pcm(dummy_pcm)
        assert res is True
        mock_sd_play.assert_called_once()
        mock_sd_wait.assert_called_once()


def test_connection_diagnostics_validation():
    # Sin API key
    ok, _, msg = check_elevenlabs_connection("", "voice_1")
    assert ok is False
    assert "API Key" in msg

    # Sin Voice ID
    ok, _, msg = check_elevenlabs_connection("key_1", "")
    assert ok is False
    assert "Voice ID" in msg


def test_connection_diagnostics_success():
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"name": "Adam"}'
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        ok, latency, msg = check_elevenlabs_connection("valid_key", "valid_voice")
        assert ok is True
        assert latency >= 0
        assert "Adam" in msg


def test_connection_diagnostics_http_401():
    http_err = urllib.error.HTTPError("https://api.elevenlabs.io", 401, "Unauthorized", {}, None)
    with patch("urllib.request.urlopen", side_effect=http_err):
        ok, _, msg = check_elevenlabs_connection("bad_key", "valid_voice")
        assert ok is False
        assert "401" in msg

    http_404 = urllib.error.HTTPError("https://api.elevenlabs.io", 404, "Not Found", {}, None)
    with patch("urllib.request.urlopen", side_effect=http_404):
        assert "404" in check_elevenlabs_connection("k", "missing")[2]

    http_500 = urllib.error.HTTPError("https://api.elevenlabs.io", 500, "Server Error", {}, None)
    with patch("urllib.request.urlopen", side_effect=http_500):
        assert "500" in check_elevenlabs_connection("k", "v")[2]

    with patch("urllib.request.urlopen", side_effect=OSError("network down")):
        assert "network down" in check_elevenlabs_connection("k", "v")[2]


def test_elevenlabs_speak_api_cache_save_and_rest_fallback(monkeypatch, tmp_path):
    import io
    import sys
    import types

    monkeypatch.setenv("ELEVENLABS_PCM_SAMPLE_RATE", "16000")
    assert ElevenLabsTTS._resolve_sample_rate("pcm_24000") == 16000
    monkeypatch.delenv("ELEVENLABS_PCM_SAMPLE_RATE")
    assert ElevenLabsTTS._resolve_sample_rate("pcm_bad") == 24000

    tts = ElevenLabsTTS(api_key="sk-test", voice_id="v123", cache_enabled=True)
    wav_file = tmp_path / "voice.wav"

    with (
        patch("src.darius_ai.audio.elevenlabs_tts_engine.is_cached", return_value=True),
        patch("src.darius_ai.audio.elevenlabs_tts_engine.get_cached_wav_path", return_value=wav_file),
        patch("src.darius_ai.audio.elevenlabs_tts_engine.play_cached_wav", return_value=False),
        patch("src.darius_ai.audio.elevenlabs_tts_engine.save_pcm_to_wav") as mock_save,
        patch.object(tts, "_fetch_pcm", return_value=b"\x01\x00\x02\x00"),
        patch.object(tts, "_play_raw_pcm", return_value=True),
    ):
        assert tts.speak("Hola nuevo") is True
        mock_save.assert_called_once_with(wav_file, b"\x01\x00\x02\x00", 24000)

    with patch.object(tts, "_fetch_pcm", return_value=None):
        assert tts.speak("Fallo API") is False

    # _fetch_pcm SDK success + SDK error -> REST fallback
    fake_client = MagicMock()
    fake_client.text_to_speech.convert.return_value = [b"\x01", b"\x02"]
    fake_el_mod = types.ModuleType("elevenlabs")
    fake_el_client_mod = types.ModuleType("elevenlabs.client")
    fake_el_client_mod.ElevenLabs = MagicMock(return_value=fake_client)
    monkeypatch.setitem(sys.modules, "elevenlabs", fake_el_mod)
    monkeypatch.setitem(sys.modules, "elevenlabs.client", fake_el_client_mod)

    assert tts._fetch_pcm("hola") == b"\x01\x02"

    fake_client.text_to_speech.convert.side_effect = RuntimeError("sdk down")
    rest_resp = MagicMock()
    rest_resp.read.return_value = b"\x03\x04"
    rest_resp.__enter__.return_value = rest_resp
    with patch("urllib.request.urlopen", return_value=rest_resp):
        assert tts._fetch_pcm("hola") == b"\x03\x04"

    # _fetch_pcm_rest HTTP error and generic error
    http_err = urllib.error.HTTPError("https://api.elevenlabs.io", 429, "Rate Limit", {}, io.BytesIO(b"quota"))
    with patch("urllib.request.urlopen", side_effect=http_err):
        assert tts._fetch_pcm_rest("hola") is None

    with patch("urllib.request.urlopen", side_effect=RuntimeError("timeout")):
        assert tts._fetch_pcm_rest("hola") is None

    # _play_raw_pcm odd-byte trim and exception branch
    with patch("sounddevice.play") as mock_play, patch("sounddevice.wait"):
        assert tts._play_raw_pcm(b"\x01\x00\x02") is True
        assert len(mock_play.call_args[0][0]) == 1
        assert tts._play_raw_pcm(b"\x01") is False

    with patch("sounddevice.play", side_effect=RuntimeError("audio busy")):
        assert tts._play_raw_pcm(b"\x01\x00") is False
