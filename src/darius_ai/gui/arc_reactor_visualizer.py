"""
arc_reactor_visualizer.py — Stub retrocompatible que redirige a cyber_core_visualizer.py
========================================================================================
Mantiene compatibilidad hacia atrás con importaciones heredadas del visualizador del reactor arc.
"""

from __future__ import annotations

from src.darius_ai.gui.cyber_core_visualizer import (
    ARC_CYAN,
    CORE_AMBER,
    CORE_CRIMSON,
    CORE_CYAN,
    CORE_EMERALD,
    CRIMSON_MARK,
    EMERALD_NOMINAL,
    STATE_COLORS,
    STATE_SPEEDS,
    TITANIUM_GOLD,
    ArcReactorVisualizer,
    CyberCoreVisualizer,
    compute_core_coords,
    compute_core_radius,
    compute_outer_ring_coords,
    compute_tick_coords,
)

__all__ = [
    "ARC_CYAN",
    "ArcReactorVisualizer",
    "CORE_AMBER",
    "CORE_CRIMSON",
    "CORE_CYAN",
    "CORE_EMERALD",
    "CRIMSON_MARK",
    "CyberCoreVisualizer",
    "EMERALD_NOMINAL",
    "STATE_COLORS",
    "STATE_SPEEDS",
    "TITANIUM_GOLD",
    "compute_core_coords",
    "compute_core_radius",
    "compute_outer_ring_coords",
    "compute_tick_coords",
]
