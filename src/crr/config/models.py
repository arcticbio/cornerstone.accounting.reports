"""Typed views of the three YAML config formats (SPEC §4).

These models are the validation: `crr validate-config` loads the YAML through them and reports
what pydantic rejects, plus the cross-file rules that no single model can see.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from crr.resolve.address import Address, AddressError, parse_address

_STRICT = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

#: SPEC §4.4 — the controlled cross-manager vocabulary. Extend by amending that section.
SEMANTIC_TAGS: frozenset[str] = frozenset(
    {
        "balance_sheet",
        "income_statement",
        "budget_variance",
        "owner_statement",
        "rent_roll",
        "occupancy",
        "delinquency",
        "general_ledger",
        "trial_balance",
        "distribution_schedule",
        "narrative",
    }
)

Cardinality = Literal["one", "per_record"]
TextLayer = Literal["always", "never", "sometimes"]


class Fingerprint(BaseModel):
    model_config = _STRICT

    description: str
    footer_regex: str | None = None
    page_size_hint: str | None = None
    ocr_quality_note: str | None = None


class RecordScope(BaseModel):
    model_config = _STRICT

    description: str
    header_regex: str | None = None


class SectionDef(BaseModel):
    """One label in a schema's section vocabulary. The prose fields are the classifier's
    label definitions and are shipped to the model verbatim (SPEC §7.2)."""

    model_config = _STRICT

    id: str
    semantic: str
    cardinality: Cardinality
    #: Documentation and a soft sanity check. YAML writes bare numbers for single-page
    #: sections ("1") and ranges as strings ("1-2"), so both shapes are accepted.
    typical_pages: str | None = None
    optional: bool = False
    not_in_standard_export: bool = False
    title: str | None = None
    description: str = ""
    visual_cues: tuple[str, ...] = ()
    text_cues: tuple[str, ...] = ()
    footer_label: str | None = None
    continuation_note: str | None = None

    @field_validator("typical_pages", mode="before")
    @classmethod
    def _typical_pages_as_text(cls, v: object) -> object:
        return str(v) if isinstance(v, int) else v

    @field_validator("semantic")
    @classmethod
    def _known_semantic(cls, v: str) -> str:
        if v not in SEMANTIC_TAGS:
            raise ValueError(
                f"unknown semantic tag {v!r}; the controlled list is SPEC §4.4: "
                f"{', '.join(sorted(SEMANTIC_TAGS))}"
            )
        return v

    @model_validator(mode="after")
    def _has_cues(self) -> SectionDef:
        if not self.visual_cues and not self.text_cues:
            raise ValueError(f"section {self.id!r} needs at least one visual_cue or text_cue")
        return self

    @property
    def display_title(self) -> str:
        """`cash_flow_12_month` → "Cash Flow 12 Month", overridable with `title` (SPEC §6.5)."""
        return self.title or self.id.replace("_", " ").title()


class SourceSchema(BaseModel):
    """`config/schemas/<schema_id>.yaml` (SPEC §4.1)."""

    model_config = _STRICT

    schema_id: str
    version: int
    producer: str
    system: str
    text_layer: TextLayer
    fingerprint: Fingerprint
    record_scope: RecordScope | None = None
    sections: tuple[SectionDef, ...]

    @model_validator(mode="after")
    def _unique_ids_and_footer_labels(self) -> SourceSchema:
        ids = [s.id for s in self.sections]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"duplicate section id(s): {', '.join(duplicates)}")
        labels = [s.footer_label for s in self.sections if s.footer_label]
        dupe_labels = sorted({label for label in labels if labels.count(label) > 1})
        if dupe_labels:
            raise ValueError(
                f"duplicate footer_label(s) within schema {self.schema_id!r}: "
                f"{', '.join(dupe_labels)}"
            )
        return self

    @property
    def section_ids(self) -> frozenset[str]:
        return frozenset(s.id for s in self.sections)

    def section(self, section_id: str) -> SectionDef:
        for s in self.sections:
            if s.id == section_id:
                return s
        raise KeyError(f"schema {self.schema_id!r} has no section {section_id!r}")


class SourceAlias(BaseModel):
    """One entry in an output definition's `sources` map."""

    model_config = _STRICT

    schema_id: str = Field(alias="schema")
    role: str
    required: bool = True


class FlowLeaf(BaseModel):
    """A single addressed flow item."""

    model_config = _STRICT

    address: str
    bookmark: str | None = None
    required: bool = True
    order: Literal["source"] = "source"

    @property
    def parsed(self) -> Address:
        return parse_address(self.address)


class FlowGroup(BaseModel):
    """`for_each_record:` — its items are repeated once per property record, in record order."""

    model_config = _STRICT

    for_each_record: tuple[FlowLeaf, ...]

    @model_validator(mode="after")
    def _items_are_record_scoped(self) -> FlowGroup:
        if not self.for_each_record:
            raise ValueError("for_each_record must contain at least one flow item")
        for item in self.for_each_record:
            if "{record}" not in item.address:
                raise ValueError(
                    f"for_each_record item {item.address!r} must address '@{{record}}' (SPEC §4.2)"
                )
        return self


FlowItem = FlowLeaf | FlowGroup


class Transforms(BaseModel):
    model_config = _STRICT

    ocr_if_no_text: bool = False
    autorotate: bool = False
    add_bookmarks: bool = True


class OutputDefinition(BaseModel):
    """`config/outputs/<output_id>.yaml` (SPEC §4.2)."""

    model_config = _STRICT

    output_id: str
    version: int
    property_manager: str
    title_template: str
    sources: dict[str, SourceAlias]
    flow: tuple[FlowItem, ...]
    unmapped_policy: Literal["explicit_drop"] = "explicit_drop"
    drop: tuple[str, ...] = ()
    transforms: Transforms = Transforms()

    @model_validator(mode="after")
    def _addresses_parse_and_name_declared_sources(self) -> OutputDefinition:
        for address in self._all_addresses():
            try:
                parsed = parse_address(address)
            except AddressError as exc:
                raise ValueError(f"{address!r}: {exc}") from exc
            if parsed.source_alias not in self.sources:
                raise ValueError(
                    f"{address!r} names undeclared source alias {parsed.source_alias!r}; "
                    f"`sources` declares {', '.join(sorted(self.sources))}"
                )
        return self

    def _all_addresses(self) -> list[str]:
        out: list[str] = []
        for item in self.flow:
            if isinstance(item, FlowGroup):
                out.extend(leaf.address for leaf in item.for_each_record)
            else:
                out.append(item.address)
        out.extend(self.drop)
        return out

    @property
    def leaves(self) -> tuple[FlowLeaf, ...]:
        """Every flow leaf, flattened — for validation, not for resolution."""
        out: list[FlowLeaf] = []
        for item in self.flow:
            if isinstance(item, FlowGroup):
                out.extend(item.for_each_record)
            else:
                out.append(item)
        return tuple(out)

    def alias_for_role(self, role: str) -> str | None:
        for alias, source in self.sources.items():
            if source.role == role:
                return alias
        return None
