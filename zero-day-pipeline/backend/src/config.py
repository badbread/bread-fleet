"""Zero-Day Response Pipeline configuration.

Follows the same pydantic-settings pattern as the Compliance
Troubleshooter. Every setting is overridable via environment
variables. The .env file is a convenience for local development;
the portal docker-compose injects them directly.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Fleet REST API connection. Required for deploying generated
    # policies and checking host results.
    fleet_api_url: str = Field(description="Fleet server URL, e.g. https://fleet.lan:8080")
    fleet_api_token: str = Field(description="Fleet API token for policy management")

    # CISA KEV feed. The default URL is the official JSON catalog.
    kev_feed_url: str = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    kev_cache_ttl_seconds: int = Field(
        default=3600,
        description="Cache the KEV feed in memory for this many seconds",
    )

    # Claude API for the AI-assisted mapper fallback. Optional: if
    # blank, the mapper uses only the curated registry and marks
    # unmatched entries as unmappable.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"

    # Audit log path. Mounted as a Docker volume so it survives
    # container recreation.
    audit_log_path: Path = Path("/data/zero-day.jsonl")

    # CORS origin for standalone development. In the portal
    # deployment, nginx handles same-origin routing so CORS is moot.
    cors_origins: list[str] = [
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    ]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
