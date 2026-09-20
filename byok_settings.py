"""
byok_settings.py — Modal de Configuración BYOK y TTS para DARIUS AI
===================================================================
Permite al usuario configurar visualmente desde la interfaz gráfica:
  1. Proveedores de IA (BYOK):
     - Google Gemini
     - OpenAI / ChatGPT
     - OpenRouter
     - NVIDIA NIM
     - Groq
     - Ollama (Local)
     - Endpoint Personalizado (Custom)
  2. Motor de Voz y Síntesis Neural (TTS):
     - SAPI5 (Nativo Windows • 100% Offline y Gratis)
     - Edge-TTS (Neural Microsoft • Gratis con Internet)
     - ElevenLabs (Neural Ultra-Realista • Clave de API)

Integra pruebas de conexión y de voz en tiempo real con persistencia en config.json.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from ai_client import PROVIDER_NAMES, resolve_provider_key, test_provider_connection
from config_loader import cfg

log = logging.getLogger("DARIUS.Settings")

# Modelos populares sugeridos por proveedor de IA
PROVIDER_DEFAULT_MODELS: dict[str, list[str]] = {
    "gemini": [
        "gemini-3.6-flash",
        "gemini-3.8-flash",
        "gemini-3.1-flash-lite",
        "gemini-flash-latest",
        "gemini-flash-lite-latest",
        "gemini-3.5-flash",
        "gemini-3.7-flash",
    ],
    "openai": ["gpt-4o-mini", "gpt-4o", "o3-mini", "gpt-4.1", "gpt-3.5-turbo"],
    "openrouter": [
        "google/gemma-3-27b-it:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "mistralai/mistral-small-3:free",
        "nvidia/nemotron-3-super:free",
        "meta-llama/llama-3-8b-instruct:free",
        "openai/gpt-4o-mini",
        "anthropic/claude-3.5-sonnet",
    ],
    "nvidia": [
        "meta/llama-3.1-70b-instruct",
        "nvidia/llama-3.1-nemotron-70b-instruct",
        "meta/llama-3.1-8b-instruct",
        "mistralai/mixtral-8x22b-instruct-v0.1",
    ],
    "groq": [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
        "gemma2-9b-it",
    ],
    "ollama": [
        "llama3.2",
        "llama3.1",
        "deepseek-r1:8b",
        "mistral",
        "qwen2.5:7b",
        "phi3",
    ],
    "custom": [
        "local-model",
        "default",
    ],
}

# Motores TTS disponibles
TTS_ENGINES = {
    "sapi": "SAPI5 (Nativo Windows • 100% Offline y Gratis)",
    "edge": "Edge-TTS (Neural Microsoft • Gratis con Internet)",
    "elevenlabs": "ElevenLabs (Neural Ultra-Realista • API Key)",
}

# Voces sugeridas para ElevenLabs
ELEVENLABS_VOICE_PRESETS = [
    "21m00Tcm4TlvDq8ikWAM (Rachel)",
    "AZnzlk1XvdvUeBnXmlld (Domi)",
    "EXAVITQu4vr4xnSDxMaL (Bella)",
    "ErXwobaYiN019PkySvjV (Antoni)",
    "TxGEqnHWrfWFTfGW9XjX (Josh)",
    "pNInz6obpgDQGcFmaJgB (Adam)",
]

ELEVENLABS_MODEL_PRESETS = [
    "eleven_multilingual_v2",
    "eleven_turbo_v2_5",
    "eleven_flash_v2_5",
    "eleven_monolingual_v1",
]


class BYOKSettingsModal(ctk.CTkToplevel):
    """
    Ventana modal de configuración para Proveedores de IA y Motores TTS.
    """

    def __init__(self, master, on_save_callback: Callable[[], None] | None = None):
        super().__init__(master)
        self.title("DARIUS AI — Configuración del Asistente")
        self.geometry("620x780")
        self.minsize(540, 720)
        self.configure(fg_color="#090D16")
        self.attributes("-topmost", True)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.on_save_callback = on_save_callback
        self.selected_provider = cfg.active_provider or "gemini"
        self.selected_tts_engine = cfg.tts_engine or "sapi"
        if self.selected_tts_engine not in TTS_ENGINES:
            self.selected_tts_engine = "sapi"

        self._show_llm_key_var = tk.BooleanVar(value=False)
        self._show_eleven_key_var = tk.BooleanVar(value=False)
        self._is_testing_llm = False
        self._is_testing_tts = False

        # Almacén temporal de valores LLM por proveedor
        self._provider_data: dict[str, dict[str, str]] = {
            "gemini": {
                "key": cfg.llm_gemini_api_key or resolve_provider_key("gemini"),
                "model": cfg.llm_gemini_model or "gemini-3.6-flash",
                "base_url": "",
            },
            "openai": {
                "key": cfg.llm_openai_api_key or resolve_provider_key("openai"),
                "model": cfg.llm_openai_model or "gpt-4o-mini",
                "base_url": "",
            },
            "openrouter": {
                "key": cfg.llm_openrouter_api_key or resolve_provider_key("openrouter"),
                "model": cfg.llm_openrouter_model or "google/gemma-3-27b-it:free",
                "base_url": "",
            },
            "nvidia": {
                "key": cfg.llm_nvidia_api_key or resolve_provider_key("nvidia"),
                "model": cfg.llm_nvidia_model or "meta/llama-3.1-70b-instruct",
                "base_url": "",
            },
            "groq": {
                "key": cfg.llm_groq_api_key or resolve_provider_key("groq"),
                "model": cfg.llm_groq_model or "llama-3.3-70b-versatile",
                "base_url": "",
            },
            "ollama": {
                "key": "",
                "model": cfg.llm_ollama_model or "llama3.2",
                "base_url": cfg.llm_ollama_base_url or "http://localhost:11434/v1",
            },
            "custom": {
                "key": cfg.llm_custom_api_key or resolve_provider_key("custom"),
                "model": cfg.llm_custom_model or "local-model",
                "base_url": cfg.llm_custom_base_url or "http://localhost:1234/v1",
            },
        }

        # Almacén temporal de valores ElevenLabs
        self._eleven_data = {
            "api_key": cfg.elevenlabs_api_key,
            "voice_id": cfg.elevenlabs_voice_id or "21m00Tcm4TlvDq8ikWAM",
            "model_id": cfg.elevenlabs_model_id or "eleven_multilingual_v2",
            "cache_enabled": cfg.elevenlabs_cache_enabled,
        }

        self._build_ui()
        self._load_provider_fields(self.selected_provider)
        self._load_tts_fields()

    def _build_ui(self):
        # ── 1. HEADER ────────────────────────────────────────────────────────
        header_frame = ctk.CTkFrame(self, fg_color="#111827", corner_radius=12,
                                    border_width=1, border_color="#1E293B")
        header_frame.pack(padx=16, pady=(16, 8), fill="x")

        ctk.CTkLabel(
            header_frame, text="⚙ AJUSTES Y CONFIGURACIÓN — DARIUS AI",
            font=("Segoe UI", 16, "bold"), text_color="#38BDF8"
        ).pack(anchor="w", padx=16, pady=(10, 2))

        ctk.CTkLabel(
            header_frame,
            text="Personaliza tus modelos de lenguaje (BYOK) y motores de síntesis de voz.",
            font=("Segoe UI", 10), text_color="#94A3B8"
        ).pack(anchor="w", padx=16, pady=(0, 10))

        # ── 2. SEGMENTED BUTTON (TABS) ───────────────────────────────────────
        tab_frame = ctk.CTkFrame(self, fg_color="transparent")
        tab_frame.pack(padx=16, pady=(0, 8), fill="x")

        self.tab_selector = ctk.CTkSegmentedButton(
            tab_frame,
            values=["🤖 MODELO DE IA (BYOK)", "🔊 VOZ Y SÍNTESIS (TTS)"],
            command=self._on_tab_changed,
            selected_color="#38BDF8",
            selected_hover_color="#0284C7",
            unselected_color="#1F2937",
            unselected_hover_color="#374151",
            text_color="#F8FAFC",
            font=("Segoe UI", 11, "bold"),
            height=34,
            corner_radius=8,
        )
        self.tab_selector.set("🤖 MODELO DE IA (BYOK)")
        self.tab_selector.pack(fill="x")

        # ── 3. CONTENEDOR TAB 1: MODELO IA (BYOK) ───────────────────────────
        self.llm_container = ctk.CTkFrame(self, fg_color="transparent")
        self.llm_container.pack(padx=16, pady=0, fill="both", expand=True)

        # Card Selector Proveedor
        llm_selector_card = ctk.CTkFrame(self.llm_container, fg_color="#111827", corner_radius=12,
                                         border_width=1, border_color="#1E293B")
        llm_selector_card.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            llm_selector_card, text="PROVEEDOR DE INTELIGENCIA ARTIFICIAL",
            font=("Segoe UI", 9, "bold"), text_color="#64748B"
        ).pack(anchor="w", padx=16, pady=(10, 4))

        provider_options = [
            f"{'⭐ ' if k == cfg.active_provider else ''}{v}"
            for k, v in PROVIDER_NAMES.items()
        ]
        self._provider_keys_list = list(PROVIDER_NAMES.keys())
        current_idx = 0
        if self.selected_provider in self._provider_keys_list:
            current_idx = self._provider_keys_list.index(self.selected_provider)

        self.provider_dropdown = ctk.CTkOptionMenu(
            llm_selector_card,
            values=provider_options,
            command=self._on_provider_changed,
            fg_color="#1F2937",
            button_color="#38BDF8",
            button_hover_color="#0284C7",
            text_color="#F8FAFC",
            dropdown_fg_color="#111827",
            dropdown_text_color="#F8FAFC",
            dropdown_hover_color="#1F2937",
            font=("Segoe UI", 11, "bold"),
            height=36,
            corner_radius=8,
        )
        self.provider_dropdown.set(provider_options[current_idx])
        self.provider_dropdown.pack(fill="x", padx=16, pady=(0, 12))

        # Formulario Dinámico LLM
        self.llm_form_card = ctk.CTkFrame(self.llm_container, fg_color="#111827", corner_radius=12,
                                          border_width=1, border_color="#1E293B")
        self.llm_form_card.pack(fill="both", expand=True)

        # 1. API Key LLM
        self.llm_key_label = ctk.CTkLabel(
            self.llm_form_card, text="CLAVE DE API (API KEY)",
            font=("Segoe UI", 9, "bold"), text_color="#64748B"
        )
        self.llm_key_label.pack(anchor="w", padx=16, pady=(10, 2))

        key_row = ctk.CTkFrame(self.llm_form_card, fg_color="transparent")
        key_row.pack(fill="x", padx=16, pady=(0, 6))

        self.llm_key_entry = ctk.CTkEntry(
            key_row,
            placeholder_text="Introduce tu clave de API…",
            show="●",
            font=("Consolas", 11),
            fg_color="#1F2937",
            border_color="#374151",
            text_color="#F8FAFC",
            height=36,
            corner_radius=8,
        )
        self.llm_key_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.toggle_llm_eye_btn = ctk.CTkButton(
            key_row,
            text="👁",
            width=38,
            height=36,
            fg_color="#1F2937",
            hover_color="#374151",
            text_color="#F8FAFC",
            font=("Segoe UI", 13),
            corner_radius=8,
            command=self._toggle_show_llm_key,
        )
        self.toggle_llm_eye_btn.pack(side="right")

        # 2. Base URL (Ollama y Custom)
        self.llm_url_label = ctk.CTkLabel(
            self.llm_form_card, text="URL BASE DEL SERVIDOR (ENDPOINT)",
            font=("Segoe UI", 9, "bold"), text_color="#64748B"
        )
        self.llm_url_entry = ctk.CTkEntry(
            self.llm_form_card,
            placeholder_text="http://localhost:11434/v1",
            font=("Consolas", 11),
            fg_color="#1F2937",
            border_color="#374151",
            text_color="#F8FAFC",
            height=36,
            corner_radius=8,
        )

        # 3. Modelo LLM
        self.llm_model_label = ctk.CTkLabel(
            self.llm_form_card, text="MODELO DE LENGUAJE",
            font=("Segoe UI", 9, "bold"), text_color="#64748B"
        )
        self.llm_model_label.pack(anchor="w", padx=16, pady=(4, 2))

        self.llm_model_combo = ctk.CTkComboBox(
            self.llm_form_card,
            values=["gemini-3.6-flash"],
            font=("Consolas", 11),
            fg_color="#1F2937",
            border_color="#374151",
            button_color="#38BDF8",
            button_hover_color="#0284C7",
            dropdown_fg_color="#111827",
            dropdown_text_color="#F8FAFC",
            text_color="#F8FAFC",
            height=36,
            corner_radius=8,
        )
        self.llm_model_combo.pack(fill="x", padx=16, pady=(0, 6))

        # 4. Hint
        self.llm_hint_label = ctk.CTkLabel(
            self.llm_form_card,
            text="💡 Obtén tu clave en Google AI Studio (aistudio.google.com)",
            font=("Segoe UI", 9),
            text_color="#94A3B8",
            wraplength=520,
            justify="left",
        )
        self.llm_hint_label.pack(anchor="w", padx=16, pady=(2, 6))

        # 5. Status Box LLM
        self.llm_status_box = ctk.CTkFrame(self.llm_form_card, fg_color="#1F2937", corner_radius=8)
        self.llm_status_box.pack(fill="x", padx=16, pady=(4, 8))

        self.llm_status_icon = ctk.CTkLabel(
            self.llm_status_box, text="⚪", font=("Segoe UI", 12), text_color="#64748B"
        )
        self.llm_status_icon.pack(side="left", padx=(10, 4), pady=6)

        self.llm_status_msg = ctk.CTkLabel(
            self.llm_status_box,
            text="Haz clic en 'Probar Conexión' para verificar las credenciales.",
            font=("Segoe UI", 10),
            text_color="#94A3B8",
            wraplength=460,
            justify="left",
        )
        self.llm_status_msg.pack(side="left", padx=(0, 10), pady=6)

        # 6. Botón Probar + Switch Activo
        llm_action_row = ctk.CTkFrame(self.llm_form_card, fg_color="transparent")
        llm_action_row.pack(fill="x", padx=16, pady=(0, 10))

        self.llm_test_btn = ctk.CTkButton(
            llm_action_row,
            text="🧪 PROBAR CONEXIÓN",
            fg_color="#1F2937",
            hover_color="#374151",
            border_color="#38BDF8",
            border_width=1,
            text_color="#38BDF8",
            font=("Segoe UI", 10, "bold"),
            height=34,
            corner_radius=8,
            command=self._on_test_llm_connection,
        )
        self.llm_test_btn.pack(side="left", padx=(0, 8))

        self.set_active_switch = ctk.CTkSwitch(
            llm_action_row,
            text="Establecer como Activo",
            font=("Segoe UI", 10, "bold"),
            text_color="#F8FAFC",
            progress_color="#38BDF8",
        )
        self.set_active_switch.pack(side="right")
        if self.selected_provider == cfg.active_provider:
            self.set_active_switch.select()

        # ── 4. CONTENEDOR TAB 2: VOZ Y SÍNTESIS (TTS) ────────────────────────
        self.tts_container = ctk.CTkFrame(self, fg_color="transparent")
        # Oculto por defecto hasta pulsar la pestaña

        # Card Selector Motor TTS
        tts_selector_card = ctk.CTkFrame(self.tts_container, fg_color="#111827", corner_radius=12,
                                         border_width=1, border_color="#1E293B")
        tts_selector_card.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            tts_selector_card, text="MOTOR DE SÍNTESIS DE VOZ",
            font=("Segoe UI", 9, "bold"), text_color="#64748B"
        ).pack(anchor="w", padx=16, pady=(10, 4))

        tts_options = list(TTS_ENGINES.values())
        self.tts_engine_dropdown = ctk.CTkOptionMenu(
            tts_selector_card,
            values=tts_options,
            command=self._on_tts_engine_changed,
            fg_color="#1F2937",
            button_color="#38BDF8",
            button_hover_color="#0284C7",
            text_color="#F8FAFC",
            dropdown_fg_color="#111827",
            dropdown_text_color="#F8FAFC",
            dropdown_hover_color="#1F2937",
            font=("Segoe UI", 11, "bold"),
            height=36,
            corner_radius=8,
        )
        # Seleccionar motor actual
        current_tts_name = TTS_ENGINES.get(self.selected_tts_engine, tts_options[0])
        self.tts_engine_dropdown.set(current_tts_name)
        self.tts_engine_dropdown.pack(fill="x", padx=16, pady=(0, 12))

        # Formulario Dinámico TTS
        self.tts_form_card = ctk.CTkFrame(self.tts_container, fg_color="#111827", corner_radius=12,
                                          border_width=1, border_color="#1E293B")
        self.tts_form_card.pack(fill="both", expand=True)

        # Campos ElevenLabs
        self.eleven_key_label = ctk.CTkLabel(
            self.tts_form_card, text="CLAVE DE API ELEVENLABS",
            font=("Segoe UI", 9, "bold"), text_color="#64748B"
        )
        self.eleven_key_label.pack(anchor="w", padx=16, pady=(10, 2))

        eleven_key_row = ctk.CTkFrame(self.tts_form_card, fg_color="transparent")
        eleven_key_row.pack(fill="x", padx=16, pady=(0, 6))

        self.eleven_key_entry = ctk.CTkEntry(
            eleven_key_row,
            placeholder_text="Introduce tu ElevenLabs API Key…",
            show="●",
            font=("Consolas", 11),
            fg_color="#1F2937",
            border_color="#374151",
            text_color="#F8FAFC",
            height=36,
            corner_radius=8,
        )
        self.eleven_key_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.toggle_eleven_eye_btn = ctk.CTkButton(
            eleven_key_row,
            text="👁",
            width=38,
            height=36,
            fg_color="#1F2937",
            hover_color="#374151",
            text_color="#F8FAFC",
            font=("Segoe UI", 13),
            corner_radius=8,
            command=self._toggle_show_eleven_key,
        )
        self.toggle_eleven_eye_btn.pack(side="right")

        # Voice ID
        self.eleven_voice_label = ctk.CTkLabel(
            self.tts_form_card, text="ID DE VOZ (VOICE ID)",
            font=("Segoe UI", 9, "bold"), text_color="#64748B"
        )
        self.eleven_voice_label.pack(anchor="w", padx=16, pady=(4, 2))

        self.eleven_voice_combo = ctk.CTkComboBox(
            self.tts_form_card,
            values=ELEVENLABS_VOICE_PRESETS,
            font=("Consolas", 11),
            fg_color="#1F2937",
            border_color="#374151",
            button_color="#38BDF8",
            button_hover_color="#0284C7",
            dropdown_fg_color="#111827",
            dropdown_text_color="#F8FAFC",
            text_color="#F8FAFC",
            height=36,
            corner_radius=8,
        )
        self.eleven_voice_combo.pack(fill="x", padx=16, pady=(0, 6))

        # Modelo ElevenLabs
        self.eleven_model_label = ctk.CTkLabel(
            self.tts_form_card, text="MODELO DE VOZ ELEVENLABS",
            font=("Segoe UI", 9, "bold"), text_color="#64748B"
        )
        self.eleven_model_label.pack(anchor="w", padx=16, pady=(4, 2))

        self.eleven_model_combo = ctk.CTkComboBox(
            self.tts_form_card,
            values=ELEVENLABS_MODEL_PRESETS,
            font=("Consolas", 11),
            fg_color="#1F2937",
            border_color="#374151",
            button_color="#38BDF8",
            button_hover_color="#0284C7",
            dropdown_fg_color="#111827",
            dropdown_text_color="#F8FAFC",
            text_color="#F8FAFC",
            height=36,
            corner_radius=8,
        )
        self.eleven_model_combo.pack(fill="x", padx=16, pady=(0, 6))

        # Switch Caché
        self.eleven_cache_switch = ctk.CTkSwitch(
            self.tts_form_card,
            text="Caché de audio en disco (Zero-Latency / Zero-Cost)",
            font=("Segoe UI", 10, "bold"),
            text_color="#F8FAFC",
            progress_color="#38BDF8",
        )
        self.eleven_cache_switch.pack(anchor="w", padx=16, pady=(4, 8))
        if self._eleven_data.get("cache_enabled", True):
            self.eleven_cache_switch.select()

        # Hint TTS
        self.tts_hint_label = ctk.CTkLabel(
            self.tts_form_card,
            text="💡 Consigue tu clave de ElevenLabs en elevenlabs.io para síntesis ultra-realista.",
            font=("Segoe UI", 9),
            text_color="#94A3B8",
            wraplength=520,
            justify="left",
        )
        self.tts_hint_label.pack(anchor="w", padx=16, pady=(2, 6))

        # Status Box TTS
        self.tts_status_box = ctk.CTkFrame(self.tts_form_card, fg_color="#1F2937", corner_radius=8)
        self.tts_status_box.pack(fill="x", padx=16, pady=(4, 8))

        self.tts_status_icon = ctk.CTkLabel(
            self.tts_status_box, text="⚪", font=("Segoe UI", 12), text_color="#64748B"
        )
        self.tts_status_icon.pack(side="left", padx=(10, 4), pady=6)

        self.tts_status_msg = ctk.CTkLabel(
            self.tts_status_box,
            text="Listo para probar síntesis de voz.",
            font=("Segoe UI", 10),
            text_color="#94A3B8",
            wraplength=460,
            justify="left",
        )
        self.tts_status_msg.pack(side="left", padx=(0, 10), pady=6)

        # Botón Probar Voz
        tts_action_row = ctk.CTkFrame(self.tts_form_card, fg_color="transparent")
        tts_action_row.pack(fill="x", padx=16, pady=(0, 10))

        self.tts_test_btn = ctk.CTkButton(
            tts_action_row,
            text="🔊 PROBAR VOZ",
            fg_color="#1F2937",
            hover_color="#374151",
            border_color="#38BDF8",
            border_width=1,
            text_color="#38BDF8",
            font=("Segoe UI", 10, "bold"),
            height=34,
            corner_radius=8,
            command=self._on_test_tts_voice,
        )
        self.tts_test_btn.pack(side="left")

        # ── 5. BOTONES INFERIORES COMPARTIDOS ────────────────────────────────
        bottom_row = ctk.CTkFrame(self, fg_color="transparent")
        bottom_row.pack(padx=16, pady=(6, 16), fill="x")

        self.save_btn = ctk.CTkButton(
            bottom_row,
            text="💾 GUARDAR Y APLICAR",
            fg_color="#38BDF8",
            hover_color="#0284C7",
            text_color="#090D16",
            font=("Segoe UI", 11, "bold"),
            height=40,
            corner_radius=8,
            command=self._on_save,
        )
        self.save_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))

        ctk.CTkButton(
            bottom_row,
            text="CERRAR",
            fg_color="#1F2937",
            hover_color="#374151",
            text_color="#F8FAFC",
            font=("Segoe UI", 11),
            height=40,
            corner_radius=8,
            command=self._on_close,
        ).pack(side="right", padx=(6, 0))

    def _on_close(self):
        with contextlib.suppress(Exception):
            self.grab_release()
        self.destroy()

    # =========================================================================
    #  MANEJO DE PESTAÑAS (TABS)
    # =========================================================================

    def _on_tab_changed(self, tab_name: str):
        if "MODELO" in tab_name:
            self.tts_container.pack_forget()
            self.llm_container.pack(padx=16, pady=0, fill="both", expand=True)
        else:
            self.llm_container.pack_forget()
            self.tts_container.pack(padx=16, pady=0, fill="both", expand=True)

    # =========================================================================
    #  LÓGICA LLM (BYOK)
    # =========================================================================

    def _toggle_show_llm_key(self):
        show = not self._show_llm_key_var.get()
        self._show_llm_key_var.set(show)
        self.llm_key_entry.configure(show="" if show else "●")
        self.toggle_llm_eye_btn.configure(text="🔒" if show else "👁")

    def _save_current_llm_fields(self):
        p = self.selected_provider
        self._provider_data[p]["key"] = self.llm_key_entry.get().strip()
        self._provider_data[p]["model"] = self.llm_model_combo.get().strip()
        if p in ("ollama", "custom"):
            self._provider_data[p]["base_url"] = self.llm_url_entry.get().strip()

    def _load_provider_fields(self, provider: str):
        data = self._provider_data.get(provider, {})

        # API Key
        self.llm_key_entry.delete(0, "end")
        self.llm_key_entry.insert(0, data.get("key", ""))

        # Modelos sugeridos
        models = PROVIDER_DEFAULT_MODELS.get(provider, ["default"])
        self.llm_model_combo.configure(values=models)
        self.llm_model_combo.set(data.get("model", models[0]))

        # URL base condicional
        if provider in ("ollama", "custom"):
            self.llm_url_label.pack(anchor="w", padx=16, pady=(4, 2), before=self.llm_model_label)
            self.llm_url_entry.pack(fill="x", padx=16, pady=(0, 6), before=self.llm_model_label)
            self.llm_url_entry.delete(0, "end")
            self.llm_url_entry.insert(0, data.get("base_url", "http://localhost:11434/v1"))
        else:
            self.llm_url_label.pack_forget()
            self.llm_url_entry.pack_forget()

        # Hints contextuales
        hints = {
            "gemini": "💡 Obtén tu clave en Google AI Studio (aistudio.google.com)",
            "openai": "💡 Obtén tu clave en OpenAI Platform (platform.openai.com/api-keys)",
            "openrouter": "💡 OpenRouter ofrece acceso unificado a cientos de modelos (openrouter.ai)",
            "nvidia": "💡 NVIDIA NIM ofrece 1000 llamadas gratis (build.nvidia.com)",
            "groq": "💡 Inferencia ultra rápida en Groq Cloud (console.groq.com)",
            "ollama": "💡 Servidor local Ollama. No requiere API key; asegúrate de correr 'ollama serve'",
            "custom": "💡 Conecta cualquier servidor local (LM Studio, vLLM, LocalAI) compatible con OpenAI",
        }
        self.llm_hint_label.configure(text=hints.get(provider, ""))

        # Reset status box
        self.llm_status_icon.configure(text="⚪", text_color="#64748B")
        self.llm_status_msg.configure(
            text=f"Listo para probar credenciales con {PROVIDER_NAMES.get(provider, provider)}.",
            text_color="#94A3B8"
        )

        # Switch activo
        if provider == cfg.active_provider:
            self.set_active_switch.select()
        else:
            self.set_active_switch.deselect()

    def _on_provider_changed(self, choice_text: str):
        self._save_current_llm_fields()
        cleaned_name = choice_text.replace("⭐ ", "").strip()
        for k, v in PROVIDER_NAMES.items():
            if v == cleaned_name:
                self.selected_provider = k
                break
        self._load_provider_fields(self.selected_provider)

    def _on_test_llm_connection(self):
        if self._is_testing_llm:
            return
        self._is_testing_llm = True
        self._save_current_llm_fields()

        provider = self.selected_provider
        data = self._provider_data[provider]
        api_key = data.get("key", "")
        model = data.get("model", "")
        base_url = data.get("base_url", "")

        self.llm_test_btn.configure(state="disabled", text="⏳ PROBANDO…")
        self.llm_status_icon.configure(text="🟡", text_color="#FBBF24")
        self.llm_status_msg.configure(text="Enviando solicitud de prueba…", text_color="#FBBF24")

        def run_test():
            success, msg, latency = test_provider_connection(
                provider=provider,
                api_key=api_key,
                model=model,
                base_url=base_url,
            )

            def update_ui():
                self._is_testing_llm = False
                self.llm_test_btn.configure(state="normal", text="🧪 PROBAR CONEXIÓN")
                if success:
                    self.llm_status_icon.configure(text="🟢", text_color="#34D399")
                    self.llm_status_msg.configure(
                        text=f"¡Conexión Exitosa! Respuesta recibida en {latency:.0f} ms.",
                        text_color="#34D399"
                    )
                else:
                    self.llm_status_icon.configure(text="🔴", text_color="#F87171")
                    self.llm_status_msg.configure(
                        text=f"Fallo de conexión: {msg}",
                        text_color="#F87171"
                    )

            self.after(0, update_ui)

        threading.Thread(target=run_test, daemon=True, name="byok-test").start()

    # =========================================================================
    #  LÓGICA TTS (VOZ)
    # =========================================================================

    def _toggle_show_eleven_key(self):
        show = not self._show_eleven_key_var.get()
        self._show_eleven_key_var.set(show)
        self.eleven_key_entry.configure(show="" if show else "●")
        self.toggle_eleven_eye_btn.configure(text="🔒" if show else "👁")

    def _save_current_tts_fields(self):
        self._eleven_data["api_key"] = self.eleven_key_entry.get().strip()
        raw_voice = self.eleven_voice_combo.get().strip()
        # Si contiene paréntesis con nombre ej "21m... (Rachel)", extraer solo el ID
        voice_id = raw_voice.split()[0].strip() if " " in raw_voice else raw_voice
        self._eleven_data["voice_id"] = voice_id
        self._eleven_data["model_id"] = self.eleven_model_combo.get().strip()
        self._eleven_data["cache_enabled"] = bool(self.eleven_cache_switch.get())

    def _load_tts_fields(self):
        # API Key
        self.eleven_key_entry.delete(0, "end")
        self.eleven_key_entry.insert(0, self._eleven_data.get("api_key", ""))

        # Voice ID
        saved_voice = self._eleven_data.get("voice_id", "21m00Tcm4TlvDq8ikWAM")
        matched = False
        for preset in ELEVENLABS_VOICE_PRESETS:
            if preset.startswith(saved_voice):
                self.eleven_voice_combo.set(preset)
                matched = True
                break
        if not matched:
            self.eleven_voice_combo.set(saved_voice)

        # Model ID
        self.eleven_model_combo.set(self._eleven_data.get("model_id", "eleven_multilingual_v2"))

        # Actualizar visibilidad según motor
        self._update_tts_visibility()

    def _update_tts_visibility(self):
        engine = self.selected_tts_engine
        if engine == "elevenlabs":
            self.eleven_key_label.pack(anchor="w", padx=16, pady=(10, 2))
            self.eleven_key_entry.master.pack(fill="x", padx=16, pady=(0, 6))
            self.eleven_voice_label.pack(anchor="w", padx=16, pady=(4, 2))
            self.eleven_voice_combo.pack(fill="x", padx=16, pady=(0, 6))
            self.eleven_model_label.pack(anchor="w", padx=16, pady=(4, 2))
            self.eleven_model_combo.pack(fill="x", padx=16, pady=(0, 6))
            self.eleven_cache_switch.pack(anchor="w", padx=16, pady=(4, 8))
            self.tts_hint_label.configure(
                text="💡 Requiere clave de ElevenLabs (elevenlabs.io). Ofrece voces neurales hiper-realistas."
            )
        elif engine == "edge":
            self.eleven_key_label.pack_forget()
            self.eleven_key_entry.master.pack_forget()
            self.eleven_voice_label.pack_forget()
            self.eleven_voice_combo.pack_forget()
            self.eleven_model_label.pack_forget()
            self.eleven_model_combo.pack_forget()
            self.eleven_cache_switch.pack_forget()
            self.tts_hint_label.configure(
                text="💡 Motor Microsoft Edge-TTS: excelente calidad neural gratuita en español (requiere internet)."
            )
        else:  # sapi
            self.eleven_key_label.pack_forget()
            self.eleven_key_entry.master.pack_forget()
            self.eleven_voice_label.pack_forget()
            self.eleven_voice_combo.pack_forget()
            self.eleven_model_label.pack_forget()
            self.eleven_model_combo.pack_forget()
            self.eleven_cache_switch.pack_forget()
            self.tts_hint_label.configure(
                text="💡 Motor SAPI5 de Windows: 100% nativo, sin conexión a internet y sin latencia."
            )

    def _on_tts_engine_changed(self, choice_text: str):
        for k, v in TTS_ENGINES.items():
            if v == choice_text:
                self.selected_tts_engine = k
                break
        self._update_tts_visibility()

    def _on_test_tts_voice(self):
        if self._is_testing_tts:
            return
        self._is_testing_tts = True
        self._save_current_tts_fields()

        engine_key = self.selected_tts_engine
        api_key = self._eleven_data["api_key"]
        voice_id = self._eleven_data["voice_id"]
        model_id = self._eleven_data["model_id"]

        self.tts_test_btn.configure(state="disabled", text="⏳ PROBANDO VOZ…")
        self.tts_status_icon.configure(text="🟡", text_color="#FBBF24")
        self.tts_status_msg.configure(text="Sintetizando audio de prueba…", text_color="#FBBF24")

        def run_tts_test():
            import time
            t0 = time.perf_counter()
            test_phrase = "Hola Óscar, esta es una prueba de voz para Darius AI."
            success = False
            msg = ""

            try:
                if engine_key == "elevenlabs":
                    if not api_key:
                        raise ValueError("No has introducido tu clave de API de ElevenLabs.")
                    from elevenlabs_tts_engine import ElevenLabsTTS
                    engine = ElevenLabsTTS(
                        api_key=api_key,
                        voice_id=voice_id,
                        model_id=model_id,
                        cache_enabled=False,
                    )
                    success = engine.speak(test_phrase)
                    if not success:
                        msg = "Fallo en la llamada a ElevenLabs (revisa tu saldo y API Key)."
                elif engine_key == "edge":
                    from edge_tts_engine import EdgeTTS
                    engine = EdgeTTS()
                    success = engine.speak(test_phrase)
                    if not success:
                        msg = "Fallo en Edge-TTS (verifica tu conexión a internet)."
                else:  # sapi
                    import pythoncom
                    import win32com.client
                    pythoncom.CoInitialize()
                    try:
                        spk = win32com.client.Dispatch("SAPI.SpVoice")
                        spk.Speak(test_phrase)
                        success = True
                    finally:
                        pythoncom.CoUninitialize()
            except Exception as e:
                success = False
                msg = str(e)

            latency_ms = int((time.perf_counter() - t0) * 1000)

            def update_ui():
                self._is_testing_tts = False
                self.tts_test_btn.configure(state="normal", text="🔊 PROBAR VOZ")
                if success:
                    self.tts_status_icon.configure(text="🟢", text_color="#34D399")
                    self.tts_status_msg.configure(
                        text=f"¡Voz reproducida exitosamente! Latencia: {latency_ms} ms.",
                        text_color="#34D399"
                    )
                else:
                    self.tts_status_icon.configure(text="🔴", text_color="#F87171")
                    self.tts_status_msg.configure(
                        text=f"Error en prueba de voz: {msg}",
                        text_color="#F87171"
                    )

            self.after(0, update_ui)

        threading.Thread(target=run_tts_test, daemon=True, name="tts-test").start()

    # =========================================================================
    #  GUARDADO ATÓMICO
    # =========================================================================

    def _on_save(self):
        # Guardar buffers
        self._save_current_llm_fields()
        self._save_current_tts_fields()

        # 1. Persistir valores LLM
        for p, data in self._provider_data.items():
            if p == "gemini":
                cfg.set(data["key"], "llm", "gemini_api_key")
                cfg.set(data["model"], "llm", "gemini_model")
                cfg.set(data["model"], "gemini", "model")
            elif p == "openai":
                cfg.set(data["key"], "llm", "openai_api_key")
                cfg.set(data["model"], "llm", "openai_model")
            elif p == "openrouter":
                cfg.set(data["key"], "llm", "openrouter_api_key")
                cfg.set(data["model"], "llm", "openrouter_model")
            elif p == "nvidia":
                cfg.set(data["key"], "llm", "nvidia_api_key")
                cfg.set(data["model"], "llm", "nvidia_model")
            elif p == "groq":
                cfg.set(data["key"], "llm", "groq_api_key")
                cfg.set(data["model"], "llm", "groq_model")
            elif p == "ollama":
                cfg.set(data["model"], "llm", "ollama_model")
                cfg.set(data["base_url"], "llm", "ollama_base_url")
            elif p == "custom":
                cfg.set(data["key"], "llm", "custom_api_key")
                cfg.set(data["model"], "llm", "custom_model")
                cfg.set(data["base_url"], "llm", "custom_base_url")

        # Activar proveedor si el switch está encendido
        if self.set_active_switch.get():
            cfg.set(self.selected_provider, "llm", "active_provider")

        # 2. Persistir valores TTS
        cfg.set(self.selected_tts_engine, "tts", "engine")
        cfg.set(self._eleven_data["api_key"], "elevenlabs", "api_key")
        cfg.set(self._eleven_data["voice_id"], "elevenlabs", "voice_id")
        cfg.set(self._eleven_data["model_id"], "elevenlabs", "model_id")
        cfg.set(bool(self._eleven_data["cache_enabled"]), "elevenlabs", "cache_enabled")

        log.info("[Settings] Ajustes de LLM y TTS guardados en config.json.")

        self.save_btn.configure(text="✔ GUARDADO CON ÉXITO", fg_color="#34D399")
        self.after(1200, lambda: self.save_btn.configure(text="💾 GUARDAR Y APLICAR", fg_color="#38BDF8"))

        if self.on_save_callback:
            self.on_save_callback()
