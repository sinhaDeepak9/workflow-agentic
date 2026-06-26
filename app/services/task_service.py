"""Human task service: lifecycle, optimistic locking, output promotion."""
from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from app.errors import ConflictError, WorkflowError
from app.models.domain import TaskComment, TaskRecord
from app.models.enums import AuditEventType, TaskStatus

if TYPE_CHECKING:
    from app.container import Container


class TaskService:
    def __init__(self, container: "Container") -> None:
        self._c = container

    # -- listing / filtering ----------------------------------------------- #
    def list_all_tasks(
        self,
        *,
        workflow_id: Optional[str] = None,
        status: Optional[List[str]] = None,
        task_type: Optional[str] = None,
        assignee: Optional[str] = None,
        effective_assignee: Optional[str] = None,
        candidate_group: Optional[str] = None,
        due_before: Optional[str] = None,
        due_after: Optional[str] = None,
        created_after: Optional[float] = None,
        created_before: Optional[float] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Return a paginated, filtered list of all task records across all workflows."""
        items = self._c.task_store.list_all()

        if workflow_id:
            items = [t for t in items if t.workflow_id == workflow_id]

        if status:
            allowed = {s.upper() for s in status}
            items = [t for t in items if t.status.value in allowed]

        if task_type:
            tt = task_type.lower()
            items = [t for t in items if t.task_type.lower() == tt]

        if assignee:
            needle = assignee.lower()
            items = [t for t in items if t.assignee and needle in t.assignee.lower()]

        if effective_assignee:
            needle = effective_assignee.lower()
            items = [
                t for t in items
                if t.effective_assignee and needle in t.effective_assignee.lower()
            ]

        if candidate_group:
            needle = candidate_group.lower()
            items = [
                t for t in items
                if any(needle in g.lower() for g in t.candidate_groups)
            ]

        if due_before:
            items = [t for t in items if t.due_date and t.due_date <= due_before]

        if due_after:
            items = [t for t in items if t.due_date and t.due_date >= due_after]

        if created_after is not None:
            items = [t for t in items if t.created_at >= created_after]

        if created_before is not None:
            items = [t for t in items if t.created_at <= created_before]

        items.sort(key=lambda t: t.created_at, reverse=True)

        total = len(items)
        start = (page - 1) * page_size
        return {
            "total": total,
            "page": page,
            "pageSize": page_size,
            "items": items[start: start + page_size],
        }

    # -- reads ------------------------------------------------------------- #
    def list_tasks(self, workflow_id: str) -> List[TaskRecord]:
        self._c.instance_store.get(workflow_id)  # existence check
        return self._c.task_store.list_for_workflow(workflow_id)

    def get_task(self, task_id: str) -> TaskRecord:
        return self._c.task_store.get(task_id)

    # -- creation (idempotent, called from graph node) --------------------- #
    def ensure_task(
        self,
        workflow_id: str,
        node: str,
        task_type: str,
        task_name: str,
        assignee: Optional[str],
        candidate_groups: List[str],
        due_date: Optional[str] = None,
    ) -> TaskRecord:
        existing = self._c.task_store.find_for_node(workflow_id, node)
        if existing is not None:
            return existing
        definition = self._c.definition_service.get_for_instance(workflow_id)
        schema_version = definition.task_schemas.get(task_type, {}).get("version", 1)
        task = TaskRecord(
            task_id=f"task_{uuid.uuid4().hex[:12]}",
            workflow_id=workflow_id,
            task_type=task_type,
            task_schema_version=schema_version,
            task_name=task_name,
            node=node,
            status=TaskStatus.PENDING,
            assignee=assignee,
            candidate_users=[assignee] if assignee else [],
            candidate_groups=list(candidate_groups),
            due_date=due_date,
        )
        self._c.task_store.put(task)
        self._c.audit_service.emit(
            workflow_id, AuditEventType.TASK_CREATED.value, "system",
            {"taskId": task.task_id, "taskType": task_type, "assignee": assignee},
        )
        return task

    # -- mutations --------------------------------------------------------- #
    def _check_version(self, task: TaskRecord, expected: int) -> None:
        if task.task_version != expected:
            raise ConflictError(
                f"Stale task version: expected {task.task_version}, got {expected}"
            )

    def claim_task(self, task_id: str, actor: str, expected_version: int) -> TaskRecord:
        with self._c.task_store.lock():
            task = self._c.task_store.get(task_id)
            self._require_active(task)
            self._c.authz.require_claim(actor, task)
            self._check_version(task, expected_version)
            task.assignee = actor
            task.delegated_to = None
            task.status = TaskStatus.IN_PROGRESS
            task.task_version += 1
            self._c.task_store.put(task)
        self._c.audit_service.emit(
            task.workflow_id, AuditEventType.TASK_CLAIMED.value, actor, {"taskId": task_id}
        )
        return task

    def delegate_task(
        self, task_id: str, actor: str, delegate_to: str, reason: Optional[str],
        expected_version: int, idempotency_key: Optional[str] = None,
    ) -> TaskRecord:
        if self._c.idempotency_get(idempotency_key) is not None:
            return self._c.task_store.get(task_id)
        with self._c.task_store.lock():
            task = self._c.task_store.get(task_id)
            self._require_active(task)
            self._c.authz.require_delegate(actor, task)
            self._check_version(task, expected_version)
            task.delegated_from = task.effective_assignee
            task.delegated_to = delegate_to
            task.status = TaskStatus.DELEGATED
            task.task_version += 1
            self._c.task_store.put(task)
        self._c.audit_service.emit(
            task.workflow_id, AuditEventType.TASK_DELEGATED.value, actor,
            {"taskId": task_id, "delegateTo": delegate_to, "reason": reason},
        )
        self._c.idempotency_set(idempotency_key, task_id)
        return task

    def reassign_task(
        self, task_id: str, actor: str, assign_to: str, reason: Optional[str],
        expected_version: int,
    ) -> TaskRecord:
        self._c.authz.require_reassign(actor)
        with self._c.task_store.lock():
            task = self._c.task_store.get(task_id)
            self._require_active(task)
            self._check_version(task, expected_version)
            task.assignee = assign_to
            task.delegated_to = None
            task.delegated_from = None
            task.status = TaskStatus.PENDING
            task.task_version += 1
            self._c.task_store.put(task)
        self._c.audit_service.emit(
            task.workflow_id, AuditEventType.TASK_REASSIGNED.value, actor,
            {"taskId": task_id, "assignTo": assign_to, "reason": reason},
        )
        return task

    def complete_task(
        self, task_id: str, actor: str, expected_version: int,
        output: Dict[str, Any], comment: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self._c.idempotency_get(idempotency_key) is not None:
            return self._build_complete_response(task_id, idempotent=True)

        with self._c.task_store.lock():
            task = self._c.task_store.get(task_id)
            self._require_active(task)
            self._c.authz.require_complete(actor, task)
            self._check_version(task, expected_version)
            # Validate payload against the task schema version.
            self._c.definition_service.validate_task_output(
                task.workflow_id, task.task_type, output
            )
            task.output_data = dict(output)
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            task.task_version += 1
            if comment:
                task.comments.append(TaskComment(actor=actor, text=comment))
            self._c.task_store.put(task)

        self._c.audit_service.emit(
            task.workflow_id, AuditEventType.TASK_COMPLETED.value, actor,
            {"taskId": task_id, "output": output},
        )
        # Promote mapped fields and resume the graph.
        self._c.workflow_service.resume_after_task(task.workflow_id, output, actor)
        self._c.idempotency_set(idempotency_key, task_id)
        return self._build_complete_response(task_id)

    def add_comment(self, task_id: str, actor: str, text: str) -> TaskRecord:
        with self._c.task_store.lock():
            task = self._c.task_store.get(task_id)
            task.comments.append(TaskComment(actor=actor, text=text))
            self._c.task_store.put(task)
        self._c.audit_service.emit(
            task.workflow_id, AuditEventType.TASK_COMMENTED.value, actor, {"taskId": task_id}
        )
        return task

    def get_task_data(self, task_id: str) -> Dict[str, Any]:
        task = self._c.task_store.get(task_id)
        return {"draftData": task.draft_data, "outputData": task.output_data}

    def patch_task_data(
        self, task_id: str, actor: str, expected_version: int, draft_data: Dict[str, Any]
    ) -> TaskRecord:
        with self._c.task_store.lock():
            task = self._c.task_store.get(task_id)
            self._require_active(task)
            self._check_version(task, expected_version)
            task.draft_data.update(draft_data)
            task.task_version += 1
            self._c.task_store.put(task)
        self._c.audit_service.emit(
            task.workflow_id, AuditEventType.TASK_DATA_PATCHED.value, actor, {"taskId": task_id}
        )
        return task

    def cancel_open_tasks(self, workflow_id: str, actor: str) -> None:
        with self._c.task_store.lock():
            for task in self._c.task_store.list_for_workflow(workflow_id):
                if task.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
                    task.status = TaskStatus.CANCELLED
                    task.task_version += 1
                    self._c.task_store.put(task)

    # -- helpers ----------------------------------------------------------- #
    def _require_active(self, task: TaskRecord) -> None:
        if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            raise WorkflowError(f"Task {task.task_id} is already {task.status.value}")

    def _build_complete_response(self, task_id: str, idempotent: bool = False) -> Dict[str, Any]:
        task = self._c.task_store.get(task_id)
        instance = self._c.instance_store.get(task.workflow_id)
        promoted = self._c.definition_service.filter_promotion(
            task.workflow_id, task.task_type, task.output_data or {}
        )
        return {
            "taskId": task.task_id,
            "workflowId": task.workflow_id,
            "taskStatus": task.status.value,
            "workflowStatus": instance.status.value,
            "resumed": True,
            "idempotentReplay": idempotent,
            "promotedVariables": promoted,
        }
