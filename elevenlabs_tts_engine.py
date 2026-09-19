"""
elevenlabs_tts_engine.py — Motor de Text-to-Speech con ElevenLabs para DARIUS AI
================================================================================
Síntesis de voz ultra-realista con modelos multilingües de ElevenLabs.
Integra caché local en disco (tts_cache.py) para reproducción instantánea
en saludos, confirmaciones y frases repetidas.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

from tts_cache import get_cached_wav_path, is_cached, play_cached_wav, save_pcm_to_wav

log = logging.getLogger("DARIUS.ElevenLabsTTS")

_BASE_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL_ID = "eleven_multilingual_v2"
DEFAULT_OUTPUT_FORMAT = "pcm_24000"
DEFAULT_SAMPLE_RATE = 24000


class ElevenLabsTTS:
    """Motor TTS de alta fidelidad con ElevenLabs y caché en disco."""

    def __init__(
        self,
        api_key: str = "",
        voice_id: str = "",
        model_id: str = DEFAULT_MODEL_ID,
        output_format: str = DEFAULT_OUTPUT_FORMAT,
        cache_enabled: bool = True,
    ):
        self.api_key = (api_key or os.environ.get("ELEVENLABS_API_KEY", "")).strip()
        self.voice_id = (voice_id or os.environ.get("ELEVENLABS_VOICE_ID", "")).strip()
        self.model_id = (model_id or os.environ.get("ELEVENLABS_MODEL_ID", DEFAULT_MODEL_ID)).strip()
        env_fmt = os.environ.get("ELEVENLABS_OUTPUT_FORMAT", DEFAULT_OUTPUT_FORMAT)
        self.output_format = (output_format or env_fmt).strip()
        self.cache_enabled = cache_enabled
        self.sample_rate = self._resolve_sample_rate(self.output_format)

    @staticmethod
    def _resolve_sample_rate(output_format: str) -> int:
        override = (os.environ.get("ELEVENLABS_PCM_SAMPLE_RATE") or "").strip()
        if override.isdigit():
            return int(override)
        if output_format.startswith("pcm_"):
            try:
                return int(output_format.split("_", maxsplit=1)[1])
            except (ValueError, IndexError):
                pass
        return DEFAULT_SAMPLE_RATE

    def is_configured(self) -> bool:
        """Verifica si se dispone de clave y voice ID requeridos."""
        return bool(self.api_key and self.voice_id)

    def speak(self, text: str) -> bool:
        """
        Sintetiza y reproduce el texto de forma síncrona.
        Primero consulta la caché local; si no existe, invoca la API y almacena el resultado.
        """
        clean_text = text.strip()
        if not clean_text:
            return False

        # 1. Verificar caché en disco
        if self.cache_enabled and is_cached(clean_text, self.voice_id, self.model_id, self.output_format):
            cache_path = get_cached_wav_path(clean_text, self.voice_id, self.model_id, self.output_format)
            log.info(f"[ElevenLabs] Reproduciendo desde caché: {cache_path.name}")
            if play_cached_wav(cache_path):
                return True
            log.warning("[ElevenLabs] Fallo al reproducir archivo en caché; reintentando vía API...")

        if not self.is_configured():
            log.warning("[ElevenLabs] API Key o Voice ID no configurados.")
            return False

        # 2. Generar audio vía SDK o REST
        raw_pcm = self._fetch_pcm(clean_text)
        if not raw_pcm:
            return False

        # 3. Guardar en caché si está habilitado
        if self.cache_enabled:
            cache_path = get_cached_wav_path(clean_text, self.voice_id, self.model_id, self.output_format)
            save_pcm_to_wav(cache_path, raw_pcm, self.sample_rate)

        # 4. Reproducir audio
        return self._play_raw_pcm(raw_pcm)

    def _fetch_pcm(self, text: str) -> bytes | None:
        """Obtiene el buffer de audio PCM crudo desde la API de ElevenLabs."""
        # Intento vía SDK oficial de ElevenLabs si está instalado
        try:
            from elevenlabs.client import ElevenLabs

            client = ElevenLabs(api_key=self.api_key)
            audio_generator = client.text_to_speech.convert(
                voice_id=self.voice_id,
                text=text,
                model_id=self.model_id,
                output_format=self.output_format,
            )
            return b"".join(audio_generator)
        except ImportError:
            log.debug("[ElevenLabs] SDK no disponible, usando REST nativo urllib...")
        except Exception as e:
            log.warning(f"[ElevenLabs SDK] Error: {e}, intentando vía REST...")

        # Fallback vía REST nativo con urllib (sin dependencias externas)
        return self._fetch_pcm_rest(text)

    def _fetch_pcm_rest(self, text: str) -> bytes | None:
        """Llamada REST directa a ElevenLabs text-to-speech endpoint."""
        url = (
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
            f"?output_format={self.output_format}"
        )
        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.8,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/pcm",
        }
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")  # noqa: S310
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
                return resp.read()
        except urllib.error.HTTPError as he:
            err_msg = he.read().decode("utf-8", errors="ignore")
            log.error(f"[ElevenLabs REST] HTTP {he.code}: {err_msg}")
            return None
        except Exception as exc:
            log.error(f"[ElevenLabs REST] Error de conexión: {exc}")
            return None

    def _play_raw_pcm(self, raw_pcm: bytes) -> bool:
        """Reproduce un stream PCM de 16-bit a la frecuencia de muestreo configurada."""
        try:
            import sounddevice as sd

            pcm_i16 = np.frombuffer(raw_pcm, dtype=np.int16)
            pcm_f = pcm_i16.astype(np.float32) / 32768.0
            sd.play(pcm_f, self.sample_rate)
            sd.wait()
            return True
        except Exception as e:
            log.error(f"[ElevenLabs] Error al reproducir audio: {e}")
            return False


def test_elevenlabs_connection(api_key: str, voice_id: str) -> tuple[bool, int, str]:
    """
    Prueba diagnóstica rápida hacia ElevenLabs para verificar la validez de la API Key y Voice ID.
    Retorna (éxito, latencia_ms, mensaje).
    """
    if not api_key.strip():
        return False, 0, "Falta la API Key de ElevenLabs."
    if not voice_id.strip():
        return False, 0, "Falta el Voice ID de ElevenLabs."

    import time

    start = time.perf_counter()
    url = f"https://api.elevenlabs.io/v1/voices/{voice_id.strip()}"
    headers = {"xi-api-key": api_key.strip()}
    req = urllib.request.Request(url, headers=headers, method="GET")  # noqa: S310

    try:
        with urllib.request.urlopen(req, timeout=8) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
            latency_ms = int((time.perf_counter() - start) * 1000)
            voice_name = data.get("name", "Desconocida")
            return True, latency_ms, f"Conexión exitosa. Voz detectada: {voice_name}"
    except urllib.error.HTTPError as he:
        latency_ms = int((time.perf_counter() - start) * 1000)
        if he.code == 401:
            return False, latency_ms, "API Key inválida o no autorizada (HTTP 401)."
        if he.code == 404:
            return False, latency_ms, "Voice ID no encontrada en ElevenLabs (HTTP 404)."
        return False, latency_ms, f"Error HTTP {he.code} de ElevenLabs."
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return False, latency_ms, f"Error de conexión: {e}"
