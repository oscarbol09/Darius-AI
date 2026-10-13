"""
tests/test_stark_timer.py — Pruebas de compatibilidad hacia atrás para stark_timer shim
======================================================================================
Verifica que las importaciones legacy desde src.darius_ai.core.stark_timer funcionen
correctamente redirigiendo a los tipos nativos DariusTimer y DariusTimerManager.
"""

from __future__ import annotations

from src.darius_ai.core.darius_timer import DariusTimer, DariusTimerManager
from src.darius_ai.core.stark_timer import (
    StarkTimer,
    StarkTimerManager,
    get_darius_timer_manager,
    get_stark_timer_manager,
)


def test_stark_timer_shim_aliases():
    assert StarkTimer is DariusTimer
    assert StarkTimerManager is DariusTimerManager
    assert get_stark_timer_manager is get_darius_timer_manager


def test_stark_timer_manager_via_shim():
    mgr = StarkTimerManager()
    try:
        t = mgr.create_timer(label="shim_test", seconds=60.0)
        assert isinstance(t, StarkTimer)
        assert isinstance(t, DariusTimer)
        assert t.label == "shim_test"
        assert mgr.get_timer(t.id) is not None
    finally:
        mgr.stop_all()
