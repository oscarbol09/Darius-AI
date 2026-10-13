"""
tests/test_darius_timer.py — Pruebas unitarias para DariusTimer y DariusTimerManager
===================================================================================
Valida la creación, cuenta regresiva de alta resolución, cancelación,
callbacks al expirar, integración SFX procedural y formateo de voz táctico de Darius AI.
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

try:
    from src.darius_ai.core.darius_timer import (
        DariusTimer,
        DariusTimerManager,
        StarkTimer,
        StarkTimerManager,
        get_darius_timer_manager,
        get_stark_timer_manager,
    )
except ImportError:
    from darius_ai.core.darius_timer import (
        DariusTimer,
        DariusTimerManager,
        StarkTimer,
        StarkTimerManager,
        get_darius_timer_manager,
        get_stark_timer_manager,
    )


@pytest.fixture(autouse=True)
def _mock_sounddevice_playback():
    with patch("src.darius_ai.audio.sound_effects.sounddevice.play", create=True):
        yield


def test_darius_timer_dataclass_defaults():
    now = time.time()
    timer = DariusTimer(
        id="timer-001",
        label="reunión táctica",
        duration_seconds=120.0,
        created_at=now,
        expires_at=now + 120.0,
    )
    assert timer.id == "timer-001"
    assert timer.label == "reunión táctica"
    assert timer.duration_seconds == 120.0
    assert timer.status == "active"
    assert timer.expires_at == now + 120.0


def test_backward_compatibility_aliases():
    assert StarkTimer is DariusTimer
    assert StarkTimerManager is DariusTimerManager
    assert get_stark_timer_manager is get_darius_timer_manager


def test_manager_create_and_get_timer():
    manager = DariusTimerManager()
    try:
        timer = manager.create_timer(label="té verde", seconds=180.0)
        assert timer.id.startswith("timer_") or len(timer.id) > 0
        assert timer.label == "té verde"
        assert timer.duration_seconds == 180.0
        assert timer.status == "active"
        assert timer.expires_at > timer.created_at

        fetched = manager.get_timer(timer.id)
        assert fetched is not None
        assert fetched.id == timer.id

        remaining = manager.get_remaining_seconds(timer.id)
        assert 178.0 <= remaining <= 180.5

        active_timers = manager.list_active_timers()
        assert any(t.id == timer.id for t in active_timers)
    finally:
        manager.stop_all()


def test_manager_cancel_timer():
    manager = DariusTimerManager()
    try:
        timer = manager.create_timer(label="horno", seconds=600.0)
        assert timer.status == "active"

        cancelled = manager.cancel_timer(timer.id)
        assert cancelled is True

        fetched = manager.get_timer(timer.id)
        assert fetched is not None
        assert fetched.status == "cancelled"

        active_timers = manager.list_active_timers()
        assert not any(t.id == timer.id for t in active_timers)

        # Cancelar de nuevo debe retornar False
        assert manager.cancel_timer(timer.id) is False
        # Cancelar temporizador inexistente
        assert manager.cancel_timer("non_existent_id") is False
    finally:
        manager.stop_all()


def test_manager_get_nonexistent_timer():
    manager = DariusTimerManager()
    try:
        assert manager.get_timer("inexistente") is None
        assert manager.get_remaining_seconds("inexistente") == 0.0
    finally:
        manager.stop_all()


def test_timer_expiration_and_callback():
    manager = DariusTimerManager()
    callback_called = threading.Event()
    received_timer = []

    def on_expire(timer):
        received_timer.append(timer)
        callback_called.set()

    try:
        timer = manager.create_timer(label="espresso", seconds=0.1, on_expire_callback=on_expire)
        assert callback_called.wait(timeout=2.0) is True

        assert len(received_timer) == 1
        assert received_timer[0].id == timer.id

        # El temporizador debe estar marcado como expired
        fetched = manager.get_timer(timer.id)
        assert fetched is not None
        assert fetched.status == "expired"
        assert manager.get_remaining_seconds(timer.id) == 0.0
        assert not any(t.id == timer.id for t in manager.list_active_timers())
    finally:
        manager.stop_all()


def test_timer_callback_without_arguments():
    manager = DariusTimerManager()
    callback_called = threading.Event()

    def zero_arg_callback():
        callback_called.set()

    try:
        manager.create_timer(label="quick", seconds=0.05, on_expire_callback=zero_arg_callback)
        assert callback_called.wait(timeout=2.0) is True
    finally:
        manager.stop_all()


def test_timer_callback_exception_handled():
    manager = DariusTimerManager()

    def failing_callback(_timer):
        raise RuntimeError("Fallo deliberado en callback")

    try:
        timer = manager.create_timer(label="failing", seconds=0.05, on_expire_callback=failing_callback)
        time.sleep(0.2)
        # No debe crashear el thread del manager y el estado debe ser expired
        fetched = manager.get_timer(timer.id)
        assert fetched is not None
        assert fetched.status == "expired"
    finally:
        manager.stop_all()


def test_timer_triggers_sfx_on_expiration():
    manager = DariusTimerManager()
    mock_sfx = MagicMock()
    target_mod = DariusTimerManager.__module__

    with patch(f"{target_mod}.get_sfx_engine", return_value=mock_sfx):
        try:
            manager.create_timer(label="alarma", seconds=0.05)
            time.sleep(0.25)
            assert mock_sfx.play_target_lock.called or mock_sfx.play_alert_tone.called
        finally:
            manager.stop_all()


def test_format_timer_speech():
    manager = DariusTimerManager()
    try:
        now = time.time()
        timer = DariusTimer(
            id="t-speech",
            label="render de video",
            duration_seconds=300.0,
            created_at=now,
            expires_at=now + 125.0,  # 2 min 5 seg
        )

        # Formato expirado
        expired_speech = manager.format_timer_speech(timer, expired=True)
        assert "Señor, el temporizador de render de video ha concluido." in expired_speech

        # Formato activo con minutos y segundos
        active_speech = manager.format_timer_speech(timer, expired=False)
        assert "render de video" in active_speech
        assert "minuto" in active_speech
        assert "segundo" in active_speech
        assert "señor." in active_speech.lower()

        # Formato activo con solo segundos
        timer_short = DariusTimer(
            id="t-short",
            label="microondas",
            duration_seconds=45.0,
            created_at=now,
            expires_at=now + 45.0,
        )
        short_speech = manager.format_timer_speech(timer_short, expired=False)
        assert "microondas" in short_speech
        assert "segundos" in short_speech
        assert "minuto" not in short_speech
    finally:
        manager.stop_all()


def test_thread_safety_and_stop_all():
    manager = DariusTimerManager()
    threads = []
    created_ids = []
    lock = threading.Lock()

    def worker():
        for i in range(5):
            t = manager.create_timer(label=f"worker_timer_{i}", seconds=50.0)
            with lock:
                created_ids.append(t.id)

    for _ in range(4):
        th = threading.Thread(target=worker)
        threads.append(th)
        th.start()

    for th in threads:
        th.join()

    assert len(created_ids) == 20
    assert len(manager.list_active_timers()) == 20

    manager.stop_all()
    assert not manager.is_running


def test_singleton_get_darius_timer_manager():
    m1 = get_darius_timer_manager()
    m2 = get_darius_timer_manager()
    assert m1 is m2
