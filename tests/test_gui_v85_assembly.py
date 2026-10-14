"""
test_gui_v85_assembly.py — Pruebas de Integración y Ensamblaje Cybernetic Bento v8.5
=====================================================================================
Protocolo ECC: TDD Red-Green-Refactor.
Verifica:
  1. Integración de CyberTopBar, CyberSidebar y FloatingVoiceCapsule en DariusFinal.
  2. Mapeo bidireccional de navegación en _show_page para los 6 destinos tácticos.
  3. Mapeo y sincronización de modos de audio en _set_listen_mode (PTT, NOM, AUTO, GEMINI LIVE).
  4. Despacho y formateo de texto en _on_text_submit.
  5. Alternancia de estado en toggle_mute y set_status sobre CyberTopBar.
"""

from unittest.mock import MagicMock, patch

from src.darius_ai.audio.voice_filter import (
    LISTEN_MODE_AUTO,
    LISTEN_MODE_NAME,
    LISTEN_MODE_PTT,
)


class TestGuiV85NavigationAndModes:
    """Verifica la lógica de negocio y mapeos de UI v8.5 sin depender del servidor X11/Win32."""

    def test_navigation_tab_mapping(self):
        """Verifica que los 6 destinos de CyberSidebar se asignan a las páginas correctas."""
        from src.darius_ai.gui.app import DariusFinal

        app = object.__new__(DariusFinal)
        app.tk = MagicMock()
        app._pages = {
            "dashboard": MagicMock(),
            "chat": MagicMock(),
            "workspaces": MagicMock(),
            "obsidian": MagicMock(),
            "system": MagicMock(),
        }
        app._nav_btns = {}
        app.sidebar = MagicMock()
        app.sidebar.current_tab = "inicio"
        app._open_byok_settings = MagicMock()

        # 1. 'inicio' -> 'dashboard'
        app._show_page("inicio")
        assert app.current_page == "dashboard"
        app._pages["dashboard"].grid.assert_called_with(row=0, column=0, sticky="nsew")

        # 2. 'asistente' -> 'chat'
        app._show_page("asistente")
        assert app.current_page == "chat"
        app._pages["chat"].grid.assert_called_with(row=0, column=0, sticky="nsew")

        # 3. 'automatizacion' -> 'workspaces'
        app._show_page("automatizacion")
        assert app.current_page == "workspaces"

        # 4. 'memoria' -> 'obsidian'
        app._show_page("memoria")
        assert app.current_page == "obsidian"

        # 5. 'configuracion' -> abre byok settings modal
        app._show_page("configuracion")
        app._open_byok_settings.assert_called_once()

        # 6. 'logs' -> 'system'
        app._show_page("logs")
        assert app.current_page == "system"

    def test_set_listen_mode_sync(self):
        """Verifica la normalización y sincronización de modos de escucha."""
        from src.darius_ai.gui.app import DariusFinal

        app = object.__new__(DariusFinal)
        app.tk = MagicMock()
        app._mode_btns = {}
        app.ptt_hint = None
        app.mode_pill = None
        app.talk = MagicMock()
        app.set_status = MagicMock()
        app.voice_capsule = MagicMock()

        # Modo PTT
        app.voice_capsule.current_mode = "NOM"
        app._set_listen_mode("PTT")
        assert app.listen_mode == LISTEN_MODE_PTT
        app.voice_capsule.set_mode.assert_called_with("PTT")

        # Modo AUTO
        app.voice_capsule.current_mode = "PTT"
        app._set_listen_mode("AUTO")
        assert app.listen_mode == LISTEN_MODE_AUTO
        app.voice_capsule.set_mode.assert_called_with("AUTO")

        # Modo NOM
        app.voice_capsule.current_mode = "AUTO"
        app._set_listen_mode("NOM")
        assert app.listen_mode == LISTEN_MODE_NAME
        app.voice_capsule.set_mode.assert_called_with("NOM")

    def test_set_listen_mode_gemini_live(self):
        """Verifica la activación y detención de Gemini Live desde el selector de modo."""
        from src.darius_ai.gui.app import DariusFinal

        app = object.__new__(DariusFinal)
        app.tk = MagicMock()
        app._mode_btns = {}
        app.ptt_hint = None
        app.mode_pill = None
        app.talk = MagicMock()
        app.set_status = MagicMock()
        app.voice_capsule = MagicMock()
        app.voice_capsule.current_mode = "NOM"

        mock_live_engine = MagicMock()
        mock_live_engine.is_running = False
        mock_live_engine.start_live_session.return_value = (True, "Live OK")

        with patch("src.darius_ai.core.gemini_live_engine.get_gemini_live_engine", return_value=mock_live_engine):
            app._set_listen_mode("GEMINI LIVE")
            assert app.listen_mode == "gemini_live"
            mock_live_engine.start_live_session.assert_called_once()
            app.set_status.assert_any_call("GEMINI LIVE CONECTADO", "#00F0FF")

            # Al cambiar a NOM, debe detener la sesión activa
            mock_live_engine.is_running = True
            app._set_listen_mode("NOM")
            mock_live_engine.stop_live_session.assert_called_once()

    def test_on_text_submit_processing(self):
        """Verifica que _on_text_submit procese texto de entrada correctamente."""
        from src.darius_ai.gui.app import DariusFinal

        app = object.__new__(DariusFinal)
        app.tk = MagicMock()
        app.text_input = MagicMock()
        app.text_input.get.return_value = "darius activa modo desarrollo"
        app.add_to_chat = MagicMock()
        app._append_chat_file = MagicMock()
        app.execute_command = MagicMock()

        with patch("threading.Thread") as mock_thread:
            app._on_text_submit()
            app.add_to_chat.assert_called_once()
            app.text_input.delete.assert_called_with(0, "end")
            assert any(call.kwargs.get("name") == "text-cmd" for call in mock_thread.call_args_list)

    def test_toggle_mute_state(self):
        """Verifica la conmutación de silencio y actualización visual."""
        from src.darius_ai.gui.app import DariusFinal

        app = object.__new__(DariusFinal)
        app.tk = MagicMock()
        app.is_muted = False
        app.mute_btn = MagicMock()
        app.add_to_chat = MagicMock()
        app.talk = MagicMock()
        app.set_status = MagicMock()

        # Silenciar
        app.toggle_mute()
        assert app.is_muted is True
        app.mute_btn.configure.assert_called_with(text="🔇", fg_color="#F87171", hover_color="#EF4444")
        app.set_status.assert_called_with("SILENCIADO", "#F87171")

        # Reactivar
        app.toggle_mute()
        assert app.is_muted is False
        app.talk.assert_called_once_with("Sistemas de escucha reactivados.")
        app.set_status.assert_called_with("SISTEMA LISTO", "#34D399")

    def test_voice_capsule_mic_toggle(self):
        """Verifica la respuesta al clic de micrófono en FloatingVoiceCapsule."""
        from src.darius_ai.gui.app import DariusFinal

        app = object.__new__(DariusFinal)
        app.tk = MagicMock()
        app.is_muted = False
        app.listen_mode = LISTEN_MODE_NAME
        app.set_status = MagicMock()

        # Activar
        app._on_voice_capsule_mic_toggle(True)
        assert app.is_listening is True
        app.set_status.assert_called_with("🎙 ESCUCHANDO…", "#00F0FF")

        # Desactivar
        app._on_voice_capsule_mic_toggle(False)
        assert app.is_listening is False
        app.set_status.assert_called_with("SISTEMA LISTO", "#34D399")
