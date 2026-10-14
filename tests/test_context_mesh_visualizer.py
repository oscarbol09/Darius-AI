"""
test_context_mesh_visualizer.py — Suite de pruebas para el Visualizador de Malla de Ondas de Contexto
=====================================================================================================
Protocolo ECC: TDD Red-Green-Refactor.
Valida:
  1. Constantes geométricas y tokens de color de la malla neón azul.
  2. Función matemática pura y headless compute_wave_mesh_coords.
  3. Comportamiento en modo headless y widget de ContextMeshVisualizer.
  4. Invariante crítica de rendimiento 60 FPS: NUNCA invocar canvas.delete('all'),
     actualizar atómicamente con canvas.coords().
  5. Ciclo de vida y animación del widget.
"""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock

import customtkinter as ctk
import numpy as np
import pytest

from src.darius_ai.gui.context_mesh_visualizer import (
    DEFAULT_HEIGHT,
    DEFAULT_NUM_LINES,
    DEFAULT_POINTS_PER_LINE,
    DEFAULT_WIDTH,
    MESH_COLORS,
    ContextMeshVisualizer,
    compute_wave_mesh_coords,
)


class TestContextMeshMathAndConstants:
    """Valida los cálculos matemáticos vectorizados con NumPy en modo headless."""

    def test_mesh_palette_and_defaults(self):
        assert len(MESH_COLORS) == 5
        # Comprobar presencia de las tonalidades cian/cielo requeridas
        assert "#00F0FF" in MESH_COLORS
        assert "#38BDF8" in MESH_COLORS
        assert "#0284C7" in MESH_COLORS
        assert "#1E3A8A" in MESH_COLORS

        assert DEFAULT_WIDTH == 400
        assert DEFAULT_HEIGHT == 120
        assert DEFAULT_NUM_LINES == 5
        assert DEFAULT_POINTS_PER_LINE == 60

    def test_compute_wave_mesh_coords_shape_and_dtype(self):
        coords = compute_wave_mesh_coords(
            width=400.0,
            height=120.0,
            phase=0.0,
            energy=0.0,
            num_lines=5,
            num_points_per_line=60,
        )
        assert isinstance(coords, np.ndarray)
        assert coords.shape == (5, 60, 2)
        assert np.issubdtype(coords.dtype, np.floating)

    def test_compute_wave_mesh_coords_custom_parameters(self):
        coords = compute_wave_mesh_coords(
            width=200.0,
            height=80.0,
            phase=1.5,
            energy=10.0,
            num_lines=3,
            num_points_per_line=30,
        )
        assert coords.shape == (3, 30, 2)

    def test_compute_wave_mesh_coords_x_span_and_monotony(self):
        width = 400.0
        coords = compute_wave_mesh_coords(
            width=width,
            height=120.0,
            phase=0.0,
            energy=0.0,
            num_lines=5,
            num_points_per_line=60,
        )
        for layer in range(5):
            xs = coords[layer, :, 0]
            assert np.isclose(xs[0], 0.0)
            assert np.isclose(xs[-1], width)
            # Debe ser estrictamente monótona creciente
            assert np.all(np.diff(xs) > 0)

    def test_compute_wave_mesh_coords_y_bounds(self):
        height = 120.0
        coords = compute_wave_mesh_coords(
            width=400.0,
            height=height,
            phase=0.5,
            energy=5.0,
            num_lines=5,
            num_points_per_line=60,
        )
        for layer in range(5):
            ys = coords[layer, :, 1]
            assert np.all(ys >= 0.0)
            assert np.all(ys <= height)

    def test_compute_wave_mesh_coords_deterministic(self):
        c1 = compute_wave_mesh_coords(400.0, 120.0, phase=0.42, energy=15.0)
        c2 = compute_wave_mesh_coords(400.0, 120.0, phase=0.42, energy=15.0)
        assert np.array_equal(c1, c2)

    def test_compute_wave_mesh_coords_phase_variation(self):
        c1 = compute_wave_mesh_coords(400.0, 120.0, phase=0.0, energy=0.0)
        c2 = compute_wave_mesh_coords(400.0, 120.0, phase=1.0, energy=0.0)
        # Las coordenadas Y deben haber variado por la onda móvil
        assert not np.allclose(c1[:, :, 1], c2[:, :, 1])

    def test_compute_wave_mesh_coords_energy_amplitude_scaling(self):
        c_quiet = compute_wave_mesh_coords(400.0, 120.0, phase=0.0, energy=0.0)
        c_energetic = compute_wave_mesh_coords(400.0, 120.0, phase=0.0, energy=80.0)
        # La varianza o rango de amplitud vertical en energía alta debe ser mayor
        var_quiet = np.var(c_quiet[:, :, 1])
        var_energetic = np.var(c_energetic[:, :, 1])
        assert var_energetic > var_quiet

    def test_compute_wave_mesh_coords_layer_depth_offset(self):
        coords = compute_wave_mesh_coords(400.0, 120.0, phase=0.0, energy=0.0, num_lines=5)
        # Las distintas capas deben tener diferentes promedios o fases en Y
        means = [np.mean(coords[layer, :, 1]) for layer in range(5)]
        assert len(set(np.round(means, 2))) > 1


class TestContextMeshVisualizerWidget:
    """Valida la creación, ciclo de vida e invariantes de rendimiento del widget."""

    @pytest.fixture
    def widget(self):
        """Crea una instancia real del widget o la destruye limpiamente."""
        try:
            root = ctk.CTk()
            root.withdraw()
            viz = ContextMeshVisualizer(root, width=400, height=120)
        except Exception as exc:
            pytest.skip(f"Tkinter/Tcl no disponible en este entorno: {exc}")
        yield viz
        with contextlib.suppress(Exception):
            root.destroy()

    def test_widget_canvas_items_initialized(self, widget):
        # 5 líneas de capa de profundidad creadas
        assert len(widget.line_ids) == 5
        # Múltiples puntos de partículas creados
        assert len(widget.dot_ids) >= 5
        # Canvas sin bordes
        assert int(widget.canvas.cget("highlightthickness")) == 0
        assert int(widget.canvas.cget("bd")) == 0

    def test_update_frame_uses_coords_zero_delete_all(self, widget):
        canvas = widget.canvas
        canvas.delete = MagicMock()
        canvas.coords = MagicMock(wraps=canvas.coords)

        for frame in range(4):
            widget.update_frame(phase=frame * 0.1, energy=10.0)

        # Invariante crítica ECC: NUNCA se invoca canvas.delete('all')
        canvas.delete.assert_not_called()

        # canvas.coords debe actualizarse para cada línea y cada partícula por frame
        expected_items_per_frame = len(widget.line_ids) + len(widget.dot_ids)
        assert canvas.coords.call_count == 4 * expected_items_per_frame

    def test_animation_lifecycle(self, widget):
        assert not widget.is_animating
        widget.start_animation(interval_ms=16)
        assert widget.is_animating
        widget.set_energy(25.0)
        assert widget.energy == 25.0
        widget.stop_animation()
        assert not widget.is_animating
