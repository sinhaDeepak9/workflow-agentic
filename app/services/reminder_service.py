"""Reminder / timer worker.

BPMN boundary timers are modelled as a background scan that resolves the current
*effective* assignee for every open human task and emits a reminder event.
Reminders never advance the graph.
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Dict

from app.models.enums import AuditEventType

if TYPE_CHECKING:
    from app.container import Container


class ReminderService:
    def __init__(self, container: "Container") -> None:
        self._c = container
        self._timer: threading.Timer | None = None
        self._counts: Dict[str, int] = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        if not self._c.settings.reminder_enabled:
            return
        self._schedule()

    def stop(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    def _schedule(self) -> None:
        interval = self._c.settings.reminder_interval_seconds
        with self._lock:
            self._timer = threading.Timer(interval, self._run)
            self._timer.daemon = True
            self._timer.start()

    def _run(self) -> None:
        try:
            self.scan_once()
        finally:
            self._schedule()

    def scan_once(self) -> int:
        """Send reminders for all open tasks. Returns the number sent."""
        sent = 0
        max_count = self._c.settings.reminder_max_count
        for task in self._c.task_store.list_open():
            count = self._counts.get(task.task_id, 0)
            if count >= max_count:
                continue
            assignee = task.effective_assignee  # resolved dynamically
            if not assignee:
                continue
            self._counts[task.task_id] = count + 1
            self._c.audit_service.emit(
                task.workflow_id, AuditEventType.REMINDER_SENT.value, "system",
                {"taskId": task.task_id, "assignee": assignee, "reminderNumber": count + 1},
            )
            sent += 1
        return sent
