"""
darius_timer.py — Motor de Temporizadores Tácticos Neuro-Timer para DARIUS AI
=============================================================================
Gestiona temporizadores de alta resolución en hilos en segundo plano,
con callbacks asíncronos al expirar, integración procedural SFX y
formateo de voz táctico con cadencia Darius AI.
"""

from __future__ import annotations

import inspect
import logging
import threading
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

try:
    from src.darius_ai.audio.sound_effects import get_sfx_engine
except ImportError:
    try:
        from darius_ai.audio.sound_effects import get_sfx_engine
    except ImportError:

        def get_sfx_engine():
            return None


log = logging.getLogger("DARIUS.TIMER")


@dataclass
class DariusTimer:
    """Representa un temporizador activo o histórico en el sistema Darius AI."""

    id: str
    label: str
    duration_seconds: float
    created_at: float
    expires_at: float
    status: str = "active"  # "active", "cancelled", "expired"


class DariusTimerManager:
    """
    Gestor multi-hilo de temporizadores de precisión para Darius AI.
    Arquitectura NeuroTimer de Temporizadores Tácticos Darius.
    """

    def __init__(self, tick_interval: float = 0.05) -> None:
        self._tick_interval = tick_interval
        self._timers: dict[str, DariusTimer] = {}
        self._callbacks: dict[str, Callable | None] = {}
        self._lock = threading.Lock()
        self._running = True
        self._thread: threading.Thread | None = None
        self._start_worker()

    def _start_worker(self) -> None:
        """Inicia el hilo demonio de cuenta regresiva si no está activo."""
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._running = True
                self._thread = threading.Thread(
                    target=self._worker_loop,
                    name="DariusTimerWorker",
                    daemon=True,
                )
                self._thread.start()

    def _worker_loop(self) -> None:
        """Bucle principal de verificación y disparo de temporizadores."""
        while self._running:
            expired_timers: list[tuple[DariusTimer, Callable | None]] = []
            now = time.time()

            with self._lock:
                for timer in self._timers.values():
                    if timer.status == "active" and now >= timer.expires_at:
                        timer.status = "expired"
                        cb = self._callbacks.get(timer.id)
                        expired_timers.append((timer, cb))

            # Ejecutar callbacks y efectos fuera del lock para evitar contención
            for timer, cb in expired_timers:
                self._handle_expiration(timer, cb)

            time.sleep(self._tick_interval)

    def _handle_expiration(self, timer: DariusTimer, callback: Callable | None) -> None:
        """Dispara los efectos de audio y el callback registrado."""
        # 1. Disparar SFX procedural
        self._trigger_sfx()

        # 2. Ejecutar callback si existe
        if callback is not None:
            try:
                sig = inspect.signature(callback)
                if len(sig.parameters) >= 1:
                    callback(timer)
                else:
                    callback()
            except Exception as exc:
                log.warning("[DariusTimer] Error al ejecutar callback del temporizador '%s': %s", timer.id, exc)

    def _trigger_sfx(self) -> None:
        """Dispara confirmación sonora procedural sin bloquear."""
        try:
            sfx = get_sfx_engine()
            if sfx is not None:
                if hasattr(sfx, "play_target_lock"):
                    sfx.play_target_lock()
                elif hasattr(sfx, "play_alert_tone"):
                    sfx.play_alert_tone()
        except Exception as exc:
            log.debug("[DariusTimer] SFX no disponible al expirar temporizador: %s", exc)

    @property
    def is_running(self) -> bool:
        """Indica si el gestor de temporizadores se encuentra en ejecución."""
        return self._running

    def create_timer(
        self,
        label: str,
        seconds: float,
        on_expire_callback: Callable | None = None,
    ) -> DariusTimer:
        """Crea y registra un nuevo temporizador de precisión."""
        now = time.time()
        timer_id = f"timer_{uuid.uuid4().hex[:8]}"
        timer = DariusTimer(
            id=timer_id,
            label=label,
            duration_seconds=float(seconds),
            created_at=now,
            expires_at=now + float(seconds),
            status="active",
        )

        with self._lock:
            self._timers[timer_id] = timer
            self._callbacks[timer_id] = on_expire_callback

        log.info("[DariusTimer] Temporizador '%s' (%s) programado para %.1f s", label, timer_id, seconds)
        return timer

    def cancel_timer(self, timer_id: str) -> bool:
        """Cancela un temporizador activo si existe."""
        with self._lock:
            timer = self._timers.get(timer_id)
            if timer is not None and timer.status == "active":
                timer.status = "cancelled"
                log.info("[DariusTimer] Temporizador '%s' cancelado.", timer_id)
                return True
        return False

    def get_timer(self, timer_id: str) -> DariusTimer | None:
        """Obtiene una copia referencial del temporizador."""
        with self._lock:
            return self._timers.get(timer_id)

    def list_active_timers(self) -> list[DariusTimer]:
        """Devuelve todos los temporizadores en estado 'active'."""
        with self._lock:
            return [t for t in self._timers.values() if t.status == "active"]

    def get_remaining_seconds(self, timer_id: str) -> float:
        """Calcula los segundos restantes para un temporizador."""
        with self._lock:
            timer = self._timers.get(timer_id)
            if timer is None or timer.status != "active":
                return 0.0
            remaining = timer.expires_at - time.time()
            return max(0.0, remaining)

    def format_timer_speech(self, timer: DariusTimer, expired: bool = False) -> str:
        """
        Formatea el mensaje auditivo en la cadencia táctica de Darius AI.
        Ejemplos:
          - Expirado: "Señor, el temporizador de café ha concluido."
          - Activo: "Quedan 2 minutos y 30 segundos para café, señor."
          - Corto: "Quedan 45 segundos para microondas, señor."
        """
        if expired:
            return f"Señor, el temporizador de {timer.label} ha concluido."

        rem = self.get_remaining_seconds(timer.id)
        if rem <= 0.0:
            rem = max(0.0, timer.expires_at - time.time())

        total_secs = int(round(rem))
        m = total_secs // 60
        s = total_secs % 60

        if m > 0:
            m_str = "1 minuto" if m == 1 else f"{m} minutos"
            s_str = "1 segundo" if s == 1 else f"{s} segundos"
            return f"Quedan {m_str} y {s_str} para {timer.label}, señor."

        s_str = "1 segundo" if s == 1 else f"{s} segundos"
        return f"Quedan {s_str} para {timer.label}, señor."

    def stop_all(self) -> None:
        """Detiene el hilo en segundo plano y finaliza el gestor."""
        self._running = False
        with self._lock:
            for timer in self._timers.values():
                if timer.status == "active":
                    timer.status = "cancelled"

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)


_GLOBAL_TIMER_MANAGER: DariusTimerManager | None = None
_GLOBAL_TIMER_MANAGER_LOCK = threading.Lock()


def get_darius_timer_manager() -> DariusTimerManager:
    """Retorna la instancia global única del gestor de temporizadores tácticos Darius."""
    global _GLOBAL_TIMER_MANAGER
    if _GLOBAL_TIMER_MANAGER is None:
        with _GLOBAL_TIMER_MANAGER_LOCK:
            if _GLOBAL_TIMER_MANAGER is None:
                _GLOBAL_TIMER_MANAGER = DariusTimerManager()
    return _GLOBAL_TIMER_MANAGER


# Aliases para compatibilidad hacia atrás
get_stark_timer_manager = get_darius_timer_manager
StarkTimer = DariusTimer
StarkTimerManager = DariusTimerManager

__all__ = [
    "DariusTimer",
    "DariusTimerManager",
    "StarkTimer",
    "StarkTimerManager",
    "get_darius_timer_manager",
    "get_stark_timer_manager",
]
