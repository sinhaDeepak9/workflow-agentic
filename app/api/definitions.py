"""Workflow definition REST endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from app.api import serializers
from app.container import get_container
from app.models.api import PublishDefinitionRequest, ValidateMigrationRequest

router = APIRouter(prefix="/api/workflow-definitions", tags=["definitions"])


@router.get("/{workflow_type}/versions")
def list_versions(workflow_type: str):
    c = get_container()
    return [serializers.definition_view(d) for d in c.definition_service.list_versions(workflow_type)]


@router.get("/{workflow_type}/versions/{version}")
def get_version(workflow_type: str, version: int):
    definition = get_container().definition_service.get(workflow_type, version)
    return serializers.definition_view(definition)


@router.post("/{workflow_type}/versions")
def publish_version(workflow_type: str, body: PublishDefinitionRequest):
    definition = get_container().definition_service.publish(
        workflow_type=workflow_type,
        actor=body.actor,
        state_schema_version=body.state_schema_version,
        variable_registry=body.variable_registry,
        task_schemas=body.task_schemas,
        output_promotion=body.output_promotion,
        deprecated_variables=body.deprecated_variables,
    )
    return serializers.definition_view(definition)


@router.post("/{workflow_type}/versions/{version}/validate-migration")
def validate_migration(workflow_type: str, version: int, body: ValidateMigrationRequest):
    return get_container().definition_service.validate_migration(
        workflow_type=workflow_type, actor=body.actor,
        from_version=body.from_version, to_version=version,
    )
