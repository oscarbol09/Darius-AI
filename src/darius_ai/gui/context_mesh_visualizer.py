"""
context_mesh_visualizer.py — Visualizador Vectorial de Malla de Ondas de Contexto para Darius AI
================================================================================================
Renderizador vectorial de alta performance a 60 FPS sobre tk.Canvas para el visualizador
de malla de contexto 3D ondulante de Darius AI v8.5.

Geometría y Cinética:
  - 5 capas de profundidad continuas en tonalidades cian/cielo neón (#00F0FF, #38BDF8, #0284C7, #1E3A8A).
  - Ondas de interferencia sinusoidal vectorizadas en NumPy:
      y(x, t) = A_1 · sin(k_1 · x - ω_1 · t) + A_2 · cos(k_2 · x + ω_2 · t) + turbulencia · E_rms
  - Puntos de partículas neón proyectados sobre los nodos clave de la malla.
  - Actualizaciones atómicas exclusivas mediante canvas.coords(), eliminando por completo
    canvas.delete('all') para prevenir fugas de memoria en el runtime Tcl y parpadeos.
"""

from __future__ import annotations

import contextlib
import logging
import tkinter as tk
from typing import Any, Final

import customtkinter as ctk
import numpy as np

from src.darius_ai.gui import gui_theme as theme

log = logging.getLogger("darius.context_mesh")

# =============================================================================
#  CONSTANTES GEOMÉTRICAS Y PALETA DE COLORES
# =============================================================================
DEFAULT_WIDTH: Final[int] = 400
DEFAULT_HEIGHT: Final[int] = 120
DEFAULT_NUM_LINES: Final[int] = 5
DEFAULT_POINTS_PER_LINE: Final[int] = 60

# Gradiente de profundidad: Del cian neón frontal a los azules profundos
MESH_COLORS: Final[tuple[str, ...]] = (
    "#00F0FF",  # Capa 0 (frontal brillante)
    "#38BDF8",  # Capa 1 (cielo intermedio)
    "#0284C7",  # Capa 2 (azul primario)
    "#1E3A8A",  # Capa 3 (azul profundo)
    "#0F2A4A",  # Capa 4 (fondo de perspectiva)
)

LINE_WIDTHS: Final[tuple[float, ...]] = (2.0, 1.6, 1.2, 1.0, 0.8)


# =============================================================================
#  CÁLCULO MATEMÁTICO VECTORIZADO (HEADLESS & DETERMINISTA)
# =============================================================================
def compute_wave_mesh_coords(
    width: float = float(DEFAULT_WIDTH),
    height: float = float(DEFAULT_HEIGHT),
    phase: float = 0.0,
    energy: float = 0.0,
    num_lines: int = DEFAULT_NUM_LINES,
    num_points_per_line: int = DEFAULT_POINTS_PER_LINE,
) -> np.ndarray:
    """Calcula las coordenadas de la malla de ondas 3D con perspectiva de profundidad.

    Aplica la ecuación de interferencia multiarmónica:
        y(x, t) = y_center(i) + A_1 · sin(k_1 · x - ω_1 · t_i) + A_2 · cos(k_2 · x + ω_2 · t_i) + ruido(E_rms)

    Retorna:
        np.ndarray de forma (num_lines, num_points_per_line, 2) con dtype float64.
        coords[layer, pt, 0] es X, coords[layer, pt, 1] es Y.
    """
    w = max(10.0, float(width))
    h = max(10.0, float(height))
    n_lines = max(1, int(num_lines))
    n_pts = max(2, int(num_points_per_line))

    # Coordenadas X continuas a lo largo del ancho del canvas
    xs = np.linspace(0.0, w, n_pts, dtype=np.float64)
    # Espacio normalizado angular [0, 4π]
    u = (xs / w) * (4.0 * np.pi)

    # Preasignar array tridimensional de salida
    coords = np.empty((n_lines, n_pts, 2), dtype=np.float64)
    coords[:, :, 0] = xs[np.newaxis, :]

    # Escalado de energía RMS y turbulencia acústica
    clamped_energy = max(0.0, float(energy))
    amp_boost = 1.0 + min(clamped_energy / 40.0, 2.5)
    noise_amp = min(clamped_energy * 0.08, h * 0.15)

    for i in range(n_lines):
        # Factor de profundidad z_i en [0.0, 1.0]
        z_i = float(i) / float(max(1, n_lines - 1)) if n_lines > 1 else 0.0

        # Perspectiva 3D: capas profundas tienen distinta línea base y menor oscilación
        y_center = h * (0.35 + 0.30 * z_i)
        a_base = (h * 0.12) * (1.0 - 0.25 * z_i)

        a1 = a_base * amp_boost
        a2 = a1 * 0.55

        # Parámetros de onda de interferencia
        k1, k2 = 1.8, 3.2
        w1, w2 = 1.0, 1.35
        t_i = phase + i * 0.45

        wave_primary = a1 * np.sin(k1 * u - w1 * t_i)
        wave_secondary = a2 * np.cos(k2 * u + w2 * t_i)

        # Turbulencia pseudo-armónica determinista
        turb = np.sin(5.5 * u - 2.0 * t_i) * np.cos(2.8 * u + t_i) * noise_amp

        y = y_center + wave_primary + wave_secondary + turb
        coords[i, :, 1] = np.clip(y, 0.0, h)

    return coords


# =============================================================================
#  WIDGET CUSTOMTKINTER VECTORIAL 60 FPS
# =============================================================================
class ContextMeshVisualizer(ctk.CTkFrame):
    """Visualizador HUD de malla de ondas de contexto a 60 FPS con Tkinter Canvas.

    Mantiene buffers preasignados y actualiza exclusivamente mediante canvas.coords()
    sin invocar canvas.delete('all'), asegurando fluidez perfecta y cero fugas de memoria.
    """

    def __init__(
        self,
        master: Any,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        num_lines: int = DEFAULT_NUM_LINES,
        num_points: int = DEFAULT_POINTS_PER_LINE,
        **kwargs: Any,
    ) -> None:
        bg_card = kwargs.pop("fg_color", theme.BG_HEADER)
        super().__init__(
            master,
            fg_color=bg_card,
            corner_radius=theme.RADIUS_MD,
            border_width=1,
            border_color=theme.BORDER_SUBTLE,
            **kwargs,
        )
        self.w = int(width)
        self.h = int(height)
        self.num_lines = int(num_lines)
        self.num_points = int(num_points)

        # Estado cinético y animación
        self._phase = 0.0
        self._phase_step = 0.045
        self._energy = 0.0
        self._is_animating = False
        self._after_id: str | None = None

        # Integración con Canvas sin bordes
        self.canvas = tk.Canvas(
            self,
            width=self.w,
            height=self.h,
            bg=theme.BG_HEADER,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True, padx=4, pady=4)

        # Coordenadas iniciales
        initial_coords = compute_wave_mesh_coords(
            width=float(self.w),
            height=float(self.h),
            phase=0.0,
            energy=0.0,
            num_lines=self.num_lines,
            num_points_per_line=self.num_points,
        )

        # 1. Crear líneas vectoriales una sola vez
        self._line_ids: list[int] = []
        for i in range(self.num_lines):
            color = MESH_COLORS[i % len(MESH_COLORS)]
            line_w = LINE_WIDTHS[i % len(LINE_WIDTHS)]
            flat_pts = initial_coords[i].ravel().tolist()
            lid = self.canvas.create_line(
                *flat_pts,
                fill=color,
                width=line_w,
                capstyle=tk.ROUND,
                joinstyle=tk.ROUND,
                smooth=True,
            )
            self._line_ids.append(lid)

        # 2. Crear puntos de partículas neón
        self._dot_ids: list[int] = []
        self._particle_indices: list[tuple[int, int]] = []
        # Distribuir partículas en nodos clave (capas frontales)
        step_pts = max(4, self.num_points // 8)
        for layer in range(min(3, self.num_lines)):
            for pt_idx in range(step_pts // 2, self.num_points, step_pts):
                self._particle_indices.append((layer, pt_idx))
                x = initial_coords[layer, pt_idx, 0]
                y = initial_coords[layer, pt_idx, 1]
                r = 2.0 if layer == 0 else 1.5
                dot_color = MESH_COLORS[layer]
                did = self.canvas.create_oval(
                    x - r,
                    y - r,
                    x + r,
                    y + r,
                    fill=dot_color,
                    outline="",
                )
                self._dot_ids.append(did)

    @property
    def is_animating(self) -> bool:
        """Indica si el bucle de animación 60 FPS está en curso."""
        return self._is_animating

    @property
    def energy(self) -> float:
        """Nivel actual de energía acústica RMS."""
        return self._energy

    @property
    def line_ids(self) -> list[int]:
        """Identificadores de las líneas de capa de profundidad en tk.Canvas."""
        return self._line_ids

    @property
    def dot_ids(self) -> list[int]:
        """Identificadores de las partículas en tk.Canvas."""
        return self._dot_ids

    def set_energy(self, energy: float) -> None:
        """Establece la modulación de energía RMS para amplificar la onda."""
        self._energy = max(0.0, float(energy))

    def update_frame(self, phase: float | None = None, energy: float | None = None) -> None:
        """Actualiza atómicamente todos los elementos de la malla vía canvas.coords()."""
        if phase is None:
            self._phase += self._phase_step
            p = self._phase
        else:
            p = phase
            self._phase = phase

        e = self._energy if energy is None else float(energy)

        coords = compute_wave_mesh_coords(
            width=float(self.w),
            height=float(self.h),
            phase=p,
            energy=e,
            num_lines=self.num_lines,
            num_points_per_line=self.num_points,
        )

        # Actualización atómica de líneas
        for i, lid in enumerate(self._line_ids):
            flat_pts = coords[i].ravel().tolist()
            self.canvas.coords(lid, *flat_pts)

        # Actualización atómica de partículas
        for (layer, pt_idx), did in zip(self._particle_indices, self._dot_ids, strict=False):
            x = coords[layer, pt_idx, 0]
            y = coords[layer, pt_idx, 1]
            r = 2.0 if layer == 0 else 1.5
            self.canvas.coords(did, x - r, y - r, x + r, y + r)

    def start_animation(self, interval_ms: int = 16) -> None:
        """Inicia el bucle de renderizado periódico a 60 FPS."""
        if self._is_animating:
            return
        self._is_animating = True

        def _tick() -> None:
            if not self._is_animating:
                return
            self.update_frame()
            self._after_id = self.after(interval_ms, _tick)

        self._after_id = self.after(interval_ms, _tick)

    def stop_animation(self) -> None:
        """Detiene de forma segura el bucle de animación."""
        self._is_animating = False
        if self._after_id is not None:
            with contextlib.suppress(Exception):
                self.after_cancel(self._after_id)
            self._after_id = None
