"""Seismic Sensor — USGS GeoJSON global earthquake telemetry with Anti-SSRF, TTL cache, and Butler vocal alerts."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

try:
    from src.darius_ai.core.security_guard import AntiSSRFValidator
except ImportError:
    from darius_ai.core.security_guard import AntiSSRFValidator  # type: ignore[import-not-found,no-redef]

logger = logging.getLogger(__name__)


@dataclass
class SeismicEvent:
    """Represents a validated seismic event registered by geological survey networks."""

    event_id: str
    magnitude: float
    place: str
    time_epoch_ms: int
    depth_km: float
    tsunami_alert: bool
    latitude: float
    longitude: float
    url: str = ""


class SeismicSensor:
    """USGS Earthquake GeoJSON feed monitor with Anti-SSRF validation, TTL caching, and Butler alert synthesis."""

    DEFAULT_FEED_URL: str = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"

    def __init__(
        self,
        feed_url: str | None = None,
        timeout: float = 8.0,
        cache_ttl_seconds: float = 300.0,
    ) -> None:
        self.feed_url: str = feed_url or self.DEFAULT_FEED_URL
        self.timeout: float = timeout
        self.cache_ttl_seconds: float = cache_ttl_seconds
        self._cache_data: list[SeismicEvent] = []
        self._cache_timestamp: float = 0.0

    def _fetch_usgs_events(self) -> list[SeismicEvent]:
        """Fetch and normalize USGS GeoJSON earthquake features."""
        is_safe, reason = AntiSSRFValidator.is_safe_url(self.feed_url, allow_dns_lookup=False)
        if not is_safe:
            logger.warning("SSRF check rejected USGS feed URL '%s': %s", self.feed_url, reason)
            raise ValueError(f"Blocked by security validator: {reason}")

        resp = httpx.get(self.feed_url, timeout=self.timeout)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()

        features = data.get("features")
        if not isinstance(features, list):
            return []

        events: list[SeismicEvent] = []
        for feature in features:
            if not isinstance(feature, dict):
                continue

            properties = feature.get("properties")
            geometry = feature.get("geometry")
            if not isinstance(properties, dict) or not isinstance(geometry, dict):
                continue

            coords = geometry.get("coordinates")
            if not isinstance(coords, list) or len(coords) < 2:
                continue

            # GeoJSON standard coordinates: [lon, lat, depth]
            raw_lon, raw_lat = coords[0], coords[1]
            raw_depth = coords[2] if len(coords) > 2 else 0.0

            try:
                lon = float(raw_lon)
                lat = float(raw_lat)
                depth = float(raw_depth) if raw_depth is not None else 0.0
            except (ValueError, TypeError):
                continue

            raw_mag = properties.get("mag")
            if raw_mag is None:
                continue
            try:
                mag = round(float(raw_mag), 2)
            except (ValueError, TypeError):
                continue

            event_id = str(feature.get("id") or properties.get("code") or "unknown_event")
            place = str(properties.get("place") or "Ubicación no especificada").strip()
            time_ms = int(properties.get("time") or 0)
            tsunami = bool(properties.get("tsunami", 0))
            url = str(properties.get("url") or "")

            events.append(
                SeismicEvent(
                    event_id=event_id,
                    magnitude=mag,
                    place=place,
                    time_epoch_ms=time_ms,
                    depth_km=round(depth, 1),
                    tsunami_alert=tsunami,
                    latitude=lat,
                    longitude=lon,
                    url=url,
                )
            )

        return events

    def get_recent_earthquakes(
        self, min_magnitude: float = 4.5, limit: int = 5
    ) -> tuple[bool, list[SeismicEvent], str]:
        """Query recent seismic events matching the minimum magnitude threshold."""
        now = time.time()

        if self._cache_data and (now - self._cache_timestamp) < self.cache_ttl_seconds:
            logger.debug("Returning cached seismic events (age=%.1fs)", now - self._cache_timestamp)
            filtered = [e for e in self._cache_data if e.magnitude >= min_magnitude]
            limited = filtered[:limit]
            return True, limited, self.format_vocal_alert(limited, min_magnitude)

        try:
            raw_events = self._fetch_usgs_events()
        except Exception as exc:
            logger.error("USGS seismic feed query failed: %s", exc)
            msg = (
                "Señor, los sensores del servicio geológico USGS no responden en este momento. "
                "Imposible sincronizar la telemetría sísmica global."
            )
            if "security validator" in str(exc):
                msg = "Señor, la solicitud telemétrica ha sido bloqueada por directivas de seguridad anti-SSRF."
            return False, [], msg

        # Sort descending by recency
        raw_events.sort(key=lambda ev: ev.time_epoch_ms, reverse=True)

        self._cache_data = raw_events
        self._cache_timestamp = now

        filtered_events = [e for e in raw_events if e.magnitude >= min_magnitude]
        limited_events = filtered_events[:limit]
        vocal_alert = self.format_vocal_alert(limited_events, min_magnitude)

        logger.info(
            "Seismic scan completed: %d total events, %d meet >= M%.1f threshold (limited to %d)",
            len(raw_events),
            len(filtered_events),
            min_magnitude,
            len(limited_events),
        )
        return True, limited_events, vocal_alert

    def format_vocal_alert(self, events: list[SeismicEvent], min_magnitude: float = 4.5) -> str:
        """Format seismic events into an authoritative Butler auditory brief."""
        if not events:
            return (
                f"Reporte sísmico global, señor. No se han registrado movimientos telúricos relevantes "
                f"de magnitud superior a {min_magnitude:.1f} en las últimas 24 horas. "
                "La corteza terrestre permanece estable."
            )

        count = len(events)
        plural = "movimientos telúricos" if count != 1 else "movimiento telúrico"

        # Find most intense event for primary emphasis
        primary = max(events, key=lambda ev: ev.magnitude)

        tsunami_events = [ev for ev in events if ev.tsunami_alert]
        tsunami_warning = ""
        if tsunami_events:
            tsunami_places = ", ".join(ev.place for ev in tsunami_events[:2])
            tsunami_warning = (
                f" ADVERTENCIA CRÍTICA: Se ha emitido alerta activa de tsunami para la región de {tsunami_places}."
            )

        report = (
            f"Reporte sísmico global, señor. En las últimas 24 horas se registraron {count} {plural} "
            f"de magnitud superior a {min_magnitude:.1f}. El evento más significativo fue de magnitud "
            f"{primary.magnitude:.1f} en {primary.place}, a una profundidad de {primary.depth_km:.1f} km."
            f"{tsunami_warning}"
        )
        return report


_GLOBAL_SEISMIC_SENSOR: SeismicSensor | None = None


def get_seismic_sensor() -> SeismicSensor:
    """Retorna la instancia singleton de SeismicSensor."""
    global _GLOBAL_SEISMIC_SENSOR
    if _GLOBAL_SEISMIC_SENSOR is None:
        _GLOBAL_SEISMIC_SENSOR = SeismicSensor()
    return _GLOBAL_SEISMIC_SENSOR
