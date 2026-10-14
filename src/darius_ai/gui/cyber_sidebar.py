"""
cyber_sidebar.py — Cyber Sidebar Navigation Rail para DARIUS AI v8.5
====================================================================
Rail de navegación vertical estilo Cybernetic Bento Glassmorphism:
  1. Contenedor de vidrio oscuro (#070B14 / #0B1220) con borde hairline (#1E293B).
  2. 6 destinos de navegación táctica:
     - 🏠 Inicio
     - 🎙 Asistente
     - ⚡ Automatización
     - 📖 Memoria (Obsidian)
     - ⚙ Configuración
     - 📄 Logs
  3. Resaltado activo en forma de cápsula cian (#00F0FF / #38BDF8) con halo y borde.
  4. Tarjeta inferior con cita inspiracional de Darius.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Final

import customtkinter as ctk

from src.darius_ai.gui import gui_theme as theme

log = logging.getLogger("darius.cyber_sidebar")

# =============================================================================
#  TOKENS VISUALES & CONSTANTES DEL SIDEBAR
# =============================================================================
DEFAULT_SIDEBAR_WIDTH: Final[int] = 210
SIDEBAR_BG: Final[str] = "#070B14"
SIDEBAR_BORDER: Final[str] = "#1E293B"

NAV_ACTIVE_BG: Final[str] = "#0D223A"
NAV_ACTIVE_FG: Final[str] = "#00F0FF"
NAV_ACTIVE_BORDER: Final[str] = "#00F0FF"
NAV_INACTIVE_FG: Final[str] = "#94A3B8"
NAV_HOVER_BG: Final[str] = "#131C2D"

DEFAULT_INSPIRATIONAL_QUOTE: Final[str] = (
    '"La tecnología es más poderosa cuando te da tiempo para pensar."\n— Darius —'
)

NAV_ITEMS: Final[list[dict[str, str]]] = [
    {"id": "inicio", "label": "Inicio", "icon": "🏠"},
    {"id": "asistente", "label": "Asistente", "icon": "🎙"},
    {"id": "automatizacion", "label": "Automatización", "icon": "⚡"},
    {"id": "memoria", "label": "Memoria (Obsidian)", "icon": "📖"},
    {"id": "configuracion", "label": "Configuración", "icon": "⚙"},
    {"id": "logs", "label": "Logs", "icon": "📄"},
]


class CyberSidebar(ctk.CTkFrame):
    """
    Rail de navegación vertical para la estación de mando Cybernetic Bento de Darius.

    Gestiona la selección activa de pestañas, el despacho de eventos de navegación
    y la presentación de la cita inspiracional del sistema.
    """

    def __init__(
        self,
        master: Any,
        width: int = DEFAULT_SIDEBAR_WIDTH,
        on_nav_change: Callable[[str], None] | None = None,
        initial_tab: str = "inicio",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            master,
            width=width,
            fg_color=SIDEBAR_BG,
            border_width=1,
            border_color=SIDEBAR_BORDER,
            corner_radius=0,
            **kwargs,
        )

        self.sidebar_width = width
        self.on_nav_change = on_nav_change
        self._current_tab = initial_tab
        self.nav_buttons: dict[str, ctk.CTkButton] = {}

        # Prevenir deformación dimensional del contenedor
        self.grid_propagate(False)
        self.pack_propagate(False)

        self._build_header()
        self._build_nav_items()
        self._build_quote_card()

        # Aplicar estado visual inicial
        self.select_tab(self._current_tab, dispatch_callback=False)

    @property
    def current_tab(self) -> str:
        """Devuelve el identificador de la pestaña actualmente activa."""
        return self._current_tab

    def _build_header(self) -> None:
        """Crea el separador superior o espacio inicial del sidebar."""
        self._top_spacer = ctk.CTkFrame(self, height=12, fg_color="transparent")
        self._top_spacer.pack(fill="x", pady=(8, 4))

    def _build_nav_items(self) -> None:
        """Construye los 6 botones interactivos de navegación."""
        self.nav_container = ctk.CTkFrame(self, fg_color="transparent")
        self.nav_container.pack(fill="x", padx=10, pady=4)

        for item in NAV_ITEMS:
            tab_id = item["id"]
            icon = item["icon"]
            label = item["label"]
            btn_text = f"  {icon}  {label}"

            btn = ctk.CTkButton(
                self.nav_container,
                text=btn_text,
                font=theme.FONT_NAV,
                height=38,
                corner_radius=theme.RADIUS_MD,
                fg_color="transparent",
                hover_color=NAV_HOVER_BG,
                text_color=NAV_INACTIVE_FG,
                border_width=0,
                anchor="w",
                command=lambda tid=tab_id: self.select_tab(tid),
            )
            btn.pack(fill="x", pady=3)
            self.nav_buttons[tab_id] = btn

    def _build_quote_card(self) -> None:
        """Construye la tarjeta de cita inspiracional en el fondo del sidebar."""
        self.quote_card = ctk.CTkFrame(
            self,
            fg_color="#0A101D",
            border_width=1,
            border_color=SIDEBAR_BORDER,
            corner_radius=theme.RADIUS_MD,
        )
        self.quote_card.pack(side="bottom", fill="x", padx=10, pady=(0, 16))

        # Indicador sutil de cápsula
        quote_header = ctk.CTkFrame(self.quote_card, height=2, fg_color=theme.ACCENT_PRIMARY)
        quote_header.pack(fill="x", padx=14, pady=(8, 4))

        self.quote_label = ctk.CTkLabel(
            self.quote_card,
            text=DEFAULT_INSPIRATIONAL_QUOTE,
            font=(theme.FONT_FAMILY, 9, "italic"),
            text_color=theme.TEXT_SECONDARY,
            justify="center",
            wraplength=self.sidebar_width - 36,
        )
        self.quote_label.pack(fill="x", padx=8, pady=(4, 10))

    def select_tab(self, tab_id: str, dispatch_callback: bool = True) -> None:
        """
        Selecciona y resalta una pestaña específica del sidebar.

        Args:
            tab_id: Identificador de la pestaña ('inicio', 'asistente', etc.).
            dispatch_callback: Si es True, despacha el evento a `on_nav_change`.
        """
        if tab_id not in self.nav_buttons:
            log.warning("Pestaña desconocida solicitada en CyberSidebar: %s", tab_id)
            return

        self._current_tab = tab_id

        # Actualizar estilo visual de todos los botones
        for tid, btn in self.nav_buttons.items():
            if tid == tab_id:
                btn.configure(
                    fg_color=NAV_ACTIVE_BG,
                    text_color=NAV_ACTIVE_FG,
                    border_width=1,
                    border_color=NAV_ACTIVE_BORDER,
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=NAV_INACTIVE_FG,
                    border_width=0,
                )

        if dispatch_callback and callable(self.on_nav_change):
            try:
                self.on_nav_change(tab_id)
            except Exception as exc:
                log.error("Error despachando on_nav_change(%s): %s", tab_id, exc)
