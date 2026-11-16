"""
human_gui.py — Módulo proxy para compatibilidad hacia atrás.
===========================================================
NOTA DE ARQUITECTURA (ECC):
La automatización de bajo nivel de ratón, teclado y curvas de Bézier
ha sido trasladada a su dominio arquitectónico canónico:
    `src.darius_ai.automation.human_input`

Este archivo reexporta todos los símbolos para garantizar
retrocompatibilidad con scripts existentes.
"""

from __future__ import annotations

import warnings

from src.darius_ai.automation.human_input import (  # noqa: F401
    FailsafeError,
    HumanGUIAutomator,
    gui,
    human_click,
    human_move_to,
    human_type,
)

warnings.warn(
    "src.darius_ai.gui.human_gui está deprecado. Use src.darius_ai.automation.human_input en su lugar.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "FailsafeError",
    "HumanGUIAutomator",
    "gui",
    "human_click",
    "human_move_to",
    "human_type",
]
