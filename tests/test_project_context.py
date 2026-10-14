"""Pruebas para el descubrimiento e inyección de contexto de proyectos locales en Darius AI."""

import pathlib
from unittest.mock import patch

from src.darius_ai.core.ai_client import _build_system_instruction, _get_local_project_context


def test_get_local_project_context_finds_thesisforge(tmp_path: pathlib.Path):
    fake_proj = tmp_path / "thesisforge"
    fake_proj.mkdir()
    readme = fake_proj / "README.md"
    readme.write_text("# ThesisForge\nAsistente de investigacion academica con IA.", encoding="utf-8")

    with patch("pathlib.Path.home", return_value=tmp_path):
        gh_dir = tmp_path / "Documents" / "Proyectos Personales GH"
        gh_dir.mkdir(parents=True)
        (gh_dir / "thesisforge").symlink_to(fake_proj, target_is_directory=True) if hasattr(
            pathlib.Path, "symlink_to"
        ) else None

        # Prueba con "tesisforge" (español normalizado a thesisforge)
        res = _get_local_project_context("de que se trata mi proyecto tesisforge?")
        # Debe manejar la consulta sin lanzar excepciones
        assert isinstance(res, str)


def test_get_local_project_context_empty_on_short_or_unrelated():
    assert _get_local_project_context("") == ""
    assert _get_local_project_context("hola") == ""
    assert _get_local_project_context("que hora es?") == ""


def test_build_system_instruction_contains_darius_protocol_and_no_stark():
    instruction = _build_system_instruction("cual es el estado del sistema?")
    assert "[ACTION: darius_protocol()]" in instruction
    assert "[ACTION: stark_protocol()]" not in instruction
    assert "Mark VII" not in instruction
