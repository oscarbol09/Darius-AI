"""
test_cyber_core_visualizer.py — Suite de pruebas para el HUD Cyber Core de Darius AI
====================================================================================
Valida la arquitectura del HUD Cyber Core de Darius AI:
  1. Paleta de colores Cyber Core (CORE_CYAN, CORE_AMBER, CORE_CRIMSON, CORE_EMERALD) y aliases.
  2. Geometría matemática desacoplada y verificable en modo headless:
     - Anillo exterior segmentado: 12 arcos con rotación horaria.
     - Anillo táctico intermedio: 36 marcas radiales con contrarrotación.
     - Núcleo central (Cyber Core): radio pulsante modulado por energía RMS.
  3. Estados operativos (IDLE, LISTENING, THINKING, SPEAKING, ALERT).
  4. Ciclo de vida del widget y prevención de fugas de memoria:
     - Actualizaciones atómicas exclusivas mediante canvas.coords().
     - Cero invocaciones a canvas.delete('all').
  5. Compatibilidad retroactiva con ArcReactorVisualizer.
"""

import contextlib
from unittest.mock import MagicMock

import customtkinter as ctk
import numpy as np
import pytest

from src.darius_ai.gui.arc_reactor_visualizer import (
    ArcReactorVisualizer as ProxyArcReactorVisualizer,
)
from src.darius_ai.gui.cyber_core_visualizer import (
    ARC_CYAN,
    CORE_AMBER,
    CORE_CRIMSON,
    CORE_CYAN,
    CORE_EMERALD,
    CRIMSON_MARK,
    EMERALD_NOMINAL,
    STATE_COLORS,
    TITANIUM_GOLD,
    ArcReactorVisualizer,
    CyberCoreVisualizer,
    compute_core_coords,
    compute_core_radius,
    compute_outer_ring_coords,
    compute_tick_coords,
)


class TestCyberCorePaletteAndConstants:
    """Verifica los tokens de color Cyber Core y constantes del HUD."""

    def test_cyber_core_color_palette_hex_values(self):
        assert CORE_CYAN.upper() == "#00F0FF"
        assert CORE_AMBER.upper() == "#E6AA38"
        assert CORE_CRIMSON.upper() == "#C42B3B"
        assert CORE_EMERALD.upper() == "#00FF88"

    def test_legacy_color_token_aliases(self):
        assert ARC_CYAN == CORE_CYAN
        assert TITANIUM_GOLD == CORE_AMBER
        assert CRIMSON_MARK == CORE_CRIMSON
        assert EMERALD_NOMINAL == CORE_EMERALD

    def test_state_colors_mapping(self):
        assert STATE_COLORS["IDLE"] == CORE_CYAN
        assert STATE_COLORS["LISTENING"] == CORE_CYAN
        assert STATE_COLORS["THINKING"] == CORE_AMBER
        assert STATE_COLORS["ALERT"] == CORE_CRIMSON
        assert STATE_COLORS["SPEAKING"] == CORE_EMERALD


class TestHeadlessGeometryCalculations:
    """Valida los cálculos matemáticos vectorizados con NumPy en modo headless."""

    def test_outer_ring_geometry_12_arcs(self):
        cx, cy, radius = 60.0, 60.0, 50.0
        phase = 0.0
        coords = compute_outer_ring_coords(cx, cy, radius, phase, num_arcs=12, points_per_arc=5)

        # 12 arcos, cada uno con 5 puntos (x, y) -> 10 coordenadas
        assert len(coords) == 12
        assert coords.shape == (12, 10)

        # Todos los puntos deben estar en el radio especificado respecto al centro
        for arc in coords:
            xs = arc[0::2]
            ys = arc[1::2]
            distances = np.hypot(xs - cx, ys - cy)
            assert np.allclose(distances, radius, atol=1e-3)

    def test_outer_ring_clockwise_rotation(self):
        cx, cy, radius = 60.0, 60.0, 50.0
        coords_0 = compute_outer_ring_coords(cx, cy, radius, phase=0.0, num_arcs=12)
        coords_step = compute_outer_ring_coords(cx, cy, radius, phase=np.pi / 6.0, num_arcs=12)

        # Ángulo medio del primer arco en phase 0
        mid_0 = coords_0[0, :2]
        angle_0 = np.arctan2(mid_0[1] - cy, mid_0[0] - cx)

        # Ángulo medio del primer arco tras avance positivo de fase (horario en canvas)
        mid_step = coords_step[0, :2]
        angle_step = np.arctan2(mid_step[1] - cy, mid_step[0] - cx)

        # En coordenadas de pantalla (Y hacia abajo), ángulo creciente rota en sentido horario
        diff = (angle_step - angle_0) % (2.0 * np.pi)
        assert np.isclose(diff, np.pi / 6.0, atol=1e-3)

    def test_middle_tactical_tick_ring_36_marks(self):
        cx, cy = 60.0, 60.0
        r_inner, r_outer = 34.0, 42.0
        phase = 0.0
        ticks = compute_tick_coords(cx, cy, r_inner, r_outer, phase, num_ticks=36)

        assert len(ticks) == 36
        assert ticks.shape == (36, 4)

        for tick in ticks:
            x1, y1, x2, y2 = tick
            d1 = np.hypot(x1 - cx, y1 - cy)
            d2 = np.hypot(x2 - cx, y2 - cy)
            assert np.isclose(d1, r_inner, atol=1e-3)
            assert np.isclose(d2, r_outer, atol=1e-3)

            # Ambos extremos deben ser colineales con el centro (mismo rayo radial)
            theta1 = np.arctan2(y1 - cy, x1 - cx)
            theta2 = np.arctan2(y2 - cy, x2 - cx)
            assert np.isclose(theta1, theta2, atol=1e-3)

    def test_tactical_ticks_counter_rotation(self):
        cx, cy = 60.0, 60.0
        r_inner, r_outer = 34.0, 42.0
        ticks_0 = compute_tick_coords(cx, cy, r_inner, r_outer, phase=0.0, num_ticks=36)
        # Contrarrotación con fase negativa
        ticks_counter = compute_tick_coords(cx, cy, r_inner, r_outer, phase=-np.pi / 4.0, num_ticks=36)

        theta_0 = np.arctan2(ticks_0[0, 1] - cy, ticks_0[0, 0] - cx)
        theta_counter = np.arctan2(ticks_counter[0, 1] - cy, ticks_counter[0, 0] - cx)
        diff = (theta_counter - theta_0) % (2.0 * np.pi)
        assert np.isclose(diff, 2.0 * np.pi - np.pi / 4.0, atol=1e-3)

    def test_central_core_pulsing_formula(self):
        r0 = 16.0
        k = 0.05
        # Energía cero -> radio base r0
        assert compute_core_radius(r0, energy=0.0, k=k) == r0

        # Energía positiva -> r0 + k * energy
        energy = 100.0
        expected = r0 + k * energy  # 16 + 5 = 21.0
        assert np.isclose(compute_core_radius(r0, energy=energy, k=k), expected)

        # Clamping de radio máximo y mínimo
        assert compute_core_radius(r0, energy=1000.0, k=k, max_radius=25.0) == 25.0
        assert compute_core_radius(r0, energy=-100.0, k=k, min_radius=12.0) == 12.0

    def test_central_core_bounding_box_coords(self):
        cx, cy, radius = 60.0, 60.0, 18.0
        coords = compute_core_coords(cx, cy, radius)
        assert coords == (42.0, 42.0, 78.0, 78.0)


class TestCyberCoreStateTransitions:
    """Verifica la máquina de estados del HUD y actualización de paletas/velocidades."""

    def test_default_state_is_idle(self):
        assert CyberCoreVisualizer.DEFAULT_STATE == "IDLE"

    def test_state_color_and_speed_updates(self):
        visualizer = CyberCoreVisualizer.__new__(CyberCoreVisualizer)
        visualizer.current_state = "IDLE"
        visualizer.current_color = CORE_CYAN
        visualizer.omega_1 = 1.0
        visualizer.omega_2 = 1.5
        visualizer.canvas = None

        visualizer.set_state("THINKING")
        assert visualizer.current_state == "THINKING"
        assert visualizer.current_color == CORE_AMBER
        assert visualizer.omega_1 > 1.0
        assert visualizer.omega_2 > 1.5

        visualizer.set_state("ALERT")
        assert visualizer.current_state == "ALERT"
        assert visualizer.current_color == CORE_CRIMSON

        visualizer.set_state("SPEAKING")
        assert visualizer.current_state == "SPEAKING"
        assert visualizer.current_color == CORE_EMERALD

        # Soporte para minúsculas
        visualizer.set_state("listening")
        assert visualizer.current_state == "LISTENING"
        assert visualizer.current_color == CORE_CYAN

        # Estado desconocido cae a DEFAULT_STATE
        visualizer.set_state("INVALID_STATE")
        assert visualizer.current_state == CyberCoreVisualizer.DEFAULT_STATE
        assert visualizer.current_color == CORE_CYAN


class TestCyberCoreWidgetRendering:
    """Verifica el renderizado de alta performance y prevención de fugas de memoria."""

    @pytest.fixture
    def widget(self):
        """Crea una instancia real del widget o la destruye limpiamente."""
        try:
            root = ctk.CTk()
            root.withdraw()
            viz = CyberCoreVisualizer(root, width=120, height=120)
        except Exception as exc:
            pytest.skip(f"Tkinter/Tcl no disponible en este entorno: {exc}")
        yield viz
        with contextlib.suppress(Exception):
            root.destroy()

    def test_widget_canvas_items_initialized(self, widget):
        # 12 arcos externos creados
        assert len(widget._arc_ids) == 12
        # 36 marcas radiales creadas
        assert len(widget._tick_ids) == 36
        # Núcleo creado
        assert widget._core_id is not None
        assert widget._core_inner_id is not None

    def test_update_frame_uses_coords_zero_delete_all(self, widget):
        # Monitorear llamadas sobre el canvas
        canvas = widget.canvas
        canvas.delete = MagicMock()
        canvas.coords = MagicMock(wraps=canvas.coords)

        # Ejecutar 5 frames de animación a 60 FPS
        for frame in range(5):
            phase = frame * 0.05
            widget.update_frame(phase=phase, energy=20.0, state="LISTENING")

        # Invariante crítica ECC: NUNCA se invoca canvas.delete('all')
        canvas.delete.assert_not_called()

        # canvas.coords debe haber sido llamado para 12 arcos + 36 ticks + 2 núcleos por frame
        expected_calls_per_frame = 12 + 36 + 2
        assert canvas.coords.call_count == 5 * expected_calls_per_frame

    def test_update_frame_state_switch(self, widget):
        widget.update_frame(phase=0.1, energy=10.0, state="THINKING")
        assert widget.current_state == "THINKING"
        assert widget.current_color == CORE_AMBER

        widget.update_frame(phase=0.2, energy=10.0, state="ALERT")
        assert widget.current_state == "ALERT"
        assert widget.current_color == CORE_CRIMSON

    def test_custom_dimensions_scaling(self):
        try:
            root = ctk.CTk()
            root.withdraw()
            viz200 = CyberCoreVisualizer(root, width=200, height=200)
        except Exception as exc:
            pytest.skip(f"Tkinter/Tcl no disponible en este entorno: {exc}")
        assert viz200.w == 200
        assert viz200.h == 200
        assert viz200.cx == 100.0
        assert viz200.cy == 100.0
        assert viz200.r_outer > 50.0  # Escalado proporcionalmente
        with contextlib.suppress(Exception):
            root.destroy()


class TestBackwardsCompatibility:
    """Verifica que ArcReactorVisualizer sea un alias perfecto de CyberCoreVisualizer."""

    def test_arc_reactor_alias(self):
        assert ArcReactorVisualizer is CyberCoreVisualizer
        assert ProxyArcReactorVisualizer is CyberCoreVisualizer
