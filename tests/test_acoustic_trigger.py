"""
test_acoustic_trigger.py — Tests Unitarios para el Detector de Aplausos y Micrófono
===================================================================================
Valida cálculo de energía RMS, resolución de dispositivos de entrada y
el ciclo de vida del detector acústico.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.darius_ai.audio.acoustic_trigger import (
    AcousticDoubleClapDetector,
    auto_select_best_mic,
    get_input_devices,
    probe_device_max_rms,
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
    with patch("src.darius_ai.audio.acoustic_trigger.get_input_devices", return_value=devices):
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
        patch("src.darius_ai.audio.acoustic_trigger.get_input_devices", return_value=devices),
        patch("src.darius_ai.audio.acoustic_trigger.probe_device_max_rms", side_effect=[0.0001, 0.05]),
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
        assert detector.start() is True  # Idempotente cuando ya está corriendo
        detector.stop()
        assert not detector.is_running()


def test_rms_mono_empty_returns_zero():
    assert rms_mono(np.array([], dtype=np.float32)) == 0.0


def test_get_input_devices_filters_output_only_and_handles_errors():
    devs = [
        {"name": "Speakers", "max_input_channels": 0},
        {"name": "USB Mic", "max_input_channels": 2},
    ]
    with patch("sounddevice.query_devices", return_value=devs):
        res = get_input_devices()
        assert len(res) == 1
        assert res[0][0] == 1

    with patch("sounddevice.query_devices", side_effect=RuntimeError("no audio")):
        assert get_input_devices() == []


def test_resolve_input_device_not_found_raises():
    with (
        patch("src.darius_ai.audio.acoustic_trigger.get_input_devices", return_value=[]),
        pytest.raises(ValueError, match="No se encontró"),
    ):
        resolve_input_device_index("inexistente")


def test_probe_device_max_rms_reads_blocks_and_handles_failure():
    mock_stream = MagicMock()
    mock_stream.__enter__.return_value = mock_stream
    mock_stream.read.return_value = (np.full((64, 1), 0.25, dtype=np.float32), False)

    with (
        patch("sounddevice.InputStream", return_value=mock_stream),
        patch("src.darius_ai.audio.acoustic_trigger.time.monotonic", side_effect=[0.0, 0.05, 1.0]),
    ):
        peak = probe_device_max_rms(0, blocksize=64, probe_s=0.1)
        assert peak == pytest.approx(0.25, abs=1e-4)

    with patch("sounddevice.InputStream", side_effect=RuntimeError("busy")):
        assert probe_device_max_rms(0, blocksize=64) is None


def test_auto_select_best_mic_with_override_and_default_ok():
    with (
        patch("src.darius_ai.audio.acoustic_trigger.resolve_input_device_index", return_value=3),
        patch("sounddevice.query_devices", return_value={"name": "Studio Mic"}),
        patch("src.darius_ai.audio.acoustic_trigger.probe_device_max_rms", return_value=0.05),
    ):
        assert auto_select_best_mic(device_override="studio") == 3

    with (
        patch("sounddevice.default.device", [2, 0]),
        patch("sounddevice.query_devices", return_value={"name": "Default Mic"}),
        patch("src.darius_ai.audio.acoustic_trigger.probe_device_max_rms", return_value=0.02),
    ):
        assert auto_select_best_mic() == 2


def test_listen_loop_detects_double_clap_and_respects_echo_suppression():
    import threading

    triggered = threading.Event()
    detector = AcousticDoubleClapDetector(
        on_trigger=triggered.set,
        spike_ratio=5.0,
        cooldown_s=1.0,
        min_double_gap_s=0.1,
        max_double_gap_s=0.6,
    )

    quiet = (np.full((64, 1), 0.0001, dtype=np.float32), False)
    clap = (np.full((64, 1), 0.5, dtype=np.float32), False)

    frames = [quiet, clap, quiet, clap, quiet]

    def fake_read(_blocksize):
        if frames:
            return frames.pop(0)
        detector.stop()
        return quiet

    mock_stream = MagicMock()
    mock_stream.__enter__.return_value = mock_stream
    mock_stream.read.side_effect = fake_read

    detector._running = True
    # Tiempos en segundos: silencio inicial -> primer aplauso -> silencio -> segundo aplauso (gap=0.25s)
    mono_times = iter([10.0, 10.0, 10.1, 10.1, 10.2, 10.2, 10.35, 10.35, 10.5, 10.5, 10.6, 10.6])
    with (
        patch("src.darius_ai.audio.acoustic_trigger.auto_select_best_mic", return_value=0),
        patch("sounddevice.InputStream", return_value=mock_stream),
        patch("src.darius_ai.audio.acoustic_trigger.time.monotonic", side_effect=lambda: next(mono_times, 12.0)),
    ):
        detector._listen_loop()

    assert triggered.wait(timeout=1.0) is True
