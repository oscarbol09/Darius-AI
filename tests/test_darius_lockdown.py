"""
test_darius_lockdown.py — Pruebas unitarias para Darius Emergency Lockdown Engine
=================================================================================
Valida el Protocolo de Silencio Táctico (<15 ms), parada de medios, purga de cola TTS,
checkpoints atómicos WAL (TRUNCATE) en SQLite y bloqueo nativo Win32 LockWorkStation.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.darius_ai.core.darius_lockdown import (
    DariusLockdownEngine,
    StarkLockdownEngine,
    get_darius_lockdown_engine,
    get_stark_lockdown_engine,
)


class TestTacticalSilence:
    """Pruebas del Nivel 1: Silencio Táctico de ultra-baja latencia."""

    @pytest.fixture
    def mock_media_ctrl(self):
        ctrl = MagicMock()
        ctrl.stop.return_value = (True, "Detenido")
        ctrl.toggle_mute.return_value = (True, "Silenciado")
        return ctrl

    @pytest.fixture
    def mock_tts_worker(self):
        worker = MagicMock()
        return worker

    def test_tactical_silence_latency_and_actions(self, mock_media_ctrl, mock_tts_worker):
        engine = DariusLockdownEngine(tts_worker=mock_tts_worker, media_controller=mock_media_ctrl)

        start = time.perf_counter()
        success, msg = engine.trigger_tactical_silence()
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Debe responder en <15 ms para contención acústica inmediata
        assert elapsed_ms < 15.0, f"Latencia excedida: {elapsed_ms:.2f} ms"
        assert success is True
        assert "Silencio Táctico" in msg

        # Verificaciones operacionales
        mock_tts_worker.clear_queue.assert_called_once()
        mock_media_ctrl.stop.assert_called_once()
        mock_media_ctrl.toggle_mute.assert_called_once()

    def test_tactical_silence_without_tts_worker(self, mock_media_ctrl):
        engine = DariusLockdownEngine(tts_worker=None, media_controller=mock_media_ctrl)
        success, msg = engine.trigger_tactical_silence()

        assert success is True
        assert "Silencio Táctico" in msg
        mock_media_ctrl.stop.assert_called_once()


class TestEmergencyLockdownWALCheckpoints:
    """Pruebas de integridad ACID y checkpoints SQLite WAL (TRUNCATE) en modo Código Rojo."""

    @pytest.fixture
    def temp_dbs(self, tmp_path: Path):
        scheduler_db = tmp_path / "scheduler.db"
        approvals_db = tmp_path / "approvals.db"

        # Inicializar ambas bases de datos con modo WAL
        for db in (scheduler_db, approvals_db):
            with sqlite3.connect(str(db)) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("CREATE TABLE test_data (id INTEGER PRIMARY KEY, info TEXT)")
                conn.execute("INSERT INTO test_data (info) VALUES ('darius_telemetry')")
                conn.commit()

        return scheduler_db, approvals_db

    def test_wal_checkpoints_truncate(self, temp_dbs):
        scheduler_db, approvals_db = temp_dbs

        engine = DariusLockdownEngine(
            scheduler_db_path=scheduler_db,
            approval_db_path=approvals_db,
            media_controller=MagicMock(),
        )

        with patch("src.darius_ai.core.darius_lockdown.ctypes") as mock_ctypes:
            mock_ctypes.windll.user32.LockWorkStation.return_value = 1
            success, msg = engine.trigger_emergency_lockdown(lock_workstation=False)

        assert success is True
        assert "Protocolo Código Rojo ejecutado" in msg

        # Verificar que las bases de datos siguen siendo legibles y consistentes
        for db in (scheduler_db, approvals_db):
            with sqlite3.connect(str(db)) as conn:
                res = conn.execute("SELECT info FROM test_data").fetchone()
                assert res[0] == "darius_telemetry"

    def test_wal_checkpoints_graceful_missing_files(self, tmp_path: Path):
        non_existent_sched = tmp_path / "ghost_sched.db"
        non_existent_appr = tmp_path / "ghost_appr.db"

        engine = DariusLockdownEngine(
            scheduler_db_path=non_existent_sched,
            approval_db_path=non_existent_appr,
            media_controller=MagicMock(),
        )

        success, msg = engine.trigger_emergency_lockdown(lock_workstation=False)
        assert success is True
        assert "Protocolo Código Rojo ejecutado" in msg


class TestEmergencyLockdownWorkstationLock:
    """Pruebas del bloqueo nativo de estación Windows (user32.LockWorkStation)."""

    @pytest.fixture
    def engine(self, tmp_path: Path):
        return DariusLockdownEngine(
            scheduler_db_path=tmp_path / "s.db",
            approval_db_path=tmp_path / "a.db",
            media_controller=MagicMock(),
        )

    def test_lock_workstation_enabled(self, engine: DariusLockdownEngine):
        with patch("src.darius_ai.core.darius_lockdown.ctypes") as mock_ctypes:
            mock_user32 = MagicMock()
            mock_ctypes.windll.user32 = mock_user32

            success, msg = engine.trigger_emergency_lockdown(lock_workstation=True)

            assert success is True
            assert "Protocolo Código Rojo ejecutado" in msg
            mock_user32.LockWorkStation.assert_called_once()

    def test_lock_workstation_disabled(self, engine: DariusLockdownEngine):
        with patch("src.darius_ai.core.darius_lockdown.ctypes") as mock_ctypes:
            mock_user32 = MagicMock()
            mock_ctypes.windll.user32 = mock_user32

            success, _msg = engine.trigger_emergency_lockdown(lock_workstation=False)

            assert success is True
            mock_user32.LockWorkStation.assert_not_called()

    def test_lock_workstation_non_windows_fallback(self, engine: DariusLockdownEngine):
        with patch("src.darius_ai.core.darius_lockdown.ctypes") as mock_ctypes:
            # Simular ctypes sin atributo windll (entorno Linux/macOS o CI)
            del mock_ctypes.windll

            success, msg = engine.trigger_emergency_lockdown(lock_workstation=True)
            assert success is True
            assert "Protocolo Código Rojo ejecutado" in msg

    def test_lock_workstation_exception_handled(self, engine: DariusLockdownEngine):
        with patch("src.darius_ai.core.darius_lockdown.ctypes") as mock_ctypes:
            mock_user32 = MagicMock()
            mock_user32.LockWorkStation.side_effect = OSError("Win32 error")
            mock_ctypes.windll.user32 = mock_user32

            success, msg = engine.trigger_emergency_lockdown(lock_workstation=True)
            assert success is True
            assert "Protocolo Código Rojo ejecutado" in msg


class TestLockdownResilienceAndRegistration:
    """Pruebas de tolerancia a fallos y registro de componentes."""

    def test_default_media_controller_fallback(self):
        engine = DariusLockdownEngine()
        ctrl = engine._get_media_controller()
        assert ctrl is not None

    def test_register_tts_worker_dynamically(self):
        engine = DariusLockdownEngine(media_controller=MagicMock())
        worker = MagicMock()
        engine.register_tts_worker(worker)
        engine.trigger_tactical_silence()
        worker.clear_queue.assert_called_once()

    def test_tactical_silence_errors_suppressed(self):
        faulty_worker = MagicMock()
        faulty_worker.clear_queue.side_effect = RuntimeError("Worker hung")

        faulty_media = MagicMock()
        faulty_media.stop.side_effect = RuntimeError("Media error")
        faulty_media.toggle_mute.side_effect = RuntimeError("Audio endpoint error")

        engine = DariusLockdownEngine(tts_worker=faulty_worker, media_controller=faulty_media)
        success, msg = engine.trigger_tactical_silence()
        assert success is True
        assert "Silencio Táctico" in msg

    def test_checkpoint_database_corrupt_file_handled(self, tmp_path: Path):
        corrupt_db = tmp_path / "corrupt.db"
        corrupt_db.write_bytes(b"NOT A SQLITE FILE HEADER")

        engine = DariusLockdownEngine(
            scheduler_db_path=corrupt_db,
            approval_db_path=tmp_path / "empty.db",
            media_controller=MagicMock(),
        )
        # Debe manejar el error de SQLite pacíficamente
        assert engine._checkpoint_database(corrupt_db) is False


def test_singleton_get_darius_lockdown_engine():
    e1 = get_darius_lockdown_engine()
    e2 = get_darius_lockdown_engine()
    assert e1 is e2


def test_backward_compatibility_aliases():
    assert StarkLockdownEngine is DariusLockdownEngine
    assert get_stark_lockdown_engine is get_darius_lockdown_engine
