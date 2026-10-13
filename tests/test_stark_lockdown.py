"""
test_stark_lockdown.py — Pruebas de compatibilidad hacia atrás para stark_lockdown shim
========================================================================================
Valida que las importaciones legacy desde src.darius_ai.core.stark_lockdown funcionen
correctamente redirigiendo a los tipos nativos DariusLockdownEngine.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.darius_ai.core.darius_lockdown import (
    DariusLockdownEngine,
    get_darius_lockdown_engine,
)
from src.darius_ai.core.stark_lockdown import (
    StarkLockdownEngine,
    get_stark_lockdown_engine,
    lockdown_engine,
)


def test_stark_lockdown_shim_aliases():
    assert StarkLockdownEngine is DariusLockdownEngine
    assert get_stark_lockdown_engine is get_darius_lockdown_engine
    assert isinstance(lockdown_engine, DariusLockdownEngine)


def test_stark_lockdown_engine_via_shim():
    engine = StarkLockdownEngine(media_controller=MagicMock())
    success, msg = engine.trigger_tactical_silence()
    assert success is True
    assert "Silencio Táctico" in msg
