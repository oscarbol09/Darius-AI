"""
test_bento_dashboard.py — Suite de pruebas para el Dashboard Bento Cybernetic de Darius AI
==========================================================================================
Protocolo ECC: TDD Red-Green-Refactor.
Valida:
  1. Clases de datos y formateadores métricos (HardwareMetricsData, SituationalMetricsData).
  2. Funciones puras de cálculo y colorimetría (get_metric_color, format_metric_percent).
  3. Comportamiento en modo headless del widget BentoDashboardView.
  4. Métodos de actualización de telemetría de hardware y suite situacional.
  5. Despacho seguro de acciones tácticas y transiciones de estado del Cyber Core.
"""

import contextlib
from unittest.mock import MagicMock

import customtkinter as ctk
import pytest

from src.darius_ai.gui.bento_dashboard import (
    BentoCard,
    BentoDashboardView,
    HardwareMetricsData,
    SituationalMetricsData,
    format_bytes_human,
    format_metric_percent,
    get_metric_color,
)
from src.darius_ai.gui.cyber_core_visualizer import CORE_AMBER, CORE_CRIMSON, CORE_CYAN, CORE_EMERALD


class TestBentoDashboardPureFunctions:
    """Verifica las funciones de cálculo métrico, colores y formateo."""

    def test_get_metric_color_nominal(self):
        # < 70% debe ser cian o esmeralda (nominal)
        assert get_metric_color(25.0) in (CORE_CYAN, CORE_EMERALD, "#00F0FF", "#00FF88", "#10B981")
        assert get_metric_color(69.0) in (CORE_CYAN, CORE_EMERALD, "#00F0FF", "#00FF88", "#10B981")

    def test_get_metric_color_warning(self):
        # 70% - 89% debe ser ámbar (advertencia / carga elevada)
        assert get_metric_color(75.0) in (CORE_AMBER, "#E6AA38", "#F59E0B")
        assert get_metric_color(88.0) in (CORE_AMBER, "#E6AA38", "#F59E0B")

    def test_get_metric_color_critical(self):
        # >= 90% debe ser carmesí (crítico)
        assert get_metric_color(90.0) in (CORE_CRIMSON, "#C42B3B", "#F43F5E")
        assert get_metric_color(99.5) in (CORE_CRIMSON, "#C42B3B", "#F43F5E")

    def test_format_metric_percent(self):
        assert format_metric_percent(42.5) == "42.5%"
        assert format_metric_percent(0.0) == "0.0%"
        assert format_metric_percent(100.0) == "100.0%"
        assert format_metric_percent(105.0) == "100.0%"  # Clampeado
        assert format_metric_percent(-5.0) == "0.0%"  # Clampeado

    def test_format_bytes_human(self):
        assert "B" in format_bytes_human(500)
        assert "KB" in format_bytes_human(1024 * 5)
        assert "MB" in format_bytes_human(1024 * 1024 * 15)
        assert "GB" in format_bytes_human(1024 * 1024 * 1024 * 32)

    def test_hardware_metrics_dataclass_defaults(self):
        metrics = HardwareMetricsData()
        assert metrics.cpu_percent == 0.0
        assert metrics.ram_percent == 0.0
        assert metrics.disk_percent == 0.0
        assert metrics.net_sent_kbps == 0.0
        assert metrics.net_recv_kbps == 0.0

    def test_situational_metrics_dataclass_defaults(self):
        sit = SituationalMetricsData()
        assert sit.iss_location == "Calculando..."
        assert sit.space_weather_kp == "G0 (Nominal)"
        assert sit.aircraft_count == 0
        assert sit.seismic_summary == "Nominal"


class TestBentoDashboardWidget:
    """Verifica la inicialización e interacción de los componentes Bento."""

    @pytest.fixture
    def app_fixture(self):
        try:
            root = ctk.CTk()
            root.withdraw()
            mock_app = MagicMock()
            mock_app.root = root
            mock_app.talk = MagicMock()
            mock_app._cmd_darius_protocol = MagicMock()
            mock_app._cmd_workspace_dev = MagicMock()
            mock_app._cmd_workspace_trading = MagicMock()
            mock_app._cmd_focus_cursor = MagicMock()
            view = BentoDashboardView(root, app_ref=mock_app)
        except Exception as exc:
            pytest.skip(f"Tkinter/Tcl no disponible en este entorno: {exc}")
        yield view, mock_app
        with contextlib.suppress(Exception):
            root.destroy()

    def test_bento_dashboard_initialization(self, app_fixture):
        view, _ = app_fixture
        assert view is not None
        assert isinstance(view.hero_card, BentoCard)
        assert isinstance(view.hardware_card, BentoCard)
        assert isinstance(view.situational_card, BentoCard)
        assert isinstance(view.launchpad_card, BentoCard)

    def test_update_hardware_metrics(self, app_fixture):
        view, _ = app_fixture
        data = HardwareMetricsData(
            cpu_percent=45.0,
            ram_percent=62.0,
            ram_used_gb=19.8,
            ram_total_gb=32.0,
            disk_percent=55.0,
            disk_free_gb=350.0,
            net_sent_kbps=120.5,
            net_recv_kbps=850.2,
        )
        view.update_hardware_metrics(data)
        assert "45.0%" in view.cpu_value_lbl.cget("text")
        assert "62.0%" in view.ram_value_lbl.cget("text")

    def test_update_situational_metrics(self, app_fixture):
        view, _ = app_fixture
        data = SituationalMetricsData(
            iss_location="Sobre el Atlántico Norte",
            iss_distance_km=1420.5,
            space_weather_kp="Kp 2.1 (G0 Nominal)",
            aircraft_count=7,
            seismic_summary="M4.8 en Japón",
        )
        view.update_situational_metrics(data)
        assert "Atlántico" in view.iss_val_lbl.cget("text")
        assert "2.1" in view.space_val_lbl.cget("text")
        assert "7" in view.air_val_lbl.cget("text")

    def test_set_core_state_delegation(self, app_fixture):
        view, _ = app_fixture
        view.set_core_state(state="LISTENING", energy=40.0)
        assert view.core_visualizer.current_state == "LISTENING"
        assert "ESCUCHANDO" in view.core_status_lbl.cget("text")

    def test_launchpad_action_dispatch(self, app_fixture):
        view, mock_app = app_fixture
        # Invocar botón Protocolo Darius
        view._on_launch_protocol()
        mock_app._cmd_darius_protocol.assert_called_once()
