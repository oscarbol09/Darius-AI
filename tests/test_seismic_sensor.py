"""Unit tests for SeismicSensor (USGS GeoJSON, Anti-SSRF, TTL cache, tsunami alert, Butler cadence)."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure src is in sys.path
SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

try:
    from src.darius_ai.core.seismic_sensor import (
        SeismicEvent,
        SeismicSensor,
    )
except ImportError:
    from darius_ai.core.seismic_sensor import (  # type: ignore[import-not-found,no-redef]
        SeismicEvent,
        SeismicSensor,
    )


# Sample USGS GeoJSON
SAMPLE_USGS_GEOJSON = {
    "type": "FeatureCollection",
    "metadata": {
        "generated": 1773440000000,
        "url": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson",
        "title": "USGS Earthquakes, Past Day",
        "status": 200,
        "count": 4,
    },
    "features": [
        {
            "type": "Feature",
            "properties": {
                "mag": 7.2,
                "place": "120 km E of Sendai, Japan",
                "time": 1773439000000,
                "updated": 1773439500000,
                "url": "https://earthquake.usgs.gov/earthquakes/event/us7000test1",
                "tsunami": 1,
                "sig": 850,
                "type": "earthquake",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [142.36, 38.32, 24.5],  # [lon, lat, depth]
            },
            "id": "us7000test1",
        },
        {
            "type": "Feature",
            "properties": {
                "mag": 5.4,
                "place": "14 km SSW of Mesa de Los Santos, Colombia",
                "time": 1773438000000,
                "updated": 1773438500000,
                "url": "https://earthquake.usgs.gov/earthquakes/event/us7000test2",
                "tsunami": 0,
                "sig": 450,
                "type": "earthquake",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [-73.12, 6.78, 150.2],
            },
            "id": "us7000test2",
        },
        {
            "type": "Feature",
            "properties": {
                "mag": 3.1,  # below default 4.5 threshold
                "place": "Central California",
                "time": 1773437000000,
                "updated": 1773437500000,
                "url": "https://earthquake.usgs.gov/earthquakes/event/us7000test3",
                "tsunami": 0,
                "sig": 150,
                "type": "earthquake",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [-121.5, 36.8, 8.1],
            },
            "id": "us7000test3",
        },
        {
            "type": "Feature",
            "properties": {
                "mag": None,  # Malformed magnitude
                "place": "Unknown",
                "time": 1773436000000,
                "url": "",
                "tsunami": 0,
            },
            "geometry": {
                "type": "Point",
                "coordinates": [-100.0, 20.0, 10.0],
            },
            "id": "us7000test4",
        },
    ],
}


# ============================================================================
# Dataclass Tests
# ============================================================================


def test_seismic_event_dataclass_creation():
    event = SeismicEvent(
        event_id="us7000test1",
        magnitude=7.2,
        place="120 km E of Sendai, Japan",
        time_epoch_ms=1773439000000,
        depth_km=24.5,
        tsunami_alert=True,
        latitude=38.32,
        longitude=142.36,
        url="https://earthquake.usgs.gov/earthquakes/event/us7000test1",
    )
    assert event.event_id == "us7000test1"
    assert event.magnitude == 7.2
    assert event.place == "120 km E of Sendai, Japan"
    assert event.time_epoch_ms == 1773439000000
    assert event.depth_km == 24.5
    assert event.tsunami_alert is True
    assert event.latitude == 38.32
    assert event.longitude == 142.36
    assert event.url == "https://earthquake.usgs.gov/earthquakes/event/us7000test1"


def test_seismic_event_url_default():
    event = SeismicEvent(
        event_id="us7000test2",
        magnitude=5.4,
        place="Colombia",
        time_epoch_ms=1773438000000,
        depth_km=150.2,
        tsunami_alert=False,
        latitude=6.78,
        longitude=-73.12,
    )
    assert event.url == ""


# ============================================================================
# SeismicSensor Fetch & Parsing Tests
# ============================================================================


def test_get_recent_earthquakes_success():
    sensor = SeismicSensor()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_USGS_GEOJSON

    with patch("httpx.get", return_value=mock_resp) as mock_get:
        success, events, msg = sensor.get_recent_earthquakes(min_magnitude=4.5, limit=5)

        assert success is True
        assert len(events) == 2  # 7.2 and 5.4 meet min_mag 4.5, 3.1 and None are excluded
        assert events[0].event_id == "us7000test1"
        assert events[0].magnitude == 7.2
        assert events[0].latitude == 38.32
        assert events[0].longitude == 142.36
        assert events[0].depth_km == 24.5
        assert events[0].tsunami_alert is True

        assert events[1].event_id == "us7000test2"
        assert events[1].magnitude == 5.4
        assert events[1].tsunami_alert is False
        assert mock_get.called


def test_get_recent_earthquakes_min_magnitude_filter():
    sensor = SeismicSensor()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_USGS_GEOJSON

    with patch("httpx.get", return_value=mock_resp):
        # Filtering for major quakes >= 6.0
        success, events, _ = sensor.get_recent_earthquakes(min_magnitude=6.0, limit=5)
        assert success is True
        assert len(events) == 1
        assert events[0].magnitude == 7.2

        # Filtering lower threshold >= 3.0
        success2, events2, _ = sensor.get_recent_earthquakes(min_magnitude=3.0, limit=5)
        assert success2 is True
        assert len(events2) == 3


def test_get_recent_earthquakes_limit():
    sensor = SeismicSensor()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_USGS_GEOJSON

    with patch("httpx.get", return_value=mock_resp):
        success, events, _ = sensor.get_recent_earthquakes(min_magnitude=3.0, limit=2)
        assert success is True
        assert len(events) == 2


def test_get_recent_earthquakes_tsunami_flag_detection():
    sensor = SeismicSensor()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_USGS_GEOJSON

    with patch("httpx.get", return_value=mock_resp):
        success, events, _ = sensor.get_recent_earthquakes(min_magnitude=4.5)
        tsunami_events = [e for e in events if e.tsunami_alert]
        assert len(tsunami_events) == 1
        assert tsunami_events[0].event_id == "us7000test1"


def test_get_recent_earthquakes_sorted_by_recency():
    sensor = SeismicSensor()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_USGS_GEOJSON

    with patch("httpx.get", return_value=mock_resp):
        success, events, _ = sensor.get_recent_earthquakes(min_magnitude=4.5)
        # Event 1 is newer (1773439000000) than Event 2 (1773438000000)
        assert events[0].time_epoch_ms >= events[1].time_epoch_ms


def test_get_recent_earthquakes_ttl_cache():
    sensor = SeismicSensor(cache_ttl_seconds=300.0)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = SAMPLE_USGS_GEOJSON

    with patch("httpx.get", return_value=mock_resp) as mock_get:
        s1, e1, _ = sensor.get_recent_earthquakes(min_magnitude=4.5)
        assert s1 is True
        assert mock_get.call_count == 1

        # Second call immediately uses cache
        s2, e2, _ = sensor.get_recent_earthquakes(min_magnitude=4.5)
        assert s2 is True
        assert mock_get.call_count == 1
        assert len(e1) == len(e2)

        # Invalidate cache manually
        sensor._cache_timestamp = time.time() - 310.0
        s3, e3, _ = sensor.get_recent_earthquakes(min_magnitude=4.5)
        assert s3 is True
        assert mock_get.call_count == 2


def test_get_recent_earthquakes_network_failure_fallback():
    sensor = SeismicSensor()

    with patch("httpx.get", side_effect=Exception("USGS feed offline")):
        success, events, msg = sensor.get_recent_earthquakes()
        assert success is False
        assert events == []
        assert "Señor" in msg
        assert "USGS" in msg or "sísmic" in msg.lower()


def test_get_recent_earthquakes_anti_ssrf_blocks_unsafe():
    sensor = SeismicSensor()

    with patch(
        "src.darius_ai.core.seismic_sensor.AntiSSRFValidator.is_safe_url",
        return_value=(False, "SSRF Blocked"),
    ):
        success, events, msg = sensor.get_recent_earthquakes()
        assert success is False
        assert events == []
        msg_lower = msg.lower()
        assert any(term in msg_lower for term in ("seguridad", "bloquead", "ssrf", "señor"))


def test_get_recent_earthquakes_malformed_feature_handling():
    sensor = SeismicSensor()

    bad_geojson = {
        "features": [
            {"geometry": None, "properties": {"mag": 5.0}},
            {"geometry": {"type": "Point", "coordinates": []}, "properties": {"mag": 5.0}},
            {"geometry": {"type": "Polygon"}, "properties": {"mag": 5.0}},
            {"no_geom": True},
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = bad_geojson

    with patch("httpx.get", return_value=mock_resp):
        success, events, msg = sensor.get_recent_earthquakes(min_magnitude=4.5)
        assert success is True
        assert events == []


def test_get_recent_earthquakes_malformed_json_resilience():
    sensor = SeismicSensor()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = ValueError("Corrupted GeoJSON stream")

    with patch("httpx.get", return_value=mock_resp):
        success, events, msg = sensor.get_recent_earthquakes()
        assert success is False
        assert events == []


# ============================================================================
# Butler Vocal Alert Tests
# ============================================================================


def test_format_vocal_alert_with_events_no_tsunami():
    sensor = SeismicSensor()
    events = [
        SeismicEvent(
            event_id="col123",
            magnitude=5.4,
            place="Mesa de Los Santos, Colombia",
            time_epoch_ms=1773438000000,
            depth_km=150.2,
            tsunami_alert=False,
            latitude=6.78,
            longitude=-73.12,
        )
    ]

    alert = sensor.format_vocal_alert(events, min_magnitude=4.5)
    assert "Reporte sísmico global, señor" in alert
    assert "5.4" in alert
    assert "Mesa de Los Santos" in alert
    assert "tsunami" not in alert.lower() or "sin alerta de tsunami" in alert.lower()


def test_format_vocal_alert_with_tsunami_warning():
    sensor = SeismicSensor()
    events = [
        SeismicEvent(
            event_id="jp789",
            magnitude=7.5,
            place="Sendai, Japan",
            time_epoch_ms=1773439000000,
            depth_km=24.0,
            tsunami_alert=True,
            latitude=38.32,
            longitude=142.36,
        )
    ]

    alert = sensor.format_vocal_alert(events, min_magnitude=4.5)
    assert "Reporte sísmico global, señor" in alert
    assert "7.5" in alert
    assert "tsunami" in alert.lower()
    assert "Sendai" in alert


def test_format_vocal_alert_empty_events():
    sensor = SeismicSensor()
    alert = sensor.format_vocal_alert([], min_magnitude=4.5)
    assert "Reporte sísmico global, señor" in alert
    assert "No se han registrado" in alert or "sin actividad" in alert.lower() or "estable" in alert.lower()


def test_seismic_sensor_custom_feed_url():
    custom_url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson"
    sensor = SeismicSensor(feed_url=custom_url)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"features": []}

    with patch("httpx.get", return_value=mock_resp) as mock_get:
        success, events, _ = sensor.get_recent_earthquakes()
        assert success is True
        assert mock_get.call_args[0][0] == custom_url
