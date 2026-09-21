"""
test_screen_vision.py — Pruebas unitarias para el motor de visión y captura de pantalla
"""

import base64
import io
from unittest.mock import patch

from PIL import Image

from screen_vision import ScreenVisionEngine


def test_screen_vision_capture_mocked():
    """Valida la captura, redimensionamiento y encoding base64 en memoria."""
    engine = ScreenVisionEngine()

    # Crear imagen sintética 1920x1080
    test_img = Image.new("RGB", (1920, 1080), color="blue")

    with patch.object(engine, "capture_screen_image", return_value=test_img):
        b64, meta = engine.capture_screen_base64(monitor_index=1)

        assert isinstance(b64, str)
        assert len(b64) > 0
        assert meta["original_width"] == 1920
        assert meta["original_height"] == 1080
        # Verificar que se escaló respetando límites
        assert meta["width"] <= 1600
        assert meta["height"] <= 1000

        # Verificar que el base64 es un JPEG válido
        raw_bytes = base64.b64decode(b64)
        img_recovered = Image.open(io.BytesIO(raw_bytes))
        assert img_recovered.format == "JPEG"


def test_screen_vision_analyze_screen_mocked():
    """Verifica que analyze_screen formule el prompt y devuelva la respuesta del LLM."""
    engine = ScreenVisionEngine()
    test_img = Image.new("RGB", (800, 600), color="green")
    mock_resp = ("En la pantalla hay un editor de código abierto.", "Gemini (gemini-2.5-flash)")

    with patch.object(engine, "capture_screen_image", return_value=test_img), \
         patch("screen_vision.get_ai_response", return_value=mock_resp):

        result = engine.analyze_screen(prompt="¿Qué estoy viendo?")
        assert "editor de código" in result


def test_screen_vision_analyze_screen_error_mocked():
    """Verifica el modo especializado de análisis de errores en pantalla."""
    engine = ScreenVisionEngine()
    test_img = Image.new("RGB", (800, 600), color="red")
    mock_resp = ("Se detectó un error de sintaxis en la línea 42.", "OpenAI (gpt-4o-mini)")

    with patch.object(engine, "capture_screen_image", return_value=test_img), \
         patch("screen_vision.get_ai_response", return_value=mock_resp):

        result = engine.analyze_screen_error(monitor_index=1)
        assert "error de sintaxis" in result
