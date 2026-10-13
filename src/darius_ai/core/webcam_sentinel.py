"""
webcam_sentinel.py — Centinela de Presencia Humana y Visión Perceptual para DARIUS AI
=====================================================================================
Monitorea de forma pasiva y eficiente en segundo plano el campo visual frente al PC
mediante la webcam del usuario. Arquitectura nativa de centinela visual Darius AI.

Casos de Uso:
  1. Auto-Wake / Bienvenida: detecta cuando Óscar se sienta frente al PC y ejecuta
     el protocolo de bienvenida y workspace.
  2. Auto-Sleep / Pausa: detecta cuando Óscar se aleja del escritorio durante un tiempo
     prolongado para pausar multimedia o bloquear sesión.
  3. Alerta de Hombro ("Shoulder-Surfer Alert"): alerta si detecta a más de una persona
     mirando la pantalla.
  4. Cero impacto de rendimiento: muestreo adaptativo de baja frecuencia (1 a 2 FPS)
     con consumo <1% de CPU.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from collections.abc import Callable
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.darius_ai.core.face_biometrics import FaceBiometricsEngine

log = logging.getLogger("DARIUS.Sentinel")

_CV2_AVAILABLE = False
try:
    import cv2

    _CV2_AVAILABLE = True
except ImportError:
    cv2 = None  # type: ignore
    _CV2_AVAILABLE = False


class SentinelState(str, Enum):  # noqa: UP042
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    UNAVAILABLE = "unavailable"


class WebcamSentinel:
    """
    Centinela perceptual de presencia humana mediante webcam.
    """

    def __init__(
        self,
        camera_index: int = 0,
        check_interval_sec: float = 0.8,
        absence_threshold_sec: float = 120.0,
        arrival_debounce_frames: int = 2,
        biometrics_engine: FaceBiometricsEngine | None = None,
    ):
        self._camera_index = camera_index
        self._check_interval_sec = check_interval_sec
        self._absence_threshold_sec = absence_threshold_sec
        self._arrival_debounce_frames = arrival_debounce_frames
        self._biometrics_engine = biometrics_engine

        self._state = SentinelState.STOPPED
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Métricas de presencia
        self._is_user_present = False
        self._person_count = 0
        self._last_seen_timestamp = 0.0
        self._consecutive_detections = 0

        # Suscriptores de eventos
        self._callbacks: dict[str, list[Callable[..., Any]]] = {
            "on_user_arrived": [],
            "on_user_left": [],
            "on_shoulder_surfer": [],
            "on_frame_stats": [],
            "on_biometric_verified": [],
        }

    @property
    def biometrics_engine(self) -> Any:
        """Motor biométrico facial asociado al centinela."""
        return self._biometrics_engine

    @biometrics_engine.setter
    def biometrics_engine(self, engine: Any) -> None:
        self._biometrics_engine = engine

    @property
    def is_running(self) -> bool:
        return self._state == SentinelState.RUNNING

    @property
    def state(self) -> SentinelState:
        return self._state

    @property
    def is_user_present(self) -> bool:
        return self._is_user_present

    @property
    def person_count(self) -> int:
        return self._person_count

    def on(self, event_name: str, callback: Callable[..., Any]) -> None:
        """Registra un callback para un evento del centinela."""
        with self._lock:
            if event_name in self._callbacks and callback not in self._callbacks[event_name]:
                self._callbacks[event_name].append(callback)

    def off(self, event_name: str, callback: Callable[..., Any]) -> None:
        """Elimina el registro de un callback."""
        with self._lock:
            if event_name in self._callbacks and callback in self._callbacks[event_name]:
                self._callbacks[event_name].remove(callback)

    def _emit(self, event_name: str, *args, **kwargs) -> None:
        """Emite un evento a todos los callbacks registrados de forma segura."""
        with self._lock:
            handlers = list(self._callbacks.get(event_name, []))

        for h in handlers:
            try:
                h(*args, **kwargs)
            except Exception as e:
                log.debug(f"[Sentinel] Error en handler '{event_name}': {e}")

    def _trigger_async_biometrics(self, face_roi: Any = None) -> None:
        """Dispara la verificación biométrica en un hilo secundario para no bloquear el centinela."""
        if self._biometrics_engine is None:
            return

        def _worker() -> None:
            try:
                if face_roi is not None:
                    res = self._biometrics_engine.verify_face_frame(face_roi)
                else:
                    res = self._biometrics_engine.verify_live_user(
                        timeout_seconds=2.0, camera_index=self._camera_index
                    )
                self._emit("on_biometric_verified", result=res)
            except Exception as e:
                log.debug(f"[Sentinel] Error en verificación biométrica asíncrona: {e}")

        threading.Thread(target=_worker, daemon=True, name="SentinelBiometricAuth").start()

    def _process_detection(self, detected_count: int, face_roi: Any = None) -> None:
        """
        Máquina de estados para procesar el conteo de personas detectadas en un fotograma.
        """
        now = time.time()
        self._person_count = detected_count

        if detected_count >= 1:
            self._last_seen_timestamp = now
            self._consecutive_detections += 1

            # Detectar llegada del usuario
            if not self._is_user_present and self._consecutive_detections >= self._arrival_debounce_frames:
                self._is_user_present = True
                log.info("[Sentinel] Usuario detectado frente al escritorio.")
                self._emit("on_user_arrived", person_count=detected_count)
                if self._biometrics_engine is not None:
                    self._trigger_async_biometrics(face_roi)

            # Detectar si hay más de una persona
            if detected_count >= 2:
                log.warning(f"[Sentinel] Alerta de hombro: {detected_count} personas en cuadro.")
                self._emit("on_shoulder_surfer", person_count=detected_count)

        else:
            self._consecutive_detections = 0
            # Si estaba presente y ha pasado más tiempo que el umbral de ausencia
            if self._is_user_present and (now - self._last_seen_timestamp) >= self._absence_threshold_sec:
                self._is_user_present = False
                log.info("[Sentinel] Usuario ausente del escritorio.")
                self._emit("on_user_left", duration_sec=(now - self._last_seen_timestamp))

        self._emit("on_frame_stats", count=detected_count, present=self._is_user_present, timestamp=now)

    def _open_capture(self) -> Any:
        """Intenta abrir la cámara con OpenCV."""
        if not _CV2_AVAILABLE or cv2 is None:
            return None
        try:
            cap = cv2.VideoCapture(self._camera_index)
            if cap.isOpened():
                return cap
            cap.release()
        except Exception as e:
            log.debug(f"[Sentinel] No se pudo abrir la cámara {self._camera_index}: {e}")
        return None

    def start(self) -> bool:
        """Inicia el hilo de monitoreo pasivo en segundo plano."""
        if self.is_running:
            return True

        if not _CV2_AVAILABLE:
            log.info("[Sentinel] OpenCV (cv2) no está disponible; centinela en reposo pasivo.")
            self._state = SentinelState.UNAVAILABLE
            return False

        cap = self._open_capture()
        if cap is None:
            log.info(f"[Sentinel] Cámara {self._camera_index} no disponible.")
            self._state = SentinelState.UNAVAILABLE
            return False

        self._stop_event.clear()
        self._state = SentinelState.RUNNING
        self._thread = threading.Thread(target=self._run_loop, args=(cap,), daemon=True)
        self._thread.start()
        log.info("[Sentinel] Centinela de presencia iniciado con éxito.")
        return True

    def stop(self) -> None:
        """Detiene el centinela de presencia."""
        if self._state == SentinelState.STOPPED:
            return
        self._stop_event.set()
        self._state = SentinelState.STOPPED
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None
        log.info("[Sentinel] Centinela detenido.")

    def _run_loop(self, cap: Any) -> None:
        """Bucle de ejecución con muestreo de bajo consumo."""
        try:
            # Cargar clasificador Haar en cascada estándar incluido en OpenCV para detección de rostros
            face_cascade = None
            if _CV2_AVAILABLE and cv2 is not None:
                cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                face_cascade = cv2.CascadeClassifier(cascade_path)

            while not self._stop_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    time.sleep(self._check_interval_sec)
                    continue

                person_count = 0
                face_roi = None
                if face_cascade is not None:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=4, minSize=(40, 40))
                    person_count = len(faces)
                    if person_count > 0 and len(faces[0]) == 4:
                        x, y, w, h = faces[0]
                        face_roi = gray[y : y + h, x : x + w]

                self._process_detection(person_count, face_roi=face_roi)
                time.sleep(self._check_interval_sec)

        except Exception as e:
            log.debug(f"[Sentinel] Error en bucle del centinela: {e}")
        finally:
            if cap is not None:
                with contextlib.suppress(Exception):
                    cap.release()


_GLOBAL_SENTINEL: WebcamSentinel | None = None
_GLOBAL_SENTINEL_LOCK = threading.Lock()


def get_webcam_sentinel() -> WebcamSentinel:
    """Retorna la instancia global del centinela de presencia."""
    global _GLOBAL_SENTINEL
    if _GLOBAL_SENTINEL is None:
        with _GLOBAL_SENTINEL_LOCK:
            if _GLOBAL_SENTINEL is None:
                _GLOBAL_SENTINEL = WebcamSentinel()
    return _GLOBAL_SENTINEL
