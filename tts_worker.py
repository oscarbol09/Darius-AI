"""
tts_worker.py — Motor de Text-to-Speech Multi-Engine con Worker Desacoplado
==========================================================================
Soporta tres motores de síntesis con degradación elegante:
  1. ElevenLabs (alta fidelidad con caché local de audio)
  2. Edge-TTS (voces neurales de Microsoft)
  3. SAPI5 (Windows nativo sin latencia y cero dependencias externas)
"""

import contextlib
import logging
import os
import queue
import threading
import time

from config_loader import cfg

log = logging.getLogger("DARIUS.TTS")


class TTSWorker:
    """
    Worker de TTS que corre en un hilo dedicado con soporte multi-motor
    y degradación automática a SAPI nativo en caso de error.
    """

    def __init__(self, voice_token=None):
        self._queue: queue.Queue = queue.Queue()
        self.is_speaking = threading.Event()
        self._voice_token = voice_token
        self._thread: threading.Thread | None = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True, name="tts-worker")
        self._thread.start()

    def _run(self):
        import pythoncom

        pythoncom.CoInitialize()
        import win32com.client

        sapi_speaker = win32com.client.Dispatch("SAPI.SpVoice")
        if self._voice_token:
            sapi_speaker.Voice = self._voice_token
        sapi_speaker.Rate = cfg.tts_rate
        sapi_speaker.Volume = cfg.tts_volume

        while True:
            text = self._queue.get()
            if text is None:
                break
            try:
                self.is_speaking.set()
                engine = cfg.tts_engine.lower()

                # 1. ElevenLabs con caché local
                if engine == "elevenlabs":
                    played = self._speak_elevenlabs(text)
                    if not played:
                        log.info("[TTS] Fallback a SAPI nativo tras fallo de ElevenLabs.")
                        sapi_speaker.Speak(text)

                # 2. Edge-TTS
                elif engine in ("edge", "edge_tts", "edgetts"):
                    played = self._speak_edge_tts(text)
                    if not played:
                        log.info("[TTS] Fallback a SAPI nativo tras fallo de Edge-TTS.")
                        sapi_speaker.Speak(text)

                # 3. SAPI5 por defecto
                else:
                    sapi_speaker.Speak(text)

            except Exception as e:
                log.error(f"Error en síntesis TTS: {e}")
                with contextlib.suppress(Exception):  # noqa: F821
                    sapi_speaker.Speak(text)
            finally:
                self.is_speaking.clear()
                time.sleep(cfg.speaking_tail_secs)
                self._queue.task_done()

        pythoncom.CoUninitialize()

    def _speak_elevenlabs(self, text: str) -> bool:
        """Intenta sintetizar con ElevenLabs y caché en disco."""
        try:
            from elevenlabs_tts_engine import ElevenLabsTTS

            api_key = cfg.elevenlabs_api_key or os.environ.get("ELEVENLABS_API_KEY", "")
            voice_id = cfg.elevenlabs_voice_id or os.environ.get("ELEVENLABS_VOICE_ID", "")
            tts = ElevenLabsTTS(
                api_key=api_key,
                voice_id=voice_id,
                model_id=cfg.elevenlabs_model_id,
                output_format=cfg.elevenlabs_output_format,
                cache_enabled=cfg.elevenlabs_cache_enabled,
            )
            return tts.speak(text)
        except Exception as exc:
            log.warning(f"Error en motor ElevenLabs: {exc}")
            return False

    def _speak_edge_tts(self, text: str) -> bool:
        """Intenta sintetizar con Edge-TTS."""
        try:
            from edge_tts_engine import EdgeTTS

            tts = EdgeTTS()
            tts.speak(text)
            return True
        except Exception as exc:
            log.warning(f"Error en motor Edge-TTS: {exc}")
            return False

    def speak(self, text: str):
        """Envía texto al worker. No bloquea."""
        self._queue.put(text)

    def clear_queue(self):
        """Vacía la cola de mensajes pendientes de síntesis para cancelación inmediata."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except Exception:
                break

    def stop(self):
        """Detiene el worker enviando señal None."""
        self.clear_queue()
        self._queue.put(None)

    def wait_until_done(self, timeout: float = 5.0):
        """Espera hasta que la cola esté vacía o se cumpla el timeout."""
        deadline = time.time() + timeout
        while not self._queue.empty() and time.time() < deadline:
            time.sleep(0.1)

