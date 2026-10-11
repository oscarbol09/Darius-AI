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
