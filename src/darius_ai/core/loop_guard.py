"""
loop_guard.py — Prevención de bucles, oscilación de herramientas y truncamiento de contexto
========================================================================================
Arquitectura Nativa Darius AI. Previene bucles infinitos, patrones oscilatorios
(ping-pong) y degradación de memoria por llamadas excesivas de herramientas en Darius AI.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import deque
from enum import StrEnum
from typing import Any

log = logging.getLogger("DARIUS.LoopGuard")


class LoopStatus(StrEnum):
    OK = "ok"
    WARN = "warn"
    BLOCK = "block"


class LoopGuard:
    """
    Guardián determinista contra bucles infinitos y oscilaciones de agentes y herramientas.
    """

    def __init__(
        self,
        max_identical_calls: int = 3,
        ping_pong_window: int = 6,
        warn_before_block: bool = True,
    ) -> None:
        self.max_identical_calls = max_identical_calls
        self.ping_pong_window = ping_pong_window
        self.warn_before_block = warn_before_block

        self._call_history: deque[str] = deque(maxlen=ping_pong_window * 2)
        self._call_counts: dict[str, int] = {}
        self._warned_hashes: set[str] = set()
        self._total_calls = 0

    @property
    def call_count(self) -> int:
        return self._total_calls

    @staticmethod
    def _compute_hash(tool_name: str, arguments: dict[str, Any] | str) -> str:
        """Calcula un hash determinista normalizado de la llamada."""
        try:
            if isinstance(arguments, dict):
                norm_args = json.dumps(arguments, sort_keys=True, ensure_ascii=True)
            else:
                norm_args = str(arguments).strip()
        except Exception:
            norm_args = str(arguments)

        payload = f"{tool_name.strip().lower()}::{norm_args}".encode()
        return hashlib.sha256(payload).hexdigest()

    def record_call(self, tool_name: str, arguments: dict[str, Any] | str) -> tuple[LoopStatus, str]:
        """
        Registra una llamada a herramienta y evalúa si infringe límites de repetición o ciclos.
        Retorna (LoopStatus, mensaje_diagnostico).
        """
        self._total_calls += 1
        call_hash = self._compute_hash(tool_name, arguments)

        # 1. Conteo de llamadas idénticas
        count = self._call_counts.get(call_hash, 0) + 1
        self._call_counts[call_hash] = count
        self._call_history.append(call_hash)

        if count >= self.max_identical_calls:
            if self.warn_before_block and call_hash not in self._warned_hashes:
                self._warned_hashes.add(call_hash)
                msg = f"Advertencia: Herramienta '{tool_name}' repetida {count} veces con idénticos parámetros."
                log.warning(msg)
                return LoopStatus.WARN, msg
            else:
                msg = f"Ejecución bloqueada: Herramienta '{tool_name}' superó el límite de repetición ({count})."
                log.error(msg)
                return LoopStatus.BLOCK, msg

        # 2. Detección de patrones oscilatorios (Ping-Pong)
        h = list(self._call_history)
        if len(h) >= 4 and h[-4] == h[-2] and h[-3] == h[-1] and h[-1] != h[-2]:
            msg = "Detectado ciclo de oscilación ping-pong (A -> B -> A -> B) entre herramientas."
            log.warning(msg)
            status = LoopStatus.WARN if self.warn_before_block and len(self._warned_hashes) == 0 else LoopStatus.BLOCK
            return status, msg

        if len(h) >= 6 and h[-6] == h[-3] and h[-5] == h[-2] and h[-4] == h[-1]:
            msg = "Detectado ciclo de oscilación (A -> B -> C -> A -> B -> C) entre herramientas."
            log.warning(msg)
            status = LoopStatus.WARN if self.warn_before_block and len(self._warned_hashes) == 0 else LoopStatus.BLOCK
            return status, msg

        return LoopStatus.OK, "Llamada válida."

    def compress_context(
        self,
        messages: list[dict[str, Any]],
        max_tool_output_chars: int = 1500,
    ) -> list[dict[str, Any]]:
        """
        Compresión de contexto en 4 fases para evitar desbordamiento de tokens.
        """
        compressed: list[dict[str, Any]] = []
        for msg in messages:
            msg_copy = dict(msg)
            role = msg_copy.get("role", "")
            content = msg_copy.get("content", "")

            if role == "tool" and isinstance(content, str) and len(content) > max_tool_output_chars:
                omitted = len(content) - max_tool_output_chars
                truncated = content[:max_tool_output_chars] + f"\n... [Truncado por LoopGuard: {omitted} chars]"
                msg_copy["content"] = truncated

            compressed.append(msg_copy)

        return compressed

    def reset(self) -> None:
        """Reinicia el estado del guardián."""
        self._call_history.clear()
        self._call_counts.clear()
        self._warned_hashes.clear()
        self._total_calls = 0
