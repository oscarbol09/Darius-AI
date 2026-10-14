"""Módulo GeminiLiveEngine — Cliente bidireccional en tiempo real (Multimodal Live API).

Permite streaming de audio full-duplex de ultra-baja latencia (<300-500ms)
sobre WebSockets utilizando el SDK oficial `google-genai`.
Soporta detección de interrupciones naturales (barge-in), cancelación de buffer
de audio al hablar el usuario y selección de voces neuronales oficiales.

Arquitectura:
  Micrófono (PCM 16kHz) -> WebSocket -> Gemini Live (PCM 24kHz) -> Altavoces
"""

import asyncio
import collections
import contextlib
import enum
import logging
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from src.darius_ai.core.config_loader import cfg

log = logging.getLogger("DARIUS.GeminiLive")

AVAILABLE_LIVE_VOICES: list[str] = ["Puck", "Charon", "Kore", "Fenrir", "Aoede"]
DEFAULT_LIVE_VOICE: str = "Puck"
DEFAULT_LIVE_MODEL: str = "gemini-2.0-flash-exp"


class LiveSessionState(enum.StrEnum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    LISTENING = "LISTENING"
    SPEAKING = "SPEAKING"
    ERROR = "ERROR"


@dataclass
class LiveAudioConfig:
    sample_rate_in: int = 16000
    sample_rate_out: int = 24000
    channels: int = 1
    chunk_size: int = 1024


@dataclass
class GeminiLiveEngine:
    """Motor de comunicación de voz en vivo y bidireccional con Gemini Live."""

    api_key: str = ""
    model: str = DEFAULT_LIVE_MODEL
    voice_name: str = DEFAULT_LIVE_VOICE
    audio_config: LiveAudioConfig = field(default_factory=LiveAudioConfig)

    on_audio_received: Callable[[bytes], None] | None = None
    on_text_received: Callable[[str], None] | None = None
    on_user_interrupted: Callable[[], None] | None = None
    on_state_changed: Callable[[LiveSessionState], None] | None = None
    on_error: Callable[[str], None] | None = None

    playback_buffer: collections.deque = field(default_factory=collections.deque)
    _state: LiveSessionState = LiveSessionState.DISCONNECTED
    _active_session: Any = None
    _receive_task: asyncio.Task | None = None
    _loop: asyncio.AbstractEventLoop | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self):
        if not self.api_key:
            self.api_key = (
                cfg.llm_gemini_api_key
                or cfg.get("gemini", "api_key", default="")
                or os.getenv("GEMINI_API_KEY", "")
            )

    @property
    def state(self) -> LiveSessionState:
        return self._state

    def is_active(self) -> bool:
        return self._state in (
            LiveSessionState.CONNECTED,
            LiveSessionState.LISTENING,
            LiveSessionState.SPEAKING,
        )

    def set_voice(self, voice: str) -> bool:
        """Configura la voz neuronal activa de Gemini Live."""
        if voice in AVAILABLE_LIVE_VOICES:
            self.voice_name = voice
            log.info(f"[GeminiLive] Voz configurada a '{voice}'")
            return True
        log.warning(f"[GeminiLive] Voz '{voice}' desconocida. Disponibles: {AVAILABLE_LIVE_VOICES}")
        return False

    def handle_barge_in(self) -> None:
        """Cancela el buffer de audio de salida de inmediato cuando el usuario interrumpe."""
        with self._lock:
            discarded = len(self.playback_buffer)
            self.playback_buffer.clear()
            if discarded > 0:
                log.info(f"[GeminiLive] Barge-in detectado: {discarded} chunks de audio descartados.")
        if self.on_user_interrupted:
            try:
                self.on_user_interrupted()
            except Exception as exc:
                log.warning(f"[GeminiLive] Error en callback on_user_interrupted: {exc}")

    def _set_state(self, new_state: LiveSessionState) -> None:
        self._state = new_state
        if self.on_state_changed:
            try:
                self.on_state_changed(new_state)
            except Exception as exc:
                log.warning(f"[GeminiLive] Error en callback on_state_changed: {exc}")

    def _handle_incoming_audio_chunk(self, chunk: bytes) -> None:
        """Procesa un chunk de audio entrante (PCM 24kHz) recibido desde el WebSocket."""
        with self._lock:
            self.playback_buffer.append(chunk)
        if self.on_audio_received:
            try:
                self.on_audio_received(chunk)
            except Exception as exc:
                log.warning(f"[GeminiLive] Error en callback on_audio_received: {exc}")

    def _handle_incoming_text_chunk(self, text: str) -> None:
        """Procesa la transcripción parcial o completa emitida por Gemini."""
        if self.on_text_received:
            try:
                self.on_text_received(text)
            except Exception as exc:
                log.warning(f"[GeminiLive] Error en callback on_text_received: {exc}")

    async def send_audio_chunk_async(self, pcm_data: bytes) -> bool:
        """Envía un bloque de audio crudo (PCM 16kHz mono) al WebSocket de Gemini Live."""
        if not self.is_active() or self._active_session is None:
            return False

        try:
            # Enviamos el chunk a través de send_realtime_input
            mime = f"audio/pcm;rate={self.audio_config.sample_rate_in}"
            if hasattr(self._active_session, "send_realtime_input"):
                await self._active_session.send_realtime_input(media={"mime_type": mime, "data": pcm_data})
                return True
        except Exception as exc:
            log.warning(f"[GeminiLive] Error enviando chunk de audio: {exc}")
            if self.on_error:
                self.on_error(str(exc))
        return False

    async def send_text_prompt_async(self, text: str, end_of_turn: bool = True) -> bool:
        """Envía un prompt de texto en la sesión en vivo."""
        if not self.is_active() or self._active_session is None:
            return False
        try:
            if hasattr(self._active_session, "send"):
                await self._active_session.send(text=text, end_of_turn=end_of_turn)
                return True
        except Exception as exc:
            log.warning(f"[GeminiLive] Error enviando prompt de texto: {exc}")
            if self.on_error:
                self.on_error(str(exc))
        return False

    async def start_async(self) -> bool:
        """Inicia la conexión bidireccional WebSocket con Gemini Live."""
        if self.is_active():
            return True

        self._set_state(LiveSessionState.CONNECTING)
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            speech_config = types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.voice_name)
                )
            )
            connect_config = types.LiveConnectConfig(
                response_modalities=["AUDIO"],
                speech_config=speech_config,
                system_instruction=types.Content(
                    parts=[
                        types.Part.from_text(
                            text=(
                                "Eres Darius, un copiloto y mayordomo de inteligencia artificial de alta precisión. "
                                "Responde de forma concisa, educada y en español, dirigiéndote al usuario como 'señor'."
                            )
                        )
                    ]
                ),
            )

            # Establecer sesión mediante el context manager asíncrono
            session_ctx = client.aio.live.connect(model=self.model, config=connect_config)
            self._active_session = await session_ctx.__aenter__()
            self._set_state(LiveSessionState.CONNECTED)
            log.info(f"[GeminiLive] Conectado exitosamente en vivo con modelo '{self.model}' (Voz: {self.voice_name})")

            # Iniciar bucle de recepción en background
            self._receive_task = asyncio.create_task(self._receive_loop())
            return True
        except Exception as exc:
            self._set_state(LiveSessionState.ERROR)
            err_msg = f"Fallo al conectar con Gemini Live: {exc}"
            log.error(f"[GeminiLive] {err_msg}")
            if self.on_error:
                self.on_error(err_msg)
            return False

    async def _receive_loop(self) -> None:
        """Bucle continuo para consumir las respuestas generadas por Gemini Live."""
        try:
            session = self._active_session
            if not session:
                return

            async for response in session.receive():
                server_content = getattr(response, "server_content", None)
                if not server_content:
                    continue

                # Manejo de interrupción del servidor (barge-in reportado por Gemini)
                if getattr(server_content, "interrupted", False):
                    self.handle_barge_in()

                model_turn = getattr(server_content, "model_turn", None)
                if model_turn:
                    for part in getattr(model_turn, "parts", []):
                        # Chunk de audio devuelto (PCM 24kHz)
                        inline_data = getattr(part, "inline_data", None)
                        if inline_data and getattr(inline_data, "data", None):
                            self._handle_incoming_audio_chunk(inline_data.data)

                        # Texto o transcripción
                        text_val = getattr(part, "text", None)
                        if text_val:
                            self._handle_incoming_text_chunk(text_val)

        except asyncio.CancelledError:
            pass
        except Exception as exc:
            log.warning(f"[GeminiLive] Excepción en receive_loop: {exc}")
            self._set_state(LiveSessionState.ERROR)
            if self.on_error:
                self.on_error(str(exc))
        finally:
            self._set_state(LiveSessionState.DISCONNECTED)

    async def stop_async(self) -> None:
        """Detiene la sesión y limpia recursos asíncronos."""
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._receive_task

        if self._active_session:
            try:
                if hasattr(self._active_session, "close"):
                    await self._active_session.close()
            except Exception as exc:
                log.warning(f"[GeminiLive] Error al cerrar sesión: {exc}")
            self._active_session = None

        with self._lock:
            self.playback_buffer.clear()
        self._set_state(LiveSessionState.DISCONNECTED)
        log.info("[GeminiLive] Sesión en vivo desconectada.")

    def format_vocal_status(self) -> str:
        """Genera un reporte conciso del estado de Gemini Live para el usuario."""
        if self.is_active():
            return (
                f"Enlace Gemini Live activo en ultra-baja latencia. "
                f"Modelo: {self.model}, voz neuronal: {self.voice_name}."
            )
        return "El canal de voz Gemini Live se encuentra inactivo y desconectado."


_GLOBAL_LIVE_ENGINE: GeminiLiveEngine | None = None
_ENGINE_LOCK = threading.Lock()


def get_gemini_live_engine() -> GeminiLiveEngine:
    """Obtiene la instancia singleton de GeminiLiveEngine."""
    global _GLOBAL_LIVE_ENGINE
    if _GLOBAL_LIVE_ENGINE is None:
        with _ENGINE_LOCK:
            if _GLOBAL_LIVE_ENGINE is None:
                _GLOBAL_LIVE_ENGINE = GeminiLiveEngine()
    return _GLOBAL_LIVE_ENGINE
