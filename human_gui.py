"""
human_gui.py — Motor de Automatización de Interfaz Humana ("Computer Use" y Scraping)
=====================================================================================
Permite a Darius AI interactuar con la interfaz gráfica de Windows como un humano:
  1. Movimiento no lineal del ratón mediante Curvas de Bézier cúbicas con aceleración
     y desaceleración natural (Ley de Fitts).
  2. Clics con duración y cadencia de presión humana.
  3. Escritura mecanográfica con variación estocástica de pulsaciones (WPM) y soporte Unicode.
  4. Failsafe (parada de pánico) en esquinas de pantalla o comando de detención.
  5. Extracción y scraping de contenido web/HTML limpio en segundo plano.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import html
import logging
import math
import os
import random
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

log = logging.getLogger("DARIUS.HumanGUI")

# ─────────────────────────────────────────────────────────────────────────────
#  CONSTANTES WIN32 Y MOUSE / KEYBOARD FLAGS
# ─────────────────────────────────────────────────────────────────────────────

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP       = 0x0002
KEYEVENTF_UNICODE     = 0x0004
KEYEVENTF_SCANCODE    = 0x0008

MOUSEEVENTF_MOVE       = 0x0001
MOUSEEVENTF_LEFTDOWN   = 0x0002
MOUSEEVENTF_LEFTUP     = 0x0004
MOUSEEVENTF_RIGHTDOWN  = 0x0008
MOUSEEVENTF_RIGHTUP    = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP   = 0x0040
MOUSEEVENTF_WHEEL      = 0x0800

VK_MAP = {
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "win": 0x5B,
    "windows": 0x5B,
    "enter": 0x0D,
    "intro": 0x0D,
    "tab": 0x09,
    "esc": 0x1B,
    "escape": 0x1B,
    "backspace": 0x08,
    "space": 0x20,
    "espacio": 0x20,
    "del": 0x2E,
    "delete": 0x2E,
    "supr": 0x2E,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
}


class FailsafeError(Exception):
    """Excepción lanzada cuando el usuario activa la parada de emergencia."""
    pass


FailsafeException = FailsafeError


class HumanGUIAutomator:
    """Motor central de control y automatización de interfaz con emulación humana."""

    def __init__(self):
        self._user32 = ctypes.windll.user32 if os.name == "nt" else None
        self._abort_flag = threading.Event()
        self.failsafe_enabled = True

    def check_failsafe(self):
        """Verifica si el cursor está en una esquina de pánico o si se solicitó abortar."""
        if self._abort_flag.is_set():
            self._abort_flag.clear()
            raise FailsafeError("Operación de automatización abortada por el usuario.")

        if not self.failsafe_enabled or not self._user32:
            return

        pos = self.get_cursor_pos()
        # Esquina superior izquierda (0,0) con margen de 8px
        if pos[0] <= 8 and pos[1] <= 8:
            raise FailsafeError(f"Parada de emergencia activada por cursor en esquina {pos}.")

    def abort(self):
        """Solicita la detención inmediata de cualquier acción en curso."""
        self._abort_flag.set()
        log.info("[HumanGUI] Bandera de abortar establecida.")

    def get_cursor_pos(self) -> tuple[int, int]:
        """Obtiene las coordenadas absolutas actuales del cursor del ratón."""
        if not self._user32:
            return (0, 0)
        pt = ctypes.wintypes.POINT()
        self._user32.GetCursorPos(ctypes.byref(pt))
        return (int(pt.x), int(pt.y))

    def set_cursor_pos(self, x: int, y: int):
        """Fija la posición del cursor de forma inmediata."""
        if self._user32:
            self._user32.SetCursorPos(int(x), int(y))

    # ─────────────────────────────────────────────────────────────────────────
    #  FÍSICA DEL MOVIMIENTO: CURVAS DE BÉZIER Y LEY DE FITTS
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def calculate_bezier_trajectory(
        start: tuple[int, int],
        end: tuple[int, int],
        steps: int = 25,
        deviation_factor: float = 0.25,
    ) -> list[tuple[int, int]]:
        """
        Genera una serie de puntos en una curva de Bézier cúbica no lineal con
        aceleración y desaceleración natural (Ease-in / Ease-out).
        """
        x0, y0 = start
        x3, y3 = end
        dist = math.hypot(x3 - x0, y3 - y0)
        if dist < 4:
            return [end]

        # Puntos de control aleatorios perpendiculares a la trayectoria
        mid_x = (x0 + x3) / 2
        mid_y = (y0 + y3) / 2
        offset = dist * deviation_factor * random.uniform(0.6, 1.4)  # noqa: S311
        angle = math.atan2(y3 - y0, x3 - x0) + (math.pi / 2 if random.random() > 0.5 else -math.pi / 2)  # noqa: S311

        x1 = int(mid_x + math.cos(angle) * offset * random.uniform(0.5, 1.0))  # noqa: S311
        y1 = int(mid_y + math.sin(angle) * offset * random.uniform(0.5, 1.0))  # noqa: S311
        x2 = int(mid_x + math.cos(angle) * offset * random.uniform(0.2, 0.7))  # noqa: S311
        y2 = int(mid_y + math.sin(angle) * offset * random.uniform(0.2, 0.7))  # noqa: S311

        points: list[tuple[int, int]] = []
        for i in range(1, steps + 1):
            # Progresión u normalizada [0..1]
            u = i / steps
            # Perfil sinusoidal de Fitts (ease-in-out suave)
            t = 0.5 * (1.0 - math.cos(math.pi * u))

            # Ecuación cúbica de Bézier
            inv = 1.0 - t
            bx = (inv ** 3) * x0 + 3 * (inv ** 2) * t * x1 + 3 * inv * (t ** 2) * x2 + (t ** 3) * x3
            by = (inv ** 3) * y0 + 3 * (inv ** 2) * t * y1 + 3 * inv * (t ** 2) * y2 + (t ** 3) * y3

            # Añadir micro-jitter sutil (excepto en el punto final)
            if i < steps:
                jitter_x = random.uniform(-0.8, 0.8)  # noqa: S311
                jitter_y = random.uniform(-0.8, 0.8)  # noqa: S311
                bx += jitter_x
                by += jitter_y

            points.append((int(round(bx)), int(round(by))))

        return points

    def human_mouse_move(
        self,
        target_x: int,
        target_y: int,
        duration: float = 0.4,
        steps: int = 25,
    ) -> bool:
        """
        Mueve el cursor hacia (target_x, target_y) trazando un arco natural.
        """
        self.check_failsafe()
        start = self.get_cursor_pos()
        path = self.calculate_bezier_trajectory(start, (target_x, target_y), steps=steps)

        step_delay = max(0.005, duration / max(1, len(path)))

        for px, py in path:
            self.check_failsafe()
            self.set_cursor_pos(px, py)
            time.sleep(step_delay * random.uniform(0.8, 1.2))  # noqa: S311

        # Asegurar posición final exacta
        self.set_cursor_pos(target_x, target_y)
        return True

    def human_click(
        self,
        x: int | None = None,
        y: int | None = None,
        button: str = "left",
        double: bool = False,
    ) -> bool:
        """
        Ejecuta un clic o doble clic con duraciones humanas de pulsación.
        """
        self.check_failsafe()
        if x is not None and y is not None:
            self.human_mouse_move(x, y)

        btn = button.lower().strip()
        down_flag = MOUSEEVENTF_RIGHTDOWN if btn in ("right", "derecho") else MOUSEEVENTF_LEFTDOWN
        up_flag = MOUSEEVENTF_RIGHTUP if btn in ("right", "derecho") else MOUSEEVENTF_LEFTUP

        if not self._user32:
            return False

        cx, cy = self.get_cursor_pos()

        def _single_click():
            self.check_failsafe()
            self._user32.mouse_event(down_flag, cx, cy, 0, 0)
            time.sleep(random.uniform(0.06, 0.12))  # noqa: S311
            self._user32.mouse_event(up_flag, cx, cy, 0, 0)

        _single_click()
        if double:
            time.sleep(random.uniform(0.08, 0.14))  # noqa: S311
            _single_click()

        return True

    def human_scroll(self, clicks: int = -3):
        """Simula desplazamiento con la rueda del ratón."""
        self.check_failsafe()
        if not self._user32:
            return
        cx, cy = self.get_cursor_pos()
        # 120 unidades por cada muesca de scroll en Windows
        wheel_amount = clicks * 120
        self._user32.mouse_event(MOUSEEVENTF_WHEEL, cx, cy, wheel_amount, 0)

    # ─────────────────────────────────────────────────────────────────────────
    #  TECLADO Y ESCRITURA MECANOGRÁFICA
    # ─────────────────────────────────────────────────────────────────────────

    def press_key_code(self, vk_code: int):
        """Presiona y suelta una tecla virtual de Windows."""
        if not self._user32:
            return
        self.check_failsafe()
        self._user32.keybd_event(vk_code, 0, 0, 0)
        time.sleep(random.uniform(0.03, 0.07))  # noqa: S311
        self._user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)

    def press_unicode_char(self, char: str):
        """Escribe cualquier carácter Unicode directamente sin problemas de layout."""
        if not self._user32:
            return
        self.check_failsafe()
        code = ord(char)
        self._user32.keybd_event(0, code, KEYEVENTF_UNICODE, 0)
        time.sleep(random.uniform(0.015, 0.04))  # noqa: S311
        self._user32.keybd_event(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0)

    def human_type(
        self,
        text: str,
        wpm: int = 70,
        click_before: bool = False,
    ) -> bool:
        """
        Escribe un texto emulando la cadencia mecanográfica humana con variación
        estocástica de latencia por carácter.
        """
        self.check_failsafe()
        if click_before:
            self.human_click()

        # Tiempo base promedio por carácter basado en WPM (1 palabra ≈ 5 caracteres)
        char_delay_base = 60.0 / (wpm * 5.0)

        for char in text:
            self.check_failsafe()

            if char == "\n":
                self.press_key_code(VK_MAP["enter"])
                time.sleep(random.uniform(0.12, 0.25))  # noqa: S311
            elif char == "\t":
                self.press_key_code(VK_MAP["tab"])
                time.sleep(random.uniform(0.08, 0.18))  # noqa: S311
            else:
                self.press_unicode_char(char)
                # Pausa adicional en signos de puntuación
                if char in (".", ",", "!", "?", ";", ":"):
                    time.sleep(random.uniform(0.15, 0.35))  # noqa: S311
                elif char == " ":
                    time.sleep(random.uniform(char_delay_base * 0.8, char_delay_base * 1.5))  # noqa: S311
                else:
                    jitter = random.gauss(0, char_delay_base * 0.3)  # noqa: S311
                    delay = max(0.015, char_delay_base + jitter)
                    time.sleep(delay)

        return True

    def human_hotkey(self, *keys: str) -> bool:
        """
        Ejecuta una combinación de teclas (ej: 'ctrl', 'v' o 'win', 'r').
        """
        self.check_failsafe()
        if not self._user32:
            return False

        vk_list = []
        for k in keys:
            norm_k = k.lower().strip()
            if norm_k in VK_MAP:
                vk_list.append(VK_MAP[norm_k])
            elif len(norm_k) == 1:
                vk_list.append(ord(norm_k.upper()))

        if not vk_list:
            return False

        # Presionar en orden
        for vk in vk_list:
            self._user32.keybd_event(vk, 0, 0, 0)
            time.sleep(random.uniform(0.02, 0.05))  # noqa: S311

        time.sleep(random.uniform(0.05, 0.10))  # noqa: S311

        # Soltar en orden inverso
        for vk in reversed(vk_list):
            self._user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(random.uniform(0.01, 0.03))  # noqa: S311

        return True

    # ─────────────────────────────────────────────────────────────────────────
    #  SCRAPING Y EXTRACCIÓN WEB
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def scrape_web_content(url: str, max_chars: int = 3000, timeout: int = 10) -> dict[str, Any]:
        """
        Descarga y limpia el contenido legible de una página web en segundo plano
        sin dependencias externas.
        """
        clean_url = url.strip()
        if not clean_url.startswith(("http://", "https://")):
            clean_url = f"https://{clean_url}"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        }

        req = urllib.request.Request(clean_url, headers=headers)  # noqa: S310
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                raw_html = resp.read().decode("utf-8", errors="replace")

            # Extraer título
            title_match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
            title = html.unescape(title_match.group(1).strip()) if title_match else "Sin título"

            # Eliminar bloques de scripts, estilos, cabeceras y pies de página
            cleaned = re.sub(r"<(script|style|nav|header|footer|svg|noscript)[^>]*>.*?</\1>", "",
                             raw_html, flags=re.IGNORECASE | re.DOTALL)
            # Eliminar comentarios HTML
            cleaned = re.sub(r"<!--.*?-->", "", cleaned, flags=re.DOTALL)
            # Reemplazar saltos de bloque
            cleaned = re.sub(r"<(p|br|div|h[1-6]|li|tr)[^>]*>", "\n", cleaned, flags=re.IGNORECASE)
            # Eliminar todas las demás etiquetas
            cleaned = re.sub(r"<[^>]+>", " ", cleaned)
            # Desescapar entidades HTML y condensar espacios
            text = html.unescape(cleaned)
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            compact_text = "\n".join(lines)[:max_chars]

            return {
                "success": True,
                "url": clean_url,
                "title": title,
                "content": compact_text or "Página vacía o sin contenido legible.",
            }
        except urllib.error.HTTPError as he:
            return {"success": False, "url": clean_url, "error": f"Error HTTP {he.code}: {he.reason}"}
        except Exception as exc:
            return {"success": False, "url": clean_url, "error": str(exc)}


# Instancia singleton accesible globalmente
gui = HumanGUIAutomator()
