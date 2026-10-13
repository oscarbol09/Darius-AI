"""
test_darius_persona.py — Pruebas unitarias para DariusPersona y Wit Engine nativo de DARIUS.
"""

import pytest

from src.darius_ai.core.darius_persona import DariusPersona, JarvisPersona, build_jarvis_system_prompt
from src.darius_ai.core.jarvis_persona import JarvisPersona as ProxyJarvisPersona


class TestDariusPersonaConfiguration:
    """Verifica atributos de clase, inicialización y configuración de la personalidad Darius."""

    def test_default_initialization(self):
        persona = DariusPersona()
        assert persona.assistant_name == "DARIUS"
        assert persona.user_name == "señor"
        assert hasattr(DariusPersona, "ARCHETYPE")
        assert "Tactical" in DariusPersona.ARCHETYPE or "Copilot" in DariusPersona.ARCHETYPE
        assert hasattr(DariusPersona, "VOICE_TONE")
        assert "Subtle Wit" in DariusPersona.VOICE_TONE or "Dry Wit" in DariusPersona.VOICE_TONE

    def test_custom_initialization(self):
        persona = DariusPersona(user_name="Comandante", assistant_name="DARIUS-PRIME")
        assert persona.user_name == "Comandante"
        assert persona.assistant_name == "DARIUS-PRIME"


class TestDariusSystemPrompt:
    """Verifica la generación del prompt del sistema auténtico de Darius AI."""

    def test_system_prompt_contains_core_traits(self):
        persona = DariusPersona()
        prompt = persona.build_darius_system_prompt()

        assert isinstance(prompt, str)
        assert len(prompt) > 200
        # Tono de mayordomo y copiloto táctico con honorífico señor
        assert "señor" in prompt.lower()
        assert "darius" in prompt.lower()
        assert "dynamic autonomous realtime intelligent utility system" in prompt.lower()
        # Directivas anti-slop
        assert "slop" in prompt.lower() or "lenguaje" in prompt.lower() or "modelo" in prompt.lower()
        # Agudeza sutil / dry wit y lealtad absoluta
        assert "agudeza" in prompt.lower() or "dry wit" in prompt.lower() or "ironía" in prompt.lower()
        assert "lealtad" in prompt.lower()

    def test_system_prompt_custom_parameters(self):
        prompt = DariusPersona.build_darius_system_prompt(user_name="Comandante", assistant_name="AURA")
        assert "Comandante" in prompt
        assert "AURA" in prompt

    def test_system_prompt_via_class_and_instance(self):
        inst_prompt = DariusPersona(user_name="Dario").build_darius_system_prompt()
        class_prompt = DariusPersona.build_darius_system_prompt(user_name="Dario")
        assert "Dario" in inst_prompt
        assert "Dario" in class_prompt


class TestDariusWittyRetorts:
    """Verifica el motor de agudeza sobria y sutil de Darius."""

    @pytest.mark.parametrize(
        "query",
        [
            "cuéntame un chiste",
            "dime un chiste por favor",
            "hazme reír",
            "tienes algún chiste?",
        ],
    )
    def test_joke_retorts(self, query):
        persona = DariusPersona()
        retort = persona.get_witty_retort(query)
        assert isinstance(retort, str)
        assert len(retort) > 10
        assert any(
            token in retort.lower()
            for token in ["humor", "chiste", "absoluto", "lógicos", "comedia", "estimación", "señor"]
        )

    @pytest.mark.parametrize(
        "query",
        [
            "quién eres tú?",
            "cuál es tu propósito",
            "cómo te llamas",
            "identifícate",
            "who are you",
        ],
    )
    def test_identity_retorts(self, query):
        persona = DariusPersona()
        retort = persona.get_witty_retort(query)
        assert "DARIUS" in retort or "asistente" in retort.lower() or "copiloto" in retort.lower()
        assert "señor" in retort.lower()

    @pytest.mark.parametrize(
        "query",
        [
            "eres inteligente?",
            "qué tan listo eres",
            "crees que eres sabio?",
            "are you smart",
        ],
    )
    def test_intelligence_retorts(self, query):
        persona = DariusPersona()
        retort = persona.get_witty_retort(query)
        assert isinstance(retort, str)
        assert len(retort) > 15
        assert "señor" in retort.lower()

    @pytest.mark.parametrize(
        "query",
        [
            "eres un inútil",
            "no sirves para nada",
            "eres tonto",
            "qué idiota eres",
            "basura",
        ],
    )
    def test_insult_retorts(self, query):
        persona = DariusPersona()
        retort = persona.get_witty_retort(query)
        assert isinstance(retort, str)
        assert any(
            word in retort.lower()
            for word in ["telemetría", "crítica", "precisión", "modestia", "señor", "cálculos", "tolerancia"]
        )

    def test_compliment_retort(self):
        persona = DariusPersona()
        retort = persona.get_witty_retort("eres el mejor de todos")
        assert "señor" in retort.lower()

    def test_unknown_query_fallback_retort(self):
        persona = DariusPersona()
        retort = persona.get_witty_retort("el precio de las zanahorias en Marte")
        assert isinstance(retort, str)
        assert len(retort) > 10
        assert "señor" in retort.lower()

    def test_unknown_query_no_fallback(self):
        persona = DariusPersona()
        retort = persona.get_witty_retort("interrogante completamente atípica xyz", fallback=False)
        assert retort is None


class TestDariusTacticalAcknowledgment:
    """Verifica confirmaciones operativas auténticas estilo DARIUS."""

    @pytest.mark.parametrize(
        "action_type",
        ["general", "system", "search", "security", "code", "warning", "unknown_type"],
    )
    def test_acknowledgment_types(self, action_type):
        persona = DariusPersona()
        ack = persona.get_tactical_acknowledgment(action_type)
        assert isinstance(ack, str)
        assert len(ack) > 5
        assert ack.endswith(".") or ack.endswith("!")
        valid_seeds = [
            "órdenes",
            "línea",
            "telemetría",
            "parámetros",
            "registros",
            "perímetro",
            "secuencia",
            "señor",
        ]
        assert any(seed in ack.lower() for seed in valid_seeds)

    def test_acknowledgment_respects_custom_user_name(self):
        persona = DariusPersona(user_name="Comandante")
        ack = persona.get_tactical_acknowledgment("general")
        assert "Comandante" in ack


class TestDariusFormatButlerResponse:
    """Verifica el formateo y saneamiento de respuestas para mantener cadencia de mayordomo táctico."""

    def test_strips_ai_slop_and_greetings(self):
        persona = DariusPersona()
        raw = "¡Hola! Claro que sí, con mucho gusto puedo ayudarte con eso. La temperatura del CPU es 45°C."
        formatted = persona.format_butler_response(raw)
        assert "¡Hola!" not in formatted
        assert "con mucho gusto" not in formatted.lower()
        assert "45°C" in formatted
        assert formatted.startswith("La temperatura") or formatted.startswith("Señor, la temperatura")

    def test_strips_ai_farewells_and_emojis(self):
        persona = DariusPersona()
        raw = (
            "🚀 El despliegue ha finalizado con éxito. 👍 "
            "¡Espero que esto te haya servido! Si necesitas algo más, avísame."
        )
        formatted = persona.format_butler_response(raw)
        assert "🚀" not in formatted
        assert "👍" not in formatted
        assert "¡Espero que esto te haya servido!" not in formatted
        assert "El despliegue ha finalizado con éxito." in formatted

    def test_handles_empty_or_whitespace(self):
        persona = DariusPersona()
        assert persona.format_butler_response("") == "A sus órdenes, señor."
        assert persona.format_butler_response("   ") == "A sus órdenes, señor."

    def test_preserves_already_clean_technical_text(self):
        persona = DariusPersona()
        clean_text = "El archivo de configuración ha sido sincronizado en el disco, señor."
        result = persona.format_butler_response(clean_text)
        assert "El archivo de configuración ha sido sincronizado" in result

    def test_single_char_response(self):
        persona = DariusPersona()
        assert persona.format_butler_response("x") == "X"

    def test_pure_slop_input_returns_default(self):
        persona = DariusPersona()
        assert persona.format_butler_response("¡Hola! Con mucho gusto") == "A sus órdenes, señor."


class TestDariusPersonaBackwardsCompatibility:
    """Verifica que los alias retrocompatibles JarvisPersona y build_jarvis_system_prompt funcionen."""

    def test_jarvis_persona_alias(self):
        assert JarvisPersona is DariusPersona
        legacy = JarvisPersona()
        assert isinstance(legacy, DariusPersona)
        assert legacy.user_name == "señor"
        assert legacy.assistant_name == "DARIUS"

    def test_build_jarvis_system_prompt_alias(self):
        prompt = build_jarvis_system_prompt()
        assert isinstance(prompt, str)
        assert "darius" in prompt.lower()

        inst_prompt = JarvisPersona().build_jarvis_system_prompt()
        assert isinstance(inst_prompt, str)
        assert "darius" in inst_prompt.lower()

    def test_proxy_module_import(self):
        assert ProxyJarvisPersona is DariusPersona
