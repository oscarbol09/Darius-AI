"""
workspace_manager.py — Gestor Multi-Monitor, Control de Ventanas y Protocolos Win32
===================================================================================
Control nativo del espacio de trabajo en Windows para Darius AI:
  - Enumeración y posicionamiento en múltiples monitores (EnumDisplayMonitors)
  - Snap milimétrico de navegadores (Chrome/Edge) a pantallas específicas
  - Enfoque nativo de Cursor / VS Code (evitando ventanas duplicadas) con soporte F11
  - Orquestación de rutinas compuestas: "Protocolo Darius", "Modo Dev", "Modo Trading"
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger("DARIUS.Workspace")

_BASE_DIR = Path(__file__).resolve().parent

# Constantes Win32
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_GW_OWNER = 4
_GWL_EXSTYLE = -20
_WS_EX_TOOLWINDOW = 0x00000080
_SW_RESTORE = 9
_SW_SHOWMAXIMIZED = 3
_HWND_TOP = 0
_KEYEVENTF_KEYUP = 0x0002
_VK_F11 = 0x7A


# ─────────────────────────────────────────────────────────────────────────────
#  DETECCIÓN Y MONITORES WIN32
# ─────────────────────────────────────────────────────────────────────────────

def get_monitor_rects() -> list[tuple[int, int, int, int]]:
    """
    Retorna los rectángulos de todos los monitores físicos conectados (left, top, right, bottom),
    ordenados de izquierda a derecha y luego de arriba a abajo.
    """
    if sys.platform != "win32":
        return [(0, 0, 1920, 1080)]

    try:
        import ctypes
        from ctypes import wintypes

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        collected: list[tuple[int, int, int, int]] = []

        @ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(RECT),
            wintypes.LPARAM,
        )
        def _callback(_hm, _hdc, lprc, _lp):
            r = lprc.contents
            collected.append((int(r.left), int(r.top), int(r.right), int(r.bottom)))
            return True

        ctypes.windll.user32.EnumDisplayMonitors(None, None, _callback, 0)
        collected.sort(key=lambda t: (t[0], t[1]))
        return collected or [(0, 0, 1920, 1080)]
    except Exception as exc:
        log.warning(f"Error enumerando monitores: {exc}")
        return [(0, 0, 1920, 1080)]


def get_monitor_bounds(one_based_index: int = 1) -> tuple[int, int, int, int]:
    """Retorna (left, top, right, bottom) para el monitor N (1-based)."""
    rects = get_monitor_rects()
    idx = max(0, min(one_based_index - 1, len(rects) - 1))
    return rects[idx]


def get_monitor_size(one_based_index: int = 1) -> tuple[int, int]:
    """Retorna (ancho, alto) en píxeles para el monitor N."""
    left, top, right, bottom = get_monitor_bounds(one_based_index)
    return (max(320, right - left), max(240, bottom - top))


def get_monitor_count() -> int:
    """Retorna el número de monitores físicos detectados."""
    return len(get_monitor_rects())


# ─────────────────────────────────────────────────────────────────────────────
#  DETECCIÓN DE EJECUTABLES
# ─────────────────────────────────────────────────────────────────────────────

def find_chrome_executable() -> str | None:
    """Busca el ejecutable de Google Chrome en rutas estándar de Windows."""
    if sys.platform == "win32":
        for base in (
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
            os.environ.get("LOCALAPPDATA", ""),
        ):
            if not base:
                continue
            p = os.path.join(base, "Google", "Chrome", "Application", "chrome.exe")
            if os.path.isfile(p):
                return p
    return shutil.which("google-chrome") or shutil.which("chrome")


def find_cursor_executable() -> str | None:
    """Busca el ejecutable de Cursor IDE en el sistema."""
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        for sub in ("Programs\\cursor\\Cursor.exe", "Programs\\Cursor\\Cursor.exe", "Programs\\cursor\\cursor.exe"):
            if local:
                p = os.path.join(local, *sub.split("\\"))
                if os.path.isfile(p):
                    return p
    return shutil.which("cursor")


def find_vscode_executable() -> str | None:
    """Busca el ejecutable de Visual Studio Code."""
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            p = os.path.join(local, "Programs", "Microsoft VS Code", "Code.exe")
            if os.path.isfile(p):
                return p
    return shutil.which("code")


# ─────────────────────────────────────────────────────────────────────────────
#  ENFOQUE NATIVO DE VENTANAS WIN32 (CURSOR / VS CODE / NAVEGADOR)
# ─────────────────────────────────────────────────────────────────────────────

def get_process_main_hwnd(target_exe_name: str) -> int | None:
    """
    Encuentra la ventana principal más grande de un proceso dado (ej: 'Cursor.exe', 'Code.exe').
    """
    if sys.platform != "win32":
        return None

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        target_name = target_exe_name.lower()
        candidates: list[tuple[int, int]] = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _enum(hwnd: wintypes.HWND, _lp: wintypes.LPARAM) -> bool:
            if user32.GetWindow(hwnd, _GW_OWNER):
                return True
            if user32.GetWindowLongW(hwnd, _GWL_EXSTYLE) & _WS_EX_TOOLWINDOW:
                return True
            if not user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
                return True

            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == 0:
                return True

            hproc = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
            if not hproc:
                return True

            try:
                buf = ctypes.create_unicode_buffer(4096)
                sz = wintypes.DWORD(len(buf))
                if not kernel32.QueryFullProcessImageNameW(hproc, 0, buf, ctypes.byref(sz)):
                    return True
                exe_path = buf.value
            finally:
                kernel32.CloseHandle(hproc)

            if os.path.basename(exe_path).lower() != target_name:
                return True

            r = wintypes.RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
                return True

            w, h = r.right - r.left, r.bottom - r.top
            if w >= 200 and h >= 200:
                candidates.append((w * h, int(hwnd)))
            return True

        user32.EnumWindows(_enum, 0)
        if not candidates:
            return None
        return max(candidates, key=lambda t: t[0])[1]
    except Exception as exc:
        log.warning(f"Error buscando ventana de {target_exe_name}: {exc}")
        return None


def bring_window_to_foreground(hwnd: int) -> bool:
    """Restaura y trae al frente una ventana usando AttachThreadInput."""
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        import ctypes

        user32 = ctypes.windll.user32
        user32.ShowWindow(hwnd, _SW_RESTORE)

        fg = user32.GetForegroundWindow()
        tid_tgt = user32.GetWindowThreadProcessId(hwnd, None)
        tid_fg = user32.GetWindowThreadProcessId(fg, None) if fg else 0

        if tid_fg and tid_tgt:
            user32.AttachThreadInput(tid_fg, tid_tgt, True)
        user32.SetForegroundWindow(hwnd)
        if tid_fg and tid_tgt:
            user32.AttachThreadInput(tid_fg, tid_tgt, False)
        return True
    except Exception as e:
        log.warning(f"Error dando foco a ventana {hwnd}: {e}")
        return False


def send_f11_fullscreen(hwnd: int) -> None:
    """Envía la tecla F11 a la ventana para activar el modo pantalla completa."""
    if sys.platform != "win32" or not hwnd:
        return
    try:
        import ctypes

        user32 = ctypes.windll.user32
        bring_window_to_foreground(hwnd)
        user32.keybd_event(_VK_F11, 0, 0, 0)
        user32.keybd_event(_VK_F11, 0, _KEYEVENTF_KEYUP, 0)
    except Exception as exc:
        log.warning(f"Error enviando F11: {exc}")


def snap_window_to_monitor(
    hwnd: int,
    monitor_index: int,
    *,
    fullscreen: bool = False,
    window_size: tuple[int, int] | None = None,
) -> None:
    """Posiciona y redimensiona una ventana en el monitor indicado."""
    if sys.platform != "win32" or not hwnd:
        return
    try:
        import ctypes

        ml, mt, mr, mb = get_monitor_bounds(monitor_index)
        user32 = ctypes.windll.user32
        flags = 0x0040 | 0x0020  # SWP_SHOWWINDOW | SWP_FRAMECHANGED

        user32.ShowWindow(hwnd, _SW_RESTORE)
        if fullscreen:
            w, h = mr - ml, mb - mt
            x, y = ml, mt
        else:
            w, h = window_size or (1400, 900)
            x = ml + max(0, (mr - ml - w) // 2)
            y = mt + max(0, (mb - mt - h) // 2)

        user32.SetWindowPos(hwnd, _HWND_TOP, x, y, w, h, flags)

        if fullscreen:
            user32.ShowWindow(hwnd, _SW_SHOWMAXIMIZED)
            send_f11_fullscreen(hwnd)
    except Exception as exc:
        log.warning(f"Error al ubicar ventana en monitor {monitor_index}: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
#  APERTURA Y CONTROL DE APLICACIONES
# ─────────────────────────────────────────────────────────────────────────────

def focus_or_launch_cursor(fullscreen: bool = True) -> bool:
    """
    Enfoca la instancia activa de Cursor.exe si existe;
    si no está abierta, la inicia de forma independiente.
    """
    hwnd = get_process_main_hwnd("cursor.exe")
    if hwnd is not None:
        log.info(f"Enfocando instancia existente de Cursor (HWND={hwnd})")
        bring_window_to_foreground(hwnd)
        if fullscreen:
            time.sleep(0.3)
            send_f11_fullscreen(hwnd)
        return True

    # Si no hay ventana, lanzar nuevo proceso
    exe = find_cursor_executable() or find_vscode_executable()
    if not exe:
        log.warning("No se encontró ejecutable de Cursor o VS Code.")
        return False

    detached = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    subprocess.Popen([exe], creationflags=detached, stdin=subprocess.DEVNULL)  # noqa: S603
    if fullscreen and sys.platform == "win32":
        time.sleep(1.5)
        new_hwnd = get_process_main_hwnd("cursor.exe") or get_process_main_hwnd("code.exe")
        if new_hwnd:
            send_f11_fullscreen(new_hwnd)
    return True


def open_url_on_monitor(
    url: str,
    monitor_index: int = 1,
    *,
    fullscreen: bool = False,
    window_size: tuple[int, int] | None = None,
    new_window: bool = True,
) -> bool:
    """
    Abre una URL en Chrome (o navegador por defecto) posicionada en el monitor especificado.
    """
    u = url.strip()
    if not u:
        return False

    chrome = find_chrome_executable()
    if chrome:
        ml, mt, _, _ = get_monitor_bounds(monitor_index)
        args = [chrome]
        if new_window:
            args.append("--new-window")
        args.append(f"--window-position={ml},{mt}")
        if window_size:
            args.append(f"--window-size={window_size[0]},{window_size[1]}")
        if fullscreen:
            args.append("--start-fullscreen")
        args.append(u)

        detached = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        subprocess.Popen(  # noqa: S603
            args,
            creationflags=detached,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True

    # Fallback al navegador del sistema
    webbrowser.open(u)
    return True


# ─────────────────────────────────────────────────────────────────────────────
#  RUTINAS Y PROTOCOLOS DE ESPACIO DE TRABAJO (DARIUS AI)
# ─────────────────────────────────────────────────────────────────────────────

def play_spotify_or_song(uri_or_url: str) -> None:
    """Abre una pista de Spotify o enlace de audio."""
    target = uri_or_url.strip()
    if not target:
        return
    if sys.platform == "win32":
        try:
            os.startfile(target)  # noqa: S606
            return
        except Exception as e:
            log.warning(f"os.startfile falló para '{target}': {e}")
    webbrowser.open(target)


def run_darius_welcome_protocol(
    talk_fn: Callable[[str], None] | None = None,
    song_url: str = "",
    claude_url: str = "https://claude.ai/new",
    monitor_claude: int = 1,
    monitor_secondary: int = 2,
    secondary_url: str = "",
    welcome_phrase: str = "",
) -> None:
    """
    Ejecuta el protocolo de bienvenida y preparación de estación de Darius AI:
      1. Inicia reproducción de música/audio opcional.
      2. Abre herramientas web / dashboards en monitores designados.
      3. Sintetiza frase de bienvenida.
      4. Trae al frente el editor de código (Cursor) en pantalla completa.
    """
    log.info("⚡ [Protocolo Darius] Iniciando secuencia de bienvenida...")

    # 1. Música de fondo
    if song_url.strip():
        play_spotify_or_song(song_url)
        time.sleep(0.8)

    # 2. Navegador con Claude / herramientas en monitor configurado
    if claude_url.strip():
        open_url_on_monitor(claude_url, monitor_index=monitor_claude, fullscreen=True)

    if secondary_url.strip() and get_monitor_count() > 1:
        open_url_on_monitor(secondary_url, monitor_index=monitor_secondary, fullscreen=True)

    # 3. Frase de bienvenida
    phrase = welcome_phrase.strip() or (
        "Bienvenido de vuelta, Óscar. Todos los sistemas de Darius AI han sido inicializados. "
        "Espacio de desarrollo y métricas listos."
    )
    if talk_fn:
        talk_fn(phrase)

    # 4. Abrir/Enfocar Cursor en pantalla completa
    time.sleep(0.5)
    focus_or_launch_cursor(fullscreen=True)


# Alias de compatibilidad
run_workspace_welcome_protocol = run_darius_welcome_protocol


def run_dev_mode(talk_fn: Callable[[str], None] | None = None) -> None:
    """Activa el modo de desarrollo: Cursor fullscreen + Claude en monitor secundario."""
    if talk_fn:
        talk_fn("Activando modo de desarrollo. Preparando entorno de código y asistencia.")
    open_url_on_monitor("https://claude.ai/new", monitor_index=2 if get_monitor_count() > 1 else 1, fullscreen=False)
    focus_or_launch_cursor(fullscreen=True)


def run_trading_mode(talk_fn: Callable[[str], None] | None = None) -> None:
    """Activa el modo de trading / análisis de mercados."""
    if talk_fn:
        talk_fn("Activando modo de mercados. Abriendo gráficas y monitoreo financiero.")
    open_url_on_monitor("https://www.binance.com/en/trade/BTC_USDT", monitor_index=1, fullscreen=True)
    if get_monitor_count() > 1:
        open_url_on_monitor("https://tasaradar.com", monitor_index=2, fullscreen=True)
