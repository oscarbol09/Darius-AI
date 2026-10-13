"""
test_task_scheduler.py — Tests unitarios para TaskScheduler (tareas programadas interval/once/cron)
"""

from __future__ import annotations

import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from src.darius_ai.core.task_scheduler import ScheduleType, TaskScheduler, TaskStatus


@pytest.fixture
def temp_scheduler():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_scheduler.db"
        sched = TaskScheduler(db_path=db_path, poll_interval=1)
        yield sched
        sched.stop()


def test_schedule_interval_task(temp_scheduler):
    task = temp_scheduler.schedule_task(
        prompt="Verificar estado de batería",
        schedule_type=ScheduleType.INTERVAL,
        schedule_value="30",
        agent="system",
    )
    assert task.id is not None
    assert task.status == TaskStatus.ACTIVE

    tasks = temp_scheduler.list_tasks()
    assert len(tasks) == 1
    assert tasks[0].prompt == "Verificar estado de batería"


def test_schedule_once_task_due(temp_scheduler):
    # Crear una tarea programada para hace 1 segundo (ya vencida)
    past_iso = (datetime.now(UTC) - timedelta(seconds=2)).isoformat()
    task = temp_scheduler.schedule_task(
        prompt="Recordatorio urgente",
        schedule_type=ScheduleType.ONCE,
        schedule_value=past_iso,
    )
    due_tasks = temp_scheduler.get_due_tasks()
    assert len(due_tasks) == 1
    assert due_tasks[0].id == task.id

    # Marcar como ejecutada
    temp_scheduler.mark_executed(task.id, success=True, result="Alerta mostrada")
    # Para tareas 'once', el estado debe pasar a COMPLETED
    updated_tasks = temp_scheduler.list_tasks()
    assert updated_tasks[0].status == TaskStatus.COMPLETED


def test_pause_and_resume_task(temp_scheduler):
    task = temp_scheduler.schedule_task(
        prompt="Monitorear red",
        schedule_type=ScheduleType.INTERVAL,
        schedule_value="60",
    )
    assert temp_scheduler.pause_task(task.id) is True
    assert temp_scheduler.list_tasks()[0].status == TaskStatus.PAUSED

    assert temp_scheduler.resume_task(task.id) is True
    assert temp_scheduler.list_tasks()[0].status == TaskStatus.ACTIVE


def test_cancel_task(temp_scheduler):
    task = temp_scheduler.schedule_task(
        prompt="Limpiar temporales",
        schedule_type=ScheduleType.INTERVAL,
        schedule_value="120",
    )
    assert temp_scheduler.cancel_task(task.id) is True
    assert temp_scheduler.list_tasks()[0].status == TaskStatus.CANCELLED


def test_schedule_cron_and_invalid_interval(temp_scheduler):
    task_cron = temp_scheduler.schedule_task(
        prompt="Backup diario",
        schedule_type=ScheduleType.CRON,
        schedule_value="0 8 * * *",
    )
    assert task_cron.next_run != ""

    task_invalid = temp_scheduler.schedule_task(
        prompt="Tarea fallback",
        schedule_type=ScheduleType.INTERVAL,
        schedule_value="invalido",
    )
    assert task_invalid.next_run != ""


def test_scheduler_worker_and_callback(temp_scheduler):
    executed = []
    temp_scheduler.executor_callback = lambda t: executed.append(t.prompt)

    # Programar tarea ya vencida
    past_iso = (datetime.now(UTC) - timedelta(seconds=2)).isoformat()
    temp_scheduler.schedule_task(
        prompt="Tarea con callback",
        schedule_type=ScheduleType.ONCE,
        schedule_value=past_iso,
    )

    temp_scheduler.start()
    time.sleep(1.2)
    temp_scheduler.stop()

    assert len(executed) >= 1
    assert "Tarea con callback" in executed

