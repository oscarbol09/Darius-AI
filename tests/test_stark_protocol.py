"""
test_stark_protocol.py — Pruebas de compatibilidad hacia atrás para StarkProtocolEngine.
========================================================================================
Valida que las llamadas heredadas a src.darius_ai.core.stark_protocol funcionen idénticamente.
"""

from src.darius_ai.core.stark_protocol import (
    DariusProtocolEngine,
    StarkProtocolEngine,
    get_darius_protocol_engine,
    get_stark_engine,
    get_stark_protocol_engine,
)


def test_legacy_stark_imports():
    assert StarkProtocolEngine is DariusProtocolEngine
    assert get_stark_engine is get_darius_protocol_engine
    assert get_stark_protocol_engine is get_darius_protocol_engine

    engine = get_stark_engine()
    assert isinstance(engine, DariusProtocolEngine)
