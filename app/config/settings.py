"""Application configuration loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed settings sourced from environment variables / .env.

    See `.env.example` for the documented set of variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_name: str = "HawaiReportApproval"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # Workflow runtime
    workflow_type: str = "HawaiReportApproval"
    default_definition_version: int = 1

    # Reminder scheduler
    reminder_enabled: bool = True
    reminder_interval_seconds: int = 3600
    reminder_max_count: int = 3

    # Security / RBAC
    auth_enabled: bool = True
    admin_users: str = "admin.user"

    # Persistence
    store_backend: str = "memory"

    @property
    def admin_user_set(self) -> List[str]:
        return [u.strip() for u in self.admin_users.split(",") if u.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
