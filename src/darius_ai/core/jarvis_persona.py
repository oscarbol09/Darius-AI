"""
jarvis_persona.py — Stub retrocompatible que redirige a darius_persona.py
========================================================================
Mantiene compatibilidad hacia atrás total con módulos preexistentes que
importen JarvisPersona o build_jarvis_system_prompt.
"""

from __future__ import annotations

from src.darius_ai.core.darius_persona import (
    DariusPersona,
    JarvisPersona,
    build_darius_system_prompt,
    build_jarvis_system_prompt,
)

__all__ = [
    "DariusPersona",
    "JarvisPersona",
    "build_darius_system_prompt",
    "build_jarvis_system_prompt",
]
