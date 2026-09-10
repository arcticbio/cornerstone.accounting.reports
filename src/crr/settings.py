"""Runtime settings. Every environment variable the runner reads is declared here (SPEC §12)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RepoKind = Literal["local", "gdrive"]
ExemplarPolicy = Literal["exclude_same_property", "any"]


class ModelPrice(BaseModel):
    """USD per million tokens for one model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input: float
    cache_read: float
    cache_write: float
    output: float


#: Built-in list price estimate, USD per MTok. Override with CRR_PRICE_TABLE_JSON when the
#: published price list moves; the manifest records the estimate, never a billed amount.
#: `cache_write` is the 1-hour-TTL rate (2x base input) because that is the TTL the classifier
#: asks for; cache reads are 0.1x base input.
DEFAULT_PRICE_TABLE: dict[str, ModelPrice] = {
    "claude-opus-5": ModelPrice(input=5.0, cache_read=0.5, cache_write=10.0, output=25.0),
    "claude-sonnet-5": ModelPrice(input=2.0, cache_read=0.2, cache_write=4.0, output=10.0),
    "claude-haiku-4-5": ModelPrice(input=1.0, cache_read=0.1, cache_write=2.0, output=5.0),
    "claude-haiku-4-5-20251001": ModelPrice(input=1.0, cache_read=0.1, cache_write=2.0, output=5.0),
}


class Settings(BaseSettings):
    """All configuration for one run. Constructed once and passed down; never read from globals."""

    model_config = SettingsConfigDict(
        env_prefix="CRR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- classifier ------------------------------------------------------------------
    #: Read from CRR_ANTHROPIC_API_KEY first. Claude Code on the web reserves the unprefixed
    #: ANTHROPIC_API_KEY for its own account auth and strips it from the session container, so a
    #: key set only under that name never reaches the runner. The unprefixed name stays as a
    #: fallback for local shells, GitHub Actions and Azure. See docs/SETUP-CREDENTIALS.md.
    anthropic_api_key: Annotated[
        str | None,
        Field(validation_alias=AliasChoices("CRR_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY")),
    ] = None
    model: str = "claude-opus-5"
    min_confidence: float = 0.85
    max_parallel_docs: int = 2
    #: `output_config.effort` for the classifier. Page classification is a perceptual call on
    #: a single image, not a reasoning problem; `low` is both cheaper and no less accurate here.
    classifier_effort: Literal["low", "medium", "high", "xhigh", "max"] = "low"
    exemplar_policy: ExemplarPolicy = "exclude_same_property"

    # -- preprocessing ---------------------------------------------------------------
    render_dpi: int = 150
    render_max_edge_px: int = 1568
    page_text_chars: int = 6_000

    # -- repositories ----------------------------------------------------------------
    repo: RepoKind = "local"
    bundle_root: Path = Path("data/bundle/2026-06")
    work_dir: Path = Path("work")
    #: Where the local repository publishes. Defaults to `<work_dir>/published`, which mirrors
    #: the repository layout without writing into `bundle_root` — the June bundle is a
    #: read-only fixture (D-08). Set it to `bundle_root` to publish beside the inputs.
    publish_root: Path | None = None
    google_service_account_b64: Annotated[
        str | None, Field(validation_alias="GOOGLE_SERVICE_ACCOUNT_B64")
    ] = None
    gdrive_root_folder_id: str | None = None

    # -- config tree -----------------------------------------------------------------
    config_dir: Path = Path("config")
    golden_dir: Path = Path("eval/golden")

    # -- eval gates ------------------------------------------------------------------
    eval_min_page_accuracy: float = 0.98
    eval_min_boundary_f1: float = 0.98

    # -- cost ------------------------------------------------------------------------
    price_table_json: str | None = None

    @field_validator("min_confidence", "eval_min_page_accuracy", "eval_min_boundary_f1")
    @classmethod
    def _unit_interval(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("must be between 0 and 1")
        return v

    @property
    def local_publish_root(self) -> Path:
        return self.publish_root if self.publish_root is not None else self.work_dir / "published"

    @property
    def price_table(self) -> dict[str, ModelPrice]:
        """The built-in price table, overlaid with CRR_PRICE_TABLE_JSON when set."""
        table = dict(DEFAULT_PRICE_TABLE)
        if self.price_table_json:
            raw = json.loads(self.price_table_json)
            for model, prices in raw.items():
                table[model] = ModelPrice.model_validate(prices)
        return table
