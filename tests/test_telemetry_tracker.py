"""
test_telemetry_tracker.py — Pruebas unitarias para el rastreador de telemetría y eventos agénticos
"""

import time
from unittest.mock import MagicMock

import pytest

from src.darius_ai.core.telemetry_tracker import (
    AgentEvent,
    TelemetryTracker,
    get_telemetry_tracker,
    trace_step,
)


class TestTelemetryTracker:
    @pytest.fixture
    def tracker(self):
        return TelemetryTracker(max_history=10)

    def test_push_and_retrieve_events(self, tracker):
        tracker.push_event("research_agent", "Buscando en Exa API...", status="running")
        tracker.push_event("obsidian_agent", "Guardando dossier...", status="success", duration_ms=45.2)

        events = tracker.get_recent_events()
        assert len(events) == 2
        assert events[0].agent_name == "research_agent"
        assert events[1].agent_name == "obsidian_agent"
        assert events[1].duration_ms == 45.2

    def test_listener_notification(self, tracker):
        mock_listener = MagicMock()
        tracker.add_listener(mock_listener)

        tracker.push_event("vision_agent", "Analizando pantalla", status="running")
        assert mock_listener.called
        event_arg = mock_listener.call_args[0][0]
        assert isinstance(event_arg, AgentEvent)
        assert event_arg.agent_name == "vision_agent"

    def test_max_history_limit(self, tracker):
        for i in range(15):
            tracker.push_event("agent", f"Paso {i}")
        events = tracker.get_recent_events()
        assert len(events) == 10
        assert events[-1].message == "Paso 14"

    def test_trace_step_decorator(self, tracker):
        @trace_step("calc_agent", "suma_pesada", tracker=tracker)
        def my_function(a, b):
            time.sleep(0.01)
            return a + b

        res = my_function(3, 4)
        assert res == 7
        events = tracker.get_recent_events()
        assert len(events) == 2  # Inicio (running) y Final (success)
        assert events[0].status == "running"
        assert events[1].status == "success"
        assert events[1].duration_ms >= 5.0


class TestSingletonTracker:
    def test_get_telemetry_tracker_singleton(self):
        t1 = get_telemetry_tracker()
        t2 = get_telemetry_tracker()
        assert t1 is t2
