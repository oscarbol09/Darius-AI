"""Unit tests for AirTrafficSentinel (OpenSky, adsb.lol fallback, Anti-SSRF, TTL cache, haversine, Butler cadence)."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure src is in sys.path
SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

try:
    from src.darius_ai.core.air_traffic_sentinel import (
        AircraftContact,
        AirTrafficSentinel,
        haversine_distance,
    )
except ImportError:
    from darius_ai.core.air_traffic_sentinel import (  # type: ignore[import-not-found,no-redef]
        AircraftContact,
        AirTrafficSentinel,
        haversine_distance,
    )


# Sample OpenSky response
SAMPLE_OPENSKY_PAYLOAD = {
    "time": 1773440000,
    "states": [
        [
            "0ac123",
            "AVA010  ",
            "Colombia",
            1773439990,
            1773439995,
            -74.1200,  # lon
            4.7200,   # lat
            3200.0,   # baro altitude (m)
            False,    # on ground
            180.5,    # velocity (m/s) -> ~649.8 km/h
            275.0,    # true track (deg)
            -5.2,     # vertical rate (m/s)
            None,
            3250.0,   # geo altitude (m)
            "1200",
            False,
            0,
            0,
        ],
        [
            "0ac456",
            "LAT404  ",
            "Chile",
            1773439980,
            1773439990,
            -74.0500,  # lon
            4.8000,   # lat
            7500.0,   # baro altitude (m)
            False,
            220.0,    # velocity (m/s) -> 792.0 km/h
            90.0,     # true track
            2.1,      # vertical rate
            None,
            7600.0,
            "2301",
            False,
            0,
            0,
        ],
        [
            "0ac999",
            "FARAWAY ",
            "Brazil",
            1773439980,
            1773439990,
            -70.0000,  # lon far away
            8.0000,   # lat far away (> 500 km)
            10000.0,
            False,
            250.0,
            180.0,
            0.0,
            None,
            10100.0,
            "4412",
            False,
            0,
            0,
        ],
        [
            "0ac000",
            "NOLATLON",
            "Unknown",
            1773439980,
            1773439990,
            None,     # Missing longitude
            None,     # Missing latitude
            None,
            False,
            None,
            None,
            None,
            None,
            None,
            None,
            False,
            0,
            0,
        ],
    ],
}

# Sample adsb.lol response
SAMPLE_ADSBLOL_PAYLOAD = {
    "ac": [
        {
            "hex": "0ac789",
            "flight": "SATENA21",
            "lat": 4.7300,
            "lon": -74.0800,
            "alt_baro": 12000,  # ft -> ~3657.6 m
            "alt_geom": 12150,
            "gs": 280.0,        # kts -> ~518.56 km/h
            "track": 180.5,     # deg
            "baro_rate": -500,  # ft/min -> ~ -2.54 m/s
            "category": "A3",
        },
        {
            "hex": "0ac321",
            "flight": "GND01   ",
            "lat": 4.7000,
            "lon": -74.1400,
            "alt_baro": "ground",
            "alt_geom": None,
            "gs": 15.0,
            "track": 45.0,
            "baro_rate": 0,
        },
    ],
    "total": 2,
    "ctime": 1773440010,
}


# ============================================================================
# Dataclass & Haversine Tests
# ============================================================================


def test_aircraft_contact_dataclass_creation():
    contact = AircraftContact(
        icao24="0ac123",
        callsign="AVA010",
        origin_country="Colombia",
        latitude=4.7200,
        longitude=-74.1200,
        altitude_m=3200.0,
        speed_kmh=649.8,
        heading_deg=275.0,
        vertical_rate_mps=-5.2,
        distance_km=5.4,
    )
    assert contact.icao24 == "0ac123"
    assert contact.callsign == "AVA010"
    assert contact.origin_country == "Colombia"
    assert contact.latitude == 4.7200
    assert contact.longitude == -74.1200
    assert contact.altitude_m == 3200.0
    assert contact.speed_kmh == 649.8
    assert contact.heading_deg == 275.0
    assert contact.vertical_rate_mps == -5.2
    assert contact.distance_km == 5.4


def test_aircraft_contact_default_distance():
    contact = AircraftContact(
        icao24="0ac123",
        callsign="AVA010",
        origin_country="Colombia",
        latitude=4.7200,
        longitude=-74.1200,
        altitude_m=None,
        speed_kmh=None,
        heading_deg=None,
        vertical_rate_mps=None,
    )
    assert contact.distance_km is None


def test_haversine_distance_accuracy():
    # Bogota center (4.7110, -74.0721) to El Dorado (4.7016, -74.1469) ~ 8.4 km
    dist = haversine_distance(4.7110, -74.0721, 4.7016, -74.1469)
    assert 7.5 < dist < 9.5

    # Same location must be 0.0
    assert haversine_distance(4.7110, -74.0721, 4.7110, -74.0721) == 0.0

    # Bogota to Medellin (6.2442, -75.5812) ~ 238.7 km
    dist_medellin = haversine_distance(4.7110, -74.0721, 6.2442, -75.5812)
    assert 210.0 < dist_medellin < 250.0


# ============================================================================
# AirTrafficSentinel Scan Overhead Tests
# ============================================================================


def test_scan_overhead_opensky_success():
    sentinel = AirTrafficSentinel(timeout=5.0)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_OPENSKY_PAYLOAD

    with patch("httpx.get", return_value=mock_resp) as mock_get:
        success, contacts, msg = sentinel.scan_overhead(lat=4.7110, lon=-74.0721, radius_km=50.0, max_contacts=5)

        assert success is True
        assert len(contacts) == 2  # FARAWAY (8.0, -70.0) is filtered by radius 50 km, and NOLATLON is skipped
        assert contacts[0].icao24 == "0ac123"
        assert contacts[0].callsign == "AVA010"
        assert contacts[0].origin_country == "Colombia"
        assert contacts[0].speed_kmh == pytest.approx(649.8, 0.1)
        assert contacts[0].altitude_m == 3200.0
        assert contacts[0].distance_km is not None
        assert contacts[0].distance_km < contacts[1].distance_km  # Proximity sorted
        assert mock_get.called
        assert "opensky-network.org" in mock_get.call_args[0][0]


def test_scan_overhead_filters_out_of_radius():
    sentinel = AirTrafficSentinel()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_OPENSKY_PAYLOAD

    with patch("httpx.get", return_value=mock_resp):
        # Small radius 5 km: only AVA010 or neither
        success, contacts, _ = sentinel.scan_overhead(lat=4.7110, lon=-74.0721, radius_km=10.0, max_contacts=5)
        assert success is True
        for c in contacts:
            assert c.distance_km is not None
            assert c.distance_km <= 10.0


def test_scan_overhead_max_contacts_limit():
    sentinel = AirTrafficSentinel()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_OPENSKY_PAYLOAD

    with patch("httpx.get", return_value=mock_resp):
        success, contacts, _ = sentinel.scan_overhead(lat=4.7110, lon=-74.0721, radius_km=100.0, max_contacts=1)
        assert success is True
        assert len(contacts) == 1


def test_scan_overhead_fallback_to_adsb_lol():
    sentinel = AirTrafficSentinel()

    opensky_fail = MagicMock()
    opensky_fail.status_code = 502
    opensky_fail.raise_for_status.side_effect = Exception("OpenSky Gateway Timeout")

    adsb_success = MagicMock()
    adsb_success.status_code = 200
    adsb_success.json.return_value = SAMPLE_ADSBLOL_PAYLOAD

    def side_effect_get(url, *args, **kwargs):
        if "opensky-network.org" in url:
            raise Exception("OpenSky unreachable")
        if "api.adsb.lol" in url:
            return adsb_success
        raise ValueError(f"Unexpected url: {url}")

    with patch("httpx.get", side_effect=side_effect_get):
        success, contacts, msg = sentinel.scan_overhead(lat=4.7110, lon=-74.0721, radius_km=50.0)

        assert success is True
        assert len(contacts) == 2
        # SATENA21
        assert contacts[0].callsign == "SATENA21"
        assert contacts[0].altitude_m == pytest.approx(12000 * 0.3048, 0.1)
        assert contacts[0].speed_kmh == pytest.approx(280.0 * 1.852, 0.1)
        # Ground aircraft GND01
        assert contacts[1].callsign == "GND01"
        assert contacts[1].altitude_m == 0.0 or contacts[1].altitude_m is None


def test_scan_overhead_both_providers_fail_graceful_fallback():
    sentinel = AirTrafficSentinel()

    with patch("httpx.get", side_effect=Exception("Total network isolation")):
        success, contacts, msg = sentinel.scan_overhead(lat=4.7110, lon=-74.0721, radius_km=50.0)
        assert success is False
        assert contacts == []
        assert "Señor" in msg
        assert "ADS-B" in msg or "radar" in msg.lower()


def test_scan_overhead_ttl_cache():
    sentinel = AirTrafficSentinel(cache_ttl_seconds=10.0)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_OPENSKY_PAYLOAD

    with patch("httpx.get", return_value=mock_resp) as mock_get:
        # First call hits network
        s1, c1, _ = sentinel.scan_overhead(lat=4.7110, lon=-74.0721, radius_km=50.0)
        assert s1 is True
        assert mock_get.call_count == 1

        # Second immediate call uses cache
        s2, c2, _ = sentinel.scan_overhead(lat=4.7110, lon=-74.0721, radius_km=50.0)
        assert s2 is True
        assert mock_get.call_count == 1
        assert len(c1) == len(c2)

        # Invalidate cache by simulating expiration
        sentinel._cache_timestamp = time.time() - 15.0
        s3, c3, _ = sentinel.scan_overhead(lat=4.7110, lon=-74.0721, radius_km=50.0)
        assert s3 is True
        assert mock_get.call_count == 2


def test_scan_overhead_ssrf_validator_blocks_malicious_target():
    sentinel = AirTrafficSentinel()

    with patch(
        "src.darius_ai.core.air_traffic_sentinel.AntiSSRFValidator.is_safe_url",
        return_value=(False, "SSRF attempt"),
    ):
        success, contacts, msg = sentinel.scan_overhead()
        assert success is False
        assert contacts == []
        msg_lower = msg.lower()
        assert any(term in msg_lower for term in ("seguridad", "bloqueada", "ssrf", "señor"))


def test_scan_overhead_bounding_box_clamping():
    sentinel = AirTrafficSentinel()
    # Observer at North Pole
    lamin, lomin, lamax, lomax = sentinel._calculate_bounding_box(lat=89.9, lon=0.0, radius_km=200.0)
    assert lamin >= -90.0
    assert lamax <= 90.0
    assert lomin >= -180.0
    assert lomax <= 180.0


def test_scan_overhead_malformed_json_resilience():
    sentinel = AirTrafficSentinel()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = ValueError("Malformed JSON payload")

    with patch("httpx.get", return_value=mock_resp):
        success, contacts, msg = sentinel.scan_overhead()
        assert success is False
        assert contacts == []


# ============================================================================
# Butler Vocal Formatting Tests
# ============================================================================


def test_format_vocal_radar_with_contacts():
    sentinel = AirTrafficSentinel()
    contacts = [
        AircraftContact(
            icao24="0ac123",
            callsign="AVA010",
            origin_country="Colombia",
            latitude=4.7200,
            longitude=-74.1200,
            altitude_m=3200.0,
            speed_kmh=649.8,
            heading_deg=275.0,
            vertical_rate_mps=-5.2,
            distance_km=5.4,
        ),
        AircraftContact(
            icao24="0ac456",
            callsign="LAT404",
            origin_country="Chile",
            latitude=4.8000,
            longitude=-74.0500,
            altitude_m=7500.0,
            speed_kmh=792.0,
            heading_deg=90.0,
            vertical_rate_mps=2.1,
            distance_km=10.2,
        ),
    ]

    briefing = sentinel.format_vocal_radar(contacts, observer_name="Bogotá")
    assert "Señor" in briefing
    assert "2 aeronaves" in briefing or "2" in briefing
    assert "AVA010" in briefing
    assert "5.4" in briefing or "5" in briefing


def test_format_vocal_radar_empty():
    sentinel = AirTrafficSentinel()
    briefing = sentinel.format_vocal_radar([], observer_name="su posición")
    assert "Señor" in briefing
    assert "no detecta" in briefing or "ninguna" in briefing or "despejado" in briefing
