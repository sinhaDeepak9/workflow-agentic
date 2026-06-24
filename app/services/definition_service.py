"""Workflow definition service: versioning, schema validation, migration check."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

from app.errors import ValidationFailure
from app.models.domain import WorkflowDefinition
from app.models.enums import AuditEventType, TaskType

if TYPE_CHECKING:
    from app.container import Container


# Process-level variable registry (Read.md).
_INITIAL_VARIABLES: List[str] = [
    "reportType", "instanceDescription", "reportOwners", "targetUser", "mqdUser",
    "healthPlanName", "reportingPeriod", "dueDate", "reviewer", "supervisor",
    "isEscalated", "isApproved", "mcoEmail", "mcoUser", "slaDate", "reminder1",
    "reminder2", "userList", "decision", "slaSuper", "resubmissionRequiredBy",
    "processActivationTime", "internalSubmissionId", "slaDays", "notification",
]

_INITIAL_TASK_SCHEMAS: Dict[str, Dict[str, Any]] = {
    TaskType.REPORT_SUBMISSION_REVIEW.value: {
        "version": 1,
        "required": ["isApproved", "decision"],
        "optional": ["isEscalated", "resubmissionRequiredBy", "comment"],
    },
    TaskType.SUPERVISOR_REVIEW.value: {
        "version": 1,
        "required": ["isApproved", "decision"],
        "optional": ["comment"],
    },
}

_INITIAL_PROMOTION: Dict[str, List[str]] = {
    TaskType.REPORT_SUBMISSION_REVIEW.value: [
        "isEscalated", "isApproved", "decision", "resubmissionRequiredBy",
    ],
    TaskType.SUPERVISOR_REVIEW.value: ["isApproved", "decision"],
}


class DefinitionService:
    def __init__(self, container: "Container") -> None:
        self._c = container

    # -- seeding ----------------------------------------------------------- #
    def seed_initial_definition(self) -> None:
        wf_type = self._c.settings.workflow_type
        if self._c.definition_store.latest_version(wf_type) is not None:
            return
        self._c.definition_store.put(
            WorkflowDefinition(
                workflow_type=wf_type,
                version=1,
                state_schema_version=1,
                variable_registry=list(_INITIAL_VARIABLES),
                task_schemas={k: dict(v) for k, v in _INITIAL_TASK_SCHEMAS.items()},
                output_promotion={k: list(v) for k, v in _INITIAL_PROMOTION.items()},
                published_by="system",
            )
        )

    # -- reads ------------------------------------------------------------- #
    def get(self, workflow_type: str, version: int) -> WorkflowDefinition:
        return self._c.definition_store.get(workflow_type, version)

    def list_versions(self, workflow_type: str) -> List[WorkflowDefinition]:
        return self._c.definition_store.list_versions(workflow_type)

    def get_for_instance(self, workflow_id: str) -> WorkflowDefinition:
        instance = self._c.instance_store.get(workflow_id)
        return self._c.definition_store.get(
            instance.workflow_type, instance.definition_version
        )

    # -- publish ----------------------------------------------------------- #
    def publish(
        self,
        workflow_type: str,
        actor: str,
        state_schema_version: int,
        variable_registry: List[str],
        task_schemas: Dict[str, Dict[str, Any]],
        output_promotion: Dict[str, List[str]],
        deprecated_variables: List[str],
    ) -> WorkflowDefinition:
        self._c.authz.require_publish_definition(actor)
        latest = self._c.definition_store.latest_version(workflow_type) or 0
        definition = WorkflowDefinition(
            workflow_type=workflow_type,
            version=latest + 1,
            state_schema_version=state_schema_version,
            variable_registry=list(variable_registry),
            task_schemas=task_schemas,
            output_promotion=output_promotion,
            deprecated_variables=list(deprecated_variables),
            published_by=actor,
        )
        self._c.definition_store.put(definition)
        return definition

    def validate_migration(
        self, workflow_type: str, actor: str, from_version: int, to_version: int
    ) -> Dict[str, Any]:
        """Compare two versions and report whether migration is non-destructive."""
        self._c.authz.require_validate_migration(actor)
        old = self._c.definition_store.get(workflow_type, from_version)
        new = self._c.definition_store.get(workflow_type, to_version)

        removed = [v for v in old.variable_registry if v not in new.variable_registry]
        added = [v for v in new.variable_registry if v not in old.variable_registry]
        # Removals that were not first deprecated are unsafe.
        unsafe_removals = [v for v in removed if v not in new.deprecated_variables]

        return {
            "workflowType": workflow_type,
            "fromVersion": from_version,
            "toVersion": to_version,
            "addedVariables": added,
            "removedVariables": removed,
            "unsafeRemovals": unsafe_removals,
            "compatible": not unsafe_removals,
        }

    # -- validation helpers ------------------------------------------------ #
    def validate_state_updates(self, workflow_id: str, updates: Dict[str, Any]) -> None:
        definition = self.get_for_instance(workflow_id)
        unknown = [k for k in updates if k not in definition.variable_registry]
        if unknown:
            raise ValidationFailure(
                f"Unknown variables for definition v{definition.version}: {unknown}"
            )

    def validate_task_output(
        self, workflow_id: str, task_type: str, output: Dict[str, Any]
    ) -> None:
        definition = self.get_for_instance(workflow_id)
        schema = definition.task_schemas.get(task_type)
        if schema is None:
            raise ValidationFailure(f"No task schema for '{task_type}'")
        missing = [k for k in schema["required"] if k not in output]
        if missing:
            raise ValidationFailure(f"Missing required output fields: {missing}")
        allowed = set(schema["required"]) | set(schema.get("optional", []))
        unknown = [k for k in output if k not in allowed]
        if unknown:
            raise ValidationFailure(f"Unexpected output fields: {unknown}")

    def filter_promotion(
        self, workflow_id: str, task_type: str, output: Dict[str, Any]
    ) -> Dict[str, Any]:
        definition = self.get_for_instance(workflow_id)
        allowed = definition.output_promotion.get(task_type, [])
        return {k: output[k] for k in allowed if k in output}
