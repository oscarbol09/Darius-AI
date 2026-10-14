"""
test_cyber_sidebar.py — Suite de pruebas para el Cyber Sidebar Navigation Rail (Darius v8.5)
=============================================================================================
Protocolo ECC: TDD Red-Green-Refactor.
Valida:
  1. Constantes y configuración visual del sidebar (ancho 200-220px, dark glass, borde hairline).
  2. Los 6 elementos de navegación requeridos por el diseño Bento del mockup.
  3. Comportamiento del método `select_tab(tab_id)` y despacho del callback `on_nav_change`.
  4. Estado visual activo (glowing cyan pill) e inactivo.
  5. Presencia y contenido de la tarjeta inferior de cita inspiracional de Darius.
  6. Resiliencia ante excepciones en el callback de navegación y pestañas no existentes.
"""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock

import customtkinter as ctk
import pytest

from src.darius_ai.gui.cyber_sidebar import (
    DEFAULT_INSPIRATIONAL_QUOTE,
    DEFAULT_SIDEBAR_WIDTH,
    NAV_ITEMS,
    SIDEBAR_BG,
    SIDEBAR_BORDER,
    CyberSidebar,
)


class TestCyberSidebarConstants:
    """Verifica constantes de diseño y especificación del Cyber Sidebar."""

    def test_sidebar_dimensions(self):
        assert 200 <= DEFAULT_SIDEBAR_WIDTH <= 220

    def test_color_tokens(self):
        assert SIDEBAR_BG in ("#0B1220", "#070B14")
        assert SIDEBAR_BORDER == "#1E293B"

    def test_nav_items_specification(self):
        expected_ids = ["inicio", "asistente", "automatizacion", "memoria", "configuracion", "logs"]
        actual_ids = [item["id"] for item in NAV_ITEMS]
        assert actual_ids == expected_ids
        assert len(NAV_ITEMS) == 6

        labels = {item["id"]: item["label"] for item in NAV_ITEMS}
        assert "Inicio" in labels["inicio"]
        assert "Asistente" in labels["asistente"]
        assert "Automatización" in labels["automatizacion"]
        assert "Memoria" in labels["memoria"]
        assert "Configuración" in labels["configuracion"]
        assert "Logs" in labels["logs"]

    def test_inspirational_quote_text(self):
        assert "La tecnología es más poderosa cuando te da tiempo para pensar." in DEFAULT_INSPIRATIONAL_QUOTE
        assert "Darius" in DEFAULT_INSPIRATIONAL_QUOTE


class TestCyberSidebarWidget:
    """Verifica el widget CyberSidebar en entorno CustomTkinter."""

    @pytest.fixture
    def sidebar_fixture(self):
        try:
            root = ctk.CTk()
            root.withdraw()
            mock_callback = MagicMock()
            sidebar = CyberSidebar(root, on_nav_change=mock_callback)
        except Exception as exc:
            pytest.skip(f"Tkinter/Tcl no disponible en este entorno: {exc}")
        yield sidebar, mock_callback, root
        with contextlib.suppress(Exception):
            sidebar.destroy()
            root.destroy()

    def test_sidebar_initialization(self, sidebar_fixture):
        sidebar, _, _ = sidebar_fixture
        assert sidebar is not None
        assert isinstance(sidebar, ctk.CTkFrame)
        assert sidebar.current_tab == "inicio"
        assert len(sidebar.nav_buttons) == 6
        for item_id in ["inicio", "asistente", "automatizacion", "memoria", "configuracion", "logs"]:
            assert item_id in sidebar.nav_buttons

    def test_select_tab_dispatches_callback(self, sidebar_fixture):
        sidebar, mock_callback, _ = sidebar_fixture
        sidebar.select_tab("asistente")
        assert sidebar.current_tab == "asistente"
        mock_callback.assert_called_once_with("asistente")

    def test_select_tab_all_items(self, sidebar_fixture):
        sidebar, mock_callback, _ = sidebar_fixture
        for item_id in ["automatizacion", "memoria", "configuracion", "logs", "inicio"]:
            mock_callback.reset_mock()
            sidebar.select_tab(item_id)
            assert sidebar.current_tab == item_id
            mock_callback.assert_called_once_with(item_id)

    def test_select_tab_invalid_id_ignored(self, sidebar_fixture):
        sidebar, mock_callback, _ = sidebar_fixture
        initial_tab = sidebar.current_tab
        sidebar.select_tab("vista_inexistente")
        # No debe cambiar de pestaña ni disparar callback
        assert sidebar.current_tab == initial_tab
        mock_callback.assert_not_called()

    def test_active_styling_applied(self, sidebar_fixture):
        sidebar, _, _ = sidebar_fixture
        sidebar.select_tab("memoria")
        active_btn = sidebar.nav_buttons["memoria"]
        inactive_btn = sidebar.nav_buttons["inicio"]

        # El botón activo debe tener el color de fondo cyan pill / activo
        assert active_btn.cget("fg_color") != "transparent"
        assert inactive_btn.cget("fg_color") == "transparent"

    def test_quote_card_rendered(self, sidebar_fixture):
        sidebar, _, _ = sidebar_fixture
        assert hasattr(sidebar, "quote_card")
        assert hasattr(sidebar, "quote_label")
        quote_text = sidebar.quote_label.cget("text")
        assert "La tecnología es más poderosa" in quote_text
        assert "Darius" in quote_text

    def test_set_nav_callback(self, sidebar_fixture):
        sidebar, _, _ = sidebar_fixture
        new_callback = MagicMock()
        sidebar.on_nav_change = new_callback
        sidebar.select_tab("configuracion")
        new_callback.assert_called_once_with("configuracion")

    def test_callback_exception_handled_safely(self, sidebar_fixture):
        sidebar, _, _ = sidebar_fixture
        faulty_callback = MagicMock(side_effect=RuntimeError("Test error"))
        sidebar.on_nav_change = faulty_callback
        # No debe propagar la excepción hacia arriba, se captura y registra en log
        sidebar.select_tab("logs")
        assert sidebar.current_tab == "logs"
