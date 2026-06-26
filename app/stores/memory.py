"""In-memory implementations of the four separated stores.

claude.md mandates strict separation between:
  - definition store
  - workflow state / checkpoint store
  - task store
  - audit / event store

Each store guards its own dict with a re-entrant lock. Optimistic locking is
enforced by the service layer via the `state_version` / `task_version` fields.
"""
from __future__ import annotations

import threading
from typing import Dict, List, Optional

from app.errors import NotFoundError
from app.models.domain import (
    AuditEvent,
    TaskRecord,
    WorkflowDefinition,
    WorkflowInstance,
)


class DefinitionStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        # keyed by (workflow_type, version)
        self._data: Dict[tuple, WorkflowDefinition] = {}

    def put(self, definition: WorkflowDefinition) -> WorkflowDefinition:
        with self._lock:
            self._data[(definition.workflow_type, definition.version)] = definition
            return definition

    def get(self, workflow_type: str, version: int) -> WorkflowDefinition:
        with self._lock:
            key = (workflow_type, version)
            if key not in self._data:
                raise NotFoundError(
                    f"Definition {workflow_type} v{version} not found"
                )
            return self._data[key]

    def list_versions(self, workflow_type: str) -> List[WorkflowDefinition]:
        with self._lock:
            return sorted(
                (d for d in self._data.values() if d.workflow_type == workflow_type),
                key=lambda d: d.version,
            )

    def latest_version(self, workflow_type: str) -> Optional[int]:
        versions = self.list_versions(workflow_type)
        return versions[-1].version if versions else None


class InstanceStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._data: Dict[str, WorkflowInstance] = {}

    def put(self, instance: WorkflowInstance) -> WorkflowInstance:
        with self._lock:
            self._data[instance.workflow_id] = instance
            return instance

    def get(self, workflow_id: str) -> WorkflowInstance:
        with self._lock:
            if workflow_id not in self._data:
                raise NotFoundError(f"Workflow {workflow_id} not found")
            return self._data[workflow_id]

    def list_all(self) -> List[WorkflowInstance]:
        with self._lock:
            return list(self._data.values())

    def lock(self) -> threading.RLock:
        return self._lock


class TaskStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._data: Dict[str, TaskRecord] = {}

    def put(self, task: TaskRecord) -> TaskRecord:
        with self._lock:
            self._data[task.task_id] = task
            return task

    def get(self, task_id: str) -> TaskRecord:
        with self._lock:
            if task_id not in self._data:
                raise NotFoundError(f"Task {task_id} not found")
            return self._data[task_id]

    def list_for_workflow(self, workflow_id: str) -> List[TaskRecord]:
        with self._lock:
            return [t for t in self._data.values() if t.workflow_id == workflow_id]

    def find_open(self, workflow_id: str, node: str) -> Optional[TaskRecord]:
        from app.models.enums import TaskStatus

        terminal = {TaskStatus.COMPLETED, TaskStatus.CANCELLED}
        with self._lock:
            for t in self._data.values():
                if (
                    t.workflow_id == workflow_id
                    and t.node == node
                    and t.status not in terminal
                ):
                    return t
        return None

    def find_for_node(self, workflow_id: str, node: str) -> Optional[TaskRecord]:
        """Latest task for a node regardless of status.

        Used for idempotent task creation: when a human-task node re-executes on
        resume, the existing (possibly completed) task is returned instead of
        creating a duplicate. This graph visits each human node once.
        """
        with self._lock:
            matches = [
                t
                for t in self._data.values()
                if t.workflow_id == workflow_id and t.node == node
            ]
            return max(matches, key=lambda t: t.created_at) if matches else None

    def list_open(self) -> List[TaskRecord]:
        from app.models.enums import TaskStatus

        terminal = {TaskStatus.COMPLETED, TaskStatus.CANCELLED}
        with self._lock:
            return [t for t in self._data.values() if t.status not in terminal]

    def list_all(self) -> List[TaskRecord]:
        with self._lock:
            return list(self._data.values())

    def lock(self) -> threading.RLock:
        return self._lock


class AuditStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._data: List[AuditEvent] = []

    def append(self, event: AuditEvent) -> AuditEvent:
        with self._lock:
            self._data.append(event)
            return event

    def list_for_workflow(self, workflow_id: str) -> List[AuditEvent]:
        with self._lock:
            return [e for e in self._data if e.workflow_id == workflow_id]
