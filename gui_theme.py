"""
gui_theme.py — Sistema de Diseño y Tokens Visuales para DARIUS AI
===================================================================
Estándar de diseño orgánico y profesional para aplicaciones de escritorio en Windows.
Basado en principios de artesania visual, tokens semánticos (Regla 60-30-10)
y contraste WCAG 2.2 AA.
"""

from typing import Final

# =============================================================================
#  GEOMETRÍA Y PROPORCIONES
# =============================================================================
WINDOW_TITLE: Final[str] = "DARIUS AI — Tu Copiloto en Windows"
WINDOW_WIDTH: Final[int] = 880
WINDOW_HEIGHT: Final[int] = 620
WINDOW_MIN_WIDTH: Final[int] = 800
WINDOW_MIN_HEIGHT: Final[int] = 560
SIDEBAR_WIDTH: Final[int] = 230

RADIUS_LG: Final[int] = 10
RADIUS_MD: Final[int] = 8
RADIUS_SM: Final[int] = 6

# =============================================================================
#  PALETA DE COLORES SEMÁNTICA (REGLA 60-30-10)
# =============================================================================
# Base (60%)
BG_CANVAS: Final[str] = "#0B0F19"       # Lienzo principal oscuro profundo
BG_SIDEBAR: Final[str] = "#0F1626"      # Barra lateral estructurada
BG_HEADER: Final[str] = "#0F1626"       # Cabecera superior

# Superficies y Contenedores (30%)
BG_CARD: Final[str] = "#131C2D"         # Tarjetas de contenido y burbujas Darius
BG_CARD_HOVER: Final[str] = "#182338"   # Hover en tarjetas interactivas
BG_CARD_INNER: Final[str] = "#182338"   # Paneles internos y cajas de herramientas
BG_USER_BUBBLE: Final[str] = "#1E293B"  # Burbujas de mensaje del usuario
BG_INPUT: Final[str] = "#0F1626"        # Campo de entrada de texto
BG_PILL: Final[str] = "#151F32"         # Badges de telemetría discretos

# Bordes Hairline
BORDER_SUBTLE: Final[str] = "#1E293B"   # Borde estándar sutil (1px)
BORDER_CARD: Final[str] = "#233044"     # Borde de tarjetas
BORDER_ACTIVE: Final[str] = "#38BDF8"   # Borde de foco / acento activo

# Acentos Intencionales (10%)
ACCENT_PRIMARY: Final[str] = "#38BDF8"  # Azul cielo característico de Darius
ACCENT_PRIMARY_HOVER: Final[str] = "#0284C7"
ACCENT_EMERALD: Final[str] = "#10B981"  # Sistema Listo / Online / Éxito
ACCENT_PURPLE: Final[str] = "#A855F7"   # Workspaces / Pensando / IA
ACCENT_AMBER: Final[str] = "#F59E0B"    # Advertencia / Esperando Confirmación
ACCENT_ROSE: Final[str] = "#F43F5E"     # Detenido / Error

# Tipografía y Contraste
TEXT_PRIMARY: Final[str] = "#F8FAFC"    # Texto de alto contraste (Títulos y mensajes)
TEXT_SECONDARY: Final[str] = "#94A3B8"  # Texto secundario (Subtítulos, etiquetas)
TEXT_MUTED: Final[str] = "#64748B"      # Marcas de tiempo, metadatos, versiones

# =============================================================================
#  TIPOGRAFÍA JERÁRQUICA (Segoe UI)
# =============================================================================
FONT_FAMILY: Final[str] = "Segoe UI"
FONT_MONO_FAMILY: Final[str] = "Consolas"

FONT_TITLE = (FONT_FAMILY, 15, "bold")
FONT_SUBTITLE = (FONT_FAMILY, 11, "bold")
FONT_NAV = (FONT_FAMILY, 12, "bold")
FONT_BODY = (FONT_FAMILY, 12)
FONT_BODY_BOLD = (FONT_FAMILY, 12, "bold")
FONT_CAPTION = (FONT_FAMILY, 10)
FONT_CAPTION_BOLD = (FONT_FAMILY, 10, "bold")
FONT_BADGE = (FONT_FAMILY, 9, "bold")
FONT_MONO = (FONT_MONO_FAMILY, 10)

# =============================================================================
#  METADATOS DE AUTORÍA Y MARCA
# =============================================================================
AUTHOR_NAME: Final[str] = "Oscarbol09"
AUTHOR_GITHUB_URL: Final[str] = "https://github.com/oscarbol09/Darius-AI"
AUTHOR_TAG: Final[str] = "🛠 Desarrollado por @Oscarbol09"
VERSION_TAG: Final[str] = "v7.0.0"
