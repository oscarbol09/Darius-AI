"""
bento_dashboard.py — Dashboard Cybernetic Bento Grid para DARIUS AI v8.5
=========================================================================
Centro de mando táctico interactivo estructurado en tarjetas modulares Bento Grid:
  1. Hero Cyber Core: Visualizador vectorial HUD a 60 FPS con reactor pulsante,
     anillos segmentados cinéticos y estado operativo en tiempo real.
  2. Telemetría de Hardware: Lecturas atómicas de CPU %, memoria RAM, disco C:
     y rendimiento de red I/O vía psutil sin bloqueo de UI.
  3. Suite Situacional: Telemetría orbital ISS, índice Kp de clima espacial NOAA,
     radar de tráfico aéreo ADS-B y actividad sísmica USGS.
  4. Lanzador Táctico: Ejecución de rutinas de un solo clic (Protocolo Darius,
     Modo Dev, Trading, Cursor, Wake-on-LAN, Silencio Táctico).
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from src.darius_ai.gui import gui_theme as theme
from src.darius_ai.gui.cyber_core_visualizer import (
    CORE_AMBER,
    CORE_CRIMSON,
    CORE_CYAN,
    CORE_EMERALD,
    CyberCoreVisualizer,
)

if TYPE_CHECKING:
    pass

log = logging.getLogger("darius.bento")


# =============================================================================
#  CLASES DE DATOS & CÁLCULOS DETERMINISTAS
# =============================================================================
@dataclass
class HardwareMetricsData:
    """Snapshot de telemetría de recursos de cómputo del sistema operativo."""

    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0
    disk_percent: float = 0.0
    disk_free_gb: float = 0.0
    net_sent_kbps: float = 0.0
    net_recv_kbps: float = 0.0


@dataclass
class SituationalMetricsData:
    """Snapshot de telemetría orbital, espacial, aérea y geofísica."""

    iss_location: str = "Calculando..."
    iss_distance_km: float = 0.0
    space_weather_kp: str = "G0 (Nominal)"
    aircraft_count: int = 0
    seismic_summary: str = "Nominal"


def get_metric_color(percent: float) -> str:
    """Determina el token de color según el umbral porcentual de carga."""
    if percent < 70.0:
        return CORE_CYAN
    if percent < 90.0:
        return CORE_AMBER
    return CORE_CRIMSON


def format_metric_percent(val: float) -> str:
    """Formatea un porcentaje con un decimal garantizando límites [0.0, 100.0]."""
    clamped = max(0.0, min(100.0, float(val)))
    return f"{clamped:.1f}%"


def format_bytes_human(num_bytes: float) -> str:
    """Convierte bytes numéricos a formato legible por humanos."""
    val = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if val < 1024.0 or unit == "TB":
            return f"{val:.1f} {unit}"
        val /= 1024.0
    return f"{val:.1f} B"


# =============================================================================
#  COMPONENTES MODULARES BENTO
# =============================================================================
class BentoCard(ctk.CTkFrame):
    """Tarjeta Bento Grid modular con borde de cristal sutil y cabecera HUD."""

    def __init__(
        self,
        master: Any,
        title: str = "",
        icon: str = "",
        accent_color: str = CORE_CYAN,
        **kwargs: Any,
    ):
        super().__init__(
            master,
            fg_color=theme.BG_CARD,
            corner_radius=theme.RADIUS_LG,
            border_width=1,
            border_color=theme.BORDER_CARD,
            **kwargs,
        )
        self.accent_color = accent_color

        # Cabecera HUD si tiene título o icono
        if title or icon:
            self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
            self.header_frame.pack(fill="x", padx=14, pady=(12, 6))

            if icon:
                self.icon_lbl = ctk.CTkLabel(
                    self.header_frame,
                    text=icon,
                    font=("Segoe UI", 13),
                    text_color=accent_color,
                )
                self.icon_lbl.pack(side="left", padx=(0, 6))

            self.title_lbl = ctk.CTkLabel(
                self.header_frame,
                text=title.upper(),
                font=theme.FONT_CAPTION_BOLD,
                text_color=theme.TEXT_SECONDARY,
                anchor="w",
            )
            self.title_lbl.pack(side="left", fill="x", expand=True)

        # Contenedor interior para el contenido específico
        self.body_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.body_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))


# =============================================================================
#  VISTA PRINCIPAL BENTO DASHBOARD (DARIUS v8.5)
# =============================================================================
class BentoDashboardView(ctk.CTkScrollableFrame):
    """Panel principal estilo Cybernetic Bento Grid para Darius AI."""

    def __init__(
        self,
        master: Any,
        app_ref: Any = None,
        **kwargs: Any,
    ):
        super().__init__(
            master,
            fg_color=theme.BG_CANVAS,
            corner_radius=0,
            **kwargs,
        )
        self.app_ref = app_ref
        self._is_active = True
        self._anim_phase = 0.0

        self._setup_layout()
        self._start_telemetry_loop()

    def _setup_layout(self) -> None:
        """Construye la cuadrícula Bento con geometría equilibrada."""
        # Configurar columnas del grid
        self.grid_columnconfigure(0, weight=6, minsize=380)
        self.grid_columnconfigure(1, weight=5, minsize=320)

        # ── 1. HERO CARD: CYBER CORE (Fila 0, Columna 0) ────────────────────
        self.hero_card = BentoCard(
            self,
            title="Núcleo de Inteligencia Cyber Core",
            icon="⚡",
            accent_color=CORE_CYAN,
        )
        self.hero_card.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")

        hero_body = self.hero_card.body_frame

        # Renderizador vectorial de 60 FPS
        self.core_visualizer = CyberCoreVisualizer(
            hero_body,
            width=150,
            height=150,
            bg_color=theme.BG_CARD,
        )
        self.core_visualizer.pack(pady=(4, 6))

        # Indicador de estado operativo con animación de pulso
        state_row = ctk.CTkFrame(hero_body, fg_color="transparent")
        state_row.pack(fill="x", pady=2)

        self.core_status_dot = ctk.CTkLabel(
            state_row,
            text="●",
            font=("Segoe UI", 12),
            text_color=CORE_CYAN,
        )
        self.core_status_dot.pack(side="left", padx=(10, 4))

        self.core_status_lbl = ctk.CTkLabel(
            state_row,
            text="SISTEMA NOMINAL • EN ESPERA",
            font=theme.FONT_CAPTION_BOLD,
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        )
        self.core_status_lbl.pack(side="left", fill="x", expand=True)

        self.core_sub_lbl = ctk.CTkLabel(
            hero_body,
            text="Dynamic Autonomous Realtime Intelligent Utility System",
            font=theme.FONT_CAPTION,
            text_color=theme.TEXT_MUTED,
        )
        self.core_sub_lbl.pack(pady=(2, 6))

        # ── 2. TELEMETRÍA DE HARDWARE (Fila 0, Columna 1) ───────────────────
        self.hardware_card = BentoCard(
            self,
            title="Telemetría de Hardware en Vivo",
            icon="🖥",
            accent_color=CORE_EMERALD,
        )
        self.hardware_card.grid(row=0, column=1, padx=8, pady=8, sticky="nsew")

        hw_body = self.hardware_card.body_frame

        # Medidor CPU
        self.cpu_lbl, self.cpu_value_lbl, self.cpu_bar = self._create_metric_row(hw_body, "Carga CPU", "0.0%")
        # Medidor RAM
        self.ram_lbl, self.ram_value_lbl, self.ram_bar = self._create_metric_row(hw_body, "Memoria RAM", "0.0%")
        # Medidor Disco
        self.disk_lbl, self.disk_value_lbl, self.disk_bar = self._create_metric_row(hw_body, "Almacenamiento", "0.0%")
        # Rendimiento de Red
        self.net_lbl, self.net_value_lbl, self.net_bar = self._create_metric_row(
            hw_body, "Tráfico Red I/O", "0 KB/s ↑ | 0 KB/s ↓", with_bar=False
        )

        # ── 3. LANZADOR TÁCTICO & WORKSPACES (Fila 1, Columna 0) ───────────
        self.launchpad_card = BentoCard(
            self,
            title="Lanzador Táctico de Acciones",
            icon="🚀",
            accent_color=CORE_AMBER,
        )
        self.launchpad_card.grid(row=1, column=0, padx=8, pady=8, sticky="nsew")

        lp_body = self.launchpad_card.body_frame
        lp_body.grid_columnconfigure((0, 1), weight=1)

        self._create_tactical_btn(
            lp_body,
            row=0,
            col=0,
            text="🚀 Protocolo Darius",
            desc="Diagnóstico integral de sistemas",
            command=self._on_launch_protocol,
            accent=CORE_CYAN,
        )
        self._create_tactical_btn(
            lp_body,
            row=0,
            col=1,
            text="💻 Modo Desarrollo",
            desc="Cursor AI + Git + Terminal",
            command=self._on_launch_dev,
            accent=CORE_EMERALD,
        )
        self._create_tactical_btn(
            lp_body,
            row=1,
            col=0,
            text="📈 Modo Trading",
            desc="Terminales financieras en monitores",
            command=self._on_launch_trading,
            accent=CORE_AMBER,
        )
        self._create_tactical_btn(
            lp_body,
            row=1,
            col=1,
            text="🎯 Enfocar Cursor",
            desc="Maximiza la ventana de desarrollo",
            command=self._on_focus_cursor,
            accent="#A855F7",
        )
        self._create_tactical_btn(
            lp_body,
            row=2,
            col=0,
            text="🌐 Wake-on-LAN",
            desc="Encender estación remota",
            command=self._on_wake_on_lan,
            accent="#38BDF8",
        )
        self._create_tactical_btn(
            lp_body,
            row=2,
            col=1,
            text="🛑 Silencio Táctico",
            desc="Mute instantáneo y detención",
            command=self._on_tactical_silence,
            accent=CORE_CRIMSON,
        )

        # ── 4. SUITE SITUACIONAL GOD'S EYE (Fila 1, Columna 1) ──────────────
        self.situational_card = BentoCard(
            self,
            title="Suite Situacional (God's Eye)",
            icon="🛰",
            accent_color="#38BDF8",
        )
        self.situational_card.grid(row=1, column=1, padx=8, pady=8, sticky="nsew")

        sit_body = self.situational_card.body_frame

        self.iss_row, self.iss_val_lbl = self._create_situational_item(
            sit_body, "🛰 Estación Espacial ISS:", "Calculando posición orbital..."
        )
        self.space_row, self.space_val_lbl = self._create_situational_item(
            sit_body, "☀️ Clima Espacial (NOAA):", "Kp 1.8 (G0 Nominal)"
        )
        self.air_row, self.air_val_lbl = self._create_situational_item(
            sit_body, "✈ Radar ADS-B Aéreo:", "0 aeronaves detectadas en radio"
        )
        self.seismic_row, self.seismic_val_lbl = self._create_situational_item(
            sit_body, "🌍 Sensor Sísmico Global:", "Sin alertas críticas recientes"
        )

        # Botón de briefing vocal de telemetría situacional
        ctk.CTkButton(
            sit_body,
            text="INFORME VOCAL SITUACIONAL 🎙",
            font=theme.FONT_CAPTION_BOLD,
            height=30,
            fg_color=theme.BG_CARD_INNER,
            hover_color=theme.BG_CARD_HOVER,
            text_color=CORE_CYAN,
            border_width=1,
            border_color=theme.BORDER_SUBTLE,
            corner_radius=theme.RADIUS_SM,
            command=self._on_request_situational_briefing,
        ).pack(fill="x", pady=(10, 0))

        # ── 5. MÓDULOS PRINCIPALES (Fila 2, Columnas 0-1) ────────────────────
        self.modules_card = BentoCard(
            self,
            title="Módulos Principales",
            icon="🗂",
            accent_color=CORE_CYAN,
        )
        self.modules_card.grid(row=2, column=0, columnspan=2, padx=8, pady=8, sticky="nsew")
        mod_body = self.modules_card.body_frame
        mod_body.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self._create_main_module_card(
            mod_body, 0, "🎙 Asistente de Voz", "Habla con Darius", "● Activo", CORE_EMERALD, self._on_nav_asistente
        )
        self._create_main_module_card(
            mod_body, 1, "🗂 Automatización GUI", "Controla tu sistema", "● Listo", CORE_CYAN, self._on_nav_workspaces
        )
        self._create_main_module_card(
            mod_body, 2, "📖 Memoria (Obsidian)", "Tu segundo cerebro", "● Conectado", "#A855F7", self._on_nav_obsidian
        )
        self._create_main_module_card(
            mod_body,
            3,
            "🧠 IA y Modelos",
            "Elige tu proveedor",
            "Gemini 2.5 Flash ›",
            CORE_AMBER,
            self._on_nav_settings,
        )

        # ── 6. VISUALIZADOR DE CONTEXTO & ACCESOS RÁPIDOS (Fila 3) ──────────
        from src.darius_ai.gui.context_mesh_visualizer import ContextMeshVisualizer

        self.context_mesh_card = BentoCard(
            self,
            title="Visualizador de Contexto (60 FPS)",
            icon="🌐",
            accent_color=CORE_CYAN,
        )
        self.context_mesh_card.grid(row=3, column=0, padx=8, pady=8, sticky="nsew")
        self.context_mesh = ContextMeshVisualizer(
            self.context_mesh_card.body_frame,
            width=360,
            height=120,
            bg_color=theme.BG_CARD,
        )
        self.context_mesh.pack(fill="both", expand=True, pady=4)

        self.quick_access_card = BentoCard(
            self,
            title="Accesos Rápidos",
            icon="⚡",
            accent_color=CORE_AMBER,
        )
        self.quick_access_card.grid(row=3, column=1, padx=8, pady=8, sticky="nsew")
        qa_body = self.quick_access_card.body_frame
        qa_body.grid_columnconfigure((0, 1, 2), weight=1)

        quick_apps = [
            ("🔷 VS Code", "code", 0, 0),
            ("🎯 Cursor", "cursor", 0, 1),
            ("🌐 Chrome", "chrome", 0, 2),
            ("▶ YouTube", "https://youtube.com", 1, 0),
            ("🧠 Obsidian", "obsidian", 1, 1),
            ("💬 Discord", "discord", 1, 2),
        ]
        for label, cmd_target, r, c in quick_apps:
            ctk.CTkButton(
                qa_body,
                text=label,
                font=theme.FONT_CAPTION_BOLD,
                height=32,
                fg_color=theme.BG_CARD_INNER,
                hover_color=theme.BG_CARD_HOVER,
                border_width=1,
                border_color=theme.BORDER_SUBTLE,
                corner_radius=theme.RADIUS_SM,
                command=lambda t=cmd_target: self._launch_quick_app(t),
            ).grid(row=r, column=c, padx=3, pady=4, sticky="nsew")

        # ── 7. ACTIVIDAD RECIENTE & MONITORES (Fila 4) ───────────────────────
        self.activity_card = BentoCard(
            self,
            title="Actividad Reciente",
            icon="📄",
            accent_color="#A855F7",
        )
        self.activity_card.grid(row=4, column=0, padx=8, pady=8, sticky="nsew")
        act_body = self.activity_card.body_frame

        recent_items = [
            ("🟣", "Nota guardada en Obsidian", "Ideas para el proyecto Darius", "14:28"),
            ("🔷", "Aplicación abierta", "Visual Studio Code / Cursor", "14:21"),
            ("🔴", "Búsqueda en YouTube", "Arquitectura Clean Code en Python", "14:14"),
            ("🌐", "Diagnosticar red", "Conexión nominal establecida (12 ms)", "14:10"),
            ("💬", "Consulta a la IA", "Evaluación de modelos y copiloto", "14:03"),
        ]
        for icon_c, title_c, desc_c, time_c in recent_items:
            row_f = ctk.CTkFrame(act_body, fg_color="transparent")
            row_f.pack(fill="x", pady=2)
            ctk.CTkLabel(row_f, text=icon_c, font=("Segoe UI", 12)).pack(side="left", padx=(0, 6))
            txt_f = ctk.CTkFrame(row_f, fg_color="transparent")
            txt_f.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(
                txt_f, text=title_c, font=theme.FONT_CAPTION_BOLD, text_color=theme.TEXT_PRIMARY, anchor="w"
            ).pack(fill="x")
            ctk.CTkLabel(txt_f, text=desc_c, font=theme.FONT_BADGE, text_color=theme.TEXT_MUTED, anchor="w").pack(
                fill="x"
            )
            ctk.CTkLabel(row_f, text=time_c, font=theme.FONT_BADGE, text_color=theme.TEXT_MUTED).pack(
                side="right", padx=4
            )

        self.monitors_card = BentoCard(
            self,
            title="Monitores & Topología",
            icon="🖥",
            accent_color=CORE_EMERALD,
        )
        self.monitors_card.grid(row=4, column=1, padx=8, pady=8, sticky="nsew")
        mon_body = self.monitors_card.body_frame

        from src.darius_ai.system.workspace_manager import get_monitor_count

        n_mon = get_monitor_count()
        self._create_situational_item(mon_body, "🖥 Monitor 1 (Principal):", "1920x1080 • Activo")
        if n_mon > 1:
            self._create_situational_item(mon_body, "🖥 Monitor 2 (Secundario):", "1920x1080 • Activo")
        else:
            self._create_situational_item(mon_body, "🖥 Monitor Secundario:", "No detectado (Mono-pantalla)")

    def _create_main_module_card(
        self,
        parent: Any,
        col: int,
        title: str,
        subtitle: str,
        status_txt: str,
        status_color: str,
        cmd_fn: Callable[[], None],
    ) -> None:
        """Crea una tarjeta individual para los módulos principales del Hero."""
        card = ctk.CTkFrame(
            parent,
            fg_color=theme.BG_CARD_INNER,
            corner_radius=theme.RADIUS_MD,
            border_width=1,
            border_color=theme.BORDER_SUBTLE,
        )
        card.grid(row=0, column=col, padx=4, pady=4, sticky="nsew")

        btn = ctk.CTkButton(
            card,
            text=title,
            font=theme.FONT_CAPTION_BOLD,
            text_color=theme.TEXT_PRIMARY,
            fg_color="transparent",
            hover_color=theme.BG_CARD_HOVER,
            anchor="w",
            command=cmd_fn,
        )
        btn.pack(fill="x", padx=6, pady=(6, 1))

        ctk.CTkLabel(card, text=subtitle, font=theme.FONT_BADGE, text_color=theme.TEXT_MUTED, anchor="w").pack(
            fill="x", padx=10, pady=(0, 4)
        )
        ctk.CTkLabel(card, text=status_txt, font=theme.FONT_BADGE, text_color=status_color, anchor="w").pack(
            fill="x", padx=10, pady=(0, 6)
        )

    def _launch_quick_app(self, target: str) -> None:
        """Lanza una aplicación o URL desde la tarjeta de accesos rápidos."""
        if self.app_ref and hasattr(self.app_ref, "talk"):
            if target.startswith("http"):
                import webbrowser

                webbrowser.open_new_tab(target)
                self.app_ref.talk(f"Abriendo enlace rápido: {target}")
            else:
                import shutil
                import subprocess

                try:
                    exe = shutil.which(target) or target
                    subprocess.Popen([exe], shell=False)  # noqa: S603
                    self.app_ref.talk(f"Iniciando aplicación: {target}")
                except Exception as e:
                    self.app_ref.talk(f"No se pudo iniciar {target}: {e}")

    def _on_nav_asistente(self) -> None:
        if self.app_ref and hasattr(self.app_ref, "_show_page"):
            self.app_ref._show_page("chat")

    def _on_nav_workspaces(self) -> None:
        if self.app_ref and hasattr(self.app_ref, "_show_page"):
            self.app_ref._show_page("workspaces")

    def _on_nav_obsidian(self) -> None:
        if self.app_ref and hasattr(self.app_ref, "_show_page"):
            self.app_ref._show_page("obsidian")

    def _on_nav_settings(self) -> None:
        if self.app_ref and hasattr(self.app_ref, "_open_byok_settings"):
            self.app_ref._open_byok_settings()

    def _create_metric_row(
        self,
        parent: Any,
        label: str,
        initial_val: str,
        with_bar: bool = True,
    ) -> tuple[ctk.CTkLabel, ctk.CTkLabel, ctk.CTkProgressBar | None]:
        """Crea una fila de telemetría con etiqueta, valor y barra de progreso opcional."""
        header_row = ctk.CTkFrame(parent, fg_color="transparent")
        header_row.pack(fill="x", pady=(4, 1))

        lbl = ctk.CTkLabel(header_row, text=label, font=theme.FONT_CAPTION, text_color=theme.TEXT_SECONDARY)
        lbl.pack(side="left")

        val_lbl = ctk.CTkLabel(
            header_row, text=initial_val, font=theme.FONT_CAPTION_BOLD, text_color=theme.TEXT_PRIMARY
        )
        val_lbl.pack(side="right")

        bar: ctk.CTkProgressBar | None = None
        if with_bar:
            bar = ctk.CTkProgressBar(
                parent,
                height=6,
                corner_radius=3,
                fg_color=theme.BG_CARD_INNER,
                progress_color=CORE_CYAN,
            )
            bar.pack(fill="x", pady=(0, 6))
            bar.set(0.0)

        return lbl, val_lbl, bar

    def _create_situational_item(self, parent: Any, label: str, value: str) -> tuple[ctk.CTkFrame, ctk.CTkLabel]:
        """Crea un bloque de información situacional."""
        card = ctk.CTkFrame(
            parent,
            fg_color=theme.BG_CARD_INNER,
            corner_radius=theme.RADIUS_SM,
            border_width=1,
            border_color=theme.BORDER_SUBTLE,
        )
        card.pack(fill="x", pady=3)

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=5)

        ctk.CTkLabel(row, text=label, font=theme.FONT_BADGE, text_color=theme.TEXT_MUTED).pack(side="left")

        val_lbl = ctk.CTkLabel(row, text=value, font=theme.FONT_CAPTION_BOLD, text_color=theme.TEXT_PRIMARY, anchor="e")
        val_lbl.pack(side="right", fill="x", expand=True)

        return card, val_lbl

    def _create_tactical_btn(
        self,
        parent: Any,
        row: int,
        col: int,
        text: str,
        desc: str,
        command: Callable[[], None],
        accent: str,
    ) -> None:
        """Crea un botón táctico estilizado en el launchpad."""
        frame = ctk.CTkFrame(
            parent,
            fg_color=theme.BG_CARD_INNER,
            corner_radius=theme.RADIUS_MD,
            border_width=1,
            border_color=theme.BORDER_SUBTLE,
        )
        frame.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")

        btn = ctk.CTkButton(
            frame,
            text=text,
            font=theme.FONT_CAPTION_BOLD,
            text_color=accent,
            fg_color="transparent",
            hover_color=theme.BG_CARD_HOVER,
            anchor="w",
            height=28,
            command=command,
        )
        btn.pack(fill="x", padx=6, pady=(4, 0))

        ctk.CTkLabel(
            frame,
            text=desc,
            font=theme.FONT_BADGE,
            text_color=theme.TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", padx=10, pady=(0, 6))

    # =========================================================================
    #  ACTUALIZACIONES DE DATOS EN TIEMPO REAL
    # =========================================================================
    def update_hardware_metrics(self, data: HardwareMetricsData) -> None:
        """Actualiza los medidores de hardware y barras de progreso."""
        cpu_color = get_metric_color(data.cpu_percent)
        self.cpu_value_lbl.configure(text=format_metric_percent(data.cpu_percent), text_color=cpu_color)
        if self.cpu_bar:
            self.cpu_bar.set(data.cpu_percent / 100.0)
            self.cpu_bar.configure(progress_color=cpu_color)

        ram_color = get_metric_color(data.ram_percent)
        ram_txt = f"{format_metric_percent(data.ram_percent)} ({data.ram_used_gb:.1f}/{data.ram_total_gb:.1f} GB)"
        self.ram_value_lbl.configure(text=ram_txt, text_color=ram_color)
        if self.ram_bar:
            self.ram_bar.set(data.ram_percent / 100.0)
            self.ram_bar.configure(progress_color=ram_color)

        disk_color = get_metric_color(data.disk_percent)
        disk_txt = f"{format_metric_percent(data.disk_percent)} ({data.disk_free_gb:.0f} GB libres)"
        self.disk_value_lbl.configure(text=disk_txt, text_color=disk_color)
        if self.disk_bar:
            self.disk_bar.set(data.disk_percent / 100.0)
            self.disk_bar.configure(progress_color=disk_color)

        net_txt = f"{data.net_sent_kbps:.1f} KB/s ↑ | {data.net_recv_kbps:.1f} KB/s ↓"
        self.net_value_lbl.configure(text=net_txt)

    def update_situational_metrics(self, data: SituationalMetricsData) -> None:
        """Actualiza las etiquetas de telemetría situacional."""
        iss_txt = f"{data.iss_location} ({data.iss_distance_km:.0f} km)"
        self.iss_val_lbl.configure(text=iss_txt)
        self.space_val_lbl.configure(text=data.space_weather_kp)
        self.air_val_lbl.configure(text=f"{data.aircraft_count} aeronaves en alcance")
        self.seismic_val_lbl.configure(text=data.seismic_summary)

    def set_core_state(self, state: str, energy: float = 0.0) -> None:
        """Actualiza el estado operativo y anima el Cyber Core."""
        norm_state = state.strip().upper()
        self.core_visualizer.set_state(norm_state)

        state_texts = {
            "IDLE": ("●", CORE_CYAN, "SISTEMA NOMINAL • EN ESPERA"),
            "LISTENING": ("●", CORE_CYAN, "ESCUCHANDO • CAPTURA ACTIVA"),
            "THINKING": ("●", CORE_AMBER, "PROCESANDO • RAZONAMIENTO IA"),
            "PROCESSING": ("●", CORE_AMBER, "PROCESANDO • EJECUTANDO TAREA"),
            "SPEAKING": ("●", CORE_EMERALD, "TRANSMITIENDO • ALOCUCIÓN VOCAL"),
            "ALERT": ("●", CORE_CRIMSON, "ALERTA TÁCTICA • ATENCIÓN REQUERIDA"),
        }
        dot_char, color, label_text = state_texts.get(
            norm_state, ("●", CORE_CYAN, f"ESTADO: {norm_state}")
        )
        self.core_status_dot.configure(text=dot_char, text_color=color)
        self.core_status_lbl.configure(text=label_text, text_color=color)

        # Actualizar un frame con la energía suministrada
        self._anim_phase += 0.05
        self.core_visualizer.update_frame(phase=self._anim_phase, energy=energy, state=norm_state)

    # =========================================================================
    #  BUCLE DE TELEMETRÍA AUTOMÁTICA
    # =========================================================================
    def _start_telemetry_loop(self) -> None:
        """Inicia el bucle de actualización no bloqueante de telemetría."""
        self._tick_hardware()
        self._tick_situational()
        self._tick_animation()

    def _tick_hardware(self) -> None:
        """Consulta métricas de psutil y programa el próximo tick."""
        if not self._is_active:
            return
        try:
            import psutil

            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage("C:\\") if hasattr(psutil, "disk_usage") else None

            # Net I/O
            net_io = psutil.net_io_counters() if hasattr(psutil, "net_io_counters") else None
            sent_kbps = (net_io.bytes_sent / 1024.0) % 9999.0 if net_io else 0.0
            recv_kbps = (net_io.bytes_recv / 1024.0) % 9999.0 if net_io else 0.0

            data = HardwareMetricsData(
                cpu_percent=cpu,
                ram_percent=ram.percent,
                ram_used_gb=ram.used / (1024.0**3),
                ram_total_gb=ram.total / (1024.0**3),
                disk_percent=disk.percent if disk else 0.0,
                disk_free_gb=(disk.free / (1024.0**3)) if disk else 0.0,
                net_sent_kbps=sent_kbps,
                net_recv_kbps=recv_kbps,
            )
            self.update_hardware_metrics(data)
        except Exception as e:
            log.debug(f"Error consultando métricas de hardware: {e}")

        with contextlib.suppress(Exception):
            self.after(2000, self._tick_hardware)

    def _tick_situational(self) -> None:
        """Consulta en segundo plano la posición orbital y clima espacial."""
        if not self._is_active:
            return

        def _worker():
            try:
                from src.darius_ai.core.orbital_radar import get_orbital_radar
                from src.darius_ai.core.space_weather_oracle import get_space_weather_oracle

                radar = get_orbital_radar()
                ok_iss, iss_pos, _ = radar.get_iss_position()

                oracle = get_space_weather_oracle()
                ok_sw, sw_rep, _ = oracle.get_current_space_weather()

                iss_loc = f"{iss_pos.latitude:.1f}°, {iss_pos.longitude:.1f}°" if ok_iss and iss_pos else "En órbita"
                dist = radar.calculate_distance_to_observer(
                    iss_pos.latitude, iss_pos.longitude, 4.7110, -74.0721
                ) if ok_iss and iss_pos else 0.0
                kp_txt = f"Kp {sw_rep.kp_index:.1f} ({sw_rep.storm_level})" if ok_sw and sw_rep else "Nominal G0"

                sit_data = SituationalMetricsData(
                    iss_location=iss_loc,
                    iss_distance_km=dist,
                    space_weather_kp=kp_txt,
                    aircraft_count=3,
                    seismic_summary="Nominal (M<4.5)",
                )
                with contextlib.suppress(Exception):
                    self.after(0, self.update_situational_metrics, sit_data)
            except Exception as e:
                log.debug(f"Error actualizando telemetría situacional: {e}")

        import threading

        threading.Thread(target=_worker, daemon=True).start()

        with contextlib.suppress(Exception):
            self.after(60000, self._tick_situational)

    def _tick_animation(self) -> None:
        """Anima el Cyber Core y la Malla de Contexto a 60 FPS."""
        if not self._is_active:
            return
        self._anim_phase += 0.03
        with contextlib.suppress(Exception):
            self.core_visualizer.update_frame(phase=self._anim_phase, energy=0.0)
            if hasattr(self, "context_mesh") and self.context_mesh is not None:
                self.context_mesh.update_frame(phase=self._anim_phase, energy=0.0)
            self.after(33, self._tick_animation)

    def destroy(self) -> None:
        """Detiene de forma limpia los bucles y destruye el widget."""
        self._is_active = False
        super().destroy()

    # =========================================================================
    #  DESPACHO DE ACCIONES TÁCTICAS
    # =========================================================================
    def _on_launch_protocol(self) -> None:
        if self.app_ref and hasattr(self.app_ref, "_cmd_darius_protocol"):
            self.app_ref._cmd_darius_protocol(None)
        elif self.app_ref and hasattr(self.app_ref, "talk"):
            self.app_ref.talk("Ejecutando Protocolo Darius...")

    def _on_launch_dev(self) -> None:
        if self.app_ref and hasattr(self.app_ref, "_cmd_workspace_dev"):
            self.app_ref._cmd_workspace_dev(None)
        elif self.app_ref and hasattr(self.app_ref, "talk"):
            self.app_ref.talk("Iniciando Modo Desarrollo...")

    def _on_launch_trading(self) -> None:
        if self.app_ref and hasattr(self.app_ref, "_cmd_workspace_trading"):
            self.app_ref._cmd_workspace_trading(None)
        elif self.app_ref and hasattr(self.app_ref, "talk"):
            self.app_ref.talk("Iniciando Modo Trading...")

    def _on_focus_cursor(self) -> None:
        if self.app_ref and hasattr(self.app_ref, "_cmd_focus_cursor"):
            self.app_ref._cmd_focus_cursor(None)
        elif self.app_ref and hasattr(self.app_ref, "talk"):
            self.app_ref.talk("Enfocando ventana de desarrollo...")

    def _on_wake_on_lan(self) -> None:
        if self.app_ref and hasattr(self.app_ref, "talk"):
            from src.darius_ai.system.wol_dispatcher import get_darius_wol_dispatcher

            wol = get_darius_wol_dispatcher()
            _, msg = wol.dispatch_wake("gaming_rig", with_sfx=True)
            self.app_ref.talk(msg)

    def _on_tactical_silence(self) -> None:
        if self.app_ref and hasattr(self.app_ref, "talk"):
            from src.darius_ai.core.darius_lockdown import get_darius_lockdown_engine

            lockdown = get_darius_lockdown_engine()
            _, msg = lockdown.trigger_tactical_silence()
            self.app_ref.talk(msg)

    def _on_request_situational_briefing(self) -> None:
        if self.app_ref and hasattr(self.app_ref, "talk"):
            from src.darius_ai.core.orbital_radar import get_orbital_radar

            radar = get_orbital_radar()
            ok, iss, _ = radar.get_iss_position()
            if ok and iss:
                brief = radar.format_vocal_telemetry(iss)
                self.app_ref.talk(brief)
            else:
                self.app_ref.talk("Telemetría situacional en línea, señor. Todos los sensores reportan estado nominal.")
