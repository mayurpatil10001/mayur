"""
backend/core/config.py
======================
Pydantic Settings for the Sierra Chart Trade Optimization Platform.
All configuration is read from environment variables / .env file.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────────────────
    APP_NAME: str = "SC Trade Optimization Platform"
    APP_VERSION: str = "2.0.0"
    ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False

    # ── Server ────────────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    RELOAD: bool = True  # Auto-disabled in production via ENV check

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./data/trading_platform.db",
        description="SQLAlchemy async database URL. "
        "Supports SQLite (default) and PostgreSQL (asyncpg driver).",
    )
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False  # Log all SQL statements (dev only)

    # ── Data Paths ────────────────────────────────────────────────────────────
    DATASET_PATH: Path = Field(
        default=Path("./dataset"),
        description="Directory containing Sierra Chart binary .data files.",
    )
    DATA_PATH: Path = Field(
        default=Path("./data"),
        description="Writable data directory for DB, logs, exports.",
    )

    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = Field(
        default="change-me-in-production-use-32-random-bytes",
        min_length=32,
    )
    API_KEY: str = Field(
        default="",
        description="Optional API key for external clients. Empty = disabled.",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        description="Comma-separated list of allowed CORS origins.",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_FORMAT: Literal["json", "text"] = "json"
    LOG_FILE: Path | None = None

    # ── Statistical Analysis ──────────────────────────────────────────────────
    BH_FDR_ALPHA: float = Field(
        default=0.05,
        ge=0.001,
        le=0.2,
        description="Benjamini-Hochberg FDR significance threshold.",
    )
    MIN_TRADES_FOR_PROMOTION: int = Field(
        default=30,
        ge=5,
        description="Minimum trades in a time slot to be eligible for BH-FDR promotion.",
    )
    PERMUTATION_N: int = Field(
        default=1000,
        ge=100,
        description="Number of permutations for permutation tests.",
    )

    # ── Walk-Forward ──────────────────────────────────────────────────────────
    WF_IN_SAMPLE_DAYS: int = 252   # 1 trading year
    WF_OUT_OF_SAMPLE_DAYS: int = 63  # 1 quarter
    WF_STEP_DAYS: int = 63

    # ── Monte Carlo ───────────────────────────────────────────────────────────
    MC_SIMULATIONS: int = Field(default=10_000, ge=1_000, le=100_000)
    MC_RUIN_THRESHOLD: float = Field(
        default=0.50,
        description="Drawdown fraction at which ruin is declared (0.5 = 50%).",
    )

    # ── Import Pipeline ───────────────────────────────────────────────────────
    IMPORT_MAX_WORKERS: int = Field(
        default=4,
        description="ProcessPoolExecutor workers for parallel file parsing.",
    )
    IMPORT_DEDUP_WINDOW_MS: int = 250   # Per-file dedup bucket in milliseconds
    IMPORT_GLOBAL_DEDUP_S: int = 2     # Cross-file dedup bucket in seconds
    GHOST_NOTE_COVERAGE_THRESHOLD: float = 0.25  # Bypass ghost filter below this

    # ── Caching ───────────────────────────────────────────────────────────────
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for Celery and response caching (Phase 5).",
    )
    CACHE_TTL_SECONDS: int = 300  # 5 minutes

    # ── External APIs ─────────────────────────────────────────────────────────
    ALPHA_VANTAGE_KEY: str = ""
    QUANDL_KEY: str = ""

    # ── Sentry ────────────────────────────────────────────────────────────────
    SENTRY_DSN: str = ""

    @field_validator("DATASET_PATH", "DATA_PATH", mode="before")
    @classmethod
    def resolve_path(cls, v: str | Path) -> Path:
        return Path(v).resolve()

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.DATABASE_URL.lower()

    @property
    def is_postgres(self) -> bool:
        return "postgresql" in self.DATABASE_URL.lower() or "postgres" in self.DATABASE_URL.lower()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return singleton Settings instance (cached after first call)."""
    return Settings()


# Module-level alias for convenience
settings = get_settings()
