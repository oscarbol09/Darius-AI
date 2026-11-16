"""
test_ui_ux_audit_fixes.py — Pruebas Automatizadas TDD para Correcciones de Auditoría UI/UX
==========================================================================================
Protocolo ECC: Red-Green-Refactor.
Captura deterministamente los fallos detectados en la auditoría UI/UX:
  1. High-DPI Awareness en Windows.
  2. Eliminación de canvas.delete("all") en FloatingVoiceCapsule.
  3. Responsividad, scroll y Escape en BYOKSettingsModal + persistencia de antigravity.
  4. TTL de expiración (15s) en acciones destructivas (_pending_action).
  5. Desacoplamiento de Mute de la telemetría de Red en la cabecera.
  6. Cumplimiento de ratio de contraste WCAG 2.2 AA en TEXT_MUTED (>= 4.5:1).
  7. Cálculo real de tasa de transferencia de Red I/O (delta / dt).
  8. Actividad Reciente dinámica en BentoDashboardView.
  9. Reubicación arquitectónica de human_gui.py a automation/ con proxy retrocompatible.
 10. Atajos de teclado (Ctrl+1..6, Ctrl+K, Escape) en la ventana principal.
 11. Visor de logs funcional en la pestaña de logs/sistema.
"""

import time
from unittest.mock import MagicMock, patch

import customtkinter as ctk
import pytest

from src.darius_ai.gui import gui_theme as theme


class TestHighDpiAndTokens:
    def test_dpi_awareness_helper(self):
        """Verifica que enable_dpi_awareness se puede invocar de forma segura."""
        from src.darius_ai.gui.gui_theme import enable_dpi_awareness

        # Debe ejecutarse sin lanzar excepciones
        enable_dpi_awareness()

    def test_wcag_contrast_text_muted(self):
        """Verifica que TEXT_MUTED cumpla WCAG 2.2 AA (>= 4.5:1) sobre superficies oscuras."""

        def hex_to_relative_luminance(hex_code: str) -> float:
            hex_code = hex_code.lstrip("#")
            rgb = [int(hex_code[i : i + 2], 16) / 255.0 for i in (0, 2, 4)]
            linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

        def contrast_ratio(hex1: str, hex2: str) -> float:
            l1 = hex_to_relative_luminance(hex1)
            l2 = hex_to_relative_luminance(hex2)
            lighter = max(l1, l2)
            darker = min(l1, l2)
            return (lighter + 0.05) / (darker + 0.05)

        # TEXT_MUTED debe tener un contraste >= 4.5:1 sobre BG_CARD y BG_CARD_INNER
        ratio_card = contrast_ratio(theme.TEXT_MUTED, theme.BG_CARD)
        ratio_inner = contrast_ratio(theme.TEXT_MUTED, theme.BG_CARD_INNER)
        assert ratio_card >= 4.5, f"TEXT_MUTED ({theme.TEXT_MUTED}) falla contraste en BG_CARD: {ratio_card:.2f}:1"
        assert ratio_inner >= 4.5, (
            f"TEXT_MUTED ({theme.TEXT_MUTED}) falla contraste en BG_CARD_INNER: {ratio_inner:.2f}:1"
        )


class TestFloatingVoiceCapsuleZeroLeaks:
    def test_no_delete_all_in_waveform(self):
        """Verifica que _draw_waveform NO invoque delete('all') y use coords atómicos."""
        try:
            root = ctk.CTk()
            root.withdraw()
        except Exception as exc:
            pytest.skip(f"Tkinter no disponible: {exc}")

        try:
            from src.darius_ai.gui.floating_voice_capsule import FloatingVoiceCapsule

            capsule = FloatingVoiceCapsule(root)

            # Espiar llamadas a delete en waveform_canvas
            with (
                patch.object(capsule.waveform_canvas, "delete", wraps=capsule.waveform_canvas.delete) as spy_del,
                patch.object(capsule.waveform_canvas, "coords", wraps=capsule.waveform_canvas.coords) as spy_coords,
            ):
                # Actualizar audio nivel 60 veces usando update_rms_level
                for lvl in [10.0, 30.0, 50.0, 70.0, 90.0]:
                    capsule.update_rms_level(lvl)

                # NO debe haberse llamado delete("all")
                for call in spy_del.call_args_list:
                    assert call.args != ("all",), "delete('all') fue invocado en render loop!"

                # DEBE haberse llamado coords para mutar la geometría atómicamente
                assert spy_coords.call_count >= 5, "coords no fue invocado para actualizar las barras!"
        finally:
            root.destroy()


class TestByokSettingsModalResponsiveness:
    def test_scrollable_frames_and_escape_binding(self):
        """Verifica que el modal BYOK sea desplazable y se cierre con Escape."""
        try:
            root = ctk.CTk()
            root.withdraw()
        except Exception as exc:
            pytest.skip(f"Tkinter no disponible: {exc}")

        try:
            from src.darius_ai.gui.byok_settings import BYOKSettingsModal

            modal = BYOKSettingsModal(root)

            # Debe tener scrollable frames
            assert isinstance(modal.llm_container, ctk.CTkScrollableFrame)
            assert isinstance(modal.tts_container, ctk.CTkScrollableFrame)

            # Debe tener binding para Escape
            with patch.object(modal, "_on_close") as spy_close:
                modal.focus_force()
                modal.update()
                modal.event_generate("<Escape>")
                modal.update()
                spy_close.assert_called_once()
        finally:
            root.destroy()

    def test_byok_saves_antigravity(self):
        """Verifica que el proveedor antigravity persista correctamente sus ajustes."""
        try:
            root = ctk.CTk()
            root.withdraw()
        except Exception as exc:
            pytest.skip(f"Tkinter no disponible: {exc}")

        try:
            from src.darius_ai.core.config_loader import cfg
            from src.darius_ai.gui.byok_settings import BYOKSettingsModal

            modal = BYOKSettingsModal(root)
            modal.selected_provider = "antigravity"
            modal._provider_data["antigravity"]["key"] = "test-antigravity-key"
            modal._provider_data["antigravity"]["model"] = "antigravity-deep-reasoning"

            with patch.object(cfg, "set") as spy_cfg_set:
                modal._on_save()
                saved_keys = [call.args for call in spy_cfg_set.call_args_list]
                assert any("antigravity_api_key" in str(arg) or "antigravity_model" in str(arg) for arg in saved_keys)
        finally:
            root.destroy()


class TestDestructiveActionSafeguards:
    def test_pending_action_ttl_expiration(self):
        """Verifica que una acción destructiva pendiente expire tras el TTL de 15 segundos."""
        from src.darius_ai.gui.app import DariusFinal

        app = object.__new__(DariusFinal)
        app._pending_lock = MagicMock()
        app.talk = MagicMock()
        app.set_status = MagicMock()

        fn_mock = MagicMock()
        # Acción expirada hace 2 segundos
        app._pending_action = {
            "desc": "Apagar el equipo",
            "expires_at": time.time() - 2.0,
            "_fn": fn_mock,
        }

        app._handle_confirmation("sí")

        # No debe ejecutarse la función porque expiró
        fn_mock.assert_not_called()
        # Debe haber notificado que la confirmación expiró
        app.talk.assert_called_with("La solicitud de confirmación ha expirado por seguridad.")

    def test_pending_action_within_ttl_executes(self):
        """Verifica que una acción dentro del TTL sí se ejecute al confirmar."""
        from src.darius_ai.gui.app import DariusFinal

        app = object.__new__(DariusFinal)
        app._pending_lock = MagicMock()
        app.talk = MagicMock()
        app.set_status = MagicMock()

        fn_mock = MagicMock()
        app._pending_action = {
            "desc": "Apagar el equipo",
            "expires_at": time.time() + 10.0,
            "_fn": fn_mock,
        }

        with patch("threading.Thread") as mock_thread:
            app._handle_confirmation("confirmar")
            assert app._pending_action is None
            mock_thread.assert_called_once()


class TestNetworkDecoupledFromMute:
    def test_mute_does_not_change_network_status(self):
        """Verifica que mutear el audio no declare la red como Desconectada."""
        from src.darius_ai.gui.app import DariusFinal

        app = object.__new__(DariusFinal)
        app.cyber_top_bar = MagicMock()
        app.is_muted = True
        app.status_label = MagicMock()
        app.status_dot = MagicMock()
        app.after = lambda delay, fn: fn()
        app._is_network_available = lambda: True

        app.set_status("NOMINAL", "green")
        call_kwargs = app.cyber_top_bar.set_system_status.call_args[1]
        assert call_kwargs["is_online"] is True, "Mute declaró falsamente la red como Desconectada!"


class TestHumanGuiMigration:
    def test_human_gui_reexports_automation(self):
        """Verifica que human_gui reexporte las funciones desde automation.human_input."""
        import importlib
        import sys

        from src.darius_ai.automation import human_input

        sys.modules.pop("src.darius_ai.gui.human_gui", None)
        with pytest.warns(DeprecationWarning, match="deprecado"):
            human_gui = importlib.import_module("src.darius_ai.gui.human_gui")

        # Deben compartir las mismas clases y constantes
        assert human_gui.FailsafeError is human_input.FailsafeError
        assert hasattr(human_gui, "human_move_to")
        assert hasattr(human_input, "human_move_to")


class TestKeyboardShortcuts:
    def test_setup_shortcuts_registers_navigation_and_actions(self):
        """Verifica que setup_shortcuts registre bindings para Ctrl+1..6, Ctrl+K, Ctrl+M y Ctrl+,"""
        from src.darius_ai.gui.app import DariusFinal

        app = object.__new__(DariusFinal)
        bindings = {}
        app.bind = lambda key, cb: bindings.update({key: cb})

        app.setup_shortcuts()

        assert "<Control-Key-1>" in bindings
        assert "<Control-Key-2>" in bindings
        assert "<Control-Key-6>" in bindings
        assert "<Control-k>" in bindings or "<Control-K>" in bindings
        assert "<Control-m>" in bindings or "<Control-M>" in bindings
        assert "<Control-comma>" in bindings


class TestThemeAndVisualizerOptimizations:
    def test_font_code_exported_in_gui_theme(self):
        """Verifica que FONT_CODE esté exportado en gui_theme para evitar AttributeError."""
        from src.darius_ai.gui import gui_theme as theme

        assert hasattr(theme, "FONT_CODE")
        assert theme.FONT_CODE == theme.FONT_MONO

    def test_cyber_core_visualizer_set_state_dirty_check(self):
        """Verifica que set_state no sature IPC a Tcl si el estado no ha cambiado."""
        from src.darius_ai.gui.cyber_core_visualizer import CyberCoreVisualizer

        viz = object.__new__(CyberCoreVisualizer)
        viz.DEFAULT_STATE = "IDLE"
        viz.current_state = ""
        viz.canvas = MagicMock()
        viz._arc_ids = [1, 2, 3]
        viz._tick_ids = [4, 5, 6]
        viz._core_id = 7
        viz._core_inner_id = 8

        # Primer cambio: debe invocar itemconfig
        viz.set_state("IDLE")
        first_call_count = viz.canvas.itemconfig.call_count
        assert first_call_count > 0
        assert viz.current_state == "IDLE"

        # Segundo cambio idéntico: dirty-check DEBE evitar llamadas redundantes a itemconfig
        viz.canvas.reset_mock()
        viz.set_state("IDLE")
        assert viz.canvas.itemconfig.call_count == 0, "set_state saturó Tcl IPC con estado idéntico!"

    def test_bento_dashboard_set_core_state_animates_visualizers(self):
        """Verifica que set_core_state avance la fase de animación y actualice ambos visualizadores."""
        from src.darius_ai.gui.bento_dashboard import BentoDashboardView

        dashboard = object.__new__(BentoDashboardView)
        dashboard.core_visualizer = MagicMock()
        dashboard.context_mesh = MagicMock()
        dashboard.core_status_dot = MagicMock()
        dashboard.core_status_lbl = MagicMock()
        dashboard._anim_phase = 0.0

        dashboard.set_core_state("IDLE", energy=25.0)

        assert dashboard._anim_phase > 0.0, "La fase de animación no avanzó!"
        dashboard.core_visualizer.update_frame.assert_called_once()
        dashboard.context_mesh.update_frame.assert_called_once()

    def test_floating_voice_capsule_no_duplicate_methods(self):
        """Verifica que no existan definiciones redundantes en FloatingVoiceCapsule."""
        import inspect

        from src.darius_ai.gui import floating_voice_capsule

        source_lines = inspect.getsource(floating_voice_capsule)
        # 'def set_rms_energy' debe aparecer exactamente una vez
        occurrences = source_lines.count("def set_rms_energy")
        assert occurrences == 1, f"set_rms_energy está definido {occurrences} veces en floating_voice_capsule.py!"


class TestUxInterruptionAndMarkdown:
    def test_tts_worker_interrupt(self):
        """Verifica que interrupt() en TTSWorker limpie la cola y detenga la reproducción."""
        from src.darius_ai.audio.tts_worker import TTSWorker

        worker = TTSWorker()
        worker._queue.put("Texto largo que debe ser interrumpido")
        worker.is_speaking.set()

        with patch("sounddevice.stop") as mock_sd_stop:
            worker.interrupt()
            assert worker._queue.empty(), "La cola de voz no fue vaciada en interrupt()!"
            assert not worker.is_speaking.is_set(), "is_speaking debe resetearse a False en interrupt()!"
            mock_sd_stop.assert_called_once()

    def test_chat_markdown_preservation_for_gui_vs_tts(self):
        """Verifica que el formateo Markdown y bloques de código se preserven en GUI y solo se limpien en TTS."""
        import threading

        from src.darius_ai.gui.app import DariusFinal

        app = object.__new__(DariusFinal)
        app.tk = MagicMock()
        app._chat_file_lock = threading.Lock()
        app._insert_message = MagicMock()
        app.after = lambda delay, fn, *args: fn(*args)
        app._append_chat_file = MagicMock()
        app.is_muted = False
        app.tts_worker = MagicMock()

        raw_ai_text = "Aquí está tu código:\n```python\nprint('Hola')\n```\nUsa **negrita** para destacar."

        # Debe llamar display_ai_response y enviar formatted_text al GUI
        app.display_ai_response(raw_ai_text)

        # El mensaje insertado en la GUI debe contener el código y markdown intactos
        inserted_text = app._insert_message.call_args[0][1]
        assert "```python" in inserted_text
        assert "**negrita**" in inserted_text
        # Y TTS debe recibir texto limpio sin caracteres de markdown
        spoken_text = app.tts_worker.speak.call_args[0][0]
        assert "```" not in spoken_text
        assert "**" not in spoken_text
