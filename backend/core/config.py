"""Application settings, read from the environment.

PostgreSQL is the project's database. A SQLite fallback is kept only so the
suite and a first-run demo work on a machine with no server installed; it is
never the intended deployment target and the app logs loudly when it is in
use.
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- application ----------------------------------------------------
    app_name: str = "AyuDrishti"
    app_version: str = "1.0.0"
    debug: bool = False
    api_prefix: str = ""

    # ---- database -------------------------------------------------------
    # Example: postgresql+psycopg2://ayudrishti:password@localhost:5432/ayudrishti
    database_url: str = Field(
        default=f"sqlite:///{(ROOT_DIR / 'data' / 'ayudrishti.db').as_posix()}"
    )
    db_echo: bool = False

    # ---- authentication -------------------------------------------------
    # Generated per-process when unset so a fresh checkout runs, but that
    # invalidates every token on restart -- production must set this.
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    # ---- CORS -----------------------------------------------------------
    # Stored as a raw string, not a List, on purpose: pydantic-settings tries
    # to JSON-decode any list-typed env var *before* validators run, so a
    # human-friendly value like `CORS_ORIGINS=*` or a comma-separated list of
    # URLs would crash the settings loader. Keeping it a str and splitting in
    # `cors_origins_list` sidesteps that entirely.
    cors_origins: str = "*"

    # ---- pose pipeline --------------------------------------------------
    pose_rules_dir: str = str(ROOT_DIR / "data" / "pose_rules")
    pose_model_path: str = ""
    visibility_threshold: float = 0.5

    # ---- privacy --------------------------------------------------------
    # Off by default and deliberately so: the system is designed to store
    # derived metrics, never raw camera footage.
    store_raw_frames: bool = False
    retain_landmarks: bool = False

    # ---- yoga assistant (RAG over Groq) ----------------------------------
    # Empty by default: the assistant endpoint reports itself unconfigured
    # rather than failing confusingly when no key is set.
    groq_api_key: str = ""
    # Groq rotates its model lineup; check the current list at
    # https://console.groq.com/docs/models (or GET /openai/v1/models with your
    # key) and override via the GROQ_MODEL env var if this default is retired.
    groq_model: str = "openai/gpt-oss-120b"
    groq_api_base: str = "https://api.groq.com/openai/v1"
    knowledge_dir: str = str(ROOT_DIR / "data" / "knowledge")

    @property
    def cors_origins_list(self) -> List[str]:
        """CORS origins as a list, split from the comma-separated string."""
        return [v.strip() for v in self.cors_origins.split(",") if v.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgres")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
