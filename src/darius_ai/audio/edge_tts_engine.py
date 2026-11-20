"""
edge_tts_engine.py — Text-to-Speech con Microsoft Edge TTS para DARIUS AI
==========================================================================
Blueprint para migración desde SAPI (win32com) a edge-tts.

Ventajas de edge-tts:
  - Voces más naturales (neurales de Microsoft)
  - Multi-idioma sin instalar paquetes de voz de Windows
  - Funciona de manera ligera y con excelente calidad neural

Uso futuro:
    from src.darius_ai.audio.edge_tts_engine import EdgeTTS
    tts = EdgeTTS(voice="es-MX-DaliaNeural")
    tts.speak("Hola, soy Darius")

Dependencias:
  pip install edge-tts

Nota de migración:
  edge-tts es async por diseño (usa asyncio). Se envuelve
  en un wrapper síncrono para compatibilidad con main.py.
"""

import asyncio
import contextlib
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger("DARIUS.EdgeTTS")


def _play_audio_file(file_path: Path | str) -> bool:
    """
    Reproduce un archivo de audio (MP3/WAV) mediante Win32 MCI o fallback a sounddevice.
    Evita dependencias problemáticas como playsound.
    """
    target_str = str(file_path)
    if sys.platform == "win32":
        try:
            import ctypes

            winmm = ctypes.windll.winmm
            alias = f"darius_edge_{os.getpid()}_{id(target_str)}"
            open_cmd = f'open "{target_str}" type mpegvideo alias {alias}'
            if winmm.mciSendStringW(open_cmd, None, 0, None) == 0:
                winmm.mciSendStringW(f"play {alias} wait", None, 0, None)
                winmm.mciSendStringW(f"close {alias}", None, 0, None)
                return True
        except Exception as e:
            log.warning(f"Error reproduciendo audio con Win32 MCI: {e}")

    try:
        import sounddevice as sd
        import soundfile as sf

        data, fs = sf.read(target_str)
        sd.play(data, fs)
        sd.wait()
        return True
    except Exception as e:
        log.warning(f"Error reproduciendo audio con sounddevice/soundfile: {e}")
        return False


class EdgeTTS:
    """
    Motor TTS basado en edge-tts (Microsoft Edge online TTS).

    Usa asyncio internamente, expone interfaz síncrona.

    Atributos:
        voice (str): Nombre de la voz (ej: "es-MX-DaliaNeural")
        rate  (int): Velocidad (0-100, default 50)
        volume (int): Volumen (0-100, default 100)
    """

    # Recommended neural voices (Spanish & English):
    VOICES = {
        "es-MX-DaliaNeural": "Dalia (Mexicana) - Neural",
        "es-ES-AlvaroNeural": "Alvaro (Español) - Neural",
        "es-ES-ElviraNeural": "Elvira (Española) - Neural",
        "es-CO-GonzaloNeural": "Gonzalo (Colombiano) - Neural",
        "en-US-JennyNeural": "Jenny (US) - Neural",
        "en-US-GuyNeural": "Guy (US) - Neural",
        "en-GB-RyanNeural": "Ryan (UK Butler) - Neural",
        "en-GB-SoniaNeural": "Sonia (UK) - Neural",
    }

    @classmethod
    def get_default_voice(cls, language: str | None = None) -> str:
        """Return the default neural voice matching the configured ISO-639-1 language."""
        lang = language
        if lang is None:
            try:
                from src.darius_ai.core.config_loader import cfg

                lang = cfg.language
            except Exception:
                lang = "en"
        return "en-GB-RyanNeural" if str(lang).strip().lower().startswith("en") else "es-MX-DaliaNeural"

    def __init__(self, voice: str = "es-MX-DaliaNeural", rate: int = 50, volume: int = 100):
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self._loop: asyncio.AbstractEventLoop | None = None

    def speak(self, text: str) -> bool:
        """
        Síncrono: habla el texto usando edge-tts.
        Crea y cierra un event loop si es necesario.
        """
        try:
            return asyncio.run(self._speak_async(text))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(self._speak_async(text))
            finally:
                loop.close()
        except Exception as e:
            log.warning(f"Error en edge-tts: {e}")
            return False

    async def _speak_async(self, text: str) -> bool:
        """
        Asíncrono: genera audio con edge-tts y lo reproduce limpiamente.
        """
        import tempfile

        tmp_file = Path(tempfile.gettempdir()) / f"darius_edge_{os.getpid()}_{id(text)}.mp3"
        try:
            import edge_tts

            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(str(tmp_file))
            return _play_audio_file(tmp_file)
        except ImportError:
            log.warning("edge-tts no instalado. Instala con: pip install edge-tts")
            return False
        except Exception as e:
            log.warning(f"Error en edge-tts: {e}")
            return False
        finally:
            if tmp_file.exists():
                with contextlib.suppress(Exception):
                    tmp_file.unlink(missing_ok=True)
