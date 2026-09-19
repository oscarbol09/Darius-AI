"""
test_acoustic_trigger.py — Tests Unitarios para el Detector de Aplausos y Micrófono
===================================================================================
Valida cálculo de energía RMS, resolución de dispositivos de entrada y
el ciclo de vida del detector acústico.
"""

from unittest.mock import MagicMock, patch

import numpy as np

from acoustic_trigger import (
    AcousticDoubleClapDetector,
    auto_select_best_mic,
    resolve_input_device_index,
    rms_mono,
)


def test_rms_mono_silence():
    """El RMS de silencio absoluto debe ser 0.0."""
    zeros = np.zeros(512, dtype=np.float32)
    assert rms_mono(zeros) == 0.0


def test_rms_mono_dc():
    """El RMS de una señal constante de amplitud 1.0 debe ser 1.0."""
    dc = np.ones(512, dtype=np.float32)
    assert abs(rms_mono(dc) - 1.0) < 1e-5


def test_rms_mono_stereo():
    """El RMS de un buffer 2D multi-canal debe computar el promedio mono correctamente."""
    stereo = np.ones((512, 2), dtype=np.float32)
    assert abs(rms_mono(stereo) - 1.0) < 1e-5


def test_resolve_input_device_digit():
    """Resolución de dispositivo por índice numérico."""
    with patch("sounddevice.query_devices", return_value={"name": "Micrófono USB"}):
        assert resolve_input_device_index("2") == 2


def test_resolve_input_device_substring():
    """Resolución de dispositivo por coincidencia de subcadena en el nombre."""
    devices = [
        (0, {"name": "Realtek Audio", "max_input_channels": 2}),
        (1, {"name": "HyperX SoloCast Mic", "max_input_channels": 1}),
    ]
    with patch("acoustic_trigger.get_input_devices", return_value=devices):
        assert resolve_input_device_index("solocast") == 1


def test_auto_select_best_mic_fallback():
    """Auto-selección devuelve el mejor dispositivo encontrado."""
    devices = [
        (0, {"name": "Mute Mic", "max_input_channels": 1}),
        (1, {"name": "Active Mic", "max_input_channels": 1}),
    ]

    def mock_query(idx=None):
        return devices[idx][1] if idx is not None else [d[1] for d in devices]

    with (
        patch("sounddevice.default.device", [0, 0]),
        patch("sounddevice.query_devices", side_effect=mock_query),
        patch("acoustic_trigger.get_input_devices", return_value=devices),
        patch("acoustic_trigger.probe_device_max_rms", side_effect=[0.0001, 0.05]),
    ):
        best = auto_select_best_mic()
        assert best == 1


def test_clap_detector_lifecycle():
    """Prueba el ciclo de vida start/stop de AcousticDoubleClapDetector."""
    detector = AcousticDoubleClapDetector(
        on_trigger=MagicMock(),
        spike_ratio=5.0,
        cooldown_s=0.2,
    )
    assert not detector.is_running()

    with patch("threading.Thread.start"):
        detector.start()
        assert detector.is_running()
        detector.stop()
        assert not detector.is_running()
