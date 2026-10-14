"""Pruebas unitarias para AntigravityAgentBridge.

Protocolo ECC: TDD Red-Green-Refactor.
Verifica la inicialización del puente, capacidades del agente,
ejecución de consultas directas, ejecución de tareas de desarrollo
y formateo con persona butler de Darius.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.darius_ai.core.antigravity_bridge import (
    AntigravityAgentBridge,
    AntigravityResult,
    get_antigravity_bridge,
)


class TestAntigravityAgentBridgeUnit:
    def test_bridge_init_and_availability(self):
        bridge = AntigravityAgentBridge()
        assert bridge is not None
        # google-antigravity fue instalado en el entorno, debe estar disponible
        assert bridge.is_available() is True

    def test_singleton_getter(self):
        b1 = get_antigravity_bridge()
        b2 = get_antigravity_bridge()
        assert b1 is b2

    def test_custom_system_prompt_builder(self):
        bridge = AntigravityAgentBridge()
        prompt = bridge.build_system_instructions("señor")
        assert "Antigravity" in prompt
        assert "señor" in prompt
        assert "DARIUS" in prompt

    @pytest.mark.asyncio
    async def test_ask_agent_async_with_mock(self):
        bridge = AntigravityAgentBridge()

        # Mockeamos el runtime de Agent para una prueba hermética y determinista
        mock_response = MagicMock()
        mock_response.text = "He verificado el estado del repositorio, señor. Todo opera nominalmente."
        mock_response.tool_calls = [MagicMock(name="run_command")]

        with patch.object(bridge, "_execute_agent_chat", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = AntigravityResult(
                success=True,
                response_text=mock_response.text,
                tool_calls=["run_command: git status"],
                execution_time_seconds=0.45,
            )

            res = await bridge.ask_agent_async("Revisa el estado de git")
            assert res.success is True
            assert "repositorio" in res.response_text
            assert len(res.tool_calls) == 1
            assert "git status" in res.tool_calls[0]

    def test_ask_agent_sync_wrapper(self):
        bridge = AntigravityAgentBridge()
        with patch.object(bridge, "ask_agent_async", new_callable=AsyncMock) as mock_async:
            mock_async.return_value = AntigravityResult(
                success=True,
                response_text="Sistemas en línea, señor.",
                tool_calls=[],
                execution_time_seconds=0.1,
            )
            res = bridge.ask_agent("Hola Antigravity")
            assert res.success is True
            assert "Sistemas en línea" in res.response_text

    def test_execute_development_instruction(self):
        bridge = AntigravityAgentBridge()
        with patch.object(bridge, "ask_agent") as mock_ask:
            mock_ask.return_value = AntigravityResult(
                success=True,
                response_text="He ejecutado las pruebas con pytest. 42 tests en verde.",
                tool_calls=["run_command: pytest"],
                execution_time_seconds=1.2,
            )
            success, speech = bridge.execute_development_instruction("Corre los tests de pytest")
            assert success is True
            assert "pytest" in speech

    def test_error_handling_graceful(self):
        bridge = AntigravityAgentBridge()
        with patch.object(bridge, "_execute_agent_chat", side_effect=RuntimeError("Connection timeout")):
            res = bridge.ask_agent("Prueba fallo")
            assert res.success is False
            assert "Error" in res.response_text or "fallo" in res.response_text.lower()
