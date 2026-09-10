"""The build manifest (SPEC §10).

The manifest is the audit surface: what was built, from which bytes, by which classifier, with
which labels, and why it ended up where it did. It is written for every build, including a
failed one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from crr import __version__
from crr.models import BuildStatus, PageClassification, PlanItem, ResolvedSection, ReviewReason

MANIFEST_VERSION = 1

_STRICT = ConfigDict(extra="forbid")


class ConfigRef(BaseModel):
    model_config = _STRICT

    id: str
    version: int
    sha256: str


class ConfigBlock(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    #: `schema` shadows a BaseModel attribute, so the field is aliased on the wire.
    schema_ref: ConfigRef = Field(serialization_alias="schema", validation_alias="schema")
    output: ConfigRef
    properties_sha256: str


class PropertyBlock(BaseModel):
    model_config = _STRICT

    id: str
    name: str
    property_manager: str
    owning_entity: str


class ClassifierBlock(BaseModel):
    model_config = _STRICT

    name: str
    model: str | None = None
    prompt_version: str | None = None
    #: `temperature` is not sent to this model family (SPEC §7.2, QUESTIONS A-02); the effort
    #: level is what the run actually chose, so that is what is recorded.
    effort: str | None = None


class InputRef(BaseModel):
    model_config = _STRICT

    role: str
    file: str
    sha256: str
    pages: int
    has_text_layer: bool
    ocr_applied: bool = False
    ocr_version: str | None = None
    ocr_rotated_pages: bool | None = None


class DroppedRef(BaseModel):
    model_config = _STRICT

    section_id: str
    doc_role: str
    record_id: str | None = None
    pages: list[int]


class OutputRef(BaseModel):
    model_config = _STRICT

    file: str
    sha256: str
    pages: int


class TokenCounts(BaseModel):
    model_config = _STRICT

    input: int = 0
    cache_read: int = 0
    cache_write: int = 0
    output: int = 0


class CostBlock(BaseModel):
    model_config = _STRICT

    tokens: TokenCounts = TokenCounts()
    usd_estimate: float = 0.0
    api_calls: int = 0


class Timings(BaseModel):
    model_config = _STRICT

    fetch: int = 0
    preprocess: int = 0
    classify: int = 0
    compose: int = 0
    publish: int = 0


class BuildManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    manifest_version: Literal[1] = 1
    runner_version: str = __version__
    built_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: BuildStatus
    review_reasons: list[ReviewReason] = Field(default_factory=list)
    property: PropertyBlock
    period: str
    config: ConfigBlock
    classifier: ClassifierBlock
    inputs: list[InputRef] = Field(default_factory=list)
    classifications: list[PageClassification] = Field(default_factory=list)
    sections: list[ResolvedSection] = Field(default_factory=list)
    dropped: list[DroppedRef] = Field(default_factory=list)
    plan: list[PlanItem] = Field(default_factory=list)
    output: OutputRef | None = None
    cost: CostBlock = CostBlock()
    timings_ms: Timings = Timings()
    #: Set when the build failed with an exception rather than a review reason (SPEC §6.8).
    error: str | None = None
