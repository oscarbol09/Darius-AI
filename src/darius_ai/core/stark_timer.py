"""
stark_timer.py — Shim de compatibilidad hacia atrás para darius_timer.py
========================================================================
Redirige todas las llamadas y tipos hacia DariusTimer y DariusTimerManager.
"""

from __future__ import annotations

try:
    from src.darius_ai.core.darius_timer import (
        DariusTimer,
        DariusTimerManager,
        StarkTimer,
        StarkTimerManager,
        get_darius_timer_manager,
        get_stark_timer_manager,
    )
except ImportError:
    from darius_ai.core.darius_timer import (
        DariusTimer,
        DariusTimerManager,
        StarkTimer,
        StarkTimerManager,
        get_darius_timer_manager,
        get_stark_timer_manager,
    )

__all__ = [
    "DariusTimer",
    "DariusTimerManager",
    "StarkTimer",
    "StarkTimerManager",
    "get_darius_timer_manager",
    "get_stark_timer_manager",
]
