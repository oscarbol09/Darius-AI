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

load_dotenv()

from config_loader import cfg  # noqa: E402

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

BASE_DIR  = Path(__file__).parent
LOG_FILE  = BASE_DIR / "darius.log"
CHAT_FILE       = BASE_DIR / "chat_history.txt"
APP_CACHE       = BASE_DIR / "apps_cache.json"
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

    def __init__(self, master, width: int = 480, height: int = 80, num_points: int = 120, **kwargs):
        super().__init__(
            master,
            fg_color="#111827",
            corner_radius=12,
            border_width=1,
            border_color="#1E293B",
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
            bg="#111827",
            highlightthickness=0,
            bd=0
        )
        self.canvas.pack(fill="both", expand=True, padx=8, pady=4)

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
            fill="#34D399",  # Emerald sutil
            width=1.0,
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND
        )
        self.line_secondary = self.canvas.create_line(
            *self._buf_secondary.ravel().tolist(),
            fill="#818CF8",  # Indigo armónico
            width=1.5,
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND
        )
        self.line_primary = self.canvas.create_line(
            *self._buf_primary.ravel().tolist(),
            fill="#38BDF8",  # Sky-400 primario
            width=2.5,
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
            amp = float(np.clip(audio_energy / 2500.0 * 28.0 + 4.0, 3.0, 34.0))
            y1 = cy + amp * np.sin(2.0 * x + p) * np.cos(0.8 * x - p * 0.4)
            y2 = cy + (amp * 0.65) * np.sin(3.2 * x - p * 1.2 + 1.0)
            y3 = cy + (amp * 0.35) * np.cos(1.5 * x + p * 0.8)
            self.canvas.itemconfig(self.line_primary, fill="#38BDF8")
            self.canvas.itemconfig(self.line_secondary, fill="#818CF8")
            self.canvas.itemconfig(self.line_tertiary, fill="#34D399")

        elif state == "SPEAKING":
            y1 = cy + 18.0 * np.sin(2.5 * x + p * 1.6) * np.sin(0.7 * x + p * 0.3)
            y2 = cy + 12.0 * np.cos(3.0 * x - p * 1.3)
            y3 = cy + 6.0 * np.sin(1.2 * x + p * 0.5)
            self.canvas.itemconfig(self.line_primary, fill="#38BDF8")
            self.canvas.itemconfig(self.line_secondary, fill="#60A5FA")
            self.canvas.itemconfig(self.line_tertiary, fill="#818CF8")

        elif state == "THINKING":
            y1 = cy + 11.0 * np.sin(5.5 * x + p * 2.2) * np.cos(2.0 * x - p)
            y2 = cy + 8.0 * np.sin(4.0 * x - p * 1.8 + 0.5)
            y3 = cy + 5.0 * np.cos(2.5 * x + p * 1.2)
            self.canvas.itemconfig(self.line_primary, fill="#A78BFA")
            self.canvas.itemconfig(self.line_secondary, fill="#818CF8")
            self.canvas.itemconfig(self.line_tertiary, fill="#F472B6")

        elif state == "MUTED":
            y1 = cy + 0.8 * np.sin(1.0 * x + p * 0.2)
            y2 = cy + 0.5 * np.cos(1.0 * x + p * 0.2)
            y3 = cy + np.zeros_like(x)
            self.canvas.itemconfig(self.line_primary, fill="#64748B")
            self.canvas.itemconfig(self.line_secondary, fill="#475569")
            self.canvas.itemconfig(self.line_tertiary, fill="#334155")

        else:  # IDLE
            y1 = cy + 4.5 * np.sin(1.8 * x + p * 0.6)
            y2 = cy + 2.8 * np.cos(1.2 * x - p * 0.4 + 0.8)
            y3 = cy + 1.5 * np.sin(0.8 * x + p * 0.3)
            self.canvas.itemconfig(self.line_primary, fill="#38BDF8")
            self.canvas.itemconfig(self.line_secondary, fill="#818CF8")
            self.canvas.itemconfig(self.line_tertiary, fill="#34D399")

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
        self.title("DARIUS AI — Sistema Operativo Autónomo")
        self.geometry("540x960")
        self.minsize(500, 850)
        self.configure(fg_color="#090D16")
        self.protocol("WM_DELETE_WINDOW", self.kill_process)

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
        self._ptt_active          = False

        self.listen_mode = DEFAULT_LISTEN_MODE
        self.conversation_history: list[dict] = []

        self.setup_tts_config()
        self.tts_worker = TTSWorker(voice_token=self.tts_voice_token)
        self.tts_worker.start()
        self.listener = sr.Recognizer()
        self.configure_listener()
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
            with sr.Microphone() as source:
                self.listener.adjust_for_ambient_noise(source, duration=1)
            log.info("Calibración completada.")
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
        try:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(CHAT_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {speaker}: {text}\n")
            self._trim_chat_file()
        except Exception as e:
            log.warning(f"No se pudo escribir historial local: {e}")

    def _trim_chat_file(self):
        try:
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
        # ── 1. HEADER & TELEMETRÍA ──────────────────────────────────────────
        header_card = ctk.CTkFrame(
            self, fg_color="#111827", corner_radius=12,
            border_width=1, border_color="#1E293B"
        )
        header_card.pack(pady=(14, 6), padx=16, fill="x")

        title_row = ctk.CTkFrame(header_card, fg_color="transparent")
        title_row.pack(fill="x", padx=16, pady=(10, 4))

        ctk.CTkLabel(
            title_row, text="DARIUS AI",
            font=("Segoe UI", 22, "bold"), text_color="#38BDF8"
        ).pack(side="left")

        ctk.CTkButton(
            title_row,
            text="⚙ AJUSTES IA",
            width=100,
            height=26,
            fg_color="#1F2937",
            hover_color="#374151",
            border_color="#38BDF8",
            border_width=1,
            text_color="#38BDF8",
            font=("Segoe UI", 10, "bold"),
            corner_radius=6,
            command=self._open_byok_settings,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkLabel(
            title_row, text="v6.5.0 • WINDOWS",
            font=("Segoe UI", 10, "bold"), text_color="#64748B"
        ).pack(side="right", pady=(4, 0))

        # Fila de badges / telemetría
        telemetry_row = ctk.CTkFrame(header_card, fg_color="transparent")
        telemetry_row.pack(fill="x", padx=16, pady=(0, 10))

        # Status Pill con punto de estado
        status_pill = ctk.CTkFrame(telemetry_row, fg_color="#1F2937", corner_radius=8)
        status_pill.pack(side="left", padx=(0, 6))

        self.status_dot = ctk.CTkLabel(
            status_pill, text="●",
            font=("Segoe UI", 12), text_color="#34D399"
        )
        self.status_dot.pack(side="left", padx=(8, 3), pady=2)

        self.status_label = ctk.CTkLabel(
            status_pill, text="SISTEMA LISTO",
            font=("Segoe UI", 10, "bold"), text_color="#F8FAFC"
        )
        self.status_label.pack(side="left", padx=(0, 8), pady=2)

        # Proveedor de IA Activo Pill
        self.llm_pill = ctk.CTkLabel(
            telemetry_row, text=self._llm_badge_text(),
            font=("Segoe UI", 10, "bold"), text_color="#38BDF8",
            fg_color="#1F2937", corner_radius=8, padx=8, pady=2
        )
        self.llm_pill.pack(side="left", padx=4)

        # Obsidian Pill
        obsidian_connected = bool(brain.vault_path and Path(brain.vault_path).exists())
        obsidian_text = "CONECTADO" if obsidian_connected else "LOCAL"
        obsidian_color = "#34D399" if obsidian_connected else "#94A3B8"
        self.brain_pill = ctk.CTkLabel(
            telemetry_row, text=f"🧠 OBSIDIAN: {obsidian_text}",
            font=("Segoe UI", 10, "bold"), text_color=obsidian_color,
            fg_color="#1F2937", corner_radius=8, padx=8, pady=2
        )
        self.brain_pill.pack(side="left", padx=4)

        # Apps Count Pill
        self.apps_pill = ctk.CTkLabel(
            telemetry_row, text="📦 APPS: 0",
            font=("Segoe UI", 10, "bold"), text_color="#94A3B8",
            fg_color="#1F2937", corner_radius=8, padx=8, pady=2
        )
        self.apps_pill.pack(side="left", padx=4)

        # ── 2. VISUALIZADOR VECTORIAL DE ONDAS (60 FPS) ───────────────────────
        self.visualizer = HighPerfWaveVisualizer(self, width=500, height=80)
        self.visualizer.pack(pady=4, padx=16, fill="x")

        # ── 3. CONSOLA DE CONVERSACIÓN / ACTIVIDAD ─────────────────────────────
        chat_card = ctk.CTkFrame(
            self, fg_color="#111827", corner_radius=12,
            border_width=1, border_color="#1E293B"
        )
        chat_card.pack(pady=6, padx=16, fill="both", expand=True)

        chat_header = ctk.CTkFrame(chat_card, fg_color="transparent")
        chat_header.pack(fill="x", padx=14, pady=(8, 2))

        ctk.CTkLabel(
            chat_header, text="CONSOLA DE ACTIVIDAD Y COMANDOS",
            font=("Segoe UI", 9, "bold"), text_color="#64748B"
        ).pack(side="left")

        self.mode_pill = ctk.CTkLabel(
            chat_header, text=self._mode_label_text(),
            font=("Segoe UI", 9, "bold"), text_color="#38BDF8"
        )
        self.mode_pill.pack(side="right")

        self.chat_display = ctk.CTkTextbox(
            chat_card, font=("Consolas", 11),
            state="disabled", fg_color="#0B0F19",
            border_color="#1E293B", border_width=1,
            scrollbar_button_color="#1F2937",
            scrollbar_button_hover_color="#38BDF8"
        )
        self.chat_display.pack(padx=12, pady=(2, 12), fill="both", expand=True)

        tb = self.chat_display._textbox
        tb.tag_config("oscar", foreground="#34D399", font=("Consolas", 11, "bold"))
        tb.tag_config("darius", foreground="#38BDF8", font=("Consolas", 11, "bold"))
        tb.tag_config("system", foreground="#818CF8", font=("Consolas", 11, "bold"))
        tb.tag_config("warn", foreground="#FBBF24", font=("Consolas", 11, "bold"))
        tb.tag_config("oscar_text", foreground="#F1F5F9", font=("Consolas", 11))
        tb.tag_config("darius_text", foreground="#E2E8F0", font=("Consolas", 11))
        tb.tag_config("system_text", foreground="#94A3B8", font=("Consolas", 11))
        tb.tag_config("timestamp", foreground="#64748B", font=("Consolas", 9))

        # ── 4. CAMPO DE ENTRADA Y ENVÍO RÁPIDO ────────────────────────────────
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.pack(pady=4, padx=16, fill="x")

        self.text_input = ctk.CTkEntry(
            input_frame, placeholder_text="Escribe un comando o consulta para Darius…",
            font=("Segoe UI", 11), fg_color="#1F2937",
            border_color="#374151", border_width=1,
            text_color="#F8FAFC", placeholder_text_color="#64748B",
            height=38, corner_radius=8
        )
        self.text_input.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.text_input.bind("<Return>", self._on_text_submit)

        ctk.CTkButton(
            input_frame, text="ENVIAR ▶", width=84, height=38,
            fg_color="#38BDF8", hover_color="#0284C7",
            text_color="#090D16", font=("Segoe UI", 11, "bold"),
            corner_radius=8, command=self._on_text_submit
        ).pack(side="right")

        # ── 5. BOTONES DE ACCIÓN PRINCIPAL ────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=4, padx=16, fill="x")

        self.start_btn = ctk.CTkButton(
            btn_frame, text="⚡ INICIALIZAR", fg_color="#38BDF8",
            hover_color="#0284C7", text_color="#090D16",
            font=("Segoe UI", 11, "bold"), height=34, corner_radius=8,
            command=self.start_system
        )
        self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.mute_btn = ctk.CTkButton(
            btn_frame, text="🔇 SILENCIO", fg_color="#F87171",
            hover_color="#EF4444", text_color="#090D16",
            state="disabled", font=("Segoe UI", 11, "bold"),
            height=34, corner_radius=8, command=self.toggle_mute
        )
        self.mute_btn.pack(side="left", fill="x", expand=True, padx=4)

        self.clear_btn = ctk.CTkButton(
            btn_frame, text="🗑 NUEVA SESIÓN", fg_color="#1F2937",
            hover_color="#374151", text_color="#F8FAFC",
            font=("Segoe UI", 11), height=34, corner_radius=8,
            command=self.reset_conversation
        )
        self.clear_btn.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # ── 6. SELECTOR DE MODO DE ACTIVACIÓN ─────────────────────────────────
        mode_frame = ctk.CTkFrame(
            self, fg_color="#111827", corner_radius=12,
            border_width=1, border_color="#1E293B"
        )
        mode_frame.pack(pady=(4, 14), padx=16, fill="x")

        ctk.CTkLabel(
            mode_frame, text="MODO DE ACTIVACIÓN DE VOZ",
            font=("Segoe UI", 9, "bold"), text_color="#64748B"
        ).pack(pady=(8, 4))

        btn_mode_row = ctk.CTkFrame(mode_frame, fg_color="transparent")
        btn_mode_row.pack(pady=(0, 6), padx=10, fill="x")

        self._mode_btns = {}
        modes = [
            (LISTEN_MODE_PTT,  f"🎙 PTT ({LISTEN_KEY.upper()})", "#38BDF8"),
            (LISTEN_MODE_NAME, f"🔤 NOMBRE («{ASSISTANT_NAME}»)", "#34D399"),
            (LISTEN_MODE_AUTO, "🔄 AUTO", "#818CF8"),
        ]
        for mode_id, label, active_color in modes:
            is_active = (mode_id == self.listen_mode)
            btn = ctk.CTkButton(
                btn_mode_row, text=label,
                fg_color=active_color if is_active else "#1F2937",
                hover_color=active_color,
                text_color="#090D16" if is_active else "#94A3B8",
                border_color=active_color if is_active else "#374151",
                border_width=1,
                font=("Segoe UI", 10, "bold"),
                height=30, corner_radius=6,
                command=lambda m=mode_id: self._set_listen_mode(m)
            )
            btn.pack(side="left", fill="x", expand=True, padx=3)
            self._mode_btns[mode_id] = (btn, active_color)

        self.ptt_hint = ctk.CTkLabel(
            mode_frame,
            text=f"💡 Modo PTT: mantén presionado [{LISTEN_KEY.upper()}] mientras hablas",
            font=("Segoe UI", 10), text_color="#94A3B8"
        )
        if self.listen_mode == LISTEN_MODE_PTT:
            self.ptt_hint.pack(pady=(0, 8))

    def _mode_label_text(self) -> str:
        icons = {
            LISTEN_MODE_PTT:  f"🎙 PTT • [{LISTEN_KEY.upper()}]",
            LISTEN_MODE_NAME: f"🔤 NOMBRE • «{ASSISTANT_NAME}»",
            LISTEN_MODE_AUTO: "🔄 AUTO • Escucha continua",
        }
        return icons.get(self.listen_mode, "")

    def _set_listen_mode(self, mode: str):
        self.listen_mode = mode
        for mode_id, (btn, active_color) in self._mode_btns.items():
            is_active = (mode_id == mode)
            btn.configure(
                fg_color=active_color if is_active else "#1F2937",
                text_color="#090D16" if is_active else "#94A3B8",
                border_color=active_color if is_active else "#374151",
            )
        if hasattr(self, "mode_pill"):
            self.mode_pill.configure(text=self._mode_label_text())
        if mode == LISTEN_MODE_PTT:
            self.ptt_hint.pack(pady=(0, 8))
            if not KEYBOARD_AVAILABLE:
                self.talk("Advertencia: librería keyboard no instalada. Ejecuta pip install keyboard")
        else:
            with contextlib.suppress(Exception):
                self.ptt_hint.pack_forget()
        log.info(f"Modo cambiado a: {mode}")
        self.set_status(f"MODO: {mode.upper()}", "#38BDF8")

    def _llm_badge_text(self) -> str:
        prov = cfg.active_provider.upper()
        return f"🤖 IA: {prov}"

    def _open_byok_settings(self):
        from byok_settings import BYOKSettingsModal
        BYOKSettingsModal(self, on_save_callback=self._on_byok_settings_saved)

    def _on_byok_settings_saved(self):
        if hasattr(self, "llm_pill"):
            self.llm_pill.configure(text=self._llm_badge_text())
        prov_name = cfg.active_provider.upper()
        self.set_status(f"IA: {prov_name}", "#38BDF8")
        self.talk(f"Configuración de IA actualizada. Proveedor activo: {prov_name}.")

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
            import audioop

            import pyaudio
            pa = pyaudio.PyAudio()
            try:
                stream = pa.open(format=pyaudio.paInt16, channels=1,
                                 rate=16000, input=True, frames_per_buffer=512)
                while self.running:
                    try:
                        data = stream.read(512, exception_on_overflow=False)
                        self._current_audio_level = float(audioop.rms(data, 2))
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
        import audioop
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
                self._current_audio_level = float(audioop.rms(data, 2))
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
            with sr.Microphone() as source:
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

    _CMD_PATTERNS = [
        (_RE_HORA,                                                                "_cmd_hora"),
        (_RE_FECHA,                                                               "_cmd_fecha"),
        (re.compile(r"\b(nueva conversación|olvida todo|resetea la memoria)\b"), "_cmd_reset"),
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

if __name__ == "__main__":
    enable_dpi_awareness()
    app = DariusFinal()
    app.mainloop()
