"""
test_approval_store.py — Tests unitarios para ApprovalStore y Human-in-the-Loop policy
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.darius_ai.core.approval_store import (
    ApprovalStore,
    Decision,
    RiskTier,
    parse_approval_response,
)


@pytest.fixture
def temp_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_approvals.db"
        yield ApprovalStore(db_path=db_path)


def test_approval_store_trivial_tier_auto_approves(temp_store):
    action = temp_store.propose_action(
        action_type="query_metrics",
        description="Consultar uso de RAM",
        payload={"count": 5},
        tier=RiskTier.TRIVIAL,
    )
    decision = temp_store.check_permission(action.permission_key, tier=action.tier)
    assert decision == Decision.ALWAYS_APPROVE


def test_approval_store_low_tier_ask_once_and_remember(temp_store):
    action = temp_store.propose_action(
        action_type="clean_temp",
        description="Limpiar caché de miniaturas",
        payload={"path": "C:\\temp"},
        tier=RiskTier.LOW,
    )
    # Primera vez: pregunta
    decision = temp_store.check_permission(action.permission_key, tier=action.tier)
    assert decision == Decision.ASK

    # Usuario decide "always_approve"
    temp_store.record_decision(action.permission_key, Decision.ALWAYS_APPROVE)

    # Segunda vez: auto-aprobado
    decision2 = temp_store.check_permission(action.permission_key, tier=action.tier)
    assert decision2 == Decision.ALWAYS_APPROVE


def test_approval_store_high_tier_never_auto_remembers(temp_store):
    action = temp_store.propose_action(
        action_type="force_delete",
        description="Eliminar directorio de proyecto",
        payload={"dir": "C:\\proj"},
        tier=RiskTier.HIGH,
    )
    # Incluso si se intentara registrar always_approve para un tier HIGH, check_permission siempre exige confirmación
    temp_store.record_decision(action.permission_key, Decision.ALWAYS_APPROVE)
    decision = temp_store.check_permission(action.permission_key, tier=RiskTier.HIGH)
    assert decision == Decision.ASK


def test_parse_approval_response():
    # Aprobaciones simples
    assert parse_approval_response("sí") == (None, Decision.APPROVE)
    assert parse_approval_response("afirmativo") == (None, Decision.APPROVE)
    assert parse_approval_response("rechazar") == (None, Decision.DENY)
    assert parse_approval_response("cancelar") == (None, Decision.DENY)

    # Con IDs de acción
    action_id, dec = parse_approval_response("aprobar act-101")
    assert action_id == "act-101"
    assert dec == Decision.APPROVE

    # Formato numérico / lista
    action_id2, dec2 = parse_approval_response("1 sí")
    assert action_id2 == "1"
    assert dec2 == Decision.APPROVE

    # Política permanente
    action_id3, dec3 = parse_approval_response("siempre permitir git_status")
    assert dec3 == Decision.ALWAYS_APPROVE


def test_resolve_pending_action(temp_store):
    action = temp_store.propose_action(
        action_type="git_push",
        description="Subir cambios a origin",
        payload={"branch": "main"},
        tier=RiskTier.MEDIUM,
    )
    assert len(temp_store.get_pending_actions()) == 1

    temp_store.resolve_action(action.id, Decision.APPROVE)
    pending = temp_store.get_pending_actions()
    assert len(pending) == 0
