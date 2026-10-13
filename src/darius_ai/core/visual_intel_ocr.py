"""
visual_intel_ocr.py — Motor de Inteligencia Visual y Reconocimiento Óptico (OCR)
================================================================================
Proporciona capacidades avanzadas de extracción de texto, análisis de código,
inspección de errores de pantalla y lectura de portapapeles para Darius AI.

Estructura y Tiers:
  - Preprocesamiento de imagen: Escala de grises, contraste adaptativo y binarización Otsu.
  - Tier 1: Windows Native WinRT OCR (WinRT nativo o PowerShell Windows.Media.Ocr).
  - Tier 2: Tesseract OCR (descubrimiento dinámico en PATH y Program Files).
  - Tier 3: Multimodal LLM fallback a través de ScreenVisionEngine.
  - Heurísticas de extracción para stacktraces, bloques de código y URLs.
"""

from __future__ import annotations

import base64
import contextlib
import io
import logging
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageGrab, ImageOps

log = logging.getLogger("DARIUS.VisualIntelOCR")

# ============================================================================
# Dataclass de Resultado OCR
# ============================================================================


@dataclass
class OCRResult:
    """Resultado estructurado de extracción óptica de caracteres."""

    text: str
    confidence: float
    engine_used: str
    duration_ms: float
    word_count: int = 0
    lines: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.lines and self.text:
            self.lines = [line.strip() for line in self.text.splitlines() if line.strip()]
        if self.word_count == 0 and self.text:
            self.word_count = len(self.text.split())


# ============================================================================
# Algoritmos de Preprocesamiento de Imagen
# ============================================================================


def otsu_threshold(gray_arr: np.ndarray) -> int:
    """
    Calcula el umbral óptimo de binarización de Otsu maximizando la varianza entre clases.
    Si existe una meseta de varianza máxima (valle bimodal plano), promedia los candidatos.
    """
    if gray_arr.size == 0:
        return 127

    hist, _ = np.histogram(gray_arr, bins=256, range=(0, 256))
    total = gray_arr.size
    sum_total = float(np.dot(np.arange(256), hist))

    current_max = 0.0
    best_thresholds: list[int] = []
    sum_back = 0.0
    weight_back = 0.0

    for t in range(256):
        weight_back += hist[t]
        if weight_back == 0:
            continue
        weight_fore = total - weight_back
        if weight_fore == 0:
            break

        sum_back += t * hist[t]
        mean_back = sum_back / weight_back
        mean_fore = (sum_total - sum_back) / weight_fore

        # Varianza entre clases: w0 * w1 * (mu0 - mu1)^2
        var_between = weight_back * weight_fore * ((mean_back - mean_fore) ** 2)
        if var_between > current_max + 1e-5:
            current_max = var_between
            best_thresholds = [t]
        elif abs(var_between - current_max) <= 1e-5:
            best_thresholds.append(t)

    if not best_thresholds:
        return 127
    return int(round(float(np.mean(best_thresholds))))


def preprocess_image(image_input: Image.Image | np.ndarray | str | Path) -> Image.Image:
    """
    Pipeline de preprocesamiento para maximizar la tasa de acierto OCR:
      1. Conversión a PIL Image (si es ndarray o path).
      2. Conversión a escala de grises ('L').
      3. Mejora adaptativa de contraste (autocontraste / autolevel).
      4. Binarización de Otsu.
    """
    # 1. Cargar imagen en PIL
    if isinstance(image_input, (str, Path)):
        p = Path(image_input)
        if not p.is_file():
            raise FileNotFoundError(f"Archivo de imagen no encontrado: {image_input}")
        img = Image.open(p)
    elif isinstance(image_input, np.ndarray):
        img = Image.fromarray(image_input)
    elif isinstance(image_input, Image.Image):
        img = image_input
    else:
        raise ValueError(f"Tipo de imagen no soportado: {type(image_input)}")

    # 2. Conversión a escala de grises
    gray_img = img.convert("L") if img.mode != "L" else img.copy()

    # 3. Mejora adaptativa de contraste
    enhanced = ImageOps.autocontrast(gray_img, cutoff=2)

    # 4. Binarización de Otsu
    arr = np.array(enhanced)
    thresh = otsu_threshold(arr)
    bin_arr = np.where(arr > thresh, 255, 0).astype(np.uint8)

    return Image.fromarray(bin_arr)


# ============================================================================
# Motor Principal de OCR Visual Intel
# ============================================================================


class VisualIntelOCR:
    """
    Motor multicanal de reconocimiento óptico de caracteres (OCR) con failover automático:
      - Tier 1: Windows Native WinRT OCR
      - Tier 2: Tesseract OCR
      - Tier 3: Multimodal LLM fallback
    """

    DEFAULT_TIER_PREFERENCE = ("winrt", "tesseract", "llm_vision")

    # Rutas estándar de instalación de Tesseract en Windows
    KNOWN_TESSERACT_PATHS = (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Tools\Tesseract-OCR\tesseract.exe",
    )

    def __init__(self) -> None:
        self._is_windows = platform.system() == "Windows"
        self._tesseract_cmd: str | None = None
        self._tesseract_checked = False

    def discover_tesseract_path(self) -> str | None:
        """
        Descubre la ruta de ejecución de Tesseract dinámicamente en:
          1. Variable de entorno TESSERACT_CMD
          2. PATH del sistema (shutil.which)
          3. Ubicaciones estándar en Program Files
        """
        env_cmd = os.environ.get("TESSERACT_CMD")
        if env_cmd and os.path.isfile(env_cmd):
            return env_cmd

        which_cmd = shutil.which("tesseract")
        if which_cmd:
            return which_cmd

        for known in self.KNOWN_TESSERACT_PATHS:
            if os.path.isfile(known):
                return known

        return None

    def is_winrt_available(self) -> bool:
        """Determina si WinRT OCR nativo está disponible en el host."""
        if not self._is_windows:
            return False

        # Comprobar módulo python winrt
        try:
            import winrt.windows.media.ocr  # type: ignore # noqa: F401

            return True
        except ImportError:
            pass

        # Comprobar disponibilidad de PowerShell Windows.Media.Ocr
        try:
            cmd = (
                "[Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType = WindowsRuntime] | Out-Null; "
                "Write-Output ([Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages.Count)"
            )
            res = subprocess.run(  # noqa: S603
                ["powershell", "-NoProfile", "-Command", cmd],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=4,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip() and int(res.stdout.strip()) > 0:
                return True
        except Exception as e:
            log.debug(f"[VisualIntelOCR] Error verificando WinRT en PowerShell: {e}")

        return False

    def get_available_tiers(self) -> list[str]:
        """Retorna los tiers de OCR disponibles en el entorno actual."""
        tiers: list[str] = []
        if self.is_winrt_available():
            tiers.append("winrt")

        if self.discover_tesseract_path() is not None:
            tiers.append("tesseract")

        # Tier 3 (LLM multimodal) siempre está disponible como fallback
        tiers.append("llm_vision")
        return tiers

    # ------------------------------------------------------------------------
    # Motores Individuales de OCR (Tier 1, Tier 2, Tier 3)
    # ------------------------------------------------------------------------

    def _ocr_winrt(self, image: Image.Image) -> OCRResult:
        """Ejecuta OCR vía Windows Native WinRT."""
        start_time = time.perf_counter()

        # 1. Probar módulo winrt directo si existe
        try:
            import winrt.windows.graphics.imaging as imaging  # type: ignore # noqa: F401
            import winrt.windows.media.ocr as winrt_ocr  # type: ignore

            # Si el módulo existe y funciona directamente
            engine = winrt_ocr.OcrEngine.try_create_from_user_profile_languages()
            if engine is not None:
                # Si winrt python está disponible, ejecutarlo
                pass
        except Exception as e:
            log.debug(f"[VisualIntelOCR] winrt directo no disponible: {e}")

        # 2. Ejecutar mediante script PowerShell optimizado
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            image.save(tmp_path, format="PNG")
            full_path = Path(tmp_path).resolve()

            ps_script = f"""
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType = WindowsRuntime] | Out-Null

$asTaskGen = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {{
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.IsGenericMethod
}})[0]

Function AwaitWinRT($op, $t) {{
    $m = $asTaskGen.MakeGenericMethod($t)
    $task = $m.Invoke($null, @($op))
    $task.Wait()
    $task.Result
}}

$filePath = '{full_path}'
$file = AwaitWinRT ([Windows.Storage.StorageFile]::GetFileFromPathAsync($filePath)) ([Windows.Storage.StorageFile])
$modeRead = [Windows.Storage.FileAccessMode]::Read
$stream = AwaitWinRT ($file.OpenAsync($modeRead)) ([Windows.Storage.Streams.IRandomAccessStream])
$dec = AwaitWinRT ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) `
    ([Windows.Graphics.Imaging.BitmapDecoder])
$bmp = AwaitWinRT ($dec.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if (-not $engine) {{
    $langs = [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages
    if ($langs.Count -gt 0) {{
        $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($langs[0])
    }}
}}
if (-not $engine) {{
    Write-Error "No WinRT engine found"
    exit 1
}}
$res = AwaitWinRT ($engine.RecognizeAsync($bmp)) ([Windows.Media.Ocr.OcrResult])
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Write-Output $res.Text
"""
            run_res = subprocess.run(  # noqa: S603
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],  # noqa: S607
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=12,
                check=False,
            )

            if run_res.returncode != 0:
                raise RuntimeError(f"WinRT PowerShell failed: {run_res.stderr.strip()}")

            recognized_text = run_res.stdout.strip()
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            return OCRResult(
                text=recognized_text,
                confidence=0.92 if recognized_text else 0.0,
                engine_used="winrt",
                duration_ms=round(duration_ms, 2),
            )
        finally:
            if os.path.exists(tmp_path):
                with contextlib.suppress(OSError):
                    os.remove(tmp_path)

    def _ocr_tesseract(self, image: Image.Image) -> OCRResult:
        """Ejecuta OCR vía Tesseract dinámico."""
        start_time = time.perf_counter()
        tess_path = self.discover_tesseract_path()
        if not tess_path:
            raise RuntimeError("Tesseract executable not found on system")

        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = tess_path

        try:
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            words = []
            confs = []
            for word, conf in zip(data.get("text", []), data.get("conf", []), strict=False):
                w_str = str(word).strip()
                if w_str:
                    words.append(w_str)
                    try:
                        c_val = float(conf)
                        if c_val >= 0:
                            confs.append(c_val / 100.0)
                    except ValueError:
                        pass

            mean_conf = float(np.mean(confs)) if confs else 0.80
            recognized_text = pytesseract.image_to_string(image).strip()
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            return OCRResult(
                text=recognized_text,
                confidence=round(mean_conf, 2),
                engine_used="tesseract",
                duration_ms=round(duration_ms, 2),
            )
        except Exception as e:
            raise RuntimeError(f"Tesseract execution error: {e}") from e

    def _ocr_llm_vision(self, image: Image.Image) -> OCRResult:
        """Ejecuta OCR de fallback mediante ScreenVisionEngine y LLM multimodal."""
        start_time = time.perf_counter()

        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=85)
        img_bytes = buffer.getvalue()
        b64_str = base64.b64encode(img_bytes).decode("utf-8")

        prompt = (
            "Transcribe verbatim todo el texto legible presente en esta imagen.\n"
            "Reglas estrictas:\n"
            "- Devuelve únicamente el texto reconocido, sin introducciones ni explicaciones.\n"
            "- Mantén saltos de línea y formateo original del código o documento.\n"
            "- Si no hay texto legible, responde con una cadena vacía."
        )

        try:
            from src.darius_ai.core.ai_client import get_ai_response

            response_text, _ = get_ai_response(prompt, image_b64=b64_str)
            recognized_text = (response_text or "").strip()
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            return OCRResult(
                text=recognized_text,
                confidence=0.85 if recognized_text else 0.0,
                engine_used="llm_vision",
                duration_ms=round(duration_ms, 2),
            )
        except Exception as e:
            raise RuntimeError(f"LLM multimodal OCR failed: {e}") from e

    # ------------------------------------------------------------------------
    # Métodos Públicos de OCR
    # ------------------------------------------------------------------------

    def ocr_image(
        self,
        image_input: Any,
        preprocess: bool = True,
        tier_preference: list[str] | tuple[str, ...] | None = None,
    ) -> OCRResult:
        """
        Extrae texto de una imagen (PIL, ndarray, o ruta de archivo).
        Intenta los motores configurados según el orden de preferencia.
        """
        # Cargar imagen inicial
        if isinstance(image_input, (str, Path)):
            p = Path(image_input)
            if not p.is_file():
                raise FileNotFoundError(f"Imagen no encontrada: {image_input}")
            img = Image.open(p)
        elif isinstance(image_input, np.ndarray):
            img = Image.fromarray(image_input)
        elif isinstance(image_input, Image.Image):
            img = image_input
        else:
            raise ValueError(f"Entrada de imagen no soportada: {type(image_input)}")

        # Aplicar preprocesamiento si está habilitado
        working_img = preprocess_image(img) if preprocess else img

        tiers = list(tier_preference or self.DEFAULT_TIER_PREFERENCE)
        errors: list[str] = []

        start_time = time.perf_counter()
        for tier in tiers:
            tier_norm = tier.lower().strip()
            try:
                if tier_norm == "winrt":
                    return self._ocr_winrt(working_img)
                elif tier_norm == "tesseract":
                    return self._ocr_tesseract(working_img)
                elif tier_norm in ("llm_vision", "screen_vision", "llm"):
                    return self._ocr_llm_vision(working_img)
                else:
                    log.warning(f"[VisualIntelOCR] Tier desconocido ignorado: {tier}")
            except Exception as e:
                log.debug(f"[VisualIntelOCR] Falló tier '{tier}': {e}")
                errors.append(f"{tier}: {e}")

        total_duration = (time.perf_counter() - start_time) * 1000.0
        log.warning(f"[VisualIntelOCR] Todos los tiers OCR fallaron: {', '.join(errors)}")
        return OCRResult(
            text="",
            confidence=0.0,
            engine_used="none",
            duration_ms=round(total_duration, 2),
            word_count=0,
            lines=[],
        )

    def ocr_screen_region(
        self,
        bbox: tuple[int, int, int, int] | None = None,
        preprocess: bool = True,
    ) -> OCRResult:
        """
        Captura una región de pantalla (o pantalla completa si bbox es None) y realiza OCR.
        bbox format: (left, top, right, bottom).
        """
        try:
            img = ImageGrab.grab(bbox=bbox)
        except Exception as e:
            log.error(f"[VisualIntelOCR] Fallo al capturar región de pantalla: {e}")
            raise RuntimeError(f"Error capturando pantalla: {e}") from e

        return self.ocr_image(img, preprocess=preprocess)

    def ocr_clipboard(self, preprocess: bool = True) -> OCRResult:
        """
        Lee una imagen desde el portapapeles del sistema y extrae su texto mediante OCR.
        Si el portapapeles no contiene una imagen, devuelve un OCRResult vacío y seguro.
        """
        try:
            clip_content = ImageGrab.grabclipboard()
            if isinstance(clip_content, Image.Image):
                return self.ocr_image(clip_content, preprocess=preprocess)
            elif isinstance(clip_content, list):
                # En Windows, a veces grabclipboard devuelve una lista de rutas de archivo copiadas
                for item in clip_content:
                    p = Path(item)
                    if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff"):
                        return self.ocr_image(p, preprocess=preprocess)
        except Exception as e:
            log.debug(f"[VisualIntelOCR] Error leyendo portapapeles: {e}")

        return OCRResult(
            text="",
            confidence=0.0,
            engine_used="none",
            duration_ms=0.0,
            word_count=0,
            lines=[],
        )

    # ------------------------------------------------------------------------
    # Heurísticas de Detección de Código, Errores y URLs
    # ------------------------------------------------------------------------

    def extract_code_or_errors(self, text: str) -> dict[str, Any]:
        """
        Analiza el texto reconocido para extraer stack traces, códigos de error,
        bloques de código y URLs.
        """
        if not text:
            return {
                "has_code": False,
                "has_errors": False,
                "code_blocks": [],
                "errors": [],
                "stack_traces": [],
                "urls": [],
            }

        # 1. Extracción de URLs
        url_pattern = re.compile(r"https?://[^\s<>\"'()]+", re.IGNORECASE)
        urls = url_pattern.findall(text)

        # 2. Detección de Stack Traces
        stack_traces: list[str] = []
        stacktrace_patterns = [
            # Python Traceback
            re.compile(
                r"(?:Traceback\s+\(most\s+recent\s+call\s+last\):[\s\S]+?(?:\w+Error|\w+Exception):[^\n]+)",
                re.MULTILINE,
            ),
            # Node / JS Stacktrace
            re.compile(r"(?:(?:Error|TypeError|ReferenceError):[^\n]+\n(?:\s+at\s+[^\n]+\n?)+)", re.MULTILINE),
            # Java / C# Exception
            re.compile(r"(?:Exception in thread [^\n]+\n(?:\s+at\s+[^\n]+\n?)+)", re.MULTILINE),
        ]
        for p in stacktrace_patterns:
            matches = p.findall(text)
            stack_traces.extend([m.strip() for m in matches if m.strip()])

        # 3. Detección de Códigos y Mensajes de Error
        error_names_pattern = re.compile(
            r"\b(?:[A-Z]\w*(?:Error|Exception|Fault|Panic|Crash)|STATUS_\w+|ERR_\w+|HTTP\s+[45]\d{2})\b[:\s]?[^\n]*",
            re.MULTILINE,
        )
        detected_errors = [e.strip() for e in error_names_pattern.findall(text) if e.strip()]

        # 4. Detección y Extracción de Bloques de Código
        code_blocks: list[str] = []
        # Bloques con fences Markdown (```...```)
        fenced_pattern = re.compile(r"```(?:\w+)?\n([\s\S]+?)```")
        fenced_matches = fenced_pattern.findall(text)
        code_blocks.extend([c.strip() for c in fenced_matches if c.strip()])

        # Heurísticas de sintaxis de programación si no hay fences
        if not code_blocks:
            code_keywords = [
                r"\b(?:def|class|import|from\s+\w+\s+import|async\s+def|return|lambda)\b",
                r"\b(?:function|const|let|var|console\.log|export\s+default)\b",
                r"\b(?:public\s+class|private\s+void|protected|interface|package\s+)\b",
                r"\b(?:fn\s+main|impl\s+\w+|let\s+mut|println!)\b",
            ]
            has_syntax = any(re.search(kw, text) for kw in code_keywords)
            if has_syntax:
                code_blocks.append(text.strip())

        has_code = len(code_blocks) > 0
        has_errors = (len(stack_traces) > 0) or (len(detected_errors) > 0)

        return {
            "has_code": has_code,
            "has_errors": has_errors,
            "code_blocks": code_blocks,
            "errors": detected_errors,
            "stack_traces": stack_traces,
            "urls": urls,
        }


# Instancia Singleton
visual_intel_ocr = VisualIntelOCR()

__all__ = [
    "OCRResult",
    "VisualIntelOCR",
    "otsu_threshold",
    "preprocess_image",
    "visual_intel_ocr",
]
