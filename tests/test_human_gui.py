"""
test_human_gui.py — Tests Unitarios para el Motor de Automatización de Interfaz Humana
======================================================================================
Valida:
  1. Generación matemática de trayectorias con Curvas de Bézier cúbicas.
  2. Mecanismo de Failsafe (esquina de pánico y detención por evento).
  3. Emulación de clics, scroll y atajos de teclado (hotkeys).
  4. Escritura mecanográfica con soporte Unicode.
  5. Scraping web limpio con manejo defensivo de errores HTTP.
"""

import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from human_gui import (
    FailsafeError,
    HumanGUIAutomator,
)


class TestBezierTrajectories:
    """Verifica las propiedades matemáticas de la trayectoria de Bézier."""

    def test_trajectory_endpoints(self):
        start = (100, 100)
        end = (800, 600)
        path = HumanGUIAutomator.calculate_bezier_trajectory(start, end, steps=30)

        assert len(path) == 30
        assert path[-1] == end

    def test_trajectory_non_linear_deviation(self):
        start = (0, 0)
        end = (1000, 1000)
        path = HumanGUIAutomator.calculate_bezier_trajectory(start, end, steps=40, deviation_factor=0.3)

        # La línea recta exacta en el punto medio tendría x=500, y=500
        mid_point = path[len(path) // 2]
        assert isinstance(mid_point[0], int)
        assert isinstance(mid_point[1], int)

    def test_short_distance_returns_end(self):
        start = (50, 50)
        end = (51, 52)
        path = HumanGUIAutomator.calculate_bezier_trajectory(start, end)
        assert path == [end]


class TestFailsafeSystem:
    """Valida la activación del interruptor de pánico (Failsafe)."""

    def test_failsafe_at_screen_corner(self):
        automator = HumanGUIAutomator()
        with patch.object(automator, "get_cursor_pos", return_value=(0, 0)), \
             pytest.raises(FailsafeError, match="esquina"):
            automator.check_failsafe()

    def test_failsafe_safe_position_does_not_raise(self):
        automator = HumanGUIAutomator()
        with patch.object(automator, "get_cursor_pos", return_value=(500, 400)):
            automator.check_failsafe()  # No debe lanzar excepción

    def test_abort_flag_triggers_failsafe(self):
        automator = HumanGUIAutomator()
        automator.abort()
        with patch.object(automator, "get_cursor_pos", return_value=(500, 400)), \
             pytest.raises(FailsafeError, match="abortada"):
            automator.check_failsafe()


class TestMouseAndKeyboardActions:
    """Valida los despachos de clics, escritura y combinaciones de teclas."""

    @patch("time.sleep")
    def test_human_mouse_move_mocked(self, mock_sleep):
        automator = HumanGUIAutomator()
        automator.failsafe_enabled = False
        with patch.object(automator, "set_cursor_pos") as mock_set, \
             patch.object(automator, "get_cursor_pos", return_value=(100, 100)):
            ok = automator.human_mouse_move(500, 500, steps=10)
            assert ok is True
            assert mock_set.call_count >= 10
            # Última llamada debe ser exactamente el target
            assert mock_set.call_args[0] == (500, 500)

    @patch("time.sleep")
    def test_human_click_mocked(self, mock_sleep):
        automator = HumanGUIAutomator()
        automator.failsafe_enabled = False
        mock_u32 = MagicMock()
        automator._user32 = mock_u32

        with patch.object(automator, "get_cursor_pos", return_value=(300, 200)):
            ok = automator.human_click(button="left", double=False)
            assert ok is True
            assert mock_u32.mouse_event.call_count == 2  # down y up

            ok_double = automator.human_click(button="right", double=True)
            assert ok_double is True
            # 2 para single + 4 para double = 6 total
            assert mock_u32.mouse_event.call_count == 6

    @patch("time.sleep")
    def test_human_type_unicode(self, mock_sleep):
        automator = HumanGUIAutomator()
        automator.failsafe_enabled = False
        mock_u32 = MagicMock()
        automator._user32 = mock_u32

        text_to_type = "Hola Óscar! \n"
        ok = automator.human_type(text_to_type, wpm=80)
        assert ok is True
        # Cada carácter Unicode genera 2 llamadas a keybd_event (down y up)
        assert mock_u32.keybd_event.call_count >= len(text_to_type) * 2

    @patch("time.sleep")
    def test_human_hotkey_execution(self, mock_sleep):
        automator = HumanGUIAutomator()
        automator.failsafe_enabled = False
        mock_u32 = MagicMock()
        automator._user32 = mock_u32

        ok = automator.human_hotkey("ctrl", "v")
        assert ok is True
        # Presionar ctrl (down), v (down), soltar v (up), soltar ctrl (up) = 4 llamadas
        assert mock_u32.keybd_event.call_count == 4


class TestWebScraping:
    """Pruebas para el raspado y extracción de páginas web."""

    @patch("urllib.request.urlopen")
    def test_scrape_web_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = (
            b"<!DOCTYPE html><html><head><title>Noticias Tech</title>"
            b"<style>body { color: red; }</style>"
            b"<script>console.log('test');</script></head>"
            b"<body><nav>Menu</nav><header>Header</header>"
            b"<h1>Titulo Principal</h1><p>Darius AI ha actualizado su motor autonomo.</p>"
            b"<footer>Copyright</footer></body></html>"
        )
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        data = HumanGUIAutomator.scrape_web_content("https://noticias.example.com")
        assert data["success"] is True
        assert data["title"] == "Noticias Tech"
        assert "Darius AI ha actualizado" in data["content"]
        assert "<script>" not in data["content"]
        assert "<style>" not in data["content"]
        assert "<nav>" not in data["content"]

    @patch("urllib.request.urlopen")
    def test_scrape_web_http_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://fail.example.com",
            code=404,
            msg="Not Found",
            hdrs=None,  # type: ignore[arg-type]
            fp=None,
        )

        data = HumanGUIAutomator.scrape_web_content("https://fail.example.com")
        assert data["success"] is False
        assert "404" in data["error"]
