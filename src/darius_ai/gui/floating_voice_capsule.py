"""
floating_voice_capsule.py — Cápsula Flotante de Activación por Voz para DARIUS AI v8.5
=====================================================================================
Dock de control flotante estilo Cybernetic Bento Glassmorphism:
  1. Contenedor de cristal oscuro (#070B14 / #0B1220) con radio curvo y borde sutil.
  2. Botón circular de micrófono con halo pulsante reactivo en color cian (#00F0FF).
  3. Indicador de energía de voz / espectro RMS en vivo.
  4. Entrada de texto con atajo de teclado <Return> y placeholder 'Di: "Hola Darius..."'.
  5. Conmutador de modos tácticos de audio:
     - PTT: Pulsar para hablar
     - NOM: Modo Nominal / Estándar
     - AUTO: Activación automática por voz (VAD)
     - GEMINI LIVE: Sesión de voz continua de baja latencia
"""

from __future__ import annotations

import contextlib
import logging
import math
from collections.abc import Callable
from typing import Any, Final

import customtkinter as ctk

from src.darius_ai.gui import gui_theme as theme

log = logging.getLogger("darius.voice_capsule")

# =============================================================================
#  TOKENS VISUALES & CONSTANTES DE LA CÁPSULA
# =============================================================================
CAPSULE_BG: Final[str] = "#070B14"
CAPSULE_BORDER: Final[str] = "#1E293B"

HALO_ACTIVE_COLOR: Final[str] = "#00F0FF"
HALO_INACTIVE_COLOR: Final[str] = "#1E293B"
HALO_PULSE_SECONDARY: Final[str] = "#0284C7"

MIC_ACTIVE_BG: Final[str] = "#0D223A"
MIC_INACTIVE_BG: Final[str] = "#131C2D"
MIC_ACTIVE_ICON_COLOR: Final[str] = "#00F0FF"
MIC_INACTIVE_ICON_COLOR: Final[str] = "#94A3B8"

VOICE_MODES: Final[tuple[str, ...]] = ("PTT", "NOM", "AUTO", "GEMINI LIVE")


class FloatingVoiceCapsule(ctk.CTkFrame):
    """
    Cápsula flotante de activación y control de voz/texto para Darius AI.

    Ofrece acceso rápido a activación de micrófono, visualizador de nivel RMS,
    entrada de texto por lenguaje natural y alternancia de modos operativos.
    """

    def __init__(
        self,
        master: Any,
        on_submit_callback: Callable[[str], None] | None = None,
        on_mode_change: Callable[[str], None] | None = None,
        on_mic_toggle: Callable[[bool], None] | None = None,
        default_mode: str = "NOM",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            master,
            fg_color=CAPSULE_BG,
            border_width=1,
            border_color=CAPSULE_BORDER,
            corner_radius=22,
            **kwargs,
        )

        self.on_submit_callback = on_submit_callback
        self.on_mode_change = on_mode_change
        self.on_mic_toggle = on_mic_toggle

        self._is_mic_active = False
        self._current_mode = default_mode if default_mode in VOICE_MODES else "NOM"
        self._halo_color = HALO_INACTIVE_COLOR
        self._current_rms = 0.0
        self._pulse_phase = 0.0
        self._pulse_timer_id: str | None = None

        self.mode_buttons: dict[str, ctk.CTkButton] = {}

        self._build_components()
        self._update_mic_styling()
        self._update_mode_styling()

    @property
    def is_mic_active(self) -> bool:
        """Devuelve si el micrófono está actualmente en estado activo/escuchando."""
        return self._is_mic_active

    @property
    def current_mode(self) -> str:
        """Devuelve el modo operativo de voz actualmente activo."""
        return self._current_mode

    @property
    def halo_color(self) -> str:
        """Devuelve el color del halo del micrófono."""
        return self._halo_color

    @property
    def current_rms(self) -> float:
        """Devuelve el valor actual de energía RMS de audio [0.0, 100.0]."""
        return self._current_rms

    def _build_components(self) -> None:
        """Construye los elementos de interfaz interna de la cápsula."""
        # 1. Contenedor del Micrófono y Halo
        self.mic_container = ctk.CTkFrame(
            self,
            width=50,
            height=50,
            fg_color="transparent",
        )
        self.mic_container.pack(side="left", padx=(10, 6), pady=6)
        self.mic_container.pack_propagate(False)

        self.halo_frame = ctk.CTkFrame(
            self.mic_container,
            width=46,
            height=46,
            corner_radius=23,
            fg_color=self._halo_color,
            border_width=0,
        )
        self.halo_frame.place(relx=0.5, rely=0.5, anchor="center")

        self.mic_button = ctk.CTkButton(
            self.halo_frame,
            text="🎙",
            width=40,
            height=40,
            corner_radius=20,
            font=(theme.FONT_FAMILY, 15),
            fg_color=MIC_INACTIVE_BG,
            hover_color=MIC_ACTIVE_BG,
            text_color=MIC_INACTIVE_ICON_COLOR,
            command=self.toggle_mic,
        )
        self.mic_button.place(relx=0.5, rely=0.5, anchor="center")

        # 2. Indicador visual de forma de onda / RMS
        self.waveform_canvas = ctk.CTkCanvas(
            self,
            width=42,
            height=26,
            bg=CAPSULE_BG,
            highlightthickness=0,
        )
        self.waveform_canvas.pack(side="left", padx=(0, 8), pady=6)
        self._draw_waveform()

        # 3. Campo de entrada de texto
        self.entry = ctk.CTkEntry(
            self,
            placeholder_text='Di: "Hola Darius..."',
            font=theme.FONT_BODY,
            height=36,
            corner_radius=theme.RADIUS_MD,
            fg_color="#0A101D",
            border_color="#1E293B",
            border_width=1,
            text_color=theme.TEXT_PRIMARY,
            placeholder_text_color=theme.TEXT_MUTED,
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=6)
        self.entry.bind("<Return>", lambda _event: self._on_submit())

        # Botón de enviar texto (icono retorno / submit)
        self.submit_btn = ctk.CTkButton(
            self,
            text="↵",
            width=32,
            height=34,
            corner_radius=theme.RADIUS_MD,
            font=(theme.FONT_MONO_FAMILY, 14, "bold"),
            fg_color="#131C2D",
            hover_color="#1E293B",
            text_color=theme.ACCENT_PRIMARY,
            command=self._on_submit,
        )
        self.submit_btn.pack(side="left", padx=(0, 10), pady=6)

        # 4. Modos de voz rápidos (PTT, NOM, AUTO, GEMINI LIVE)
        self.modes_container = ctk.CTkFrame(self, fg_color="transparent")
        self.modes_container.pack(side="right", padx=(0, 12), pady=6)

        for mode in VOICE_MODES:
            btn = ctk.CTkButton(
                self.modes_container,
                text=mode,
                width=38 if len(mode) <= 4 else 80,
                height=26,
                corner_radius=theme.RADIUS_SM,
                font=(theme.FONT_FAMILY, 9, "bold"),
                fg_color="transparent",
                hover_color="#131C2D",
                text_color=theme.TEXT_MUTED,
                border_width=0,
                command=lambda m=mode: self.set_mode(m),
            )
            btn.pack(side="left", padx=2)
            self.mode_buttons[mode] = btn

    def _draw_waveform(self) -> None:
        """Dibuja barras de nivel de audio en el canvas basadas en self._current_rms."""
        with contextlib.suppress(Exception):
            self.waveform_canvas.delete("all")
            width = 42
            height = 26
            num_bars = 4
            bar_width = 4
            gap = 5
            start_x = (width - (num_bars * bar_width + (num_bars - 1) * gap)) / 2

            norm = self._current_rms / 100.0
            color = HALO_ACTIVE_COLOR if self._is_mic_active else theme.TEXT_MUTED

            for i in range(num_bars):
                # Escalar barra según armónicos o RMS
                scale = math.sin((i + 1) * 0.8) * 0.4 + 0.6
                h = max(3.0, (height - 6) * norm * scale)
                x0 = start_x + i * (bar_width + gap)
                x1 = x0 + bar_width
                y0 = (height - h) / 2
                y1 = y0 + h
                self.waveform_canvas.create_rectangle(
                    x0, y0, x1, y1,
                    fill=color,
                    outline="",
                )

    def _update_mic_styling(self) -> None:
        """Aplica la colorimetría correspondiente al estado activo o inactivo del mic."""
        if self._is_mic_active:
            self._halo_color = HALO_ACTIVE_COLOR
            self.halo_frame.configure(fg_color=self._halo_color)
            self.mic_button.configure(
                fg_color=MIC_ACTIVE_BG,
                text_color=MIC_ACTIVE_ICON_COLOR,
            )
            self._start_pulse_animation()
        else:
            self._halo_color = HALO_INACTIVE_COLOR
            self.halo_frame.configure(fg_color=self._halo_color)
            self.mic_button.configure(
                fg_color=MIC_INACTIVE_BG,
                text_color=MIC_INACTIVE_ICON_COLOR,
            )
            self._stop_pulse_animation()
        self._draw_waveform()

    def _update_mode_styling(self) -> None:
        """Actualiza la apariencia de los botones de modo según el modo activo."""
        for mode, btn in self.mode_buttons.items():
            if mode == self._current_mode:
                btn.configure(
                    fg_color=MIC_ACTIVE_BG,
                    text_color=HALO_ACTIVE_COLOR,
                    border_width=1,
                    border_color=HALO_ACTIVE_COLOR,
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=theme.TEXT_MUTED,
                    border_width=0,
                )

    def set_mic_active(self, active: bool) -> None:
        """
        Activa o desactiva visualmente el micrófono y su halo luminoso.

        Args:
            active: True para indicar micrófono activo / escuchando, False en reposo.
        """
        self._is_mic_active = bool(active)
        self._update_mic_styling()

    def toggle_mic(self) -> None:
        """Alterna el estado del micrófono y despacha el callback si está configurado."""
        self.set_mic_active(not self._is_mic_active)
        if callable(self.on_mic_toggle):
            try:
                self.on_mic_toggle(self._is_mic_active)
            except Exception as exc:
                log.error("Error al despachar on_mic_toggle(%s): %s", self._is_mic_active, exc)

    def set_mode(self, mode: str) -> None:
        """
        Cambia el modo operativo de voz ('PTT', 'NOM', 'AUTO', 'GEMINI LIVE').

        Args:
            mode: Nombre del modo táctico.
        """
        if mode not in VOICE_MODES:
            log.warning("Modo de voz no reconocido: %s", mode)
            return

        self._current_mode = mode
        self._update_mode_styling()

        if callable(self.on_mode_change):
            try:
                self.on_mode_change(mode)
            except Exception as exc:
                log.error("Error al despachar on_mode_change(%s): %s", mode, exc)

    def set_rms_energy(self, rms: float) -> None:
        """
        Actualiza el nivel de energía sonora RMS de la cápsula [0.0, 100.0].

        Args:
            rms: Nivel de audio en escala 0 a 100.
        """
        self._current_rms = max(0.0, min(100.0, float(rms)))
        self._draw_waveform()

    def set_prompt_text(self, text: str) -> None:
        """Establece el texto dentro del campo de entrada."""
        self.entry.delete(0, "end")
        self.entry.insert(0, text)

    def get_prompt_text(self) -> str:
        """Obtiene el texto actual del campo de entrada."""
        return self.entry.get()

    def clear_prompt(self) -> None:
        """Limpia el campo de entrada."""
        self.entry.delete(0, "end")

    def _on_submit(self) -> None:
        """Procesa el envío del prompt ingresado por el usuario."""
        text = self.get_prompt_text().strip()
        if not text:
            return

        self.clear_prompt()
        if callable(self.on_submit_callback):
            try:
                self.on_submit_callback(text)
            except Exception as exc:
                log.error("Error al despachar on_submit_callback(%s): %s", text, exc)

    def _pulse_step(self) -> None:
        """Avanza un paso de la animación del halo del micrófono."""
        self._pulse_phase += 0.25
        if self._is_mic_active:
            # Oscilación suave de luminosidad entre cian brillante y cian medio
            sine_val = (math.sin(self._pulse_phase) + 1.0) / 2.0
            halo_color = HALO_ACTIVE_COLOR if sine_val > 0.4 else HALO_PULSE_SECONDARY
            self._halo_color = halo_color
            with contextlib.suppress(Exception):
                self.halo_frame.configure(fg_color=halo_color)

    def _start_pulse_animation(self) -> None:
        """Inicia el bucle de temporizador para pulsar el halo."""
        self._stop_pulse_animation()
        self._schedule_next_pulse()

    def _schedule_next_pulse(self) -> None:
        """Programa el siguiente fotograma del pulso."""
        if not self._is_mic_active:
            return
        self._pulse_step()
        with contextlib.suppress(Exception):
            self._pulse_timer_id = self.after(120, self._schedule_next_pulse)

    def _stop_pulse_animation(self) -> None:
        """Detiene el temporizador de animación del halo."""
        if self._pulse_timer_id is not None:
            with contextlib.suppress(Exception):
                self.after_cancel(self._pulse_timer_id)
            self._pulse_timer_id = None
