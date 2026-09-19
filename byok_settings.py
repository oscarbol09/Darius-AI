"""
byok_settings.py — Modal de Configuración BYOK Multi-Proveedor para DARIUS AI
==============================================================================
Permite al usuario configurar sus propias API Keys y modelos para:
  - Google Gemini
  - OpenAI / ChatGPT
  - OpenRouter
  - NVIDIA NIM
  - Groq
  - Ollama (Local)
  - Endpoint Personalizado (Custom)

Integra pruebas de conexión en tiempo real y persistencia segura en config.json.
"""

import threading
import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from ai_client import PROVIDER_NAMES, resolve_provider_key, test_provider_connection
from config_loader import cfg

# Modelos populares sugeridos por proveedor
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


class BYOKSettingsModal(ctk.CTkToplevel):
    """
    Ventana modal de configuración BYOK con sistema de diseño Slate/Zinc.
    """

    def __init__(self, master, on_save_callback: Callable[[], None] | None = None):
        super().__init__(master)
        self.title("DARIUS AI — Configuración de Proveedores (BYOK)")
        self.geometry("580x740")
        self.minsize(520, 680)
        self.configure(fg_color="#090D16")
        self.attributes("-topmost", True)
        self.grab_set()

        self.on_save_callback = on_save_callback
        self.selected_provider = cfg.active_provider or "gemini"
        self._show_key_var = tk.BooleanVar(value=False)
        self._is_testing = False

        # Almacén temporal de valores editados por proveedor
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

        self._build_ui()
        self._load_provider_fields(self.selected_provider)

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────────────────
        header_frame = ctk.CTkFrame(self, fg_color="#111827", corner_radius=12,
                                    border_width=1, border_color="#1E293B")
        header_frame.pack(padx=16, pady=(16, 8), fill="x")

        ctk.CTkLabel(
            header_frame, text="⚙ CONFIGURACIÓN DE IA (BYOK)",
            font=("Segoe UI", 18, "bold"), text_color="#38BDF8"
        ).pack(anchor="w", padx=16, pady=(12, 2))

        ctk.CTkLabel(
            header_frame,
            text="Configura tus propias claves de API, modelos o servidores locales de IA.",
            font=("Segoe UI", 10), text_color="#94A3B8"
        ).pack(anchor="w", padx=16, pady=(0, 12))

        # ── Selector de Proveedor ───────────────────────────────────────────
        selector_card = ctk.CTkFrame(self, fg_color="#111827", corner_radius=12,
                                     border_width=1, border_color="#1E293B")
        selector_card.pack(padx=16, pady=6, fill="x")

        ctk.CTkLabel(
            selector_card, text="PROVEEDOR DE INTELIGENCIA ARTIFICIAL",
            font=("Segoe UI", 9, "bold"), text_color="#64748B"
        ).pack(anchor="w", padx=16, pady=(10, 4))

        provider_options = [
            f"{'⭐ ' if k == cfg.active_provider else ''}{v}"
            for k, v in PROVIDER_NAMES.items()
        ]
        self._provider_keys_list = list(PROVIDER_NAMES.keys())

        # Encontrar index del proveedor activo
        current_idx = 0
        if self.selected_provider in self._provider_keys_list:
            current_idx = self._provider_keys_list.index(self.selected_provider)

        self.provider_dropdown = ctk.CTkOptionMenu(
            selector_card,
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

        # ── Formulario de Configuración Dinámico ────────────────────────────
        self.form_card = ctk.CTkFrame(self, fg_color="#111827", corner_radius=12,
                                      border_width=1, border_color="#1E293B")
        self.form_card.pack(padx=16, pady=6, fill="both", expand=True)

        # 1. Campo API Key
        self.key_label = ctk.CTkLabel(
            self.form_card, text="CLAVE DE API (API KEY)",
            font=("Segoe UI", 9, "bold"), text_color="#64748B"
        )
        self.key_label.pack(anchor="w", padx=16, pady=(12, 2))

        key_row = ctk.CTkFrame(self.form_card, fg_color="transparent")
        key_row.pack(fill="x", padx=16, pady=(0, 8))

        self.key_entry = ctk.CTkEntry(
            key_row,
            placeholder_text="Introduce tu API Key…",
            show="●",
            font=("Consolas", 11),
            fg_color="#1F2937",
            border_color="#374151",
            text_color="#F8FAFC",
            height=36,
            corner_radius=8,
        )
        self.key_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.toggle_eye_btn = ctk.CTkButton(
            key_row,
            text="👁",
            width=38,
            height=36,
            fg_color="#1F2937",
            hover_color="#374151",
            text_color="#F8FAFC",
            font=("Segoe UI", 13),
            corner_radius=8,
            command=self._toggle_show_key,
        )
        self.toggle_eye_btn.pack(side="right")

        # 2. Campo Base URL (para Ollama y Custom)
        self.url_label = ctk.CTkLabel(
            self.form_card, text="URL BASE DEL SERVIDOR (ENDPOINT)",
            font=("Segoe UI", 9, "bold"), text_color="#64748B"
        )
        self.url_entry = ctk.CTkEntry(
            self.form_card,
            placeholder_text="http://localhost:11434/v1",
            font=("Consolas", 11),
            fg_color="#1F2937",
            border_color="#374151",
            text_color="#F8FAFC",
            height=36,
            corner_radius=8,
        )

        # 3. Campo Modelo
        self.model_label = ctk.CTkLabel(
            self.form_card, text="MODELO DE LENGUAJE",
            font=("Segoe UI", 9, "bold"), text_color="#64748B"
        )
        self.model_label.pack(anchor="w", padx=16, pady=(6, 2))

        self.model_combo = ctk.CTkComboBox(
            self.form_card,
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
        self.model_combo.pack(fill="x", padx=16, pady=(0, 8))

        # 4. Nota / Ayuda contextual
        self.hint_label = ctk.CTkLabel(
            self.form_card,
            text="💡 Obtén tu clave en Google AI Studio (aistudio.google.com)",
            font=("Segoe UI", 9),
            text_color="#94A3B8",
            wraplength=480,
            justify="left",
        )
        self.hint_label.pack(anchor="w", padx=16, pady=(4, 8))

        # 5. Estado de prueba de conexión
        self.status_box = ctk.CTkFrame(self.form_card, fg_color="#1F2937", corner_radius=8)
        self.status_box.pack(fill="x", padx=16, pady=(6, 12))

        self.status_icon = ctk.CTkLabel(
            self.status_box, text="⚪", font=("Segoe UI", 12), text_color="#64748B"
        )
        self.status_icon.pack(side="left", padx=(10, 4), pady=6)

        self.status_msg = ctk.CTkLabel(
            self.status_box,
            text="Haz clic en 'Probar Conexión' para verificar las credenciales.",
            font=("Segoe UI", 10),
            text_color="#94A3B8",
            wraplength=420,
            justify="left",
        )
        self.status_msg.pack(side="left", padx=(0, 10), pady=6)

        # 6. Botón de Probar Conexión y Switch de Proveedor Activo
        action_row = ctk.CTkFrame(self.form_card, fg_color="transparent")
        action_row.pack(fill="x", padx=16, pady=(0, 12))

        self.test_btn = ctk.CTkButton(
            action_row,
            text="🧪 PROBAR CONEXIÓN",
            fg_color="#1F2937",
            hover_color="#374151",
            border_color="#38BDF8",
            border_width=1,
            text_color="#38BDF8",
            font=("Segoe UI", 10, "bold"),
            height=34,
            corner_radius=8,
            command=self._on_test_connection,
        )
        self.test_btn.pack(side="left", padx=(0, 8))

        self.set_active_switch = ctk.CTkSwitch(
            action_row,
            text="Establecer como Activo",
            font=("Segoe UI", 10, "bold"),
            text_color="#F8FAFC",
            progress_color="#38BDF8",
        )
        self.set_active_switch.pack(side="right")
        if self.selected_provider == cfg.active_provider:
            self.set_active_switch.select()

        # ── Botones de Guardado y Cierre ───────────────────────────────────
        bottom_row = ctk.CTkFrame(self, fg_color="transparent")
        bottom_row.pack(padx=16, pady=(4, 16), fill="x")

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
            command=self.destroy,
        ).pack(side="right", padx=(6, 0))

    def _toggle_show_key(self):
        show = not self._show_key_var.get()
        self._show_key_var.set(show)
        self.key_entry.configure(show="" if show else "●")
        self.toggle_eye_btn.configure(text="🔒" if show else "👁")

    def _save_current_field_values(self):
        p = self.selected_provider
        self._provider_data[p]["key"] = self.key_entry.get().strip()
        self._provider_data[p]["model"] = self.model_combo.get().strip()
        if p in ("ollama", "custom"):
            self._provider_data[p]["base_url"] = self.url_entry.get().strip()

    def _load_provider_fields(self, provider: str):
        data = self._provider_data.get(provider, {})

        # API Key
        self.key_entry.delete(0, "end")
        self.key_entry.insert(0, data.get("key", ""))

        # Modelos sugeridos
        models = PROVIDER_DEFAULT_MODELS.get(provider, ["default"])
        self.model_combo.configure(values=models)
        self.model_combo.set(data.get("model", models[0]))

        # URL base condicional
        if provider in ("ollama", "custom"):
            self.url_label.pack(anchor="w", padx=16, pady=(6, 2), before=self.model_label)
            self.url_entry.pack(fill="x", padx=16, pady=(0, 8), before=self.model_label)
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, data.get("base_url", "http://localhost:11434/v1"))
        else:
            self.url_label.pack_forget()
            self.url_entry.pack_forget()

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
        self.hint_label.configure(text=hints.get(provider, ""))

        # Reset status box
        self.status_icon.configure(text="⚪", text_color="#64748B")
        self.status_msg.configure(
            text=f"Listo para probar credenciales con {PROVIDER_NAMES.get(provider, provider)}.",
            text_color="#94A3B8"
        )

        # Switch activo
        if provider == cfg.active_provider:
            self.set_active_switch.select()
        else:
            self.set_active_switch.deselect()

    def _on_provider_changed(self, choice_text: str):
        self._save_current_field_values()
        cleaned_name = choice_text.replace("⭐ ", "").strip()
        # Encontrar key correspondiente
        for k, v in PROVIDER_NAMES.items():
            if v == cleaned_name:
                self.selected_provider = k
                break
        self._load_provider_fields(self.selected_provider)

    def _on_test_connection(self):
        if self._is_testing:
            return
        self._is_testing = True
        self._save_current_field_values()

        provider = self.selected_provider
        data = self._provider_data[provider]
        api_key = data.get("key", "")
        model = data.get("model", "")
        base_url = data.get("base_url", "")

        self.test_btn.configure(state="disabled", text="⏳ PROBANDO…")
        self.status_icon.configure(text="🟡", text_color="#FBBF24")
        self.status_msg.configure(text="Enviando solicitud de prueba…", text_color="#FBBF24")

        def run_test():
            success, msg, latency = test_provider_connection(
                provider=provider,
                api_key=api_key,
                model=model,
                base_url=base_url,
            )

            def update_ui():
                self._is_testing = False
                self.test_btn.configure(state="normal", text="🧪 PROBAR CONEXIÓN")
                if success:
                    self.status_icon.configure(text="🟢", text_color="#34D399")
                    self.status_msg.configure(
                        text=f"¡Conexión Exitosa! Respuesta recibida en {latency:.0f} ms.",
                        text_color="#34D399"
                    )
                else:
                    self.status_icon.configure(text="🔴", text_color="#F87171")
                    self.status_msg.configure(
                        text=f"Fallo de conexión: {msg}",
                        text_color="#F87171"
                    )

            self.after(0, update_ui)

        threading.Thread(target=run_test, daemon=True, name="byok-test").start()

    def _on_save(self):
        self._save_current_field_values()

        # Persistir valores en config.json
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

        self.save_btn.configure(text="✔ GUARDADO CON ÉXITO", fg_color="#34D399")
        self.after(1200, lambda: self.save_btn.configure(text="💾 GUARDAR Y APLICAR", fg_color="#38BDF8"))

        if self.on_save_callback:
            self.on_save_callback()
