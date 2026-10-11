"""
test_target_dossier.py — Pruebas unitarias para el motor de generación de dossiers de inteligencia
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.darius_ai.core.target_dossier import (
    TargetDossier,
    TargetDossierEngine,
    get_dossier_engine,
)


class TestTargetDossierModel:
    def test_target_dossier_serialization_and_frontmatter(self):
        dossier = TargetDossier(
            target_name="Linus Torvalds",
            category="person",
            title_or_role="Creator of Linux & Git",
            organization="Linux Foundation",
            summary="Ingeniero de software principal y creador del kernel Linux.",
            key_attributes=["Kernel C", "Git", "Sistemas Operativos"],
            social_profiles={"github": "https://github.com/torvalds"},
            conversation_hooks=["Filosofía de diseño de Git", "Control de versiones distribuido"],
            risk_flags=[],
            sources=["https://en.wikipedia.org/wiki/Linus_Torvalds"],
            confidence_score=0.98,
        )

        md = dossier.to_markdown()
        assert "---" in md
        assert 'target: "Linus Torvalds"' in md
        assert "category: person" in md
        assert "## 📌 Resumen Ejecutivo" in md
        assert "## 🎯 Ganchos de Conversación (Conversation Hooks)" in md
        assert "Creator of Linux & Git" in md

    def test_summary_for_speech_concise(self):
        dossier = TargetDossier(
            target_name="Ada Lovelace",
            category="person",
            title_or_role="Primera programadora de la historia",
            organization="Computación Teórica",
            summary="Pionera en el cálculo mecánico y creadora del primer algoritmo.",
        )
        speech = dossier.to_speech_summary()
        assert "Ada Lovelace" in speech
        assert len(speech) < 300


class TestTargetDossierEngine:
    @pytest.fixture
    def engine(self):
        return TargetDossierEngine()

    @patch("src.darius_ai.core.target_dossier.get_ai_response")
    def test_synthesize_dossier_parses_json_llm_response(self, mock_ai, engine):
        fake_llm_json = json.dumps({
            "target_name": "Guido van Rossum",
            "category": "person",
            "title_or_role": "Benevolent Dictator For Life Emeritus",
            "organization": "Python Software Foundation",
            "summary": "Creador del lenguaje de programación Python.",
            "key_attributes": ["Python", "C", "Compiladores"],
            "career_or_history": [{"role": "Distinguished Engineer", "company": "Microsoft"}],
            "social_profiles": {"github": "https://github.com/gvanrossum"},
            "conversation_hooks": ["Evolución de tipado en Python"],
            "risk_flags": [],
            "sources": ["https://gvanrossum.github.io/"],
            "confidence_score": 0.95,
        })
        mock_ai.return_value = (fake_llm_json, "gemini")

        dossier = engine.synthesize_dossier("Guido van Rossum", raw_research_text="Datos biográficos...")
        assert dossier.target_name == "Guido van Rossum"
        assert dossier.title_or_role == "Benevolent Dictator For Life Emeritus"
        assert len(dossier.conversation_hooks) == 1
        assert dossier.confidence_score == 0.95

    @patch("src.darius_ai.core.target_dossier.get_ai_response")
    def test_synthesize_dossier_fallback_on_invalid_json(self, mock_ai, engine):
        # Si el LLM devuelve texto libre sin JSON estricto
        mock_ai.return_value = ("Resumen general sin JSON válido...", "openai")
        dossier = engine.synthesize_dossier("Proyecto X", raw_research_text="Contexto...")
        assert dossier.target_name == "Proyecto X"
        assert "Resumen general" in dossier.summary
        assert dossier.confidence_score >= 0.5

    def test_save_to_obsidian_calls_brain(self, engine):
        dossier = TargetDossier(
            target_name="Sam Altman",
            category="person",
            summary="CEO de OpenAI.",
        )
        mock_brain = MagicMock()
        mock_brain.is_connected = True
        mock_brain.vault_path = "C:\\FakeVault"

        path = engine.save_to_obsidian(dossier, vault_brain=mock_brain)
        assert "Sam_Altman.md" in path
        assert mock_brain.create_note.called

    @patch("urllib.request.urlopen")
    def test_query_exa_api_graceful_handling(self, mock_urlopen, engine):
        # Sin API key configurada debe retornar lista vacía limpiamente sin colapsar
        results = engine.query_exa_api("test query", api_key="")
        assert results == []


class TestSingletonDossierEngine:
    def test_get_dossier_engine_returns_singleton(self):
        e1 = get_dossier_engine()
        e2 = get_dossier_engine()
        assert e1 is e2
