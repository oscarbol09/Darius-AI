"""
test_workspace_manager.py — Tests Unitarios para el Gestor de Workspaces y Monitores
=====================================================================================
Valida la detección de monitores, snapping de ventanas y ejecución de rutinas compuestas.
"""

from unittest.mock import MagicMock, patch

from src.darius_ai.system.workspace_manager import (
    _check_and_update_cooldown,
    find_chrome_executable,
    find_cursor_executable,
    find_vscode_executable,
    focus_or_launch_cursor,
    get_monitor_bounds,
    get_monitor_count,
    get_monitor_rects,
    get_monitor_size,
    open_url_on_monitor,
    play_spotify_or_song,
    run_darius_welcome_protocol,
    run_dev_mode,
    run_trading_mode,
    snap_window_to_monitor,
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
    with (
        patch("src.darius_ai.system.workspace_manager.find_chrome_executable", return_value="C:\\dummy\\chrome.exe"),
        patch("subprocess.Popen") as mock_popen,
    ):
        res = open_url_on_monitor("https://example.com", monitor_index=1, fullscreen=True)
        assert res is True
        mock_popen.assert_called_once()


def test_play_spotify_or_song():
    """Prueba que URLs o URIs de Spotify se procesen adecuadamente."""
    # Vacío -> no-op
    play_spotify_or_song("")

    # Con valor en Windows
    with patch("os.startfile", create=True) as mock_startfile:
        play_spotify_or_song("spotify:track:12345")
        mock_startfile.assert_called_once_with("spotify:track:12345")


def test_check_and_update_cooldown():
    """Prueba que el cooldown prevenga ejecuciones repetidas inmediatas."""
    routine_name = "test_cooldown_routine"
    # Primera llamada -> True
    assert _check_and_update_cooldown(routine_name, cooldown_secs=5.0) is True
    # Inmediatamente después -> False
    assert _check_and_update_cooldown(routine_name, cooldown_secs=5.0) is False


def test_focus_or_launch_cursor():
    """Prueba el comportamiento de enfocar o lanzar Cursor."""
    # Caso 1: Cursor ya está abierto
    with (
        patch("src.darius_ai.system.workspace_manager.get_process_main_hwnd", return_value=12345),
        patch("src.darius_ai.system.workspace_manager.bring_window_to_foreground") as mock_bring,
        patch("src.darius_ai.system.workspace_manager.send_f11_fullscreen") as mock_f11,
    ):
        res = focus_or_launch_cursor(fullscreen=True)
        assert res is True
        mock_bring.assert_called_once_with(12345)
        mock_f11.assert_called_once_with(12345)

    # Caso 2: Cursor no está abierto, se lanza ejecutable
    with (
        patch("src.darius_ai.system.workspace_manager.get_process_main_hwnd", return_value=None),
        patch("src.darius_ai.system.workspace_manager.find_cursor_executable", return_value="C:\\dummy\\Cursor.exe"),
        patch("subprocess.Popen") as mock_popen,
    ):
        res = focus_or_launch_cursor(fullscreen=False)
        assert res is True
        mock_popen.assert_called_once()


def test_snap_window_to_monitor_invalid_hwnd():
    """snap_window_to_monitor con hwnd=0 debe retornar silenciosamente."""
    snap_window_to_monitor(0, 1)


def test_run_darius_welcome_protocol():
    """Ejecución del protocolo de bienvenida Darius sin excepciones."""
    talk_mock = MagicMock()
    with (
        patch("src.darius_ai.system.workspace_manager.play_spotify_or_song"),
        patch("src.darius_ai.system.workspace_manager.open_url_on_monitor"),
        patch("src.darius_ai.system.workspace_manager.focus_or_launch_cursor"),
        patch("time.sleep"),
    ):
        run_darius_welcome_protocol(
            talk_fn=talk_mock,
            song_url="https://spotify.com/dummy",
            claude_url="https://claude.ai",
            welcome_phrase="Hola",
            cooldown_secs=0.0,
        )
        talk_mock.assert_called_once_with("Hola")


def test_run_dev_mode():
    """Ejecución de modo desarrollo."""
    talk_mock = MagicMock()
    with (
        patch("src.darius_ai.system.workspace_manager.open_url_on_monitor"),
        patch("src.darius_ai.system.workspace_manager.focus_or_launch_cursor"),
    ):
        run_dev_mode(talk_fn=talk_mock, cooldown_secs=0.0)
        talk_mock.assert_called_once()


def test_run_trading_mode():
    """Ejecución de modo trading."""
    talk_mock = MagicMock()
    with patch("src.darius_ai.system.workspace_manager.open_url_on_monitor"):
        run_trading_mode(talk_fn=talk_mock, cooldown_secs=0.0)
        talk_mock.assert_called_once()
