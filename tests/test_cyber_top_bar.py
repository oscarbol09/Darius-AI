"""
test_cyber_top_bar.py — Suite de pruebas para la Cyber Top Bar de Darius AI
=============================================================================
Protocolo ECC: TDD Red-Green-Refactor.
Valida:
  1. Formateadores puros y headless del estado del sistema y reloj.
  2. Inicialización del componente visual CyberTopBar.
  3. Contenido de las secciones izquierda (marca), centro (pill de estado) y derecha (reloj/usuario).
  4. Métodos públicos: update_clock, set_provider_info, set_system_status.
  5. Despacho de callbacks de acciones rápidas (configuración, mute, cerrar).
"""

from __future__ import annotations

import contextlib
from datetime import datetime
from unittest.mock import MagicMock

import customtkinter as ctk
import pytest

from src.darius_ai.gui.cyber_top_bar import (
    CyberTopBar,
    format_clock_string,
    format_status_badge,
)


class TestCyberTopBarPureLogic:
    """Valida los formateadores y lógica de la cabecera en modo headless."""

    def test_format_status_badge_nominal(self):
        badge = format_status_badge(
            system_status="Operativo",
            is_online=True,
            provider="Google",
            model="Gemini 2.5 Flash",
        )
        assert "Sistema: Operativo" in badge
        assert "Red: Conectado" in badge
        assert "IA: Gemini 2.5 Flash" in badge

    def test_format_status_badge_offline_and_custom(self):
        badge = format_status_badge(
            system_status="Alerta",
            is_online=False,
            provider="Local",
            model="Ollama Llama-3",
        )
        assert "Sistema: Alerta" in badge
        assert "Red: Desconectado" in badge
        assert "IA: Ollama Llama-3" in badge

    def test_format_clock_string_custom_dt(self):
        dt = datetime(2026, 10, 14, 15, 45, 0)
        time_str, date_str = format_clock_string(dt)
        assert time_str == "15:45"
        assert "14" in date_str
        assert "2026" in date_str

    def test_format_clock_string_defaults_to_now(self):
        time_str, date_str = format_clock_string(None)
        assert ":" in time_str
        assert len(time_str) == 5
        assert len(date_str) > 5


class TestCyberTopBarWidget:
    """Valida el widget visual de CustomTkinter."""

    @pytest.fixture
    def widget(self):
        """Crea una instancia real de CyberTopBar o salta en entornos sin display."""
        try:
            root = ctk.CTk()
            root.withdraw()
            top_bar = CyberTopBar(root)
        except Exception as exc:
            pytest.skip(f"Tkinter/Tcl no disponible en este entorno: {exc}")
        yield top_bar
        with contextlib.suppress(Exception):
            root.destroy()

    def test_brand_section_displays_darius_title_and_caption(self, widget):
        assert widget.lbl_brand_title.cget("text") == "DARIUS AI"
        assert widget.lbl_brand_caption.cget("text") == "TU COPILOTO EN WINDOWS"

    def test_status_pill_badge_default_content(self, widget):
        pill_text = widget.lbl_status_pill.cget("text")
        assert "Sistema: Operativo" in pill_text
        assert "Red: Conectado" in pill_text
        assert "IA:" in pill_text

    def test_clock_and_user_profile_display(self, widget):
        assert widget.lbl_user_status.cget("text") == "Darius ● En línea"
        assert len(widget.lbl_clock_time.cget("text")) >= 4
        assert len(widget.lbl_clock_date.cget("text")) >= 5

    def test_set_provider_info_updates_center_badge(self, widget):
        widget.set_provider_info("Anthropic", "Claude 3.7 Sonnet")
        pill_text = widget.lbl_status_pill.cget("text")
        assert "IA: Claude 3.7 Sonnet" in pill_text

    def test_set_system_status_updates_indicator(self, widget):
        widget.set_system_status("Alerta de Seguridad", is_online=False)
        pill_text = widget.lbl_status_pill.cget("text")
        assert "Sistema: Alerta de Seguridad" in pill_text
        assert "Red: Desconectado" in pill_text

        widget.set_system_status("Operativo", is_online=True)
        pill_text_2 = widget.lbl_status_pill.cget("text")
        assert "Sistema: Operativo" in pill_text_2
        assert "Red: Conectado" in pill_text_2

    def test_update_clock_method(self, widget):
        dt = datetime(2026, 10, 14, 21, 30, 0)
        widget.update_clock(dt=dt)
        assert widget.lbl_clock_time.cget("text") == "21:30"
        assert "14" in widget.lbl_clock_date.cget("text")

    def test_action_callbacks_invoked(self, widget):
        mock_settings = MagicMock()
        mock_mute = MagicMock()
        mock_close = MagicMock()

        widget.on_settings = mock_settings
        widget.on_mute = mock_mute
        widget.on_close = mock_close

        widget._handle_settings()
        mock_settings.assert_called_once()

        widget._handle_mute()
        mock_mute.assert_called_once()

        widget._handle_close()
        mock_close.assert_called_once()
