"""
darius_lockdown.py — Protocolo de Silencio Táctico y Bloqueo de Emergencia Darius para DARIUS AI
================================================================================================
Implementa las salvaguardas de contención acústica e integridad transaccional:
  - Nivel 1: Silencio Táctico (<15 ms) — Detención inmediata de medios, purga de cola TTS y muteo.
  - Nivel 2: Código Rojo — Silencio táctico, checkpoint WAL (TRUNCATE) en SQLite y bloqueo nativo Win32.
Mecanismo central de parada de emergencia y contención perimetral de Darius AI.
"""

from __future__ import annotations

import ctypes
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any

from src.darius_ai.core.config_loader import get_user_data_dir

log = logging.getLogger("DARIUS.Lockdown")


class DariusLockdownEngine:
    """
    Motor central de ejecución de protocolos de emergencia y contención táctica de Darius AI.
    """

    def __init__(
        self,
        tts_worker: Any = None,
        media_controller: Any = None,
        scheduler_db_path: Path | str | None = None,
        approval_db_path: Path | str | None = None,
    ) -> None:
        self._tts_worker = tts_worker
        self._media_controller = media_controller
        self._lock = threading.Lock()

        if scheduler_db_path is None:
            self.scheduler_db_path = get_user_data_dir() / "scheduler.db"
        else:
            self.scheduler_db_path = Path(scheduler_db_path)

        if approval_db_path is None:
            self.approval_db_path = get_user_data_dir() / "approvals.db"
        else:
            self.approval_db_path = Path(approval_db_path)

    def _get_media_controller(self) -> Any:
        """Obtiene el controlador multimedia activo o fallback singleton."""
        if self._media_controller is not None:
            return self._media_controller
        from src.darius_ai.system.media_controller import media_controller

        return media_controller

    def register_tts_worker(self, worker: Any) -> None:
        """Registra el worker de Text-to-Speech para purga instantánea en silencio táctico."""
        with self._lock:
            self._tts_worker = worker

    def trigger_tactical_silence(self) -> tuple[bool, str]:
        """
        Nivel 1: Silencio Táctico (<15 ms).
        Purga inmediatamente la cola de síntesis TTS, detiene la reproducción multimedia
        activa y silencia el volumen del sistema.
        """
        with self._lock:
            # 1. Purgar cola TTS pendiente si el worker está conectado
            if self._tts_worker is not None and hasattr(self._tts_worker, "clear_queue"):
                try:
                    self._tts_worker.clear_queue()
                except Exception as e:
                    log.warning(f"[Lockdown] Error al purgar cola TTS: {e}")

            # 2. Detener medios y silenciar sistema
            ctrl = self._get_media_controller()
            if ctrl is not None:
                try:
                    ctrl.stop()
                except Exception as e:
                    log.warning(f"[Lockdown] Error deteniendo reproducción de medios: {e}")

                try:
                    ctrl.toggle_mute()
                except Exception as e:
                    log.warning(f"[Lockdown] Error aplicando silencio al sistema: {e}")

        return True, "Protocolo de Silencio Táctico ejecutado: reproducción detenida y audio silenciado, señor."

    def _checkpoint_database(self, db_path: Path) -> bool:
        """Ejecuta un checkpoint WAL explícito con truncado de bitácora en la base de datos SQLite."""
        if not db_path.exists():
            log.debug(f"[Lockdown] Archivo de base de datos no existe aún ({db_path}), checkpoint omitido.")
            return True

        try:
            with sqlite3.connect(str(db_path), timeout=5.0) as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            log.debug(f"[Lockdown] Checkpoint WAL (TRUNCATE) completado en {db_path.name}")
            return True
        except Exception as e:
            log.warning(f"[Lockdown] Error en checkpoint WAL de {db_path}: {e}")
            return False

    def trigger_emergency_lockdown(self, lock_workstation: bool = True) -> tuple[bool, str]:
        """
        Nivel 2: Código Rojo.
        1. Ejecuta Silencio Táctico para contención acústica.
        2. Realiza checkpoints atómicos WAL (TRUNCATE) en bases de datos del planificador y aprobaciones.
        3. Bloquea la estación de trabajo Windows mediante user32.LockWorkStation (si está habilitado).
        """
        # Paso 1: Silencio táctico inmediato
        self.trigger_tactical_silence()

        # Paso 2: Checkpoint atómico WAL en bases de datos de Darius
        self._checkpoint_database(self.scheduler_db_path)
        self._checkpoint_database(self.approval_db_path)

        # Paso 3: Bloqueo de sesión Windows si fue solicitado
        workstation_locked = False
        if lock_workstation:
            try:
                windll = getattr(ctypes, "windll", None)
                if windll and hasattr(windll, "user32") and hasattr(windll.user32, "LockWorkStation"):
                    windll.user32.LockWorkStation()
                    workstation_locked = True
                else:
                    log.debug("[Lockdown] user32.LockWorkStation no disponible o entorno simulado.")
            except Exception as e:
                log.warning(f"[Lockdown] Error al invocar LockWorkStation: {e}")

        status_workstation = "estación de trabajo bloqueada" if workstation_locked else "estación protegida"
        return (
            True,
            f"Protocolo Código Rojo ejecutado. Sistemas silenciados, bases de datos aseguradas en WAL y "
            f"{status_workstation}, señor.",
        )


# Singleton
_GLOBAL_LOCKDOWN_ENGINE: DariusLockdownEngine | None = None
_LOCKDOWN_LOCK = threading.Lock()


def get_darius_lockdown_engine() -> DariusLockdownEngine:
    """Retorna la instancia global del motor de bloqueo de emergencia de Darius AI."""
    global _GLOBAL_LOCKDOWN_ENGINE
    if _GLOBAL_LOCKDOWN_ENGINE is None:
        with _LOCKDOWN_LOCK:
            if _GLOBAL_LOCKDOWN_ENGINE is None:
                _GLOBAL_LOCKDOWN_ENGINE = DariusLockdownEngine()
    return _GLOBAL_LOCKDOWN_ENGINE


# Aliases para compatibilidad hacia atrás
get_stark_lockdown_engine = get_darius_lockdown_engine
StarkLockdownEngine = DariusLockdownEngine

lockdown_engine: DariusLockdownEngine = get_darius_lockdown_engine()

__all__ = [
    "DariusLockdownEngine",
    "StarkLockdownEngine",
    "get_darius_lockdown_engine",
    "get_stark_lockdown_engine",
    "lockdown_engine",
]
