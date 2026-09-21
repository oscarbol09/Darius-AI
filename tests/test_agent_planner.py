"""
test_agent_planner.py — Pruebas unitarias para el planificador agéntico multi-paso
"""

from unittest.mock import MagicMock, patch

from agent_planner import AgentPlannerEngine


def test_planner_create_plan_mocked():
    """Valida la descomposición de una meta en pasos JSON."""
    planner = AgentPlannerEngine()

    mock_llm_json = """
    {
      "goal": "captura pantalla y anota en diario",
      "steps": [
        {"tool": "screen_vision", "params": {"action": "analyze"}},
        {"tool": "append_daily_note", "params": {"entry": "{{PREV}}"}}
      ]
    }
    """
    with patch("agent_planner.get_ai_response", return_value=(mock_llm_json, "Gemini")):
        steps = planner.create_plan("captura pantalla y anota en diario")
        assert len(steps) == 2
        assert steps[0]["tool"] == "screen_vision"
        assert steps[1]["tool"] == "append_daily_note"


def test_planner_execute_step_with_context_piping():
    """Valida la ejecución de un paso y la inyección del resultado previo."""
    planner = AgentPlannerEngine()

    with patch("obsidian_brain.brain.append_daily_note", return_value=MagicMock(name="2026-09-21.md")) as mock_note:
        ok, out = planner.execute_step(
            tool="append_daily_note",
            params={"entry": "{{PREV}}"},
            prev_result="Error detectado en línea 100",
        )
        assert ok is True
        mock_note.assert_called_once_with(entry="Error detectado en línea 100")


def test_plan_and_execute_full_flow_mocked():
    """Valida la orquestación completa de un plan multi-paso."""
    planner = AgentPlannerEngine()

    mock_steps = [
        {"tool": "speak", "params": {"text": "Iniciando proceso"}},
        {"tool": "speak", "params": {"text": "Proceso finalizado"}},
    ]

    with patch.object(planner, "create_plan", return_value=mock_steps):
        spoken = []
        statuses = []

        res = planner.plan_and_execute(
            goal="Hacer dos anuncios",
            speak_fn=spoken.append,
            status_fn=lambda text, color: statuses.append(text),
        )

        assert res["ok"] is True
        assert res["steps_count"] == 2
        assert res["success_count"] == 2
        assert len(statuses) > 0
        assert len(spoken) == 1
        assert "Proceso finalizado" in spoken[0]
