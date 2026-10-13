"""
telemetry_bar.py — Barra de Telemetría HUD y Feed de Eventos Agénticos para DARIUS AI
====================================================================================
Componente de interfaz gráfica para la barra de estado y HUD táctico de Darius AI.
Muestra en tiempo real la actividad del enjambre de herramientas (IA, Visión, Dossiers,
Web, Obsidian, SO) con rotación automática de eventos y control de audio procedural.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from typing import Any

try:
    import customtkinter as ctk

    _CTK_AVAILABLE = True
except ImportError:
    ctk = None  # type: ignore
    _CTK_AVAILABLE = False

from src.darius_ai.audio.sound_effects import get_sfx_engine
from src.darius_ai.core.telemetry_tracker import AgentEvent, get_telemetry_tracker
from src.darius_ai.gui import gui_theme as theme

log = logging.getLogger("DARIUS.TelemetryBar")


class TelemetryFeedController:
    """
    Controlador lógico del feed de eventos de telemetría (desacoplado de la GUI).
    """

    def __init__(self, max_queue: int = 15):
        self._max_queue = max_queue
        self._events: list[AgentEvent] = []
        self._current_index = 0
        self._lock = threading.Lock()

    def push_event(self, event: AgentEvent) -> None:
        with self._lock:
            self._events.append(event)
            if len(self._events) > self._max_queue:
                self._events.pop(0)

    def rotate_next(self) -> AgentEvent | None:
        with self._lock:
            if not self._events:
                return None
            self._current_index = (self._current_index + 1) % len(self._events)
            return self._events[self._current_index]

    def get_current_display_text(self) -> str:
        with self._lock:
            if not self._events:
                return "⚡ Telemetría: Sistema listo en espera de comandos"
            idx = min(self._current_index, len(self._events) - 1)
            evt = self._events[idx]
            duration_str = f" ({evt.duration_ms:.0f}ms)" if evt.duration_ms > 0 else ""
            status_icon = "🟢" if evt.status == "success" else ("🔴" if evt.status == "error" else "⚡")
            return f"[{evt.time_str}] {status_icon} {evt.agent_name}: {evt.message}{duration_str}"

    def toggle_sfx(self) -> bool:
        """Alterna el estado de efectos de sonido procedurales."""
        sfx = get_sfx_engine()
        new_state = not sfx.is_enabled()
        sfx.set_enabled(new_state)
        return new_state


if _CTK_AVAILABLE and ctk is not None:

    class TelemetryBarWidget(ctk.CTkFrame):
        """
        Widget de CustomTkinter para renderizar la barra de telemetría táctica.
        """

        def __init__(self, master: Any, **kwargs):
            super().__init__(
                master,
                fg_color=theme.BG_CARD_INNER,
                border_width=1,
                border_color=theme.BORDER_SUBTLE,
                corner_radius=theme.RADIUS_SM,
                height=32,
                **kwargs,
            )
            self.controller = TelemetryFeedController()
            self._setup_ui()
            self._connect_tracker()
            self._schedule_ticker()

        def _setup_ui(self):
            self.grid_columnconfigure(0, weight=1)
            self.grid_columnconfigure(1, weight=0)

            # Etiqueta de texto de telemetría en vivo
            self.lbl_feed = ctk.CTkLabel(
                self,
                text=self.controller.get_current_display_text(),
                font=theme.FONT_MONO,
                text_color=theme.TEXT_SECONDARY,
                anchor="w",
            )
            self.lbl_feed.grid(row=0, column=0, padx=(10, 5), pady=2, sticky="ew")

            # Botón de alternancia de SFX procedural
            sfx = get_sfx_engine()
            sfx_icon = "🔊 SFX" if sfx.is_enabled() else "🔇 MUTE"
            self.btn_sfx = ctk.CTkButton(
                self,
                text=sfx_icon,
                width=64,
                height=22,
                font=theme.FONT_BADGE,
                fg_color=theme.BG_PILL,
                hover_color=theme.BG_CARD_HOVER,
                border_width=1,
                border_color=theme.BORDER_SUBTLE,
                command=self._on_toggle_sfx,
            )
            self.btn_sfx.grid(row=0, column=1, padx=(5, 8), pady=4, sticky="e")

        def _on_toggle_sfx(self):
            new_state = self.controller.toggle_sfx()
            self.btn_sfx.configure(text="🔊 SFX" if new_state else "🔇 MUTE")
            if new_state:
                get_sfx_engine().play_click_tone()

        def _connect_tracker(self):
            tracker = get_telemetry_tracker()

            def _on_event(evt: AgentEvent):
                self.controller.push_event(evt)
                # Actualizar etiqueta inmediatamente si la UI está viva
                with contextlib.suppress(Exception):
                    self.after(0, lambda: self.lbl_feed.configure(text=self.controller.get_current_display_text()))

            tracker.add_listener(_on_event)

        def _schedule_ticker(self):
            def _tick():
                self.controller.rotate_next()
                with contextlib.suppress(Exception):
                    self.lbl_feed.configure(text=self.controller.get_current_display_text())
                self.after(3500, _tick)

            self.after(3500, _tick)

else:
    # Fallback si CustomTkinter no está presente
    class TelemetryBarWidget:  # type: ignore
        def __init__(self, *args, **kwargs):
            self.controller = TelemetryFeedController()
