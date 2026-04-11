"""Application settings — Pydantic BaseSettings.

Reads from environment variables, .env file, or defaults.
All thresholds come from config/config.yaml, not here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    db_url: str = Field(
        default="postgresql://localhost:5433/nifty50",
        description="PostgreSQL connection string",
    )

    # Ingestion
    nse_base_url: str = Field(
        default="https://archives.nseindia.com",
        description="NSE archives base URL",
    )
    nse_user_agent: str = Field(
        default="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        description="User-Agent header for NSE requests",
    )
    backfill_days: int = Field(
        default=252,
        description="Number of trading days to backfill (~1 year)",
    )
    local_data_dir: Optional[Path] = Field(
        default=None,
        description="Local directory for CSV fallback. If set, ingestion reads from here instead of NSE.",
    )

    # Rate limiting
    request_delay_seconds: float = Field(
        default=2.0,
        description="Minimum delay between NSE requests (seconds)",
    )
    max_retries: int = Field(
        default=3,
        description="Max retries before circuit breaker trips",
    )
    backoff_factor: float = Field(
        default=2.0,
        description="Exponential backoff multiplier",
    )

    # Paths
    project_root: Path = Field(
        default=Path(__file__).parent.parent,
        description="Project root directory",
    )

    @property
    def config_yaml_path(self) -> Path:
        return self.project_root / "config" / "config.yaml"

    @property
    def watchlist_path(self) -> Path:
        return self.project_root / "watchlist.yaml"


settings = Settings()
