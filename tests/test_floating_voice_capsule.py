"""
test_floating_voice_capsule.py — Suite de pruebas para la Cápsula Flotante de Activación por Voz
================================================================================================
Protocolo ECC: TDD Red-Green-Refactor.
Valida:
  1. Constantes y modos de operación de voz (PTT, NOM, AUTO, GEMINI LIVE).
  2. Inicialización del dock flotante FloatingVoiceCapsule y valores predeterminados.
  3. Estado de activación del micrófono (halo brillante y color del botón).
  4. Entrada de texto y callback al enviar (`on_submit_callback`).
  5. Conmutación de modos rápidos y despacho de callback de modo.
  6. Indicador de energía RMS / forma de onda y animación de halo pulsante.
  7. Tolerancia a fallos ante excepciones en callbacks de usuario.
"""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock

import customtkinter as ctk
import pytest

from src.darius_ai.gui.floating_voice_capsule import (
    CAPSULE_BG,
    CAPSULE_BORDER,
    HALO_ACTIVE_COLOR,
    VOICE_MODES,
    FloatingVoiceCapsule,
)


class TestFloatingVoiceCapsuleConstants:
    """Verifica tokens y constantes de la cápsula flotante."""

    def test_voice_modes(self):
        assert "PTT" in VOICE_MODES
        assert "NOM" in VOICE_MODES
        assert "AUTO" in VOICE_MODES
        assert "GEMINI LIVE" in VOICE_MODES
        assert len(VOICE_MODES) == 4

    def test_color_tokens(self):
        assert CAPSULE_BG in ("#0B1220", "#070B14")
        assert CAPSULE_BORDER in ("#1E293B", "#233044")
        assert HALO_ACTIVE_COLOR in ("#00F0FF", "#38BDF8")


class TestFloatingVoiceCapsuleWidget:
    """Verifica el widget FloatingVoiceCapsule en entorno CustomTkinter."""

    @pytest.fixture
    def capsule_fixture(self):
        try:
            root = ctk.CTk()
            root.withdraw()
            mock_submit = MagicMock()
            mock_mode = MagicMock()
            mock_mic_toggle = MagicMock()
            capsule = FloatingVoiceCapsule(
                root,
                on_submit_callback=mock_submit,
                on_mode_change=mock_mode,
                on_mic_toggle=mock_mic_toggle,
            )
        except Exception as exc:
            pytest.skip(f"Tkinter/Tcl no disponible en este entorno: {exc}")
        yield capsule, mock_submit, mock_mode, mock_mic_toggle, root
        with contextlib.suppress(Exception):
            capsule.destroy()
            root.destroy()

    def test_initialization(self, capsule_fixture):
        capsule, _, _, _, _ = capsule_fixture
        assert capsule is not None
        assert isinstance(capsule, ctk.CTkFrame)
        assert capsule.is_mic_active is False
        assert capsule.current_mode in VOICE_MODES
        assert hasattr(capsule, "mic_button")
        assert hasattr(capsule, "entry")
        assert hasattr(capsule, "mode_buttons")
        assert hasattr(capsule, "waveform_canvas")
        assert len(capsule.mode_buttons) == 4

    def test_initialization_with_custom_default_mode(self):
        try:
            root = ctk.CTk()
            root.withdraw()
            capsule1 = FloatingVoiceCapsule(root, default_mode="AUTO")
            assert capsule1.current_mode == "AUTO"

            capsule2 = FloatingVoiceCapsule(root, default_mode="INVALID")
            assert capsule2.current_mode == "NOM"
        except Exception as exc:
            pytest.skip(f"Tkinter no disponible: {exc}")
        finally:
            with contextlib.suppress(Exception):
                capsule1.destroy()
                capsule2.destroy()
                root.destroy()

    def test_set_mic_active(self, capsule_fixture):
        capsule, _, _, _, _ = capsule_fixture
        capsule.set_mic_active(True)
        assert capsule.is_mic_active is True
        assert capsule.halo_color == HALO_ACTIVE_COLOR

        capsule.set_mic_active(False)
        assert capsule.is_mic_active is False
        assert capsule.halo_color != HALO_ACTIVE_COLOR

    def test_toggle_mic(self, capsule_fixture):
        capsule, _, _, mock_toggle, _ = capsule_fixture
        # Inicialmente inactivo
        capsule.toggle_mic()
        assert capsule.is_mic_active is True
        mock_toggle.assert_called_once_with(True)

        capsule.toggle_mic()
        assert capsule.is_mic_active is False
        assert mock_toggle.call_count == 2

    def test_toggle_mic_exception_handled(self, capsule_fixture):
        capsule, _, _, mock_toggle, _ = capsule_fixture
        mock_toggle.side_effect = RuntimeError("Mic toggle error")
        # No debe propagar la excepción
        capsule.toggle_mic()
        assert capsule.is_mic_active is True

    def test_set_and_get_prompt_text(self, capsule_fixture):
        capsule, _, _, _, _ = capsule_fixture
        capsule.set_prompt_text("Hola Darius, estado del sistema")
        assert capsule.get_prompt_text() == "Hola Darius, estado del sistema"

        capsule.clear_prompt()
        assert capsule.get_prompt_text() == ""

    def test_submit_callback_on_return(self, capsule_fixture):
        capsule, mock_submit, _, _, _ = capsule_fixture
        capsule.set_prompt_text("darius reporte sismico")
        capsule._on_submit()
        mock_submit.assert_called_once_with("darius reporte sismico")
        # El campo debe limpiarse tras el envío
        assert capsule.get_prompt_text() == ""

    def test_submit_ignores_empty_text(self, capsule_fixture):
        capsule, mock_submit, _, _, _ = capsule_fixture
        capsule.set_prompt_text("   ")
        capsule._on_submit()
        mock_submit.assert_not_called()

    def test_submit_callback_exception_handled(self, capsule_fixture):
        capsule, mock_submit, _, _, _ = capsule_fixture
        mock_submit.side_effect = RuntimeError("Submit callback error")
        capsule.set_prompt_text("darius diagnostico")
        capsule._on_submit()
        # Debe haberse limpiado el prompt y no crashear
        assert capsule.get_prompt_text() == ""

    def test_set_mode_switches_active_mode(self, capsule_fixture):
        capsule, _, mock_mode, _, _ = capsule_fixture
        capsule.set_mode("GEMINI LIVE")
        assert capsule.current_mode == "GEMINI LIVE"
        mock_mode.assert_called_once_with("GEMINI LIVE")

        # Probar modo PTT
        mock_mode.reset_mock()
        capsule.set_mode("PTT")
        assert capsule.current_mode == "PTT"
        mock_mode.assert_called_once_with("PTT")

    def test_set_mode_exception_handled(self, capsule_fixture):
        capsule, _, mock_mode, _, _ = capsule_fixture
        mock_mode.side_effect = RuntimeError("Mode change error")
        capsule.set_mode("AUTO")
        assert capsule.current_mode == "AUTO"

    def test_set_invalid_mode_ignored(self, capsule_fixture):
        capsule, _, mock_mode, _, _ = capsule_fixture
        original_mode = capsule.current_mode
        capsule.set_mode("MODO_INVALIDO")
        assert capsule.current_mode == original_mode
        mock_mode.assert_not_called()

    def test_set_rms_energy_clamps_bounds(self, capsule_fixture):
        capsule, _, _, _, _ = capsule_fixture
        capsule.set_rms_energy(50.0)
        assert capsule.current_rms == 50.0

        capsule.set_rms_energy(150.0)
        assert capsule.current_rms == 100.0

        capsule.set_rms_energy(-20.0)
        assert capsule.current_rms == 0.0

    def test_pulse_halo_step(self, capsule_fixture):
        capsule, _, _, _, _ = capsule_fixture
        # Inactivo: step no debe fallar
        capsule._pulse_step()
        # Activo: step debe alternar o actualizar fase
        capsule.set_mic_active(True)
        initial_phase = capsule._pulse_phase
        capsule._pulse_step()
        assert capsule._pulse_phase != initial_phase

    def test_stop_pulse_animation_when_destroyed(self, capsule_fixture):
        capsule, _, _, _, _ = capsule_fixture
        capsule.set_mic_active(True)
        assert capsule._pulse_timer_id is not None
        capsule._stop_pulse_animation()
        assert capsule._pulse_timer_id is None
