"""Tests unitarios para HighPerfWaveVisualizer (60 FPS sin delete('all'))."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import customtkinter as ctk
import pytest

from src.darius_ai.gui.visualizer import HighPerfWaveVisualizer


@pytest.mark.parametrize(
    "state, energy",
    [
        ("LISTENING", 1500.0),
        ("SPEAKING", 800.0),
        ("THINKING", 500.0),
        ("MUTED", 0.0),
        ("IDLE", 0.0),
    ],
    ids=["listening", "speaking", "thinking", "muted", "idle"],
)
def test_wave_visualizer_states_update_atomically(state: str, energy: float):
    viz = HighPerfWaveVisualizer.__new__(HighPerfWaveVisualizer)
    viz.w = 170
    viz.h = 36
    viz.num_points = 40
    viz.cy = 18.0
    viz._phase = 0.0

    import numpy as np

    viz.x_screen = np.linspace(0, viz.w, viz.num_points, dtype=np.float32)
    viz.x_norm = np.linspace(0, 4.0 * np.pi, viz.num_points, dtype=np.float32)
    viz._buf_primary = np.zeros((viz.num_points, 2), dtype=np.float32)
    viz._buf_secondary = np.zeros((viz.num_points, 2), dtype=np.float32)
    viz._buf_tertiary = np.zeros((viz.num_points, 2), dtype=np.float32)
    viz.line_primary = 1
    viz.line_secondary = 2
    viz.line_tertiary = 3
    viz.canvas = MagicMock()

    viz.update_frame(state, audio_energy=energy)

    viz.canvas.delete.assert_not_called()
    assert viz.canvas.itemconfig.call_count == 3
    assert viz.canvas.coords.call_count == 3


def test_wave_visualizer_init_with_mocked_widgets():
    mock_canvas = MagicMock()
    mock_canvas.create_line.side_effect = [1, 2, 3]
    with (
        patch.object(ctk.CTkFrame, "__init__", return_value=None),
        patch("src.darius_ai.gui.visualizer.tk.Canvas", return_value=mock_canvas),
    ):
        viz = HighPerfWaveVisualizer(master=MagicMock(), width=170, height=36, num_points=20)
        assert viz.line_tertiary == 1
        assert viz.line_secondary == 2
        assert viz.line_primary == 3
        viz.update_frame("LISTENING", audio_energy=1000.0)
        assert mock_canvas.coords.call_count == 3
