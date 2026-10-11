"""
test_telemetry_bar.py — Pruebas unitarias para el componente de telemetría HUD de la GUI
"""

from unittest.mock import MagicMock, patch

from src.darius_ai.core.telemetry_tracker import AgentEvent
from src.darius_ai.gui.telemetry_bar import TelemetryFeedController


class TestTelemetryFeedController:
    def test_empty_controller_defaults(self):
        controller = TelemetryFeedController()
        assert controller.rotate_next() is None
        text = controller.get_current_display_text()
        assert "Sistema listo" in text

    def test_controller_buffers_and_rotates_events(self):
        controller = TelemetryFeedController(max_queue=5)
        controller.push_event(AgentEvent(agent_name="agent_a", message="Mensaje 1"))
        controller.push_event(AgentEvent(agent_name="agent_b", message="Mensaje 2"))

        current = controller.get_current_display_text()
        assert "agent_a" in current

        next_evt = controller.rotate_next()
        assert next_evt is not None
        assert next_evt.agent_name == "agent_b"
        assert "agent_b" in controller.get_current_display_text()

        # Wrap around back to agent_a
        next_evt = controller.rotate_next()
        assert next_evt is not None
        assert next_evt.agent_name == "agent_a"

    def test_queue_overflow_drops_oldest(self):
        controller = TelemetryFeedController(max_queue=2)
        controller.push_event(AgentEvent(agent_name="agent_1", message="1"))
        controller.push_event(AgentEvent(agent_name="agent_2", message="2"))
        controller.push_event(AgentEvent(agent_name="agent_3", message="3"))

        # Queue length is max 2, agent_1 should have been popped
        assert len(controller._events) == 2
        assert controller._events[0].agent_name == "agent_2"
        assert controller._events[1].agent_name == "agent_3"

    def test_status_icon_formatting(self):
        controller = TelemetryFeedController()

        # Success event with duration
        controller.push_event(
            AgentEvent(agent_name="agent_ok", message="Todo bien", status="success", duration_ms=142.5)
        )
        text_ok = controller.get_current_display_text()
        assert "🟢" in text_ok
        assert "142ms" in text_ok

        # Error event
        controller = TelemetryFeedController()
        controller.push_event(AgentEvent(agent_name="agent_err", message="Fallo", status="error"))
        text_err = controller.get_current_display_text()
        assert "🔴" in text_err

        # Default / intermediate status
        controller = TelemetryFeedController()
        controller.push_event(AgentEvent(agent_name="agent_run", message="En progreso", status="running"))
        text_run = controller.get_current_display_text()
        assert "⚡" in text_run

    def test_controller_sfx_toggle(self):
        controller = TelemetryFeedController()
        with patch("src.darius_ai.gui.telemetry_bar.get_sfx_engine") as mock_sfx_getter:
            mock_sfx = MagicMock()
            mock_sfx.is_enabled.return_value = True
            mock_sfx_getter.return_value = mock_sfx

            new_state = controller.toggle_sfx()
            assert new_state is False
            mock_sfx.set_enabled.assert_called_with(False)

            mock_sfx.is_enabled.return_value = False
            new_state2 = controller.toggle_sfx()
            assert new_state2 is True
            mock_sfx.set_enabled.assert_called_with(True)
