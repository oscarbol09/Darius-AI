"""
stt_engine.py — Speech-to-Text modular para DARIUS AI
======================================================
Blueprint para migración desde speech_recognition (Google STT online)
a Vosk (offline, open-source, sin conexión a internet).

Arquitectura:
  - Interfaz unificada: listen() -> str
  - Backend seleccionable (Vosk / Google / Whisper)
  - El backend actual (Google via speech_recognition) se mantiene como default
  - Vosk y Whisper se agregan como backends alternativos

Uso futuro:
    from stt_engine import STTEngine
    stt = STTEngine(backend="vosk", model_path="models/vosk-small")
    text = stt.listen()

Dependencias opcionales:
  - Vosk:     pip install vosk
  - Whisper:  pip install openai-whisper
  - Google:   ya incluido via speech_recognition
"""

import logging
import queue

log = logging.getLogger("DARIUS.STT")


class STTEngine:
    """
    Motor de reconocimiento de voz intercambiable.

    Atributos:
        backend (str): "google" | "vosk" | "whisper"
    """

    def __init__(self, backend: str = "google", model_path: str | None = None):
        self.backend = backend
        self.model_path = model_path
        self._audio_queue: queue.Queue = queue.Queue()
        self._running = False

    def listen(self, timeout: float = 5.0) -> str | None:
        """
        Escucha y transcribe audio. Retorna texto o None si no se detectó habla.
        """
        if self.backend == "vosk":
            return self._listen_vosk(timeout)
        elif self.backend == "whisper":
            return self._listen_whisper(timeout)
        else:
            return self._listen_google(timeout)

    def _listen_google(self, timeout: float) -> str | None:
        """Backend actual: Google Speech Recognition via speech_recognition."""
        import speech_recognition as sr
        r = sr.Recognizer()
        try:
            with sr.Microphone() as source:
                r.adjust_for_ambient_noise(source, duration=0.5)
                audio = r.listen(source, timeout=timeout, phrase_time_limit=10)
            return r.recognize_google(audio, language="es-ES")
        except sr.WaitTimeoutError:
            return None
        except sr.UnknownValueError:
            return None
        except Exception as e:
            log.warning(f"Error en Google STT: {e}")
            return None

    def _listen_vosk(self, timeout: float) -> str | None:
        """
        Backend Vosk (offline).

        Pendiente:
          - Descargar modelo de https://alphacephei.com/vosk/models
          - Extraer en models/vosk-small
          - Probar con sample de audio
        """
        raise NotImplementedError(
            "Vosk backend no implementado. "
            "Requiere: pip install vosk y descargar modelo de alphacephei.com"
        )

    def _listen_whisper(self, timeout: float) -> str | None:
        """
        Backend Whisper (openai).

        Pendiente:
          - Evaluar rendimiento en CPU sin GPU
          - Probar modelos base/small vs large
        """
        raise NotImplementedError(
            "Whisper backend no implementado. "
            "Requiere: pip install openai-whisper (y ffmpeg en PATH)"
        )
