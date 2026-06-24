"""Dataclass -> JSON-serialisable dict helpers for API responses."""
from __future__ import annotations

from typing import Any, Dict

from app.models.domain import AuditEvent, TaskRecord, WorkflowDefinition, WorkflowInstance
from app.models.enums import TaskStatus


def _allowed_actions(task: TaskRecord) -> list:
    """Actions currently permitted on a task, given its status."""
    if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
        return []
    if task.status == TaskStatus.DELEGATED:
        return ["complete"]
    if task.status == TaskStatus.IN_PROGRESS:
        return ["complete", "delegate"]
    # PENDING / ESCALATED
    return ["claim", "delegate", "complete"]


def workflow_summary(instance: WorkflowInstance) -> Dict[str, Any]:
    return {
        "workflowId": instance.workflow_id,
        "workflowType": instance.workflow_type,
        "definitionVersion": instance.definition_version,
        "stateSchemaVersion": instance.state_schema_version,
        "status": instance.status.value,
        "currentNode": instance.current_node,
        "currentTaskId": instance.current_task_id,
    }


def workflow_state(instance: WorkflowInstance) -> Dict[str, Any]:
    data = workflow_summary(instance)
    data["stateVersion"] = instance.state_version
    data["variables"] = instance.variables
    return data


def task_view(task: TaskRecord) -> Dict[str, Any]:
    return {
        "taskId": task.task_id,
        "workflowId": task.workflow_id,
        "taskType": task.task_type,
        "taskSchemaVersion": task.task_schema_version,
        "taskName": task.task_name,
        "node": task.node,
        "status": task.status.value,
        "assignee": task.assignee,
        "effectiveAssignee": task.effective_assignee,
        "candidateUsers": task.candidate_users,
        "candidateGroups": task.candidate_groups,
        "allowedActions": _allowed_actions(task),
        "delegatedFrom": task.delegated_from,
        "delegatedTo": task.delegated_to,
        "taskVersion": task.task_version,
        "dueDate": task.due_date,
        "createdAt": task.created_at,
        "completedAt": task.completed_at,
        "comments": [
            {"actor": c.actor, "text": c.text, "createdAt": c.created_at}
            for c in task.comments
        ],
        "outputData": task.output_data,
    }


def definition_view(definition: WorkflowDefinition) -> Dict[str, Any]:
    return {
        "workflowType": definition.workflow_type,
        "version": definition.version,
        "stateSchemaVersion": definition.state_schema_version,
        "variableRegistry": definition.variable_registry,
        "deprecatedVariables": definition.deprecated_variables,
        "taskSchemas": definition.task_schemas,
        "outputPromotion": definition.output_promotion,
        "publishedBy": definition.published_by,
        "publishedAt": definition.published_at,
    }


def audit_view(event: AuditEvent) -> Dict[str, Any]:
    return {
        "eventId": event.event_id,
        "workflowId": event.workflow_id,
        "eventType": event.event_type,
        "actor": event.actor,
        "detail": event.detail,
        "createdAt": event.created_at,
    }
