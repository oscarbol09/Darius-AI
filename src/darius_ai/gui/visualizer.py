import tkinter as tk

import customtkinter as ctk
import numpy as np

import gui_theme as theme


class HighPerfWaveVisualizer(ctk.CTkFrame):
    """
    Visualizador vectorial de ondas a 60 FPS con múltiples armónicos sinusoidales vectorizados en NumPy.
    Utiliza actualizaciones atómicas con canvas.coords() eliminando canvas.delete('all')
    para evitar fugas de memoria en el intérprete Tcl y parpadeos visuales.
    """

    def __init__(self, master, width: int = 170, height: int = 36, num_points: int = 80, **kwargs):
        super().__init__(master, fg_color=theme.BG_HEADER, corner_radius=theme.RADIUS_MD, border_width=0, **kwargs)
        self.w = width
        self.h = height
        self.num_points = num_points
        self.cy = height / 2.0

        self.canvas = tk.Canvas(self, width=self.w, height=self.h, bg=theme.BG_HEADER, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True, padx=4, pady=2)

        # Precalcular proyecciones de coordenadas X estáticas
        self.x_screen = np.linspace(0, self.w, self.num_points, dtype=np.float32)
        self.x_norm = np.linspace(0, 4.0 * np.pi, self.num_points, dtype=np.float32)

        # Buffers preasignados de coordenadas (x0, y0, x1, y1...) para evitar reallocaciones
        self._buf_primary = np.empty((self.num_points, 2), dtype=np.float32)
        self._buf_primary[:, 0] = self.x_screen
        self._buf_primary[:, 1] = self.cy

        self._buf_secondary = np.empty((self.num_points, 2), dtype=np.float32)
        self._buf_secondary[:, 0] = self.x_screen
        self._buf_secondary[:, 1] = self.cy

        self._buf_tertiary = np.empty((self.num_points, 2), dtype=np.float32)
        self._buf_tertiary[:, 0] = self.x_screen
        self._buf_tertiary[:, 1] = self.cy

        # Crear líneas vectoriales una sola vez durante la inicialización
        self.line_tertiary = self.canvas.create_line(
            *self._buf_tertiary.ravel().tolist(),
            fill=theme.ACCENT_EMERALD,
            width=1.0,
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND,
        )
        self.line_secondary = self.canvas.create_line(
            *self._buf_secondary.ravel().tolist(),
            fill=theme.ACCENT_PURPLE,
            width=1.5,
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND,
        )
        self.line_primary = self.canvas.create_line(
            *self._buf_primary.ravel().tolist(),
            fill=theme.ACCENT_PRIMARY,
            width=2.0,
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND,
        )

        self._phase = 0.0

    def update_frame(self, state: str, audio_energy: float = 0.0):
        """
        Calcula la proyección matemática en NumPy y actualiza las líneas atómicamente.
        state: 'IDLE' | 'LISTENING' | 'THINKING' | 'SPEAKING' | 'MUTED'
        """
        self._phase += 0.07
        p = self._phase
        x = self.x_norm
        cy = self.cy

        if state == "LISTENING":
            amp = float(np.clip(audio_energy / 2500.0 * 12.0 + 2.0, 2.0, 14.0))
            y1 = cy + amp * np.sin(2.0 * x + p) * np.cos(0.8 * x - p * 0.4)
            y2 = cy + (amp * 0.65) * np.sin(3.2 * x - p * 1.2 + 1.0)
            y3 = cy + (amp * 0.35) * np.cos(1.5 * x + p * 0.8)
            self.canvas.itemconfig(self.line_primary, fill=theme.ACCENT_PRIMARY)
            self.canvas.itemconfig(self.line_secondary, fill=theme.ACCENT_PURPLE)
            self.canvas.itemconfig(self.line_tertiary, fill=theme.ACCENT_EMERALD)

        elif state == "SPEAKING":
            y1 = cy + 9.0 * np.sin(2.5 * x + p * 1.6) * np.sin(0.7 * x + p * 0.3)
            y2 = cy + 6.0 * np.cos(3.0 * x - p * 1.3)
            y3 = cy + 3.0 * np.sin(1.2 * x + p * 0.5)
            self.canvas.itemconfig(self.line_primary, fill=theme.ACCENT_PRIMARY)
            self.canvas.itemconfig(self.line_secondary, fill="#60A5FA")
            self.canvas.itemconfig(self.line_tertiary, fill=theme.ACCENT_PURPLE)

        elif state == "THINKING":
            y1 = cy + 6.0 * np.sin(5.5 * x + p * 2.2) * np.cos(2.0 * x - p)
            y2 = cy + 4.0 * np.sin(4.0 * x - p * 1.8 + 0.5)
            y3 = cy + 2.5 * np.cos(2.5 * x + p * 1.2)
            self.canvas.itemconfig(self.line_primary, fill=theme.ACCENT_PURPLE)
            self.canvas.itemconfig(self.line_secondary, fill="#C084FC")
            self.canvas.itemconfig(self.line_tertiary, fill="#F472B6")

        elif state == "MUTED":
            y1 = cy + 0.5 * np.sin(1.0 * x + p * 0.2)
            y2 = cy + 0.3 * np.cos(1.0 * x + p * 0.2)
            y3 = cy + np.zeros_like(x)
            self.canvas.itemconfig(self.line_primary, fill=theme.TEXT_MUTED)
            self.canvas.itemconfig(self.line_secondary, fill=theme.BORDER_SUBTLE)
            self.canvas.itemconfig(self.line_tertiary, fill=theme.BG_SIDEBAR)

        else:  # IDLE
            y1 = cy + 2.5 * np.sin(1.8 * x + p * 0.6)
            y2 = cy + 1.5 * np.cos(1.2 * x - p * 0.4 + 0.8)
            y3 = cy + 0.8 * np.sin(0.8 * x + p * 0.3)
            self.canvas.itemconfig(self.line_primary, fill=theme.ACCENT_PRIMARY)
            self.canvas.itemconfig(self.line_secondary, fill=theme.ACCENT_PURPLE)
            self.canvas.itemconfig(self.line_tertiary, fill=theme.ACCENT_EMERALD)

        self._buf_primary[:, 1] = y1
        self._buf_secondary[:, 1] = y2
        self._buf_tertiary[:, 1] = y3

        # Actualizaciones atómicas en Tcl
        self.canvas.coords(self.line_tertiary, *self._buf_tertiary.ravel().tolist())
        self.canvas.coords(self.line_secondary, *self._buf_secondary.ravel().tolist())
        self.canvas.coords(self.line_primary, *self._buf_primary.ravel().tolist())
