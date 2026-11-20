"""
i18n.py — Lightweight Internationalization and Localization Engine for DARIUS AI
================================================================================
Provides seamless dual-language support (English and Spanish) across:
  - System statuses & GUI component labels
  - Voice alocutions & speech synthesis texts
  - AI butler persona prompts & honorifics
  - Local command recognition phrases
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any, Final

log = logging.getLogger("DARIUS.I18n")

SUPPORTED_LANGUAGES: Final[tuple[str, ...]] = ("en", "es")
DEFAULT_LANGUAGE: Final[str] = "en"

# =============================================================================
#  TRANSLATION CATALOGS (English & Spanish)
# =============================================================================

TRANSLATIONS: Final[dict[str, dict[str, str]]] = {
    "en": {
        # System status
        "status.ready": "SYSTEM READY",
        "status.processing_ai": "⚡ PROCESSING AI…",
        "status.listening": "🎙️ LISTENING…",
        "status.thinking": "🧠 THINKING…",
        "status.muted": "MUTED",
        "status.stopped": "STOPPED",
        "status.waiting_confirm": "⚠️ AWAITING CONFIRMATION",
        "status.analyzing_screen": "👁️ ANALYZING SCREEN…",
        "status.researching": "🔬 RESEARCHING DEEPLY…",
        "status.offline": "OFFLINE",
        "status.nominal": "NOMINAL",
        "status.active": "ACTIVE",
        # GUI Rail & Navigation Tabs
        "gui.window_title": "DARIUS AI v8.5 — Cybernetic Bento Command Station",
        "gui.tab.dashboard": "Dashboard",
        "gui.tab.chat": "Chat",
        "gui.tab.workspaces": "Workspaces",
        "gui.tab.obsidian": "Obsidian",
        "gui.tab.system": "Logs & System",
        "gui.tab.settings": "Settings",
        "gui.composer_placeholder": "Type a command, ask anything, or press Right Ctrl to speak…",
        "gui.send_button": "SEND",
        "gui.mute_button": "Mute",
        "gui.unmute_button": "Unmute",
        # Floating voice capsule
        "capsule.ptt": "PTT",
        "capsule.name": "NAME",
        "capsule.auto": "AUTO",
        "capsule.live": "GEMINI LIVE",
        "capsule.tooltip_mic": "Toggle mic / Barge-in (Esc to stop)",
        "capsule.tooltip_mode": "Select voice activation mode",
        "capsule.tooltip_send": "Send text command (Enter)",
        "capsule.placeholder": 'Say: "Hello Darius..." or type a command',
        # Cyber Top Bar
        "topbar.caption": "YOUR WINDOWS COPILOT",
        "topbar.user_online": "Darius ● Online",
        "topbar.system": "System",
        "topbar.network": "Net",
        "topbar.ai": "AI",
        "topbar.online": "Connected",
        "topbar.offline": "Disconnected",
        "topbar.autonomous": "Autonomous",
        # Cyber Sidebar
        "sidebar.inicio": "Home",
        "sidebar.asistente": "Assistant",
        "sidebar.automatizacion": "Automation",
        "sidebar.memoria": "Memory (Obsidian)",
        "sidebar.configuracion": "Settings",
        "sidebar.logs": "Logs",
        "sidebar.quote": '"Technology is at its most powerful when it affords you time to think."\n— Darius —',
        # Bento Dashboard
        "bento.nominal_standby": "SYSTEM NOMINAL • STANDBY",
        "bento.darius_protocol": "🚀 Darius Protocol",
        "bento.dev_mode": "💻 Dev Mode",
        "bento.trading_mode": "📈 Trading Mode",
        "bento.focus_cursor": "🎯 Focus Cursor",
        "bento.wol": "🌐 Wake-on-LAN",
        "bento.tactical_silence": "🛑 Tactical Silence",
        "bento.situational_briefing": "SITUATIONAL VOICE BRIEFING 🎙",
        # Settings Modal
        "settings.title": "⚙ SETTINGS & CONFIGURATION — DARIUS AI",
        "settings.subtitle": "Customize your language models (BYOK), voice synthesis engines, and interface language.",
        "settings.language_label": "🌐 Interface & Voice Language:",
        "settings.save_btn": "💾 SAVE & APPLY",
        "settings.saved_btn": "✔ SAVED SUCCESSFULLY",
        "settings.close_btn": "CLOSE",
        # Spoken alocutions
        "speech.welcome": "Welcome back, {user}. All Darius AI systems are online and fully operational.",
        "speech.time": "It is {time} on the local system.",
        "speech.date": "Today is {date}.",
        "speech.stopped": "Operation stopped and speech queue silenced.",
        "speech.confirm_shutdown": "Warning: PC shutdown requested. Say 'confirm' or press Enter within 15 seconds.",
        "speech.confirm_restart": "Warning: PC restart requested. Say 'confirm' or press Enter within 15 seconds.",
        "speech.action_cancelled": "Action cancelled, sir.",
        "speech.dns_flushed": "Windows DNS resolution cache cleared successfully.",
        "speech.scrape_analyzing": "Analyzing content from {url}, one moment.",
        "speech.scrape_error": "Failed to analyze webpage: {error}",
        "speech.click_scheduled": "Clicking in two seconds.",
        "speech.click_done": "Click executed.",
        "speech.type_scheduled": "Typing text in two seconds.",
        "speech.type_done": "Text typed successfully.",
        "speech.screen_analyzing": "Analyzing what is shown on your screen, one moment.",
        "speech.deep_research_start": "Initiating deep investigation on '{topic}'.",
        "speech.ai_no_response": "I did not receive a response from the AI engine, sir.",
        "speech.ai_error": "An error occurred while querying the AI. Local commands remain active.",
        "speech.darius_protocol_start": "Initiating Darius Protocol. Configuring workspace and tools.",
        "speech.workspace_dev": "Development workspace activated.",
        "speech.workspace_trading": "Trading workspace activated.",
        "speech.cursor_focused": "Cursor IDE focused in fullscreen.",
        "speech.monitors_detected": "{count} monitors detected: {details}.",
        "speech.sentinel_active": "Human presence webcam sentinel activated in background, sir.",
        "speech.sentinel_inactive": "Human presence webcam sentinel deactivated, sir.",
        "speech.dossier_generated": "Intelligence dossier synthesized for {target}.",
        # Common phrases
        "common.error": "Error: {error}",
        "common.success": "Success",
        "common.warning": "Warning",
    },
    "es": {
        # System status
        "status.ready": "SISTEMA LISTO",
        "status.processing_ai": "⚡ PROCESANDO IA…",
        "status.listening": "🎙️ ESCUCHANDO…",
        "status.thinking": "🧠 PENSANDO…",
        "status.muted": "SILENCIADO",
        "status.stopped": "DETENIDO",
        "status.waiting_confirm": "⚠️ ESPERANDO CONFIRMACIÓN",
        "status.analyzing_screen": "👁️ ANALIZANDO PANTALLA…",
        "status.researching": "🔬 INVESTIGANDO A FONDO…",
        "status.offline": "DESCONECTADO",
        "status.nominal": "NOMINAL",
        "status.active": "ACTIVO",
        # GUI Rail & Navigation Tabs
        "gui.window_title": "DARIUS AI v8.5 — Estación de Mando Cybernetic Bento",
        "gui.tab.dashboard": "Panel",
        "gui.tab.chat": "Chat",
        "gui.tab.workspaces": "Espacios",
        "gui.tab.obsidian": "Obsidian",
        "gui.tab.system": "Logs y Sistema",
        "gui.tab.settings": "Configuración",
        "gui.composer_placeholder": "Escribe un comando, haz una pregunta o presiona Right Ctrl para hablar…",
        "gui.send_button": "ENVIAR",
        "gui.mute_button": "Silenciar",
        "gui.unmute_button": "Activar sonido",
        # Floating voice capsule
        "capsule.ptt": "PTT",
        "capsule.name": "NOM",
        "capsule.auto": "AUTO",
        "capsule.live": "GEMINI LIVE",
        "capsule.tooltip_mic": "Activar micrófono / Barge-in (Esc para detener)",
        "capsule.tooltip_mode": "Seleccionar modo de activación por voz",
        "capsule.tooltip_send": "Enviar comando de texto (Enter)",
        "capsule.placeholder": 'Di: "Hola Darius..." o escribe un comando',
        # Cyber Top Bar
        "topbar.caption": "TU COPILOTO EN WINDOWS",
        "topbar.user_online": "Darius ● En línea",
        "topbar.system": "Sistema",
        "topbar.network": "Red",
        "topbar.ai": "IA",
        "topbar.online": "Conectado",
        "topbar.offline": "Desconectado",
        "topbar.autonomous": "Autónomo",
        # Cyber Sidebar
        "sidebar.inicio": "Inicio",
        "sidebar.asistente": "Asistente",
        "sidebar.automatizacion": "Automatización",
        "sidebar.memoria": "Memoria (Obsidian)",
        "sidebar.configuracion": "Configuración",
        "sidebar.logs": "Logs",
        "sidebar.quote": '"La tecnología es más poderosa cuando te da tiempo para pensar."\n— Darius —',
        # Bento Dashboard
        "bento.nominal_standby": "SISTEMA NOMINAL • EN ESPERA",
        "bento.darius_protocol": "🚀 Protocolo Darius",
        "bento.dev_mode": "💻 Modo Desarrollo",
        "bento.trading_mode": "📈 Modo Trading",
        "bento.focus_cursor": "🎯 Enfocar Cursor",
        "bento.wol": "🌐 Wake-on-LAN",
        "bento.tactical_silence": "🛑 Silencio Táctico",
        "bento.situational_briefing": "INFORME VOCAL SITUACIONAL 🎙",
        # Settings Modal
        "settings.title": "⚙ AJUSTES Y CONFIGURACIÓN — DARIUS AI",
        "settings.subtitle": "Personaliza tus modelos de lenguaje (BYOK), motores de síntesis de voz e idioma.",
        "settings.language_label": "🌐 Idioma de Interfaz y Voz:",
        "settings.save_btn": "💾 GUARDAR Y APLICAR",
        "settings.saved_btn": "✔ GUARDADO CON ÉXITO",
        "settings.close_btn": "CERRAR",
        # Spoken alocutions
        "speech.welcome": "Bienvenido de vuelta, {user}. Todos los sistemas de Darius AI han sido inicializados.",
        "speech.time": "Son las {time} en el sistema local.",
        "speech.date": "Hoy es {date}.",
        "speech.stopped": "Operación detenida y cola de voz silenciada.",
        "speech.confirm_shutdown": (
            "Advertencia: Se solicitó apagar el equipo. Di 'confirmar' o presiona Enter en 15 segundos."
        ),
        "speech.confirm_restart": (
            "Advertencia: Se solicitó reiniciar el equipo. Di 'confirmar' o presiona Enter en 15 segundos."
        ),
        "speech.action_cancelled": "Acción cancelada, señor.",
        "speech.dns_flushed": "Caché de resolución DNS de Windows limpiada con éxito.",
        "speech.scrape_analyzing": "Analizando el contenido de {url}, un momento.",
        "speech.scrape_error": "Error al analizar la página: {error}",
        "speech.click_scheduled": "Haciendo clic en dos segundos.",
        "speech.click_done": "Clic ejecutado.",
        "speech.type_scheduled": "Escribiendo texto en dos segundos.",
        "speech.type_done": "Texto escrito correctamente.",
        "speech.screen_analyzing": "Analizando lo que se muestra en tu pantalla, un momento.",
        "speech.deep_research_start": "Iniciando investigación a fondo sobre '{topic}'.",
        "speech.ai_no_response": "No obtuve respuesta del motor de IA, señor.",
        "speech.ai_error": "Ocurrió un error al consultar la IA. Comandos locales activos.",
        "speech.darius_protocol_start": "Iniciando Protocolo Darius. Configurando entorno de trabajo y herramientas.",
        "speech.workspace_dev": "Modo de desarrollo activado.",
        "speech.workspace_trading": "Modo trading activado.",
        "speech.cursor_focused": "Cursor enfocado en pantalla completa.",
        "speech.monitors_detected": "{count} monitores detectados: {details}.",
        "speech.sentinel_active": "Centinela de presencia humana activado en segundo plano, señor.",
        "speech.sentinel_inactive": "Centinela de presencia humana desactivado, señor.",
        "speech.dossier_generated": "Dossier de inteligencia sintetizado para {target}.",
        # Common phrases
        "common.error": "Error: {error}",
        "common.success": "Éxito",
        "common.warning": "Advertencia",
    },
}


class I18nEngine:
    """
    Singleton Internationalization (i18n) Engine.
    Manages current locale, key translations, and change observers.
    """

    def __init__(self, initial_lang: str = DEFAULT_LANGUAGE) -> None:
        self._lock = threading.RLock()
        self._lang = initial_lang if initial_lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
        self._listeners: list[Callable[[str], None]] = []

    @property
    def language(self) -> str:
        """Returns the current active ISO-639-1 language code ('en' or 'es')."""
        with self._lock:
            return self._lang

    def set_language(self, lang: str) -> bool:
        """
        Switches the active language and notifies all registered observers.
        Returns True if the language changed, False otherwise.
        """
        clean_lang = lang.strip().lower()
        target = "es" if clean_lang.startswith("es") else "en"

        with self._lock:
            if target == self._lang:
                return False
            self._lang = target
            listeners = list(self._listeners)

        log.info(f"[i18n] Active language switched to: '{target}'")
        for callback in listeners:
            try:
                callback(target)
            except Exception as exc:  # noqa: BLE001
                log.warning(f"[i18n] Error in language observer: {exc}")
        return True

    def get(self, key: str, default: str | None = None, **kwargs: Any) -> str:
        """
        Retrieves the localized string for `key`.
        Falls back to English if the key is missing in Spanish, or to `default` or `key`.
        Supports safe string formatting with kwargs.
        """
        with self._lock:
            lang = self._lang

        # 1. Lookup in current language
        msg = TRANSLATIONS.get(lang, {}).get(key)

        # 2. Fallback to English
        if msg is None and lang != "en":
            msg = TRANSLATIONS.get("en", {}).get(key)

        # 3. Fallback to default or raw key
        if msg is None:
            msg = default if default is not None else key

        # 4. Safe interpolation
        if kwargs:
            try:
                return msg.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                return msg
        return msg

    def register_listener(self, callback: Callable[[str], None]) -> None:
        """Registers a callback function to be called when the language changes."""
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def unregister_listener(self, callback: Callable[[str], None]) -> None:
        """Removes a registered callback."""
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)


# Global Engine Instance
_I18N_INSTANCE: I18nEngine | None = None
_I18N_LOCK = threading.Lock()


def get_i18n() -> I18nEngine:
    """Returns the global I18nEngine singleton."""
    global _I18N_INSTANCE
    if _I18N_INSTANCE is None:
        with _I18N_LOCK:
            if _I18N_INSTANCE is None:
                # Initialize from config if possible
                try:
                    from src.darius_ai.core.config_loader import cfg

                    configured_lang = cfg.get("assistant", "language", default="en")
                except Exception:
                    configured_lang = "en"
                _I18N_INSTANCE = I18nEngine(initial_lang=configured_lang)
    return _I18N_INSTANCE


def t(key: str, default: str | None = None, **kwargs: Any) -> str:
    """Convenience alias for translating strings: t('status.ready')"""
    return get_i18n().get(key, default=default, **kwargs)


# Translation shortcut
_ = t
