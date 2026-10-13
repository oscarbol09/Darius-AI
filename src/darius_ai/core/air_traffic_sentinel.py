"""Air Traffic Sentinel — Multi-provider ADS-B / OpenSky & adsb.lol radar with Anti-SSRF and TTL caching."""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import Any

import httpx

try:
    from src.darius_ai.core.security_guard import AntiSSRFValidator
except ImportError:
    from darius_ai.core.security_guard import AntiSSRFValidator  # type: ignore[import-not-found,no-redef]

logger = logging.getLogger(__name__)


def _safe_float(val: Any) -> float | None:
    """Safely convert a value to float, returning None on failure."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two geographic coordinates in kilometers."""
    if lat1 == lat2 and lon1 == lon2:
        return 0.0

    earth_radius_km = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(d_lat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return round(earth_radius_km * c, 2)


@dataclass
class AircraftContact:
    """Represents an airborne or ground aircraft state vector observed via ADS-B."""

    icao24: str
    callsign: str
    origin_country: str
    latitude: float
    longitude: float
    altitude_m: float | None
    speed_kmh: float | None
    heading_deg: float | None
    vertical_rate_mps: float | None
    distance_km: float | None = None


class AirTrafficSentinel:
    """Multi-provider air traffic radar utilizing OpenSky Network with adsb.lol fallback."""

    OPENSKY_URL_TEMPLATE: str = (
        "https://opensky-network.org/api/states/all?"
        "lamin={lamin:.4f}&lomin={lomin:.4f}&lamax={lamax:.4f}&lomax={lomax:.4f}"
    )
    ADSBLOL_URL_TEMPLATE: str = "https://api.adsb.lol/v2/lat/{lat:.4f}/lon/{lon:.4f}/dist/{dist_nm}"

    def __init__(self, timeout: float = 8.0, cache_ttl_seconds: float = 10.0) -> None:
        self.timeout: float = timeout
        self.cache_ttl_seconds: float = cache_ttl_seconds
        self._cache_data: list[AircraftContact] = []
        self._cache_timestamp: float = 0.0
        self._cache_key: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def _calculate_bounding_box(
        self, lat: float, lon: float, radius_km: float
    ) -> tuple[float, float, float, float]:
        """Compute geographic bounding box (lamin, lomin, lamax, lomax) clamped to global coordinates."""
        delta_lat = radius_km / 111.0
        cos_lat = max(0.001, math.cos(math.radians(lat)))
        delta_lon = radius_km / (111.0 * cos_lat)

        lamin = max(-90.0, min(90.0, lat - delta_lat))
        lamax = max(-90.0, min(90.0, lat + delta_lat))
        lomin = max(-180.0, min(180.0, lon - delta_lon))
        lomax = max(-180.0, min(180.0, lon + delta_lon))

        return lamin, lomin, lamax, lomax

    def _fetch_opensky(self, lat: float, lon: float, radius_km: float) -> list[AircraftContact]:
        """Query OpenSky Network states endpoint within the computed bounding box."""
        lamin, lomin, lamax, lomax = self._calculate_bounding_box(lat, lon, radius_km)
        url = self.OPENSKY_URL_TEMPLATE.format(
            lamin=lamin,
            lomin=lomin,
            lamax=lamax,
            lomax=lomax,
        )

        is_safe, reason = AntiSSRFValidator.is_safe_url(url, allow_dns_lookup=False)
        if not is_safe:
            logger.warning("SSRF check rejected OpenSky URL '%s': %s", url, reason)
            raise ValueError(f"Blocked by security validator: {reason}")

        resp = httpx.get(url, timeout=self.timeout)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()

        states = data.get("states")
        if not isinstance(states, list):
            return []

        contacts: list[AircraftContact] = []
        for row in states:
            if not isinstance(row, list) or len(row) < 7:
                continue

            c_lon = _safe_float(row[5])
            c_lat = _safe_float(row[6])
            if c_lon is None or c_lat is None:
                continue

            raw_icao = str(row[0]).strip().lower() if row[0] is not None else "unknown"
            raw_callsign = str(row[1]).strip() if row[1] is not None else ""
            callsign = raw_callsign or raw_icao.upper()
            country = str(row[2]).strip() if row[2] is not None else "Unknown"

            baro_alt = row[7] if len(row) > 7 else None
            geo_alt = row[13] if len(row) > 13 else None
            alt_val = baro_alt if baro_alt is not None else geo_alt
            altitude_m = round(alt_f, 1) if (alt_f := _safe_float(alt_val)) is not None else None

            velocity = row[9] if len(row) > 9 else None
            speed_kmh = round(vel_f * 3.6, 1) if (vel_f := _safe_float(velocity)) is not None else None

            track = row[10] if len(row) > 10 else None
            heading_deg = round(trk_f, 1) if (trk_f := _safe_float(track)) is not None else None

            vertical_rate = row[11] if len(row) > 11 else None
            vertical_rate_mps = round(vr_f, 2) if (vr_f := _safe_float(vertical_rate)) is not None else None

            contacts.append(
                AircraftContact(
                    icao24=raw_icao,
                    callsign=callsign,
                    origin_country=country,
                    latitude=c_lat,
                    longitude=c_lon,
                    altitude_m=altitude_m,
                    speed_kmh=speed_kmh,
                    heading_deg=heading_deg,
                    vertical_rate_mps=vertical_rate_mps,
                )
            )

        return contacts

    def _fetch_adsb_lol(self, lat: float, lon: float, radius_km: float) -> list[AircraftContact]:
        """Fallback query to adsb.lol radius point API."""
        dist_nm = max(1, int(round(radius_km / 1.852)))
        url = self.ADSBLOL_URL_TEMPLATE.format(lat=lat, lon=lon, dist_nm=dist_nm)

        is_safe, reason = AntiSSRFValidator.is_safe_url(url, allow_dns_lookup=False)
        if not is_safe:
            logger.warning("SSRF check rejected adsb.lol URL '%s': %s", url, reason)
            raise ValueError(f"Blocked by security validator: {reason}")

        resp = httpx.get(url, timeout=self.timeout)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()

        aircraft_rows = data.get("ac") or data.get("aircraft")
        if not isinstance(aircraft_rows, list):
            return []

        contacts: list[AircraftContact] = []
        for item in aircraft_rows:
            if not isinstance(item, dict):
                continue

            raw_hex = str(item.get("hex", "")).strip().lower()
            c_lat = _safe_float(item.get("lat"))
            c_lon = _safe_float(item.get("lon"))
            if not raw_hex or c_lat is None or c_lon is None:
                continue

            raw_callsign = str(item.get("flight", "")).strip()
            callsign = raw_callsign or raw_hex.upper()

            alt_baro = item.get("alt_baro")
            altitude_m: float | None = None
            if alt_baro == "ground":
                altitude_m = 0.0
            elif (baro_f := _safe_float(alt_baro)) is not None:
                altitude_m = round(baro_f * 0.3048, 1)
            elif (geom_f := _safe_float(item.get("alt_geom"))) is not None:
                altitude_m = round(geom_f * 0.3048, 1)

            gs = item.get("gs")
            speed_kmh = round(gs_f * 1.852, 1) if (gs_f := _safe_float(gs)) is not None else None

            track = item.get("track")
            heading_deg = round(trk_f, 1) if (trk_f := _safe_float(track)) is not None else None

            baro_rate = item.get("baro_rate")
            vertical_rate_mps = round(br_f * 0.00508, 2) if (br_f := _safe_float(baro_rate)) is not None else None

            contacts.append(
                AircraftContact(
                    icao24=raw_hex,
                    callsign=callsign,
                    origin_country="Unknown",
                    latitude=c_lat,
                    longitude=c_lon,
                    altitude_m=altitude_m,
                    speed_kmh=speed_kmh,
                    heading_deg=heading_deg,
                    vertical_rate_mps=vertical_rate_mps,
                )
            )

        return contacts

    def scan_overhead(
        self,
        lat: float = 4.7110,
        lon: float = -74.0721,
        radius_km: float = 100.0,
        max_contacts: int = 5,
    ) -> tuple[bool, list[AircraftContact], str]:
        """Scan airspace surrounding the observer location and return contacts sorted by proximity."""
        cache_key = (round(lat, 3), round(lon, 3), round(radius_km, 1))
        now = time.time()

        if (
            self._cache_data
            and (now - self._cache_timestamp) < self.cache_ttl_seconds
            and self._cache_key == cache_key
        ):
            logger.debug("Returning cached air traffic contacts (age=%.1fs)", now - self._cache_timestamp)
            limited = self._cache_data[:max_contacts]
            return True, limited, self.format_vocal_radar(limited)

        contacts: list[AircraftContact] = []
        provider_used = "OpenSky"

        try:
            contacts = self._fetch_opensky(lat, lon, radius_km)
        except Exception as exc_opensky:
            logger.info("OpenSky query failed (%s); attempting adsb.lol fallback", exc_opensky)
            try:
                contacts = self._fetch_adsb_lol(lat, lon, radius_km)
                provider_used = "adsb.lol"
            except Exception as exc_fallback:
                logger.error("Both OpenSky and adsb.lol queries failed: %s; %s", exc_opensky, exc_fallback)
                msg = (
                    "Señor, los transpondedores ADS-B y el radar OpenSky no se encuentran disponibles "
                    "en este momento. Imposible establecer contacto telemétrico."
                )
                if "security validator" in str(exc_opensky) or "security validator" in str(exc_fallback):
                    msg = "Señor, la solicitud telemétrica ha sido bloqueada por directivas de seguridad anti-SSRF."
                return False, [], msg

        # Calculate distances and filter within circular radius
        verified_contacts: list[AircraftContact] = []
        for c in contacts:
            d = haversine_distance(lat, lon, c.latitude, c.longitude)
            if d <= radius_km:
                c.distance_km = d
                verified_contacts.append(c)

        # Sort ascending by proximity
        verified_contacts.sort(key=lambda item: item.distance_km if item.distance_km is not None else 999999.0)

        # Update cache
        self._cache_data = verified_contacts
        self._cache_timestamp = now
        self._cache_key = cache_key

        limited_contacts = verified_contacts[:max_contacts]
        vocal_report = self.format_vocal_radar(limited_contacts)
        logger.info(
            "Air traffic scan via %s found %d aircraft (limited to %d)",
            provider_used,
            len(verified_contacts),
            len(limited_contacts),
        )
        return True, limited_contacts, vocal_report

    def format_vocal_radar(self, contacts: list[AircraftContact], observer_name: str = "su posición") -> str:
        """Format contact details into J.A.R.V.I.S. butler vocal delivery cadence."""
        if not contacts:
            return (
                f"Señor, el sensor ADS-B no detecta aeronaves activas en el espacio aéreo sobre {observer_name}. "
                "El corredor permanece despejado."
            )

        count = len(contacts)
        plural = "aeronaves" if count != 1 else "aeronave"
        lead = contacts[0]

        dist_str = f"{lead.distance_km:.1f}" if lead.distance_km is not None else "proximidad no determinada"
        alt_str = f" a {lead.altitude_m:.0f} metros" if lead.altitude_m is not None else ""
        spd_str = f", desarrollando {lead.speed_kmh:.0f} km/h" if lead.speed_kmh is not None else ""

        report = (
            f"Señor, el sensor ADS-B reporta {count} {plural} en un radio táctico sobre {observer_name}. "
            f"La más próxima es el vuelo {lead.callsign} a {dist_str} km{alt_str}{spd_str}."
        )
        return report


_GLOBAL_AIR_TRAFFIC_SENTINEL: AirTrafficSentinel | None = None


def get_air_traffic_sentinel() -> AirTrafficSentinel:
    """Retorna la instancia singleton de AirTrafficSentinel."""
    global _GLOBAL_AIR_TRAFFIC_SENTINEL
    if _GLOBAL_AIR_TRAFFIC_SENTINEL is None:
        _GLOBAL_AIR_TRAFFIC_SENTINEL = AirTrafficSentinel()
    return _GLOBAL_AIR_TRAFFIC_SENTINEL
