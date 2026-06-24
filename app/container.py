"""Dependency container: wires stores, services and the compiled graph.

Services hold a back-reference to the container so they can reach siblings,
which keeps the otherwise circular wiring (workflow <-> task) simple.
"""
from __future__ import annotations

import threading
from typing import Dict, Optional

from app.auth import Authorizer
from app.config.settings import get_settings
from app.services.audit_service import AuditService
from app.services.definition_service import DefinitionService
from app.services.reminder_service import ReminderService
from app.services.task_service import TaskService
from app.services.workflow_service import WorkflowService
from app.stores.memory import AuditStore, DefinitionStore, InstanceStore, TaskStore


class Container:
    def __init__(self) -> None:
        self.settings = get_settings()

        # Four separated stores (claude.md constraint #2).
        self.definition_store = DefinitionStore()
        self.instance_store = InstanceStore()
        self.task_store = TaskStore()
        self.audit_store = AuditStore()

        # Idempotency registry: key -> stored resource id.
        self._idempotency: Dict[str, str] = {}
        self._idem_lock = threading.Lock()

        # Services.
        self.audit_service = AuditService(self)
        self.definition_service = DefinitionService(self)
        self.authz = Authorizer(self)
        self.task_service = TaskService(self)
        self.workflow_service = WorkflowService(self)
        self.reminder_service = ReminderService(self)

        # Compiled LangGraph (built last; nodes capture this container).
        from app.graph.builder import build_graph

        self.graph = build_graph(self)

        # Seed definition v1.
        self.definition_service.seed_initial_definition()

    # -- idempotency helpers ------------------------------------------------ #
    def idempotency_get(self, key: Optional[str]) -> Optional[str]:
        if not key:
            return None
        with self._idem_lock:
            return self._idempotency.get(key)

    def idempotency_set(self, key: Optional[str], resource_id: str) -> None:
        if not key:
            return
        with self._idem_lock:
            self._idempotency[key] = resource_id


_container: Optional[Container] = None
_container_lock = threading.Lock()


def get_container() -> Container:
    global _container
    if _container is None:
        with _container_lock:
            if _container is None:
                _container = Container()
    return _container
