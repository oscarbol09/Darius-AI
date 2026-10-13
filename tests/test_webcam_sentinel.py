"""
test_webcam_sentinel.py — Pruebas unitarias para el centinela de presencia y visión de Darius AI
"""

import time
from unittest.mock import MagicMock, patch

from src.darius_ai.core.webcam_sentinel import (
    SentinelState,
    WebcamSentinel,
    get_webcam_sentinel,
)


class TestWebcamSentinelStateAndDebounce:
    def test_initial_state(self):
        sentinel = WebcamSentinel(camera_index=0, check_interval_sec=0.1)
        assert sentinel.is_running is False
        assert sentinel.is_user_present is False
        assert sentinel.person_count == 0

    def test_state_transitions_with_callbacks(self):
        sentinel = WebcamSentinel(
            camera_index=0,
            check_interval_sec=0.01,
            absence_threshold_sec=0.05,
            arrival_debounce_frames=2,
        )

        on_arrived = MagicMock()
        on_left = MagicMock()
        on_surfer = MagicMock()

        sentinel.on("on_user_arrived", on_arrived)
        sentinel.on("on_user_left", on_left)
        sentinel.on("on_shoulder_surfer", on_surfer)

        # 1. Simular primera detección (frame 1) - todavía no pasa debounce
        sentinel._process_detection(detected_count=1)
        assert sentinel.is_user_present is False
        assert not on_arrived.called

        # 2. Simular segunda detección (frame 2) - debounce superado -> usuario llega
        sentinel._process_detection(detected_count=1)
        assert sentinel.is_user_present is True
        assert on_arrived.called

        # 3. Detectar dos personas -> alerta de hombro
        sentinel._process_detection(detected_count=2)
        assert sentinel.person_count == 2
        assert on_surfer.called

        # 4. Ausencia y tiempo transcurrido -> usuario se fue
        time.sleep(0.06)
        sentinel._process_detection(detected_count=0)
        assert sentinel.is_user_present is False
        assert on_left.called

    def test_graceful_handling_when_no_camera_available(self):
        sentinel = WebcamSentinel(camera_index=99)
        # Iniciar sin cámara disponible no debe crashear
        with patch.object(sentinel, "_open_capture", return_value=None):
            sentinel.start()
            assert sentinel.is_running is False or sentinel.state == SentinelState.UNAVAILABLE
            sentinel.stop()

    def test_register_and_unregister_callbacks(self):
        sentinel = WebcamSentinel()
        cb = MagicMock()
        sentinel.on("on_user_arrived", cb)
        assert cb in sentinel._callbacks["on_user_arrived"]
        sentinel.off("on_user_arrived", cb)
        assert cb not in sentinel._callbacks["on_user_arrived"]


class TestSentinelSingleton:
    def test_get_webcam_sentinel_singleton(self):
        s1 = get_webcam_sentinel()
        s2 = get_webcam_sentinel()
        assert s1 is s2
        assert isinstance(s1, WebcamSentinel)


class TestWebcamSentinelBiometricsIntegration:
    def test_biometrics_engine_property(self):
        sentinel = WebcamSentinel()
        assert sentinel.biometrics_engine is None

        mock_engine = MagicMock()
        sentinel.biometrics_engine = mock_engine
        assert sentinel.biometrics_engine is mock_engine

    def test_async_verification_on_user_arrived_with_face_roi(self):
        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_engine.verify_face_frame.return_value = mock_result

        sentinel = WebcamSentinel(
            arrival_debounce_frames=1,
            biometrics_engine=mock_engine,
        )

        on_biometrics = MagicMock()
        sentinel.on("on_biometric_verified", on_biometrics)

        mock_roi = MagicMock()
        sentinel._process_detection(detected_count=1, face_roi=mock_roi)

        # Dar tiempo breve para que el hilo daemon ejecute la verificación
        time.sleep(0.05)

        mock_engine.verify_face_frame.assert_called_once_with(mock_roi)
        on_biometrics.assert_called_once_with(result=mock_result)

    def test_async_verification_on_user_arrived_without_face_roi(self):
        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_engine.verify_live_user.return_value = mock_result

        sentinel = WebcamSentinel(
            arrival_debounce_frames=1,
            biometrics_engine=mock_engine,
        )

        on_biometrics = MagicMock()
        sentinel.on("on_biometric_verified", on_biometrics)

        # Detección sin ROI -> fallback a verify_live_user
        sentinel._process_detection(detected_count=1, face_roi=None)

        time.sleep(0.05)

        mock_engine.verify_live_user.assert_called_once_with(
            timeout_seconds=2.0, camera_index=0
        )
        on_biometrics.assert_called_once_with(result=mock_result)

    def test_async_biometrics_none_or_exception(self):
        sentinel = WebcamSentinel(biometrics_engine=None)
        # No debe crashear si biometrics_engine es None
        sentinel._trigger_async_biometrics()

        mock_engine = MagicMock()
        mock_engine.verify_face_frame.side_effect = Exception("Worker error")
        sentinel.biometrics_engine = mock_engine
        sentinel._trigger_async_biometrics(face_roi="roi")
        time.sleep(0.05)


class TestSentinelLifecycleAndExecution:
    def test_callback_error_resilience(self):
        sentinel = WebcamSentinel()
        faulty_cb = MagicMock(side_effect=RuntimeError("Handler crashed"))
        sentinel.on("on_user_arrived", faulty_cb)
        # _emit no debe propagar la excepción
        sentinel._emit("on_user_arrived", person_count=1)
        assert faulty_cb.called

    def test_start_already_running_and_stop_already_stopped(self):
        sentinel = WebcamSentinel()
        sentinel._state = SentinelState.RUNNING
        assert sentinel.start() is True

        sentinel._state = SentinelState.STOPPED
        sentinel.stop()  # No debe lanzar error

    def test_open_capture_scenarios(self):
        sentinel = WebcamSentinel(camera_index=0)
        mock_cv2 = MagicMock()
        mock_cap = MagicMock()

        # Caso 1: Cámara abre exitosamente
        mock_cap.isOpened.return_value = True
        mock_cv2.VideoCapture.return_value = mock_cap
        with (
            patch("src.darius_ai.core.webcam_sentinel.cv2", mock_cv2),
            patch("src.darius_ai.core.webcam_sentinel._CV2_AVAILABLE", True),
        ):
            cap = sentinel._open_capture()
            assert cap is mock_cap

        # Caso 2: Cámara falla al abrir
        mock_cap.isOpened.return_value = False
        with (
            patch("src.darius_ai.core.webcam_sentinel.cv2", mock_cv2),
            patch("src.darius_ai.core.webcam_sentinel._CV2_AVAILABLE", True),
        ):
            cap = sentinel._open_capture()
            assert cap is None
            assert mock_cap.release.called

    def test_start_and_stop_full_lifecycle(self):
        sentinel = WebcamSentinel(check_interval_sec=0.01)
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True

        with (
            patch("src.darius_ai.core.webcam_sentinel._CV2_AVAILABLE", True),
            patch.object(sentinel, "_open_capture", return_value=mock_cap),
        ):
            started = sentinel.start()
            assert started is True
            assert sentinel.is_running is True
            time.sleep(0.02)
            sentinel.stop()
            assert sentinel.is_running is False

    def test_run_loop_execution_and_cleanup(self):
        sentinel = WebcamSentinel(check_interval_sec=0.01)
        mock_cap = MagicMock()
        mock_frame = MagicMock()
        mock_frame.shape = (100, 100, 3)

        def mock_read():
            sentinel._stop_event.set()
            return True, mock_frame

        mock_cap.read.side_effect = mock_read

        mock_cv2 = MagicMock()
        mock_cascade = MagicMock()
        mock_cascade.detectMultiScale.return_value = [(10, 10, 40, 40)]
        mock_cv2.CascadeClassifier.return_value = mock_cascade
        mock_cv2.cvtColor.return_value = mock_frame

        with (
            patch("src.darius_ai.core.webcam_sentinel.cv2", mock_cv2),
            patch("src.darius_ai.core.webcam_sentinel._CV2_AVAILABLE", True),
            patch.object(sentinel, "_process_detection") as mock_process,
        ):
            sentinel._run_loop(mock_cap)
            assert mock_process.called
            assert mock_cap.release.called
