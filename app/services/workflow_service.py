"""Workflow instance service: lifecycle, state, and graph orchestration."""
from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from langgraph.types import Command

from app.errors import ConflictError, ValidationFailure, WorkflowError
from app.graph.state import CONTROL_KEYS
from app.models.domain import WorkflowInstance
from app.models.enums import AuditEventType, WorkflowStatus

if TYPE_CHECKING:
    from app.container import Container


class WorkflowService:
    def __init__(self, container: "Container") -> None:
        self._c = container

    # -- listing / filtering ----------------------------------------------- #
    def list_workflows(
        self,
        *,
        status: Optional[List[str]] = None,
        workflow_type: Optional[str] = None,
        current_node: Optional[str] = None,
        definition_version: Optional[int] = None,
        owner: Optional[str] = None,
        created_after: Optional[float] = None,
        created_before: Optional[float] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Return a paginated, filtered list of all workflow instances."""
        items = self._c.instance_store.list_all()

        if status:
            allowed = {s.upper() for s in status}
            items = [i for i in items if i.status.value in allowed]

        if workflow_type:
            wt = workflow_type.lower()
            items = [i for i in items if i.workflow_type.lower() == wt]

        if current_node:
            items = [i for i in items if i.current_node == current_node]

        if definition_version is not None:
            items = [i for i in items if i.definition_version == definition_version]

        if owner:
            needle = owner.lower()
            def _owner_match(inst: "WorkflowInstance") -> bool:  # type: ignore[name-defined]
                v = inst.variables
                scalars = [
                    v.get(k) for k in ("targetUser", "reviewer", "supervisor", "mqdUser", "mcoUser")
                ]
                lists = v.get("reportOwners") or []
                candidates = [str(s).lower() for s in scalars if s] + [
                    str(u).lower() for u in lists
                ]
                return any(needle in c for c in candidates)
            items = [i for i in items if _owner_match(i)]

        if created_after is not None:
            items = [i for i in items if i.created_at >= created_after]

        if created_before is not None:
            items = [i for i in items if i.created_at <= created_before]

        items.sort(key=lambda i: i.created_at, reverse=True)

        total = len(items)
        start = (page - 1) * page_size
        return {
            "total": total,
            "page": page,
            "pageSize": page_size,
            "items": items[start: start + page_size],
        }

    def _config(self, workflow_id: str) -> dict:
        return {"configurable": {"thread_id": workflow_id}}

    # -- lifecycle --------------------------------------------------------- #
    def start_workflow(
        self,
        actor: str,
        variables: Dict[str, Any],
        idempotency_key: Optional[str] = None,
    ) -> WorkflowInstance:
        cached = self._c.idempotency_get(idempotency_key)
        if cached is not None:
            return self._c.instance_store.get(cached)

        wf_type = self._c.settings.workflow_type
        version = self._c.settings.default_definition_version
        definition = self._c.definition_service.get(wf_type, version)

        workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
        instance = WorkflowInstance(
            workflow_id=workflow_id,
            workflow_type=wf_type,
            definition_version=definition.version,
            state_schema_version=definition.state_schema_version,
            status=WorkflowStatus.RUNNING,
            variables=dict(variables),
        )
        self._c.instance_store.put(instance)
        self._c.audit_service.emit(
            workflow_id, AuditEventType.WORKFLOW_STARTED.value, actor, {"variables": variables}
        )

        initial_state = {**variables, "current_node": None, "current_task_id": None}
        self._drive(workflow_id, initial_state)

        self._c.idempotency_set(idempotency_key, workflow_id)
        return self._c.instance_store.get(workflow_id)

    def mark_waiting(self, workflow_id: str, node: str, task_id: str) -> None:
        """Called from a human-task node before it interrupts."""
        with self._c.instance_store.lock():
            instance = self._c.instance_store.get(workflow_id)
            instance.status = WorkflowStatus.WAITING_ON_HUMAN_TASK
            instance.current_node = node
            instance.current_task_id = task_id
            instance.updated_at = time.time()
            self._c.instance_store.put(instance)

    def resume_after_task(self, workflow_id: str, output: Dict[str, Any], actor: str) -> None:
        """Resume the paused graph with the completed task output."""
        self._drive(workflow_id, Command(resume=output))
        self._c.audit_service.emit(
            workflow_id, AuditEventType.WORKFLOW_RESUMED.value, actor, {"trigger": "task_completed"}
        )

    def resume_workflow(self, workflow_id: str, actor: str, idempotency_key: Optional[str] = None) -> WorkflowInstance:
        if self._c.idempotency_get(idempotency_key) is not None:
            return self._c.instance_store.get(workflow_id)
        instance = self._c.instance_store.get(workflow_id)
        if instance.status != WorkflowStatus.WAITING_ON_HUMAN_TASK:
            raise WorkflowError("Workflow is not waiting and cannot be resumed manually")
        # Re-drive without new input; remains paused until task completion resumes it.
        self._sync_from_graph(workflow_id)
        self._c.audit_service.emit(
            workflow_id, AuditEventType.WORKFLOW_RESUMED.value, actor, {"trigger": "manual"}
        )
        self._c.idempotency_set(idempotency_key, workflow_id)
        return self._c.instance_store.get(workflow_id)

    def cancel_workflow(
        self, workflow_id: str, actor: str, reason: Optional[str], idempotency_key: Optional[str] = None
    ) -> WorkflowInstance:
        self._c.authz.require_cancel(actor)
        if self._c.idempotency_get(idempotency_key) is not None:
            return self._c.instance_store.get(workflow_id)
        with self._c.instance_store.lock():
            instance = self._c.instance_store.get(workflow_id)
            instance.status = WorkflowStatus.CANCELLED
            instance.updated_at = time.time()
            self._c.instance_store.put(instance)
        self._c.task_service.cancel_open_tasks(workflow_id, actor)
        self._c.audit_service.emit(
            workflow_id, AuditEventType.WORKFLOW_CANCELLED.value, actor, {"reason": reason}
        )
        self._c.idempotency_set(idempotency_key, workflow_id)
        return instance

    # -- state ------------------------------------------------------------- #
    def patch_state(
        self,
        workflow_id: str,
        actor: str,
        expected_state_version: int,
        updates: Dict[str, Any],
        reason: Optional[str],
    ) -> WorkflowInstance:
        self._c.authz.require_patch_state(actor)
        self._c.definition_service.validate_state_updates(workflow_id, updates)
        with self._c.instance_store.lock():
            instance = self._c.instance_store.get(workflow_id)
            if instance.state_version != expected_state_version:
                raise ConflictError(
                    f"Stale state version: expected {instance.state_version}, "
                    f"got {expected_state_version}"
                )
            instance.variables.update(updates)
            instance.state_version += 1
            instance.updated_at = time.time()
            self._c.instance_store.put(instance)
        # Keep the checkpoint consistent so a later resume sees patched values.
        try:
            self._c.graph.update_state(self._config(workflow_id), updates)
        except Exception:  # checkpoint may not exist yet for a brand-new instance
            pass
        self._c.audit_service.emit(
            workflow_id,
            AuditEventType.WORKFLOW_STATE_PATCHED.value,
            actor,
            {"updates": updates, "reason": reason},
        )
        return instance

    # -- graph driving ----------------------------------------------------- #
    def _drive(self, workflow_id: str, graph_input) -> None:
        config = self._config(workflow_id)
        self._c.graph.invoke(graph_input, config)
        self._sync_from_graph(workflow_id)

    def _sync_from_graph(self, workflow_id: str) -> None:
        config = self._config(workflow_id)
        snapshot = self._c.graph.get_state(config)
        values: Dict[str, Any] = dict(snapshot.values or {})
        with self._c.instance_store.lock():
            instance = self._c.instance_store.get(workflow_id)
            if instance.status == WorkflowStatus.CANCELLED:
                return
            instance.variables = {
                k: v for k, v in values.items() if k not in CONTROL_KEYS
            }
            if snapshot.next:
                # Pending work remains. A paused human-task node leaves an open
                # task in the task store (see human-task node + mark_waiting).
                open_task = self._find_open_task(workflow_id)
                if open_task is not None:
                    instance.status = WorkflowStatus.WAITING_ON_HUMAN_TASK
                    instance.current_node = open_task.node
                    instance.current_task_id = open_task.task_id
                else:
                    instance.status = WorkflowStatus.RUNNING
                    instance.current_node = values.get("current_node")
                    instance.current_task_id = None
            else:
                instance.status = WorkflowStatus.COMPLETED
                instance.current_node = values.get("current_node")
                instance.current_task_id = None
                self._c.audit_service.emit(
                    workflow_id, AuditEventType.WORKFLOW_COMPLETED.value, "system", {}
                )
            instance.state_version += 1
            instance.updated_at = time.time()
            self._c.instance_store.put(instance)

    def _find_open_task(self, workflow_id: str):
        terminal = {"COMPLETED", "CANCELLED"}
        for task in self._c.task_store.list_for_workflow(workflow_id):
            if task.status.value not in terminal:
                return task
        return None
