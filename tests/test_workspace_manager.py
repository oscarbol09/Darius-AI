"""
test_workspace_manager.py — Tests Unitarios para el Gestor de Workspaces y Monitores
=====================================================================================
Valida la detección de monitores, snapping de ventanas y ejecución de rutinas compuestas.
"""

from unittest.mock import MagicMock, patch

from workspace_manager import (
    find_chrome_executable,
    find_cursor_executable,
    find_vscode_executable,
    get_monitor_bounds,
    get_monitor_count,
    get_monitor_rects,
    get_monitor_size,
    open_url_on_monitor,
    run_darius_welcome_protocol,
    run_dev_mode,
    run_trading_mode,
)


def test_get_monitor_rects():
    """get_monitor_rects debe retornar al menos un monitor."""
    rects = get_monitor_rects()
    assert isinstance(rects, list)
    assert len(rects) >= 1
    assert len(rects[0]) == 4


def test_get_monitor_bounds_and_size():
    """get_monitor_bounds y get_monitor_size deben respetar límites razonables."""
    bounds = get_monitor_bounds(1)
    assert len(bounds) == 4
    w, h = get_monitor_size(1)
    assert w >= 320
    assert h >= 240


def test_get_monitor_count():
    """El conteo de monitores debe ser un entero positivo."""
    count = get_monitor_count()
    assert isinstance(count, int)
    assert count >= 1


def test_executable_finders():
    """Los buscadores de ejecutables retornan str o None sin lanzar excepciones."""
    chrome = find_chrome_executable()
    cursor = find_cursor_executable()
    code = find_vscode_executable()
    assert chrome is None or isinstance(chrome, str)
    assert cursor is None or isinstance(cursor, str)
    assert code is None or isinstance(code, str)


def test_open_url_on_monitor_empty():
    """Una URL vacía no realiza ninguna acción y retorna False."""
    assert open_url_on_monitor("") is False


def test_open_url_on_monitor_mocked():
    """Apertura de URL en monitor con Popen mocked."""
    with patch("workspace_manager.find_chrome_executable", return_value="C:\\dummy\\chrome.exe"), \
         patch("subprocess.Popen") as mock_popen:
        res = open_url_on_monitor("https://example.com", monitor_index=1, fullscreen=True)
        assert res is True
        mock_popen.assert_called_once()


def test_run_darius_welcome_protocol():
    """Ejecución del protocolo de bienvenida Darius sin excepciones."""
    talk_mock = MagicMock()
    with patch("workspace_manager.play_spotify_or_song"), \
         patch("workspace_manager.open_url_on_monitor"), \
         patch("workspace_manager.focus_or_launch_cursor"), \
         patch("time.sleep"):
        run_darius_welcome_protocol(
            talk_fn=talk_mock,
            song_url="https://spotify.com/dummy",
            claude_url="https://claude.ai",
            welcome_phrase="Hola",
        )
        talk_mock.assert_called_once_with("Hola")


def test_run_dev_mode():
    """Ejecución de modo desarrollo."""
    talk_mock = MagicMock()
    with patch("workspace_manager.open_url_on_monitor"), \
         patch("workspace_manager.focus_or_launch_cursor"):
        run_dev_mode(talk_fn=talk_mock)
        talk_mock.assert_called_once()


def test_run_trading_mode():
    """Ejecución de modo trading."""
    talk_mock = MagicMock()
    with patch("workspace_manager.open_url_on_monitor"):
        run_trading_mode(talk_fn=talk_mock)
        talk_mock.assert_called_once()
