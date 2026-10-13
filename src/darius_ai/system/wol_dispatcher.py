"""
wol_dispatcher.py — Despachador Wake-on-LAN (WOL) Táctico para DARIUS AI
========================================================================
Gestiona el encendido remoto de nodos de infraestructura, rigs de cómputo y servidores
en la red local mediante tramas RFC Magic Packet (102 bytes) sobre difusión UDP.
Módulo táctico de encendido remoto para nodos e infraestructura de Darius AI.
"""

from __future__ import annotations

import contextlib
import ipaddress
import logging
import re
import socket
import threading
from dataclasses import dataclass

import psutil

from src.darius_ai.audio.sound_effects import get_sfx_engine

log = logging.getLogger("DARIUS.WOL")


class WOLError(ValueError):
    """Excepción para errores de validación y despacho de tramas Wake-on-LAN."""


@dataclass
class WOLTarget:
    """Perfil de nodo de destino para transmisiones Wake-on-LAN."""

    alias: str
    name: str
    mac_address: str
    broadcast_ip: str | None = None
    port: int = 9
    description: str = ""


class DariusWOLDispatcher:
    """
    Despachador central de tramas Wake-on-LAN con validación estricta de capa de enlace,
    cálculo de difusión multi-interfaz y confirmaciones acústicas procedurales de Darius AI.
    """

    def __init__(self) -> None:
        self._targets: dict[str, WOLTarget] = {}
        self._lock = threading.Lock()
        self._register_default_profiles()

    def _register_default_profiles(self) -> None:
        """Inicializa perfiles tácticos predeterminados del ecosistema Darius AI."""
        defaults = [
            WOLTarget(
                alias="gaming_rig",
                name="Gaming Rig (Darius Station)",
                mac_address="00:11:22:33:44:55",
                port=9,
                description="Estación principal de alta computación y renderizado",
            ),
            WOLTarget(
                alias="nas",
                name="NAS Storage Vault",
                mac_address="00:11:22:33:44:66",
                port=9,
                description="Almacén central de copias de seguridad y archivos",
            ),
            WOLTarget(
                alias="homelab",
                name="Homelab Cluster Node",
                mac_address="00:11:22:33:44:77",
                port=9,
                description="Nodo de virtualización y microservicios locales",
            ),
            WOLTarget(
                alias="server",
                name="Primary Home Server",
                mac_address="00:11:22:33:44:88",
                port=9,
                description="Servidor dedicado de infraestructura y bases de datos",
            ),
        ]
        for t in defaults:
            self.register_target(t)

    def normalize_mac(self, mac_raw: str) -> str:
        """
        Normaliza separadores (':', '-', '.', '') y valida que la dirección MAC:
          1. Posea exactamente 12 dígitos hexadecimales.
          2. No sea nula (00:00:00:00:00:00).
          3. No sea de difusión (FF:FF:FF:FF:FF:FF).
          4. No sea multicast (bit menos significativo del primer octeto en 1).
        Retorna la dirección en formato estándar 'AA:BB:CC:DD:EE:FF'.
        """
        if not mac_raw or not isinstance(mac_raw, str):
            raise WOLError("Dirección MAC vacía o tipo inválido.")

        clean = re.sub(r"[:\-\.\s]", "", mac_raw.strip()).upper()

        if len(clean) != 12:
            raise WOLError(
                f"Longitud de dirección MAC inválida: se esperan 12 dígitos hexadecimales, se obtuvieron {len(clean)}."
            )

        if not re.fullmatch(r"[0-9A-F]{12}", clean):
            raise WOLError(f"La dirección MAC contiene caracteres hexadecimales no válidos: '{clean}'.")

        if clean == "000000000000":
            raise WOLError("La dirección MAC no puede ser nula (00:00:00:00:00:00).")

        if clean == "FFFFFFFFFFFF":
            raise WOLError("La dirección MAC no puede ser de difusión (FF:FF:FF:FF:FF:FF).")

        first_byte = int(clean[:2], 16)
        if first_byte & 0x01 != 0:
            raise WOLError(
                f"La dirección MAC {clean} es de tipo Multicast (primer byte 0x{first_byte:02X} tiene LSB=1), "
                "no admitida para tramas Wake-on-LAN dirigidas."
            )

        octets = [clean[i : i + 2] for i in range(0, 12, 2)]
        return ":".join(octets)

    def build_magic_packet(self, mac_address: str) -> bytes:
        """
        Construye la trama RFC Magic Packet:
          - Sincronización: 6 bytes 0xFF.
          - Carga útil: 16 repeticiones de la dirección MAC de destino (6 bytes cada una).
          - Total exacto: 6 + (16 * 6) = 102 bytes.
        """
        normalized = self.normalize_mac(mac_address)
        mac_bytes = bytes.fromhex(normalized.replace(":", ""))
        return b"\xff" * 6 + (mac_bytes * 16)

    def register_target(self, target: WOLTarget) -> None:
        """Registra o actualiza un perfil de nodo para transmisiones Wake-on-LAN."""
        with self._lock:
            self._targets[target.alias.strip().lower()] = target

    def get_target(self, query: str) -> WOLTarget | None:
        """Busca un objetivo registrado por alias o nombre exacto (case-insensitive)."""
        q = query.strip().lower()
        with self._lock:
            if q in self._targets:
                return self._targets[q]
            for t in self._targets.values():
                if t.name.lower() == q:
                    return t
        return None

    def list_targets(self) -> list[WOLTarget]:
        """Retorna la lista de todos los perfiles de destino registrados."""
        with self._lock:
            return list(self._targets.values())

    def get_broadcast_addresses(self) -> list[str]:
        """
        Calcula las direcciones de difusión IPv4 de todas las interfaces de red activas
        y no-loopback. Incluye '255.255.255.255' como destino global de respaldo.
        """
        broadcasts: set[str] = set()

        try:
            net_if_addrs = psutil.net_if_addrs()
            net_if_stats = psutil.net_if_stats()

            for iface_name, addrs in net_if_addrs.items():
                stats = net_if_stats.get(iface_name)
                if stats and not stats.isup:
                    continue

                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        ip_str = addr.address
                        if ip_str.startswith("127."):
                            continue

                        # Si psutil ya provee broadcast directamente
                        if addr.broadcast:
                            broadcasts.add(addr.broadcast)
                        elif addr.netmask:
                            with contextlib.suppress(Exception):
                                iface_net = ipaddress.IPv4Network(f"{ip_str}/{addr.netmask}", strict=False)
                                broadcasts.add(str(iface_net.broadcast_address))
        except Exception as e:
            log.warning(f"[WOL] Error enumerando interfaces de red con psutil: {e}")

        # Asegurar dirección de difusión global por defecto
        broadcasts.add("255.255.255.255")
        return sorted(broadcasts)

    def dispatch_wake(
        self,
        target_spec: str,
        broadcast_override: str | None = None,
        port_override: int | None = None,
        with_sfx: bool = True,
    ) -> tuple[bool, str]:
        """
        Construye y transmite el paquete mágico Wake-on-LAN sobre difusión UDP.
        Admite resolución por alias de perfil registrado o dirección MAC ad-hoc.
        """
        target = self.get_target(target_spec)
        normalized_mac: str

        if target is not None:
            try:
                normalized_mac = self.normalize_mac(target.mac_address)
            except WOLError as err:
                return False, f"Dirección MAC configurada en objetivo '{target.alias}' es inválida: {err}"
            target_name = target.name
            port = port_override if port_override is not None else target.port
            destinations = (
                [broadcast_override]
                if broadcast_override
                else ([target.broadcast_ip] if target.broadcast_ip else self.get_broadcast_addresses())
            )
        else:
            # Intentar interpretar target_spec directamente como una dirección MAC
            try:
                normalized_mac = self.normalize_mac(target_spec)
                target_name = f"Dispositivo ({normalized_mac})"
                port = port_override if port_override is not None else 9
                destinations = [broadcast_override] if broadcast_override else self.get_broadcast_addresses()
            except WOLError:
                return (
                    False,
                    f"Objetivo Wake-on-LAN '{target_spec}' no encontrado ni es una dirección MAC válida, señor.",
                )

        try:
            packet = self.build_magic_packet(normalized_mac)
        except WOLError as err:
            return False, f"Error generando Magic Packet: {err}"

        # Transmisión UDP broadcast
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                for dest in destinations:
                    sock.sendto(packet, (dest, port))
        except Exception as e:
            log.error(f"[WOL] Error transmitiendo trama UDP: {e}")
            return False, f"Error al despachar Wake-on-LAN: {e}"

        # Secuencia acústica procedural de Darius AI
        if with_sfx:
            try:
                sfx = get_sfx_engine()
                if sfx is not None:
                    sfx.play_target_lock()
                    sfx.play_success_chime()
            except Exception as e:
                log.debug(f"[WOL] Degradación pacífica de SFX: {e}")

        dest_count = len(destinations)
        return (
            True,
            f"Protocolo Wake-on-LAN transmitido para '{target_name}' ({normalized_mac}) "
            f"a través de {dest_count} interfaces de difusión (puerto {port}), señor.",
        )


# Singleton
_GLOBAL_WOL_DISPATCHER: DariusWOLDispatcher | None = None
_WOL_LOCK = threading.Lock()


def get_darius_wol_dispatcher() -> DariusWOLDispatcher:
    """Retorna la instancia global del despachador Wake-on-LAN de Darius AI."""
    global _GLOBAL_WOL_DISPATCHER
    if _GLOBAL_WOL_DISPATCHER is None:
        with _WOL_LOCK:
            if _GLOBAL_WOL_DISPATCHER is None:
                _GLOBAL_WOL_DISPATCHER = DariusWOLDispatcher()
    return _GLOBAL_WOL_DISPATCHER


# Aliases para compatibilidad hacia atrás
get_wol_dispatcher = get_darius_wol_dispatcher
get_stark_wol_dispatcher = get_darius_wol_dispatcher
StarkWOLDispatcher = DariusWOLDispatcher

wol_dispatcher: DariusWOLDispatcher = get_darius_wol_dispatcher()

__all__ = [
    "DariusWOLDispatcher",
    "StarkWOLDispatcher",
    "WOLError",
    "WOLTarget",
    "get_darius_wol_dispatcher",
    "get_stark_wol_dispatcher",
    "get_wol_dispatcher",
    "wol_dispatcher",
]
