"""
approval_store.py — Almacén SQLite de aprobaciones seguras y memoria de permisos Human-in-the-Loop
==================================================================================================
Arquitectura Nativa Darius AI. Provee gestión de acciones pendientes, clasificación
por niveles de riesgo (Tiers) y memoria de autorizaciones para Darius AI.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from src.darius_ai.core.config_loader import get_user_data_dir

log = logging.getLogger("DARIUS.ApprovalStore")


class RiskTier(StrEnum):
    TRIVIAL = "trivial"  # Ejecuta de inmediato sin preguntar
    LOW = "low"          # Pregunta una vez, luego recuerda
    MEDIUM = "medium"    # Pregunta siempre a menos que se indique always_approve
    HIGH = "high"        # Siempre pregunta, nunca auto-recuerda


class Decision(StrEnum):
    APPROVE = "approve"
    DENY = "deny"
    ALWAYS_APPROVE = "always_approve"
    ALWAYS_DENY = "always_deny"
    ASK = "ask"


@dataclass
class PendingAction:
    id: str
    action_type: str
    description: str
    payload: dict[str, Any]
    permission_key: str
    tier: RiskTier
    status: str = "pending"
    created_at: str = ""


def parse_approval_response(text: str) -> tuple[str | None, Decision | None]:
    """
    Parsea respuestas en lenguaje natural (voz o texto) para extraer la decisión y el ID de acción.
    Soporta español e inglés: 'sí', 'aprobar', 'rechazar', '1 sí', 'siempre permitir git_status', etc.
    """
    clean = text.strip().lower()

    action_id: str | None = None
    match_id = re.search(r"\b(act-[a-zA-Z0-9_-]+|\d+)\b", clean)
    if match_id:
        action_id = match_id.group(1)

    always_allow_kw = ("siempre permitir", "siempre sí", "always allow", "always approve", "siempre autorizar")
    if any(k in clean for k in always_allow_kw):
        return action_id, Decision.ALWAYS_APPROVE
    if any(k in clean for k in ("siempre denegar", "siempre rechazar", "always deny")):
        return action_id, Decision.ALWAYS_DENY
    if any(k in clean for k in ("sí", "si", "aprobar", "afirmativo", "proceder", "ok", "adelante", "yes", "approve")):
        return action_id, Decision.APPROVE
    if any(k in clean for k in ("no", "rechazar", "cancelar", "denegar", "abortar", "deny", "cancel")):
        return action_id, Decision.DENY

    return action_id, None


class ApprovalStore:
    """
    Almacén con base de datos SQLite (WAL) para control de acceso y autorizaciones.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            db_path = get_user_data_dir() / "approvals.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS pending_actions (
                    id TEXT PRIMARY KEY,
                    action_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    permission_key TEXT NOT NULL,
                    tier TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS permission_memory (
                    permission_key TEXT PRIMARY KEY,
                    decision TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def propose_action(
        self,
        action_type: str,
        description: str,
        payload: dict[str, Any],
        tier: RiskTier = RiskTier.MEDIUM,
    ) -> PendingAction:
        action_id = f"act-{uuid.uuid4().hex[:8]}"
        now = datetime.now(UTC).isoformat()
        perm_key = f"{action_type}:{json.dumps(payload, sort_keys=True)}"

        action = PendingAction(
            id=action_id,
            action_type=action_type,
            description=description,
            payload=payload,
            permission_key=perm_key,
            tier=tier,
            status="pending",
            created_at=now,
        )

        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO pending_actions (
                    id, action_type, description, payload, permission_key, tier, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action.id,
                    action.action_type,
                    action.description,
                    json.dumps(action.payload),
                    action.permission_key,
                    str(action.tier),
                    action.status,
                    action.created_at,
                ),
            )
        return action

    def check_permission(self, permission_key: str, tier: RiskTier = RiskTier.MEDIUM) -> Decision:
        tier_val = str(tier)

        if tier_val == RiskTier.TRIVIAL.value:
            return Decision.ALWAYS_APPROVE

        if tier_val == RiskTier.HIGH.value:
            return Decision.ASK

        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT decision FROM permission_memory WHERE permission_key = ?",
                (permission_key,),
            )
            row = cursor.fetchone()
            if row:
                saved = row[0]
                if saved == Decision.ALWAYS_APPROVE.value:
                    return Decision.ALWAYS_APPROVE
                if saved == Decision.ALWAYS_DENY.value:
                    return Decision.ALWAYS_DENY

        return Decision.ASK

    def record_decision(self, permission_key: str, decision: Decision | str) -> None:
        dec_val = str(decision)
        now = datetime.now(UTC).isoformat()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO permission_memory (permission_key, decision, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(permission_key) DO UPDATE SET decision = excluded.decision, updated_at = excluded.updated_at
                """,
                (permission_key, dec_val, now),
            )

    def get_pending_actions(self) -> list[PendingAction]:
        with self._connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, action_type, description, payload, permission_key, tier, status, created_at
                FROM pending_actions WHERE status = 'pending'
                """
            )
            rows = cursor.fetchall()

        actions = []
        for r in rows:
            actions.append(
                PendingAction(
                    id=r[0],
                    action_type=r[1],
                    description=r[2],
                    payload=json.loads(r[3]),
                    permission_key=r[4],
                    tier=RiskTier(r[5]) if r[5] in [t.value for t in RiskTier] else RiskTier.MEDIUM,
                    status=r[6],
                    created_at=r[7],
                )
            )
        return actions

    def resolve_action(self, action_id: str, decision: Decision | str) -> None:
        status_val = "approved" if decision in (Decision.APPROVE, Decision.ALWAYS_APPROVE, "approve") else "denied"
        with self._connection() as conn:
            conn.execute(
                "UPDATE pending_actions SET status = ? WHERE id = ?",
                (status_val, action_id),
            )
