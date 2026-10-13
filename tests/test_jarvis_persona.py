"""
test_jarvis_persona.py — Pruebas de compatibilidad hacia atrás para JarvisPersona.
==================================================================================
Valida que el shim retrocompatible src.darius_ai.core.jarvis_persona funcione idénticamente.
"""

from src.darius_ai.core.jarvis_persona import (
    DariusPersona,
    JarvisPersona,
    build_darius_system_prompt,
    build_jarvis_system_prompt,
)


def test_legacy_jarvis_imports():
    assert JarvisPersona is DariusPersona
    assert build_jarvis_system_prompt is build_darius_system_prompt

    instance = JarvisPersona()
    assert instance.assistant_name == "DARIUS"
    assert instance.user_name == "señor"
    assert "DARIUS" in instance.build_jarvis_system_prompt()
