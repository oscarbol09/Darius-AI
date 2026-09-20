"""
test_gui_theme.py — Pruebas Unitarias para el Sistema de Diseño y Tokens de Darius AI
====================================================================================
Valida la consistencia de los tokens visuales (60-30-10), la metadata de autoría,
y la presencia de la licencia GNU GPLv3 con Copyright para Oscarbol09.
"""

import re
from pathlib import Path

import gui_theme as theme


def test_theme_geometry_constants():
    """Valida que las proporciones de ventana cumplan el estándar de escritorio split-pane."""
    assert theme.WINDOW_WIDTH >= 800
    assert theme.WINDOW_HEIGHT >= 600
    assert theme.WINDOW_MIN_WIDTH <= theme.WINDOW_WIDTH
    assert theme.WINDOW_MIN_HEIGHT <= theme.WINDOW_HEIGHT
    assert 200 <= theme.SIDEBAR_WIDTH <= 300


def test_theme_color_palette_tokens():
    """Verifica que todos los tokens de color sigan la convención hexadecimal estándar."""
    hex_pattern = re.compile(r"^#[0-9A-Fa-f]{6}$")

    colors = [
        theme.BG_CANVAS,
        theme.BG_SIDEBAR,
        theme.BG_HEADER,
        theme.BG_CARD,
        theme.BG_CARD_HOVER,
        theme.BG_CARD_INNER,
        theme.BG_USER_BUBBLE,
        theme.BG_INPUT,
        theme.BG_PILL,
        theme.BORDER_SUBTLE,
        theme.BORDER_CARD,
        theme.BORDER_ACTIVE,
        theme.ACCENT_PRIMARY,
        theme.ACCENT_PRIMARY_HOVER,
        theme.ACCENT_EMERALD,
        theme.ACCENT_PURPLE,
        theme.ACCENT_AMBER,
        theme.ACCENT_ROSE,
        theme.TEXT_PRIMARY,
        theme.TEXT_SECONDARY,
        theme.TEXT_MUTED,
    ]

    for color in colors:
        assert isinstance(color, str), f"El token {color} debe ser string"
        assert hex_pattern.match(color), f"El color {color} no es un valor hexadecimal de 6 dígitos válido"


def test_theme_author_metadata():
    """Valida los metadatos de autoría y enlace a GitHub."""
    assert theme.AUTHOR_NAME == "Oscarbol09"
    assert "https://github.com/oscarbol09" in theme.AUTHOR_GITHUB_URL
    assert "@Oscarbol09" in theme.AUTHOR_TAG
    assert theme.VERSION_TAG == "v7.0.0"


def test_license_file_and_copyright():
    """Verifica que el archivo LICENSE exista y contenga los términos de GNU GPLv3 y autoría."""
    license_path = Path(__file__).resolve().parent.parent / "LICENSE"
    assert license_path.exists(), "El archivo LICENSE debe existir en la raíz del repositorio"

    content = license_path.read_text(encoding="utf-8")
    assert "GNU GENERAL PUBLIC LICENSE" in content
    assert "Version 3" in content
    assert "Copyright (C) 2026 Oscarbol09" in content
