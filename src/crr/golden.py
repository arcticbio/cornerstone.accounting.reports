"""Reading `eval/golden/<pm>/<property>.json`.

The golden files are the ground truth for `crr eval` (SPEC §8), the source of the classifier's
few-shot exemplars (SPEC §7.2) and — through `GoldenClassifier` — the fixture that lets the
whole pipeline run without an API key. One loader serves all three.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from crr.models import Orientation, PageClassification, Property, PropertyRecord

GOLDEN_CLASSIFIER_NAME = "golden"

_STRICT = ConfigDict(extra="forbid", frozen=True)


def _drop_underscored(data: Any) -> Any:
    """Golden files carry `_path_note` for human readers; keys starting with `_` are
    annotations, not data."""
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if not str(k).startswith("_")}
    return data


class GoldenPage(BaseModel):
    model_config = _STRICT

    page: int
    section: str
    continuation: bool
    record: str | None = None
    orientation: Orientation | None = None


class GoldenDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    role: str
    schema_id: str
    file: str
    pages: tuple[GoldenPage, ...]

    @model_validator(mode="before")
    @classmethod
    def _rename_schema(cls, data: Any) -> Any:
        data = _drop_underscored(data)
        if isinstance(data, dict) and "schema" in data:
            data = dict(data)
            data["schema_id"] = data.pop("schema")
        return data


class ExpectedPage(BaseModel):
    """One entry of the frozen `expected_output` sequence (SPEC §9.5)."""

    model_config = _STRICT

    output_page: int
    doc_role: str
    section: str
    record: str | None
    source_page: int


class GoldenProperty(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    property_id: str
    #: The display name. Aliased because `property` shadows the builtin inside the class body.
    property_name: str = Field(alias="property")
    property_manager: str
    pm_id: str
    period: str
    schema_id: str
    output_definition: str
    records: tuple[PropertyRecord, ...]
    expected_output_page_count: int
    expected_output: tuple[ExpectedPage, ...] | None = None
    documents: tuple[GoldenDocument, ...]
    notes: tuple[str, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def _rename_schema(cls, data: Any) -> Any:
        data = _drop_underscored(data)
        if isinstance(data, dict) and "schema" in data:
            data = dict(data)
            data["schema_id"] = data.pop("schema")
        return data

    def document(self, role: str) -> GoldenDocument:
        for doc in self.documents:
            if doc.role == role:
                return doc
        raise KeyError(f"{self.property_id} has no document with role {role!r}")

    @property
    def roles(self) -> tuple[str, ...]:
        return tuple(doc.role for doc in self.documents)

    def record_name(self, record_id: str | None) -> str | None:
        if record_id is None:
            return None
        for record in self.records:
            if record.id == record_id:
                return record.pm_name
        return None

    def classifications(self, role: str) -> list[PageClassification]:
        """Golden labels as `PageClassification`s.

        `record` in a golden file is the *mapped* record id; the classifier's contract is the
        raw `record_qualifier`, so it is rendered back to the record's `pm_name`. The segmenter
        then maps it forward again, which keeps that mapping under test on every golden build.
        """
        doc = self.document(role)
        return [
            PageClassification(
                doc_role=role,
                page=page.page,
                section_id=page.section,
                is_continuation=page.continuation,
                record_qualifier=self.record_name(page.record),
                orientation=page.orientation or Orientation.UPRIGHT,
                confidence=1.0,
                evidence="golden label",
                classifier=GOLDEN_CLASSIFIER_NAME,
            )
            for page in doc.pages
        ]

    def to_property(self, folder: str, owning_entity: str) -> Property:
        """A `Property` built from the golden file alone — for tests that must not depend on
        `config/properties.yaml`."""
        return Property(
            id=self.property_id,
            name=self.property_name,
            folder=folder,
            property_manager=self.pm_id,
            owning_entity=owning_entity,
            records=self.records,
        )


def load_golden(path: Path) -> GoldenProperty:
    return GoldenProperty.model_validate(json.loads(path.read_text()))


def load_all_golden(golden_dir: Path) -> dict[str, GoldenProperty]:
    """property_id → golden labels, for every file under `golden_dir`."""
    out: dict[str, GoldenProperty] = {}
    for path in sorted(golden_dir.glob("*/*.json")):
        golden = load_golden(path)
        out[golden.property_id] = golden
    return out


def write_golden(path: Path, golden: GoldenProperty) -> None:
    """Write a golden file back, preserving the on-disk key spelling."""
    data = golden.model_dump(mode="json", by_alias=True, exclude_none=False)
    data["schema"] = data.pop("schema_id")
    documents = []
    for doc in data["documents"]:
        for page in doc["pages"]:
            if page.get("orientation") is None:
                page.pop("orientation", None)
        documents.append(
            {
                "role": doc["role"],
                "schema": doc["schema_id"],
                "file": doc["file"],
                "pages": doc["pages"],
            }
        )
    data["documents"] = documents
    ordered = {
        "property_id": data["property_id"],
        "property": data["property"],
        "property_manager": data["property_manager"],
        "pm_id": data["pm_id"],
        "period": data["period"],
        "schema": data["schema"],
        "output_definition": data["output_definition"],
        "records": data["records"],
        "expected_output_page_count": data["expected_output_page_count"],
        "expected_output": data["expected_output"],
        "documents": data["documents"],
        "notes": data["notes"],
        "_path_note": (
            "Paths are relative to settings.bundle_root (default: data/bundle/2026-06)."
        ),
    }
    path.write_text(json.dumps(ordered, indent=2) + "\n")
