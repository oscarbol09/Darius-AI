"""
DARIUS AI - Asistente de escritorio con voz para Windows
=========================================================
Mejoras v3:  Wake word, animación de ondas, memoria, mutex, TTS worker, campo de texto
Mejoras v4:  windows_commands.py — paneles del SO, fuzzy matching semántico
Mejoras v5:  SYSTEM_ACTIONS — subprocesos reales, confirmación de voz, salidas TTS
Mejoras v6:  Modos PTT / NOMBRE / AUTO, selector en UI, indicador de modo
Correcciones v6.1:
  - BUG 1 FIX: cutoff fuzzy subido (0.52→0.75 en SYSTEM_ACTIONS) en windows_commands.py
    Previene que "cuanto es 2x2" matchee "ver espacio en disco"
  - BUG 2 FIX: execute_command limpia el nombre ANTES de evaluar patrones, así
    "darius suspende el equipo" no llega con "darius" al fuzzy de windows_commands
  - BUG 3 FIX: regex de apagar/reiniciar ampliados para capturar todas las variantes:
    "apagate", "apaga el pc", "apaga el equipo", "apaga la máquina"
    "reinicia el equipo", "reinicia el pc"
  - BUG 4 FIX: "cerrar sesion" y "cierra la sesion" ahora matchean _cmd_accion
    correctamente en vez de caer a Gemini
  - _cmd_accion ya no captura preguntas genéricas ("cuanto es X") — usa lista de
    palabras clave exclusivamente relacionadas con el SO
"""

import contextlib
import datetime
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.parse
import urllib.request
import webbrowser
import winreg
from difflib import SequenceMatcher, get_close_matches
from pathlib import Path

import customtkinter as ctk
import numpy as np
import speech_recognition as sr
import win32api
import win32com.client
import win32event
import winerror
from dotenv import load_dotenv

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

import gui_theme as theme
from acoustic_trigger import AcousticDoubleClapDetector, auto_select_best_mic
from obsidian_brain import brain
from tts_worker import TTSWorker
from voice_filter import (
    LISTEN_MODE_AUTO,
    LISTEN_MODE_NAME,
    LISTEN_MODE_PTT,
    _strip_name,
    check_name_in_text,
)
from windows_commands import (
    resolve_action as wincmd_resolve_action,
)
from windows_commands import (
    resolve_and_launch as wincmd_launch,
)
from windows_commands import (
    run_action as wincmd_run_action,
)
from workspace_manager import (
    focus_or_launch_cursor,
    get_monitor_count,
    get_monitor_rects,
    run_darius_welcome_protocol,
    run_dev_mode,
    run_trading_mode,
)

load_dotenv()

from config_loader import cfg, get_user_data_dir  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
#  INSTANCIA ÚNICA
# ─────────────────────────────────────────────────────────────────────────────

_MUTEX_NAME   = "Global\\DariusAI_SingleInstance"
_mutex_handle = win32event.CreateMutex(None, False, _MUTEX_NAME)
if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
    import tkinter.messagebox as mb
    mb.showerror("DARIUS AI", "Ya hay una instancia de Darius en ejecución.")
    sys.exit(0)

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────────────────

ASSISTANT_NAME       = cfg.assistant_name
USER_NAME            = cfg.user_name
GEMINI_MODEL         = cfg.gemini_model
GEMINI_MAX_TOKENS    = cfg.gemini_max_tokens
GEMINI_TEMPERATURE   = cfg.gemini_temperature
GEMINI_HISTORY_TURNS = cfg.gemini_history_turns
TTS_RATE             = cfg.tts_rate
TTS_VOLUME           = cfg.tts_volume
MIC_ENERGY_THRESHOLD = cfg.mic_energy_threshold
MIC_PAUSE_THRESHOLD  = cfg.mic_pause_threshold
MIC_LISTEN_TIMEOUT   = cfg.mic_listen_timeout
MIC_PHRASE_LIMIT     = cfg.mic_phrase_limit
APP_CACHE_HOURS      = cfg.app_cache_hours
SPEAKING_TAIL_SECS   = cfg.speaking_tail_secs
LISTEN_KEY             = cfg.listen_key
DEFAULT_LISTEN_MODE    = cfg.default_listen_mode
NAME_SIMILARITY_CUTOFF = cfg.name_similarity_cutoff
MIN_WORDS_WITHOUT_NAME = cfg.min_words_without_name

DATA_DIR        = get_user_data_dir()
LOG_FILE        = DATA_DIR / "darius.log"
CHAT_FILE       = DATA_DIR / "chat_history.txt"
APP_CACHE       = DATA_DIR / "apps_cache.json"
MAX_CHAT_LINES  = 10000

# ─────────────────────────────────────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("DARIUS")

from ai_client import get_ai_response  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
#  CONTROL DE VOLUMEN
# ─────────────────────────────────────────────────────────────────────────────

try:
    from ctypes import POINTER, cast

    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    _sessions    = AudioUtilities.GetSpeakers()
    _interface   = _sessions.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    _volume_ctrl = cast(_interface, POINTER(IAudioEndpointVolume))
    PYCAW_AVAILABLE = True
except Exception:
    _volume_ctrl    = None
    PYCAW_AVAILABLE = False

def volume_up():
    if PYCAW_AVAILABLE:
        _volume_ctrl.SetMasterVolumeLevelScalar(min(1.0, _volume_ctrl.GetMasterVolumeLevelScalar() + 0.1), None)
    else:
        subprocess.run(["nircmd.exe", "changesysvolume", "5000"], shell=False)  # noqa: S607

def volume_down():
    if PYCAW_AVAILABLE:
        _volume_ctrl.SetMasterVolumeLevelScalar(max(0.0, _volume_ctrl.GetMasterVolumeLevelScalar() - 0.1), None)
    else:
        subprocess.run(["nircmd.exe", "changesysvolume", "-5000"], shell=False)  # noqa: S607

def volume_mute():
    if PYCAW_AVAILABLE:
        _volume_ctrl.SetMute(1, None)
    else:
        subprocess.run(["nircmd.exe", "mutesysvolume", "1"], shell=False)  # noqa: S607

# ─────────────────────────────────────────────────────────────────────────────
#  WAKE WORD / TECLADO
# ─────────────────────────────────────────────────────────────────────────────

try:
    import pvporcupine  # noqa: F401 — availability check
    import pyaudio  # noqa: F401 — availability check
    PORCUPINE_AVAILABLE = True
except ImportError:
    PORCUPINE_AVAILABLE = False

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False
    log.warning("'keyboard' no instalado — instala con: pip install keyboard")


# ─────────────────────────────────────────────────────────────────────────────
#  SOPORTE HIGH-DPI Y HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def enable_dpi_awareness():
    """Habilita DPI awareness en Windows para nitidez en pantallas de alta resolución."""
    if sys.platform == "win32":
        with contextlib.suppress(Exception):
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
            return
        with contextlib.suppress(Exception):
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()


# ─────────────────────────────────────────────────────────────────────────────
#  VISUALIZADOR VECTORIAL DE ONDAS A 60 FPS (Senior Craftsmanship)
# ─────────────────────────────────────────────────────────────────────────────

class HighPerfWaveVisualizer(ctk.CTkFrame):
    """
    Visualizador vectorial de ondas a 60 FPS con múltiples armónicos sinusoidales vectorizados en NumPy.
    Utiliza actualizaciones atómicas con canvas.coords() eliminando canvas.delete('all')
    para evitar fugas de memoria en el intérprete Tcl y parpadeos visuales.
    """

    def __init__(self, master, width: int = 170, height: int = 36, num_points: int = 80, **kwargs):
        super().__init__(
            master,
            fg_color=theme.BG_HEADER,
            corner_radius=theme.RADIUS_MD,
            border_width=0,
            **kwargs
        )
        self.w = width
        self.h = height
        self.num_points = num_points
        self.cy = height / 2.0

        self.canvas = tk.Canvas(
            self,
            width=self.w,
            height=self.h,
            bg=theme.BG_HEADER,
            highlightthickness=0,
            bd=0
        )
        self.canvas.pack(fill="both", expand=True, padx=4, pady=2)

        # Precalcular proyecciones de coordenadas X estáticas
        self.x_screen = np.linspace(0, self.w, self.num_points, dtype=np.float32)
        self.x_norm = np.linspace(0, 4.0 * np.pi, self.num_points, dtype=np.float32)

        # Buffers preasignados de coordenadas (x0, y0, x1, y1...) para evitar reallocaciones
        self._buf_primary = np.empty((self.num_points, 2), dtype=np.float32)
        self._buf_primary[:, 0] = self.x_screen
        self._buf_primary[:, 1] = self.cy

        self._buf_secondary = np.empty((self.num_points, 2), dtype=np.float32)
        self._buf_secondary[:, 0] = self.x_screen
        self._buf_secondary[:, 1] = self.cy

        self._buf_tertiary = np.empty((self.num_points, 2), dtype=np.float32)
        self._buf_tertiary[:, 0] = self.x_screen
        self._buf_tertiary[:, 1] = self.cy

        # Crear líneas vectoriales una sola vez durante la inicialización
        self.line_tertiary = self.canvas.create_line(
            *self._buf_tertiary.ravel().tolist(),
            fill=theme.ACCENT_EMERALD,
            width=1.0,
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND
        )
        self.line_secondary = self.canvas.create_line(
            *self._buf_secondary.ravel().tolist(),
            fill=theme.ACCENT_PURPLE,
            width=1.5,
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND
        )
        self.line_primary = self.canvas.create_line(
            *self._buf_primary.ravel().tolist(),
            fill=theme.ACCENT_PRIMARY,
            width=2.0,
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND
        )

        self._phase = 0.0

    def update_frame(self, state: str, audio_energy: float = 0.0):
        """
        Calcula la proyección matemática en NumPy y actualiza las líneas atómicamente.
        state: 'IDLE' | 'LISTENING' | 'THINKING' | 'SPEAKING' | 'MUTED'
        """
        self._phase += 0.07
        p = self._phase
        x = self.x_norm
        cy = self.cy

        if state == "LISTENING":
            amp = float(np.clip(audio_energy / 2500.0 * 12.0 + 2.0, 2.0, 14.0))
            y1 = cy + amp * np.sin(2.0 * x + p) * np.cos(0.8 * x - p * 0.4)
            y2 = cy + (amp * 0.65) * np.sin(3.2 * x - p * 1.2 + 1.0)
            y3 = cy + (amp * 0.35) * np.cos(1.5 * x + p * 0.8)
            self.canvas.itemconfig(self.line_primary, fill=theme.ACCENT_PRIMARY)
            self.canvas.itemconfig(self.line_secondary, fill=theme.ACCENT_PURPLE)
            self.canvas.itemconfig(self.line_tertiary, fill=theme.ACCENT_EMERALD)

        elif state == "SPEAKING":
            y1 = cy + 9.0 * np.sin(2.5 * x + p * 1.6) * np.sin(0.7 * x + p * 0.3)
            y2 = cy + 6.0 * np.cos(3.0 * x - p * 1.3)
            y3 = cy + 3.0 * np.sin(1.2 * x + p * 0.5)
            self.canvas.itemconfig(self.line_primary, fill=theme.ACCENT_PRIMARY)
            self.canvas.itemconfig(self.line_secondary, fill="#60A5FA")
            self.canvas.itemconfig(self.line_tertiary, fill=theme.ACCENT_PURPLE)

        elif state == "THINKING":
            y1 = cy + 6.0 * np.sin(5.5 * x + p * 2.2) * np.cos(2.0 * x - p)
            y2 = cy + 4.0 * np.sin(4.0 * x - p * 1.8 + 0.5)
            y3 = cy + 2.5 * np.cos(2.5 * x + p * 1.2)
            self.canvas.itemconfig(self.line_primary, fill=theme.ACCENT_PURPLE)
            self.canvas.itemconfig(self.line_secondary, fill="#C084FC")
            self.canvas.itemconfig(self.line_tertiary, fill="#F472B6")

        elif state == "MUTED":
            y1 = cy + 0.5 * np.sin(1.0 * x + p * 0.2)
            y2 = cy + 0.3 * np.cos(1.0 * x + p * 0.2)
            y3 = cy + np.zeros_like(x)
            self.canvas.itemconfig(self.line_primary, fill=theme.TEXT_MUTED)
            self.canvas.itemconfig(self.line_secondary, fill=theme.BORDER_SUBTLE)
            self.canvas.itemconfig(self.line_tertiary, fill=theme.BG_SIDEBAR)

        else:  # IDLE
            y1 = cy + 2.5 * np.sin(1.8 * x + p * 0.6)
            y2 = cy + 1.5 * np.cos(1.2 * x - p * 0.4 + 0.8)
            y3 = cy + 0.8 * np.sin(0.8 * x + p * 0.3)
            self.canvas.itemconfig(self.line_primary, fill=theme.ACCENT_PRIMARY)
            self.canvas.itemconfig(self.line_secondary, fill=theme.ACCENT_PURPLE)
            self.canvas.itemconfig(self.line_tertiary, fill=theme.ACCENT_EMERALD)

        self._buf_primary[:, 1] = y1
        self._buf_secondary[:, 1] = y2
        self._buf_tertiary[:, 1] = y3

        # Actualizaciones atómicas en Tcl
        self.canvas.coords(self.line_tertiary, *self._buf_tertiary.ravel().tolist())
        self.canvas.coords(self.line_secondary, *self._buf_secondary.ravel().tolist())
        self.canvas.coords(self.line_primary, *self._buf_primary.ravel().tolist())


# ─────────────────────────────────────────────────────────────────────────────
#  CLASE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

class DariusFinal(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title(theme.WINDOW_TITLE)
        self.geometry(f"{theme.WINDOW_WIDTH}x{theme.WINDOW_HEIGHT}")
        self.minsize(theme.WINDOW_MIN_WIDTH, theme.WINDOW_MIN_HEIGHT)
        self.configure(fg_color=theme.BG_CANVAS)
        self.protocol("WM_DELETE_WINDOW", self.kill_process)

        icon_path = Path(__file__).resolve().parent / "assets" / "darius.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception as e:
                log.debug(f"No se pudo cargar iconbitmap: {e}")

        self.running              = True
        self.is_listening         = False
        self.waiting_for_command  = False
        self.is_muted             = False
        self.installed_apps       = {}
        self._current_audio_level = 0.0
        self._smoothed_energy     = 0.0
        self._is_thinking         = False
        self._pending_action: dict | None = None
        self._pending_lock        = threading.RLock()
        self._chat_file_lock      = threading.Lock()
        self._mic_device_index: int | None = None
        self._ptt_active          = False

        self.listen_mode = DEFAULT_LISTEN_MODE
        self.conversation_history: list[dict] = []

        self.setup_tts_config()
        self.tts_worker = TTSWorker(voice_token=self.tts_voice_token)
        self.tts_worker.start()
        self.listener = sr.Recognizer()
        self.configure_listener()

        # Detector de doble aplauso (Protocolo Darius / Acoustic Trigger)
        self._clap_detector = AcousticDoubleClapDetector(
            on_trigger=self._on_acoustic_double_clap,
            spike_ratio=cfg.acoustic_trigger_spike_ratio,
            cooldown_s=cfg.acoustic_trigger_cooldown_s,
            device_spec=cfg.acoustic_trigger_device,
            is_speaking_fn=lambda: self.tts_worker.is_speaking.is_set(),
        )
        if cfg.acoustic_trigger_enabled:
            self._clap_detector.start()

        self.setup_ui()
        self.scan_apps_async()
        self._start_render_pipeline()

    # =========================================================================
    #  TTS / VOZ
    # =========================================================================

    def setup_tts_config(self):
        temp   = win32com.client.Dispatch("SAPI.SpVoice")
        voices = temp.GetVoices()
        self.tts_voice_token = None
        for i in range(voices.Count):
            v    = voices.Item(i)
            desc = v.GetDescription()
            log.info(f"  Voz [{i}] {desc}")
            if any(k in desc.lower() for k in ["spanish", "helena", "sabina", "es-es", "español"]):
                self.tts_voice_token = v
                log.info(f"Voz seleccionada: {desc}")
        if not self.tts_voice_token and voices.Count > 0:
            self.tts_voice_token = voices.Item(0)

    def configure_listener(self):
        self.listener.energy_threshold         = MIC_ENERGY_THRESHOLD
        self.listener.dynamic_energy_threshold = True
        self.listener.pause_threshold          = MIC_PAUSE_THRESHOLD
        self.listener.non_speaking_duration    = 0.5
        try:
            self._mic_device_index = auto_select_best_mic(cfg.acoustic_trigger_device)
            mic_kwargs = {"device_index": self._mic_device_index} if self._mic_device_index is not None else {}
            with sr.Microphone(**mic_kwargs) as source:
                self.listener.adjust_for_ambient_noise(source, duration=1)
            log.info(f"Calibración completada en dispositivo {self._mic_device_index}.")
        except Exception as e:
            log.warning(f"No se pudo calibrar el micrófono: {e}")

    def talk(self, text: str):
        log.info(f"DARIUS: {text}")
        self.after(0, self._insert_message, "Darius", text)
        self._append_chat_file("DARIUS", text)
        if not self.is_muted:
            self.tts_worker.speak(text)

    # =========================================================================
    #  HISTORIAL
    # =========================================================================

    def _append_chat_file(self, speaker: str, text: str):
        with self._chat_file_lock:
            try:
                ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(CHAT_FILE, "a", encoding="utf-8") as f:
                    f.write(f"[{ts}] {speaker}: {text}\n")
                self._trim_chat_file()
            except Exception as e:
                log.warning(f"No se pudo escribir historial local: {e}")

    def _trim_chat_file(self):
        # Nota: asume que el lock _chat_file_lock ya está adquirido por _append_chat_file
        try:
            if not CHAT_FILE.exists():
                return
            with open(CHAT_FILE, encoding="utf-8") as f:
                lines = f.readlines()
            if len(lines) > MAX_CHAT_LINES:
                with open(CHAT_FILE, "w", encoding="utf-8") as f:
                    f.writelines(lines[-int(MAX_CHAT_LINES * 0.8):])
        except Exception as e:
            log.warning(f"No se pudo rotar historial: {e}")

    # =========================================================================
    #  UI
    # =========================================================================

    def setup_ui(self):
        # ── GRID CONFIGURATION ──────────────────────────────────────────────
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0, minsize=theme.SIDEBAR_WIDTH)
        self.grid_columnconfigure(1, weight=1)

        # ── 1. LEFT SIDEBAR ─────────────────────────────────────────────────
        self.sidebar_frame = ctk.CTkFrame(
            self,
            width=theme.SIDEBAR_WIDTH,
            fg_color=theme.BG_SIDEBAR,
            corner_radius=0,
            border_width=1,
            border_color=theme.BORDER_SUBTLE,
        )
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_propagate(False)

        # 1.1 Brand Header
        brand_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        brand_frame.pack(fill="x", padx=14, pady=(14, 8))

        brand_icon_row = ctk.CTkFrame(brand_frame, fg_color="transparent")
        brand_icon_row.pack(fill="x")

        logo_path = Path(__file__).resolve().parent / "assets" / "logo_icon.png"
        if PIL_AVAILABLE and logo_path.exists():
            try:
                pil_logo = Image.open(logo_path)
                self._sidebar_logo_img = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(24, 24))
                ctk.CTkLabel(brand_icon_row, text="", image=self._sidebar_logo_img).pack(side="left", padx=(0, 8))
            except Exception as e:
                log.debug(f"Logo sidebar no disponible: {e}")

        brand_text_col = ctk.CTkFrame(brand_icon_row, fg_color="transparent")
        brand_text_col.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            brand_text_col,
            text="DARIUS AI",
            font=theme.FONT_TITLE,
            text_color=theme.ACCENT_PRIMARY,
            anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            brand_text_col,
            text=f"Copiloto Windows • {theme.VERSION_TAG}",
            font=theme.FONT_CAPTION,
            text_color=theme.TEXT_MUTED,
            anchor="w",
        ).pack(fill="x")

        # Hairline divider
        ctk.CTkFrame(self.sidebar_frame, height=1, fg_color=theme.BORDER_SUBTLE).pack(fill="x", padx=12, pady=6)

        # 1.2 Navigation Menu
        ctk.CTkLabel(
            self.sidebar_frame,
            text="VISTAS",
            font=theme.FONT_CAPTION_BOLD,
            text_color=theme.TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", padx=14, pady=(2, 4))

        self._nav_btns = {}
        views = [
            ("chat", "💬 Conversación"),
            ("workspaces", "⚡ Workspaces"),
            ("obsidian", "🧠 Obsidian Brain"),
            ("system", "🛠 Sistema & Audio"),
        ]

        for view_id, label in views:
            btn = ctk.CTkButton(
                self.sidebar_frame,
                text=f"  {label}",
                font=theme.FONT_NAV,
                height=32,
                corner_radius=theme.RADIUS_MD,
                fg_color=theme.BG_CARD_HOVER if view_id == "chat" else "transparent",
                hover_color=theme.BG_CARD_HOVER,
                text_color=theme.ACCENT_PRIMARY if view_id == "chat" else theme.TEXT_SECONDARY,
                anchor="w",
                command=lambda v=view_id: self._show_page(v),
            )
            btn.pack(fill="x", padx=10, pady=2)
            self._nav_btns[view_id] = btn

        # Hairline divider
        ctk.CTkFrame(self.sidebar_frame, height=1, fg_color=theme.BORDER_SUBTLE).pack(fill="x", padx=12, pady=8)

        # 1.3 Telemetry & Mode Selector
        ctk.CTkLabel(
            self.sidebar_frame,
            text="ACTIVACIÓN DE VOZ",
            font=theme.FONT_CAPTION_BOLD,
            text_color=theme.TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", padx=14, pady=(0, 4))

        mode_row = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        mode_row.pack(fill="x", padx=10, pady=(0, 4))

        self._mode_btns = {}
        modes = [
            (LISTEN_MODE_PTT, "🎙 PTT", theme.ACCENT_PRIMARY),
            (LISTEN_MODE_NAME, "🔤 NOM", theme.ACCENT_EMERALD),
            (LISTEN_MODE_AUTO, "🔄 AUTO", theme.ACCENT_PURPLE),
        ]
        for mode_id, label, active_color in modes:
            is_active = (mode_id == self.listen_mode)
            btn = ctk.CTkButton(
                mode_row,
                text=label,
                fg_color=active_color if is_active else theme.BG_PILL,
                hover_color=active_color,
                text_color=theme.BG_CANVAS if is_active else theme.TEXT_SECONDARY,
                border_color=active_color if is_active else theme.BORDER_SUBTLE,
                border_width=1,
                font=theme.FONT_CAPTION_BOLD,
                height=26,
                corner_radius=theme.RADIUS_SM,
                command=lambda m=mode_id: self._set_listen_mode(m),
            )
            btn.pack(side="left", fill="x", expand=True, padx=2)
            self._mode_btns[mode_id] = (btn, active_color)

        self.ptt_hint = ctk.CTkLabel(
            self.sidebar_frame,
            text=f"Mantén [{LISTEN_KEY.upper()}] presionado",
            font=theme.FONT_CAPTION,
            text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        if self.listen_mode == LISTEN_MODE_PTT:
            self.ptt_hint.pack(fill="x", padx=14, pady=(0, 4))

        # Telemetry Badges
        ctk.CTkLabel(
            self.sidebar_frame,
            text="ESTADO DE SISTEMAS",
            font=theme.FONT_CAPTION_BOLD,
            text_color=theme.TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", padx=14, pady=(6, 4))

        telemetry_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        telemetry_frame.pack(fill="x", padx=10, pady=0)

        # Clap trigger button
        clap_active = hasattr(self, "_clap_detector") and self._clap_detector.is_running()
        self.clap_btn = ctk.CTkButton(
            telemetry_frame,
            text=self._clap_badge_text(),
            font=theme.FONT_BADGE,
            text_color=theme.ACCENT_EMERALD if clap_active else theme.TEXT_SECONDARY,
            fg_color=theme.BG_PILL,
            hover_color=theme.BG_CARD_HOVER,
            border_color=theme.BORDER_SUBTLE,
            border_width=1,
            corner_radius=theme.RADIUS_SM,
            height=24,
            anchor="w",
            command=self.toggle_clap_detector,
        )
        self.clap_btn.pack(fill="x", pady=2)

        # LLM Pill
        self.llm_pill = ctk.CTkLabel(
            telemetry_frame,
            text=self._llm_badge_text(),
            font=theme.FONT_BADGE,
            text_color=theme.ACCENT_PRIMARY,
            fg_color=theme.BG_PILL,
            corner_radius=theme.RADIUS_SM,
            padx=8,
            pady=3,
            anchor="w",
        )
        self.llm_pill.pack(fill="x", pady=2)

        # Obsidian Pill
        obsidian_connected = bool(brain.vault_path and Path(brain.vault_path).exists())
        obsidian_text = "CONECTADO" if obsidian_connected else "LOCAL"
        obsidian_color = theme.ACCENT_EMERALD if obsidian_connected else theme.TEXT_MUTED
        self.brain_pill = ctk.CTkLabel(
            telemetry_frame,
            text=f"🧠 OBSIDIAN: {obsidian_text}",
            font=theme.FONT_BADGE,
            text_color=obsidian_color,
            fg_color=theme.BG_PILL,
            corner_radius=theme.RADIUS_SM,
            padx=8,
            pady=3,
            anchor="w",
        )
        self.brain_pill.pack(fill="x", pady=2)

        # TTS Pill
        self.tts_pill = ctk.CTkLabel(
            telemetry_frame,
            text=self._tts_badge_text(),
            font=theme.FONT_BADGE,
            text_color=theme.ACCENT_AMBER,
            fg_color=theme.BG_PILL,
            corner_radius=theme.RADIUS_SM,
            padx=8,
            pady=3,
            anchor="w",
        )
        self.tts_pill.pack(fill="x", pady=2)

        # Apps Pill
        self.apps_pill = ctk.CTkLabel(
            telemetry_frame,
            text=f"📦 {len(self.installed_apps)} APPS",
            font=theme.FONT_BADGE,
            text_color=theme.TEXT_SECONDARY,
            fg_color=theme.BG_PILL,
            corner_radius=theme.RADIUS_SM,
            padx=8,
            pady=3,
            anchor="w",
        )
        self.apps_pill.pack(fill="x", pady=2)

        # Monitors Pill
        self.monitors_pill = ctk.CTkLabel(
            telemetry_frame,
            text=f"🖥 {get_monitor_count()} PANTALLA{'S' if get_monitor_count() > 1 else ''}",
            font=theme.FONT_BADGE,
            text_color=theme.ACCENT_PURPLE,
            fg_color=theme.BG_PILL,
            corner_radius=theme.RADIUS_SM,
            padx=8,
            pady=3,
            anchor="w",
        )
        self.monitors_pill.pack(fill="x", pady=2)

        # 1.4 Sidebar Footer (Settings & Author Attribution)
        footer_spacer = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        footer_spacer.pack(fill="both", expand=True)

        footer_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        footer_frame.pack(fill="x", padx=10, pady=(0, 10))

        # BYOK Settings button
        ctk.CTkButton(
            footer_frame,
            text="⚙ AJUSTES IA / MODELOS",
            height=28,
            fg_color=theme.BG_CARD_INNER,
            hover_color=theme.BG_CARD_HOVER,
            border_color=theme.BORDER_SUBTLE,
            border_width=1,
            text_color=theme.ACCENT_PRIMARY,
            font=theme.FONT_CAPTION_BOLD,
            corner_radius=theme.RADIUS_SM,
            command=self._open_byok_settings,
        ).pack(fill="x", pady=(0, 6))

        # Author Attribution (Discreet link to Github)
        ctk.CTkButton(
            footer_frame,
            text=f"{theme.AUTHOR_TAG} • GPLv3",
            height=22,
            fg_color="transparent",
            hover_color=theme.BG_CARD_HOVER,
            text_color=theme.TEXT_MUTED,
            font=theme.FONT_CAPTION,
            corner_radius=theme.RADIUS_SM,
            command=self._open_author_github,
        ).pack(fill="x")

        # ── 2. RIGHT MAIN STUDIO PANE ───────────────────────────────────────
        self.main_studio_frame = ctk.CTkFrame(self, fg_color=theme.BG_CANVAS, corner_radius=0)
        self.main_studio_frame.grid(row=0, column=1, sticky="nsew")
        self.main_studio_frame.grid_rowconfigure(1, weight=1)
        self.main_studio_frame.grid_columnconfigure(0, weight=1)

        # 2.1 Top Studio Header
        header_card = ctk.CTkFrame(
            self.main_studio_frame,
            fg_color=theme.BG_HEADER,
            corner_radius=theme.RADIUS_LG,
            border_width=1,
            border_color=theme.BORDER_CARD,
            height=52,
        )
        header_card.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))

        # Left: Status Indicator
        status_box = ctk.CTkFrame(header_card, fg_color="transparent")
        status_box.pack(side="left", padx=(12, 8), pady=8)

        self.status_dot = ctk.CTkLabel(
            status_box,
            text="●",
            font=("Segoe UI", 13),
            text_color=theme.ACCENT_EMERALD,
        )
        self.status_dot.pack(side="left", padx=(0, 5))

        self.status_label = ctk.CTkLabel(
            status_box,
            text="SISTEMA LISTO",
            font=theme.FONT_SUBTITLE,
            text_color=theme.TEXT_PRIMARY,
        )
        self.status_label.pack(side="left")

        # Center: Waveform Visualizer
        self.visualizer = HighPerfWaveVisualizer(header_card, width=170, height=36)
        self.visualizer.pack(side="left", padx=12, pady=6, fill="y")

        # Right: Quick Action Buttons
        actions_box = ctk.CTkFrame(header_card, fg_color="transparent")
        actions_box.pack(side="right", padx=(8, 12), pady=8)

        self.clear_btn = ctk.CTkButton(
            actions_box,
            text="🗑 LIMPIAR",
            width=78,
            height=30,
            fg_color=theme.BG_CARD_INNER,
            hover_color=theme.BG_CARD_HOVER,
            text_color=theme.TEXT_PRIMARY,
            font=theme.FONT_CAPTION_BOLD,
            border_color=theme.BORDER_SUBTLE,
            border_width=1,
            corner_radius=theme.RADIUS_SM,
            command=self.reset_conversation,
        )
        self.clear_btn.pack(side="right", padx=(4, 0))

        self.mute_btn = ctk.CTkButton(
            actions_box,
            text="🔇 SILENCIO",
            width=82,
            height=30,
            fg_color=theme.ACCENT_ROSE,
            hover_color="#E11D48",
            text_color=theme.TEXT_PRIMARY,
            state="disabled",
            font=theme.FONT_CAPTION_BOLD,
            corner_radius=theme.RADIUS_SM,
            command=self.toggle_mute,
        )
        self.mute_btn.pack(side="right", padx=4)

        self.start_btn = ctk.CTkButton(
            actions_box,
            text="⚡ INICIAR",
            width=82,
            height=30,
            fg_color=theme.ACCENT_PRIMARY,
            hover_color=theme.ACCENT_PRIMARY_HOVER,
            text_color=theme.BG_CANVAS,
            font=theme.FONT_CAPTION_BOLD,
            corner_radius=theme.RADIUS_SM,
            command=self.start_system,
        )
        self.start_btn.pack(side="right", padx=(0, 4))

        # 2.2 View Container (Stacked Views)
        self.view_container = ctk.CTkFrame(self.main_studio_frame, fg_color="transparent")
        self.view_container.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 6))
        self.view_container.grid_rowconfigure(0, weight=1)
        self.view_container.grid_columnconfigure(0, weight=1)

        self._pages = {}

        # ── Page: Chat ──
        page_chat = ctk.CTkFrame(
            self.view_container,
            fg_color=theme.BG_CARD,
            corner_radius=theme.RADIUS_LG,
            border_width=1,
            border_color=theme.BORDER_CARD,
        )
        page_chat.grid(row=0, column=0, sticky="nsew")
        self._pages["chat"] = page_chat

        chat_hdr = ctk.CTkFrame(page_chat, fg_color="transparent")
        chat_hdr.pack(fill="x", padx=12, pady=(8, 2))

        ctk.CTkLabel(
            chat_hdr,
            text="HISTORIAL DE ACTIVIDAD & COMANDOS",
            font=theme.FONT_CAPTION_BOLD,
            text_color=theme.TEXT_MUTED,
        ).pack(side="left")

        self.mode_pill = ctk.CTkLabel(
            chat_hdr,
            text=self._mode_label_text(),
            font=theme.FONT_CAPTION_BOLD,
            text_color=theme.ACCENT_PRIMARY,
        )
        self.mode_pill.pack(side="right")

        self.chat_display = ctk.CTkTextbox(
            page_chat,
            font=(theme.FONT_MONO_FAMILY, 11),
            state="disabled",
            fg_color=theme.BG_CANVAS,
            border_color=theme.BORDER_SUBTLE,
            border_width=1,
            scrollbar_button_color=theme.BG_SIDEBAR,
            scrollbar_button_hover_color=theme.ACCENT_PRIMARY,
        )
        self.chat_display.pack(padx=10, pady=(2, 10), fill="both", expand=True)

        tb = self.chat_display._textbox
        tb.tag_config("oscar", foreground=theme.ACCENT_EMERALD, font=(theme.FONT_MONO_FAMILY, 11, "bold"))
        tb.tag_config("darius", foreground=theme.ACCENT_PRIMARY, font=(theme.FONT_MONO_FAMILY, 11, "bold"))
        tb.tag_config("system", foreground=theme.ACCENT_PURPLE, font=(theme.FONT_MONO_FAMILY, 11, "bold"))
        tb.tag_config("warn", foreground=theme.ACCENT_AMBER, font=(theme.FONT_MONO_FAMILY, 11, "bold"))
        tb.tag_config("oscar_text", foreground=theme.TEXT_PRIMARY, font=(theme.FONT_MONO_FAMILY, 11))
        tb.tag_config("darius_text", foreground="#E2E8F0", font=(theme.FONT_MONO_FAMILY, 11))
        tb.tag_config("system_text", foreground=theme.TEXT_SECONDARY, font=(theme.FONT_MONO_FAMILY, 11))
        tb.tag_config("timestamp", foreground=theme.TEXT_MUTED, font=(theme.FONT_MONO_FAMILY, 9))

        # ── Page: Workspaces ──
        page_ws = ctk.CTkScrollableFrame(
            self.view_container,
            fg_color=theme.BG_CARD,
            corner_radius=theme.RADIUS_LG,
            border_width=1,
            border_color=theme.BORDER_CARD,
        )
        self._pages["workspaces"] = page_ws

        ctk.CTkLabel(
            page_ws,
            text="ESPACIOS DE TRABAJO AUTOMATIZADOS",
            font=theme.FONT_SUBTITLE,
            text_color=theme.ACCENT_PRIMARY,
            anchor="w",
        ).pack(fill="x", padx=14, pady=(12, 4))
        ctk.CTkLabel(
            page_ws,
            text="Lanza y organiza entornos multitarea en tus monitores con un solo clic.",
            font=theme.FONT_CAPTION,
            text_color=theme.TEXT_SECONDARY,
            anchor="w",
        ).pack(fill="x", padx=14, pady=(0, 10))

        ws_grid = ctk.CTkFrame(page_ws, fg_color="transparent")
        ws_grid.pack(fill="x", padx=10, pady=4)
        ws_grid.grid_columnconfigure(0, weight=1)
        ws_grid.grid_columnconfigure(1, weight=1)

        def _create_ws_card(parent, row, col, title, desc, icon, cmd_fn, accent_color):
            card = ctk.CTkFrame(
                parent,
                fg_color=theme.BG_CARD_INNER,
                corner_radius=theme.RADIUS_MD,
                border_width=1,
                border_color=theme.BORDER_SUBTLE,
            )
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

            card_top = ctk.CTkFrame(card, fg_color="transparent")
            card_top.pack(fill="x", padx=10, pady=(10, 4))

            ctk.CTkLabel(card_top, text=icon, font=("Segoe UI", 16)).pack(side="left", padx=(0, 6))
            ctk.CTkLabel(card_top, text=title, font=theme.FONT_BODY_BOLD, text_color=accent_color).pack(side="left")

            ctk.CTkLabel(
                card,
                text=desc,
                font=theme.FONT_CAPTION,
                text_color=theme.TEXT_SECONDARY,
                wraplength=220,
                justify="left",
            ).pack(fill="x", padx=10, pady=(0, 10))

            ctk.CTkButton(
                card,
                text="EJECUTAR ▶",
                height=28,
                fg_color=theme.BG_CARD,
                hover_color=accent_color,
                text_color=theme.TEXT_PRIMARY,
                font=theme.FONT_CAPTION_BOLD,
                border_color=theme.BORDER_SUBTLE,
                border_width=1,
                corner_radius=theme.RADIUS_SM,
                command=cmd_fn,
            ).pack(fill="x", padx=10, pady=(0, 10))

        _create_ws_card(
            ws_grid, 0, 0, "Protocolo Darius",
            "Música de bienvenida, Cursor en pantalla principal y Claude en secundario.",
            "🚀", lambda: self._cmd_darius_protocol(None), theme.ACCENT_PRIMARY,
        )
        _create_ws_card(
            ws_grid, 0, 1, "Modo Desarrollo",
            "Lanza Cursor AI, Git y terminal de desarrollo listo para programar.",
            "💻", lambda: self._cmd_workspace_dev(None), theme.ACCENT_EMERALD,
        )
        _create_ws_card(
            ws_grid, 1, 0, "Modo Trading",
            "Abre gráficos y terminales financieras en monitores configurados.",
            "📈", lambda: self._cmd_workspace_trading(None), theme.ACCENT_AMBER,
        )
        _create_ws_card(
            ws_grid, 1, 1, "Enfocar Cursor",
            "Maximiza o enfoca la ventana activa de Cursor en pantalla completa.",
            "🎯", lambda: self._cmd_focus_cursor(None), theme.ACCENT_PURPLE,
        )
        _create_ws_card(
            ws_grid, 2, 0, "Top Procesos RAM",
            "Consulta en tiempo real qué aplicaciones consumen más memoria.",
            "📊", lambda: self._cmd_top_processes(None), theme.TEXT_PRIMARY,
        )
        _create_ws_card(
            ws_grid, 2, 1, "Limpiar Caché DNS",
            "Vacía y resetea la caché de resolución de nombres DNS de Windows.",
            "🌐", lambda: self._cmd_flush_dns(None), theme.ACCENT_PRIMARY,
        )

        # ── Page: Obsidian Brain ──
        page_obs = ctk.CTkScrollableFrame(
            self.view_container,
            fg_color=theme.BG_CARD,
            corner_radius=theme.RADIUS_LG,
            border_width=1,
            border_color=theme.BORDER_CARD,
        )
        self._pages["obsidian"] = page_obs

        ctk.CTkLabel(
            page_obs,
            text="SEGUNDO CEREBRO • OBSIDIAN VAULT",
            font=theme.FONT_SUBTITLE,
            text_color=theme.ACCENT_EMERALD,
            anchor="w",
        ).pack(fill="x", padx=14, pady=(12, 4))

        vault_str = str(brain.vault_path) if brain.vault_path else "No configurado (usando carpeta local)"
        ctk.CTkLabel(
            page_obs,
            text=f"Bóveda: {vault_str}",
            font=theme.FONT_CAPTION,
            text_color=theme.TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", padx=14, pady=(0, 10))

        # Quick journal entry frame
        journal_card = ctk.CTkFrame(
            page_obs,
            fg_color=theme.BG_CARD_INNER,
            corner_radius=theme.RADIUS_MD,
            border_width=1,
            border_color=theme.BORDER_SUBTLE,
        )
        journal_card.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            journal_card,
            text="📝 Anotar en Diario / Daily Note",
            font=theme.FONT_BODY_BOLD,
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 4))

        self._journal_entry = ctk.CTkEntry(
            journal_card,
            placeholder_text="Escribe una nota para guardar en tu bitácora de hoy…",
            font=theme.FONT_BODY,
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER_SUBTLE,
            text_color=theme.TEXT_PRIMARY,
            height=34,
        )
        self._journal_entry.pack(fill="x", padx=12, pady=4)

        def _save_journal():
            txt = self._journal_entry.get().strip()
            if txt:
                brain.append_daily_note(txt)
                self._journal_entry.delete(0, "end")
                self.talk(f"Anotado en tu diario: {txt}")

        ctk.CTkButton(
            journal_card,
            text="GUARDAR EN DIARIO 💾",
            height=28,
            fg_color=theme.ACCENT_EMERALD,
            hover_color="#059669",
            text_color=theme.BG_CANVAS,
            font=theme.FONT_CAPTION_BOLD,
            corner_radius=theme.RADIUS_SM,
            command=_save_journal,
        ).pack(anchor="e", padx=12, pady=(4, 10))

        # Search Vault card
        search_card = ctk.CTkFrame(
            page_obs,
            fg_color=theme.BG_CARD_INNER,
            corner_radius=theme.RADIUS_MD,
            border_width=1,
            border_color=theme.BORDER_SUBTLE,
        )
        search_card.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            search_card,
            text="🔍 Buscar en Memoria de Obsidian",
            font=theme.FONT_BODY_BOLD,
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 4))

        search_row = ctk.CTkFrame(search_card, fg_color="transparent")
        search_row.pack(fill="x", padx=12, pady=4)

        self._obs_search_entry = ctk.CTkEntry(
            search_row,
            placeholder_text="Término o tema a buscar…",
            font=theme.FONT_BODY,
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER_SUBTLE,
            text_color=theme.TEXT_PRIMARY,
            height=34,
        )
        self._obs_search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        def _search_obs():
            q = self._obs_search_entry.get().strip()
            if q:
                self._cmd_buscar_notas(f"busca en obsidian {q}")

        ctk.CTkButton(
            search_row,
            text="BUSCAR 🔍",
            width=80,
            height=34,
            fg_color=theme.ACCENT_PRIMARY,
            hover_color=theme.ACCENT_PRIMARY_HOVER,
            text_color=theme.BG_CANVAS,
            font=theme.FONT_CAPTION_BOLD,
            corner_radius=theme.RADIUS_SM,
            command=_search_obs,
        ).pack(side="right")

        # ── Page: System & Audio ──
        page_sys = ctk.CTkScrollableFrame(
            self.view_container,
            fg_color=theme.BG_CARD,
            corner_radius=theme.RADIUS_LG,
            border_width=1,
            border_color=theme.BORDER_CARD,
        )
        self._pages["system"] = page_sys

        ctk.CTkLabel(
            page_sys,
            text="DIAGNÓSTICO & CONTROL DEL SISTEMA",
            font=theme.FONT_SUBTITLE,
            text_color=theme.ACCENT_PRIMARY,
            anchor="w",
        ).pack(fill="x", padx=14, pady=(12, 4))

        # Audio Volume Control Card
        vol_card = ctk.CTkFrame(
            page_sys,
            fg_color=theme.BG_CARD_INNER,
            corner_radius=theme.RADIUS_MD,
            border_width=1,
            border_color=theme.BORDER_SUBTLE,
        )
        vol_card.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            vol_card,
            text="🔊 Control Rápido de Volumen del Sistema",
            font=theme.FONT_BODY_BOLD,
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 6))

        vol_btn_row = ctk.CTkFrame(vol_card, fg_color="transparent")
        vol_btn_row.pack(fill="x", padx=12, pady=(0, 10))

        ctk.CTkButton(
            vol_btn_row,
            text="SUBIR VOLUMEN 🔼",
            font=theme.FONT_CAPTION_BOLD,
            fg_color=theme.BG_CARD,
            hover_color=theme.BG_CARD_HOVER,
            text_color=theme.TEXT_PRIMARY,
            border_color=theme.BORDER_SUBTLE,
            border_width=1,
            height=30,
            command=self._cmd_vol_up,
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))

        ctk.CTkButton(
            vol_btn_row,
            text="BAJAR VOLUMEN 🔽",
            font=theme.FONT_CAPTION_BOLD,
            fg_color=theme.BG_CARD,
            hover_color=theme.BG_CARD_HOVER,
            text_color=theme.TEXT_PRIMARY,
            border_color=theme.BORDER_SUBTLE,
            border_width=1,
            height=30,
            command=self._cmd_vol_down,
        ).pack(side="left", fill="x", expand=True, padx=4)

        ctk.CTkButton(
            vol_btn_row,
            text="MUTE AUDIO 🔇",
            font=theme.FONT_CAPTION_BOLD,
            fg_color=theme.BG_CARD,
            hover_color=theme.BG_CARD_HOVER,
            text_color=theme.ACCENT_ROSE,
            border_color=theme.BORDER_SUBTLE,
            border_width=1,
            height=30,
            command=self._cmd_vol_mute,
        ).pack(side="left", fill="x", expand=True, padx=(4, 0))

        # Apps database card
        apps_card = ctk.CTkFrame(
            page_sys,
            fg_color=theme.BG_CARD_INNER,
            corner_radius=theme.RADIUS_MD,
            border_width=1,
            border_color=theme.BORDER_SUBTLE,
        )
        apps_card.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            apps_card,
            text=f"📦 Catálogo de Aplicaciones ({len(self.installed_apps)} registradas)",
            font=theme.FONT_BODY_BOLD,
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkButton(
            apps_card,
            text="🔄 RE-ESCANEAR APLICACIONES DE WINDOWS",
            height=30,
            fg_color=theme.BG_CARD,
            hover_color=theme.BG_CARD_HOVER,
            text_color=theme.ACCENT_PRIMARY,
            font=theme.FONT_CAPTION_BOLD,
            border_color=theme.BORDER_SUBTLE,
            border_width=1,
            corner_radius=theme.RADIUS_SM,
            command=lambda: threading.Thread(target=self._scan_applications, daemon=True).start(),
        ).pack(fill="x", padx=12, pady=(0, 10))

        # 2.3 Bottom Command Dock
        dock_frame = ctk.CTkFrame(
            self.main_studio_frame,
            fg_color=theme.BG_CARD,
            corner_radius=theme.RADIUS_LG,
            border_width=1,
            border_color=theme.BORDER_CARD,
        )
        dock_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))

        self.text_input = ctk.CTkEntry(
            dock_frame,
            placeholder_text="Escribe un comando o consulta para Darius…",
            font=theme.FONT_BODY,
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER_SUBTLE,
            border_width=1,
            text_color=theme.TEXT_PRIMARY,
            placeholder_text_color=theme.TEXT_MUTED,
            height=38,
            corner_radius=theme.RADIUS_MD,
        )
        self.text_input.pack(side="left", fill="x", expand=True, padx=(10, 8), pady=8)
        self.text_input.bind("<Return>", self._on_text_submit)

        ctk.CTkButton(
            dock_frame,
            text="ENVIAR ▶",
            width=86,
            height=38,
            fg_color=theme.ACCENT_PRIMARY,
            hover_color=theme.ACCENT_PRIMARY_HOVER,
            text_color=theme.BG_CANVAS,
            font=theme.FONT_SUBTITLE,
            corner_radius=theme.RADIUS_MD,
            command=self._on_text_submit,
        ).pack(side="right", padx=(0, 10), pady=8)

    def _show_page(self, page_id: str):
        self.current_page = page_id
        for pid, frame in self._pages.items():
            if pid == page_id:
                frame.grid(row=0, column=0, sticky="nsew")
            else:
                frame.grid_forget()

        for pid, btn in self._nav_btns.items():
            is_active = (pid == page_id)
            btn.configure(
                fg_color=theme.BG_CARD_HOVER if is_active else "transparent",
                text_color=theme.ACCENT_PRIMARY if is_active else theme.TEXT_SECONDARY,
            )

    def _open_author_github(self):
        with contextlib.suppress(Exception):
            webbrowser.open_new_tab(theme.AUTHOR_GITHUB_URL)

    def _mode_label_text(self) -> str:
        icons = {
            LISTEN_MODE_PTT: f"🎙 PTT • [{LISTEN_KEY.upper()}]",
            LISTEN_MODE_NAME: f"🔤 NOMBRE • «{ASSISTANT_NAME}»",
            LISTEN_MODE_AUTO: "🔄 AUTO • Escucha continua",
        }
        return icons.get(self.listen_mode, "")

    def _set_listen_mode(self, mode: str):
        self.listen_mode = mode
        for mode_id, (btn, active_color) in self._mode_btns.items():
            is_active = (mode_id == mode)
            btn.configure(
                fg_color=active_color if is_active else theme.BG_PILL,
                text_color=theme.BG_CANVAS if is_active else theme.TEXT_SECONDARY,
                border_color=active_color if is_active else theme.BORDER_SUBTLE,
            )
        if hasattr(self, "mode_pill"):
            self.mode_pill.configure(text=self._mode_label_text())
        if mode == LISTEN_MODE_PTT:
            self.ptt_hint.pack(fill="x", padx=14, pady=(0, 4))
            if not KEYBOARD_AVAILABLE:
                self.talk("Advertencia: librería keyboard no instalada. Ejecuta pip install keyboard")
        else:
            with contextlib.suppress(Exception):
                self.ptt_hint.pack_forget()
        log.info(f"Modo cambiado a: {mode}")
        self.set_status(f"MODO: {mode.upper()}", theme.ACCENT_PRIMARY)

    def _llm_badge_text(self) -> str:
        prov = cfg.active_provider.upper()
        return f"🤖 IA: {prov}"

    def _clap_badge_text(self) -> str:
        state = "ON" if hasattr(self, "_clap_detector") and self._clap_detector.is_running() else "OFF"
        return f"👏 APLAUSO: {state}"

    def _tts_badge_text(self) -> str:
        eng = cfg.tts_engine.upper()
        return f"🔊 TTS: {eng}"

    def toggle_clap_detector(self):
        """Alterna el detector acústico de doble aplauso en tiempo real."""
        if self._clap_detector.is_running():
            self._clap_detector.stop()
            cfg.set(False, "acoustic_trigger", "enabled")
            self.add_to_chat("Sistema", "Detector de doble aplauso desactivado.")
        else:
            self._clap_detector.start()
            cfg.set(True, "acoustic_trigger", "enabled")
            self.add_to_chat("Sistema", "Detector de doble aplauso activado.")
        if hasattr(self, "clap_btn"):
            active = self._clap_detector.is_running()
            self.clap_btn.configure(
                text=self._clap_badge_text(),
                text_color="#34D399" if active else "#94A3B8",
            )

    def _on_acoustic_double_clap(self):
        """Manejador de evento de doble aplauso acústico."""
        if self.is_muted or self.tts_worker.is_speaking.is_set():
            return
        log.info("👏 [Trigger] Doble aplauso recibido en Darius.")
        self.add_to_chat("Sistema", "👏 ¡Doble aplauso detectado!")
        action = cfg.acoustic_trigger_action.lower()
        if action in ("protocolo_darius", "welcome_protocol"):
            self._cmd_darius_protocol(None)
        elif action == "modo_desarrollo":
            self._cmd_workspace_dev(None)
        elif action == "modo_trading":
            self._cmd_workspace_trading(None)
        elif action == "enfocar_cursor":
            self._cmd_focus_cursor(None)
        else:
            self.talk(f"Doble aplauso detectado. Esperando tus órdenes, {USER_NAME}.")

    def _open_byok_settings(self):
        from byok_settings import BYOKSettingsModal
        BYOKSettingsModal(self, on_save_callback=self._on_byok_settings_saved)

    def _on_byok_settings_saved(self):
        if hasattr(self, "llm_pill"):
            self.llm_pill.configure(text=self._llm_badge_text())
        if hasattr(self, "tts_pill"):
            self.tts_pill.configure(text=self._tts_badge_text())
        if hasattr(self, "tts_worker"):
            self.tts_worker.engine = cfg.tts_engine
        prov_name = cfg.active_provider.upper()
        tts_name = cfg.tts_engine.upper()
        self.set_status(f"IA: {prov_name} • TTS: {tts_name}", "#38BDF8")
        self.talk(f"Configuración actualizada. Proveedor: {prov_name}, Motor de voz: {tts_name}.")

    def _on_text_submit(self, event=None):
        text = self.text_input.get().strip()
        if not text:
            return
        self.text_input.delete(0, "end")
        self.add_to_chat(USER_NAME, text)
        self._append_chat_file(USER_NAME.upper(), text)
        threading.Thread(target=self.execute_command, args=(text,),
                         daemon=True, name="text-cmd").start()

    def _insert_message(self, speaker: str, text: str, tag: str = ""):
        self.chat_display.configure(state="normal")
        tb = self.chat_display._textbox
        ts = datetime.datetime.now().strftime("%H:%M")
        spk = speaker.lower()
        if spk == "darius":
            name_tag = "darius"
            text_tag = tag or "darius_text"
            prefix = "🤖 DARIUS AI"
        elif spk in ["sistema", "system"]:
            name_tag = "system"
            text_tag = tag or "system_text"
            prefix = "⚙ SISTEMA"
        else:
            name_tag = "oscar"
            text_tag = tag or "oscar_text"
            prefix = f"🧑 {USER_NAME.upper()}"

        tb.insert("end", "\n")
        tb.insert("end", f"[{ts}] ", "timestamp")
        tb.insert("end", f"{prefix}\n", name_tag)
        tb.insert("end", f"   {text}\n", text_tag)
        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")

    def add_to_chat(self, speaker: str, text: str):
        self.after(0, self._insert_message, speaker, text)

    def set_status(self, text: str, color: str = "gray"):
        dot_colors = {
            "#00fbff": "#38BDF8",
            "#00ff88": "#34D399",
            "#ffaa00": "#FBBF24",
            "#ff5555": "#F87171",
            "#aa00ff": "#A78BFA",
            "gray": "#64748B",
            "green": "#34D399",
            "cyan": "#38BDF8",
            "yellow": "#FBBF24",
            "red": "#F87171",
        }
        resolved_color = dot_colors.get(color, color)

        def _update():
            if hasattr(self, "status_label"):
                self.status_label.configure(text=text)
            if hasattr(self, "status_dot"):
                self.status_dot.configure(text_color=resolved_color)

        self.after(0, _update)

    # =========================================================================
    #  RENDER PIPELINE & ANIMACIÓN (60 FPS)
    # =========================================================================

    def _start_render_pipeline(self):
        self._render_loop()

    def _render_loop(self):
        if not self.running:
            return

        # Suavizado de energía acústica del micrófono
        target_energy = self._current_audio_level
        self._smoothed_energy += 0.3 * (target_energy - self._smoothed_energy)

        # Determinar estado visual
        if self.is_muted:
            state = "MUTED"
        elif self.tts_worker.is_speaking.is_set():
            state = "SPEAKING"
        elif self.is_listening:
            state = "LISTENING"
        elif self._is_thinking:
            state = "THINKING"
        else:
            state = "IDLE"

        if hasattr(self, "visualizer"):
            self.visualizer.update_frame(state, self._smoothed_energy)

        self.after(16, self._render_loop)  # ~60 FPS

    def animate_logic(self):
        """Compatibilidad retrospectiva con llamadas heredadas."""
        pass

    def _start_audio_level_monitor(self):
        def monitor():
            import pyaudio
            pa = pyaudio.PyAudio()
            try:
                stream = pa.open(format=pyaudio.paInt16, channels=1,
                                 rate=16000, input=True, frames_per_buffer=512)
                while self.running:
                    try:
                        data = stream.read(512, exception_on_overflow=False)
                        if data:
                            pcm_i16 = np.frombuffer(data, dtype=np.int16)
                            rms = (
                                float(np.sqrt(np.mean(pcm_i16.astype(np.float32) ** 2)))
                                if pcm_i16.size > 0
                                else 0.0
                            )
                            self._current_audio_level = rms
                    except Exception:
                        self._current_audio_level = 0.0
                    time.sleep(0.02)
                stream.stop_stream()
                stream.close()
            except Exception as e:
                log.warning(f"Monitor de audio no disponible: {e}")
            finally:
                pa.terminate()
        threading.Thread(target=monitor, daemon=True, name="audio-monitor").start()

    # =========================================================================
    #  MUTE / RESET
    # =========================================================================

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        if self.is_muted:
            self.mute_btn.configure(text="🔊 ESCUCHAR", fg_color="#34D399", hover_color="#10B981")
            self.add_to_chat("Darius", "Modo discreto activado.")
            self.set_status("SILENCIADO", "#F87171")
        else:
            self.mute_btn.configure(text="🔇 SILENCIO", fg_color="#F87171", hover_color="#EF4444")
            self.talk("Sistemas de escucha reactivados.")
            self.set_status("SISTEMA LISTO", "#34D399")

    def reset_conversation(self):
        self.conversation_history.clear()
        with self._pending_lock:
            self._pending_action = None
        self.chat_display.configure(state="normal")
        self.chat_display._textbox.delete("1.0", "end")
        self.chat_display.configure(state="disabled")
        self._append_chat_file("SISTEMA", "— Nueva conversación iniciada —")
        self.talk("Memoria borrada. Nueva conversación iniciada.")

    # =========================================================================
    #  ESCANEO DE APLICACIONES
    # =========================================================================

    def scan_apps_async(self):
        threading.Thread(target=self._load_or_scan_apps, daemon=True, name="app-scanner").start()

    def _load_or_scan_apps(self):
        if APP_CACHE.exists():
            try:
                data     = json.loads(APP_CACHE.read_text(encoding="utf-8"))
                saved_at = datetime.datetime.fromisoformat(data["saved_at"])
                if saved_at.tzinfo is None:
                    saved_at = saved_at.replace(tzinfo=datetime.UTC)
                age_h = (datetime.datetime.now(datetime.UTC) - saved_at).total_seconds() / 3600
                if age_h < APP_CACHE_HOURS:
                    self.installed_apps = data["apps"]
                    log.info(f"Apps desde caché local: {len(self.installed_apps)}")
                    self.set_status(f"BASE DE DATOS: {len(self.installed_apps)} APPS", "#34D399")
                    self.after(
                        0,
                        lambda: self.apps_pill.configure(
                            text=f"📦 APPS: {len(self.installed_apps)}",
                            text_color="#34D399"
                        ) if hasattr(self, "apps_pill") else None
                    )
                    return
            except Exception as e:
                log.warning(f"Caché local inválida: {e}")
        self._scan_applications()

    def _scan_applications(self):
        apps: dict[str, str] = {
            "calculadora": "calc", "bloc de notas": "notepad",
            "explorador": "explorer", "paint": "mspaint",
            "task manager": "taskmgr", "panel de control": "control",
        }
        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        for hive, path in reg_paths:
            try:
                key   = winreg.OpenKey(hive, path)
                count = winreg.QueryInfoKey(key)[0]
                for i in range(count):
                    try:
                        sk = winreg.OpenKey(key, winreg.EnumKey(key, i))
                        try:
                            name, _ = winreg.QueryValueEx(sk, "DisplayName")
                            exe,  _ = winreg.QueryValueEx(sk, "InstallLocation")
                            if name and exe:
                                apps[name.lower().strip()] = exe.strip()
                        except FileNotFoundError:
                            pass
                        finally:
                            sk.Close()
                    except OSError:
                        continue
                key.Close()
            except OSError:
                continue
        self.set_status("ESCANEANDO APLICACIONES...", "#FBBF24")
        scanned_dirs = []
        for folder in [
            Path(os.environ.get("PROGRAMFILES",      r"C:\Program Files")),
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")),
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs",
        ]:
            if not folder.exists():
                continue
            scanned_dirs.append(folder)
            try:
                for i, exe in enumerate(folder.rglob("*.exe")):
                    if i % 100 == 0 and i > 0:
                        self.set_status(f"ESCANEANDO: {i} EXES EN {folder.name}...", "#FBBF24")
                    stem = exe.stem.lower().replace("-", " ").replace("_", " ")
                    if stem not in apps:
                        apps[stem] = str(exe)
            except PermissionError:
                continue
        self.installed_apps = apps
        log.info(f"Apps detectadas: {len(apps)}")
        try:
            APP_CACHE.write_text(
                json.dumps({"saved_at": datetime.datetime.now(datetime.UTC).isoformat(), "apps": apps},
                           ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            log.warning(f"No se pudo guardar caché local: {e}")
        self.set_status(f"BASE DE DATOS: {len(apps)} APPS", "#34D399")
        self.after(
            0,
            lambda: self.apps_pill.configure(
                text=f"📦 APPS: {len(apps)}",
                text_color="#34D399"
            ) if hasattr(self, "apps_pill") else None
        )

    def find_app(self, query: str) -> str | None:
        q = query.lower().strip()
        if q in self.installed_apps:
            return self.installed_apps[q]
        matches = get_close_matches(q, self.installed_apps.keys(), n=1, cutoff=0.55)
        return self.installed_apps[matches[0]] if matches else None

    # =========================================================================
    #  ARRANQUE
    # =========================================================================

    def start_system(self):
        self.start_btn.configure(
            state="disabled",
            text="⚡ NÚCLEO ONLINE",
            fg_color="#1F2937",
            text_color="#34D399"
        )
        self.mute_btn.configure(state="normal")
        mode_desc = {
            LISTEN_MODE_PTT:  f"Modo P.T.T. activo. Mantén presionado {LISTEN_KEY} para hablar.",
            LISTEN_MODE_NAME: f"Modo nombre activo. Dí {ASSISTANT_NAME} para activarme.",
            LISTEN_MODE_AUTO: "Modo automático activo. Escucho todo.",
        }
        self.talk(f"Darius en línea. Esperando órdenes, {USER_NAME}. "
                  + mode_desc.get(self.listen_mode, ""))
        self._start_audio_level_monitor()
        if self.listen_mode == LISTEN_MODE_PTT:
            threading.Thread(target=self._ptt_loop, daemon=True, name="ptt-loop").start()
        elif PORCUPINE_AVAILABLE and os.getenv("PORCUPINE_ACCESS_KEY"):
            threading.Thread(target=self._porcupine_loop, daemon=True, name="wake-word").start()
        else:
            threading.Thread(target=self.main_loop, daemon=True, name="main-loop").start()

    def main_loop(self):
        while self.running:
            if self.is_muted or self.tts_worker.is_speaking.is_set():
                time.sleep(0.05)
                continue
            if self.listen_mode == LISTEN_MODE_PTT:
                time.sleep(0.1)
                continue
            self.listen_and_process()

    def _ptt_loop(self):
        if not KEYBOARD_AVAILABLE:
            log.warning("keyboard no disponible — fallback a NOMBRE.")
            self.listen_mode = LISTEN_MODE_NAME
            self.after(0, self._set_listen_mode, LISTEN_MODE_NAME)
            self.main_loop()
            return

        log.info(f"[PTT] Loop iniciado. Tecla: [{LISTEN_KEY}]")
        key_was_down = False
        while self.running:
            if self.is_muted:
                time.sleep(0.1)
                continue
            key_down = keyboard.is_pressed(LISTEN_KEY)
            if key_down and not key_was_down and not self.tts_worker.is_speaking.is_set():
                key_was_down = True
                self._ptt_active = True
                self.set_status(f"🎙 HABLANDO… (suelta {LISTEN_KEY} al terminar)", "#00ff88")
                self.is_listening = True
                self.after(0, self.animate_logic)
            elif not key_down and key_was_down:
                key_was_down = False
                self._ptt_active = False
                self.is_listening = False
                self.set_status("PROCESANDO…", "#ffaa00")
                threading.Thread(target=self._ptt_capture_and_process,
                                 daemon=True, name="ptt-capture").start()
            time.sleep(0.02)

    def _ptt_capture_and_process(self):
        import io
        import wave

        import pyaudio
        rate, chunk, channels = 16000, 512, 1
        pa = pyaudio.PyAudio()
        frames = []
        try:
            stream = pa.open(format=pyaudio.paInt16, channels=channels,
                             rate=rate, input=True, frames_per_buffer=chunk)
            while KEYBOARD_AVAILABLE and keyboard.is_pressed(LISTEN_KEY) and self.running:
                data = stream.read(chunk, exception_on_overflow=False)
                frames.append(data)
                if data:
                    pcm_i16 = np.frombuffer(data, dtype=np.int16)
                    rms = (
                        float(np.sqrt(np.mean(pcm_i16.astype(np.float32) ** 2)))
                        if pcm_i16.size > 0
                        else 0.0
                    )
                    self._current_audio_level = rms
            stream.stop_stream()
            stream.close()
        except Exception as e:
            log.error(f"[PTT] Error de grabación: {e}")
            pa.terminate()
            self.set_status("LISTO", "gray")
            return
        finally:
            pa.terminate()
        if not frames:
            self.set_status("LISTO", "gray")
            return
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(b"".join(frames))
        wav_buffer.seek(0)
        try:
            with sr.AudioFile(wav_buffer) as source:
                audio = self.listener.record(source)
            text = self.listener.recognize_google(audio, language="es-ES").lower()
            log.info(f"[PTT] Reconocido: '{text}'")
            self.add_to_chat(USER_NAME, text)
            self._append_chat_file(USER_NAME.upper(), text)
            self.execute_command(_strip_name(text, ASSISTANT_NAME) or text)
        except sr.UnknownValueError:
            log.debug("[PTT] Audio no reconocido.")
            self.set_status("LISTO", "gray")
        except sr.RequestError as e:
            log.error(f"[PTT] STT error: {e}")
            self.talk("Error de conexión con el servicio de voz.")
        except Exception as e:
            log.error(f"[PTT] Error: {e}", exc_info=True)
            self.set_status("LISTO", "gray")

    def _porcupine_loop(self):
        import struct

        import pvporcupine
        import pyaudio
        access_key = os.getenv("PORCUPINE_ACCESS_KEY", "")
        if not access_key:
            self.main_loop()
            return
        try:
            porcupine = pvporcupine.create(access_key=access_key, keywords=["computer"])
            pa        = pyaudio.PyAudio()
            stream    = pa.open(rate=porcupine.sample_rate, channels=1,
                                format=pyaudio.paInt16, input=True,
                                frames_per_buffer=porcupine.frame_length)
            while self.running:
                if self.is_muted or self.tts_worker.is_speaking.is_set():
                    time.sleep(0.05)
                    continue
                pcm   = stream.read(porcupine.frame_length, exception_on_overflow=False)
                pcm   = struct.unpack_from("h" * porcupine.frame_length, pcm)
                if porcupine.process(pcm) >= 0:
                    self.listen_and_process()
            stream.stop_stream()
            stream.close()
            pa.terminate()
            porcupine.delete()
        except Exception as e:
            log.error(f"Porcupine error: {e}")
            self.main_loop()

    # =========================================================================
    #  RECONOCIMIENTO DE VOZ
    # =========================================================================

    def listen_and_process(self):
        try:
            mic_kwargs = {"device_index": self._mic_device_index} if self._mic_device_index is not None else {}
            with sr.Microphone(**mic_kwargs) as source:
                if self.tts_worker.is_speaking.is_set():
                    return
                self.set_status("ESCUCHANDO…", "#00fbff")
                self.is_listening = True
                self.after(0, self.animate_logic)
                audio = self.listener.listen(source, timeout=MIC_LISTEN_TIMEOUT,
                                             phrase_time_limit=MIC_PHRASE_LIMIT)
                self.is_listening = False
                if self.tts_worker.is_speaking.is_set():
                    return
                self.set_status("PROCESANDO…", "#ffaa00")
                text = self.listener.recognize_google(audio, language="es-ES").lower()
                log.info(f"Reconocido: '{text}'")
                self.process_recognized_text(text)
        except sr.WaitTimeoutError:
            pass
        except sr.UnknownValueError:
            log.debug("Audio no reconocido.")
        except sr.RequestError as e:
            log.error(f"STT error: {e}")
            self.talk("Error de conexión con el servicio de voz.")
        except Exception as e:
            log.error(f"listen_and_process error: {e}", exc_info=True)
        finally:
            self.is_listening = False
            self.set_status("LISTO", "gray")

    def process_recognized_text(self, text: str):
        words      = text.split()
        name_found = False
        clean_text = text

        if self.listen_mode == LISTEN_MODE_AUTO:
            if ASSISTANT_NAME in text:
                name_found = True
                clean_text = _strip_name(text, ASSISTANT_NAME)
            elif words and SequenceMatcher(None, ASSISTANT_NAME, words[0]).ratio() > NAME_SIMILARITY_CUTOFF:
                name_found = True
                clean_text = " ".join(words[1:]).strip()

        elif self.listen_mode == LISTEN_MODE_NAME:
            name_found, clean_text = self._check_name_in_text(text)
            if not name_found:
                log.debug(f"[NOMBRE] Descartado (sin nombre): '{text}'")
                return

        self.add_to_chat(USER_NAME, text)
        self._append_chat_file(USER_NAME.upper(), text)
        self.execute_command(clean_text or text)

    def _check_name_in_text(self, text: str) -> tuple[bool, str]:
        return check_name_in_text(text, ASSISTANT_NAME, NAME_SIMILARITY_CUTOFF)

    # =========================================================================
    #  PARSEO Y EJECUCIÓN DE COMANDOS
    # =========================================================================
    #
    #  BUG 2 FIX: execute_command recibe el texto YA LIMPIO (sin nombre) desde
    #  process_recognized_text. Pero si por algún flujo llega CON el nombre
    #  (ej: entrada de texto manual que incluye "darius"), lo limpiamos aquí
    #  para que los patrones y el fuzzy nunca vean "darius suspende el equipo"
    #  sino solo "suspende el equipo".
    #
    #  BUG 3 FIX: los regex de apagar/reiniciar ahora cubren todas las variantes
    #  que produce el STT en español: "apagate", "apaga el pc/equipo/máquina",
    #  "apagar el equipo", etc.
    #
    #  BUG 4 FIX: "cerrar sesion" y "cierra la sesion" matchean en _cmd_accion
    #  porque SYSTEM_ACTIONS tiene "cerrar sesion" como entrada explícita y
    #  con cutoff 0.75 el fuzzy lo resuelve correctamente.
    # =========================================================================

    # ── Patrones de comando ───────────────────────────────────────────────────

    # Regex para apagar — cubre: "apagate", "apaga el equipo", "apaga el pc",
    # "apaga la maquina", "apaga la computadora", "apagar el equipo"
    _RE_APAGAR = re.compile(
        r"\b(apagate|apagar?\s+(el\s+)?(equipo|pc|computador[a]?|maquina|sistema))\b",
        re.IGNORECASE
    )
    # Regex para reiniciar — cubre: "reinicia el equipo", "reiniciar el pc", etc.
    _RE_REINICIAR = re.compile(
        r"\b(reinicia[r]?\s+(el\s+)?(equipo|pc|computador[a]?|maquina|sistema))\b",
        re.IGNORECASE
    )
    # Regex para _cmd_accion — SOLO palabras clave de sistema operativo
    # (ya NO incluye "cuanto", "cual es", "hay" que son genéricas)
    _RE_ACCION = re.compile(
        r"\b(ver\s+(mi\s+)?(ip|dns|ram|cpu|disco|espacio|version|serial|modelo|procesador|temperatura|procesos|conexiones|servicios|redes|firewall)|"
        r"limpiar\s+(dns|cache|disco|temporales|papelera)|"
        r"vaciar\s+(papelera|reciclaje)|"
        r"diagnosticar\s+red|reparar\s+red|"
        r"renovar\s+ip|resetear\s+red|"
        r"desconectar\s+wifi|"
        r"activar\s+firewall|desactivar\s+firewall|"
        r"bloquear\s+(pantalla|pc|equipo|sesion)|"
        r"suspender\s+(el\s+)?(equipo|pc)|"
        r"hibernar\s+(el\s+)?(equipo|pc)|"
        r"cerrar\s+(la\s+)?sesion|"
        r"probar\s+internet|ping\s+google|hay\s+internet|"
        r"tiempo\s+encendido|uptime|"
        r"resumen\s+(del\s+)?sistema|info\s+(del\s+)?sistema|"
        r"buscar\s+actualizaciones)\b",
        re.IGNORECASE
    )

    _RE_DIARIO = re.compile(
        r"\b(anota|escribe|guarda)\s+(en\s+mi\s+)?(diario|bit[aá]cora)\b",
        re.IGNORECASE
    )
    _RE_MEMORIA = re.compile(
        r"\b(recuerda|memoriza|guarda\s+en\s+memoria|guarda\s+en\s+obsidian)\b",
        re.IGNORECASE
    )
    _RE_BUSCAR_NOTAS = re.compile(
        r"\b(busca|buscar|consulta)\s+en\s+(mis\s+notas|mi\s+diario|obsidian)\b",
        re.IGNORECASE
    )
    _RE_HORA = re.compile(
        r"\b(qu[eé]\s+horas?(\s+(es|son|tienes|marca))?|hora\s+actual|hora\s+exacta|dime\s+la\s+hora|la\s+hora|tienes\s+la\s+hora)\b",
        re.IGNORECASE
    )
    _RE_FECHA = re.compile(
        r"\b(qu[eé]\s+fecha(\s+(es|tenemos|hoy))?|qu[eé]\s+d[ií]a(\s+(es(\s+hoy)?|tenemos))?|fecha\s+de\s+hoy|d[ií]a\s+de\s+hoy|a\s+qu[eé]\s+estamos(\s+hoy)?)\b",
        re.IGNORECASE
    )

    # Regex para Workspaces y Protocolo Darius
    _RE_DARIUS_PROTOCOL = re.compile(
        r"\b(inicia[r]?|ejecuta[r]?|activa[r]?)?\s*(protocolo\s+darius|protocolo|modo\s+bienvenida|rutina\s+de\s+bienvenida|bienvenida\s+darius)\b",
        re.IGNORECASE
    )
    _RE_WORKSPACE_DEV = re.compile(
        r"\b(inicia[r]?|activa[r]?)?\s*(modo\s+desarrollo|modo\s+dev|modo\s+programaci[oó]n|entorno\s+de\s+desarrollo)\b",
        re.IGNORECASE
    )
    _RE_WORKSPACE_TRADING = re.compile(
        r"\b(inicia[r]?|activa[r]?)?\s*(modo\s+trading|modo\s+mercados|modo\s+finanzas|pantalla\s+trading)\b",
        re.IGNORECASE
    )
    _RE_CURSOR = re.compile(
        r"\b(enfoca[r]?\s+cursor|cursor\s+pantalla\s+completa|maximizar\s+cursor|abrir\s+cursor)\b",
        re.IGNORECASE
    )
    _RE_MONITORES = re.compile(
        r"\b(ver\s+monitores|cu[aá]ntos\s+monitores|pantallas\s+conectadas|info\s+monitores)\b",
        re.IGNORECASE
    )
    _RE_DETENER = re.compile(
        r"\b(c[aá]llate|silencio|detente|detener(se)?|parar?|cancela[r]?|alto|basta|para\s+ya|det[eé]n(te)?|stop)\b",
        re.IGNORECASE
    )
    _RE_DNS = re.compile(
        r"\b(limpia[r]?|borra[r]?|vacia[r]?|flashe?a[r]?|resetea[r]?)\s+(el\s+|la\s+)?(cach[eé]\s+)?dns(\s+(del?\s+)?(sistema|internet|pc|red))?\b",
        re.IGNORECASE
    )
    _RE_GH_PRS = re.compile(
        r"\b(ver|consultar|mostrar|lista[r]?)\s+(los\s+)?(prs?|pull\s+requests?)(\s+(de\s+)?github)?\b",
        re.IGNORECASE
    )
    _RE_GIT_STATUS = re.compile(
        r"\b(ver\s+|consultar\s+|mostrar\s+)?(estado\s+de\s+git|git\s+status|cambios\s+en\s+git|c[oó]mo\s+est[aá]\s+el\s+repo(sitorio)?)\b",
        re.IGNORECASE
    )
    _RE_TOP_PROCESSES = re.compile(
        r"\b(qu[eé]\s+(app[s]?\s+|proceso[s]?\s+)?consume[n]?\s+m[aá]s\s+ram|procesos\s+pesados|procesos\s+que\s+m[aá]s\s+consumen(\s+ram)?|top\s+procesos|quien\s+consume\s+m[aá]s\s+(memoria|ram))\b",
        re.IGNORECASE
    )
    _RE_HUMAN_TYPE = re.compile(
        r"\b(escribe|teclea|digita|escribe\s+por\s+m[ií])\s+(.+)$",
        re.IGNORECASE
    )
    _RE_HUMAN_CLICK = re.compile(
        r"\b(haz\s+clic|da\s+clic|clic\s+izquierdo|clic\s+derecho|doble\s+clic|mover\s+mouse)\b",
        re.IGNORECASE
    )
    _RE_SCRAPE_WEB = re.compile(
        r"\b(extrae|scrapp?ea|analiza|lee|resume)\s+(la\s+p[aá]gina|el\s+sitio|la\s+web|de\s+la\s+url)?\s*(https?://\S+)\b",
        re.IGNORECASE
    )
    _RE_VISION_SCREEN = re.compile(
        r"\b(qu[eé]\s+hay\s+en\s+(mi\s+)?pantalla|analiza\s+(mi\s+)?pantalla|lee\s+(la\s+)?pantalla|analiza\s+(este\s+)?error\s+(en\s+pantalla)?|mira\s+(la\s+)?pantalla|qu[eé]\s+estoy\s+viendo|captura\s+(de\s+)?pantalla)\b",  # noqa: E501
        re.IGNORECASE
    )
    _RE_DEEP_RESEARCH = re.compile(
        r"\b(investiga\s+(a\s+fondo|profundamente|exhaustivamente|sobre)?|investigaci[oó]n\s+profunda\s+(sobre|de)?|haz\s+una\s+investigaci[oó]n\s+(sobre|de)?)\s+(.+)$",  # noqa: E501
        re.IGNORECASE
    )
    _RE_PLANNER_GOAL = re.compile(
        r"\b(planifica|crea\s+un\s+plan\s+para|ejecuta\s+el\s+plan|plan\s+de\s+acci[oó]n\s+para)\s+(.+)$",
        re.IGNORECASE
    )

    _CMD_PATTERNS = [
        (_RE_DETENER,                                                             "_cmd_detener"),
        (_RE_HORA,                                                                "_cmd_hora"),
        (_RE_FECHA,                                                               "_cmd_fecha"),
        (re.compile(r"\b(nueva conversación|olvida todo|resetea la memoria)\b"), "_cmd_reset"),
        (_RE_VISION_SCREEN,                                                       "_cmd_screen_vision"),
        (_RE_DEEP_RESEARCH,                                                       "_cmd_deep_research"),
        (_RE_PLANNER_GOAL,                                                        "_cmd_agent_planner"),
        (_RE_SCRAPE_WEB,                                                          "_cmd_scrape_web"),
        (_RE_HUMAN_TYPE,                                                          "_cmd_human_type"),
        (_RE_HUMAN_CLICK,                                                         "_cmd_human_click"),
        (_RE_DNS,                                                                 "_cmd_flush_dns"),
        (_RE_GH_PRS,                                                              "_cmd_gh_prs"),
        (_RE_GIT_STATUS,                                                          "_cmd_git_status"),
        (_RE_TOP_PROCESSES,                                                       "_cmd_top_processes"),
        (_RE_DARIUS_PROTOCOL,                                                     "_cmd_darius_protocol"),
        (_RE_WORKSPACE_DEV,                                                       "_cmd_workspace_dev"),
        (_RE_WORKSPACE_TRADING,                                                   "_cmd_workspace_trading"),
        (_RE_CURSOR,                                                              "_cmd_focus_cursor"),
        (_RE_MONITORES,                                                           "_cmd_ver_monitores"),
        (re.compile(r"\b(reproduce|pon|ponme|coloca|escuchar|música)\b"),        "_cmd_youtube"),
        (re.compile(r"\b(busca|buscar|googlea)\b"),                              "_cmd_buscar"),
        (re.compile(r"\b(abre|abrir|lanza|ejecuta|inicia|muestra)\b"),           "_cmd_abrir"),
        (re.compile(r"\bsubir\s+volumen\b"),                                     "_cmd_vol_up"),
        (re.compile(r"\bbajar\s+volumen\b"),                                     "_cmd_vol_down"),
        (re.compile(r"\bsilenciar\b"),                                           "_cmd_vol_mute"),
        (re.compile(r"\b(cómo estás|estado del sistema|status)\b"),              "_cmd_estado"),
        (re.compile(r"\b(adiós|adios|descansa|apágate|cerrar darius)\b"),        "_cmd_cerrar"),
        # Comandos de Memoria y Notas en Obsidian
        (_RE_DIARIO,       "_cmd_diario"),
        (_RE_MEMORIA,      "_cmd_memoria"),
        (_RE_BUSCAR_NOTAS, "_cmd_buscar_notas"),
        # BUG 3 FIX ↓ — usa los regex más específicos definidos arriba
        (_RE_APAGAR,    "_cmd_apagar_pc"),
        (_RE_REINICIAR, "_cmd_reiniciar_pc"),
        # BUG 4 FIX ↓ — _cmd_accion ahora solo captura acciones de sistema
        (_RE_ACCION,    "_cmd_accion"),
    ]

    def execute_command(self, cmd: str):
        # BUG 2 FIX: limpia el nombre si todavía aparece en el comando
        # (puede ocurrir en entrada de texto manual o modo AUTO sin limpieza previa)
        cmd = _strip_name(cmd.strip(), ASSISTANT_NAME)
        if not cmd:
            return
        log.info(f"Ejecutando: '{cmd}'")

        with self._pending_lock:
            if self._pending_action is not None:
                self._handle_confirmation(cmd)
                return

        for pattern, handler in self._CMD_PATTERNS:
            if pattern.search(cmd):
                getattr(self, handler)(cmd)
                return

        threading.Thread(target=self.ask_gemini, args=(cmd,),
                         daemon=True, name="gemini").start()

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _cmd_hora(self, _):
        now = datetime.datetime.now()
        hora_12 = now.strftime("%I:%M %p").lower().replace("am", "a. m.").replace("pm", "p. m.")
        self.talk(f"Son las {hora_12}.")

    def _cmd_fecha(self, _):
        now = datetime.datetime.now()
        dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        meses = [
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
        ]
        dia_semana = dias[now.weekday()]
        mes = meses[now.month - 1]
        self.talk(f"Hoy es {dia_semana}, {now.day} de {mes} de {now.year}.")

    def _cmd_reset(self, _):
        self.reset_conversation()

    def _cmd_flush_dns(self, _):
        entry = wincmd_resolve_action("limpiar cache dns")
        if entry:
            self._execute_action(entry)
        else:
            self.talk("Vaciando caché DNS de Windows.")
            from agentic_bridge import bridge
            ok, out = bridge.flush_dns()
            self.talk("Caché DNS vaciada correctamente." if ok else f"Error: {out}")

    def _cmd_gh_prs(self, _):
        entry = wincmd_resolve_action("ver prs de github")
        if entry:
            self._execute_action(entry)
        else:
            from agentic_bridge import bridge
            ok, out = bridge.execute_gh("pr list")
            self.talk(self._format_output_for_tts(out, "Pull Requests de GitHub"))

    def _cmd_git_status(self, _):
        entry = wincmd_resolve_action("ver estado de git")
        if entry:
            self._execute_action(entry)
        else:
            from agentic_bridge import bridge
            ok, out = bridge.execute_git("status --short")
            self.talk(self._format_output_for_tts(out, "Estado de Git"))

    def _cmd_top_processes(self, _):
        entry = wincmd_resolve_action("procesos que mas consumen")
        if entry:
            self._execute_action(entry)
        else:
            from agentic_bridge import bridge
            ok, out = bridge.get_top_processes(5)
            self.talk(self._format_output_for_tts(out, "Procesos con mayor consumo de RAM"))

    def _cmd_human_type(self, cmd: str):
        m = self._RE_HUMAN_TYPE.search(cmd)
        text_to_type = m.group(2).strip() if m else ""
        if not text_to_type:
            self.talk("¿Qué texto deseas que escriba?")
            return
        self.talk("Escribiendo texto en dos segundos.")
        def run():
            time.sleep(2.0)
            from human_gui import gui
            gui.human_type(text_to_type)
            self.talk("Texto escrito correctamente.")
        threading.Thread(target=run, daemon=True, name="human-type").start()

    def _cmd_human_click(self, cmd: str):
        is_right = bool(re.search(r"derecho", cmd, re.IGNORECASE))
        is_double = bool(re.search(r"doble", cmd, re.IGNORECASE))
        clicks = 2 if is_double else 1
        button = "right" if is_right else "left"
        self.talk("Haciendo clic en dos segundos.")
        def run():
            time.sleep(2.0)
            from human_gui import gui
            gui.human_click(button=button, clicks=clicks)
            self.talk("Clic ejecutado.")
        threading.Thread(target=run, daemon=True, name="human-click").start()

    def _cmd_scrape_web(self, cmd: str):
        m = self._RE_SCRAPE_WEB.search(cmd)
        url = m.group(3).strip() if m else ""
        if not url:
            self.talk("Por favor proporciona una URL válida para analizar.")
            return
        self.talk(f"Analizando el contenido de {url}.")
        def run():
            from human_gui import gui
            res = gui.scrape_web_content(url)
            if not res.get("ok"):
                self.talk(f"Error al analizar la página: {res.get('error')}")
                return
            title = res.get("title", "Página web")
            content = res.get("content", "")
            summary_prompt = (
                f"Resume brevemente y extrae los puntos clave del siguiente contenido web "
                f"extraído de '{title}' ({url}):\n\n{content[:4000]}"
            )
            self.ask_gemini(summary_prompt)
        threading.Thread(target=run, daemon=True, name="scrape-web").start()

    def _cmd_screen_vision(self, cmd: str):
        self.set_status("👁️ ANALIZANDO PANTALLA…", "#38BDF8")
        self.talk("Analizando lo que se muestra en tu pantalla, un momento.")

        def run():
            from screen_vision import vision_engine
            is_error = bool(re.search(r"\berror|fallo|excepci[oó]n|falla\b", cmd, re.IGNORECASE))
            is_ocr = bool(re.search(r"\blee|texto|documento|c[oó]digo\b", cmd, re.IGNORECASE))

            if is_error:
                analysis = vision_engine.analyze_screen_error(monitor_index=1)
            elif is_ocr:
                analysis = vision_engine.read_screen_text(monitor_index=1)
            else:
                analysis = vision_engine.analyze_screen(prompt=cmd, monitor_index=1)

            self.add_to_chat("Darius", analysis)
            self.talk(analysis)
            self.set_status("SISTEMA LISTO", "#34D399")

        threading.Thread(target=run, daemon=True, name="screen-vision").start()

    def _cmd_deep_research(self, cmd: str):
        m = self._RE_DEEP_RESEARCH.search(cmd)
        topic = m.group(4).strip() if m else cmd
        self.set_status("🔬 INVESTIGANDO A FONDO…", "#A855F7")

        def run():
            from deep_research import research_pipeline
            res = research_pipeline.run_research(
                topic=topic,
                save_to_obsidian=True,
                speak_fn=self.talk,
            )
            self.add_to_chat("Darius", f"### Informe de Investigación: {topic}\n\n{res['report']}")
            self.set_status("SISTEMA LISTO", "#34D399")

        threading.Thread(target=run, daemon=True, name="deep-research").start()

    def _cmd_agent_planner(self, cmd: str):
        m = self._RE_PLANNER_GOAL.search(cmd)
        goal = m.group(2).strip() if m else cmd

        def run():
            from agent_planner import agent_planner
            res = agent_planner.plan_and_execute(
                goal=goal,
                speak_fn=self.talk,
                status_fn=self.set_status,
            )
            self.add_to_chat("Darius", res["summary"])

        threading.Thread(target=run, daemon=True, name="agent-planner").start()

    def _cmd_darius_protocol(self, _):
        self.talk("Iniciando Protocolo Darius. Configurando entorno de trabajo y herramientas.")
        threading.Thread(
            target=run_darius_welcome_protocol,
            kwargs={
                "talk_fn": self.talk,
                "song_url": cfg.workspace_song_uri,
                "claude_url": cfg.workspace_claude_url,
                "monitor_claude": cfg.workspace_monitor_claude,
                "monitor_secondary": cfg.workspace_monitor_secondary,
                "secondary_url": cfg.workspace_secondary_url,
                "welcome_phrase": cfg.workspace_welcome_phrase,
            },
            daemon=True,
            name="darius-protocol",
        ).start()

    def _cmd_workspace_dev(self, _):
        threading.Thread(target=run_dev_mode, args=(self.talk,), daemon=True, name="ws-dev").start()

    def _cmd_workspace_trading(self, _):
        threading.Thread(target=run_trading_mode, args=(self.talk,), daemon=True, name="ws-trading").start()

    def _cmd_focus_cursor(self, _):
        self.talk("Enfocando Cursor en pantalla completa.")
        threading.Thread(
            target=focus_or_launch_cursor,
            kwargs={"fullscreen": True},
            daemon=True,
            name="focus-cursor",
        ).start()

    def _cmd_ver_monitores(self, _):
        monitors = get_monitor_rects()
        count = len(monitors)
        details = ", ".join(f"Monitor {i+1} de {r[2]-r[0]} por {r[3]-r[1]} píxeles" for i, r in enumerate(monitors))
        self.talk(f"Se han detectado {count} pantallas conectadas. {details}.")

    def _cmd_diario(self, cmd: str):
        entry = re.sub(
            r"^.*(anota|escribe|guarda)\s+(en\s+mi\s+)?(diario|bit[aá]cora)\s*(que|:)?\s*",
            "", cmd, flags=re.IGNORECASE
        ).strip()
        if entry:
            brain.append_daily_note(entry)
            self.talk(f"Anotado en tu diario de Obsidian: {entry}.")
        else:
            self.talk("¿Qué deseas que anote en tu diario?")

    def _cmd_memoria(self, cmd: str):
        note = re.sub(
            r"^.*(recuerda|memoriza|guarda\s+en\s+memoria|guarda\s+en\s+obsidian)\s*(que|:)?\s*",
            "", cmd, flags=re.IGNORECASE
        ).strip()
        if note:
            title = note[:40].strip()
            brain.save_memory(title=title, content=note)
            self.talk("Guardado en tu memoria de Obsidian.")
        else:
            self.talk("¿Qué información deseas que recuerde?")

    def _cmd_buscar_notas(self, cmd: str):
        query = re.sub(
            r"^.*(busca|buscar|consulta)\s+en\s+(mis\s+notas|mi\s+diario|obsidian)\s*(que|:)?\s*",
            "", cmd, flags=re.IGNORECASE
        ).strip()
        if query:
            results = brain.search_vault(query, max_results=2)
            if results:
                res_text = ". ".join(f"{r['title']}: {r['snippet']}" for r in results)
                self.talk(f"Encontré en tus notas: {res_text}")
            else:
                self.talk(f"No encontré notas relacionadas con {query} en Obsidian.")
        else:
            self.talk("¿Qué tema deseas buscar en tus notas?")

    def _cmd_youtube(self, cmd):
        song = re.sub(r"^.*(reproduce|ponme|coloca|pon|escuchar|música)\s*",
                      "", cmd, flags=re.IGNORECASE).strip()
        if song:
            self.talk(f"Buscando {song}, un momento.")
            threading.Thread(target=self.play_on_youtube, args=(song,),
                             daemon=True, name="yt").start()
        else:
            self.talk("¿Qué canción quieres que reproduzca?")

    def _cmd_buscar(self, cmd):
        term = re.sub(r"^.*(busca|buscar|googlea)\s*", "", cmd, flags=re.IGNORECASE).strip()
        term = re.sub(r"\ben\s+internet\b", "", term).strip()
        if term:
            webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(term)}")
            self.talk(f"Buscando {term} en Google.")
        else:
            self.talk("¿Qué quieres que busque?")

    def _cmd_abrir(self, cmd):
        app_name = re.sub(r"^.*(abre|abrir|lanza|ejecuta|inicia|muestra)\s*",
                          "", cmd, flags=re.IGNORECASE).strip()
        self._open_app(app_name)

    def _cmd_vol_up(self, _):
        volume_up()
        self.talk("Volumen incrementado.")

    def _cmd_vol_down(self, _):
        volume_down()
        self.talk("Volumen disminuido.")

    def _cmd_vol_mute(self, _):
        volume_mute()
        self.talk("Audio silenciado.")

    def _cmd_estado(self, _):
        mode_names = {LISTEN_MODE_PTT: "P.T.T.", LISTEN_MODE_NAME: "nombre", LISTEN_MODE_AUTO: "automático"}
        self.talk(
            f"Sistema operativo. {len(self.installed_apps)} aplicaciones en base de datos. "
            f"Modo de activación: {mode_names.get(self.listen_mode, self.listen_mode)}."
        )

    def _cmd_detener(self, _):
        with contextlib.suppress(Exception):
            from human_gui import gui
            gui.abort()
        if hasattr(self, "tts_worker"):
            self.tts_worker.clear_queue()
        with contextlib.suppress(Exception):
            import sounddevice as sd
            sd.stop()
        with self._pending_lock:
            self._pending_action = None
        self.add_to_chat("Darius", "Operación detenida y cola de voz silenciada.")
        self.set_status("DETENIDO", "#F87171")

    def _cmd_cerrar(self, _):
        self.talk(f"Cerrando protocolos. Hasta pronto, {USER_NAME}.")
        self.after(2500, self.kill_process)

    def _cmd_apagar_pc(self, _):
        with self._pending_lock:
            self._pending_action = {
                "desc": "Apagar el equipo en 10 segundos",
                "confirm": True,
                "_fn": lambda: subprocess.run([os.environ["WINDIR"] + "\\System32\\shutdown.exe", "/s", "/t", "10"],  # noqa: S603,E501
                                               shell=False, check=False),
            }
        self.talk("Estás a punto de apagar el equipo. Di confirmar para proceder o cancelar para abortar.")
        self.set_status("⚠ ESPERANDO CONFIRMACIÓN", "#ffaa00")

    def _cmd_reiniciar_pc(self, _):
        with self._pending_lock:
            self._pending_action = {
                "desc": "Reiniciar el equipo en 10 segundos",
                "confirm": True,
                "_fn": lambda: subprocess.run([os.environ["WINDIR"] + "\\System32\\shutdown.exe", "/r", "/t", "10"],  # noqa: S603,E501
                                               shell=False, check=False),
            }
        self.talk("Estás a punto de reiniciar el equipo. Di confirmar para proceder o cancelar para abortar.")
        self.set_status("⚠ ESPERANDO CONFIRMACIÓN", "#ffaa00")

    def _cmd_accion(self, cmd: str):
        entry = wincmd_resolve_action(cmd)
        if entry is None:
            desc = wincmd_launch(cmd)
            if desc:
                self.talk(f"Abriendo {desc}.")
                return
            threading.Thread(target=self.ask_gemini, args=(cmd,),
                             daemon=True, name="gemini").start()
            return
        if entry.get("confirm", False):
            with self._pending_lock:
                self._pending_action = entry
            self.talk(f"Estás a punto de ejecutar: {entry['desc']}. "
                      "Di confirmar para proceder o cancelar para abortar.")
            self.set_status("⚠ ESPERANDO CONFIRMACIÓN", "#ffaa00")
        else:
            self._execute_action(entry)

    def _handle_confirmation(self, text: str):
        t = text.lower().strip()
        if any(w in t for w in ["confirmar", "confirma", "sí", "si", "adelante",
                                 "procede", "hazlo", "ok", "correcto"]):
            with self._pending_lock:
                entry               = self._pending_action
                self._pending_action = None
            self.set_status("LISTO", "gray")
            self.talk(f"Ejecutando: {entry['desc']}.")
            if "_fn" in entry:
                threading.Thread(target=entry["_fn"], daemon=True, name="action-direct").start()
            else:
                self._execute_action(entry)
        elif any(w in t for w in ["cancelar", "cancela", "no", "abortar", "detener"]):
            with self._pending_lock:
                desc                = self._pending_action["desc"]
                self._pending_action = None
            self.set_status("LISTO", "gray")
            self.talk(f"Acción cancelada: {desc}.")
        else:
            self.talk("No entendí. Di confirmar o cancelar.")

    def _execute_action(self, entry: dict):
        def run():
            desc = entry["desc"]
            self.set_status(f"⚙ {desc.upper()[:30]}…", "#aa00ff")
            success, output = wincmd_run_action(entry)
            if not success:
                self.talk(f"Error al ejecutar {desc}. {output}")
            elif output:
                self.talk(self._format_output_for_tts(output, desc))
            else:
                self.talk(f"Listo. {desc} ejecutado correctamente.")
            self.set_status("LISTO", "gray")
        threading.Thread(target=run, daemon=True, name="action").start()

    def _format_output_for_tts(self, raw: str, desc: str) -> str:
        lines = [line.strip() for line in raw.splitlines()
                 if line.strip() and not set(line.strip()) <= set("-= |+")]
        if not lines:
            return f"{desc} completado."
        if len(lines) == 1:
            return f"{desc}: {lines[0]}"
        if len(lines) <= 4:
            return f"{desc}. {'. '.join(lines[:4])}"
        return f"{desc}. {'. '.join(lines[:3])}. Y más información en pantalla."

    def _open_app(self, app_name: str):
        desc = wincmd_launch(app_name)
        if desc:
            self.talk(f"Abriendo {desc}.")
            return
        path = self.find_app(app_name)
        if path:
            try:
                os.startfile(path)  # noqa: S606
                self.talk(f"Abriendo {app_name}.")
                return
            except Exception as e:
                log.error(f"Error al abrir '{app_name}': {e}")
                self.talk(f"Encontré {app_name} pero no pude ejecutarlo.")
                return
        self.talk(f"No encontré {app_name}. Verifica el nombre o dame más detalles.")

    # =========================================================================
    #  YOUTUBE
    # =========================================================================

    def play_on_youtube(self, song: str):
        try:
            url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(song)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})  # noqa: S310
            with urllib.request.urlopen(req, timeout=8) as resp:  # noqa: S310
                html = resp.read().decode("utf-8")
            match = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
            if match:
                webbrowser.open(f"https://www.youtube.com/watch?v={match.group(1)}")
                self.talk(f"Reproduciendo {song}.")
            else:
                webbrowser.open(url)
                self.talk(f"Abriendo resultados de {song} en YouTube.")
        except Exception as e:
            log.error(f"YouTube error: {e}")
            webbrowser.open(f"https://www.youtube.com/results?search_query={urllib.parse.quote(song)}")
            self.talk(f"Buscando {song} en YouTube.")

    # =========================================================================
    #  IA PRINCIPAL (Gemini + OpenRouter fallback)
    # =========================================================================

    def ask_gemini(self, prompt: str):
        """
        Consulta a la IA con lógica de fallback en dos niveles:
          1. Intenta Gemini (modelo principal, alta calidad).
          2. Si Gemini falla, escala a OpenRouter.
          3. Si ambos fallan, informa al usuario.
        """
        self._is_thinking = True
        self.set_status("⚡ PROCESANDO IA…", "#aa00ff")
        self.conversation_history.append({"role": "user", "content": prompt})
        max_msgs = GEMINI_HISTORY_TURNS * 2
        if len(self.conversation_history) > max_msgs:
            self.conversation_history = self.conversation_history[-max_msgs:]

        try:
            answer_text, provider = get_ai_response(prompt, self.conversation_history[:-1])
            if answer_text and answer_text.strip():
                clean = re.sub(r"[*_`#>]", "", answer_text).strip()
                self.conversation_history.append({"role": "model", "content": clean})
                log.info(f"[IA] Respuesta via {provider} ({len(clean)} chars)")
                self.talk(clean)
            else:
                self.talk("No obtuve respuesta del motor de IA.")
        except Exception as exc:
            log.error(f"[IA] Error inesperado: {exc}")
            if self.conversation_history and self.conversation_history[-1]["role"] == "user":
                self.conversation_history.pop()
            self.talk("Ocurrió un error al consultar la IA. Comandos locales activos.")
        finally:
            self._is_thinking = False
            self.set_status("SISTEMA LISTO", "#34D399")

    # =========================================================================
    #  CIERRE LIMPIO
    # =========================================================================

    def kill_process(self):
        log.info("Iniciando cierre limpio…")
        self.running = False
        if hasattr(self, "_clap_detector"):
            self._clap_detector.stop()
        self.tts_worker.wait_until_done(timeout=5.0)
        self.tts_worker.stop()
        time.sleep(0.2)
        with contextlib.suppress(Exception):
            self.destroy()
        with contextlib.suppress(Exception):
            win32api.CloseHandle(_mutex_handle)
        log.info("Darius cerrado correctamente.")
        sys.exit(0)


# ─────────────────────────────────────────────────────────────────────────────
#  EXPORT COMPATIBILITY
# ─────────────────────────────────────────────────────────────────────────────
_CMD_PATTERNS = DariusFinal._CMD_PATTERNS

if __name__ == "__main__":
    if "--self-test" in sys.argv:
        from self_test import main as run_test_cli
        run_test_cli()

    enable_dpi_awareness()
    app = DariusFinal()
    app.mainloop()
