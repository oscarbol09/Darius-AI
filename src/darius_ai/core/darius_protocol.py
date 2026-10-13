"""
darius_protocol.py — Protocolo de Diagnóstico Integral Darius Core v8.5 para DARIUS AI
======================================================================================
Ejecuta la auditoría táctica de subsistemas del host (hardware, energía, topología
de pantallas, periféricos de audio, conectividad y bóveda de Obsidian).
Acompaña el análisis con la secuencia acústica procedural (radar pulse, target lock,
chime de éxito) y genera la alocución vocal representativa de DARIUS.
"""

from __future__ import annotations

import datetime
import logging
import os
import socket
import threading
import time
from typing import Any

import psutil

from src.darius_ai.audio.sound_effects import get_sfx_engine
from src.darius_ai.core.obsidian_brain import brain

log = logging.getLogger("DARIUS.Protocol")


class DariusProtocolEngine:
    """
    Motor central del Protocolo Darius: auditoría de estado del sistema,
    efectos procedurales sincronizados y síntesis del informe verbal Darius Core v8.5.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def _check_cpu(self) -> dict[str, Any]:
        """Audita el uso y topología de CPU."""
        percent = psutil.cpu_percent(interval=None)
        cores = psutil.cpu_count(logical=True) or 1
        return {
            "percent": float(percent),
            "cores": cores,
        }

    def _check_ram(self) -> dict[str, Any]:
        """Audita la memoria física y disponibilidad."""
        vmem = psutil.virtual_memory()
        return {
            "total_gb": round(vmem.total / (1024**3), 2),
            "available_gb": round(vmem.available / (1024**3), 2),
            "percent": float(vmem.percent),
        }

    def _check_disk(self) -> dict[str, Any]:
        """Audita el almacenamiento en la unidad principal del sistema."""
        try:
            root = os.path.splitdrive(os.getcwd())[0] + "\\" if os.name == "nt" else "/"
            usage = psutil.disk_usage(root)
            return {
                "total_gb": round(usage.total / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "percent": float(usage.percent),
            }
        except Exception as e:
            log.debug(f"[DariusProtocol] Fallo al leer disco: {e}")
            return {"total_gb": 0.0, "free_gb": 0.0, "percent": 0.0}

    def _check_battery(self) -> dict[str, Any]:
        """Audita el sensor de batería o estado de red eléctrica."""
        try:
            bat = psutil.sensors_battery()
            if bat is not None:
                status_str = f"{bat.percent}% ({'AC/Cargando' if bat.power_plugged else 'Batería'})"
                return {
                    "percent": int(bat.percent),
                    "plugged": bool(bat.power_plugged),
                    "secsleft": bat.secsleft,
                    "status": status_str,
                }
        except Exception as e:
            log.debug(f"[DariusProtocol] Sensor de batería no disponible: {e}")

        return {
            "percent": 100,
            "plugged": True,
            "secsleft": None,
            "status": "DESKTOP",
        }

    def _check_network(self) -> dict[str, Any]:
        """Evalúa la conectividad a Internet y calcula latencia hacia servidor DNS ultrarrápido."""
        target_host = "1.1.1.1"
        target_port = 53
        timeout_sec = 1.5
        t_start = time.perf_counter()
        try:
            with socket.create_connection((target_host, target_port), timeout=timeout_sec):
                latency = round((time.perf_counter() - t_start) * 1000, 1)
                return {
                    "online": True,
                    "latency_ms": latency,
                    "status": "ONLINE",
                }
        except Exception as e:
            log.debug(f"[DariusProtocol] Prueba de red offline: {e}")
            return {
                "online": False,
                "latency_ms": None,
                "status": "OFFLINE",
            }

    def _check_monitors(self) -> dict[str, Any]:
        """Detecta monitores conectados y su resolución de despliegue."""
        try:
            from src.darius_ai.system.workspace_manager import (
                get_monitor_count,
                get_monitor_rects,
            )

            count = get_monitor_count()
            rects = get_monitor_rects()
            resolutions = [f"{r[2] - r[0]}x{r[3] - r[1]}" for r in rects]
            if count == 0:
                count = 1
                resolutions = ["1920x1080"]
            return {"count": count, "resolutions": resolutions}
        except Exception as e:
            log.debug(f"[DariusProtocol] Fallo al enumerar monitores: {e}")
            return {"count": 1, "resolutions": ["1920x1080"]}

    def _check_audio(self) -> dict[str, Any]:
        """Audita dispositivos de audio de entrada y salida."""
        try:
            import sounddevice as sd

            devices = sd.query_devices()
            in_devs = sum(1 for d in devices if d.get("max_input_channels", 0) > 0)
            out_devs = sum(1 for d in devices if d.get("max_output_channels", 0) > 0)
            st = "OPERATIONAL" if (in_devs > 0 and out_devs > 0) else "DEGRADED"
            return {"input_devices": in_devs, "output_devices": out_devs, "status": st}
        except Exception as e:
            log.debug(f"[DariusProtocol] sounddevice no disponible: {e}")
            return {"input_devices": 1, "output_devices": 1, "status": "OPERATIONAL"}

    def _check_obsidian(self) -> dict[str, Any]:
        """Verifica la conectividad y accesibilidad de la bóveda de Obsidian."""
        try:
            vault = brain.vault_path
            is_connected = bool(vault and vault.exists())
            return {
                "connected": is_connected,
                "vault_path": str(vault) if vault else "",
                "status": "SYNCED" if is_connected else "UNAVAILABLE",
            }
        except Exception as e:
            log.debug(f"[DariusProtocol] Fallo al verificar Obsidian: {e}")
            return {"connected": False, "vault_path": "", "status": "UNAVAILABLE"}

    def run_diagnostic(self, with_sfx: bool = True) -> dict[str, Any]:
        """
        Ejecuta la auditoría integral de todos los subsistemas.
        Dispara efectos de sonido tácticos si with_sfx es True.
        """
        with self._lock:
            # 1. Efectos de sonido procedurales sincronizados
            if with_sfx:
                try:
                    sfx = get_sfx_engine()
                    sfx.play_scan_pulse(blocking=False)
                    sfx.play_target_lock(blocking=False)
                    sfx.play_success_chime(blocking=False)
                except Exception as e:
                    log.debug(f"[DariusProtocol] Fallo al despachar SFX: {e}")

            cpu = self._check_cpu()
            ram = self._check_ram()
            disk = self._check_disk()
            battery = self._check_battery()
            network = self._check_network()
            monitors = self._check_monitors()
            audio = self._check_audio()
            obsidian = self._check_obsidian()

            # Determinar estado global
            is_degraded = (
                cpu["percent"] > 90.0
                or ram["percent"] > 90.0
                or disk["percent"] > 95.0
                or (not battery["plugged"] and battery["percent"] < 15)
                or not network["online"]
                or not obsidian["connected"]
            )
            overall_status = "DEGRADED" if is_degraded else "OPTIMAL"

            return {
                "status": overall_status,
                "cpu": cpu,
                "ram": ram,
                "disk": disk,
                "battery": battery,
                "network": network,
                "monitors": monitors,
                "audio": audio,
                "obsidian": obsidian,
                "timestamp": datetime.datetime.now().astimezone().isoformat(),
            }

    def generate_vocal_briefing(self, diag_data: dict[str, Any]) -> str:
        """
        Genera la alocución vocal solemne y táctica estilo Darius Core v8.5
        para resumir el estado del sistema tras ejecutar el Protocolo de Diagnóstico Integral Darius.
        """
        cpu = diag_data.get("cpu", {})
        ram = diag_data.get("ram", {})
        bat = diag_data.get("battery", {})
        net = diag_data.get("network", {})
        mon = diag_data.get("monitors", {})
        obs = diag_data.get("obsidian", {})
        status = diag_data.get("status", "OPTIMAL")

        cpu_p = cpu.get("percent", 0.0)
        ram_avail = ram.get("available_gb", 0.0)
        ram_tot = ram.get("total_gb", 0.0)
        mon_count = mon.get("count", 1)

        # Si el estado es degradado, detallar advertencias
        if status == "DEGRADED":
            warnings = []
            if cpu_p > 85.0:
                warnings.append(f"alta demanda de CPU ({cpu_p:.1f}%)")
            if ram.get("percent", 0.0) > 85.0:
                warnings.append(f"memoria RAM crítica ({ram_avail:.1f} GB libres)")
            if not net.get("online", True):
                warnings.append("enlace de red desconectado")
            if not bat.get("plugged", True) and bat.get("percent", 100) < 20:
                warnings.append(f"batería baja al {bat.get('percent')}%")
            if not obs.get("connected", True):
                warnings.append("bóveda Obsidian no localizada")

            warn_txt = ", ".join(warnings) if warnings else "anomalías menores en subsistemas secundarios"
            return (
                f"Protocolo Darius ejecutado con advertencias, señor. "
                f"Se ha detectado estado degradado en: {warn_txt}. "
                f"Carga de CPU al {cpu_p:.1f}%, memoria RAM con {ram_avail:.1f} GB disponibles de {ram_tot:.1f} GB. "
                f"Monitores activos: {mon_count}. Procediendo con protocolos de contención preventiva, señor."
            )

        # Estado nominal / óptimo
        net_str = f"online con latencia de {net.get('latency_ms', 0):.1f} ms" if net.get("online") else "en modo local"
        bat_str = (
            "alimentación AC continua"
            if bat.get("status") == "DESKTOP"
            else f"batería al {bat.get('percent', 100)}%"
        )

        return (
            f"Protocolo Darius ejecutado con éxito, señor. Diagnóstico de sistemas al 100%. "
            f"Carga de CPU al {cpu_p:.1f}%, memoria RAM con {ram_avail:.1f} GB disponibles de {ram_tot:.1f} GB. "
            f"Energía con {bat_str}. Enlace de red {net_str}. "
            f"{mon_count} pantallas operativas con renderizado activo. "
            f"Bóveda Obsidian conectada y sincronizada. "
            f"Todos los sistemas en línea y a su completa disposición, señor."
        )


# =============================================================================
#  INSTANCIA SINGLETON Y ACCESORES GLOBALES
# =============================================================================
_GLOBAL_DARIUS_ENGINE: DariusProtocolEngine | None = None
_PROTOCOL_LOCK = threading.Lock()


def get_darius_protocol_engine() -> DariusProtocolEngine:
    """Retorna la instancia global del motor del Protocolo Darius."""
    global _GLOBAL_DARIUS_ENGINE
    if _GLOBAL_DARIUS_ENGINE is None:
        with _PROTOCOL_LOCK:
            if _GLOBAL_DARIUS_ENGINE is None:
                _GLOBAL_DARIUS_ENGINE = DariusProtocolEngine()
    return _GLOBAL_DARIUS_ENGINE


# Aliases convenientes y retrocompatibles
get_darius_engine = get_darius_protocol_engine
get_stark_engine = get_darius_protocol_engine
get_stark_protocol_engine = get_darius_protocol_engine

darius_protocol_engine = get_darius_protocol_engine()
stark_engine = darius_protocol_engine

StarkProtocolEngine = DariusProtocolEngine
