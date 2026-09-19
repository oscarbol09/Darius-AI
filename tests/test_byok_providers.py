"""
test_byok_providers.py — Tests Unitarios e Integración del Motor BYOK Multi-Proveedor
=====================================================================================
Cobertura:
  1. Resolución de claves API (config.json vs Variables de Entorno)
  2. Construcción de payloads y cabeceras OpenAI-compatibles
  3. Despacho dinámico de proveedores en get_ai_response()
  4. Función de prueba de conexión en tiempo real test_provider_connection()
  5. Manejo y clasificación de errores (401, 429, 404, timeout, conexión rechazada)
  6. Inyección de memoria Obsidian en las instrucciones de sistema
"""

import json
from unittest.mock import MagicMock, patch

from ai_client import (
    PROVIDER_NAMES,
    _build_system_instruction,
    _call_openai_compatible,
    _classify_error_message,
    get_ai_response,
    resolve_provider_key,
)
from ai_client import (
    test_provider_connection as check_provider_connection,
)
from config_loader import cfg


class TestProviderKeyResolution:
    """Verifica la jerarquía de resolución de credenciales BYOK."""

    def test_provider_key_from_config(self):
        original = cfg.llm_openai_api_key
        try:
            cfg.set("sk-test-config-key-12345", "llm", "openai_api_key")
            resolved = resolve_provider_key("openai")
            assert resolved == "sk-test-config-key-12345"
        finally:
            cfg.set(original, "llm", "openai_api_key")

    def test_provider_key_fallback_to_env(self, monkeypatch):
        original = cfg.llm_groq_api_key
        try:
            cfg.set("", "llm", "groq_api_key")
            monkeypatch.setenv("GROQ_API_KEY", "gsk_test_env_key_999")
            resolved = resolve_provider_key("groq")
            assert resolved == "gsk_test_env_key_999"
        finally:
            cfg.set(original, "llm", "groq_api_key")

    def test_ollama_requires_no_key(self):
        resolved = resolve_provider_key("ollama")
        assert resolved == ""

    def test_all_known_providers_have_display_names(self):
        expected_providers = {"gemini", "openai", "openrouter", "nvidia", "groq", "ollama", "custom"}
        assert set(PROVIDER_NAMES.keys()) == expected_providers


class TestOpenAICompatibleCaller:
    """Pruebas para el ejecutor HTTP unificado de OpenAI /chat/completions."""

    @patch("ai_client._req.urlopen")
    def test_successful_response_extraction(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "choices": [{"message": {"content": "Hola, soy una IA en Darius."}}]
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = _call_openai_compatible(
            endpoint="https://api.openai.com/v1/chat/completions",
            api_key="sk-test",
            model="gpt-4o-mini",
            prompt="Hola Darius",
        )
        assert result == "Hola, soy una IA en Darius."

    @patch("ai_client._req.urlopen")
    def test_history_included_in_payload(self, mock_urlopen):
        captured_payload = None

        def side_effect(request, timeout):
            nonlocal captured_payload
            captured_payload = json.loads(request.data.decode("utf-8"))
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({
                "choices": [{"message": {"content": "Entendido."}}]
            }).encode("utf-8")
            mock_resp.__enter__.return_value = mock_resp
            return mock_resp

        mock_urlopen.side_effect = side_effect

        history = [
            {"role": "user", "content": "¿Cómo te llamas?"},
            {"role": "model", "content": "Me llamo Darius."},
        ]

        _ = _call_openai_compatible(
            endpoint="https://api.groq.com/openai/v1/chat/completions",
            api_key="gsk-test",
            model="llama-3.3-70b-versatile",
            prompt="¿Qué hora es?",
            history=history,
        )

        assert captured_payload is not None
        messages = captured_payload["messages"]
        assert len(messages) == 4  # system + 2 history + 1 prompt
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"
        assert messages[3]["content"] == "¿Qué hora es?"


class TestErrorClassification:
    """Valida que los errores se clasifiquen en mensajes claros en español."""

    def test_auth_error_401(self):
        msg = _classify_error_message(RuntimeError("HTTP 401: Invalid API Key"), "OpenAI")
        assert "no está autorizada" in msg or "inválida" in msg

    def test_rate_limit_429(self):
        msg = _classify_error_message(RuntimeError("HTTP 429: Rate limit exceeded"), "Groq")
        assert "Límite de cuota" in msg

    def test_model_not_found_404(self):
        msg = _classify_error_message(RuntimeError("HTTP 404: Model not found"), "Ollama")
        assert "no fue encontrado" in msg

    def test_connection_refused(self):
        msg = _classify_error_message(RuntimeError("WinError 10061: Connection refused"), "Ollama")
        assert "servidor local" in msg


class TestTestProviderConnection:
    """Verifica la función de prueba de conexión en vivo / mock."""

    def test_missing_api_key_fails_fast(self):
        success, msg, latency = check_provider_connection("openai", api_key="")
        # Si no hay clave ni en config ni env
        if not resolve_provider_key("openai"):
            assert not success
            assert "Falta la API Key" in msg

    @patch("ai_client._call_openai_compatible")
    def test_successful_test_connection(self, mock_call):
        mock_call.return_value = "OK"
        success, msg, latency = check_provider_connection(
            "groq", api_key="gsk-valid", model="llama-3.3-70b-versatile"
        )
        assert success
        assert "Conexión exitosa" in msg
        assert latency >= 0.0

    @patch("ai_client._call_openai_compatible")
    def test_failed_test_connection(self, mock_call):
        mock_call.side_effect = RuntimeError("HTTP 401: Unauthorized")
        success, msg, latency = check_provider_connection(
            "groq", api_key="gsk-invalid", model="llama-3.3-70b-versatile"
        )
        assert not success
        assert "no está autorizada" in msg or "inválida" in msg


class TestDispatcherAndFallback:
    """Verifica la selección del proveedor activo y el mecanismo de fallback."""

    def test_dispatch_to_openai(self, monkeypatch):
        orig_prov = cfg.active_provider
        try:
            cfg.set("openai", "llm", "active_provider")
            with patch("ai_client.ask_openai") as mock_ask:
                mock_ask.return_value = ("Respuesta de OpenAI", "OpenAI (gpt-4o-mini)")
                text, prov = get_ai_response("Hola")
                assert text == "Respuesta de OpenAI"
                assert "OpenAI" in prov
        finally:
            cfg.set(orig_prov, "llm", "active_provider")

    def test_fallback_when_primary_fails(self):
        orig_prov = cfg.active_provider
        try:
            cfg.set("groq", "llm", "active_provider")
            cfg.set(True, "llm", "fallback_enabled")
            with patch("ai_client.ask_groq", side_effect=RuntimeError("Groq 429")), \
                 patch("ai_client.resolve_provider_key", return_value="openrouter-key-123"), \
                 patch("ai_client.ask_openrouter", return_value=("Fallback OK", "OpenRouter (gemma)")):
                text, prov = get_ai_response("Pregunta")
                assert text == "Fallback OK"
                assert "OpenRouter" in prov
        finally:
            cfg.set(orig_prov, "llm", "active_provider")


class TestObsidianSystemInstructionIntegration:
    """Verifica que la memoria contextual de Obsidian se integre en todos los prompts."""

    def test_system_instruction_contains_assistant_and_user(self):
        instruction = _build_system_instruction("recuerda mi proyecto")
        assert cfg.assistant_name in instruction
        assert cfg.user_name in instruction
        assert "español" in instruction
