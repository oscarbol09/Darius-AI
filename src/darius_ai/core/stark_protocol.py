"""
stark_protocol.py — Stub retrocompatible que redirige a darius_protocol.py
==========================================================================
Mantiene compatibilidad total con llamadas heredadas al Protocolo Stark y StarkProtocolEngine.
"""

from __future__ import annotations

from src.darius_ai.core.darius_protocol import (
    DariusProtocolEngine,
    StarkProtocolEngine,
    darius_protocol_engine,
    get_darius_engine,
    get_darius_protocol_engine,
    get_stark_engine,
    get_stark_protocol_engine,
    stark_engine,
)

__all__ = [
    "DariusProtocolEngine",
    "StarkProtocolEngine",
    "darius_protocol_engine",
    "get_darius_engine",
    "get_darius_protocol_engine",
    "get_stark_engine",
    "get_stark_protocol_engine",
    "stark_engine",
]
