"""
test_darius_protocol.py — Pruebas unitarias para el Protocolo Darius y Diagnóstico Integral Core v8.5
====================================================================================================
Valida la auditoría de hardware, telemetría, periféricos y generación de la alocución vocal nativa de DARIUS.
"""

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from src.darius_ai.core.darius_protocol import (
    DariusProtocolEngine,
    StarkProtocolEngine,
    get_darius_engine,
    get_darius_protocol_engine,
    get_stark_engine,
    get_stark_protocol_engine,
)
from src.darius_ai.core.stark_protocol import (
    StarkProtocolEngine as ProxyStarkEngine,
)


class TestDariusDiagnosticChecks:
    @pytest.fixture
    def engine(self):
        return DariusProtocolEngine()

    @patch("src.darius_ai.core.darius_protocol.get_sfx_engine")
    @patch("src.darius_ai.core.darius_protocol.psutil")
    @patch("src.darius_ai.core.darius_protocol.socket.create_connection")
    @patch("src.darius_ai.core.darius_protocol.brain")
    def test_run_diagnostic_structure(self, mock_brain, mock_sock, mock_psutil, mock_sfx_getter, engine):
        # Configurar mocks de psutil
        mock_psutil.cpu_percent.return_value = 14.5
        mock_psutil.cpu_count.return_value = 16

        mock_vmem = MagicMock()
        mock_vmem.total = 32 * (1024**3)
        mock_vmem.available = 20 * (1024**3)
        mock_vmem.percent = 37.5
        mock_psutil.virtual_memory.return_value = mock_vmem

        mock_disk = MagicMock()
        mock_disk.total = 1000 * (1024**3)
        mock_disk.free = 650 * (1024**3)
        mock_disk.percent = 35.0
        mock_psutil.disk_usage.return_value = mock_disk

        mock_psutil.sensors_battery.return_value = None  # Desktop

        # Mock de red
        mock_sock.return_value.__enter__.return_value = MagicMock()

        # Mock de Obsidian
        mock_vault = MagicMock()
        mock_vault.exists.return_value = True
        mock_vault.__str__.return_value = "C:/Users/dario/Obsidian"
        mock_brain.vault_path = mock_vault

        mock_sfx = MagicMock()
        mock_sfx_getter.return_value = mock_sfx

        data = engine.run_diagnostic(with_sfx=True)

        assert isinstance(data, dict)
        assert "cpu" in data
        assert "ram" in data
        assert "disk" in data
        assert "battery" in data
        assert "network" in data
        assert "monitors" in data
        assert "audio" in data
        assert "obsidian" in data
        assert "status" in data
        assert "timestamp" in data

        assert data["cpu"]["percent"] == 14.5
        assert data["ram"]["percent"] == 37.5
        assert data["battery"]["status"] in ("DESKTOP", "AC_POWERED")
        assert data["network"]["online"] is True
        assert data["obsidian"]["connected"] is True

        # Verificar SFX ejecutados en secuencia táctica
        mock_sfx.play_scan_pulse.assert_called_once()
        mock_sfx.play_target_lock.assert_called_once()
        mock_sfx.play_success_chime.assert_called_once()

    @patch("src.darius_ai.core.darius_protocol.get_sfx_engine")
    def test_run_diagnostic_sfx_disabled(self, mock_sfx_getter, engine):
        mock_sfx = MagicMock()
        mock_sfx_getter.return_value = mock_sfx

        data = engine.run_diagnostic(with_sfx=False)
        assert isinstance(data, dict)
        mock_sfx.play_scan_pulse.assert_not_called()
        mock_sfx.play_target_lock.assert_not_called()
        mock_sfx.play_success_chime.assert_not_called()

    @patch("src.darius_ai.core.darius_protocol.psutil.sensors_battery")
    def test_battery_laptop_detection(self, mock_sensors_battery, engine):
        mock_bat = MagicMock()
        mock_bat.percent = 88
        mock_bat.power_plugged = True
        mock_bat.secsleft = 14400
        mock_sensors_battery.return_value = mock_bat

        bat_data = engine._check_battery()
        assert bat_data["percent"] == 88
        assert bat_data["plugged"] is True
        assert "88%" in bat_data["status"] or "Cargando" in bat_data["status"] or "AC" in bat_data["status"]

    @patch("src.darius_ai.core.darius_protocol.socket.create_connection", side_effect=OSError("Network unreachable"))
    def test_network_offline_detection(self, mock_sock, engine):
        net_data = engine._check_network()
        assert net_data["online"] is False
        assert net_data["status"] == "OFFLINE"
        assert net_data["latency_ms"] is None or net_data["latency_ms"] < 0


class TestVocalBriefingGeneration:
    @pytest.fixture
    def engine(self):
        return DariusProtocolEngine()

    def test_generate_vocal_briefing_optimal(self, engine):
        sample_diag = {
            "status": "OPTIMAL",
            "cpu": {"percent": 18.2, "cores": 12},
            "ram": {"available_gb": 18.5, "total_gb": 32.0, "percent": 42.0},
            "disk": {"free_gb": 450.0, "total_gb": 1000.0, "percent": 55.0},
            "battery": {"status": "DESKTOP", "plugged": True, "percent": 100},
            "network": {"online": True, "latency_ms": 12.4, "status": "ONLINE"},
            "monitors": {"count": 2, "resolutions": ["1920x1080", "2560x1440"]},
            "audio": {"input_devices": 2, "output_devices": 3, "status": "OPERATIONAL"},
            "obsidian": {"connected": True, "status": "SYNCED"},
        }

        briefing = engine.generate_vocal_briefing(sample_diag)
        assert isinstance(briefing, str)
        assert "Protocolo Darius" in briefing
        assert "señor" in briefing.lower()
        assert "18.2%" in briefing or "18%" in briefing or "CPU" in briefing
        assert "RAM" in briefing or "memoria" in briefing.lower()
        assert "pantallas" in briefing.lower() or "monitores" in briefing.lower()
        assert "obsidian" in briefing.lower()

    def test_generate_vocal_briefing_degraded(self, engine):
        degraded_diag = {
            "status": "DEGRADED",
            "cpu": {"percent": 96.0, "cores": 8},
            "ram": {"available_gb": 1.2, "total_gb": 16.0, "percent": 92.5},
            "disk": {"free_gb": 5.0, "total_gb": 500.0, "percent": 99.0},
            "battery": {"status": "BATTERY", "plugged": False, "percent": 12},
            "network": {"online": False, "latency_ms": None, "status": "OFFLINE"},
            "monitors": {"count": 1, "resolutions": ["1920x1080"]},
            "audio": {"input_devices": 0, "output_devices": 1, "status": "DEGRADED"},
            "obsidian": {"connected": False, "status": "UNAVAILABLE"},
        }

        briefing = engine.generate_vocal_briefing(degraded_diag)
        assert isinstance(briefing, str)
        assert "Protocolo Darius" in briefing
        assert "advertencia" in briefing.lower() or "alerta" in briefing.lower() or "degradado" in briefing.lower()


class TestEngineSingletonAndAliases:
    def test_get_darius_protocol_engine_singleton(self):
        e1 = get_darius_protocol_engine()
        e2 = get_darius_protocol_engine()
        assert e1 is e2
        assert isinstance(e1, DariusProtocolEngine)

    def test_backwards_compatible_engine_aliases(self):
        assert StarkProtocolEngine is DariusProtocolEngine
        assert ProxyStarkEngine is DariusProtocolEngine

        e1 = get_darius_protocol_engine()
        assert get_darius_engine() is e1
        assert get_stark_engine() is e1
        assert get_stark_protocol_engine() is e1


class TestDariusProtocolEdgeCases:
    @pytest.fixture
    def engine(self):
        return DariusProtocolEngine()

    @patch("src.darius_ai.core.darius_protocol.psutil.disk_usage", side_effect=OSError("Disk error"))
    def test_check_disk_exception_handling(self, mock_disk, engine):
        data = engine._check_disk()
        assert data["total_gb"] == 0.0
        assert data["free_gb"] == 0.0

    @patch("src.darius_ai.core.darius_protocol.psutil.sensors_battery", side_effect=RuntimeError("Battery fail"))
    def test_check_battery_exception_handling(self, mock_bat, engine):
        data = engine._check_battery()
        assert data["status"] == "DESKTOP"
        assert data["percent"] == 100

    @patch("src.darius_ai.system.workspace_manager.get_monitor_count", side_effect=Exception("Display fail"))
    def test_check_monitors_exception_handling(self, mock_mon, engine):
        data = engine._check_monitors()
        assert data["count"] == 1
        assert data["resolutions"] == ["1920x1080"]

    def test_check_audio_exception_handling(self, engine):
        with patch.dict("sys.modules", {"sounddevice": None}), patch("src.darius_ai.core.darius_protocol.psutil"):
            data = engine._check_audio()
            assert data["status"] in ("OPERATIONAL", "DEGRADED")
            assert "input_devices" in data

    @patch("src.darius_ai.core.darius_protocol.brain")
    def test_check_obsidian_exception_handling(self, mock_brain, engine):
        type(mock_brain).vault_path = PropertyMock(side_effect=RuntimeError("Vault error"))
        data = engine._check_obsidian()
        assert data["connected"] is False
        assert data["status"] == "UNAVAILABLE"

    @patch("src.darius_ai.core.darius_protocol.get_sfx_engine", side_effect=Exception("SFX crash"))
    def test_run_diagnostic_sfx_exception_does_not_crash(self, mock_sfx, engine):
        data = engine.run_diagnostic(with_sfx=True)
        assert isinstance(data, dict)
        assert "status" in data
