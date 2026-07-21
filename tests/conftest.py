"""
conftest.py — Configuración compartida de pytest para DARIUS AI
================================================================
Define marcadores, fixtures globales y configuración de plataforma.
"""

import os
import platform
import sys

import pytest

# Añade la raíz del proyecto al path para que los tests puedan
# importar módulos como windows_commands, config_loader, etc.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def pytest_configure(config):
    """Registra marcadores personalizados para categorizar tests por plataforma."""
    config.addinivalue_line("markers", "windows: test que solo funciona en Windows")
    config.addinivalue_line("markers", "live: test que requiere API key real o hardware")


def pytest_collection_modifyitems(config, items):
    """Salta tests marcados como windows si no estamos en Windows."""
    if platform.system() != "Windows":
        skip_windows = pytest.mark.skip(reason="Solo disponible en Windows")
        for item in items:
            if "windows" in item.keywords:
                item.add_marker(skip_windows)
