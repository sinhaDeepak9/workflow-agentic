"""Persisted record shapes for the four separated stores.

These are deliberately plain dataclasses so the store layer stays independent
of the API (pydantic) layer. Version fields drive optimistic locking.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.models.enums import TaskStatus, WorkflowStatus


def _now() -> float:
    return time.time()


# --------------------------------------------------------------------------- #
# Definition store
# --------------------------------------------------------------------------- #
@dataclass
class WorkflowDefinition:
    workflow_type: str
    version: int
    state_schema_version: int
    variable_registry: List[str]
    task_schemas: Dict[str, Dict[str, Any]]
    output_promotion: Dict[str, List[str]]
    deprecated_variables: List[str] = field(default_factory=list)
    published_by: Optional[str] = None
    published_at: float = field(default_factory=_now)


# --------------------------------------------------------------------------- #
# Workflow instance store
# --------------------------------------------------------------------------- #
@dataclass
class WorkflowInstance:
    workflow_id: str
    workflow_type: str
    definition_version: int
    state_schema_version: int
    status: WorkflowStatus
    current_node: Optional[str] = None
    current_task_id: Optional[str] = None
    variables: Dict[str, Any] = field(default_factory=dict)
    state_version: int = 0
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)


# --------------------------------------------------------------------------- #
# Task store
# --------------------------------------------------------------------------- #
@dataclass
class TaskComment:
    actor: str
    text: str
    created_at: float = field(default_factory=_now)


@dataclass
class TaskRecord:
    task_id: str
    workflow_id: str
    task_type: str
    task_schema_version: int
    task_name: str
    node: str
    status: TaskStatus = TaskStatus.PENDING
    assignee: Optional[str] = None
    candidate_users: List[str] = field(default_factory=list)
    candidate_groups: List[str] = field(default_factory=list)
    draft_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Optional[Dict[str, Any]] = None
    delegated_from: Optional[str] = None
    delegated_to: Optional[str] = None
    comments: List[TaskComment] = field(default_factory=list)
    task_version: int = 0
    due_date: Optional[str] = None
    created_at: float = field(default_factory=_now)
    completed_at: Optional[float] = None

    @property
    def effective_assignee(self) -> Optional[str]:
        """Reminder workers must resolve the current effective assignee."""
        return self.delegated_to or self.assignee


# --------------------------------------------------------------------------- #
# Audit / event store
# --------------------------------------------------------------------------- #
@dataclass
class AuditEvent:
    event_id: str
    workflow_id: str
    event_type: str
    actor: Optional[str]
    detail: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=_now)
