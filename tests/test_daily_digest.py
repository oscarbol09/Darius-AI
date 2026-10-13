"""
test_daily_digest.py — Tests unitarios para DailyDigestEngine (recolección y síntesis de resumen)
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.darius_ai.core.daily_digest import DailyDigestEngine, DigestMetrics


@pytest.fixture
def temp_digest():
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_dir = Path(tmpdir) / "Vault"
        vault_dir.mkdir()
        engine = DailyDigestEngine(vault_path=vault_dir)
        yield engine


def test_collect_metrics(temp_digest):
    metrics = temp_digest.collect_metrics()
    assert isinstance(metrics, DigestMetrics)
    assert metrics.system_summary != ""
    assert isinstance(metrics.pending_tasks, list)
    assert isinstance(metrics.recent_notes, list)


def test_synthesize_narrative_rules(temp_digest):
    metrics = DigestMetrics(
        system_summary="RAM: 8.5 GB libres | Disco C: 120 GB libres",
        pending_tasks=["Revisar PR en Darius-AI", "Hacer copia de seguridad"],
        recent_notes=["Reunión Arquitectura", "Ideas Q4"],
        weather_summary="Soleado, 22°C en Bogotá",
        git_summary="Rama main, 0 cambios pendientes",
    )

    narrative = temp_digest.generate_spoken_narrative(metrics)
    # Reglas estrictas de síntesis de voz:
    # 1. Menos de 200 palabras
    word_count = len(narrative.split())
    assert word_count < 200, f"Narrativa demasiado larga: {word_count} palabras"

    # 2. Sin asteriscos, guiones markdown ni viñetas
    assert "*" not in narrative
    assert "#" not in narrative
    assert "```" not in narrative

    # 3. Menciona métricas clave
    assert "RAM" in narrative or "sistema" in narrative.lower()


def test_save_briefing_to_obsidian(temp_digest):
    metrics = DigestMetrics(
        system_summary="Sistema óptimo",
        pending_tasks=["Tarea 1"],
        recent_notes=["Nota 1"],
        weather_summary="Despejado",
        git_summary="Limpio",
    )
    briefing_path = temp_digest.save_briefing(metrics, "Buenos días, Óscar. El sistema está listo.")
    assert briefing_path.exists()
    content = briefing_path.read_text(encoding="utf-8")
    assert "Buenos días" in content
    assert "Darius AI" in content or "Briefing" in content
