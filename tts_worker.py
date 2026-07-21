"""
tts_worker.py — Motor de Text-to-Speech (SAPI) con worker en hilo propio
========================================================================
Extraído de main.py para separar responsabilidades.
Usa SAPI5 de Windows (win32com.client).
"""

import queue
import threading
import time
import logging

from config_loader import cfg

log = logging.getLogger("DARIUS.TTS")


class TTSWorker:
    """Worker de TTS que corre en un hilo dedicado con su propia
    inicialización COM (pythoncom.CoInitialize)."""

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
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        if self._voice_token:
            speaker.Voice = self._voice_token
        speaker.Rate = cfg.TTS_RATE
        speaker.Volume = cfg.TTS_VOLUME
        while True:
            text = self._queue.get()
            if text is None:
                break
            try:
                self.is_speaking.set()
                speaker.Speak(text)
            except Exception as e:
                log.error(f"Error en TTS: {e}")
            finally:
                self.is_speaking.clear()
                time.sleep(cfg.SPEAKING_TAIL_SECS)
                self._queue.task_done()
        pythoncom.CoUninitialize()

    def speak(self, text: str):
        """Envía texto al worker. No bloquea."""
        self._queue.put(text)

    def stop(self):
        """Detiene el worker enviando señal None."""
        self._queue.put(None)

    def wait_until_done(self, timeout: float = 5.0):
        """Espera hasta que la cola esté vacía o se cumpla el timeout."""
        deadline = time.time() + timeout
        while not self._queue.empty() and time.time() < deadline:
            time.sleep(0.1)
