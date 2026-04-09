"""Runtime configuration loading.

Reads environment variables once at startup via pydantic-settings, then
exposes them as a Settings singleton the rest of the backend imports.
This is the pattern that scales: never read os.environ inline in
business logic, always go through a settings object so testing and
overrides have one place to hook into.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide runtime configuration.

    Every value is overridable via environment variables. The defaults
    here are tuned for the local Compose stack; production would
    override every one through the CI deploy pipeline.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Allow environment variables to override file values, which is
        # the expected behavior in a Compose stack where the file is
        # only consulted as a fallback.
        extra="ignore",
    )

    # Fleet REST API connection. Required.
    fleet_api_url: str = Field(
        ...,
        description="Base URL for Fleet's REST API, e.g. http://10.0.0.10:8080",
    )
    fleet_api_token: str = Field(
        ...,
        description="API token for the troubleshooter's Fleet service account",
    )

    # Claude API. Optional. If unset, the translator falls back to the
    # static dict in translator.py and never makes a network call.
    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic API key. Unset = use static fallback only",
    )
    anthropic_model: str = Field(
        default="claude-sonnet-4-5",
        description="Claude model to use for translations",
    )

    # Audit log location. Mounted as a Docker volume in the Compose
    # stack so the file survives container recreation.
    audit_log_path: Path = Field(
        default=Path("/data/troubleshooter.jsonl"),
        description="Path to the JSONL audit log file",
    )

    # CORS origin allowlist. The frontend container's URL.
    cors_origin: str = Field(
        default="http://localhost:5173",
        description="Allowed CORS origin for the frontend",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide Settings singleton.

    Cached via lru_cache so reads are free after the first call. Never
    instantiate Settings directly outside this function: tests should
    monkey-patch get_settings instead so the cache key matches.
    """
    return Settings()  # type: ignore[call-arg]
