"""
test_agent_planner.py — Pruebas unitarias para el planificador agéntico multi-paso
"""

from unittest.mock import MagicMock, patch

from src.darius_ai.core.agent_planner import AgentPlannerEngine


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
    with patch("src.darius_ai.core.agent_planner.get_ai_response", return_value=(mock_llm_json, "Gemini")):
        steps = planner.create_plan("captura pantalla y anota en diario")
        assert len(steps) == 2
        assert steps[0]["tool"] == "screen_vision"
        assert steps[1]["tool"] == "append_daily_note"


def test_planner_heuristic_fallback():
    """Valida que si el LLM falla o devuelve contenido no parseable, se genera un plan fallback."""
    planner = AgentPlannerEngine()
    with patch("src.darius_ai.core.agent_planner.get_ai_response", side_effect=RuntimeError("API offline")):
        steps = planner.create_plan("meta simple")
        assert len(steps) == 1
        assert steps[0]["tool"] == "speak"
        assert "meta simple" in steps[0]["params"]["text"]


def test_planner_execute_step_with_context_piping():
    """Valida la ejecución de un paso y la inyección del resultado previo."""
    planner = AgentPlannerEngine()

    with patch(
        "src.darius_ai.core.obsidian_brain.brain.append_daily_note", return_value=MagicMock(name="2026-09-21.md")
    ) as mock_note:
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


def test_planner_execute_step_target_dossier():
    """Valida la ejecución de la herramienta target_dossier dentro del planificador."""
    planner = AgentPlannerEngine()

    mock_dossier = MagicMock()
    mock_dossier.target_name = "Test Target"
    mock_dossier.to_speech_summary.return_value = "Dossier de Test Target listo."

    with patch("src.darius_ai.core.target_dossier.get_dossier_engine") as mock_engine_getter:
        mock_engine = MagicMock()
        mock_engine.synthesize_dossier.return_value = mock_dossier
        mock_engine.save_to_obsidian.return_value = "Darius/Dossiers/Person/Test_Target.md"
        mock_engine_getter.return_value = mock_engine

        ok, out = planner.execute_step(
            tool="target_dossier",
            params={"target_name": "Test Target", "category": "person"},
            prev_result="Investigación previa",
        )

        assert ok is True
        assert "Dossier de Test Target listo" in out
        mock_engine.synthesize_dossier.assert_called_once()
        mock_engine.save_to_obsidian.assert_called_once_with(mock_dossier)


def test_planner_execute_step_unknown_tool():
    """Valida que una herramienta inexistente reporte fallo sin explotar."""
    planner = AgentPlannerEngine()
    ok, out = planner.execute_step(tool="herramienta_fantasma", params={})
    assert ok is False
    assert "Herramienta desconocida" in out


def test_planner_execute_step_open_app():
    """Valida la ejecución del paso open_app."""
    planner = AgentPlannerEngine()
    with patch("src.darius_ai.system.windows_commands.resolve_and_launch", return_value="Notepad") as mock_launch:
        ok, out = planner.execute_step(tool="open_app", params={"app_name": "bloc de notas"})
        assert ok is True
        assert "Notepad" in out
        mock_launch.assert_called_once_with("bloc de notas")


def test_planner_execute_step_save_obsidian_memory():
    """Valida guardar memoria en Obsidian."""
    planner = AgentPlannerEngine()
    mock_path = MagicMock()
    mock_path.name = "Nota.md"
    with patch("src.darius_ai.core.obsidian_brain.brain.save_memory", return_value=mock_path) as mock_save:
        ok, out = planner.execute_step(
            tool="save_obsidian_memory",
            params={"title": "Prueba", "content": "{{PREV}}"},
            prev_result="Contenido previo",
        )
        assert ok is True
        assert "Nota.md" in out
        mock_save.assert_called_once_with(title="Prueba", content="Contenido previo")


def test_planner_execute_step_screen_vision_variants():
    """Valida las variantes de screen_vision (error, ocr, analyze)."""
    planner = AgentPlannerEngine()
    with patch("src.darius_ai.core.screen_vision.vision_engine") as mock_vision:
        mock_vision.analyze_screen_error.return_value = "Error detectado"
        mock_vision.read_screen_text.return_value = "Texto leído"
        mock_vision.analyze_screen.return_value = "Ventana activa"

        ok1, out1 = planner.execute_step(tool="screen_vision", params={"action": "error"})
        assert ok1 is True and out1 == "Error detectado"

        ok2, out2 = planner.execute_step(tool="screen_vision", params={"action": "ocr"})
        assert ok2 is True and out2 == "Texto leído"

        ok3, out3 = planner.execute_step(tool="screen_vision", params={"action": "analyze", "prompt": "test"})
        assert ok3 is True and out3 == "Ventana activa"


def test_planner_execute_step_human_gui():
    """Valida las acciones de human_gui (type, hotkey, click)."""
    planner = AgentPlannerEngine()
    with patch("src.darius_ai.gui.human_gui.gui") as mock_gui:
        ok1, out1 = planner.execute_step(tool="human_gui", params={"action": "type", "text": "hola"})
        assert ok1 is True
        mock_gui.human_type.assert_called_once_with("hola")

        ok2, out2 = planner.execute_step(tool="human_gui", params={"action": "hotkey", "keys": "ctrl+c"})
        assert ok2 is True
        mock_gui.human_hotkey.assert_called_once_with("ctrl+c")

        ok3, out3 = planner.execute_step(tool="human_gui", params={"action": "click"})
        assert ok3 is True
        mock_gui.human_click.assert_called_once()
