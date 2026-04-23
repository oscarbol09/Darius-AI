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

# ── Carga de .env ANTES de cualquier otro import que use os.getenv ──────────
from dotenv import load_dotenv
load_dotenv()   # busca .env en el directorio del script (BASE_DIR)

import speech_recognition as sr
import win32com.client
import win32event
import win32api
import winerror
import os
import datetime
import customtkinter as ctk
import threading
import numpy as np
import tkinter as tk
import time
import sys
import re
import json
import queue
import logging
import webbrowser
import winreg
import urllib.parse
import urllib.request
import random
from pathlib import Path
from difflib import get_close_matches, SequenceMatcher
from google import genai
from google.genai import types
import subprocess
from config_loader import cfg

from windows_commands import (
    resolve_and_launch as wincmd_launch,
    resolve_action     as wincmd_resolve_action,
    run_action         as wincmd_run_action,
)

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

ASSISTANT_NAME       = cfg.ASSISTANT_NAME
USER_NAME            = cfg.USER_NAME
GEMINI_MODEL         = cfg.GEMINI_MODEL
GEMINI_MAX_TOKENS    = cfg.GEMINI_MAX_TOKENS
GEMINI_TEMPERATURE   = cfg.GEMINI_TEMPERATURE
GEMINI_HISTORY_TURNS = cfg.GEMINI_HISTORY_TURNS
TTS_RATE             = cfg.TTS_RATE
TTS_VOLUME           = cfg.TTS_VOLUME
MIC_ENERGY_THRESHOLD = cfg.MIC_ENERGY_THRESHOLD
MIC_PAUSE_THRESHOLD  = cfg.MIC_PAUSE_THRESHOLD
MIC_LISTEN_TIMEOUT   = cfg.MIC_LISTEN_TIMEOUT
MIC_PHRASE_LIMIT     = cfg.MIC_PHRASE_LIMIT
APP_CACHE_HOURS      = cfg.APP_CACHE_HOURS
SPEAKING_TAIL_SECS   = cfg.SPEAKING_TAIL_SECS

LISTEN_MODE_PTT   = "PTT"
LISTEN_MODE_NAME  = "NOMBRE"
LISTEN_MODE_AUTO  = "AUTO"

LISTEN_KEY             = cfg.LISTEN_KEY
DEFAULT_LISTEN_MODE    = cfg.DEFAULT_LISTEN_MODE
NAME_SIMILARITY_CUTOFF = cfg.NAME_SIMILARITY_CUTOFF
MIN_WORDS_WITHOUT_NAME = cfg.MIN_WORDS_WITHOUT_NAME

BASE_DIR  = Path(__file__).parent
LOG_FILE  = BASE_DIR / "darius.log"
CHAT_FILE = BASE_DIR / "chat_history.txt"
APP_CACHE = BASE_DIR / "apps_cache.json"

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

# ─────────────────────────────────────────────────────────────────────────────
#  GEMINI CLIENT
# ─────────────────────────────────────────────────────────────────────────────

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    log.critical("No se encontró GEMINI_API_KEY en las variables de entorno ni en .env")
    sys.exit(1)

gemini_client = genai.Client(api_key=API_KEY)

# ─────────────────────────────────────────────────────────────────────────────
#  OPENROUTER FALLBACK
# ─────────────────────────────────────────────────────────────────────────────

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Lista de modelos gratuitos y estables de OpenRouter (orden = preferencia)
# Se selecciona uno aleatoriamente en cada intento de fallback para distribuir carga
_OPENROUTER_MODELS = [
    "nvidia/nemotron-3-super:free",
    "meta-llama/llama-3-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "arcee-ai/arcee-trinity:free",
    "google/gemma-3-4b-it:free",
    "microsoft/phi-3-mini-128k-instruct:free",
    "qwen/qwen3-8b:free",
]

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _ask_openrouter(prompt: str, system_instruction: str) -> str:
    """
    Llama a la API de OpenRouter con un modelo gratuito seleccionado al azar.
    Itera sobre la lista si el primer intento falla, garantizando la mayor
    disponibilidad posible.

    Args:
        prompt:             Mensaje del usuario.
        system_instruction: Instrucción de sistema (personalidad de Darius).

    Returns:
        Texto de respuesta del modelo.

    Raises:
        RuntimeError: Si todos los modelos de la lista fallan.
    """
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY no configurada")

    import json as _json
    import urllib.request as _req

    # Barajar la lista para evitar que siempre se martille el mismo modelo
    models = _OPENROUTER_MODELS.copy()
    random.shuffle(models)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://darius-ai.local",   # identificador del proyecto
        "X-Title": "Darius AI Assistant",
    }

    last_error: Exception | None = None
    for model in models:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user",   "content": prompt},
            ],
            "max_tokens": GEMINI_MAX_TOKENS,
            "temperature": GEMINI_TEMPERATURE,
        }
        try:
            data    = _json.dumps(payload).encode("utf-8")
            request = _req.Request(_OPENROUTER_URL, data=data, headers=headers, method="POST")
            with _req.urlopen(request, timeout=20) as resp:
                body = _json.loads(resp.read().decode("utf-8"))
                # Validar estructura antes de acceder
                choices = body.get("choices", [])
                if not choices:
                    raise ValueError(f"OpenRouter devolvió choices vacío para modelo '{model}'")
                message = choices[0].get("message", {})
                content = message.get("content", "")
                if not content or not content.strip():
                    finish = choices[0].get("finish_reason", "unknown")
                    raise ValueError(f"Respuesta vacía de '{model}' (finish_reason={finish})")
                log.info(f"[OpenRouter] Respuesta de modelo '{model}' obtenida.")
                return content.strip()
        except TimeoutError as exc:
            log.warning(f"[OpenRouter] Timeout en modelo '{model}': {exc}")
            last_error = exc
            continue
        except Exception as exc:
            log.warning(f"[OpenRouter] Modelo '{model}' falló: {exc}")
            last_error = exc
            continue

    raise RuntimeError(f"Todos los modelos de OpenRouter fallaron. Último error: {last_error}")

# ─────────────────────────────────────────────────────────────────────────────
#  CONTROL DE VOLUMEN
# ─────────────────────────────────────────────────────────────────────────────

try:
    from ctypes import cast, POINTER
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
        os.system("nircmd.exe changesysvolume 5000")

def volume_down():
    if PYCAW_AVAILABLE:
        _volume_ctrl.SetMasterVolumeLevelScalar(max(0.0, _volume_ctrl.GetMasterVolumeLevelScalar() - 0.1), None)
    else:
        os.system("nircmd.exe changesysvolume -5000")

def volume_mute():
    if PYCAW_AVAILABLE:
        _volume_ctrl.SetMute(1, None)
    else:
        os.system("nircmd.exe mutesysvolume 1")

# ─────────────────────────────────────────────────────────────────────────────
#  WAKE WORD / TECLADO
# ─────────────────────────────────────────────────────────────────────────────

try:
    import pvporcupine, pyaudio
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
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _strip_name(text: str) -> str:
    """Quita el nombre del asistente del texto y devuelve el comando limpio."""
    return text.replace(ASSISTANT_NAME, "").strip()


# ─────────────────────────────────────────────────────────────────────────────
#  CLASE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

class DariusFinal(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("DARIUS AI - SISTEMA OPERATIVO")
        self.geometry("520x920")
        self.configure(fg_color="#0f0f0f")
        self.protocol("WM_DELETE_WINDOW", self.kill_process)

        self.running              = True
        self.is_listening         = False
        self.is_speaking          = threading.Event()
        self.waiting_for_command  = False
        self.is_muted             = False
        self.installed_apps       = {}
        self._current_audio_level = 0.0
        self._pending_action: dict | None = None
        self._ptt_active          = False

        self.listen_mode = DEFAULT_LISTEN_MODE
        self.conversation_history: list[dict] = []
        self.tts_queue = queue.Queue()

        self.setup_tts_config()
        self.listener = sr.Recognizer()
        self.configure_listener()
        self.setup_ui()
        self._start_tts_worker()
        self.scan_apps_async()

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

    def _start_tts_worker(self):
        def worker():
            import pythoncom
            pythoncom.CoInitialize()
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            if self.tts_voice_token:
                speaker.Voice = self.tts_voice_token
            speaker.Rate   = TTS_RATE
            speaker.Volume = TTS_VOLUME
            while True:
                text = self.tts_queue.get()
                if text is None:
                    break
                try:
                    self.is_speaking.set()
                    speaker.Speak(text)
                except Exception as e:
                    log.error(f"TTS error: {e}")
                finally:
                    self.is_speaking.clear()
                    time.sleep(SPEAKING_TAIL_SECS)
                    self.tts_queue.task_done()
            pythoncom.CoUninitialize()
        threading.Thread(target=worker, daemon=True, name="tts-worker").start()

    def talk(self, text: str):
        log.info(f"DARIUS: {text}")
        self.after(0, self._insert_message, "Darius", text)
        self._append_chat_file("DARIUS", text)
        if not self.is_muted:
            self.tts_queue.put(text)

    # =========================================================================
    #  HISTORIAL
    # =========================================================================

    def _append_chat_file(self, speaker: str, text: str):
        try:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(CHAT_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {speaker}: {text}\n")
        except Exception as e:
            log.warning(f"No se pudo escribir historial: {e}")

    # =========================================================================
    #  UI
    # =========================================================================

    def setup_ui(self):
        ctk.CTkLabel(self, text="DARIUS AI",
                     font=("Orbitron", 32, "bold"), text_color="#00fbff").pack(pady=(20, 0))

        self.status_label = ctk.CTkLabel(self, text="SISTEMA LISTO",
                                         font=("Arial", 12), text_color="gray")
        self.status_label.pack(pady=3)

        self.mode_label = ctk.CTkLabel(self, text=self._mode_label_text(),
                                       font=("Consolas", 11), text_color="#555555")
        self.mode_label.pack(pady=0)

        self.canvas = tk.Canvas(self, width=350, height=100,
                                bg="#0f0f0f", highlightthickness=0)
        self.canvas.pack(pady=10)
        self.wave_bars = [
            self.canvas.create_rectangle(
                10 + i * 14, 45, 10 + i * 14 + 8, 55, fill="#00fbff", outline="")
            for i in range(25)
        ]

        self.chat_display = ctk.CTkTextbox(
            self, width=470, height=310, font=("Consolas", 12),
            state="disabled", fg_color="#111111",
            border_color="#00fbff", border_width=1,
            scrollbar_button_color="#00fbff",
            scrollbar_button_hover_color="#00aacc"
        )
        self.chat_display.pack(pady=8)
        tb = self.chat_display._textbox
        tb.tag_config("oscar",       foreground="#00ff88", font=("Consolas", 12, "bold"))
        tb.tag_config("darius",      foreground="#00fbff", font=("Consolas", 12, "bold"))
        tb.tag_config("oscar_text",  foreground="#ccffdd", font=("Consolas", 12))
        tb.tag_config("darius_text", foreground="#ddfeff", font=("Consolas", 12))
        tb.tag_config("timestamp",   foreground="#555555", font=("Consolas", 10))
        tb.tag_config("warn",        foreground="#ffaa00", font=("Consolas", 12, "bold"))

        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.pack(pady=5, padx=20, fill="x")

        self.text_input = ctk.CTkEntry(
            input_frame, placeholder_text="Escribe un comando…",
            font=("Consolas", 12), fg_color="#1a1a1a",
            border_color="#00fbff", border_width=1, text_color="#ffffff"
        )
        self.text_input.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.text_input.bind("<Return>", self._on_text_submit)

        ctk.CTkButton(
            input_frame, text="▶", width=40, fg_color="#00fbff",
            text_color="black", font=("Arial", 14, "bold"),
            command=self._on_text_submit
        ).pack(side="right")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=5)

        self.start_btn = ctk.CTkButton(
            btn_frame, text="INICIALIZAR", fg_color="#00fbff",
            text_color="black", font=("Arial", 13, "bold"),
            command=self.start_system
        )
        self.start_btn.pack(side="left", padx=5)

        self.mute_btn = ctk.CTkButton(
            btn_frame, text="🔇 SILENCIO", fg_color="#ff5555",
            state="disabled", font=("Arial", 13), command=self.toggle_mute
        )
        self.mute_btn.pack(side="left", padx=5)

        self.clear_btn = ctk.CTkButton(
            btn_frame, text="🗑 NUEVA CONV.", fg_color="#555555",
            font=("Arial", 13), command=self.reset_conversation
        )
        self.clear_btn.pack(side="left", padx=5)

        mode_frame = ctk.CTkFrame(self, fg_color="#111111", corner_radius=8)
        mode_frame.pack(pady=8, padx=20, fill="x")

        ctk.CTkLabel(mode_frame, text="MODO DE ACTIVACIÓN",
                     font=("Consolas", 10, "bold"), text_color="#555555").pack(pady=(6, 2))

        btn_mode_row = ctk.CTkFrame(mode_frame, fg_color="transparent")
        btn_mode_row.pack(pady=(0, 8))

        self._mode_btns = {}
        modes = [
            (LISTEN_MODE_PTT,  f"🎙 PTT ({LISTEN_KEY.upper()})", "#ff8800"),
            (LISTEN_MODE_NAME, "🔤 NOMBRE",                       "#00fbff"),
            (LISTEN_MODE_AUTO, "🔄 AUTO",                          "#888888"),
        ]
        for mode_id, label, color in modes:
            btn = ctk.CTkButton(
                btn_mode_row, text=label, width=130,
                fg_color=color if mode_id == self.listen_mode else "#2a2a2a",
                text_color="black" if mode_id == self.listen_mode else "#aaaaaa",
                font=("Arial", 12, "bold"),
                command=lambda m=mode_id: self._set_listen_mode(m)
            )
            btn.pack(side="left", padx=4)
            self._mode_btns[mode_id] = (btn, color)

        self.ptt_hint = ctk.CTkLabel(
            mode_frame,
            text=f"💡 Modo PTT: mantén presionado [{LISTEN_KEY.upper()}] mientras hablas",
            font=("Arial", 10), text_color="#444444"
        )
        if self.listen_mode == LISTEN_MODE_PTT:
            self.ptt_hint.pack(pady=(0, 6))

    def _mode_label_text(self) -> str:
        icons = {
            LISTEN_MODE_PTT:  f"🎙 PTT — tecla: [{LISTEN_KEY.upper()}]",
            LISTEN_MODE_NAME: f"🔤 NOMBRE — solo responde a «{ASSISTANT_NAME}»",
            LISTEN_MODE_AUTO: "🔄 AUTO — escucha todo",
        }
        return icons.get(self.listen_mode, "")

    def _set_listen_mode(self, mode: str):
        self.listen_mode = mode
        for mode_id, (btn, color) in self._mode_btns.items():
            btn.configure(fg_color=color if mode_id == mode else "#2a2a2a",
                          text_color="black" if mode_id == mode else "#aaaaaa")
        self.mode_label.configure(text=self._mode_label_text())
        if mode == LISTEN_MODE_PTT:
            self.ptt_hint.pack(pady=(0, 6))
            if not KEYBOARD_AVAILABLE:
                self.talk("Advertencia: librería keyboard no instalada. Ejecuta pip install keyboard")
        else:
            try:
                self.ptt_hint.pack_forget()
            except Exception:
                pass
        log.info(f"Modo cambiado a: {mode}")
        self.set_status(self._mode_label_text(), "#00fbff")

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
        tb        = self.chat_display._textbox
        ts        = datetime.datetime.now().strftime("%H:%M")
        is_darius = speaker.lower() == "darius"
        name_tag  = "darius"      if is_darius else "oscar"
        text_tag  = tag or ("darius_text" if is_darius else "oscar_text")
        prefix    = "🤖 DARIUS"   if is_darius else f"🧑 {USER_NAME.upper()}"
        tb.insert("end", "\n")
        tb.insert("end", f"[{ts}] ", "timestamp")
        tb.insert("end", f"{prefix}\n", name_tag)
        tb.insert("end", f"   {text}\n", text_tag)
        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")

    def add_to_chat(self, speaker: str, text: str):
        self.after(0, self._insert_message, speaker, text)

    def set_status(self, text: str, color: str = "gray"):
        self.after(0, self.status_label.configure, {"text": text, "text_color": color})

    # =========================================================================
    #  ANIMACIÓN
    # =========================================================================

    def animate_logic(self):
        if not self.running:
            return
        if self.is_listening:
            energy = self._current_audio_level
            base_h = np.clip(energy / 4000 * 70, 4, 75)
            for bar in self.wave_bars:
                h = np.clip(base_h * np.random.uniform(0.5, 1.5), 4, 75)
                x0, _, x1, _ = self.canvas.coords(bar)
                self.canvas.coords(bar, x0, 50 - h/2, x1, 50 + h/2)
            self.after(80, self.animate_logic)
        elif self.is_speaking.is_set():
            for bar in self.wave_bars:
                h = np.random.randint(8, 45)
                x0, _, x1, _ = self.canvas.coords(bar)
                self.canvas.coords(bar, x0, 50 - h/2, x1, 50 + h/2)
            self.after(120, self.animate_logic)
        else:
            for bar in self.wave_bars:
                x0, _, x1, _ = self.canvas.coords(bar)
                self.canvas.coords(bar, x0, 45, x1, 55)

    def _start_audio_level_monitor(self):
        def monitor():
            import audioop, pyaudio
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
                    time.sleep(0.05)
                stream.stop_stream(); stream.close()
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
            self.mute_btn.configure(text="🔊 ESCUCHAR", fg_color="#00ff88")
            self.add_to_chat("Darius", "Modo discreto activado.")
        else:
            self.mute_btn.configure(text="🔇 SILENCIO", fg_color="#ff5555")
            self.talk("Sistemas de escucha reactivados.")

    def reset_conversation(self):
        self.conversation_history.clear()
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
                age_h    = (datetime.datetime.now() - saved_at).total_seconds() / 3600
                if age_h < APP_CACHE_HOURS:
                    self.installed_apps = data["apps"]
                    log.info(f"Apps desde caché: {len(self.installed_apps)}")
                    self.after(0, self.status_label.configure,
                               {"text": f"BASE DE DATOS: {len(self.installed_apps)} APPS",
                                "text_color": "#00ff88"})
                    return
            except Exception as e:
                log.warning(f"Caché inválida: {e}")
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
        for folder in [
            Path(os.environ.get("PROGRAMFILES",      r"C:\Program Files")),
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")),
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs",
        ]:
            if not folder.exists():
                continue
            try:
                for exe in folder.rglob("*.exe"):
                    stem = exe.stem.lower().replace("-", " ").replace("_", " ")
                    if stem not in apps:
                        apps[stem] = str(exe)
            except PermissionError:
                continue
        self.installed_apps = apps
        log.info(f"Apps detectadas: {len(apps)}")
        try:
            APP_CACHE.write_text(
                json.dumps({"saved_at": datetime.datetime.now().isoformat(), "apps": apps},
                           ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            log.warning(f"No se pudo guardar caché: {e}")
        self.after(0, self.status_label.configure,
                   {"text": f"BASE DE DATOS: {len(apps)} APPS", "text_color": "#00ff88"})

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
        self.start_btn.configure(state="disabled", text="NÚCLEO ONLINE")
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
            if self.is_muted or self.is_speaking.is_set():
                time.sleep(0.05); continue
            if self.listen_mode == LISTEN_MODE_PTT:
                time.sleep(0.1); continue
            self.listen_and_process()

    def _ptt_loop(self):
        if not KEYBOARD_AVAILABLE:
            log.warning("keyboard no disponible — fallback a NOMBRE.")
            self.listen_mode = LISTEN_MODE_NAME
            self.after(0, self._set_listen_mode, LISTEN_MODE_NAME)
            self.main_loop(); return

        log.info(f"[PTT] Loop iniciado. Tecla: [{LISTEN_KEY}]")
        key_was_down = False
        while self.running:
            if self.is_muted:
                time.sleep(0.1); continue
            key_down = keyboard.is_pressed(LISTEN_KEY)
            if key_down and not key_was_down and not self.is_speaking.is_set():
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
        import audioop, pyaudio, wave, io
        RATE, CHUNK, CHANNELS = 16000, 512, 1
        pa = pyaudio.PyAudio()
        frames = []
        try:
            stream = pa.open(format=pyaudio.paInt16, channels=CHANNELS,
                             rate=RATE, input=True, frames_per_buffer=CHUNK)
            while KEYBOARD_AVAILABLE and keyboard.is_pressed(LISTEN_KEY) and self.running:
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
                self._current_audio_level = float(audioop.rms(data, 2))
            stream.stop_stream(); stream.close()
        except Exception as e:
            log.error(f"[PTT] Error de grabación: {e}")
            pa.terminate(); self.set_status("LISTO", "gray"); return
        finally:
            pa.terminate()
        if not frames:
            self.set_status("LISTO", "gray"); return
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wf:
            wf.setnchannels(CHANNELS); wf.setsampwidth(2)
            wf.setframerate(RATE); wf.writeframes(b"".join(frames))
        wav_buffer.seek(0)
        try:
            with sr.AudioFile(wav_buffer) as source:
                audio = self.listener.record(source)
            text = self.listener.recognize_google(audio, language="es-ES").lower()
            log.info(f"[PTT] Reconocido: '{text}'")
            self.add_to_chat(USER_NAME, text)
            self._append_chat_file(USER_NAME.upper(), text)
            self.execute_command(_strip_name(text) or text)
        except sr.UnknownValueError:
            log.debug("[PTT] Audio no reconocido."); self.set_status("LISTO", "gray")
        except sr.RequestError as e:
            log.error(f"[PTT] STT error: {e}"); self.talk("Error de conexión con el servicio de voz.")
        except Exception as e:
            log.error(f"[PTT] Error: {e}", exc_info=True); self.set_status("LISTO", "gray")

    def _porcupine_loop(self):
        import pvporcupine, pyaudio, struct
        access_key = os.getenv("PORCUPINE_ACCESS_KEY", "")
        if not access_key:
            self.main_loop(); return
        try:
            porcupine = pvporcupine.create(access_key=access_key, keywords=["computer"])
            pa        = pyaudio.PyAudio()
            stream    = pa.open(rate=porcupine.sample_rate, channels=1,
                                format=pyaudio.paInt16, input=True,
                                frames_per_buffer=porcupine.frame_length)
            while self.running:
                if self.is_muted or self.is_speaking.is_set():
                    time.sleep(0.05); continue
                pcm   = stream.read(porcupine.frame_length, exception_on_overflow=False)
                pcm   = struct.unpack_from("h" * porcupine.frame_length, pcm)
                if porcupine.process(pcm) >= 0:
                    self.listen_and_process()
            stream.stop_stream(); stream.close()
            pa.terminate(); porcupine.delete()
        except Exception as e:
            log.error(f"Porcupine error: {e}"); self.main_loop()

    # =========================================================================
    #  RECONOCIMIENTO DE VOZ
    # =========================================================================

    def listen_and_process(self):
        try:
            with sr.Microphone() as source:
                if self.is_speaking.is_set(): return
                self.set_status("ESCUCHANDO…", "#00fbff")
                self.is_listening = True
                self.after(0, self.animate_logic)
                audio = self.listener.listen(source, timeout=MIC_LISTEN_TIMEOUT,
                                             phrase_time_limit=MIC_PHRASE_LIMIT)
                self.is_listening = False
                if self.is_speaking.is_set(): return
                self.set_status("PROCESANDO…", "#ffaa00")
                text = self.listener.recognize_google(audio, language="es-ES").lower()
                log.info(f"Reconocido: '{text}'")
                self.process_recognized_text(text)
        except sr.WaitTimeoutError:
            pass
        except sr.UnknownValueError:
            log.debug("Audio no reconocido.")
        except sr.RequestError as e:
            log.error(f"STT error: {e}"); self.talk("Error de conexión con el servicio de voz.")
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
                clean_text = _strip_name(text)
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
        words = text.split()
        if ASSISTANT_NAME in text:
            return True, _strip_name(text)
        if words:
            similarity = SequenceMatcher(None, ASSISTANT_NAME, words[0]).ratio()
            if similarity >= NAME_SIMILARITY_CUTOFF:
                log.debug(f"[NOMBRE] Variante aceptada: '{words[0]}' ({similarity:.2f})")
                return True, " ".join(words[1:]).strip()
        return False, text

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

    _CMD_PATTERNS = [
        (re.compile(r"\b(qué hora|hora exacta)\b"),                              "_cmd_hora"),
        (re.compile(r"\b(qué fecha|fecha de hoy|día de hoy)\b"),                 "_cmd_fecha"),
        (re.compile(r"\b(nueva conversación|olvida todo|resetea la memoria)\b"), "_cmd_reset"),
        (re.compile(r"\b(reproduce|pon|ponme|coloca|escuchar|música)\b"),        "_cmd_youtube"),
        (re.compile(r"\b(busca|buscar|googlea)\b"),                              "_cmd_buscar"),
        (re.compile(r"\b(abre|abrir|lanza|ejecuta|inicia|muestra)\b"),           "_cmd_abrir"),
        (re.compile(r"\bsubir\s+volumen\b"),                                     "_cmd_vol_up"),
        (re.compile(r"\bbajar\s+volumen\b"),                                     "_cmd_vol_down"),
        (re.compile(r"\bsilenciar\b"),                                           "_cmd_vol_mute"),
        (re.compile(r"\b(cómo estás|estado del sistema|status)\b"),              "_cmd_estado"),
        (re.compile(r"\b(adiós|adios|descansa|apágate|cerrar darius)\b"),        "_cmd_cerrar"),
        # BUG 3 FIX ↓ — usa los regex más específicos definidos arriba
        (_RE_APAGAR,    "_cmd_apagar_pc"),
        (_RE_REINICIAR, "_cmd_reiniciar_pc"),
        # BUG 4 FIX ↓ — _cmd_accion ahora solo captura acciones de sistema
        (_RE_ACCION,    "_cmd_accion"),
    ]

    def execute_command(self, cmd: str):
        # BUG 2 FIX: limpia el nombre si todavía aparece en el comando
        # (puede ocurrir en entrada de texto manual o modo AUTO sin limpieza previa)
        cmd = _strip_name(cmd.strip())
        if not cmd:
            return
        log.info(f"Ejecutando: '{cmd}'")

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
        self.talk(f"Son las {datetime.datetime.now().strftime('%H:%M')}.")

    def _cmd_fecha(self, _):
        self.talk(f"Hoy es {datetime.datetime.now().strftime('%d de %B de %Y')}.")

    def _cmd_reset(self, _):
        self.reset_conversation()

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
        volume_up(); self.talk("Volumen incrementado.")

    def _cmd_vol_down(self, _):
        volume_down(); self.talk("Volumen disminuido.")

    def _cmd_vol_mute(self, _):
        volume_mute(); self.talk("Audio silenciado.")

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
        self._pending_action = {
            "desc": "Apagar el equipo en 10 segundos",
            "confirm": True,
            "_fn": lambda: subprocess.run(["shutdown", "/s", "/t", "10"], shell=False, check=False),
        }
        self.talk("Estás a punto de apagar el equipo. Di confirmar para proceder o cancelar para abortar.")
        self.set_status("⚠ ESPERANDO CONFIRMACIÓN", "#ffaa00")

    def _cmd_reiniciar_pc(self, _):
        self._pending_action = {
            "desc": "Reiniciar el equipo en 10 segundos",
            "confirm": True,
            "_fn": lambda: subprocess.run(["shutdown", "/r", "/t", "10"], shell=False, check=False),
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
            entry               = self._pending_action
            self._pending_action = None
            self.set_status("LISTO", "gray")
            self.talk(f"Ejecutando: {entry['desc']}.")
            if "_fn" in entry:
                threading.Thread(target=entry["_fn"], daemon=True, name="action-direct").start()
            else:
                self._execute_action(entry)
        elif any(w in t for w in ["cancelar", "cancela", "no", "abortar", "detener"]):
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
        lines = [l.strip() for l in raw.splitlines()
                 if l.strip() and not set(l.strip()) <= set("-= |+")]
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
                os.startfile(path) if os.path.isfile(path) else os.system(path)
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
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
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
    #  GEMINI  (con fallback automático a OpenRouter)
    # =========================================================================

    # Instrucción de sistema compartida por Gemini y el fallback OpenRouter
    def _build_system_instruction(self) -> str:
        return (
            f"Eres Darius, asistente de IA con personalidad futurista y directa. "
            f"El usuario se llama {USER_NAME}. "
            "Responde en español, conciso (máximo 3 oraciones), "
            "sin markdown, sin asteriscos, sin bullets. Solo texto plano."
        )

    # Errores de Gemini que activan el fallback (cuota, servicio caído, timeout)
    _GEMINI_FALLBACK_ERRORS = (
        "429", "RESOURCE_EXHAUSTED", "quota",
        "503", "UNAVAILABLE", "timeout", "Deadline",
    )

    def ask_gemini(self, prompt: str):
        """
        Consulta a la IA con lógica de fallback en dos niveles:
          1. Intenta Gemini (modelo principal, alta calidad).
          2. Si Gemini falla por cuota/disponibilidad, escala a OpenRouter
             (modelo gratuito seleccionado aleatoriamente de la lista).
          3. Si OpenRouter también falla, informa al usuario y mantiene
             las capacidades de comandos locales activas.
        """
        self.set_status("⚡ PROCESANDO IA…", "#aa00ff")
        self.conversation_history.append({"role": "user", "parts": [{"text": prompt}]})
        max_msgs = GEMINI_HISTORY_TURNS * 2
        if len(self.conversation_history) > max_msgs:
            self.conversation_history = self.conversation_history[-max_msgs:]

        system_instruction = self._build_system_instruction()
        answer: str | None = None

        # ── Intento 1: Gemini ─────────────────────────────────────────────────
        try:
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=GEMINI_TEMPERATURE,
                max_output_tokens=GEMINI_MAX_TOKENS,
            )
            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=self.conversation_history,
                config=config,
            )
            # Extraer texto con fallback progresivo para evitar respuestas truncadas
            answer = None
            if hasattr(response, "text") and response.text and response.text.strip():
                answer = response.text.strip()
            elif hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                finish_reason = getattr(candidate, "finish_reason", None)
                if finish_reason and str(finish_reason) not in ("STOP", "1", "FinishReason.STOP"):
                    log.warning(f"[Gemini] finish_reason inesperado: {finish_reason}")
                try:
                    answer = candidate.content.parts[0].text.strip()
                except (AttributeError, IndexError) as parse_err:
                    log.warning(f"[Gemini] No se pudo extraer texto del candidato: {parse_err}")
            if not answer:
                raise ValueError("Gemini devolvió respuesta vacía o sin texto legible")
            log.info("[Gemini] Respuesta obtenida correctamente.")

        except Exception as gemini_err:
            err_str = str(gemini_err)
            log.warning(f"[Gemini] Error: {err_str}")

            # Decidir si este error amerita un fallback o es un error de config
            is_fallback_worthy = any(k in err_str for k in self._GEMINI_FALLBACK_ERRORS)
            is_auth_error      = any(k in err_str for k in ["API_KEY", "authentication", "UNAUTHENTICATED"])
            is_network_error   = any(k in err_str.lower() for k in ["network", "connection", "unreachable"])

            if is_auth_error:
                self.talk("Error de autenticación con Gemini. Verifica tu API key.")
                self.set_status("LISTO", "gray")
                return

            if is_network_error:
                self.talk("Sin conexión a internet. Los comandos locales siguen activos.")
                self.set_status("LISTO", "gray")
                return

            if is_fallback_worthy or True:   # intenta OpenRouter en cualquier error no crítico
                # ── Intento 2: OpenRouter (fallback) ─────────────────────────
                log.info("[Fallback] Activando sistema de respaldo OpenRouter…")
                self.set_status("⚡ MODO FALLBACK (OpenRouter)…", "#ff8800")
                try:
                    answer = _ask_openrouter(prompt, system_instruction)
                    log.info("[Fallback] Respuesta de OpenRouter obtenida.")
                except Exception as or_err:
                    log.error(f"[Fallback] OpenRouter también falló: {or_err}")
                    # Informar de forma diferenciada según el error original de Gemini
                    if is_fallback_worthy and "quota" in err_str.lower():
                        self.talk(
                            "Límite de Gemini alcanzado y el sistema de respaldo tampoco respondió. "
                            "Comandos locales activos."
                        )
                    else:
                        self.talk(
                            "Los motores de IA no están disponibles en este momento. "
                            "Comandos locales activos."
                        )
                    self.set_status("LISTO", "gray")
                    return

        # ── Procesar y hablar la respuesta ────────────────────────────────────
        if answer:
            answer = re.sub(r"[*_`#>]", "", answer).strip()
            self.conversation_history.append({"role": "model", "parts": [{"text": answer}]})
            self.talk(answer)
        else:
            self.talk("No obtuve respuesta del motor de IA.")

        self.set_status("LISTO", "gray")

    # =========================================================================
    #  CIERRE LIMPIO
    # =========================================================================

    def kill_process(self):
        log.info("Iniciando cierre limpio…")
        self.running = False
        deadline = time.time() + 5
        while (not self.tts_queue.empty() or self.is_speaking.is_set()) and time.time() < deadline:
            time.sleep(0.1)
        self.tts_queue.put(None)
        time.sleep(0.2)
        try: self.destroy()
        except Exception: pass
        try: win32api.CloseHandle(_mutex_handle)
        except Exception: pass
        log.info("Darius cerrado correctamente.")
        sys.exit(0)


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = DariusFinal()
    app.mainloop()
