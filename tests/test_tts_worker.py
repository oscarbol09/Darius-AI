"""
test_tts_worker.py — Tests Unitarios para el Worker Multi-Engine de TTS
======================================================================
Valida la cola asíncrona, encolado, cancelación, flags de estado (is_speaking)
y degradación elegante entre motores (ElevenLabs -> Edge -> SAPI).
"""

from unittest.mock import MagicMock, patch

from src.darius_ai.audio.tts_worker import TTSWorker


def test_tts_worker_init():
    worker = TTSWorker()
    assert worker._queue.empty()
    assert not worker.is_speaking.is_set()


def test_tts_worker_queue_operations():
    worker = TTSWorker()
    worker.speak("Mensaje 1")
    worker.speak("Mensaje 2")
    assert not worker._queue.empty()

    worker.clear_queue()
    assert worker._queue.empty()

    worker.stop()
    # Debe haber recibido None como señal de terminación
    assert worker._queue.get() is None


def test_speak_elevenlabs_delegation():
    worker = TTSWorker()
    with patch("src.darius_ai.audio.elevenlabs_tts_engine.ElevenLabsTTS.speak", return_value=True) as mock_speak:
        res = worker._speak_elevenlabs("Texto de prueba")
        assert res is True
        mock_speak.assert_called_once_with("Texto de prueba")


def test_speak_elevenlabs_exception_handled():
    worker = TTSWorker()
    with patch("src.darius_ai.audio.elevenlabs_tts_engine.ElevenLabsTTS.speak", side_effect=RuntimeError("API error")):
        res = worker._speak_elevenlabs("Texto")
        assert res is False


def test_speak_edge_tts_delegation():
    worker = TTSWorker()
    with patch("src.darius_ai.audio.edge_tts_engine.EdgeTTS.speak", return_value=True) as mock_speak:
        res = worker._speak_edge_tts("Texto Edge")
        assert res is True
        mock_speak.assert_called_once_with("Texto Edge")


def test_speak_edge_tts_exception_handled():
    worker = TTSWorker()
    with patch("src.darius_ai.audio.edge_tts_engine.EdgeTTS.speak", side_effect=RuntimeError("Edge error")):
        res = worker._speak_edge_tts("Texto")
        assert res is False


def test_worker_loop_execution_with_sapi_mock():
    worker = TTSWorker()

    mock_sapi = MagicMock()
    mock_win32com = MagicMock()
    mock_win32com.client.Dispatch.return_value = mock_sapi
    import threading

    from src.darius_ai.core.config_loader import cfg

    spoken = threading.Event()
    mock_sapi.Speak.side_effect = lambda *_a, **_kw: spoken.set()

    with (
        patch("pythoncom.CoInitialize", create=True),
        patch("pythoncom.CoUninitialize", create=True),
        patch.dict(
            "sys.modules",
            {"win32api": MagicMock(), "win32com": mock_win32com, "win32com.client": mock_win32com.client},
        ),
        patch.object(type(cfg), "tts_engine", new=property(lambda self: "sapi")),
        patch.object(type(cfg), "speaking_tail_secs", new=property(lambda self: 0.0)),
    ):
        worker.start()
        worker.speak("Hola SAPI")
        assert spoken.wait(timeout=2.0) is True
        worker.wait_until_done(timeout=1.0)
        worker.stop()

    mock_sapi.Speak.assert_called_with("Hola SAPI")
