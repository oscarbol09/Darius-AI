"""
stark_lockdown.py — Shim de compatibilidad hacia atrás para darius_lockdown.py
============================================================================
Redirige todas las llamadas y tipos hacia DariusLockdownEngine.
"""

from __future__ import annotations

try:
    from src.darius_ai.core.darius_lockdown import (
        DariusLockdownEngine,
        StarkLockdownEngine,
        get_darius_lockdown_engine,
        get_stark_lockdown_engine,
        lockdown_engine,
    )
except ImportError:
    from darius_ai.core.darius_lockdown import (
        DariusLockdownEngine,
        StarkLockdownEngine,
        get_darius_lockdown_engine,
        get_stark_lockdown_engine,
        lockdown_engine,
    )

__all__ = [
    "DariusLockdownEngine",
    "StarkLockdownEngine",
    "get_darius_lockdown_engine",
    "get_stark_lockdown_engine",
    "lockdown_engine",
]
