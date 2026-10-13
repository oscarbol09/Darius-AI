"""
test_arc_reactor_visualizer.py — Pruebas de compatibilidad hacia atrás para ArcReactorVisualizer.
================================================================================================
Valida que las importaciones heredadas de src.darius_ai.gui.arc_reactor_visualizer sigan operativas.
"""

from src.darius_ai.gui.arc_reactor_visualizer import (
    ARC_CYAN,
    CRIMSON_MARK,
    EMERALD_NOMINAL,
    TITANIUM_GOLD,
    ArcReactorVisualizer,
    CyberCoreVisualizer,
)


def test_legacy_arc_reactor_imports():
    assert ArcReactorVisualizer is CyberCoreVisualizer
    assert ARC_CYAN.upper() == "#00F0FF"
    assert TITANIUM_GOLD.upper() == "#E6AA38"
    assert CRIMSON_MARK.upper() == "#C42B3B"
    assert EMERALD_NOMINAL.upper() == "#00FF88"
