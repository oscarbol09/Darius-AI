"""Tests for OrbitalRadar and ISSPosition tracking module."""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

# Ensure src directory is in sys.path
SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

try:
    from src.darius_ai.core.orbital_radar import ISSPosition, OrbitalRadar
except ImportError:
    from darius_ai.core.orbital_radar import ISSPosition, OrbitalRadar  # type: ignore[import-not-found,no-redef]


# Mock Open-Notify payload
MOCK_OPEN_NOTIFY_SUCCESS = {
    "message": "success",
    "timestamp": 1728859200,
    "iss_position": {
        "latitude": "51.5074",
        "longitude": "-0.1278",
    },
}


class TestOrbitalRadar:
    """Test suite for OrbitalRadar and ISS tracking."""

    def test_iss_position_dataclass_defaults(self) -> None:
        """Verify default values and types on ISSPosition dataclass."""
        pos = ISSPosition(latitude=10.5, longitude=-20.5, timestamp=1700000000.0)
        assert pos.latitude == 10.5
        assert pos.longitude == -20.5
        assert pos.altitude_km == pytest.approx(420.0, rel=0.1)
        assert pos.speed_kmh == pytest.approx(27600.0, rel=0.1)
        assert pos.visibility == "daylight"
        assert pos.footprint_km == 2200.0

    def test_calculate_distance_haversine_same_point(self) -> None:
        """Distance between the same coordinates must be 0.0 km."""
        radar = OrbitalRadar()
        dist = radar.calculate_distance_to_observer(40.4168, -3.7038, 40.4168, -3.7038)
        assert dist == pytest.approx(0.0, abs=1e-3)

    def test_calculate_distance_haversine_known_locations(self) -> None:
        """Distance between Madrid and Paris is approximately 1050-1060 km."""
        radar = OrbitalRadar()
        # Madrid: 40.4168° N, 3.7038° W; Paris: 48.8566° N, 2.3522° E
        dist = radar.calculate_distance_to_observer(40.4168, -3.7038, 48.8566, 2.3522)
        assert 1040.0 < dist < 1070.0

    def test_calculate_distance_haversine_antipodal(self) -> None:
        """Distance between antipodal equator points is half the Earth's circumference (~20015 km)."""
        radar = OrbitalRadar()
        dist = radar.calculate_distance_to_observer(0.0, 0.0, 0.0, 180.0)
        assert dist == pytest.approx(math.pi * 6371.0, rel=0.01)

    def test_calculate_bearing_to_observer(self) -> None:
        """Bearing from (0, 0) directly North to (10, 0) should be 0 (or 360) degrees."""
        radar = OrbitalRadar()
        bearing = radar.calculate_bearing_to_observer(0.0, 0.0, 10.0, 0.0)
        assert bearing == pytest.approx(0.0, abs=0.5)

        # Due East from (0, 0) to (0, 10) should be 90 degrees
        bearing_east = radar.calculate_bearing_to_observer(0.0, 0.0, 0.0, 10.0)
        assert bearing_east == pytest.approx(90.0, abs=0.5)

    def test_get_iss_position_success(self) -> None:
        """Verify successful ISS position retrieval and parsing from Open-Notify."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_OPEN_NOTIFY_SUCCESS

        with patch("httpx.Client.get", return_value=mock_resp):
            radar = OrbitalRadar()
            success, pos, msg = radar.get_iss_position()

            assert success is True
            assert pos is not None
            assert pos.latitude == pytest.approx(51.5074)
            assert pos.longitude == pytest.approx(-0.1278)
            assert pos.timestamp == 1728859200.0
            assert "telemetría" in msg.lower() or "éxito" in msg.lower() or "success" in msg.lower()

    def test_get_iss_position_caching_within_ttl(self) -> None:
        """Successive requests within 5s TTL must return cached position without network calls."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_OPEN_NOTIFY_SUCCESS

        with patch("httpx.Client.get", return_value=mock_resp) as mock_get:
            radar = OrbitalRadar(ttl_seconds=5.0)
            res1 = radar.get_iss_position()
            res2 = radar.get_iss_position()

            assert res1[0] is True
            assert res2[0] is True
            assert res1[1] == res2[1]
            assert mock_get.call_count == 1

    def test_get_iss_position_cache_expiry(self) -> None:
        """Requests after TTL expiration must invoke a new HTTP request."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_OPEN_NOTIFY_SUCCESS

        with patch("httpx.Client.get", return_value=mock_resp) as mock_get:
            radar = OrbitalRadar(ttl_seconds=1.0)
            radar.get_iss_position()
            assert mock_get.call_count == 1

            # Advance cache timestamp
            radar._cache_timestamp -= 2.0

            radar.get_iss_position()
            assert mock_get.call_count == 2

    def test_get_iss_position_clear_cache(self) -> None:
        """Explicit cache clearance invalidates cache immediately."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_OPEN_NOTIFY_SUCCESS

        with patch("httpx.Client.get", return_value=mock_resp) as mock_get:
            radar = OrbitalRadar(ttl_seconds=10.0)
            radar.get_iss_position()
            radar.clear_cache()
            radar.get_iss_position()
            assert mock_get.call_count == 2

    def test_get_iss_position_http_error_with_fallback(self) -> None:
        """HTTP 500 error must trigger fallback telemetry safely without crashing."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Error", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client.get", side_effect=mock_resp.raise_for_status.side_effect):
            radar = OrbitalRadar(allow_fallback=True)
            success, pos, msg = radar.get_iss_position()

            assert success is True
            assert pos is not None
            assert "simulada" in msg.lower() or "estimada" in msg.lower() or "fallback" in msg.lower()

    def test_get_iss_position_http_error_without_fallback(self) -> None:
        """When fallback is disabled, HTTP error returns (False, None, error_message)."""
        with patch("httpx.Client.get", side_effect=httpx.ConnectError("Connection refused")):
            radar = OrbitalRadar(allow_fallback=False)
            success, pos, msg = radar.get_iss_position()

            assert success is False
            assert pos is None
            assert "error" in msg.lower() or "falla" in msg.lower()

    def test_get_iss_position_timeout_fallback(self) -> None:
        """Timeout triggers fallback telemetry cleanly."""
        with patch("httpx.Client.get", side_effect=httpx.TimeoutException("Timeout")):
            radar = OrbitalRadar(allow_fallback=True)
            success, pos, msg = radar.get_iss_position()

            assert success is True
            assert pos is not None

    def test_get_iss_position_malformed_json_fallback(self) -> None:
        """Malformed or incomplete JSON triggers fallback gracefully."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message": "failure"}

        with patch("httpx.Client.get", return_value=mock_resp):
            radar = OrbitalRadar(allow_fallback=True)
            success, pos, msg = radar.get_iss_position()

            assert success is True
            assert pos is not None

    def test_get_iss_position_ssrf_blocked(self) -> None:
        """Cloud metadata or private IP endpoints must be blocked by AntiSSRFValidator."""
        radar = OrbitalRadar(api_url="http://169.254.169.254/latest/meta-data/iss.json", allow_fallback=False)
        success, pos, msg = radar.get_iss_position()

        assert success is False
        assert pos is None
        assert "ssrf" in msg.lower() or "bloquead" in msg.lower() or "prohibid" in msg.lower()

    def test_format_vocal_telemetry_without_observer(self) -> None:
        """Vocal telemetry formatting in authentic J.A.R.V.I.S. cadence without observer."""
        radar = OrbitalRadar()
        pos = ISSPosition(
            latitude=25.7617,
            longitude=-80.1918,
            altitude_km=418.5,
            speed_kmh=27580.0,
            timestamp=time.time(),
            visibility="daylight",
        )
        briefing = radar.format_vocal_telemetry(pos)

        assert "Señor" in briefing
        assert "Estación Espacial Internacional" in briefing
        assert "25.76" in briefing
        assert "-80.19" in briefing
        assert "418.5" in briefing
        assert "27580" in briefing

    def test_format_vocal_telemetry_with_observer(self) -> None:
        """Vocal telemetry formatting with observer coordinates includes distance."""
        radar = OrbitalRadar()
        pos = ISSPosition(
            latitude=40.4168,
            longitude=-3.7038,
            altitude_km=420.0,
            speed_kmh=27600.0,
            timestamp=time.time(),
        )
        # Observer in Madrid (same coordinates)
        briefing = radar.format_vocal_telemetry(pos, observer_coords=(40.4168, -3.7038))

        assert "Señor" in briefing
        assert "distancia" in briefing.lower()
        assert "km" in briefing.lower()

    def test_format_vocal_telemetry_none_fallback(self) -> None:
        """Passing None for ISSPosition returns a polite offline butler notification."""
        radar = OrbitalRadar()
        briefing = radar.format_vocal_telemetry(None)  # type: ignore[arg-type]
        assert "Señor" in briefing
        assert "telemetría" in briefing.lower()
