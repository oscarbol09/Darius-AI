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

from src.darius_ai.core.ai_client import (
    PROVIDER_NAMES,
    _build_system_instruction,
    _call_openai_compatible,
    _classify_error_message,
    get_ai_response,
    resolve_provider_key,
)
from src.darius_ai.core.ai_client import (
    test_provider_connection as check_provider_connection,
)
from src.darius_ai.core.config_loader import cfg


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
        expected_providers = {
            "gemini",
            "antigravity",
            "openai",
            "openrouter",
            "nvidia",
            "groq",
            "ollama",
            "custom",
        }
        assert set(PROVIDER_NAMES.keys()) == expected_providers


class TestOpenAICompatibleCaller:
    """Pruebas para el ejecutor HTTP unificado de OpenAI /chat/completions."""

    @patch("src.darius_ai.core.ai_client._req.urlopen")
    def test_successful_response_extraction(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"choices": [{"message": {"content": "Hola, soy una IA en Darius."}}]}
        ).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = _call_openai_compatible(
            endpoint="https://api.openai.com/v1/chat/completions",
            api_key="sk-test",
            model="gpt-4o-mini",
            prompt="Hola Darius",
        )
        assert result == "Hola, soy una IA en Darius."

    @patch("src.darius_ai.core.ai_client._req.urlopen")
    def test_history_included_in_payload(self, mock_urlopen):
        captured_payload = None

        def side_effect(request, timeout):
            nonlocal captured_payload
            captured_payload = json.loads(request.data.decode("utf-8"))
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"choices": [{"message": {"content": "Entendido."}}]}).encode(
                "utf-8"
            )
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

    def test_missing_api_key_fails_fast(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        cfg.set("", "llm", "openai_api_key")
        success, msg, latency = check_provider_connection("openai", api_key="")
        assert not success
        assert "Falta la API Key" in msg
        assert latency == 0.0

    @patch("src.darius_ai.core.ai_client._call_openai_compatible")
    def test_successful_test_connection(self, mock_call):
        mock_call.return_value = "OK"
        success, msg, latency = check_provider_connection("groq", api_key="gsk-valid", model="llama-3.3-70b-versatile")
        assert success
        assert "Conexión exitosa" in msg
        assert latency >= 0.0

    @patch("src.darius_ai.core.ai_client._call_openai_compatible")
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
            with patch("src.darius_ai.core.ai_client.ask_openai") as mock_ask:
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
            with (
                patch("src.darius_ai.core.ai_client.ask_groq", side_effect=RuntimeError("Groq 429")),
                patch(
                    "src.darius_ai.core.ai_client.resolve_provider_key",
                    side_effect=lambda prov: "openrouter-key-123" if prov == "openrouter" else "",
                ),
                patch(
                    "src.darius_ai.core.ai_client.ask_openrouter", return_value=("Fallback OK", "OpenRouter (gemma)")
                ),
            ):
                text, prov = get_ai_response("Pregunta")
                assert text == "Fallback OK"
                assert "OpenRouter" in prov
        finally:
            cfg.set(orig_prov, "llm", "active_provider")

    def test_gemini_503_high_demand_fallback(self):
        """Verifica que si un modelo devuelve 503 alta demanda, rote y tenga éxito con el siguiente."""
        from src.darius_ai.core.ai_client import ask_gemini

        def fake_call_gemini_rest(api_key, model, *args, **kwargs):
            if "3.5" in model:
                raise RuntimeError("HTTP 503: Model is experiencing high demand. Spikes in demand are temporary.")
            return "Respuesta recuperada tras rotación de modelo Gemini."

        with (
            patch("src.darius_ai.core.ai_client.resolve_provider_key", return_value="gemini-fake-key"),
            patch("src.darius_ai.core.ai_client._call_gemini_rest", side_effect=fake_call_gemini_rest),
        ):
            text, prov = ask_gemini("Hola Darius")
            assert text == "Respuesta recuperada tras rotación de modelo Gemini."
            assert "Gemini" in prov

    def test_multi_provider_cascade_to_groq_when_gemini_fails(self):
        """Verifica que si Gemini falla, el despachador haga cascada hacia Groq u otro configurado."""

        orig_prov = cfg.active_provider
        try:
            cfg.set("gemini", "llm", "active_provider")
            cfg.set(True, "llm", "fallback_enabled")

            def resolve_key_mock(prov):
                if prov == "gemini":
                    return "gemini-key"
                if prov == "groq":
                    return "groq-key"
                return ""

            with (
                patch("src.darius_ai.core.ai_client.ask_gemini", side_effect=RuntimeError("Gemini 503 Dead")),
                patch("src.darius_ai.core.ai_client.resolve_provider_key", side_effect=resolve_key_mock),
                patch(
                    "src.darius_ai.core.ai_client.ask_groq",
                    return_value=("Respuesta desde Groq en cascada", "Groq (llama-3.3-70b-versatile)"),
                ),
            ):
                text, prov = get_ai_response("Pregunta")
                assert "Groq" in prov
                assert "Respuesta desde Groq" in text
        finally:
            cfg.set(orig_prov, "llm", "active_provider")


class TestObsidianSystemInstructionIntegration:
    """Verifica que la memoria contextual de Obsidian y las herramientas se integren en todos los prompts."""

    def test_system_instruction_contains_assistant_and_user(self):
        cfg.set_language("es")
        instruction_es = _build_system_instruction("recuerda mi proyecto")
        assert cfg.assistant_name in instruction_es
        assert cfg.user_name in instruction_es
        assert "español" in instruction_es

        cfg.set_language("en")
        instruction_en = _build_system_instruction("remember my project")
        assert cfg.assistant_name in instruction_en
        assert cfg.user_name in instruction_en
        assert "English" in instruction_en

    def test_system_instruction_contains_agentic_tools_and_obsidian_context(self):
        from src.darius_ai.core.obsidian_brain import brain

        brain.save_memory("Proyecto Hermetico", "Despliegue aislado de pruebas CI.", category="devops")

        cfg.set_language("es")
        instruction_es = _build_system_instruction("limpia el dns Proyecto Hermetico")
        assert "[ACTION: flush_dns()]" in instruction_es
        assert "[HERRAMIENTAS Y EJECUCIÓN AUTÓNOMA DEL SISTEMA]" in instruction_es
        assert "[CONTEXTO DE MEMORIA EN OBSIDIAN]" in instruction_es
        assert "Proyecto Hermetico" in instruction_es

        cfg.set_language("en")
        instruction_en = _build_system_instruction("flush dns")
        assert "[ACTION: flush_dns()]" in instruction_en
        assert "[SYSTEM AUTONOMOUS TOOLS & EXECUTION]" in instruction_en


class TestAgenticToolCallingLoop:
    """Valida el bucle de ejecución autónoma de herramientas y síntesis de voz."""

    def test_agentic_tool_intercepted_and_synthesized(self):
        orig_prov = cfg.active_provider
        try:
            cfg.set("openai", "llm", "active_provider")
            with (
                patch("src.darius_ai.core.ai_client.ask_openai") as mock_ask,
                patch("src.darius_ai.core.agentic_bridge.bridge.flush_dns") as mock_dns,
            ):
                mock_dns.return_value = (True, "Caché DNS vaciada con éxito.")
                # Primera llamada emite acción, segunda sintetiza
                mock_ask.side_effect = [
                    ("[ACTION: flush_dns()]", "OpenAI (gpt-4o-mini)"),
                    ("Listo Óscar, he limpiado la caché DNS de tu equipo.", "OpenAI (gpt-4o-mini)"),
                ]
                text, prov = get_ai_response("limpia el dns de mi red")
                assert text == "Listo Óscar, he limpiado la caché DNS de tu equipo."
                assert "[Tool:flush_dns]" in prov
                mock_dns.assert_called_once()
                assert mock_ask.call_count == 2
        finally:
            cfg.set(orig_prov, "llm", "active_provider")

    def test_agentic_tool_passes_normal_text(self):
        orig_prov = cfg.active_provider
        try:
            cfg.set("openai", "llm", "active_provider")
            with patch("src.darius_ai.core.ai_client.ask_openai") as mock_ask:
                mock_ask.return_value = ("Hola, ¿cómo estás?", "OpenAI (gpt-4o-mini)")
                text, prov = get_ai_response("Hola")
                assert text == "Hola, ¿cómo estás?"
                assert "[Tool:" not in prov
                assert mock_ask.call_count == 1
        finally:
            cfg.set(orig_prov, "llm", "active_provider")


class TestCallGeminiRestAndProviderWrappers:
    """Cobertura hermética de _call_gemini_rest, wrappers ask_* y test_provider_connection."""

    def test_call_gemini_rest_success_history_and_image(self):
        import io
        import urllib.error

        from src.darius_ai.core.ai_client import _call_gemini_rest

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"candidates": [{"content": {"parts": [{"text": "Respuesta Gemini REST"}]}}]}
        ).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        history = [
            {"role": "user", "content": "Uno"},
            {"role": "user", "content": "Dos"},
            {"role": "model", "content": "Tres"},
            {"role": "model", "content": ""},
        ]
        with patch("src.darius_ai.core.ai_client._req.urlopen", return_value=mock_resp) as mock_open:
            out = _call_gemini_rest(
                api_key="gem-test-key",
                model="models/gemini-3.5-flash-lite",
                prompt="Analiza",
                system_instruction="Eres Darius",
                history=history,
                image_b64="ZmFrZQ==",
            )
            assert out == "Respuesta Gemini REST"
            req_obj = mock_open.call_args[0][0]
            payload = json.loads(req_obj.data.decode("utf-8"))
            assert payload["system_instruction"]["parts"][0]["text"] == "Eres Darius"
            assert payload["contents"][-1]["parts"][1]["inline_data"]["data"] == "ZmFrZQ=="

        # Respuesta sin candidatos / vacía
        mock_empty = MagicMock()
        mock_empty.read.return_value = json.dumps({"candidates": []}).encode("utf-8")
        mock_empty.__enter__.return_value = mock_empty
        with patch("src.darius_ai.core.ai_client._req.urlopen", return_value=mock_empty):
            import pytest

            with pytest.raises(RuntimeError, match="candidatos"):
                _call_gemini_rest("gem-test-key", "gemini-3.5-flash-lite", "Hola")

        # HTTPError y URLError
        http_err = urllib.error.HTTPError(
            "https://generativelanguage.googleapis.com",
            429,
            "Too Many Requests",
            {},
            io.BytesIO(b'{"error": {"message": "Quota exceeded"}}'),
        )
        with patch("src.darius_ai.core.ai_client._req.urlopen", side_effect=http_err):
            import pytest

            with pytest.raises(RuntimeError, match="HTTP 429: Quota exceeded"):
                _call_gemini_rest("gem-test-key", "gemini-3.5-flash-lite", "Hola")

        with patch("src.darius_ai.core.ai_client._req.urlopen", side_effect=urllib.error.URLError("DNS fail")):
            import pytest

            with pytest.raises(RuntimeError, match="Fallo de conexión"):
                _call_gemini_rest("gem-test-key", "gemini-3.5-flash-lite", "Hola")

    def test_provider_ask_wrappers_success_and_missing_keys(self, monkeypatch):
        import pytest

        from src.darius_ai.core.ai_client import (
            ask_antigravity,
            ask_custom,
            ask_groq,
            ask_nvidia,
            ask_ollama,
            ask_openai,
            ask_openrouter,
        )

        # Sin claves debe fallar rápido
        for fn in (ask_openai, ask_openrouter, ask_nvidia, ask_groq):
            with pytest.raises(RuntimeError, match="configurada"):
                fn("Hola")

        # Con claves y transporte mockeado
        with (
            patch("src.darius_ai.core.ai_client.resolve_provider_key", return_value="k-test-123"),
            patch("src.darius_ai.core.ai_client._call_openai_compatible", return_value="OK"),
        ):
            assert ask_openai("Hi")[1].startswith("OpenAI")
            assert ask_openrouter("Hi")[1].startswith("OpenRouter")
            assert ask_nvidia("Hi")[1].startswith("NVIDIA NIM")
            assert ask_groq("Hi")[1].startswith("Groq")
            assert ask_ollama("Hi")[1].startswith("Ollama")
            assert ask_custom("Hi")[1].startswith("Custom")

        # Fallo completo en rotación de OpenRouter / NVIDIA / Groq
        with (
            patch("src.darius_ai.core.ai_client.resolve_provider_key", return_value="k-test-123"),
            patch("src.darius_ai.core.ai_client._call_openai_compatible", side_effect=RuntimeError("503")),
        ):
            for fn in (ask_openrouter, ask_nvidia, ask_groq):
                with pytest.raises(RuntimeError, match="fallaron"):
                    fn("Hi")

        # ask_antigravity
        mock_bridge = MagicMock()
        mock_bridge.ask_agent.return_value = MagicMock(success=True, response_text="Listo")
        with patch("src.darius_ai.core.antigravity_bridge.get_antigravity_bridge", return_value=mock_bridge):
            assert ask_antigravity("Hi") == ("Listo", "Antigravity Agent")

        mock_bridge.ask_agent.return_value = MagicMock(success=False, response_text="Sin agente")
        with (
            patch("src.darius_ai.core.antigravity_bridge.get_antigravity_bridge", return_value=mock_bridge),
            pytest.raises(RuntimeError, match="Sin agente"),
        ):
            ask_antigravity("Hi")

    def test_check_provider_connection_all_providers(self):
        with (
            patch("src.darius_ai.core.ai_client._call_gemini_rest", return_value="OK"),
            patch("src.darius_ai.core.ai_client._call_openai_compatible", return_value="OK"),
        ):
            for prov in ("gemini", "openai", "openrouter", "nvidia", "groq", "ollama", "custom"):
                ok, msg, _ = check_provider_connection(prov, api_key="sk-test-123")
                assert ok is True
                assert "Conexión exitosa" in msg

        # Proveedor desconocido y falta de clave por proveedor
        ok_unk, msg_unk, _ = check_provider_connection("unknown_xyz", api_key="x")
        assert ok_unk is False
        assert "desconocido" in msg_unk.lower()

        for prov in ("gemini", "openrouter", "nvidia", "groq"):
            ok_miss, _, _ = check_provider_connection(prov, api_key="")
            assert ok_miss is False

        # Antigravity connection test
        mock_bridge = MagicMock()
        mock_bridge.is_available.return_value = True
        mock_bridge.ask_agent.return_value = MagicMock(success=True, response_text="OK")
        with patch("src.darius_ai.core.antigravity_bridge.get_antigravity_bridge", return_value=mock_bridge):
            ok_ag, msg_ag, _ = check_provider_connection("antigravity")
            assert ok_ag is True
            assert "Antigravity" in msg_ag

        mock_bridge.is_available.return_value = False
        with patch("src.darius_ai.core.antigravity_bridge.get_antigravity_bridge", return_value=mock_bridge):
            ok_ag_no, _, _ = check_provider_connection("antigravity")
            assert ok_ag_no is False
