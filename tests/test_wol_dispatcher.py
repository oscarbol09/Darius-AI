"""
test_wol_dispatcher.py — Pruebas unitarias para Darius Wake-on-LAN (WOL) Dispatcher
====================================================================================
Valida la normalización de direcciones MAC, rechazo de multicast/broadcast/nulas,
generación del Magic Packet RFC (102 bytes), cálculo de direcciones de broadcast múltiple,
gestión de perfiles/alias y despacho UDP táctico con efectos de sonido de Darius AI.
"""

from __future__ import annotations

import socket
from collections import namedtuple
from unittest.mock import MagicMock, patch

import pytest

from src.darius_ai.system.wol_dispatcher import (
    DariusWOLDispatcher,
    StarkWOLDispatcher,
    WOLError,
    WOLTarget,
    get_darius_wol_dispatcher,
    get_stark_wol_dispatcher,
    get_wol_dispatcher,
)


class TestMACNormalization:
    """Pruebas de validación y normalización estricta de direcciones MAC."""

    @pytest.fixture
    def dispatcher(self) -> DariusWOLDispatcher:
        return DariusWOLDispatcher()

    @pytest.mark.parametrize(
        ("raw_mac", "expected"),
        [
            ("00:11:22:33:44:55", "00:11:22:33:44:55"),
            ("00-11-22-33-44-55", "00:11:22:33:44:55"),
            ("0011.2233.4455", "00:11:22:33:44:55"),
            ("001122334455", "00:11:22:33:44:55"),
            ("aa:bb:cc:dd:ee:fa", "AA:BB:CC:DD:EE:FA"),
            ("AA-BB-CC-DD-EE-FA", "AA:BB:CC:DD:EE:FA"),
            ("aabb.ccdd.eefa", "AA:BB:CC:DD:EE:FA"),
            ("2c:f0:5d:12:34:56", "2C:F0:5D:12:34:56"),
        ],
    )
    def test_normalize_valid_mac_formats(self, dispatcher: DariusWOLDispatcher, raw_mac: str, expected: str):
        assert dispatcher.normalize_mac(raw_mac) == expected

    @pytest.mark.parametrize(
        "invalid_mac",
        [
            "",
            "00:11:22:33:44",  # Incompleta (5 octetos)
            "00:11:22:33:44:55:66",  # Excedida (7 octetos)
            "00:11:22:33:44:ZZ",  # Caracteres no hexadecimales
            "not-a-mac-address",
            "00112233445",  # 11 dígitos
            "00112233445566",  # 14 dígitos
        ],
    )
    def test_reject_malformed_mac(self, dispatcher: DariusWOLDispatcher, invalid_mac: str):
        with pytest.raises(WOLError, match=r"(?i)longitud|hexadecimal|malformada|vac|inv"):
            dispatcher.normalize_mac(invalid_mac)

    def test_reject_null_mac(self, dispatcher: DariusWOLDispatcher):
        """Rechaza dirección MAC nula (00:00:00:00:00:00)."""
        with pytest.raises(WOLError, match=r"(?i)nula|reservada"):
            dispatcher.normalize_mac("00:00:00:00:00:00")
        with pytest.raises(WOLError, match=r"(?i)nula|reservada"):
            dispatcher.normalize_mac("000000000000")

    def test_reject_broadcast_mac(self, dispatcher: DariusWOLDispatcher):
        """Rechaza dirección MAC de difusión (FF:FF:FF:FF:FF:FF)."""
        with pytest.raises(WOLError, match=r"(?i)difusi|broadcast|multicast"):
            dispatcher.normalize_mac("FF:FF:FF:FF:FF:FF")

    @pytest.mark.parametrize(
        "multicast_mac",
        [
            "01:00:5E:00:00:01",  # IPv4 multicast
            "33:33:00:00:00:01",  # IPv6 multicast
            "03:12:34:56:78:9A",  # Primer octeto impar (LSB = 1)
            "01-80-C2-00-00-00",  # Spanning Tree multicast
            "05:00:00:00:00:00",  # LSB = 1
        ],
    )
    def test_reject_multicast_mac(self, dispatcher: DariusWOLDispatcher, multicast_mac: str):
        """Rechaza direcciones MAC multicast (bit menos significativo del primer octeto en 1)."""
        with pytest.raises(WOLError, match=r"(?i)multicast|difusi"):
            dispatcher.normalize_mac(multicast_mac)


class TestMagicPacketGeneration:
    """Pruebas del formato binario RFC del Magic Packet de Wake-on-LAN."""

    @pytest.fixture
    def dispatcher(self) -> DariusWOLDispatcher:
        return DariusWOLDispatcher()

    def test_magic_packet_structure_and_length(self, dispatcher: DariusWOLDispatcher):
        target_mac = "2C:F0:5D:89:AB:CD"
        packet = dispatcher.build_magic_packet(target_mac)

        # Longitud estándar RFC: 102 bytes
        assert len(packet) == 102

        # Encabezado de sincronización: 6 bytes 0xFF
        assert packet[:6] == b"\xff" * 6

        # Carga útil: 16 repeticiones consecutivas de la MAC en binario
        raw_mac_bytes = bytes.fromhex(target_mac.replace(":", ""))
        assert len(raw_mac_bytes) == 6

        for i in range(16):
            start = 6 + (i * 6)
            end = start + 6
            assert packet[start:end] == raw_mac_bytes

    def test_magic_packet_rejects_invalid_mac(self, dispatcher: DariusWOLDispatcher):
        with pytest.raises(WOLError):
            dispatcher.build_magic_packet("00:00:00:00:00:00")


class TestBroadcastDiscovery:
    """Pruebas de cálculo de difusión multi-interfaz y fallback global."""

    @pytest.fixture
    def dispatcher(self) -> DariusWOLDispatcher:
        return DariusWOLDispatcher()

    def test_broadcast_includes_global_fallback(self, dispatcher: DariusWOLDispatcher):
        addrs = dispatcher.get_broadcast_addresses()
        assert "255.255.255.255" in addrs
        assert len(addrs) >= 1

    def test_broadcast_calculation_from_mock_interfaces(self, dispatcher: DariusWOLDispatcher):
        snic = namedtuple("snicaddr", ["family", "address", "netmask", "broadcast", "ptp"])
        sstats = namedtuple("snetinfo", ["isup", "duplex", "speed", "mtu"])

        mock_ifaces = {
            "Ethernet 1": [
                snic(
                    family=socket.AF_INET,
                    address="192.168.1.50",
                    netmask="255.255.255.0",
                    broadcast="192.168.1.255",
                    ptp=None,
                ),
            ],
            "Loopback": [
                snic(family=socket.AF_INET, address="127.0.0.1", netmask="255.0.0.0", broadcast=None, ptp=None),
            ],
        }
        mock_stats = {
            "Ethernet 1": sstats(isup=True, duplex=0, speed=1000, mtu=1500),
            "Loopback": sstats(isup=True, duplex=0, speed=0, mtu=65536),
        }

        with patch("src.darius_ai.system.wol_dispatcher.psutil.net_if_addrs", return_value=mock_ifaces), \
             patch("src.darius_ai.system.wol_dispatcher.psutil.net_if_stats", return_value=mock_stats):
            addrs = dispatcher.get_broadcast_addresses()

            assert "192.168.1.255" in addrs
            assert "255.255.255.255" in addrs
            # Loopback debe ser ignorado
            assert "127.255.255.255" not in addrs


class TestTargetManagement:
    """Pruebas de registro, consulta y perfiles tácticos."""

    @pytest.fixture
    def dispatcher(self) -> DariusWOLDispatcher:
        return DariusWOLDispatcher()

    def test_default_profiles_registered(self, dispatcher: DariusWOLDispatcher):
        profiles = ["gaming_rig", "nas", "homelab", "server"]
        for profile in profiles:
            target = dispatcher.get_target(profile)
            assert target is not None
            assert target.alias == profile
            assert target.mac_address != ""
            assert target.port == 9

    def test_register_and_retrieve_custom_target(self, dispatcher: DariusWOLDispatcher):
        custom = WOLTarget(
            alias="gpu_cluster",
            name="Darius AI GPU Cluster",
            mac_address="00:1A:2B:3C:4D:5E",
            broadcast_ip="192.168.10.255",
            port=9,
            description="Cluster de entrenamiento local",
        )
        dispatcher.register_target(custom)

        # Recuperar por alias exacto e insensible a mayúsculas
        assert dispatcher.get_target("gpu_cluster") == custom
        assert dispatcher.get_target("GPU_CLUSTER") == custom
        # Recuperar por nombre
        assert dispatcher.get_target("Darius AI GPU Cluster") == custom

    def test_get_target_unknown_returns_none(self, dispatcher: DariusWOLDispatcher):
        assert dispatcher.get_target("unregistered_host") is None


class TestDispatchWake:
    """Pruebas del despacho de Wake-on-LAN vía UDP y efectos acústicos."""

    @pytest.fixture
    def dispatcher(self) -> DariusWOLDispatcher:
        return DariusWOLDispatcher()

    @patch("src.darius_ai.system.wol_dispatcher.get_sfx_engine")
    @patch("src.darius_ai.system.wol_dispatcher.socket.socket")
    def test_dispatch_wake_by_alias_success(self, mock_socket_cls, mock_get_sfx, dispatcher: DariusWOLDispatcher):
        mock_sock = MagicMock()
        mock_socket_cls.return_value.__enter__.return_value = mock_sock
        mock_sfx = MagicMock()
        mock_get_sfx.return_value = mock_sfx

        success, msg = dispatcher.dispatch_wake("gaming_rig", with_sfx=True)

        assert success is True
        assert "Protocolo Wake-on-LAN transmitido" in msg
        assert "Gaming Rig" in msg

        # Verificar opciones de socket UDP broadcast
        mock_sock.setsockopt.assert_called_with(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        assert mock_sock.sendto.call_count >= 1

        # Verificar efectos de sonido procedurales de Darius AI
        mock_sfx.play_target_lock.assert_called_once()
        mock_sfx.play_success_chime.assert_called_once()

    @patch("src.darius_ai.system.wol_dispatcher.get_sfx_engine")
    @patch("src.darius_ai.system.wol_dispatcher.socket.socket")
    def test_dispatch_wake_adhoc_valid_mac(self, mock_socket_cls, mock_get_sfx, dispatcher: DariusWOLDispatcher):
        mock_sock = MagicMock()
        mock_socket_cls.return_value.__enter__.return_value = mock_sock

        success, msg = dispatcher.dispatch_wake("00:11:22:33:44:55", with_sfx=False)

        assert success is True
        assert "Protocolo Wake-on-LAN transmitido" in msg
        assert "00:11:22:33:44:55" in msg
        mock_get_sfx.return_value.play_target_lock.assert_not_called()

    @patch("src.darius_ai.system.wol_dispatcher.socket.socket")
    def test_dispatch_wake_with_port_override(self, mock_socket_cls, dispatcher: DariusWOLDispatcher):
        mock_sock = MagicMock()
        mock_socket_cls.return_value.__enter__.return_value = mock_sock

        dispatcher.dispatch_wake("nas", port_override=7, with_sfx=False)

        # Verificar que el puerto enviado sea el override (7)
        for call_args in mock_sock.sendto.call_args_list:
            _packet, addr = call_args[0]
            assert addr[1] == 7

    def test_dispatch_wake_unknown_target_fails(self, dispatcher: DariusWOLDispatcher):
        success, msg = dispatcher.dispatch_wake("non_existent_machine", with_sfx=False)
        assert success is False
        assert "no encontrado" in msg.lower() or "inválid" in msg.lower()

    @patch("src.darius_ai.system.wol_dispatcher.socket.socket")
    def test_dispatch_wake_network_error_handled(self, mock_socket_cls, dispatcher: DariusWOLDispatcher):
        mock_sock = MagicMock()
        mock_sock.sendto.side_effect = OSError("Network is unreachable")
        mock_socket_cls.return_value.__enter__.return_value = mock_sock

        success, msg = dispatcher.dispatch_wake("server", with_sfx=False)
        assert success is False
        assert "Error al despachar Wake-on-LAN" in msg

    def test_dispatch_wake_target_with_invalid_mac_configured(self, dispatcher: DariusWOLDispatcher):
        bad_target = WOLTarget(
            alias="bad_device",
            name="Bad Device",
            mac_address="not-valid-mac",
        )
        dispatcher.register_target(bad_target)
        success, msg = dispatcher.dispatch_wake("bad_device", with_sfx=False)
        assert success is False
        assert "inválida" in msg.lower() or "invalida" in msg.lower()

    @patch("src.darius_ai.system.wol_dispatcher.socket.socket")
    @patch("src.darius_ai.system.wol_dispatcher.get_sfx_engine")
    def test_dispatch_wake_sfx_exception_handled_gracefully(
        self, mock_get_sfx, mock_socket_cls, dispatcher: DariusWOLDispatcher
    ):
        mock_sock = MagicMock()
        mock_socket_cls.return_value.__enter__.return_value = mock_sock
        mock_sfx = MagicMock()
        mock_sfx.play_target_lock.side_effect = RuntimeError("Audio device busy")
        mock_get_sfx.return_value = mock_sfx

        success, msg = dispatcher.dispatch_wake("gaming_rig", with_sfx=True)
        assert success is True
        assert "Protocolo Wake-on-LAN transmitido" in msg


def test_singleton_and_aliases():
    disp1 = get_darius_wol_dispatcher()
    disp2 = get_wol_dispatcher()
    disp3 = get_stark_wol_dispatcher()
    assert disp1 is disp2
    assert disp1 is disp3
    assert StarkWOLDispatcher is DariusWOLDispatcher
