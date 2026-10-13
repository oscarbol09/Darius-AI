"""Space Weather Oracle — NOAA Space Weather Prediction Center (SWPC) Planetary K-index & Geomagnetic Storm Monitor."""

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

DEFAULT_NOAA_KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"


@dataclass
class SpaceWeatherReport:
    """Represents a space weather report containing geomagnetic and solar storm metrics."""

    kp_index: float
    storm_level: str
    geomagnetic_status: str
    timestamp: str
    radio_blackout_risk: str
    satellite_risk: str
    observed_at: str = ""


class SpaceWeatherOracle:
    """Consumes NOAA SWPC planetary K-index with AntiSSRF validation, TTL caching, and Butler vocal formatting."""

    def __init__(
        self,
        api_url: str = DEFAULT_NOAA_KP_URL,
        client: httpx.Client | None = None,
        ttl_seconds: float = 900.0,
        allow_fallback: bool = True,
    ) -> None:
        self.api_url = api_url
        self._client = client
        self.ttl_seconds = ttl_seconds
        self.allow_fallback = allow_fallback

        self._cached_report: SpaceWeatherReport | None = None
        self._cache_timestamp: float = 0.0

    def clear_cache(self) -> None:
        """Invalidate currently cached report."""
        self._cached_report = None
        self._cache_timestamp = 0.0

    @staticmethod
    def classify_kp(kp: float) -> dict[str, str]:
        """Classify planetary K-index into storm level, geomagnetic status, and mission operational risks."""
        if kp < 4.0:
            return {
                "storm_level": "G0 (Tranquilo / Nominal)",
                "geomagnetic_status": "Nominal / Campo geomagnético en calma",
                "radio_blackout_risk": "Bajo / Sin perturbaciones HF",
                "satellite_risk": "Mínimo / Operaciones orbitales nominales",
            }
        elif kp < 5.0:
            return {
                "storm_level": "G0+ (Activo)",
                "geomagnetic_status": "Actividad geomagnética no tormentosa",
                "radio_blackout_risk": "Bajo / Leves fluctuaciones en altas latitudes",
                "satellite_risk": "Bajo / Variaciones menores en resistencia aerodinámica",
            }
        elif kp < 6.0:
            return {
                "storm_level": "G1 (Tormenta Menor)",
                "geomagnetic_status": "Tormenta geomagnética menor",
                "radio_blackout_risk": "Menor / Débiles degradaciones en HF en polos",
                "satellite_risk": "Leve / Impacto menor en operaciones de satélites en LEO",
            }
        elif kp < 7.0:
            return {
                "storm_level": "G2 (Tormenta Moderada)",
                "geomagnetic_status": "Tormenta geomagnética moderada",
                "radio_blackout_risk": "Moderado / Desvanecimientos en HF de alta latitud",
                "satellite_risk": "Moderado / Posible incremento de arrastre en LEO y carga electrostática",
            }
        elif kp < 8.0:
            return {
                "storm_level": "G3 (Tormenta Fuerte)",
                "geomagnetic_status": "Tormenta geomagnética fuerte",
                "radio_blackout_risk": "Elevado / Problemas de propagación de radio HF intermitentes",
                "satellite_risk": "Alto / Carga superficial en componentes satelitales y correcciones de orientación",
            }
        elif kp < 9.0:
            return {
                "storm_level": "G4 (Tormenta Severa)",
                "geomagnetic_status": "Tormenta geomagnética severa",
                "radio_blackout_risk": "Severo / Apagón de radio HF generalizado en lados diurnos",
                "satellite_risk": "Crítico / Problemas de seguimiento, aumento crítico de arrastre orbital",
            }
        else:
            return {
                "storm_level": "G5 (Tormenta Extrema)",
                "geomagnetic_status": "Tormenta geomagnética extrema",
                "radio_blackout_risk": "Extremo / Apagón total de comunicaciones de radio HF durante horas",
                "satellite_risk": (
                    "Extremo / Anomalías graves de telemetría y orientación, riesgo de pérdida de satélites"
                ),
            }

    def get_simulated_report(self) -> SpaceWeatherReport:
        """Generate baseline simulated space weather report during outages."""
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        kp = 2.33
        cls = self.classify_kp(kp)
        return SpaceWeatherReport(
            kp_index=kp,
            storm_level=cls["storm_level"],
            geomagnetic_status=cls["geomagnetic_status"],
            timestamp=now_str,
            radio_blackout_risk=cls["radio_blackout_risk"],
            satellite_risk=cls["satellite_risk"],
            observed_at=now_str,
        )

    def _parse_noaa_payload(self, data: Any) -> tuple[float, str]:
        """Extract latest planetary K-index and timestamp from NOAA JSON payload."""
        if not isinstance(data, list) or not data:
            raise ValueError("Payload de NOAA SWPC no es una lista válida o está vacía")

        # Table format with header row
        if isinstance(data[0], list):
            headers = [str(col).lower() for col in data[0]]
            kp_idx = -1
            time_idx = -1
            for i, col in enumerate(headers):
                if "kp" in col:
                    kp_idx = i
                elif "time" in col:
                    time_idx = i

            if kp_idx == -1:
                kp_idx = 1 if len(data[0]) > 1 else 0
            if time_idx == -1:
                time_idx = 0

            # Last row contains newest reading
            last_row = data[-1]
            if len(data) > 1 and last_row != data[0]:
                kp_val = float(last_row[kp_idx])
                obs_time = str(last_row[time_idx])
                return kp_val, obs_time
            raise ValueError("Tabla de NOAA SWPC sin filas de datos válidas")

        # Dict format
        if isinstance(data[0], dict):
            last_entry = data[-1]
            raw_kp = last_entry.get("Kp") or last_entry.get("kp") or last_entry.get("kp_index")
            if raw_kp is None:
                raise ValueError("Clave Kp ausente en el objeto de NOAA")
            kp_val = float(raw_kp)
            obs_time = str(last_entry.get("time_tag") or last_entry.get("time") or time.strftime("%Y-%m-%d %H:%M:%S"))
            return kp_val, obs_time

        raise ValueError("Estructura de datos desconocida en respuesta NOAA")

    def get_current_space_weather(self) -> tuple[bool, SpaceWeatherReport | None, str]:
        """Fetch latest planetary K-index from NOAA SWPC with caching, SSRF checks, and fallback."""
        now = time.time()
        if self._cached_report is not None and (now - self._cache_timestamp) < self.ttl_seconds:
            return True, self._cached_report, "Telemetría de clima espacial recuperada desde caché en memoria."

        # Anti-SSRF check
        safe, reason = AntiSSRFValidator.is_safe_url(self.api_url)
        if not safe:
            err = f"Acceso URL bloqueado por AntiSSRFValidator: {reason}"
            logger.warning(err)
            if self.allow_fallback:
                sim = self.get_simulated_report()
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

            kp_val, obs_time = self._parse_noaa_payload(data)
            cls = self.classify_kp(kp_val)
            now_iso = time.strftime("%Y-%m-%d %H:%M:%S")

            report = SpaceWeatherReport(
                kp_index=kp_val,
                storm_level=cls["storm_level"],
                geomagnetic_status=cls["geomagnetic_status"],
                timestamp=now_iso,
                radio_blackout_risk=cls["radio_blackout_risk"],
                satellite_risk=cls["satellite_risk"],
                observed_at=obs_time,
            )

            self._cached_report = report
            self._cache_timestamp = now
            return True, report, "Telemetría de clima espacial de la NOAA obtenida con éxito."

        except Exception as exc:
            err_msg = f"Error al consultar clima espacial de NOAA: {exc}"
            logger.warning(err_msg)
            if self.allow_fallback:
                sim_rep = self.get_simulated_report()
                self._cached_report = sim_rep
                self._cache_timestamp = now
                return True, sim_rep, f"Telemetría espacial estimada/simulada (fallback activo por: {exc})"

            return False, None, err_msg

    def format_vocal_briefing(self, report: SpaceWeatherReport | None) -> str:
        """Format space weather briefing in authentic J.A.R.V.I.S. cadence."""
        if report is None:
            return (
                "Señor, los sensores del Centro de Predicción del Clima Espacial de la NOAA no responden "
                "en este momento. Mantendré los escudos y la telemetría en estado de alerta pasiva."
            )

        kp_str = f"{report.kp_index:.1f}"
        return (
            f"Telemetría espacial en línea, señor. Índice Kp planetario en nivel {kp_str}, "
            f"clasificado como {report.storm_level}. Estado geomagnético: {report.geomagnetic_status}. "
            f"Riesgo para satélites: {report.satellite_risk}. Riesgo de apagón de radio: {report.radio_blackout_risk}."
        )


_GLOBAL_SPACE_WEATHER_ORACLE: SpaceWeatherOracle | None = None


def get_space_weather_oracle() -> SpaceWeatherOracle:
    """Retorna la instancia singleton de SpaceWeatherOracle."""
    global _GLOBAL_SPACE_WEATHER_ORACLE
    if _GLOBAL_SPACE_WEATHER_ORACLE is None:
        _GLOBAL_SPACE_WEATHER_ORACLE = SpaceWeatherOracle()
    return _GLOBAL_SPACE_WEATHER_ORACLE
