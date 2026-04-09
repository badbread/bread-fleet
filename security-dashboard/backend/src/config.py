"""Dashboard backend configuration.

Minimal for the MVP because the dashboard serves synthetic data and
has no external dependencies (no Fleet API calls, no Claude API). In
production, this would include Fleet API credentials and Postgres
connection settings for the historical snapshot store.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Bind address for uvicorn. Overridable for container deployments
    # where the port may differ from the default.
    host: str = "0.0.0.0"
    port: int = 8089

    # CORS origins allowed for standalone development. In the portal
    # deployment, nginx handles same-origin routing so CORS is moot.
    cors_origins: list[str] = [
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]

    model_config = {"env_prefix": "DASHBOARD_"}
