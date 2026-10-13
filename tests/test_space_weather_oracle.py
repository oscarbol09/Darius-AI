"""Tests for SpaceWeatherOracle and SpaceWeatherReport module."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

# Ensure src directory is in sys.path
SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

try:
    from src.darius_ai.core.space_weather_oracle import SpaceWeatherOracle, SpaceWeatherReport
except ImportError:
    from darius_ai.core.space_weather_oracle import (  # type: ignore[import-not-found,no-redef]
        SpaceWeatherOracle,
        SpaceWeatherReport,
    )


# Mock NOAA SWPC tabular array format
MOCK_NOAA_ARRAY_DATA = [
    ["time_tag", "Kp", "a_running", "station_count"],
    ["2026-10-13 12:00:00.000", "2.00", "7", "8"],
    ["2026-10-13 15:00:00.000", "2.67", "9", "8"],
    ["2026-10-13 18:00:00.000", "3.33", "12", "8"],
]

# Mock NOAA SWPC list of objects format
MOCK_NOAA_DICT_DATA = [
    {
        "time_tag": "2026-10-13 18:00:00.000",
        "Kp": 5.67,
        "a_running": 45,
        "station_count": 8,
    }
]


class TestSpaceWeatherOracle:
    """Test suite for SpaceWeatherOracle NOAA planetary K-index monitoring."""

    def test_space_weather_report_dataclass(self) -> None:
        """Verify report creation and field values."""
        report = SpaceWeatherReport(
            kp_index=3.33,
            storm_level="G0 (Tranquilo / Nominal)",
            geomagnetic_status="Nominal / Campo geomagnético en calma",
            timestamp="2026-10-13 18:00:00",
            radio_blackout_risk="Bajo",
            satellite_risk="Mínimo",
            observed_at="2026-10-13 18:00:00",
        )
        assert report.kp_index == 3.33
        assert "G0" in report.storm_level
        assert report.radio_blackout_risk == "Bajo"

    @pytest.mark.parametrize(
        ("kp", "expected_storm_prefix"),
        [
            (0.0, "G0 (Tranquilo"),
            (2.33, "G0 (Tranquilo"),
            (3.99, "G0 (Tranquilo"),
            (4.0, "G0+ (Activo)"),
            (4.67, "G0+ (Activo)"),
            (5.0, "G1 (Tormenta Menor)"),
            (5.67, "G1 (Tormenta Menor)"),
            (6.0, "G2 (Tormenta Moderada)"),
            (6.67, "G2 (Tormenta Moderada)"),
            (7.0, "G3 (Tormenta Fuerte)"),
            (7.67, "G3 (Tormenta Fuerte)"),
            (8.0, "G4 (Tormenta Severa)"),
            (8.67, "G4 (Tormenta Severa)"),
            (9.0, "G5 (Tormenta Extrema)"),
            (9.5, "G5 (Tormenta Extrema)"),
        ],
    )
    def test_classify_kp_storm_levels(self, kp: float, expected_storm_prefix: str) -> None:
        """Verify strict classification of planetary K-index scale according to NOAA SWPC."""
        oracle = SpaceWeatherOracle()
        classification = oracle.classify_kp(kp)
        assert classification["storm_level"].startswith(expected_storm_prefix)

    def test_get_current_space_weather_success_array_format(self) -> None:
        """Verify ingestion of NOAA planetary K-index array table format."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_NOAA_ARRAY_DATA

        with patch("httpx.Client.get", return_value=mock_resp):
            oracle = SpaceWeatherOracle()
            success, report, msg = oracle.get_current_space_weather()

            assert success is True
            assert report is not None
            assert report.kp_index == pytest.approx(3.33)
            assert "G0" in report.storm_level
            assert report.observed_at == "2026-10-13 18:00:00.000"
            msg_l = msg.lower()
            assert any(term in msg_l for term in ("éxito", "ok", "nominal", "telemetría"))

    def test_get_current_space_weather_success_dict_format(self) -> None:
        """Verify ingestion of NOAA planetary K-index dict format."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_NOAA_DICT_DATA

        with patch("httpx.Client.get", return_value=mock_resp):
            oracle = SpaceWeatherOracle()
            success, report, msg = oracle.get_current_space_weather()

            assert success is True
            assert report is not None
            assert report.kp_index == pytest.approx(5.67)
            assert "G1" in report.storm_level

    def test_get_current_space_weather_caching_within_ttl(self) -> None:
        """Multiple calls within TTL (15 min) must not trigger subsequent HTTP calls."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_NOAA_ARRAY_DATA

        with patch("httpx.Client.get", return_value=mock_resp) as mock_get:
            oracle = SpaceWeatherOracle(ttl_seconds=900.0)
            res1 = oracle.get_current_space_weather()
            res2 = oracle.get_current_space_weather()

            assert res1[0] is True
            assert res2[0] is True
            assert res1[1] == res2[1]
            assert mock_get.call_count == 1

    def test_get_current_space_weather_cache_expiry(self) -> None:
        """Expired TTL triggers fresh NOAA fetch."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_NOAA_ARRAY_DATA

        with patch("httpx.Client.get", return_value=mock_resp) as mock_get:
            oracle = SpaceWeatherOracle(ttl_seconds=60.0)
            oracle.get_current_space_weather()
            assert mock_get.call_count == 1

            oracle._cache_timestamp -= 100.0
            oracle.get_current_space_weather()
            assert mock_get.call_count == 2

    def test_get_current_space_weather_clear_cache(self) -> None:
        """Explicit cache clearing forces new request."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_NOAA_ARRAY_DATA

        with patch("httpx.Client.get", return_value=mock_resp) as mock_get:
            oracle = SpaceWeatherOracle()
            oracle.get_current_space_weather()
            oracle.clear_cache()
            oracle.get_current_space_weather()
            assert mock_get.call_count == 2

    def test_get_current_space_weather_http_error_fallback(self) -> None:
        """HTTP error with fallback enabled returns estimated/fallback report."""
        mock_resp = MagicMock()
        mock_resp.status_code = 503

        with patch("httpx.Client.get", side_effect=httpx.ConnectError("Network is down")):
            oracle = SpaceWeatherOracle(allow_fallback=True)
            success, report, msg = oracle.get_current_space_weather()

            assert success is True
            assert report is not None
            assert "fallback" in msg.lower() or "estimada" in msg.lower() or "nominal" in msg.lower()

    def test_get_current_space_weather_http_error_no_fallback(self) -> None:
        """HTTP error with fallback disabled returns (False, None, error_message)."""
        with patch("httpx.Client.get", side_effect=httpx.ConnectError("Network is down")):
            oracle = SpaceWeatherOracle(allow_fallback=False)
            success, report, msg = oracle.get_current_space_weather()

            assert success is False
            assert report is None
            assert "error" in msg.lower() or "falla" in msg.lower() or "down" in msg.lower()

    def test_get_current_space_weather_timeout(self) -> None:
        """Timeout triggers fallback gracefully."""
        with patch("httpx.Client.get", side_effect=httpx.TimeoutException("Timeout")):
            oracle = SpaceWeatherOracle(allow_fallback=True)
            success, report, msg = oracle.get_current_space_weather()

            assert success is True
            assert report is not None

    def test_get_current_space_weather_malformed_json(self) -> None:
        """Malformed, empty, or corrupt payload handled safely."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []

        with patch("httpx.Client.get", return_value=mock_resp):
            oracle = SpaceWeatherOracle(allow_fallback=True)
            success, report, msg = oracle.get_current_space_weather()

            assert success is True
            assert report is not None

    def test_get_current_space_weather_ssrf_blocked(self) -> None:
        """Attempts to target metadata or internal IPs are blocked."""
        oracle = SpaceWeatherOracle(api_url="http://169.254.169.254/latest/meta-data", allow_fallback=False)
        success, report, msg = oracle.get_current_space_weather()

        assert success is False
        assert report is None
        assert "ssrf" in msg.lower() or "bloquead" in msg.lower() or "prohibid" in msg.lower()

    def test_format_vocal_briefing(self) -> None:
        """Verify vocal briefing formatted in authentic J.A.R.V.I.S. cadence."""
        oracle = SpaceWeatherOracle()
        report = SpaceWeatherReport(
            kp_index=6.33,
            storm_level="G2 (Tormenta Moderada)",
            geomagnetic_status="Tormenta geomagnética moderada",
            timestamp="2026-10-13 18:00:00",
            radio_blackout_risk="Moderado",
            satellite_risk="Moderado",
            observed_at="2026-10-13 18:00:00",
        )
        briefing = oracle.format_vocal_briefing(report)

        assert "Telemetría espacial en línea, señor" in briefing
        assert "6.3" in briefing
        assert "G2 (Tormenta Moderada)" in briefing
        assert "Riesgo para satélites" in briefing
        assert "Riesgo de apagón de radio" in briefing

    def test_format_vocal_briefing_none_fallback(self) -> None:
        """Passing None report produces polite offline J.A.R.V.I.S. briefing."""
        oracle = SpaceWeatherOracle()
        briefing = oracle.format_vocal_briefing(None)  # type: ignore[arg-type]

        assert "Señor" in briefing
        assert "NOAA" in briefing
        assert "telemetría" in briefing.lower() or "escudos" in briefing.lower()
