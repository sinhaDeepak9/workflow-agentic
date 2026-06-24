"""Workflow and task status enums (per claude.md / API_information.md)."""
from __future__ import annotations

from enum import Enum


class WorkflowStatus(str, Enum):
    RUNNING = "RUNNING"
    WAITING_ON_HUMAN_TASK = "WAITING_ON_HUMAN_TASK"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    DELEGATED = "DELEGATED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ESCALATED = "ESCALATED"


class TaskType(str, Enum):
    REPORT_SUBMISSION_REVIEW = "report_submission_review"
    SUPERVISOR_REVIEW = "supervisor_review"


class AuditEventType(str, Enum):
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_STATE_PATCHED = "workflow_state_patched"
    WORKFLOW_RESUMED = "workflow_resumed"
    WORKFLOW_CANCELLED = "workflow_cancelled"
    WORKFLOW_COMPLETED = "workflow_completed"
    TASK_CREATED = "task_created"
    TASK_CLAIMED = "task_claimed"
    TASK_DELEGATED = "task_delegated"
    TASK_REASSIGNED = "task_reassigned"
    TASK_COMPLETED = "task_completed"
    TASK_COMMENTED = "task_commented"
    TASK_DATA_PATCHED = "task_data_patched"
    REMINDER_SENT = "reminder_sent"
    DEFINITION_VERSION_PUBLISHED = "definition_version_published"
    MIGRATION_VALIDATED = "migration_validated"
