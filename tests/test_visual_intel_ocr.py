"""
test_visual_intel_ocr.py — Comprehensive Unit & Integration Tests for Visual Intel OCR
=======================================================================================
Verifies OCRResult dataclass, image preprocessing (grayscale, contrast, Otsu),
multi-tier engine discovery (WinRT -> Tesseract -> LLM Vision fallback),
screen region & clipboard OCR, and code/error/URL extraction heuristics.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from src.darius_ai.core.visual_intel_ocr import (
    OCRResult,
    VisualIntelOCR,
    otsu_threshold,
    preprocess_image,
)

# ============================================================================
# 1. OCRResult Dataclass Tests
# ============================================================================


class TestOCRResult:
    def test_ocr_result_creation_and_attributes(self):
        res = OCRResult(
            text="Hello World\nLine 2",
            confidence=0.95,
            engine_used="tesseract",
            duration_ms=42.5,
            word_count=4,
            lines=["Hello World", "Line 2"],
        )
        assert res.text == "Hello World\nLine 2"
        assert res.confidence == 0.95
        assert res.engine_used == "tesseract"
        assert res.duration_ms == 42.5
        assert res.word_count == 4
        assert res.lines == ["Hello World", "Line 2"]

    def test_ocr_result_default_lines_and_word_count(self):
        res = OCRResult(
            text="Single line of text",
            confidence=0.88,
            engine_used="winrt",
            duration_ms=12.0,
        )
        assert res.word_count == 4
        assert res.lines == ["Single line of text"]

    def test_ocr_result_empty_text(self):
        res = OCRResult(
            text="",
            confidence=0.0,
            engine_used="none",
            duration_ms=0.0,
        )
        assert res.word_count == 0
        assert res.lines == []


# ============================================================================
# 2. Image Preprocessing Tests (Grayscale, Contrast, Otsu)
# ============================================================================


class TestImagePreprocessing:
    @pytest.fixture
    def sample_rgb_image(self) -> Image.Image:
        # Create a 64x64 synthetic image with dark and bright patches
        arr = np.zeros((64, 64, 3), dtype=np.uint8)
        arr[:32, :] = [30, 40, 50]  # dark background
        arr[32:, :] = [220, 230, 240]  # bright text/foreground
        return Image.fromarray(arr)

    def test_otsu_threshold_calculation(self):
        # Bimodal distribution with peaks at 50 and 200
        arr = np.zeros((100, 100), dtype=np.uint8)
        arr[:50, :] = 50
        arr[50:, :] = 200
        t = otsu_threshold(arr)
        # Optimal Otsu threshold should split between 50 and 200 (around 124-126)
        assert 50 < t < 200

    def test_preprocess_image_from_pil(self, sample_rgb_image):
        processed = preprocess_image(sample_rgb_image)
        assert isinstance(processed, Image.Image)
        # Should be grayscale (mode 'L') or 1-bit
        assert processed.mode in ("L", "1")
        # Check dimensions preserved
        assert processed.size == (64, 64)

    def test_preprocess_image_from_numpy(self):
        arr = np.random.randint(0, 255, size=(40, 40, 3), dtype=np.uint8)
        processed = preprocess_image(arr)
        assert isinstance(processed, Image.Image)
        assert processed.size == (40, 40)

    def test_preprocess_image_pure_grayscale_input(self):
        gray_img = Image.new("L", (50, 50), color=128)
        processed = preprocess_image(gray_img)
        assert isinstance(processed, Image.Image)
        assert processed.size == (50, 50)


# ============================================================================
# 3. Multi-Tier Engine Discovery Tests
# ============================================================================


class TestEngineDiscovery:
    @pytest.fixture
    def ocr(self) -> VisualIntelOCR:
        return VisualIntelOCR()

    def test_discover_tesseract_via_env(self, ocr, monkeypatch, tmp_path):
        fake_tess = tmp_path / "fake_tesseract.exe"
        fake_tess.write_text("dummy")
        monkeypatch.setenv("TESSERACT_CMD", str(fake_tess))

        path = ocr.discover_tesseract_path()
        assert path == str(fake_tess)

    def test_discover_tesseract_via_path(self, ocr, monkeypatch):
        monkeypatch.delenv("TESSERACT_CMD", raising=False)
        with patch("shutil.which", return_value="C:\\dummy\\path\\tesseract.exe"):
            path = ocr.discover_tesseract_path()
            assert path == "C:\\dummy\\path\\tesseract.exe"

    def test_discover_tesseract_fallback_program_files(self, ocr, monkeypatch):
        monkeypatch.delenv("TESSERACT_CMD", raising=False)
        with patch("shutil.which", return_value=None), patch("os.path.isfile") as mock_isfile:
            mock_isfile.side_effect = lambda p: p == r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            path = ocr.discover_tesseract_path()
            assert path == r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    def test_discover_tesseract_none_found(self, ocr, monkeypatch):
        monkeypatch.delenv("TESSERACT_CMD", raising=False)
        with patch("shutil.which", return_value=None), patch("os.path.isfile", return_value=False):
            path = ocr.discover_tesseract_path()
            assert path is None

    def test_get_available_tiers(self, ocr):
        with (
            patch.object(ocr, "is_winrt_available", return_value=True),
            patch.object(ocr, "discover_tesseract_path", return_value="C:\\tess.exe"),
        ):
            tiers = ocr.get_available_tiers()
            assert "winrt" in tiers
            assert "tesseract" in tiers
            assert "llm_vision" in tiers


# ============================================================================
# 4. OCR Execution on Images (File, PIL, NumPy)
# ============================================================================


class TestOCRImageExecution:
    @pytest.fixture
    def ocr(self) -> VisualIntelOCR:
        return VisualIntelOCR()

    def test_ocr_image_tier1_winrt_success(self, ocr):
        img = Image.new("RGB", (100, 100), color="white")
        with patch.object(ocr, "_ocr_winrt", return_value=OCRResult(
            text="Recognized by WinRT",
            confidence=0.92,
            engine_used="winrt",
            duration_ms=15.0,
        )):
            res = ocr.ocr_image(img, tier_preference=["winrt"])
            assert res.text == "Recognized by WinRT"
            assert res.engine_used == "winrt"
            assert res.confidence == 0.92

    def test_ocr_image_tier1_fails_falls_to_tier2_tesseract(self, ocr):
        img = Image.new("RGB", (100, 100), color="white")
        with (
            patch.object(ocr, "_ocr_winrt", side_effect=RuntimeError("WinRT unavailable")),
            patch.object(
                ocr,
                "_ocr_tesseract",
                return_value=OCRResult(
                    text="Recognized by Tesseract",
                    confidence=0.85,
                    engine_used="tesseract",
                    duration_ms=35.0,
                ),
            ),
        ):
            res = ocr.ocr_image(img, tier_preference=["winrt", "tesseract"])
            assert res.text == "Recognized by Tesseract"
            assert res.engine_used == "tesseract"

    def test_ocr_image_all_local_fail_falls_to_tier3_llm(self, ocr):
        img = Image.new("RGB", (100, 100), color="white")
        with (
            patch.object(ocr, "_ocr_winrt", side_effect=RuntimeError("WinRT fail")),
            patch.object(ocr, "_ocr_tesseract", side_effect=RuntimeError("Tess fail")),
            patch.object(
                ocr,
                "_ocr_llm_vision",
                return_value=OCRResult(
                    text="Recognized by LLM Vision",
                    confidence=0.80,
                    engine_used="llm_vision",
                    duration_ms=120.0,
                ),
            ),
        ):
            res = ocr.ocr_image(img, tier_preference=["winrt", "tesseract", "llm_vision"])
            assert res.text == "Recognized by LLM Vision"
            assert res.engine_used == "llm_vision"

    def test_ocr_image_with_numpy_input(self, ocr):
        arr = np.ones((50, 50, 3), dtype=np.uint8) * 255
        with patch.object(ocr, "_ocr_winrt", return_value=OCRResult(
            text="NumPy test",
            confidence=0.90,
            engine_used="winrt",
            duration_ms=10.0,
        )):
            res = ocr.ocr_image(arr, tier_preference=["winrt"])
            assert res.text == "NumPy test"

    def test_ocr_image_with_file_path(self, ocr, tmp_path):
        img_path = tmp_path / "test_ocr.png"
        Image.new("RGB", (60, 60), color="blue").save(img_path)

        with patch.object(ocr, "_ocr_winrt", return_value=OCRResult(
            text="Path test",
            confidence=0.91,
            engine_used="winrt",
            duration_ms=11.0,
        )):
            res = ocr.ocr_image(str(img_path), tier_preference=["winrt"])
            assert res.text == "Path test"

    def test_ocr_image_invalid_path_raises_or_fails(self, ocr):
        with pytest.raises((FileNotFoundError, ValueError)):
            ocr.ocr_image("non_existent_file_path_12345.png")

    def test_ocr_image_total_exhaustion_returns_empty_result(self, ocr):
        img = Image.new("RGB", (40, 40), color="black")
        with (
            patch.object(ocr, "_ocr_winrt", side_effect=RuntimeError("fail 1")),
            patch.object(ocr, "_ocr_tesseract", side_effect=RuntimeError("fail 2")),
            patch.object(ocr, "_ocr_llm_vision", side_effect=RuntimeError("fail 3")),
        ):
            res = ocr.ocr_image(img, tier_preference=["winrt", "tesseract", "llm_vision"])
            assert res.text == ""
            assert res.confidence == 0.0
            assert res.engine_used == "none"


# ============================================================================
# 5. Screen Region & Clipboard OCR Tests
# ============================================================================


class TestScreenRegionAndClipboard:
    @pytest.fixture
    def ocr(self) -> VisualIntelOCR:
        return VisualIntelOCR()

    def test_ocr_screen_region_with_bbox(self, ocr):
        mock_img = Image.new("RGB", (200, 200), color="white")
        with (
            patch("PIL.ImageGrab.grab", return_value=mock_img) as mock_grab,
            patch.object(
                ocr,
                "ocr_image",
                return_value=OCRResult(
                    text="Region text",
                    confidence=0.95,
                    engine_used="winrt",
                    duration_ms=20.0,
                ),
            ) as mock_ocr_img,
        ):
            bbox = (10, 10, 110, 110)
            res = ocr.ocr_screen_region(bbox=bbox)
            assert res.text == "Region text"
            mock_grab.assert_called_once_with(bbox=bbox)
            mock_ocr_img.assert_called_once()

    def test_ocr_screen_region_full_screen(self, ocr):
        mock_img = Image.new("RGB", (800, 600), color="white")
        with (
            patch("PIL.ImageGrab.grab", return_value=mock_img) as mock_grab,
            patch.object(
                ocr,
                "ocr_image",
                return_value=OCRResult(
                    text="Full screen text",
                    confidence=0.90,
                    engine_used="winrt",
                    duration_ms=25.0,
                ),
            ),
        ):
            res = ocr.ocr_screen_region(bbox=None)
            assert res.text == "Full screen text"
            mock_grab.assert_called_once_with(bbox=None)

    def test_ocr_clipboard_success(self, ocr):
        mock_clip_img = Image.new("RGB", (150, 150), color="gray")
        with (
            patch("PIL.ImageGrab.grabclipboard", return_value=mock_clip_img),
            patch.object(
                ocr,
                "ocr_image",
                return_value=OCRResult(
                    text="Clipboard text content",
                    confidence=0.89,
                    engine_used="winrt",
                    duration_ms=18.0,
                ),
            ),
        ):
            res = ocr.ocr_clipboard()
            assert res.text == "Clipboard text content"

    def test_ocr_clipboard_empty_or_non_image(self, ocr):
        with patch("PIL.ImageGrab.grabclipboard", return_value=None):
            res = ocr.ocr_clipboard()
            assert res.text == ""
            assert res.confidence == 0.0
            assert res.engine_used == "none"
            assert res.word_count == 0


# ============================================================================
# 6. Code, Stack Trace, and URL Extraction Heuristics Tests
# ============================================================================


class TestCodeAndErrorExtraction:
    @pytest.fixture
    def ocr(self) -> VisualIntelOCR:
        return VisualIntelOCR()

    def test_extract_python_stacktrace(self, ocr):
        text = """
Traceback (most recent call last):
  File "main.py", line 42, in <module>
    compute_matrix(x)
ValueError: invalid literal for int() with base 10: 'abc'
Visit https://docs.python.org/3/library/exceptions.html for help.
"""
        info = ocr.extract_code_or_errors(text)
        assert info["has_errors"] is True
        assert len(info["stack_traces"]) > 0
        assert any("ValueError" in err for err in info["errors"])
        assert "https://docs.python.org/3/library/exceptions.html" in info["urls"]

    def test_extract_code_blocks(self, ocr):
        text = """
Here is the refactored code:
```python
def calculate_metrics(items: list[int]) -> float:
    return sum(items) / len(items)
```
Check https://github.com/example/repo for documentation.
"""
        info = ocr.extract_code_or_errors(text)
        assert info["has_code"] is True
        assert len(info["code_blocks"]) > 0
        assert "def calculate_metrics" in info["code_blocks"][0]
        assert "https://github.com/example/repo" in info["urls"]

    def test_extract_inline_code_heuristics(self, ocr):
        text = """
const express = require('express');
const app = express();
app.get('/api/health', (req, res) => res.json({ status: 'ok' }));
"""
        info = ocr.extract_code_or_errors(text)
        assert info["has_code"] is True
        assert len(info["code_blocks"]) > 0

    def test_extract_clean_text_no_code_no_errors(self, ocr):
        text = "El informe mensual de ventas muestra un crecimiento del 15% en el primer trimestre."
        info = ocr.extract_code_or_errors(text)
        assert info["has_code"] is False
        assert info["has_errors"] is False
        assert info["stack_traces"] == []
        assert info["errors"] == []
        assert info["urls"] == []
        assert info["code_blocks"] == []

    def test_extract_code_or_errors_empty_text(self, ocr):
        info = ocr.extract_code_or_errors("")
        assert info["has_code"] is False
        assert info["has_errors"] is False

    def test_extract_node_and_java_stacktraces(self, ocr):
        text = """
TypeError: Cannot read property 'foo' of undefined
    at Object.<anonymous> (/app/index.js:10:5)
    at Module._compile (internal/modules/cjs/loader.js:956:30)

Exception in thread "main" java.lang.NullPointerException
    at com.example.MyClass.run(MyClass.java:23)
    at com.example.MyClass.main(MyClass.java:10)

HTTP 500 Internal Server Error
STATUS_ACCESS_VIOLATION
"""
        info = ocr.extract_code_or_errors(text)
        assert info["has_errors"] is True
        assert len(info["stack_traces"]) >= 2
        assert any("500" in err for err in info["errors"])


# ============================================================================
# 7. Deep Coverage for Engine Internals & Fallback Handlers
# ============================================================================


class TestEngineInternalsAndCoverage:
    @pytest.fixture
    def ocr(self) -> VisualIntelOCR:
        return VisualIntelOCR()

    def test_otsu_threshold_empty_array(self):
        empty = np.array([], dtype=np.uint8)
        assert otsu_threshold(empty) == 127

    def test_preprocess_image_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Tipo de imagen no soportado"):
            preprocess_image(12345)  # type: ignore

    def test_preprocess_image_file_path_roundtrip(self, tmp_path):
        p = tmp_path / "sample.png"
        Image.new("RGB", (20, 20), color="white").save(p)
        res = preprocess_image(str(p))
        assert isinstance(res, Image.Image)

    def test_is_winrt_available_non_windows(self, ocr):
        ocr._is_windows = False
        assert ocr.is_winrt_available() is False

    def test_is_winrt_available_powershell_success(self, ocr):
        ocr._is_windows = True
        with patch("subprocess.run") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=0, stdout="2\n")
            assert ocr.is_winrt_available() is True

    def test_is_winrt_available_powershell_zero(self, ocr):
        ocr._is_windows = True
        with patch("subprocess.run") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=0, stdout="0\n")
            assert ocr.is_winrt_available() is False

    def test_is_winrt_available_powershell_exception(self, ocr):
        ocr._is_windows = True
        with patch("subprocess.run", side_effect=RuntimeError("Powershell error")):
            assert ocr.is_winrt_available() is False

    def test_ocr_winrt_powershell_success(self, ocr):
        img = Image.new("RGB", (30, 30), color="white")
        with patch("subprocess.run") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=0, stdout="Recognized Text\n", stderr="")
            res = ocr._ocr_winrt(img)
            assert res.text == "Recognized Text"
            assert res.engine_used == "winrt"
            assert res.confidence == 0.92

    def test_ocr_winrt_powershell_failure_raises(self, ocr):
        img = Image.new("RGB", (30, 30), color="white")
        with (
            patch("subprocess.run") as mock_sub,
            pytest.raises(RuntimeError, match="WinRT PowerShell failed"),
        ):
            mock_sub.return_value = MagicMock(returncode=1, stdout="", stderr="WinRT failed")
            ocr._ocr_winrt(img)

    def test_ocr_tesseract_no_path_raises(self, ocr):
        img = Image.new("RGB", (30, 30), color="white")
        with (
            patch.object(ocr, "discover_tesseract_path", return_value=None),
            pytest.raises(RuntimeError, match="Tesseract executable not found"),
        ):
            ocr._ocr_tesseract(img)

    def test_ocr_tesseract_success_with_pytesseract(self, ocr):
        img = Image.new("RGB", (30, 30), color="white")
        mock_pytess = MagicMock()
        mock_pytess.image_to_data.return_value = {
            "text": ["Hello", "World"],
            "conf": [95, 85],
        }
        mock_pytess.image_to_string.return_value = "Hello World"
        with (
            patch.object(ocr, "discover_tesseract_path", return_value="C:\\dummy\\tesseract.exe"),
            patch.dict("sys.modules", {"pytesseract": mock_pytess}),
        ):
            res = ocr._ocr_tesseract(img)
            assert res.text == "Hello World"
            assert res.engine_used == "tesseract"
            assert res.confidence == 0.90

    def test_ocr_tesseract_execution_error_raises(self, ocr):
        img = Image.new("RGB", (30, 30), color="white")
        mock_pytess = MagicMock()
        mock_pytess.image_to_data.side_effect = RuntimeError("Tess crash")
        with (
            patch.object(ocr, "discover_tesseract_path", return_value="C:\\dummy\\tesseract.exe"),
            patch.dict("sys.modules", {"pytesseract": mock_pytess}),
            pytest.raises(RuntimeError, match="Tesseract execution error"),
        ):
            ocr._ocr_tesseract(img)

    def test_ocr_llm_vision_success(self, ocr):
        img = Image.new("RGB", (30, 30), color="white")
        with patch("src.darius_ai.core.ai_client.get_ai_response", return_value=("Transcribed Text", "openai")):
            res = ocr._ocr_llm_vision(img)
            assert res.text == "Transcribed Text"
            assert res.engine_used == "llm_vision"
            assert res.confidence == 0.85

    def test_ocr_llm_vision_error_raises(self, ocr):
        img = Image.new("RGB", (30, 30), color="white")
        with (
            patch("src.darius_ai.core.ai_client.get_ai_response", side_effect=RuntimeError("AI network error")),
            pytest.raises(RuntimeError, match="LLM multimodal OCR failed"),
        ):
            ocr._ocr_llm_vision(img)

    def test_ocr_image_unknown_tier_and_no_preprocess(self, ocr):
        img = Image.new("RGB", (20, 20), color="white")
        with patch.object(ocr, "_ocr_winrt", return_value=OCRResult(
            text="Direct",
            confidence=0.9,
            engine_used="winrt",
            duration_ms=10.0,
        )):
            res = ocr.ocr_image(img, preprocess=False, tier_preference=["fake_tier", "winrt"])
            assert res.text == "Direct"

    def test_ocr_screen_region_grab_error_raises(self, ocr):
        with (
            patch("PIL.ImageGrab.grab", side_effect=RuntimeError("GDI grab error")),
            pytest.raises(RuntimeError, match="Error capturando pantalla"),
        ):
            ocr.ocr_screen_region()

    def test_ocr_clipboard_file_list_with_image(self, ocr, tmp_path):
        p = tmp_path / "clip.png"
        Image.new("RGB", (30, 30), color="white").save(p)
        with (
            patch("PIL.ImageGrab.grabclipboard", return_value=[str(p)]),
            patch.object(ocr, "ocr_image", return_value=OCRResult(
                text="File in clipboard",
                confidence=0.9,
                engine_used="winrt",
                duration_ms=12.0,
            )),
        ):
            res = ocr.ocr_clipboard()
            assert res.text == "File in clipboard"

    def test_ocr_clipboard_exception_handled_safely(self, ocr):
        with patch("PIL.ImageGrab.grabclipboard", side_effect=RuntimeError("Clip error")):
            res = ocr.ocr_clipboard()
            assert res.text == ""
            assert res.engine_used == "none"

