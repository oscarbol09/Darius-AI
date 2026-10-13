"""
media_controller.py — Controlador Multimedia y Despachador Win32 para DARIUS AI
================================================================================
Gestiona el control de reproducción multimedia y volumen del sistema mediante
despacho directo de Virtual Keys (VK) a través de `user32.dll` (keybd_event)
y manipulación del nivel de audio maestro a través de pycaw / PowerShell.
"""

from __future__ import annotations

import ctypes
import logging
import platform
import re
import subprocess
import threading
import urllib.parse
import webbrowser
from typing import Any

from src.darius_ai.core.security_guard import is_safe_url

log = logging.getLogger("DARIUS.MediaController")

# Constantes de Virtual Key de Windows para Medios y Audio
VK_VOLUME_MUTE = 0xAD  # 173
VK_VOLUME_DOWN = 0xAE  # 174
VK_VOLUME_UP = 0xAF  # 175
VK_MEDIA_NEXT_TRACK = 0xB0  # 176
VK_MEDIA_PREV_TRACK = 0xB1  # 177
VK_MEDIA_STOP = 0xB2  # 178
VK_MEDIA_PLAY_PAUSE = 0xB3  # 179

KEYEVENTF_KEYUP = 0x0002


def clean_media_query(query: str) -> str:
    """
    Limpia y extrae el título de la canción, álbum o artista de una orden de voz.
    Ejemplos:
      - "reproduce música de Daft Punk" -> "Daft Punk"
      - "pon la canción Bohemian Rhapsody" -> "Bohemian Rhapsody"
      - "escuchar a Queen" -> "Queen"
      - "pon música de Pink Floyd en spotify" -> "Pink Floyd"
    """
    if not query:
        return ""

    cleaned = query.strip()

    # 1. Eliminar sufijos de plataforma (ej: "en spotify", "en youtube")
    suffixes = [
        r"\s+(?:en|por|on|de)\s+(?:spotify|youtube|apple\s+music|deezer|amazon\s+music|tidal|la\s+radio)\b.*$",
    ]
    for suf in suffixes:
        cleaned = re.sub(suf, "", cleaned, flags=re.IGNORECASE).strip()

    # 2. Eliminar prefijos de órdenes verbales comunes
    prefixes = [
        r"^(?:por\s+favor\s+)?(?:reproduce|reproducir|pon|poner|escuchar|escucha|toca|tocar|play)\s+(?:unas\s+|las\s+|los\s+|una\s+|la\s+|el\s+)?(?:canciones|canción|cancion|temas|tema|pistas|pista|música|musica|algo|tracks|track|songs|song|music)?\s*(?:de|del|a|by)?\s*",  # noqa: E501
        r"^(?:por\s+favor\s+)?(?:reproduce|reproducir|pon|poner|escuchar|escucha|toca|tocar|play)\s*",
    ]
    for pref in prefixes:
        cleaned = re.sub(pref, "", cleaned, flags=re.IGNORECASE).strip()

    # 3. Eliminar comillas y signos de puntuación excedentes en los extremos
    cleaned = cleaned.strip("\"'`“”‘’«».,;:!? ")
    return cleaned


def clean_youtube_query(query: str) -> str:
    """
    Sanitiza y extrae el término de búsqueda para YouTube de una orden de voz o texto.
    Elimina expresiones como 'busca en youtube', 'reproduce en youtube', 'pon en youtube', etc.
    """
    if not query:
        return ""

    cleaned = query.strip()

    # 1. Eliminar prefijos específicos de YouTube (ej: "busca en youtube", "reproduce en youtube", etc.)
    yt_prefixes = [
        r"^(?:por\s+favor\s+)?(?:busca|buscar|encuentra|encontrar|search|reproduce|reproducir|pon|poner|escuchar|escucha|ver|mira|mirar|play|toca|tocar)\s+(?:en|por|on|de)\s+youtube\s*(?:un\s+|una\s+|el\s+|la\s+|los\s+|las\s+)?(?:video|vídeo|canción|cancion|tema|clip|música|musica)?\s*(?:de|del|sobre)?\s*",  # noqa: E501
        r"^youtube\s+",
    ]
    for pref in yt_prefixes:
        cleaned = re.sub(pref, "", cleaned, flags=re.IGNORECASE).strip()

    if cleaned.lower() == "youtube":
        return ""

    # 2. Eliminar sufijos al final del comando (ej: "... en youtube", "... por youtube")
    suffixes = [
        r"\s+(?:en|por|on|de)\s+youtube\s*$",
        r"\s+(?:en|por|on|de)\s+(?:spotify|apple\s+music|deezer|amazon\s+music|tidal|la\s+radio)\s*$",
    ]
    for suf in suffixes:
        cleaned = re.sub(suf, "", cleaned, flags=re.IGNORECASE).strip()

    # 3. Eliminar prefijos visuales (ej: "ver video de...", "mira el clip de...")
    visual_prefixes = [
        r"^(?:por\s+favor\s+)?(?:ver|mira|mirar)\s+(?:un\s+|una\s+|el\s+|la\s+|los\s+|las\s+)?(?:video|vídeo|clip)?\s*(?:de|del|sobre)?\s*",  # noqa: E501
        r"^(?:por\s+favor\s+)?(?:reproduce|reproducir|pon|poner|play)\s+(?:un\s+|el\s+)(?:video|vídeo|clip)\s*(?:de|del|sobre)?\s*",  # noqa: E501
    ]
    for pref in visual_prefixes:
        cleaned = re.sub(pref, "", cleaned, flags=re.IGNORECASE).strip()

    # 4. Aplicar clean_media_query para remoción de prefijos genéricos restantes
    cleaned = clean_media_query(cleaned)

    # 5. Caso particular si la query era solo un verbo de búsqueda sin término
    search_only_verbs = r"^(?:busca|buscar|search|ver|mira|mirar|play|reproduce|reproducir|pon|poner)$"
    if re.fullmatch(search_only_verbs, cleaned, re.IGNORECASE):
        return ""

    return cleaned.strip("\"'`“”‘’«».,;:!? ")


class MediaController:
    """
    Controlador multimedia para Windows con emisión de teclas virtuales y control de volumen.
    """

    def __init__(self) -> None:
        self._is_windows = platform.system() == "Windows"

    def _send_vk(self, vk_code: int, action_name: str) -> tuple[bool, str]:
        """
        Envía un evento de tecla virtual de Windows (KeyDown + KeyUp).
        Si no está en Windows o se produce un error, degrada graciosamente.
        """
        if not self._is_windows:
            log.debug(f"[MediaController] No-Windows/CI: Simulando {action_name} (VK: 0x{vk_code:02X})")
            return True, f"Simulado {action_name} en entorno no-Windows"

        try:
            windll = getattr(ctypes, "windll", None)
            if not windll or not hasattr(windll, "user32"):
                log.debug(f"[MediaController] user32 no disponible. Simulando {action_name}")
                return True, f"Simulado {action_name} (sin user32)"

            user32 = windll.user32
            # KeyDown
            user32.keybd_event(vk_code, 0, 0, 0)
            # KeyUp
            user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)
            return True, f"Comando {action_name} emitido con éxito"
        except Exception as e:
            log.warning(f"[MediaController] Error despachando VK 0x{vk_code:02X} ({action_name}): {e}")
            return False, f"Error al emitir comando de medios: {e}"

    def play_pause(self) -> tuple[bool, str]:
        """Alterna reproducción / pausa (VK 0xB3)."""
        return self._send_vk(VK_MEDIA_PLAY_PAUSE, "Play/Pause")

    def next_track(self) -> tuple[bool, str]:
        """Avanza a la pista siguiente (VK 0xB0)."""
        return self._send_vk(VK_MEDIA_NEXT_TRACK, "Next Track")

    def prev_track(self) -> tuple[bool, str]:
        """Retrocede a la pista anterior (VK 0xB1)."""
        return self._send_vk(VK_MEDIA_PREV_TRACK, "Previous Track")

    def stop(self) -> tuple[bool, str]:
        """Detiene la reproducción multimedia (VK 0xB2)."""
        return self._send_vk(VK_MEDIA_STOP, "Stop")

    def volume_up(self, step: int = 2) -> tuple[bool, str]:
        """Incrementa el volumen del sistema en saltos de tecla (VK 0xAF)."""
        step = max(1, step)
        success = True
        msg = ""
        for _ in range(step):
            s, m = self._send_vk(VK_VOLUME_UP, "Volume Up")
            if not s:
                success = False
                msg = m
        return success, msg or f"Volumen incrementado (+{step} pasos)"

    def volume_down(self, step: int = 2) -> tuple[bool, str]:
        """Reduce el volumen del sistema en saltos de tecla (VK 0xAE)."""
        step = max(1, step)
        success = True
        msg = ""
        for _ in range(step):
            s, m = self._send_vk(VK_VOLUME_DOWN, "Volume Down")
            if not s:
                success = False
                msg = m
        return success, msg or f"Volumen decrementado (-{step} pasos)"

    def toggle_mute(self) -> tuple[bool, str]:
        """Alterna el silencio de audio del sistema (VK 0xAD)."""
        return self._send_vk(VK_VOLUME_MUTE, "Mute")

    def _get_pycaw_endpoint(self) -> Any:
        """Obtiene la interfaz de control de volumen de pycaw."""
        try:
            from pycaw.pycaw import AudioUtilities

            speakers = AudioUtilities.GetSpeakers()
            if speakers is None:
                return None
            if hasattr(speakers, "EndpointVolume"):
                return speakers.EndpointVolume

            from ctypes import POINTER, cast

            from comtypes import CLSCTX_ALL
            from pycaw.api.endpointvolume import IAudioEndpointVolume

            interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            return cast(interface, POINTER(IAudioEndpointVolume))
        except Exception as e:
            log.debug(f"[MediaController] pycaw no disponible o falló: {e}")
            return None

    def set_volume_percent(self, percent: int) -> tuple[bool, str]:
        """
        Ajusta el volumen maestro del sistema a un porcentaje específico (0 a 100)
        usando pycaw con degradación a PowerShell.
        """
        target = max(0, min(100, int(percent)))
        scalar = target / 100.0

        ep = self._get_pycaw_endpoint()
        if ep is not None:
            try:
                ep.SetMasterVolumeLevelScalar(scalar, None)
                return True, f"Volumen maestro ajustado al {target}%"
            except Exception as e:
                log.warning(f"[MediaController] Error en pycaw al ajustar volumen: {e}")

        # Fallback vía PowerShell
        try:
            ps_script = (
                f"$wsh = New-Object -ComObject WScript.Shell; "
                f"$target = {target}; "
                f"for ($i=0; $i -lt 50; $i++) {{ $wsh.SendKeys([char]174) }}; "
                f"$steps = [math]::Round($target / 2); "
                f"for ($i=0; $i -lt $steps; $i++) {{ $wsh.SendKeys([char]175) }}"
            )
            res = subprocess.run(  # noqa: S603
                ["powershell", "-NoProfile", "-Command", ps_script],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode == 0:
                return True, f"Volumen maestro ajustado al {target}% vía PowerShell"
        except Exception as e:
            log.debug(f"[MediaController] Fallback PowerShell falló: {e}")

        return False, f"No se pudo ajustar el volumen maestro al {target}%"

    def get_volume_percent(self) -> int:
        """Lee el porcentaje actual del volumen maestro del sistema (0 a 100)."""
        ep = self._get_pycaw_endpoint()
        if ep is not None:
            try:
                scalar = ep.GetMasterVolumeLevelScalar()
                return int(round(scalar * 100))
            except Exception as e:
                log.debug(f"[MediaController] Error leyendo volumen con pycaw: {e}")
        return 50

    def clean_media_query(self, query: str) -> str:
        """Método de instancia delegado a clean_media_query."""
        return clean_media_query(query)

    def clean_youtube_query(self, query: str) -> str:
        """Método de instancia delegado a clean_youtube_query."""
        return clean_youtube_query(query)

    def search_and_play_youtube(self, query: str, auto_play: bool = True) -> tuple[bool, str]:
        """
        Busca y reproduce un video o canción en YouTube.
        Sanitiza la consulta, valida la URL generada contra ataques SSRF,
        abre el navegador predeterminado y, si auto_play=True, despacha comando de reproducción.
        """
        cleaned = clean_youtube_query(query)
        if not cleaned:
            return False, "Consulta de búsqueda en YouTube vacía o inválida"

        encoded = urllib.parse.quote_plus(cleaned)
        youtube_url = f"https://www.youtube.com/results?search_query={encoded}"

        # Validación Anti-SSRF
        is_safe, reason = is_safe_url(youtube_url)
        if not is_safe:
            log.warning(f"[MediaController] URL de YouTube bloqueada por Anti-SSRF: {reason}")
            return False, f"URL bloqueada por política de seguridad Anti-SSRF: {reason}"

        # Abrir navegador predeterminado del sistema
        try:
            opened = webbrowser.open(youtube_url)
            if not opened:
                log.debug(f"[MediaController] webbrowser.open retornó False para {youtube_url}")
        except Exception as e:
            log.error(f"[MediaController] Error al abrir navegador para YouTube: {e}")
            return False, f"Error al abrir YouTube en el navegador: {e}"

        if auto_play:
            self.play_pause()
            msg = f"Buscando y reproduciendo '{cleaned}' en YouTube: {youtube_url}"
        else:
            msg = f"Buscando '{cleaned}' en YouTube: {youtube_url}"

        return True, msg


# Instancia Singleton
_GLOBAL_MEDIA_CONTROLLER: MediaController | None = None
_MEDIA_LOCK = threading.Lock()


def get_media_controller() -> MediaController:
    """Retorna la instancia global del controlador multimedia."""
    global _GLOBAL_MEDIA_CONTROLLER
    if _GLOBAL_MEDIA_CONTROLLER is None:
        with _MEDIA_LOCK:
            if _GLOBAL_MEDIA_CONTROLLER is None:
                _GLOBAL_MEDIA_CONTROLLER = MediaController()
    return _GLOBAL_MEDIA_CONTROLLER


# Instancia singleton accesible globalmente
media_controller = get_media_controller()

