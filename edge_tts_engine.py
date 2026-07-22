"""
edge_tts_engine.py — Text-to-Speech con Microsoft Edge TTS para DARIUS AI
==========================================================================
Blueprint para migración desde SAPI (win32com) a edge-tts.

Ventajas de edge-tts:
  - Voces más naturales (neurales de Microsoft)
  - Multi-idioma sin instalar paquetes de voz de Windows
  - No requiere SAPI ni win32com
  - Funciona en Linux/Railway (no solo Windows)

Uso futuro:
    from edge_tts_engine import EdgeTTS
    tts = EdgeTTS(voice="es-MX-DaliaNeural")
    tts.speak("Hola, soy Darius")

Dependencias:
  pip install edge-tts

Nota de migración:
  edge-tts es async por diseño (usa asyncio). Se envuelve
  en un wrapper síncrono para compatibilidad con main.py.
"""

import asyncio
import logging

log = logging.getLogger("DARIUS.EdgeTTS")


class EdgeTTS:
    """
    Motor TTS basado en edge-tts (Microsoft Edge online TTS).

    Usa asyncio internamente, expone interfaz síncrona.

    Atributos:
        voice (str): Nombre de la voz (ej: "es-MX-DaliaNeural")
        rate  (int): Velocidad (0-100, default 50)
        volume (int): Volumen (0-100, default 100)
    """

    # Voces recomendadas para español:
    VOICES = {
        "es-MX-DaliaNeural": "Dalia (Mexicana) - Neural",
        "es-ES-AlvaroNeural": "Alvaro (Español) - Neural",
        "es-ES-ElviraNeural": "Elvira (Española) - Neural",
        "es-CO-GonzaloNeural": "Gonzalo (Colombiano) - Neural",
    }

    def __init__(self, voice: str = "es-MX-DaliaNeural", rate: int = 50, volume: int = 100):
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self._loop: asyncio.AbstractEventLoop | None = None

    def speak(self, text: str):
        """
        Síncrono: habla el texto usando edge-tts.
        Crea un event loop si es necesario.
        """
        try:
            asyncio.run(self._speak_async(text))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._speak_async(text))
        except Exception as e:
            log.warning(f"Error en edge-tts: {e}")

    async def _speak_async(self, text: str):
        """
        Asíncrono: ejecuta edge-tts.
        Pendiente: implementar con edge_tts.Communicate.
        """
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save("_tts_temp.mp3")
            try:
                import playsound
                playsound.playsound("_tts_temp.mp3")
            except ImportError:
                log.warning("playsound no instalado. pip install playsound")
        except ImportError:
            log.warning("edge-tts no instalado. pip install edge-tts")
        except Exception as e:
            log.warning(f"Error en edge-tts: {e}")
