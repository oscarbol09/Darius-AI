"""
test_complexity_router.py — Tests unitarios para el analizador y enrutador de complejidad de consultas
"""

from __future__ import annotations

import pytest

from src.darius_ai.core.complexity_router import (
    ComplexityRouter,
    ComplexityTier,
    ModelTarget,
)


@pytest.fixture
def router():
    return ComplexityRouter()


def test_complexity_router_trivial_query(router):
    # Saludos o comandos básicos de 1 paso
    score, tier, budget, target = router.analyze("hola darius")
    assert score < 0.25
    assert tier == ComplexityTier.TRIVIAL
    assert budget <= 1024
    assert target == ModelTarget.LOCAL_FAST


def test_complexity_router_simple_query(router):
    score, tier, budget, target = router.analyze("¿qué hora es en Madrid?")
    assert tier in (ComplexityTier.TRIVIAL, ComplexityTier.SIMPLE)
    assert budget <= 2048


def test_complexity_router_code_and_reasoning_query(router):
    query = (
        "Escribe una función en Python con tipado estricto que implemente el algoritmo Dijkstra "
        "usando un heap binario heapq. Explica la complejidad temporal O((V+E) log V) en detalle."
    )
    score, tier, budget, target = router.analyze(query)
    assert score >= 0.50
    assert tier in (ComplexityTier.COMPLEX, ComplexityTier.VERY_COMPLEX)
    assert budget >= 4096
    assert target == ModelTarget.FRONTIER_REASONING


def test_complexity_router_reasoning_headroom(router):
    # Verificar que para modelos de razonamiento (como DeepSeek-R1 o o1) el presupuesto se duplique
    budget_std = router.get_token_budget(ComplexityTier.COMPLEX, is_reasoning_model=False)
    budget_reasoning = router.get_token_budget(ComplexityTier.COMPLEX, is_reasoning_model=True)
    assert budget_reasoning == budget_std * 2
