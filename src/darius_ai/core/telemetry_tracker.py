"""
telemetry_tracker.py — Rastreador de Telemetría y Observabilidad Agéntica para DARIUS AI
========================================================================================
Permite monitorizar, medir latencias y emitir eventos en tiempo real sobre la ejecución
de agentes, herramientas de automatización y llamadas de red.
Inspirado en la observabilidad Laminar y la barra de estado de JARVIS (StatusBar.tsx).
"""

from __future__ import annotations

import datetime
import functools
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("DARIUS.Telemetry")


@dataclass
class AgentEvent:
    """Evento individual de telemetría de un agente."""

    agent_name: str
    message: str
    status: str = "running"  # running | success | warning | error
    duration_ms: float = 0.0
    time_str: str = field(
        default_factory=lambda: datetime.datetime.now().strftime("%H:%M:%S")
    )


class TelemetryTracker:
    """
    Gestor central de telemetría y eventos de agentes para Darius AI.
    """

    def __init__(self, max_history: int = 50):
        self._max_history = max_history
        self._events: list[AgentEvent] = []
        self._listeners: list[Callable[[AgentEvent], Any]] = []
        self._lock = threading.Lock()

    def add_listener(self, listener: Callable[[AgentEvent], Any]) -> None:
        """Agrega un suscriptor para recibir eventos en tiempo real."""
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[AgentEvent], Any]) -> None:
        """Elimina un suscriptor."""
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def push_event(
        self,
        agent_name: str,
        message: str,
        status: str = "running",
        duration_ms: float = 0.0,
    ) -> AgentEvent:
        """Registra un nuevo evento y lo emite a los observadores registrados."""
        evt = AgentEvent(
            agent_name=agent_name,
            message=message,
            status=status,
            duration_ms=duration_ms,
        )

        with self._lock:
            self._events.append(evt)
            if len(self._events) > self._max_history:
                self._events.pop(0)
            active_listeners = list(self._listeners)

        for listener in active_listeners:
            try:
                listener(evt)
            except Exception as e:
                log.debug(f"[Telemetry] Error notificando listener: {e}")

        return evt

    def get_recent_events(self, limit: int | None = None) -> list[AgentEvent]:
        """Retorna una copia de los eventos recientes."""
        with self._lock:
            if limit is not None:
                return list(self._events[-limit:])
            return list(self._events)

    def clear(self) -> None:
        """Limpia el historial de eventos."""
        with self._lock:
            self._events.clear()


_GLOBAL_TRACKER: TelemetryTracker | None = None
_GLOBAL_TRACKER_LOCK = threading.Lock()


def get_telemetry_tracker() -> TelemetryTracker:
    """Retorna la instancia global del rastreador de telemetría."""
    global _GLOBAL_TRACKER
    if _GLOBAL_TRACKER is None:
        with _GLOBAL_TRACKER_LOCK:
            if _GLOBAL_TRACKER is None:
                _GLOBAL_TRACKER = TelemetryTracker()
    return _GLOBAL_TRACKER


def trace_step(
    agent_name: str,
    step_label: str,
    tracker: TelemetryTracker | None = None,
):
    """
    Decorador para medir y registrar automáticamente la ejecución de un paso agéntico.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            t = tracker or get_telemetry_tracker()
            t.push_event(agent_name, f"Iniciando: {step_label}", status="running")
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                t.push_event(
                    agent_name,
                    f"Completado: {step_label}",
                    status="success",
                    duration_ms=round(elapsed_ms, 2),
                )
                return result
            except Exception as e:
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                t.push_event(
                    agent_name,
                    f"Error en {step_label}: {e}",
                    status="error",
                    duration_ms=round(elapsed_ms, 2),
                )
                raise

        return wrapper

    return decorator
