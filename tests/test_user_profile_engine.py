"""Tests para UserProfileEngine — Partición 4: Dynamic User Profile & Memory Service."""

from __future__ import annotations

import concurrent.futures
from pathlib import Path

from src.darius_ai.core.config_loader import cfg
from src.darius_ai.core.user_profile_engine import (
    DEFAULT_CATEGORIES,
    UserProfileEngine,
)


class TestUserProfileEngineInitAndPaths:
    def test_init_with_custom_path(self, tmp_path: Path):
        custom_file = tmp_path / "custom_user.md"
        engine = UserProfileEngine(profile_path=custom_file)
        assert engine.profile_path == custom_file.resolve()

    def test_init_default_path_resolution(self):
        engine = UserProfileEngine()
        assert engine.profile_path is not None
        assert engine.profile_path.name in ("User_Profile.md", "USER.md")

    def test_read_empty_profile_returns_default_categories(self, tmp_path: Path):
        custom_file = tmp_path / "USER.md"
        engine = UserProfileEngine(profile_path=custom_file)

        profile = engine.read_profile()
        for cat in DEFAULT_CATEGORIES:
            assert cat in profile
            assert profile[cat] == []


class TestUserProfileCrudOperations:
    def test_add_fact_creates_file_and_category(self, tmp_path: Path):
        file_path = tmp_path / "USER.md"
        engine = UserProfileEngine(profile_path=file_path)

        success = engine.add_fact("Identidad y Rol", "Ingeniero de Software Senior")
        assert success is True
        assert file_path.exists()

        profile = engine.read_profile()
        assert "Ingeniero de Software Senior" in profile["Identidad y Rol"]

        content = file_path.read_text(encoding="utf-8")
        assert "## Identidad y Rol" in content
        assert "- Ingeniero de Software Senior" in content

    def test_add_fact_deduplication(self, tmp_path: Path):
        file_path = tmp_path / "USER.md"
        engine = UserProfileEngine(profile_path=file_path)

        assert engine.add_fact("Stack Tecnológico", "Python 3.12") is True
        assert engine.add_fact("Stack Tecnológico", "Python 3.12") is False
        assert engine.add_fact("Stack Tecnológico", "  Python 3.12  ") is False
        assert engine.add_fact("Stack Tecnológico", "") is False

        profile = engine.read_profile()
        assert profile["Stack Tecnológico"] == ["Python 3.12"]

    def test_add_fact_with_category_alias(self, tmp_path: Path):
        file_path = tmp_path / "USER.md"
        engine = UserProfileEngine(profile_path=file_path)

        assert engine.add_fact("stack", "FastAPI") is True
        assert engine.add_fact("preferencias", "Respuestas en español") is True
        assert engine.add_fact("proyectos", "Darius-AI") is True
        assert engine.add_fact("restricciones", "No generar código sin tipado") is True
        assert engine.add_fact("rol", "Arquitecto de Soluciones") is True

        profile = engine.read_profile()
        assert "FastAPI" in profile["Stack Tecnológico"]
        assert "Respuestas en español" in profile["Preferencias y Estilo"]
        assert "Darius-AI" in profile["Proyectos Activos"]
        assert "No generar código sin tipado" in profile["Restricciones y Hábitos"]
        assert "Arquitecto de Soluciones" in profile["Identidad y Rol"]

    def test_add_fact_custom_category(self, tmp_path: Path):
        file_path = tmp_path / "USER.md"
        engine = UserProfileEngine(profile_path=file_path)

        assert engine.add_fact("Certificaciones", "AWS Solutions Architect") is True
        profile = engine.read_profile()
        assert "Certificaciones" in profile
        assert profile["Certificaciones"] == ["AWS Solutions Architect"]

    def test_update_fact_success_and_failure(self, tmp_path: Path):
        file_path = tmp_path / "USER.md"
        engine = UserProfileEngine(profile_path=file_path)

        engine.add_fact("Stack Tecnológico", "Python 3.10")
        assert engine.update_fact("Stack Tecnológico", "Python 3.10", "Python 3.12") is True

        profile = engine.read_profile()
        assert "Python 3.12" in profile["Stack Tecnológico"]
        assert "Python 3.10" not in profile["Stack Tecnológico"]

        # Failure cases
        assert engine.update_fact("Stack Tecnológico", "NonExistent", "NewVal") is False
        assert engine.update_fact("NonExistentCat", "Old", "New") is False
        assert engine.update_fact("Stack Tecnológico", "Python 3.12", "") is False

    def test_remove_fact_success_and_failure(self, tmp_path: Path):
        file_path = tmp_path / "USER.md"
        engine = UserProfileEngine(profile_path=file_path)

        engine.add_fact("Proyectos Activos", "Proyecto Alpha")
        engine.add_fact("Proyectos Activos", "Proyecto Beta")

        assert engine.remove_fact("Proyectos Activos", "Proyecto Alpha") is True
        profile = engine.read_profile()
        assert "Proyecto Alpha" not in profile["Proyectos Activos"]
        assert "Proyecto Beta" in profile["Proyectos Activos"]

        # Failure cases
        assert engine.remove_fact("Proyectos Activos", "Proyecto Inexistente") is False
        assert engine.remove_fact("Categoria Inexistente", "X") is False
        assert engine.remove_fact("Proyectos Activos", "") is False


class TestUserProfileExtractionAndPrompt:
    def test_extract_facts_from_text(self):
        engine = UserProfileEngine()
        sample_text = (
            "Hola Darius, soy arquitecto de software y desarrollador lead. "
            "Prefiero que las explicaciones sean breves y concisas. "
            "Actualmente mi proyecto es Darius-AI. "
            "Uso Python, Rust y Docker para el despliegue. "
            "No me gusta el código sin pruebas unitarias."
        )

        facts = engine.extract_facts_from_text(sample_text)
        assert len(facts) >= 5

        categories_found = {cat for cat, _ in facts}
        assert "Identidad y Rol" in categories_found
        assert "Preferencias y Estilo" in categories_found
        assert "Proyectos Activos" in categories_found
        assert "Stack Tecnológico" in categories_found
        assert "Restricciones y Hábitos" in categories_found

    def test_extract_facts_empty_and_noise(self):
        engine = UserProfileEngine()
        assert engine.extract_facts_from_text("") == []
        assert engine.extract_facts_from_text("   ") == []
        assert engine.extract_facts_from_text("¿Qué hora es en Tokio?") == []

    def test_get_profile_prompt_injection_empty(self, tmp_path: Path):
        file_path = tmp_path / "USER.md"
        engine = UserProfileEngine(profile_path=file_path)

        injection = engine.get_profile_prompt_injection()
        assert injection == ""

    def test_get_profile_prompt_injection_compact(self, tmp_path: Path):
        file_path = tmp_path / "USER.md"
        engine = UserProfileEngine(profile_path=file_path)

        engine.add_fact("Identidad y Rol", "Dario - Lead Dev")
        engine.add_fact("Preferencias y Estilo", "Respuestas técnicas directas")

        injection = engine.get_profile_prompt_injection()
        assert "Perfil de Usuario" in injection
        assert "Dario - Lead Dev" in injection
        assert "Respuestas técnicas directas" in injection
        # Empty categories should not bloat the prompt
        assert "Proyectos Activos" not in injection
        assert "Stack Tecnológico" not in injection
        assert "Restricciones y Hábitos" not in injection


class TestThreadSafetyAndMarkdownParsing:
    def test_concurrent_add_facts(self, tmp_path: Path):
        file_path = tmp_path / "USER.md"
        engine = UserProfileEngine(profile_path=file_path)

        num_threads = 10
        facts_to_add = [f"Tecnología_{i}" for i in range(num_threads)]

        def worker(fact: str) -> bool:
            return engine.add_fact("Stack Tecnológico", fact)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(worker, facts_to_add))

        assert all(results)
        profile = engine.read_profile()
        assert len(profile["Stack Tecnológico"]) == num_threads
        for fact in facts_to_add:
            assert fact in profile["Stack Tecnológico"]

    def test_parse_existing_markdown_with_custom_formatting(self, tmp_path: Path):
        file_path = tmp_path / "USER.md"
        raw_markdown = (
            "# Perfil Personal de Usuario\n\n"
            "## Identidad y Rol\n"
            "* Tech Lead\n"
            "- Fundador\n\n"
            "## Preferencias y Estilo\n"
            "- Modo oscuro siempre\n\n"
            "## Notas Adicionales\n"
            "- Trabaja en huso horario GMT-5\n"
        )
        file_path.write_text(raw_markdown, encoding="utf-8")

        engine = UserProfileEngine(profile_path=file_path)
        profile = engine.read_profile()

        assert "Tech Lead" in profile["Identidad y Rol"]
        assert "Fundador" in profile["Identidad y Rol"]
        assert "Modo oscuro siempre" in profile["Preferencias y Estilo"]
        assert "Notas Adicionales" in profile
        assert "Trabaja en huso horario GMT-5" in profile["Notas Adicionales"]


class TestUserProfileEngineEdgeCases:
    def test_init_with_configured_obsidian_vault(self, tmp_path: Path, monkeypatch):
        vault_path = tmp_path / "ObsidianVault"
        vault_path.mkdir()
        monkeypatch.setattr(type(cfg), "obsidian_vault_path", property(lambda self: str(vault_path)))

        engine = UserProfileEngine()
        expected = vault_path / "Darius" / "User_Profile.md"
        assert engine.profile_path == expected.resolve()
        assert expected.parent.exists()

    def test_init_fallback_on_oserror(self, monkeypatch, tmp_path: Path):
        def mock_home():
            raise OSError("Access denied")

        monkeypatch.setattr(Path, "home", mock_home)
        monkeypatch.setattr(type(cfg), "obsidian_vault_path", property(lambda self: ""))

        engine = UserProfileEngine()
        assert engine.profile_path.name == "USER.md"


    def test_read_profile_handles_read_oserror(self, tmp_path: Path, monkeypatch):
        file_path = tmp_path / "USER.md"
        file_path.write_text("# Perfil\n", encoding="utf-8")
        engine = UserProfileEngine(profile_path=file_path)

        def mock_read_text(*args, **kwargs):
            raise OSError("Read failed")

        monkeypatch.setattr(Path, "read_text", mock_read_text)
        profile = engine.read_profile()
        for cat in DEFAULT_CATEGORIES:
            assert cat in profile

    def test_extract_facts_clause_with_empty_and_clause_separators(self):
        engine = UserProfileEngine()
        text = ", prefiero respuestas concisas, uso Python"
        facts = engine.extract_facts_from_text(text)
        assert len(facts) == 2
        categories = {c for c, _ in facts}
        assert "Preferencias y Estilo" in categories
        assert "Stack Tecnológico" in categories

    def test_format_fact_empty_returns_empty_string(self):
        assert UserProfileEngine._format_fact("  . , ; ") == ""
        assert UserProfileEngine._format_fact("") == ""



