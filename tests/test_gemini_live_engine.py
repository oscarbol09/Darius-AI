"""Pruebas unitarias para GeminiLiveEngine (Multimodal Live WebSocket Engine).

Protocolo ECC: TDD Red-Green-Refactor.
Verifica la inicialización, configuración de voz, envío de audio, recepción,
manejo de interrupciones (barge-in), callbacks y estado offline/mock.
"""

import asyncio
import types
from unittest.mock import AsyncMock, MagicMock, patch

from src.darius_ai.core.gemini_live_engine import (
    AVAILABLE_LIVE_VOICES,
    DEFAULT_LIVE_VOICE,
    GeminiLiveEngine,
    LiveAudioConfig,
    LiveSessionState,
    get_gemini_live_engine,
)


class TestGeminiLiveConfig:
    def test_default_voices_catalog(self):
        assert "Puck" in AVAILABLE_LIVE_VOICES
        assert "Charon" in AVAILABLE_LIVE_VOICES
        assert "Kore" in AVAILABLE_LIVE_VOICES
        assert "Fenrir" in AVAILABLE_LIVE_VOICES
        assert "Aoede" in AVAILABLE_LIVE_VOICES
        assert DEFAULT_LIVE_VOICE == "Puck"

    def test_audio_config_defaults(self):
        cfg = LiveAudioConfig()
        assert cfg.sample_rate_in == 16000
        assert cfg.sample_rate_out == 24000
        assert cfg.channels == 1
        assert cfg.chunk_size == 1024


class TestGeminiLiveEngineUnit:
    def test_engine_init(self):
        engine = GeminiLiveEngine(
            api_key="synthetic_test_key_12345",
            model="gemini-2.0-flash-exp",
            voice_name="Charon",
        )
        assert engine.api_key == "synthetic_test_key_12345"
        assert engine.model == "gemini-2.0-flash-exp"
        assert engine.voice_name == "Charon"
        assert engine.state == LiveSessionState.DISCONNECTED
        assert not engine.is_active()

    def test_set_voice(self):
        engine = GeminiLiveEngine(api_key="test")
        assert engine.voice_name == DEFAULT_LIVE_VOICE
        ok = engine.set_voice("Fenrir")
        assert ok is True
        assert engine.voice_name == "Fenrir"

        # Voz inexistente
        fail = engine.set_voice("InvalidVoiceXYZ")
        assert fail is False
        assert engine.voice_name == "Fenrir"

    def test_callbacks_registration(self):
        engine = GeminiLiveEngine(api_key="test")
        audio_mock = MagicMock()
        text_mock = MagicMock()
        interrupted_mock = MagicMock()
        state_mock = MagicMock()

        engine.on_audio_received = audio_mock
        engine.on_text_received = text_mock
        engine.on_user_interrupted = interrupted_mock
        engine.on_state_changed = state_mock

        assert engine.on_audio_received is audio_mock
        assert engine.on_text_received is text_mock
        assert engine.on_user_interrupted is interrupted_mock
        assert engine.on_state_changed is state_mock

    def test_singleton_getter(self):
        engine1 = get_gemini_live_engine()
        engine2 = get_gemini_live_engine()
        assert engine1 is engine2

    def test_trigger_barge_in(self):
        engine = GeminiLiveEngine(api_key="test")
        interrupted_mock = MagicMock()
        engine.on_user_interrupted = interrupted_mock

        engine.playback_buffer.extend([b"chunk1", b"chunk2", b"chunk3"])
        assert len(engine.playback_buffer) == 3

        engine.handle_barge_in()
        assert len(engine.playback_buffer) == 0
        interrupted_mock.assert_called_once()

    def test_format_vocal_status(self):
        engine = GeminiLiveEngine(api_key="test")
        status_msg = engine.format_vocal_status()
        assert "Gemini Live" in status_msg
        assert "desconectado" in status_msg.lower() or "inactivo" in status_msg.lower()

    def test_send_audio_chunk_when_disconnected(self):
        async def _run():
            engine = GeminiLiveEngine(api_key="test")
            dummy_pcm = b"\x00\x00" * 512
            # No debe lanzar excepción si está desconectado, simplemente ignorar o registrar
            sent = await engine.send_audio_chunk_async(dummy_pcm)
            assert sent is False

        asyncio.run(_run())

    def test_mock_session_streaming(self):
        """Simula una sesión conectada con AsyncMock."""

        async def _run():
            engine = GeminiLiveEngine(api_key="mock_key")
            received_chunks = []
            received_texts = []

            engine.on_audio_received = lambda chunk: received_chunks.append(chunk)
            engine.on_text_received = lambda text: received_texts.append(text)

            mock_session = AsyncMock()
            mock_session.send_realtime_input = AsyncMock()
            mock_session.close = AsyncMock()

            engine._active_session = mock_session
            engine._state = LiveSessionState.CONNECTED

            assert engine.is_active() is True

            dummy_pcm = b"\x01\x02" * 256
            ok = await engine.send_audio_chunk_async(dummy_pcm)
            assert ok is True
            mock_session.send_realtime_input.assert_called_once()

            # Simula recepción de audio y texto
            engine._handle_incoming_audio_chunk(b"fake_output_pcm_24k")
            assert len(received_chunks) == 1
            assert received_chunks[0] == b"fake_output_pcm_24k"

            engine._handle_incoming_text_chunk("Hola señor, enlace en vivo establecido.")
            assert len(received_texts) == 1
            assert "enlace en vivo" in received_texts[0]

            await engine.stop_async()
            assert engine.state == LiveSessionState.DISCONNECTED
            mock_session.close.assert_called_once()

        asyncio.run(_run())

    def test_is_running_property(self):
        engine = GeminiLiveEngine(api_key="mock_key")
        assert hasattr(engine, "is_running")
        assert engine.is_running is False

        engine._state = LiveSessionState.CONNECTED
        assert engine.is_running is True

        engine._state = LiveSessionState.DISCONNECTED
        assert engine.is_running is False

    def test_synchronous_live_session_lifecycle(self):
        engine = GeminiLiveEngine(api_key="")
        assert callable(getattr(engine, "start_live_session", None))
        assert callable(getattr(engine, "stop_live_session", None))

        # Sin API key configurada debe fallar con mensaje claro
        ok, msg = engine.start_live_session()
        assert ok is False
        assert "api key" in msg.lower() or "configurada" in msg.lower()

        # Detener la sesión no debe arrojar excepciones
        ok_stop, msg_stop = engine.stop_live_session()
        assert ok_stop is True

    def test_start_async_receive_loop_and_text_prompt(self):
        async def _run():
            events = []
            engine = GeminiLiveEngine(
                api_key="mock_key",
                on_text_received=lambda t: events.append(("text", t)),
                on_audio_received=lambda b: events.append(("audio", b)),
                on_user_interrupted=lambda: events.append(("interrupt", True)),
            )

            part_audio = MagicMock(inline_data=MagicMock(data=b"\x01\x02"), text=None)
            part_text = MagicMock(inline_data=None, text="Entendido, señor.")
            sc1 = MagicMock(interrupted=True, model_turn=MagicMock(parts=[part_audio, part_text]))
            msg1 = MagicMock(server_content=sc1)

            class FakeSession:
                def __init__(self):
                    self.send = AsyncMock()
                    self.close = AsyncMock()

                async def receive(self):
                    yield msg1

            fake_session = FakeSession()

            class FakeCtx:
                async def __aenter__(self):
                    return fake_session

            fake_client = MagicMock()
            fake_client.aio.live.connect.return_value = FakeCtx()

            fake_genai = types.ModuleType("google.genai")
            fake_genai.Client = MagicMock(return_value=fake_client)  # type: ignore[attr-defined]
            fake_types = types.ModuleType("google.genai.types")
            fake_types.SpeechConfig = lambda **kw: kw  # type: ignore[attr-defined]
            fake_types.VoiceConfig = lambda **kw: kw  # type: ignore[attr-defined]
            fake_types.PrebuiltVoiceConfig = lambda **kw: kw  # type: ignore[attr-defined]
            fake_types.LiveConnectConfig = lambda **kw: kw  # type: ignore[attr-defined]
            fake_types.Content = lambda **kw: kw  # type: ignore[attr-defined]
            fake_types.Part = MagicMock()  # type: ignore[attr-defined]
            fake_types.Modality = types.SimpleNamespace(AUDIO="AUDIO")  # type: ignore[attr-defined]
            fake_genai.types = fake_types  # type: ignore[attr-defined]

            fake_google = types.ModuleType("google")
            fake_google.genai = fake_genai  # type: ignore[attr-defined]

            with patch.dict(
                "sys.modules",
                {"google": fake_google, "google.genai": fake_genai, "google.genai.types": fake_types},
            ):
                started = await engine.start_async()
                assert started is True
                assert engine.is_active() is True
                assert "activo" in engine.format_vocal_status().lower()

                sent_txt = await engine.send_text_prompt_async("Hola Gemini Live")
                assert sent_txt is True
                fake_session.send.assert_awaited_once()

                if engine._receive_task:
                    await engine._receive_task

                assert ("interrupt", True) in events
                assert ("audio", b"\x01\x02") in events
                assert ("text", "Entendido, señor.") in events
                await engine.stop_async()

        asyncio.run(_run())

    def test_start_async_handles_connection_failure(self):
        async def _run():
            errors = []
            engine = GeminiLiveEngine(api_key="mock_key", on_error=errors.append)
            with patch("builtins.__import__", side_effect=RuntimeError("SDK fail")):
                ok = await engine.start_async()
            assert ok is False
            assert engine.state == LiveSessionState.ERROR
            assert len(errors) == 1

        asyncio.run(_run())

    def test_w2_05_playback_buffer_cap_and_send_client_content_and_aexit(self):
        """W2-05: Verifica que playback_buffer tenga maxlen=256, send_client_content funcione y __aexit__ se invoque."""
        engine = GeminiLiveEngine(api_key="mock_key")
        assert engine.playback_buffer.maxlen == 256
        for i in range(300):
            engine._handle_incoming_audio_chunk(bytes([i % 256]))
        assert len(engine.playback_buffer) == 256

        async def _run_sdk_v2():
            engine._set_state(LiveSessionState.CONNECTED)
            fake_session = MagicMock()
            fake_session.send_client_content = AsyncMock()
            fake_session.close = AsyncMock()
            fake_ctx = MagicMock()
            fake_ctx.__aexit__ = AsyncMock()
            engine._active_session = fake_session
            engine._session_ctx = fake_ctx

            ok = await engine.send_text_prompt_async("Hola SDK 2.x", end_of_turn=True)
            assert ok is True
            fake_session.send_client_content.assert_awaited_once()

            await engine.stop_async()
            fake_ctx.__aexit__.assert_awaited_once()

        asyncio.run(_run_sdk_v2())
