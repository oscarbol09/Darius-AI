"""
cyber_core_visualizer.py — Motor Gráfico HUD Cyber Core para Darius AI
======================================================================
Renderizador vectorial de alta performance a 60 FPS sobre tk.Canvas para el Cyber Core
de Darius AI. Emplea actualizaciones atómicas con canvas.coords() y geometría precomputada
en NumPy para eliminar por completo canvas.delete('all'), previniendo fugas de memoria
en el runtime Tcl y eliminando el parpadeo visual.

Geometría y Cinética:
  - Anillo exterior: 12 arcos segmentados con rotación horaria (θ₁(t) = ω₁ · t).
  - Anillo táctico intermedio: 36 marcas radiales con contrarrotación (θ₂(t) = -ω₂ · t).
  - Núcleo central Cyber Core: radio pulsante modulado por energía de audio RMS (R(t) = R₀ + k · E_rms).

Paleta de Colores Cyber Core:
  - Core Cyan (#00F0FF): IDLE / LISTENING
  - Core Amber (#E6AA38): THINKING / PROCESSING
  - Core Crimson (#C42B3B): ALERT / RECORDING
  - Core Emerald (#00FF88): SPEAKING / SUCCESS / NOMINAL
"""

from __future__ import annotations

import tkinter as tk
from typing import Any, Final

import customtkinter as ctk
import numpy as np

# =============================================================================
#  PALETA DE COLORES CYBER CORE & CONSTANTES SEMÁNTICAS
# =============================================================================
CORE_CYAN: Final[str] = "#00F0FF"  # Idle / Listening
CORE_AMBER: Final[str] = "#E6AA38"  # Thinking / Processing
CORE_CRIMSON: Final[str] = "#C42B3B"  # Alert / Recording
CORE_EMERALD: Final[str] = "#00FF88"  # Success / Nominal / Speaking

# Aliases retrocompatibles para consumidores preexistentes
ARC_CYAN: Final[str] = CORE_CYAN
TITANIUM_GOLD: Final[str] = CORE_AMBER
CRIMSON_MARK: Final[str] = CORE_CRIMSON
EMERALD_NOMINAL: Final[str] = CORE_EMERALD

STATE_COLORS: Final[dict[str, str]] = {
    "IDLE": CORE_CYAN,
    "LISTENING": CORE_CYAN,
    "THINKING": CORE_AMBER,
    "PROCESSING": CORE_AMBER,
    "SPEAKING": CORE_EMERALD,
    "ALERT": CORE_CRIMSON,
    "RECORDING": CORE_CRIMSON,
    "SUCCESS": CORE_EMERALD,
    "NOMINAL": CORE_EMERALD,
}

STATE_SPEEDS: Final[dict[str, tuple[float, float]]] = {
    "IDLE": (1.0, 1.5),
    "LISTENING": (1.2, 1.8),
    "THINKING": (2.5, 3.2),
    "PROCESSING": (2.5, 3.2),
    "SPEAKING": (1.8, 2.2),
    "ALERT": (3.5, 4.0),
    "RECORDING": (2.0, 2.4),
    "SUCCESS": (1.0, 1.2),
    "NOMINAL": (1.0, 1.2),
}


# =============================================================================
#  CÁLCULOS GEOMÉTRICOS MATEMÁTICOS (DESACOPLADOS / HEADLESS)
# =============================================================================
def compute_outer_ring_coords(
    cx: float,
    cy: float,
    radius: float,
    phase: float,
    num_arcs: int = 12,
    arc_span_deg: float = 20.0,
    points_per_arc: int = 5,
) -> np.ndarray:
    """Calcula las coordenadas de los arcos segmentados del anillo exterior.

    Rotación horaria: θ₁(t) = ω₁ · t.
    Devuelve un array NumPy de forma (num_arcs, points_per_arc * 2) con [x0, y0, x1, y1, ...].
    """
    sector_step = 2.0 * np.pi / float(num_arcs)
    sector_centers = phase + np.arange(num_arcs, dtype=np.float64) * sector_step

    span_rad = np.radians(arc_span_deg)
    arc_offsets = np.linspace(-span_rad / 2.0, span_rad / 2.0, points_per_arc, dtype=np.float64)

    # Matriz angular 2D: (num_arcs, points_per_arc)
    angles = sector_centers[:, np.newaxis] + arc_offsets[np.newaxis, :]

    xs = cx + radius * np.cos(angles)
    ys = cy + radius * np.sin(angles)

    coords = np.empty((num_arcs, points_per_arc * 2), dtype=np.float64)
    coords[:, 0::2] = xs
    coords[:, 1::2] = ys
    return coords


def compute_tick_coords(
    cx: float,
    cy: float,
    r_inner: float,
    r_outer: float,
    phase: float,
    num_ticks: int = 36,
) -> np.ndarray:
    """Calcula las coordenadas [x1, y1, x2, y2] de las marcas radiales del anillo táctico intermedio.

    Contrarrotación: θ₂(t) = -ω₂ · t (pasando phase negativa para rotación antihoraria).
    Devuelve un array NumPy de forma (num_ticks, 4).
    """
    tick_step = 2.0 * np.pi / float(num_ticks)
    angles = phase + np.arange(num_ticks, dtype=np.float64) * tick_step

    cos_a = np.cos(angles)
    sin_a = np.sin(angles)

    x1 = cx + r_inner * cos_a
    y1 = cy + r_inner * sin_a
    x2 = cx + r_outer * cos_a
    y2 = cy + r_outer * sin_a

    coords = np.empty((num_ticks, 4), dtype=np.float64)
    coords[:, 0] = x1
    coords[:, 1] = y1
    coords[:, 2] = x2
    coords[:, 3] = y2
    return coords


def compute_core_radius(
    base_radius: float,
    energy: float,
    k: float = 0.05,
    min_radius: float | None = None,
    max_radius: float | None = None,
) -> float:
    """Calcula el radio pulsante del núcleo central: R(t) = R₀ + k · E_rms con clamping opcional."""
    r = float(base_radius + k * float(energy))
    if min_radius is not None:
        r = max(float(min_radius), r)
    if max_radius is not None:
        r = min(float(max_radius), r)
    return float(r)


def compute_core_coords(
    cx: float,
    cy: float,
    radius: float,
) -> tuple[float, float, float, float]:
    """Calcula la caja delimitadora (bounding box) para dibujar un óvalo central (x0, y0, x1, y1)."""
    return (cx - radius, cy - radius, cx + radius, cy + radius)


# =============================================================================
#  COMPONENTE HUD CTK / CANVAS DE ALTO RENDIMIENTO
# =============================================================================
class CyberCoreVisualizer(ctk.CTkFrame):
    """Visualizador HUD Cyber Core vectorial a 60 FPS para Darius AI.

    Renderiza anillos cinéticos concéntricos y un núcleo reactivo sobre tk.Canvas.
    Garantiza cero canvas.delete('all') para actualización sin fugas de memoria.
    """

    DEFAULT_STATE: Final[str] = "IDLE"

    # Enlaces estáticos a los cálculos desacoplados para acceso transparente
    compute_outer_ring_coords = staticmethod(compute_outer_ring_coords)
    compute_tick_coords = staticmethod(compute_tick_coords)
    compute_core_radius = staticmethod(compute_core_radius)
    compute_core_coords = staticmethod(compute_core_coords)

    def __init__(
        self,
        master: Any = None,
        width: int = 120,
        height: int = 120,
        bg_color: str = "#0B0F19",
        **kwargs: Any,
    ) -> None:
        super().__init__(master, fg_color=bg_color, corner_radius=0, border_width=0, **kwargs)
        self.w = width
        self.h = height
        self.cx = float(width) / 2.0
        self.cy = float(height) / 2.0

        # Proporciones geométricas escaladas respecto al estándar 120x120
        scale = min(self.w, self.h) / 120.0
        self.r_outer = 50.0 * scale
        self.r_tick_outer = 42.0 * scale
        self.r_tick_inner = 34.0 * scale
        self.r0 = 16.0 * scale
        self.k = 0.05 * scale
        self.min_core_radius = 10.0 * scale
        self.max_core_radius = 28.0 * scale

        self.current_state = self.DEFAULT_STATE
        self.current_color = STATE_COLORS[self.current_state]
        self.omega_1, self.omega_2 = STATE_SPEEDS[self.current_state]

        # Lienzo Tkinter de alta velocidad
        self.canvas = tk.Canvas(
            self,
            width=self.w,
            height=self.h,
            bg=bg_color,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        # Buffers de identificadores vectoriales (creados 1 sola vez en __init__)
        self._arc_ids: list[int] = []
        self._tick_ids: list[int] = []

        # 1. Crear los 12 arcos del anillo exterior
        init_arcs = compute_outer_ring_coords(self.cx, self.cy, self.r_outer, 0.0, num_arcs=12)
        for i in range(12):
            arc_id = self.canvas.create_line(
                *init_arcs[i].tolist(),
                fill=self.current_color,
                width=max(1.5, 2.0 * scale),
                capstyle=tk.ROUND,
                joinstyle=tk.ROUND,
            )
            self._arc_ids.append(arc_id)

        # 2. Crear las 36 marcas radiales del anillo táctico intermedio
        init_ticks = compute_tick_coords(self.cx, self.cy, self.r_tick_inner, self.r_tick_outer, 0.0, num_ticks=36)
        for j in range(36):
            tick_id = self.canvas.create_line(
                *init_ticks[j].tolist(),
                fill=self.current_color,
                width=max(1.0, 1.2 * scale),
                capstyle=tk.BUTT,
            )
            self._tick_ids.append(tick_id)

        # 3. Crear el núcleo reactor central (anillo exterior pulsante y núcleo interior sólido)
        init_core_box = compute_core_coords(self.cx, self.cy, self.r0)
        self._core_id = self.canvas.create_oval(
            *init_core_box,
            outline=self.current_color,
            width=max(1.5, 2.0 * scale),
            fill="",
        )

        init_inner_box = compute_core_coords(self.cx, self.cy, self.r0 * 0.45)
        self._core_inner_id = self.canvas.create_oval(
            *init_inner_box,
            outline=self.current_color,
            fill=self.current_color,
            width=1,
        )

    def set_state(self, state: str) -> None:
        """Actualiza la paleta de colores y las velocidades angulares según el estado operativo."""
        norm_state = state.strip().upper()
        if norm_state not in STATE_COLORS:
            norm_state = self.DEFAULT_STATE

        self.current_state = norm_state
        self.current_color = STATE_COLORS[norm_state]
        self.omega_1, self.omega_2 = STATE_SPEEDS[norm_state]

        if hasattr(self, "canvas") and self.canvas is not None:
            color = self.current_color
            for arc_id in self._arc_ids:
                self.canvas.itemconfig(arc_id, fill=color)
            for tick_id in self._tick_ids:
                self.canvas.itemconfig(tick_id, fill=color)
            if hasattr(self, "_core_id") and self._core_id is not None:
                self.canvas.itemconfig(self._core_id, outline=color)
            if hasattr(self, "_core_inner_id") and self._core_inner_id is not None:
                self.canvas.itemconfig(self._core_inner_id, fill=color, outline=color)

    def update_frame(self, phase: float, energy: float = 0.0, state: str = "IDLE") -> None:
        """Actualiza atómicamente las coordenadas cinéticas de todos los elementos vectoriales.

        Garantiza prevención de fugas de memoria mediante coords() exclusivo (cero delete).
        """
        if state is not None and state.strip().upper() != self.current_state:
            self.set_state(state)

        # Cinemática de rotación: horaria para outer, antihoraria para ticks
        theta_1 = self.omega_1 * phase
        theta_2 = -self.omega_2 * phase

        # Radio pulsante del núcleo modulado por energía RMS
        r_core = compute_core_radius(
            self.r0,
            energy,
            k=self.k,
            min_radius=self.min_core_radius,
            max_radius=self.max_core_radius,
        )

        outer_coords = compute_outer_ring_coords(self.cx, self.cy, self.r_outer, theta_1, num_arcs=12)
        tick_coords = compute_tick_coords(
            self.cx,
            self.cy,
            self.r_tick_inner,
            self.r_tick_outer,
            theta_2,
            num_ticks=36,
        )
        core_coords = compute_core_coords(self.cx, self.cy, r_core)
        inner_core_coords = compute_core_coords(self.cx, self.cy, r_core * 0.45)

        if hasattr(self, "canvas") and self.canvas is not None:
            for i, arc_id in enumerate(self._arc_ids):
                self.canvas.coords(arc_id, *outer_coords[i].tolist())
            for j, tick_id in enumerate(self._tick_ids):
                self.canvas.coords(tick_id, *tick_coords[j].tolist())
            if hasattr(self, "_core_id") and self._core_id is not None:
                self.canvas.coords(self._core_id, *core_coords)
            if hasattr(self, "_core_inner_id") and self._core_inner_id is not None:
                self.canvas.coords(self._core_inner_id, *inner_core_coords)


# Alias retrocompatible
ArcReactorVisualizer = CyberCoreVisualizer
