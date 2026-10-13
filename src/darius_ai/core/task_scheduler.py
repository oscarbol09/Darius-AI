"""
task_scheduler.py — Programador de tareas en segundo plano para Darius AI
========================================================================
Arquitectura Nativa Darius AI. Soporta tareas programadas de una sola vez (once),
intervalos recurrentes en segundos (interval) y expresiones cron simplificadas en SQLite con WAL.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import uuid
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

from src.darius_ai.core.config_loader import get_user_data_dir

log = logging.getLogger("DARIUS.TaskScheduler")


class ScheduleType(StrEnum):
    ONCE = "once"
    INTERVAL = "interval"
    CRON = "cron"


class TaskStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class ScheduledTask:
    id: str
    prompt: str
    schedule_type: ScheduleType
    schedule_value: str
    status: TaskStatus = TaskStatus.ACTIVE
    next_run: str = ""
    last_run: str = ""
    agent: str = "system"


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _now_iso() -> str:
    return _now_utc().isoformat()


class TaskScheduler:
    """
    Motor autónomo de programación de tareas con persistencia en SQLite.
    """

    def __init__(
        self,
        db_path: Path | str | None = None,
        poll_interval: int = 10,
        executor_callback: Callable[[ScheduledTask], Any] | None = None,
    ) -> None:
        if db_path is None:
            db_path = get_user_data_dir() / "scheduler.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.poll_interval = poll_interval
        self.executor_callback = executor_callback

        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._init_db()

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    id TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    schedule_type TEXT NOT NULL,
                    schedule_value TEXT NOT NULL,
                    status TEXT NOT NULL,
                    next_run TEXT NOT NULL,
                    last_run TEXT,
                    agent TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS task_run_logs (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    executed_at TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    result TEXT
                );
                """
            )

    def _compute_initial_next_run(self, schedule_type: ScheduleType, schedule_value: str) -> str:
        now = _now_utc()
        if schedule_type == ScheduleType.ONCE:
            return schedule_value
        elif schedule_type == ScheduleType.INTERVAL:
            try:
                seconds = float(schedule_value)
                return (now + timedelta(seconds=seconds)).isoformat()
            except ValueError:
                return (now + timedelta(minutes=5)).isoformat()
        else:  # CRON o aproximación
            return (now + timedelta(hours=1)).isoformat()

    def schedule_task(
        self,
        prompt: str,
        schedule_type: ScheduleType | str,
        schedule_value: str,
        agent: str = "system",
    ) -> ScheduledTask:
        st_enum = ScheduleType(schedule_type) if isinstance(schedule_type, str) else schedule_type
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        next_run = self._compute_initial_next_run(st_enum, schedule_value)

        task = ScheduledTask(
            id=task_id,
            prompt=prompt,
            schedule_type=st_enum,
            schedule_value=schedule_value,
            status=TaskStatus.ACTIVE,
            next_run=next_run,
            agent=agent,
        )

        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO scheduled_tasks (
                    id, prompt, schedule_type, schedule_value, status, next_run, last_run, agent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    task.prompt,
                    task.schedule_type.value,
                    task.schedule_value,
                    task.status.value,
                    task.next_run,
                    task.last_run,
                    task.agent,
                ),
            )
        log.info(f"[Scheduler] Tarea programada '{task.id}': '{prompt}' (próxima: {next_run})")
        return task

    def list_tasks(self) -> list[ScheduledTask]:
        with self._connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, prompt, schedule_type, schedule_value, status, next_run, last_run, agent
                FROM scheduled_tasks
                """
            )
            rows = cursor.fetchall()

        tasks = []
        for r in rows:
            tasks.append(
                ScheduledTask(
                    id=r[0],
                    prompt=r[1],
                    schedule_type=ScheduleType(r[2]),
                    schedule_value=r[3],
                    status=TaskStatus(r[4]),
                    next_run=r[5],
                    last_run=r[6] or "",
                    agent=r[7],
                )
            )
        return tasks

    def get_due_tasks(self) -> list[ScheduledTask]:
        now_str = _now_iso()
        with self._connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, prompt, schedule_type, schedule_value, status, next_run, last_run, agent
                FROM scheduled_tasks
                WHERE status = 'active' AND next_run <= ?
                """,
                (now_str,),
            )
            rows = cursor.fetchall()

        due = []
        for r in rows:
            due.append(
                ScheduledTask(
                    id=r[0],
                    prompt=r[1],
                    schedule_type=ScheduleType(r[2]),
                    schedule_value=r[3],
                    status=TaskStatus(r[4]),
                    next_run=r[5],
                    last_run=r[6] or "",
                    agent=r[7],
                )
            )
        return due

    def mark_executed(self, task_id: str, success: bool, result: str = "") -> None:
        now_str = _now_iso()
        log_id = f"log-{uuid.uuid4().hex[:8]}"

        with self._connection() as conn:
            conn.execute(
                "INSERT INTO task_run_logs (id, task_id, executed_at, success, result) VALUES (?, ?, ?, ?, ?)",
                (log_id, task_id, now_str, 1 if success else 0, result[:1000]),
            )

            cursor = conn.execute(
                "SELECT schedule_type, schedule_value FROM scheduled_tasks WHERE id = ?",
                (task_id,),
            )
            row = cursor.fetchone()
            if not row:
                return

            st_type = ScheduleType(row[0])
            st_val = row[1]

            if st_type == ScheduleType.ONCE:
                conn.execute(
                    "UPDATE scheduled_tasks SET status = 'completed', last_run = ? WHERE id = ?",
                    (now_str, task_id),
                )
            elif st_type == ScheduleType.INTERVAL:
                try:
                    secs = float(st_val)
                    next_run = (_now_utc() + timedelta(seconds=secs)).isoformat()
                except ValueError:
                    next_run = (_now_utc() + timedelta(minutes=5)).isoformat()

                conn.execute(
                    "UPDATE scheduled_tasks SET last_run = ?, next_run = ? WHERE id = ?",
                    (now_str, next_run, task_id),
                )
            else:
                next_run = (_now_utc() + timedelta(hours=1)).isoformat()
                conn.execute(
                    "UPDATE scheduled_tasks SET last_run = ?, next_run = ? WHERE id = ?",
                    (now_str, next_run, task_id),
                )

    def pause_task(self, task_id: str) -> bool:
        with self._connection() as conn:
            res = conn.execute("UPDATE scheduled_tasks SET status = 'paused' WHERE id = ?", (task_id,))
            return res.rowcount > 0

    def resume_task(self, task_id: str) -> bool:
        with self._connection() as conn:
            res = conn.execute("UPDATE scheduled_tasks SET status = 'active' WHERE id = ?", (task_id,))
            return res.rowcount > 0

    def cancel_task(self, task_id: str) -> bool:
        with self._connection() as conn:
            res = conn.execute("UPDATE scheduled_tasks SET status = 'cancelled' WHERE id = ?", (task_id,))
            return res.rowcount > 0

    def start(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            return
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._poll_loop, daemon=True, name="DariusTaskScheduler")
        self._worker_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                due_tasks = self.get_due_tasks()
                for task in due_tasks:
                    if self.executor_callback:
                        try:
                            res = self.executor_callback(task)
                            self.mark_executed(task.id, success=True, result=str(res))
                        except Exception as exc:
                            log.error(f"[Scheduler] Error ejecutando tarea {task.id}: {exc}")
                            self.mark_executed(task.id, success=False, result=str(exc))
            except Exception as e:
                log.error(f"[Scheduler] Error en ciclo de sondeo: {e}")

            self._stop_event.wait(self.poll_interval)
