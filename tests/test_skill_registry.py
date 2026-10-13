"""
test_skill_registry.py — Tests unitarios para SkillRegistry y SkillManifest
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.darius_ai.core.skill_registry import (
    SkillManifest,
    SkillParam,
    SkillRegistry,
)


@pytest.fixture
def temp_registry():
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "Skills"
        skills_dir.mkdir()
        yield SkillRegistry(storage_dir=skills_dir)


def test_register_and_get_skill(temp_registry):
    manifest = SkillManifest(
        name="diagnose_network",
        description="Diagnóstico exhaustivo de conectividad y DNS de Windows",
        parameters=[SkillParam(name="host", description="Host a diagnosticar", default="8.8.8.8")],
        required_tier="trivial",
        playbook="1. Ejecutar ping al host\n2. Limpiar cache DNS si hay falla",
    )
    temp_registry.register_skill(manifest)
    retrieved = temp_registry.get_skill("diagnose_network")
    assert retrieved is not None
    assert retrieved.name == "diagnose_network"
    assert len(retrieved.parameters) == 1
    assert retrieved.parameters[0].name == "host"


def test_discover_markdown_skills(temp_registry):
    # Crear un archivo de habilidad en formato markdown con frontmatter
    skill_file = temp_registry.storage_dir / "git_audit.md"
    skill_file.write_text(
        """---
name: git_audit
description: Inspección rápida del estado del repositorio Git
required_tier: low
---
# Procedimiento Git Audit
1. Ejecutar `git status`
2. Si hay cambios pendientes, listar archivos modificados
""",
        encoding="utf-8",
    )

    discovered = temp_registry.discover_skills()
    assert "git_audit" in discovered
    manifest = discovered["git_audit"]
    assert manifest.description == "Inspección rápida del estado del repositorio Git"
    assert manifest.required_tier == "low"
    assert "git status" in manifest.playbook


def test_format_catalog_prompt(temp_registry):
    manifest = SkillManifest(
        name="system_cleanup",
        description="Liberar espacio en disco",
        parameters=[],
        required_tier="medium",
        playbook="Vaciar papelera de reciclaje y temp",
    )
    temp_registry.register_skill(manifest)
    prompt_catalog = temp_registry.format_catalog_prompt()
    assert "system_cleanup" in prompt_catalog
    assert "Liberar espacio en disco" in prompt_catalog
