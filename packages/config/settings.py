"""Application settings — every tunable lives here.

Loaded from environment + .env file. No hardcoded constants buried in
function bodies. Override anything via .env or the environment.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Neo4j (LHS KG store)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "regulai-dev-password"
    neo4j_database: str = "neo4j"

    # OpenAI (Sentinel agent)
    openai_api_key: str | None = None
    openai_model: str = "gpt-5"

    # Confidence thresholds (overridable)
    sentinel_confidence_threshold: float = 0.75
    bridge_confidence_threshold: float = 0.85

    # Coverage check rigor (advisory vs enforced)
    coverage_advisory_only: bool = True

    # Materialization output directory (LHS writes JSON here; RHS will swap to Snowflake)
    materialized_dir: Path = Path("materialized")


settings = Settings()
