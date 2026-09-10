"""The domain model (SPEC §3).

Everything here is a pure data carrier: no I/O, no config lookups. Models are frozen so a
stage cannot mutate an earlier stage's output, and forbid extra keys so a renamed field in a
manifest or a golden file fails loudly instead of being silently dropped.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PeriodId = str  # "2026-06"

_MODEL_CONFIG = ConfigDict(extra="forbid", frozen=True)


class Orientation(StrEnum):
    """How the page *content* is turned, not how the page box is set."""

    UPRIGHT = "upright"
    ROT_90_CW = "rotated_90_cw"
    ROT_90_CCW = "rotated_90_ccw"
    ROT_180 = "rotated_180"

    @property
    def correcting_rotation(self) -> int:
        """Clockwise degrees that bring this content upright (SPEC §6.5)."""
        return {
            Orientation.UPRIGHT: 0,
            Orientation.ROT_90_CW: 270,
            Orientation.ROT_90_CCW: 90,
            Orientation.ROT_180: 180,
        }[self]


class BuildStatus(StrEnum):
    BUILT = "built"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class PropertyRecord(BaseModel):
    """One property record inside a PM system, under a single owning entity."""

    model_config = _MODEL_CONFIG

    id: str
    pm_name: str | None = None


class Property(BaseModel):
    model_config = _MODEL_CONFIG

    id: str
    name: str
    folder: str
    property_manager: str
    owning_entity: str
    records: tuple[PropertyRecord, ...] = ()

    @field_validator("records")
    @classmethod
    def _records_unique(cls, v: tuple[PropertyRecord, ...]) -> tuple[PropertyRecord, ...]:
        ids = [r.id for r in v]
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate record ids: {ids}")
        return v

    @property
    def is_single_record(self) -> bool:
        return len(self.records) == 1

    def record(self, record_id: str) -> PropertyRecord:
        for r in self.records:
            if r.id == record_id:
                return r
        raise KeyError(f"{self.id} has no record {record_id!r}")


class SourceDocument(BaseModel):
    """One input file, after fetch and preprocessing."""

    model_config = _MODEL_CONFIG

    role: str
    schema_id: str
    path: Path
    sha256: str
    page_count: int = Field(ge=0)
    has_text_layer: bool
    ocr_applied: bool = False
    ocr_version: str | None = None
    ocr_rotated_pages: bool | None = None


class PageClassification(BaseModel):
    """One page's label. The classifier's entire output surface (D-01)."""

    model_config = _MODEL_CONFIG

    doc_role: str
    page: int = Field(ge=1)
    section_id: str
    is_continuation: bool
    record_qualifier: str | None
    orientation: Orientation
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str
    footer_label: str | None = None
    footer_agrees: bool | None = None
    classifier: str

    UNKNOWN: ClassVar[str] = "unknown"

    @property
    def is_unknown(self) -> bool:
        return self.section_id == "unknown"


class ResolvedSection(BaseModel):
    """A run of consecutive pages the segmenter grouped into one instance of a section."""

    model_config = _MODEL_CONFIG

    doc_role: str
    section_id: str
    record_id: str | None
    pages: tuple[int, ...]
    orientation_fixes: dict[int, Orientation] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _pages_contiguous(self) -> ResolvedSection:
        if not self.pages:
            raise ValueError("a resolved section must cover at least one page")
        if list(self.pages) != list(range(self.pages[0], self.pages[0] + len(self.pages))):
            raise ValueError(f"pages must be contiguous and ascending: {self.pages}")
        stray = set(self.orientation_fixes) - set(self.pages)
        if stray:
            raise ValueError(f"orientation_fixes name pages outside the section: {sorted(stray)}")
        return self

    @property
    def first_page(self) -> int:
        return self.pages[0]


class PlanItem(BaseModel):
    """One output page: where it comes from and what happens to it."""

    model_config = _MODEL_CONFIG

    output_page: int = Field(ge=1)
    doc_role: str
    source_page: int = Field(ge=1)
    section_id: str
    record_id: str | None
    transforms: tuple[str, ...] = ("copy",)
    bookmark: str | None = None


class ReviewReason(BaseModel):
    """One entry in the review gate's verdict (SPEC §6.8)."""

    model_config = _MODEL_CONFIG

    code: str
    doc_role: str | None = None
    page: int | None = None
    detail: str = ""
