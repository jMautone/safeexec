"""Typed application settings loaded from the environment."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SAFEEXEC_", env_file=".env", extra="ignore")

    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://safeexec:safeexec@localhost:5432/safeexec"

    python_image: str = "python:3.13-slim"
    node_image: str = "node:22-slim"
    sandbox_runtime: str | None = None
    sandbox_user: str = "65534:65534"
    sandbox_workdir_base: str | None = None
    docker_timeout_seconds: float = 10.0

    default_timeout_ms: int = 5_000
    max_timeout_ms: int = 30_000
    default_memory_mb: int = 128
    max_memory_mb: int = 512
    default_cpus: float = 0.5
    max_cpus: float = 2.0
    default_max_output_bytes: int = 64 * 1024
    max_max_output_bytes: int = 1024 * 1024

    max_concurrent_executions: int = 4


@lru_cache
def get_settings() -> Settings:
    return Settings()
