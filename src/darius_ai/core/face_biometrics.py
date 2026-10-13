"""
face_biometrics.py — Face Biometrics & Sentry Authentication para DARIUS AI
=================================================================================
Módulo de visión por computador y autenticación biométrica nativo de Darius AI.
Proporciona verificación facial basada en descriptores LBPH (Local Binary Patterns Histograms)
con contingencia degradada de 3 niveles, fallback seguro de dependencias y cálculo
matemático de confianza calibrado (eliminando bugs de porcentajes negativos).
"""

from __future__ import annotations

import contextlib
import json
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger("DARIUS.Biometrics")

_CV2_AVAILABLE = False
_CV2_FACE_AVAILABLE = False

try:
    import cv2
    import numpy as np

    _CV2_AVAILABLE = True
    if hasattr(cv2, "face") and hasattr(cv2.face, "LBPHFaceRecognizer_create"):
        _CV2_FACE_AVAILABLE = True
except ImportError:
    cv2 = None  # type: ignore
    np = None  # type: ignore
    _CV2_AVAILABLE = False
    _CV2_FACE_AVAILABLE = False


@dataclass
class BiometricResult:
    """Resultado estructurado de autenticación biométrica facial."""

    verified: bool = False
    confidence: float = 0.0
    user_name: str = "desconocido"
    distance: float = 999.0
    status: str = "CHALLENGE_REQUIRED"


class FaceBiometricsEngine:
    """
    Motor biométrico de alta precisión para Darius AI con soporte LBPH y fallback resiliente.
    """

    def __init__(
        self,
        data_dir: str | Path | None = None,
        model_path: str | Path | None = None,
        user_name: str = "señor",
        distance_threshold: float = 65.0,
    ) -> None:
        if data_dir is None:
            self._data_dir = Path.home() / ".darius_ai" / "biometrics"
        else:
            self._data_dir = Path(data_dir)

        self._model_path = Path(model_path) if model_path else self._data_dir / "face_model.yml"
        self._labels_path = self._data_dir / "labels.json"
        self._user_name = user_name
        self._distance_threshold = distance_threshold

        self._lock = threading.Lock()
        self._is_trained = False
        self._label_map: dict[int, str] = {1: self._user_name}
        self._recognizer: Any = None

        self._is_available = _CV2_AVAILABLE and _CV2_FACE_AVAILABLE
        if self._is_available and cv2 is not None:
            try:
                self._recognizer = cv2.face.LBPHFaceRecognizer_create()
                self._load_existing_model()
            except Exception as e:
                log.warning(f"[Biometrics] Error inicializando reconocedor LBPH: {e}")
                self._is_available = False

    @property
    def is_available(self) -> bool:
        """Indica si OpenCV y el módulo cv2.face están disponibles."""
        return self._is_available

    @property
    def is_trained(self) -> bool:
        """Indica si el modelo biométrico está entrenado y cargado en memoria."""
        return self._is_trained

    @property
    def user_name(self) -> str:
        return self._user_name

    @property
    def distance_threshold(self) -> float:
        return self._distance_threshold

    def calculate_confidence(self, distance: float) -> float:
        """
        Calcula la confianza en rango [0.0, 1.0] a partir de la distancia Chi-cuadrada de LBPH.
        Fórmula matemática calibrada:
            confidence = max(0.0, min(1.0, 1.0 - (distance / 100.0)))
        Corrige la lógica invertida y valores negativos del script original de J.A.R.V.I.S.
        """
        if distance < 0.0:
            return 1.0
        return max(0.0, min(1.0, 1.0 - (float(distance) / 100.0)))

    def is_distance_verified(self, distance: float) -> bool:
        """Determina si la distancia se encuentra dentro del umbral de verificación (< 65.0)."""
        return distance < self._distance_threshold

    def _load_existing_model(self) -> bool:
        """Carga el modelo y mapa de etiquetas si existen en disco."""
        if not self._is_available or self._recognizer is None:
            return False

        if not self._model_path.exists():
            return False

        try:
            with self._lock:
                self._recognizer.read(str(self._model_path))
                if self._labels_path.exists():
                    with open(self._labels_path, encoding="utf-8") as f:
                        raw_map = json.load(f)
                        self._label_map = {int(k): str(v) for k, v in raw_map.items()}
                self._is_trained = True
                log.info(f"[Biometrics] Perfil facial cargado desde {self._model_path}")
                return True
        except Exception as e:
            log.warning(f"[Biometrics] No se pudo leer el modelo existente {self._model_path}: {e}")
            self._is_trained = False
            return False

    def enroll_face(
        self,
        images: list[Any],
        label_id: int = 1,
        user_name: str | None = None,
    ) -> bool:
        """
        Registra un conjunto de imágenes de entrenamiento para un usuario y guarda el modelo.
        """
        if not self._is_available or self._recognizer is None:
            log.warning("[Biometrics] OpenCV/cv2.face no disponible. No se puede enrolar.")
            return False

        if not images:
            log.warning("[Biometrics] No se proporcionaron imágenes para enrolamiento.")
            return False

        target_user = user_name or self._user_name

        try:
            with self._lock:
                labels = [label_id] * len(images)
                labels_arr = np.array(labels, dtype=np.int32) if np is not None else labels

                self._recognizer.train(images, labels_arr)
                self._label_map[label_id] = target_user

                # Asegurar directorio de datos
                self._data_dir.mkdir(parents=True, exist_ok=True)
                self._recognizer.save(str(self._model_path))

                with open(self._labels_path, "w", encoding="utf-8") as f:
                    json.dump(self._label_map, f, ensure_ascii=False, indent=2)

                self._is_trained = True
                log.info(f"[Biometrics] Perfil biométrico enrolado con éxito para '{target_user}'.")
                return True
        except Exception as e:
            log.error(f"[Biometrics] Error durante enrolamiento facial: {e}")
            return False

    def verify_face_frame(self, gray_frame_roi: Any) -> BiometricResult:
        """
        Verifica un recorte en escala de grises de un rostro frente al modelo cargado.
        """
        if not self._is_available:
            return BiometricResult(
                verified=False,
                confidence=0.0,
                user_name="desconocido",
                distance=999.0,
                status="ENGINE_UNAVAILABLE",
            )

        if gray_frame_roi is None or gray_frame_roi == "":
            return BiometricResult(
                verified=False,
                confidence=0.0,
                user_name="desconocido",
                distance=999.0,
                status="INVALID_FRAME",
            )

        if not self._is_trained or self._recognizer is None:
            return BiometricResult(
                verified=False,
                confidence=0.0,
                user_name="desconocido",
                distance=999.0,
                status="MODEL_NOT_TRAINED",
            )

        try:
            with self._lock:
                label_id, distance = self._recognizer.predict(gray_frame_roi)

            distance = float(distance)
            confidence = self.calculate_confidence(distance)

            if self.is_distance_verified(distance):
                matched_user = self._label_map.get(label_id, self._user_name)
                return BiometricResult(
                    verified=True,
                    confidence=confidence,
                    user_name=matched_user,
                    distance=distance,
                    status="VERIFIED",
                )
            else:
                return BiometricResult(
                    verified=False,
                    confidence=confidence,
                    user_name="desconocido",
                    distance=distance,
                    status="CHALLENGE_REQUIRED",
                )

        except Exception as e:
            log.debug(f"[Biometrics] Error al clasificar fotograma facial: {e}")
            return BiometricResult(
                verified=False,
                confidence=0.0,
                user_name="desconocido",
                distance=999.0,
                status="CHALLENGE_REQUIRED",
            )

    def verify_live_user(
        self,
        timeout_seconds: float = 3.0,
        camera_index: int = 0,
    ) -> BiometricResult:
        """
        Autenticación en vivo mediante cámara con contingencia de 3 niveles:
          - Tier 1: Biometric match from camera -> status="VERIFIED"
          - Tier 2: Timeout / poca luz / desconocido -> status="CHALLENGE_REQUIRED"
          - Tier 3: Cámara no disponible / headless -> status="CAMERA_UNAVAILABLE"
        """
        if not _CV2_AVAILABLE or cv2 is None:
            return BiometricResult(
                verified=False,
                confidence=0.0,
                user_name="desconocido",
                distance=999.0,
                status="CAMERA_UNAVAILABLE",
            )

        cap = None
        try:
            cap = cv2.VideoCapture(camera_index)
            if cap is None or not cap.isOpened():
                return BiometricResult(
                    verified=False,
                    confidence=0.0,
                    user_name="desconocido",
                    distance=999.0,
                    status="CAMERA_UNAVAILABLE",
                )
        except Exception as e:
            log.debug(f"[Biometrics] Error abriendo cámara {camera_index}: {e}")
            return BiometricResult(
                verified=False,
                confidence=0.0,
                user_name="desconocido",
                distance=999.0,
                status="CAMERA_UNAVAILABLE",
            )

        # Cargar clasificador de rostros en cascada
        face_cascade = None
        try:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            face_cascade = cv2.CascadeClassifier(cascade_path)
        except Exception as e:
            log.debug(f"[Biometrics] No se pudo instanciar CascadeClassifier: {e}")

        start_time = time.time()
        fallback_result = BiometricResult(
            verified=False,
            confidence=0.0,
            user_name="desconocido",
            distance=999.0,
            status="CHALLENGE_REQUIRED",
        )

        try:
            while (time.time() - start_time) < timeout_seconds:
                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.04)
                    continue

                if face_cascade is not None:
                    try:
                        if hasattr(frame, "shape") and len(getattr(frame, "shape", [])) == 3:
                            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        else:
                            gray = frame
                        faces = face_cascade.detectMultiScale(
                            gray,
                            scaleFactor=1.2,
                            minNeighbors=4,
                            minSize=(40, 40),
                        )
                        for x, y, w, h in faces:
                            roi = gray[y : y + h, x : x + w] if hasattr(gray, "__getitem__") else gray
                            res = self.verify_face_frame(roi)
                            fallback_result = res
                            if res.verified:
                                return res
                    except Exception as e:
                        log.debug(f"[Biometrics] Error evaluando frame en vivo: {e}")

                time.sleep(0.04)

        finally:
            if cap is not None:
                with contextlib.suppress(Exception):
                    cap.release()

        # Tier 2: Timeout o rostro no verificado
        return fallback_result

    def get_biometric_greeting(self, result: BiometricResult) -> str:
        """Genera el saludo táctico vocal de J.A.R.V.I.S. según el resultado biométrico."""
        if result.verified:
            return f"Identidad biométrica confirmada: {result.user_name}. Protocolos de mando autorizados."
        elif result.status == "CHALLENGE_REQUIRED":
            return (
                "Advertencia de seguridad: Sujeto no identificado o iluminación insuficiente. "
                "Desafío de autenticación secundario requerido."
            )
        elif result.status == "CAMERA_UNAVAILABLE":
            return (
                "Sensores ópticos no disponibles. "
                "Autenticación biométrica degradada a protocolo de contingencia."
            )
        else:
            return f"Estado de autenticación biométrica: {result.status}. Acceso restringido."


def get_biometric_greeting(result: BiometricResult) -> str:
    """Función de conveniencia para generar el saludo vocal de Darius AI."""
    engine = FaceBiometricsEngine()
    return engine.get_biometric_greeting(result)


_GLOBAL_BIOMETRICS_ENGINE: FaceBiometricsEngine | None = None
_GLOBAL_BIOMETRICS_LOCK = threading.Lock()


def get_face_biometrics_engine() -> FaceBiometricsEngine:
    """Retorna la instancia singleton global del motor de biometría facial."""
    global _GLOBAL_BIOMETRICS_ENGINE
    if _GLOBAL_BIOMETRICS_ENGINE is None:
        with _GLOBAL_BIOMETRICS_LOCK:
            if _GLOBAL_BIOMETRICS_ENGINE is None:
                _GLOBAL_BIOMETRICS_ENGINE = FaceBiometricsEngine()
    return _GLOBAL_BIOMETRICS_ENGINE
