"""Tests unitarios herméticos para los handlers y flujo de comandos de DariusFinal (app.py)."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from src.darius_ai.gui.app import DariusFinal


@pytest.fixture
def app_stub():
    """Crea una instancia desacoplada de DariusFinal sin levantar ventana Tkinter."""
    app = object.__new__(DariusFinal)
    app.running = True
    app.is_listening = False
    app.waiting_for_command = False
    app.is_muted = False
    app.installed_apps = {"notepad": "C:\\Windows\\notepad.exe"}
    app._is_thinking = False
    app._pending_action = None
    app._pending_lock = threading.RLock()
    app._chat_file_lock = threading.Lock()
    app._history_lock = threading.Lock()
    app.listen_mode = "NOMBRE"
    app.conversation_history = []
    app.tts_worker = MagicMock()
    app.talk = MagicMock()
    app.set_status = MagicMock()
    app.add_to_chat = MagicMock()
    app.display_ai_response = MagicMock()
    app.reset_conversation = MagicMock()
    app.after = MagicMock()
    app.kill_process = MagicMock()
    app.find_app = MagicMock(return_value="")
    app.tk = MagicMock()
    return app


def test_execute_command_routes_local_handlers(app_stub):
    app_stub.execute_command("darius qué hora es")
    app_stub.talk.assert_called()
    assert "Son las" in app_stub.talk.call_args[0][0]

    app_stub.talk.reset_mock()
    app_stub.execute_command("qué fecha es hoy")
    assert "Hoy es" in app_stub.talk.call_args[0][0]

    app_stub.execute_command("nueva conversación")
    app_stub.reset_conversation.assert_called_once()


def test_execute_command_empty_or_name_only_noop(app_stub):
    app_stub.execute_command("   ")
    app_stub.talk.assert_not_called()


def test_volume_and_status_commands(app_stub):
    with (
        patch("src.darius_ai.gui.app.volume_up") as mock_up,
        patch("src.darius_ai.gui.app.volume_down") as mock_down,
        patch("src.darius_ai.gui.app.volume_mute") as mock_mute,
    ):
        app_stub._cmd_vol_up("subir volumen")
        mock_up.assert_called_once()
        app_stub._cmd_vol_down("bajar volumen")
        mock_down.assert_called_once()
        app_stub._cmd_vol_mute("silenciar")
        mock_mute.assert_called_once()

    app_stub._cmd_estado("estado del sistema")
    assert "1 aplicaciones" in app_stub.talk.call_args[0][0]


def test_obsidian_commands_diary_memory_and_search(app_stub):
    app_stub._cmd_diario("anota en mi diario")
    assert "¿Qué deseas" in app_stub.talk.call_args[0][0]

    app_stub._cmd_diario("anota en mi diario hoy desplegué ci")
    assert "Anotado en tu diario" in app_stub.talk.call_args[0][0]

    app_stub._cmd_memoria("recuerda")
    assert "¿Qué información" in app_stub.talk.call_args[0][0]

    app_stub._cmd_memoria("recuerda que pytest usa conftest aislado")
    assert "Guardado en tu memoria" in app_stub.talk.call_args[0][0]

    app_stub._cmd_buscar_notas("busca en mis notas conftest")
    assert "Encontré en tus notas" in app_stub.talk.call_args[0][0]

    app_stub._cmd_buscar_notas("busca en mis notas palabrainexistente123")
    assert "No encontré notas" in app_stub.talk.call_args[0][0]


def test_web_search_and_open_app_commands(app_stub):
    with patch("src.darius_ai.gui.app.webbrowser.open") as mock_open:
        app_stub._cmd_buscar("busca python pytest")
        mock_open.assert_called_once()
        assert "google.com/search" in mock_open.call_args[0][0]

    app_stub._cmd_buscar("busca")
    assert "¿Qué quieres que busque?" in app_stub.talk.call_args[0][0]

    with patch("src.darius_ai.gui.app.wincmd_launch", return_value="Bloc de notas"):
        app_stub._cmd_abrir("abre bloc")
        assert "Abriendo Bloc de notas" in app_stub.talk.call_args[0][0]

    with (
        patch("src.darius_ai.gui.app.wincmd_launch", return_value=None),
        patch("src.darius_ai.gui.app.os.startfile", create=True) as mock_start,
    ):
        app_stub.find_app.return_value = "C:\\Fake\\app.exe"
        app_stub._open_app("fakeapp")
        mock_start.assert_called_once_with("C:\\Fake\\app.exe")

    with patch("src.darius_ai.gui.app.wincmd_launch", return_value=None):
        app_stub.find_app.return_value = ""
        app_stub._open_app("inexistente")
        assert "No encontré inexistente" in app_stub.talk.call_args[0][0]


def test_confirmation_lifecycle_confirm_cancel_timeout_and_detener(app_stub):
    app_stub._cmd_apagar_pc("apagar pc")
    assert app_stub._pending_action is not None
    assert "confirmar" in app_stub.talk.call_args[0][0]

    # Cancelar acción pendiente
    app_stub._handle_confirmation("cancelar")
    assert app_stub._pending_action is None
    assert "cancelada" in app_stub.talk.call_args[0][0].lower()

    # Expirar acción pendiente
    app_stub._cmd_reiniciar_pc("reiniciar pc")
    app_stub._pending_action["expires_at"] = time.time() - 5.0
    app_stub._check_confirmation_timeout()
    assert app_stub._pending_action is None

    # Confirmar con expiración detectada
    app_stub._pending_action = {"desc": "Test", "expires_at": time.time() - 1.0}
    app_stub._handle_confirmation("confirmar")
    assert "expirado" in app_stub.talk.call_args[0][0]

    # Confirmar sin acción pendiente y texto irreconocible
    app_stub._handle_confirmation("confirmar")
    assert "No hay ninguna acción" in app_stub.talk.call_args[0][0]
    app_stub._handle_confirmation("tal vez")
    assert "No entendí" in app_stub.talk.call_args[0][0]

    # Detener limpia estado y corta TTS
    app_stub._pending_action = {"desc": "x"}
    with patch("src.darius_ai.automation.human_input.gui.abort"):
        app_stub._cmd_detener("detente")
    app_stub.tts_worker.interrupt.assert_called_once()
    assert app_stub._pending_action is None


def test_format_output_for_tts_and_ask_gemini(app_stub):
    assert "completado" in app_stub._format_output_for_tts("---\n===", "Ping")
    assert app_stub._format_output_for_tts("OK", "Ping") == "Ping: OK"
    assert "más información en pantalla" in app_stub._format_output_for_tts("1\n2\n3\n4\n5", "Lista")

    with patch("src.darius_ai.gui.app.get_ai_response", return_value=("Todo nominal.", "Gemini")):
        app_stub.ask_gemini("¿Cómo estás?")
        app_stub.display_ai_response.assert_called_once_with("Todo nominal.")
        assert len(app_stub.conversation_history) == 2

    with patch("src.darius_ai.gui.app.get_ai_response", return_value=("", "Gemini")):
        app_stub.ask_gemini("Vacío")
        assert "No obtuve respuesta" in app_stub.talk.call_args[0][0]

    with patch("src.darius_ai.gui.app.get_ai_response", side_effect=RuntimeError("network")):
        app_stub.ask_gemini("Error")
        assert "Ocurrió un error" in app_stub.talk.call_args[0][0]


def test_play_on_youtube_and_ver_monitores(app_stub):
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"videoId":"dQw4w9WgXcQ"}'
    mock_resp.__enter__.return_value = mock_resp

    with (
        patch("urllib.request.urlopen", return_value=mock_resp),
        patch("src.darius_ai.gui.app.webbrowser.open") as mock_open,
    ):
        app_stub.play_on_youtube("synthwave")
        mock_open.assert_called_once_with("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    with patch("src.darius_ai.gui.app.get_monitor_rects", return_value=[(0, 0, 1920, 1080)]):
        app_stub._cmd_ver_monitores("ver monitores")
        assert "1 pantallas" in app_stub.talk.call_args[0][0]


def test_app_system_and_agent_command_dispatchers(app_stub):
    class ImmediateThread:
        def __init__(self, target=None, args=(), kwargs=None, **_rest):
            self._target = target
            self._args = args
            self._kwargs = kwargs or {}

        def start(self):
            if self._target:
                self._target(*self._args, **self._kwargs)

    with (
        patch("src.darius_ai.gui.app.threading.Thread", ImmediateThread),
        patch("src.darius_ai.gui.app.wincmd_resolve_action", return_value=None),
        patch("src.darius_ai.core.agentic_bridge.bridge.flush_dns", return_value=(True, "OK")),
        patch("src.darius_ai.core.agentic_bridge.bridge.execute_gh", return_value=(True, "PR #1")),
        patch("src.darius_ai.core.agentic_bridge.bridge.execute_git", return_value=(True, "M a.py")),
        patch("src.darius_ai.core.agentic_bridge.bridge.get_top_processes", return_value=(True, "python")),
    ):
        app_stub._cmd_flush_dns("limpiar dns")
        app_stub._cmd_gh_prs("ver prs")
        app_stub._cmd_git_status("estado git")
        app_stub._cmd_top_processes("top procesos")
        assert app_stub.talk.call_count >= 4

    with (
        patch("src.darius_ai.gui.app.threading.Thread", ImmediateThread),
        patch("src.darius_ai.gui.app.wincmd_resolve_action", return_value={"desc": "Ping", "action": {}}),
        patch("src.darius_ai.gui.app.wincmd_run_action", return_value=(True, "Reply from 1.1.1.1")),
    ):
        app_stub._cmd_accion("ping google")
        assert "Ping: Reply from 1.1.1.1" in app_stub.talk.call_args[0][0]

    with (
        patch("src.darius_ai.gui.app.threading.Thread", ImmediateThread),
        patch("src.darius_ai.gui.app.run_darius_welcome_protocol") as mock_prot,
        patch("src.darius_ai.gui.app.run_dev_mode") as mock_dev,
        patch("src.darius_ai.gui.app.run_trading_mode") as mock_trd,
        patch("src.darius_ai.gui.app.focus_or_launch_cursor") as mock_cur,
    ):
        app_stub._cmd_darius_protocol("protocolo darius")
        app_stub._cmd_workspace_dev("modo dev")
        app_stub._cmd_workspace_trading("modo trading")
        app_stub._cmd_focus_cursor("enfoca cursor")
        mock_prot.assert_called_once()
        mock_dev.assert_called_once()
        mock_trd.assert_called_once()
        mock_cur.assert_called_once()


def test_app_network_logs_and_scrape_handlers(app_stub, tmp_path):
    import socket

    app_stub._cached_network_status = None
    with patch("src.darius_ai.gui.app.socket.create_connection", side_effect=OSError("offline")):
        assert app_stub._is_network_available() is False
        # Cache hit dentro de 5s
        assert app_stub._is_network_available() is False

    app_stub._cached_network_status = None
    fake_sock = MagicMock()
    with patch("src.darius_ai.gui.app.socket.create_connection", return_value=fake_sock):
        assert app_stub._is_network_available() is True
        fake_sock.close.assert_called_once()
    assert socket is not None

    app_stub.logs_textbox = MagicMock()
    app_stub._refresh_logs_display()
    app_stub.logs_textbox.insert.assert_called_once()

    app_stub.chat_box = MagicMock()
    app_stub._reset_mock = None
    with patch.object(app_stub, "_insert_message", create=True):
        app_stub.conversation_history = [{"role": "user", "content": "hola"}]
        app_stub._cmd_cerrar("adios")
        app_stub.after.assert_called()


def test_app_human_click_scrape_web_vol_mute_and_project_roots(app_stub, tmp_path):
    class ImmediateThread:
        def __init__(self, target=None, **_rest):
            self._target = target

        def start(self):
            if self._target:
                self._target()

    with (
        patch("src.darius_ai.gui.app.threading.Thread", ImmediateThread),
        patch("src.darius_ai.gui.app.time.sleep"),
        patch("src.darius_ai.automation.human_input.gui") as mock_gui,
    ):
        mock_gui.scrape_web_content.return_value = {
            "success": True,
            "title": "Ejemplo",
            "content": "Texto limpio",
        }
        app_stub._cmd_human_click("haz doble clic derecho")
        mock_gui.human_click.assert_called_once_with(button="right", double=True)

        with patch.object(app_stub, "ask_gemini") as mock_ask:
            app_stub._cmd_scrape_web("analiza la pagina https://example.com")
            mock_ask.assert_called_once()
            assert "Ejemplo" in mock_ask.call_args[0][0]

    with patch("src.darius_ai.gui.app.volume_mute") as mock_mute:
        app_stub._cmd_vol_mute()
        mock_mute.assert_called_once()

    from src.darius_ai.core import ai_client, config_loader

    proj_dir = tmp_path / "custom_repo"
    proj_dir.mkdir()
    (proj_dir / "README.md").write_text("# DemoRepo", encoding="utf-8")
    with config_loader.cfg._lock:
        config_loader.cfg._data["project_roots"] = [str(tmp_path)]
    ctx = ai_client._get_local_project_context("revisa custom_repo por favor")
    assert "DemoRepo" in ctx


def test_confirmation_negation_and_disable_tools_and_idempotent_start(app_stub):
    """Verifica negaciones en confirmación, enable_tools=False y start_system idempotente."""
    import time

    from src.darius_ai.core import ai_client

    # "no, cancelar sesion" o "no, imposible" debe cancelar, NUNCA ejecutar
    executed = []
    app_stub._pending_action = {
        "desc": "Apagar equipo",
        "expires_at": time.time() + 15.0,
        "_fn": lambda: executed.append(True),
    }
    app_stub._handle_confirmation("no, cancelar sesion")
    assert executed == []
    assert app_stub._pending_action is None
    assert "cancelada" in app_stub.talk.call_args[0][0].lower()

    # _resolve_agentic_tool_loop con enable_tools=False neutraliza etiquetas [ACTION: ...] sin ejecutar
    with patch("src.darius_ai.core.agentic_bridge.bridge.parse_and_execute_tool") as mock_exec:
        clean_text, prov = ai_client._resolve_agentic_tool_loop(
            "Resumen listo [ACTION: execute_powershell(calc.exe)]",
            "Gemini",
            MagicMock(),
            "Resume web",
            enable_tools=False,
        )
        mock_exec.assert_not_called()
        assert "[ACTION:" not in clean_text
        assert prov == "Gemini"

    # start_system es idempotente y no lanza hilos duplicados
    app_stub._voice_loop_started = False
    with patch("src.darius_ai.gui.app.threading.Thread") as mock_thread:
        app_stub.start_system()
        first_count = mock_thread.call_count
        app_stub.start_system()
        assert mock_thread.call_count == first_count
