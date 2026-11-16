"""Tests unitarios herméticos para STTEngine (Speech-to-Text modular)."""

from __future__ import annotations

import types
from unittest.mock import MagicMock, patch

import pytest

from src.darius_ai.audio.stt_engine import STTEngine


@pytest.mark.parametrize(
    "backend, method_name",
    [
        ("vosk", "_listen_vosk"),
        ("whisper", "_listen_whisper"),
    ],
    ids=["vosk_not_implemented", "whisper_not_implemented"],
)
def test_stt_unimplemented_backends_raise_not_implemented(backend: str, method_name: str):
    stt = STTEngine(backend=backend, model_path="models/test")
    assert stt.model_path == "models/test"
    with pytest.raises(NotImplementedError):
        stt.listen(timeout=1.0)


def test_stt_google_backend_success():
    fake_sr = types.ModuleType("speech_recognition")

    class WaitTimeoutError(Exception):
        pass

    class UnknownValueError(Exception):
        pass

    fake_sr.WaitTimeoutError = WaitTimeoutError  # type: ignore[attr-defined]
    fake_sr.UnknownValueError = UnknownValueError  # type: ignore[attr-defined]

    mock_recognizer = MagicMock()
    mock_recognizer.listen.return_value = b"fake-audio"
    mock_recognizer.recognize_google.return_value = "darius que hora es"
    fake_sr.Recognizer = MagicMock(return_value=mock_recognizer)  # type: ignore[attr-defined]

    mock_mic = MagicMock()
    mock_mic.__enter__.return_value = MagicMock()
    fake_sr.Microphone = MagicMock(return_value=mock_mic)  # type: ignore[attr-defined]

    stt = STTEngine(backend="google")
    with patch.dict("sys.modules", {"speech_recognition": fake_sr}):
        result = stt.listen(timeout=2.0)

    assert result == "darius que hora es"
    mock_recognizer.adjust_for_ambient_noise.assert_called_once()
    mock_recognizer.recognize_google.assert_called_once_with(b"fake-audio", language="es-ES")


@pytest.mark.parametrize(
    "exc_name",
    ["WaitTimeoutError", "UnknownValueError", "RuntimeError"],
    ids=["timeout_returns_none", "unknown_speech_returns_none", "unexpected_error_returns_none"],
)
def test_stt_google_backend_handles_errors_gracefully(exc_name: str):
    fake_sr = types.ModuleType("speech_recognition")

    class WaitTimeoutError(Exception):
        pass

    class UnknownValueError(Exception):
        pass

    fake_sr.WaitTimeoutError = WaitTimeoutError  # type: ignore[attr-defined]
    fake_sr.UnknownValueError = UnknownValueError  # type: ignore[attr-defined]

    exc_map = {
        "WaitTimeoutError": WaitTimeoutError("timeout"),
        "UnknownValueError": UnknownValueError("unrecognized"),
        "RuntimeError": RuntimeError("mic failure"),
    }

    mock_recognizer = MagicMock()
    mock_recognizer.listen.side_effect = exc_map[exc_name]
    fake_sr.Recognizer = MagicMock(return_value=mock_recognizer)  # type: ignore[attr-defined]

    mock_mic = MagicMock()
    mock_mic.__enter__.return_value = MagicMock()
    fake_sr.Microphone = MagicMock(return_value=mock_mic)  # type: ignore[attr-defined]

    stt = STTEngine(backend="google")
    with patch.dict("sys.modules", {"speech_recognition": fake_sr}):
        assert stt.listen(timeout=1.0) is None
