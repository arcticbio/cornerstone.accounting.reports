"""Runtime settings. Every environment variable the runner reads is documented here (SPEC §12).

Env prefix is ``CRR_``. Two variables are read without the prefix as a fallback, because they
follow their vendors' conventions and are already set that way in local shells and CI:
``ANTHROPIC_API_KEY`` and ``GOOGLE_SERVICE_ACCOUNT_B64``.

The classifier key is ``CRR_ANTHROPIC_API_KEY`` first. Claude Code on the web reserves the
unprefixed ``ANTHROPIC_API_KEY`` for its own account auth and strips it from the session
container, so a key set under that name alone never reaches the runner. See
``docs/SETUP-CREDENTIALS.md``.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ClassifierName = Literal["anthropic", "golden"]
RepositoryName = Literal["local", "gdrive"]
ExemplarPolicy = Literal["exclude_same_property", "any"]

# USD per million tokens. Overridable with CRR_PRICE_TABLE_JSON.
DEFAULT_PRICE_TABLE: dict[str, dict[str, float]] = {
    "claude-opus-5": {
        "input": 15.0,
        "cache_read": 1.5,
        "cache_write": 18.75,
        "output": 75.0,
    },
}


class Settings(BaseSettings):
    """Process configuration, read from the environment once per run."""

    model_config = SettingsConfigDict(
        env_prefix="CRR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- classifier -------------------------------------------------------------------
    anthropic_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("CRR_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"),
        description="Classifier key. Required for --classifier anthropic.",
    )
    model: str = Field(default="claude-opus-5", description="Classifier model id (D-09).")
    min_confidence: float = Field(default=0.85, ge=0.0, le=1.0)

    # --- preprocessing ----------------------------------------------------------------
    render_dpi: int = Field(default=150, gt=0)
    max_parallel_docs: int = Field(default=2, gt=0)

    # --- repository -------------------------------------------------------------------
    bundle_root: Path = Field(default=Path("data/bundle/2026-06"))
    repo: RepositoryName = Field(default="local")
    google_service_account_b64: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "CRR_GOOGLE_SERVICE_ACCOUNT_B64", "GOOGLE_SERVICE_ACCOUNT_B64"
        ),
        description="base64 of the service-account JSON, one line.",
    )
    gdrive_root_folder_id: str | None = Field(default=None)
    work_dir: Path = Field(default=Path("work"))

    # --- classification prompts and eval ----------------------------------------------
    exemplar_policy: ExemplarPolicy = Field(default="exclude_same_property")
    eval_min_page_accuracy: float = Field(default=0.98, ge=0.0, le=1.0)
    eval_min_boundary_f1: float = Field(default=0.98, ge=0.0, le=1.0)
    price_table_json: str | None = Field(default=None)

    @field_validator("price_table_json")
    @classmethod
    def _price_table_is_json(cls, v: str | None) -> str | None:
        if v is None:
            return None
        try:
            json.loads(v)
        except json.JSONDecodeError as exc:  # pragma: no cover - message is the point
            raise ValueError(f"CRR_PRICE_TABLE_JSON is not valid JSON: {exc}") from exc
        return v

    @property
    def has_classifier_key(self) -> bool:
        """True when --classifier anthropic can run."""
        return self.anthropic_api_key is not None

    @property
    def has_gdrive_credentials(self) -> bool:
        """True when --repo gdrive can run."""
        return (
            self.google_service_account_b64 is not None and self.gdrive_root_folder_id is not None
        )

    @property
    def price_table(self) -> dict[str, dict[str, float]]:
        """USD per million tokens, per model, with the env override applied."""
        if self.price_table_json is None:
            return DEFAULT_PRICE_TABLE
        parsed: dict[str, dict[str, float]] = json.loads(self.price_table_json)
        return parsed


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings for the life of the process."""
    return Settings()
