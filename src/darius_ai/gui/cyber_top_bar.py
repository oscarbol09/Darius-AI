"""
cyber_top_bar.py — Barra Superior Táctica Cyber Top Bar para DARIUS AI v8.5
===========================================================================
Cabecera táctica Cybernetic Bento inspirada en la consola de mando de Darius AI:
  1. Marca izquierda: Icono de reactor/marca + "DARIUS AI" + "TU COPILOTO EN WINDOWS".
  2. Badge central: Status Pill interactivo:
     "Sistema: Operativo | Red: Conectado | IA: [Modelo Activo]".
  3. Área derecha: Reloj digital en vivo (HH:MM / DD MMM YYYY), avatar de usuario
     con estado de disponibilidad ("Darius ● En línea") y accesos directos
     (Configuración, Mute, Cerrar).
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from datetime import datetime
from typing import Any, Final

import customtkinter as ctk

from src.darius_ai.gui import gui_theme as theme

# Meses abreviados en español para reloj táctico
SPANISH_MONTHS: Final[dict[int, str]] = {
    1: "Ene",
    2: "Feb",
    3: "Mar",
    4: "Abr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dic",
}


# =============================================================================
#  LÓGICA PURA Y FORMATEADORES HEADLESS
# =============================================================================
def format_status_badge(
    system_status: str = "Operativo",
    is_online: bool = True,
    provider: str = "Google",
    model: str = "Gemini 2.5 Flash",
) -> str:
    """Genera la cadena formateada del badge de telemetría de estado central."""
    net_str = "Conectado" if is_online else "Desconectado"
    model_str = model if model else (provider if provider else "Autónomo")
    return f"Sistema: {system_status} | Red: {net_str} | IA: {model_str}"


def format_clock_string(dt: datetime | None = None) -> tuple[str, str]:
    """Formatea la hora y fecha en formato militar táctico (HH:MM, DD MMM YYYY).

    Retorna:
        tuple[str, str]: (time_str, date_str), ej: ("14:30", "14 Oct 2026").
    """
    now = dt if dt is not None else datetime.now()
    month_name = SPANISH_MONTHS.get(now.month, now.strftime("%b"))
    time_str = now.strftime("%H:%M")
    date_str = f"{now.day:02d} {month_name} {now.year}"
    return time_str, date_str


# =============================================================================
#  WIDGET CYBER TOP BAR (CUSTOMTKINTER)
# =============================================================================
class CyberTopBar(ctk.CTkFrame):
    """Barra superior táctica con información de marca, estado del modelo y reloj en vivo."""

    def __init__(
        self,
        master: Any,
        on_settings: Callable[[], None] | None = None,
        on_mute: Callable[[], None] | None = None,
        on_close: Callable[[], None] | None = None,
        provider: str = "Google",
        model: str = "Gemini 2.5 Flash",
        **kwargs: Any,
    ) -> None:
        bg_bar = kwargs.pop("fg_color", theme.BG_HEADER)
        super().__init__(
            master,
            fg_color=bg_bar,
            corner_radius=theme.RADIUS_MD,
            border_width=1,
            border_color=theme.BORDER_SUBTLE,
            height=58,
            **kwargs,
        )

        # Callbacks
        self.on_settings = on_settings
        self.on_mute = on_mute
        self.on_close = on_close

        # Estado del sistema y telemetría
        self._system_status = "Operativo"
        self._is_online = True
        self._provider = provider
        self._model = model
        self._clock_timer_id: str | None = None

        self._build_ui()
        self.update_clock()
        self._schedule_clock()

    def _build_ui(self) -> None:
        """Construye las tres zonas de la barra superior: Izquierda, Centro, Derecha."""
        # =====================================================================
        # 1. ZONA IZQUIERDA: Marca y Logotipo
        # =====================================================================
        self.brand_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.brand_frame.pack(side="left", padx=(14, 10), pady=6)

        # Glifo distintivo de Darius Cyber Core
        self.lbl_brand_icon = ctk.CTkLabel(
            self.brand_frame,
            text="◈",
            font=(theme.FONT_FAMILY, 18, "bold"),
            text_color=theme.ACCENT_PRIMARY,
        )
        self.lbl_brand_icon.pack(side="left", padx=(0, 8))

        self.brand_text_box = ctk.CTkFrame(self.brand_frame, fg_color="transparent")
        self.brand_text_box.pack(side="left")

        self.lbl_brand_title = ctk.CTkLabel(
            self.brand_text_box,
            text="DARIUS AI",
            font=theme.FONT_TITLE,
            text_color=theme.TEXT_PRIMARY,
        )
        self.lbl_brand_title.pack(anchor="w")

        self.lbl_brand_caption = ctk.CTkLabel(
            self.brand_text_box,
            text="TU COPILOTO EN WINDOWS",
            font=theme.FONT_CAPTION,
            text_color=theme.TEXT_MUTED,
        )
        self.lbl_brand_caption.pack(anchor="w")

        # =====================================================================
        # 2. ZONA DERECHA: Reloj, Perfil y Acciones Rápidas
        # =====================================================================
        self.right_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.right_frame.pack(side="right", padx=(8, 14), pady=6)

        # Avatar y Estado de Usuario
        self.user_box = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.user_box.pack(side="left", padx=(0, 10))

        self.lbl_user_status = ctk.CTkLabel(
            self.user_box,
            text="Darius ● En línea",
            font=theme.FONT_CAPTION_BOLD,
            text_color=theme.ACCENT_EMERALD,
        )
        self.lbl_user_status.pack(anchor="e")

        # Reloj digital táctico
        self.clock_box = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.clock_box.pack(side="left", padx=(4, 12))

        self.lbl_clock_time = ctk.CTkLabel(
            self.clock_box,
            text="--:--",
            font=theme.FONT_SUBTITLE,
            text_color=theme.TEXT_PRIMARY,
        )
        self.lbl_clock_time.pack(anchor="e")

        self.lbl_clock_date = ctk.CTkLabel(
            self.clock_box,
            text="-- --- ----",
            font=theme.FONT_CAPTION,
            text_color=theme.TEXT_MUTED,
        )
        self.lbl_clock_date.pack(anchor="e")

        # Botones de Acción Rápida
        self.actions_box = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.actions_box.pack(side="left", padx=(2, 0))

        self.btn_settings = ctk.CTkButton(
            self.actions_box,
            text="⚙",
            width=28,
            height=28,
            corner_radius=theme.RADIUS_SM,
            fg_color=theme.BG_CARD_INNER,
            hover_color=theme.BG_CARD_HOVER,
            text_color=theme.TEXT_SECONDARY,
            command=self._handle_settings,
        )
        self.btn_settings.pack(side="left", padx=2)

        self.btn_mute = ctk.CTkButton(
            self.actions_box,
            text="🔊",
            width=28,
            height=28,
            corner_radius=theme.RADIUS_SM,
            fg_color=theme.BG_CARD_INNER,
            hover_color=theme.BG_CARD_HOVER,
            text_color=theme.TEXT_SECONDARY,
            command=self._handle_mute,
        )
        self.btn_mute.pack(side="left", padx=2)

        self.btn_close = ctk.CTkButton(
            self.actions_box,
            text="✕",
            width=28,
            height=28,
            corner_radius=theme.RADIUS_SM,
            fg_color=theme.BG_CARD_INNER,
            hover_color=theme.ACCENT_ROSE,
            text_color=theme.TEXT_SECONDARY,
            command=self._handle_close,
        )
        self.btn_close.pack(side="left", padx=2)

        # =====================================================================
        # 3. ZONA CENTRAL: Pill de Estado Expandible
        # =====================================================================
        self.center_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.center_frame.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        self.pill_card = ctk.CTkFrame(
            self.center_frame,
            fg_color=theme.BG_PILL,
            corner_radius=theme.RADIUS_LG,
            border_width=1,
            border_color=theme.BORDER_CARD,
        )
        self.pill_card.pack(anchor="center", pady=2, padx=4)

        initial_status = format_status_badge(
            self._system_status,
            self._is_online,
            self._provider,
            self._model,
        )
        self.lbl_status_pill = ctk.CTkLabel(
            self.pill_card,
            text=initial_status,
            font=theme.FONT_BADGE,
            text_color=theme.TEXT_SECONDARY,
            padx=14,
            pady=4,
        )
        self.lbl_status_pill.pack()
        # Aliases de compatibilidad hacia atrás
        self.lbl_system_badge = self.lbl_status_pill
        self.lbl_status_badge = self.lbl_status_pill


    # =========================================================================
    #  MÉTODOS PÚBLICOS DE ACTUALIZACIÓN
    # =========================================================================
    def update_clock(self, dt: datetime | None = None) -> None:
        """Actualiza la hora y fecha mostrada en la sección del reloj."""
        time_str, date_str = format_clock_string(dt)
        self.lbl_clock_time.configure(text=time_str)
        self.lbl_clock_date.configure(text=date_str)

    def set_provider_info(self, provider_name: str, model_name: str) -> None:
        """Actualiza la información del proveedor y modelo IA activo en el badge."""
        self._provider = provider_name
        self._model = model_name
        self._refresh_status_pill()

    def set_system_status(self, status_text: str, is_online: bool = True) -> None:
        """Actualiza el indicador de estado del sistema y conectividad de red."""
        self._system_status = status_text
        self._is_online = is_online

        # Actualizar color del indicador de usuario según la red
        if is_online:
            self.lbl_user_status.configure(
                text="Darius ● En línea",
                text_color=theme.ACCENT_EMERALD,
            )
        else:
            self.lbl_user_status.configure(
                text="Darius ○ Desconectado",
                text_color=theme.ACCENT_ROSE,
            )

        self._refresh_status_pill()

    def _refresh_status_pill(self) -> None:
        """Regenera el texto del pill central con el estado consolidado."""
        pill_text = format_status_badge(
            system_status=self._system_status,
            is_online=self._is_online,
            provider=self._provider,
            model=self._model,
        )
        self.lbl_status_pill.configure(text=pill_text)

    # =========================================================================
    #  DESPACHO DE EVENTOS Y RELOJ PERIÓDICO
    # =========================================================================
    def _schedule_clock(self) -> None:
        """Programa el refresco automático del reloj cada segundo."""
        def _tick() -> None:
            self.update_clock()
            self._clock_timer_id = self.after(1000, _tick)

        self._clock_timer_id = self.after(1000, _tick)

    def _handle_settings(self) -> None:
        if self.on_settings is not None:
            self.on_settings()

    def _handle_mute(self) -> None:
        if self.on_mute is not None:
            self.on_mute()

    def _handle_close(self) -> None:
        if self.on_close is not None:
            self.on_close()

    def destroy(self) -> None:
        """Cancela temporizadores pendientes antes de destruir el widget."""
        if self._clock_timer_id is not None:
            with contextlib.suppress(Exception):
                self.after_cancel(self._clock_timer_id)
            self._clock_timer_id = None
        super().destroy()
