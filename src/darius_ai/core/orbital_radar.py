"""Orbital Radar — ISS Real-Time Tracking, Observer Astrometry & Vocal Telemetry."""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass

import httpx

try:
    from src.darius_ai.core.security_guard import AntiSSRFValidator
except ImportError:
    from darius_ai.core.security_guard import AntiSSRFValidator  # type: ignore[import-not-found,no-redef]

logger = logging.getLogger(__name__)

DEFAULT_ISS_URL = "http://api.open-notify.org/iss-now.json"
EARTH_RADIUS_KM = 6371.0


@dataclass
class ISSPosition:
    """Represents the instantaneous kinematic position of the International Space Station."""

    latitude: float
    longitude: float
    timestamp: float
    altitude_km: float = 420.0
    speed_kmh: float = 27600.0
    visibility: str = "daylight"
    footprint_km: float = 2200.0


class OrbitalRadar:
    """Tracks ISS orbital coordinates via Open-Notify API with SSRF validation, caching, and fallback."""

    def __init__(
        self,
        api_url: str = DEFAULT_ISS_URL,
        client: httpx.Client | None = None,
        ttl_seconds: float = 5.0,
        allow_fallback: bool = True,
    ) -> None:
        self.api_url = api_url
        self._client = client
        self.ttl_seconds = ttl_seconds
        self.allow_fallback = allow_fallback

        self._cached_position: ISSPosition | None = None
        self._cache_timestamp: float = 0.0

    def clear_cache(self) -> None:
        """Clear cached telemetry."""
        self._cached_position = None
        self._cache_timestamp = 0.0

    @staticmethod
    def calculate_distance_to_observer(
        iss_lat: float, iss_lon: float, obs_lat: float, obs_lon: float
    ) -> float:
        """Calculate Great-Circle distance to observer in kilometers using Haversine formula."""
        phi1 = math.radians(iss_lat)
        phi2 = math.radians(obs_lat)
        delta_phi = math.radians(obs_lat - iss_lat)
        delta_lambda = math.radians(obs_lon - iss_lon)

        a = (
            math.sin(delta_phi / 2.0) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
        return EARTH_RADIUS_KM * c

    @staticmethod
    def calculate_bearing_to_observer(
        from_lat: float, from_lon: float, to_lat: float, to_lon: float
    ) -> float:
        """Calculate initial azimuth/bearing from observer to target coordinates in degrees (0-360)."""
        phi1 = math.radians(from_lat)
        phi2 = math.radians(to_lat)
        delta_lambda = math.radians(to_lon - from_lon)

        y = math.sin(delta_lambda) * math.cos(phi2)
        x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
        theta = math.atan2(y, x)
        return (math.degrees(theta) + 360.0) % 360.0

    def get_simulated_iss_position(self) -> ISSPosition:
        """Generate realistic simulated ISS telemetry based on current orbital period (~92.7 min)."""
        now = time.time()
        orbital_period_s = 5560.8
        fraction = (now % orbital_period_s) / orbital_period_s
        mean_anomaly = 2.0 * math.pi * fraction

        # ISS orbital inclination is 51.64 degrees
        lat = 51.64 * math.sin(mean_anomaly)

        # Longitude moves westward due to Earth rotation and eastward due to orbital track
        day_fraction = (now % 86400.0) / 86400.0
        lon = ((fraction * 360.0 - day_fraction * 360.0) + 180.0) % 360.0 - 180.0

        return ISSPosition(
            latitude=round(lat, 4),
            longitude=round(lon, 4),
            altitude_km=420.0,
            speed_kmh=27600.0,
            timestamp=now,
            visibility="daylight",
            footprint_km=2200.0,
        )

    def get_iss_position(self) -> tuple[bool, ISSPosition | None, str]:
        """Fetch current ISS position from Open-Notify API with caching and resilient fallback."""
        now = time.time()
        if self._cached_position is not None and (now - self._cache_timestamp) < self.ttl_seconds:
            return True, self._cached_position, "Telemetría de la ISS recuperada desde caché en memoria."

        # Anti-SSRF Validation
        safe, reason = AntiSSRFValidator.is_safe_url(self.api_url)
        if not safe:
            err = f"Acceso URL bloqueado por AntiSSRFValidator: {reason}"
            logger.warning(err)
            if self.allow_fallback:
                sim = self.get_simulated_iss_position()
                return True, sim, f"Telemetría estimada (URL bloqueada por AntiSSRF: {reason})"
            return False, None, err

        try:
            if self._client is not None:
                resp = self._client.get(self.api_url, timeout=5.0)
            else:
                with httpx.Client(timeout=5.0) as client:
                    resp = client.get(self.api_url)

            resp.raise_for_status()
            data = resp.json()

            if not isinstance(data, dict) or data.get("message") != "success" or "iss_position" not in data:
                raise ValueError(f"Payload inválido o incompleto de Open-Notify: {data}")

            pos_data = data["iss_position"]
            lat = float(pos_data["latitude"])
            lon = float(pos_data["longitude"])
            ts = float(data.get("timestamp", now))

            position = ISSPosition(
                latitude=lat,
                longitude=lon,
                timestamp=ts,
                altitude_km=420.0,
                speed_kmh=27600.0,
                visibility="daylight",
                footprint_km=2200.0,
            )

            self._cached_position = position
            self._cache_timestamp = now
            return True, position, "Telemetría orbital de la ISS obtenida con éxito."

        except Exception as exc:
            err_msg = f"Error al consultar telemetría ISS: {exc}"
            logger.warning(err_msg)
            if self.allow_fallback:
                sim_pos = self.get_simulated_iss_position()
                self._cached_position = sim_pos
                self._cache_timestamp = now
                return True, sim_pos, f"Telemetría orbital estimada/simulada (fallback activo por: {exc})"

            return False, None, err_msg

    def format_vocal_telemetry(
        self, iss: ISSPosition | None, observer_coords: tuple[float, float] | None = None
    ) -> str:
        """Format telemetry report in authentic J.A.R.V.I.S. cadence."""
        if iss is None:
            return (
                "Señor, los canales de telemetría con la Estación Espacial Internacional (ISS) no responden "
                "en este momento. Mantendré los sensores orbitales en escucha pasiva."
            )

        lat_str = f"{iss.latitude:.2f}"
        lon_str = f"{iss.longitude:.2f}"
        alt_str = f"{iss.altitude_km:.1f}"
        speed_str = f"{iss.speed_kmh:.0f}"

        msg = (
            f"Señor, la Estación Espacial Internacional (ISS) se encuentra actualmente sobrevolando "
            f"las coordenadas [{lat_str}°, {lon_str}°] a {alt_str} km de altitud, desplazándose a {speed_str} km/h. "
            f"Estado de visibilidad: {iss.visibility}."
        )

        if observer_coords is not None:
            dist = self.calculate_distance_to_observer(
                iss.latitude, iss.longitude, observer_coords[0], observer_coords[1]
            )
            bearing = self.calculate_bearing_to_observer(
                observer_coords[0], observer_coords[1], iss.latitude, iss.longitude
            )
            msg += f" Distancia estimada a su posición: {dist:.1f} km, con marcación azimutal de {bearing:.1f}°."

        return msg


_GLOBAL_ORBITAL_RADAR: OrbitalRadar | None = None


def get_orbital_radar() -> OrbitalRadar:
    """Retorna la instancia singleton de OrbitalRadar."""
    global _GLOBAL_ORBITAL_RADAR
    if _GLOBAL_ORBITAL_RADAR is None:
        _GLOBAL_ORBITAL_RADAR = OrbitalRadar()
    return _GLOBAL_ORBITAL_RADAR
