"""Audit / event emission service."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from app.models.domain import AuditEvent

if TYPE_CHECKING:
    from app.container import Container


class AuditService:
    def __init__(self, container: "Container") -> None:
        self._c = container

    def emit(
        self,
        workflow_id: str,
        event_type: str,
        actor: Optional[str],
        detail: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            workflow_id=workflow_id,
            event_type=event_type,
            actor=actor,
            detail=detail or {},
        )
        return self._c.audit_store.append(event)

    def history(self, workflow_id: str) -> List[AuditEvent]:
        return self._c.audit_store.list_for_workflow(workflow_id)
