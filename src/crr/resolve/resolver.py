"""Resolve an output definition against what the classifier found (SPEC §5, §6.5).

Input: the sections each document yielded, the output definition, the property.
Output: an ordered `PlanItem[]` — one entry per output page — plus the pages that were
explicitly dropped and the reasons the review gate must weigh. Pure function: no I/O.

D-11: every source page ends up in the plan, in the dropped set, or in a review reason.
`unaccounted_pages` is what proves it, and the invariant test in SPEC §9.1 asserts it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from crr.config.models import FlowGroup, FlowLeaf, OutputDefinition, SourceSchema
from crr.log import get_logger
from crr.models import PlanItem, Property, ResolvedSection, ReviewReason
from crr.resolve.address import Address, parse_address
from crr.segment.segmenter import Segmentation

log = get_logger(__name__)


class ResolveError(Exception):
    """The output definition cannot be resolved at all (a bug in config that validation
    should have caught). Distinct from a review reason, which is a data problem."""


@dataclass(frozen=True)
class DroppedSection:
    section_id: str
    doc_role: str
    record_id: str | None
    pages: tuple[int, ...]


@dataclass
class ResolveResult:
    plan: tuple[PlanItem, ...] = ()
    dropped: tuple[DroppedSection, ...] = ()
    reasons: tuple[ReviewReason, ...] = ()
    #: doc_role -> pages that reached neither the plan, the drop list nor a review reason.
    unaccounted_pages: dict[str, tuple[int, ...]] = field(default_factory=dict)

    @property
    def page_count(self) -> int:
        return len(self.plan)


def _humanise(section_id: str, schema: SourceSchema | None) -> str:
    if schema is not None and section_id in schema.section_ids:
        return schema.section(section_id).display_title
    return section_id.replace("_", " ").title()


def _render_bookmark(
    template: str | None,
    *,
    section_title: str,
    record_name: str | None,
    prop: Property,
    period_label: str,
) -> str | None:
    """Render a bookmark template. On a single-record property the ` - {record_name}` suffix
    is dropped entirely rather than rendered empty (SPEC §6.5)."""
    if template is None:
        return None
    text = template
    if record_name is None and "{record_name}" in text:
        text = text.replace(" - {record_name}", "").replace("{record_name}", "").strip(" -")
    return text.format(
        section_title=section_title,
        record_name=record_name or "",
        property=prop.name,
        period_label=period_label,
    )


class _Resolver:
    def __init__(
        self,
        output: OutputDefinition,
        prop: Property,
        segments: dict[str, Segmentation],
        schemas: dict[str, SourceSchema],
        period_label: str,
        present_roles: set[str] | None = None,
    ) -> None:
        self.output = output
        self.prop = prop
        self.segments = segments
        self.schemas = schemas
        self.period_label = period_label
        self.present_roles = present_roles
        self.plan: list[PlanItem] = []
        self.reasons: list[ReviewReason] = []
        self.consumed: set[tuple[str, str, str | None, int]] = set()

    # -- helpers ---------------------------------------------------------------------
    def _role(self, alias: str) -> str:
        source = self.output.sources.get(alias)
        if source is None:
            raise ResolveError(f"undeclared source alias {alias!r}")
        return source.role

    def _schema_for(self, alias: str) -> SourceSchema | None:
        source = self.output.sources.get(alias)
        return self.schemas.get(source.schema_id) if source else None

    def _sections_for(self, alias: str) -> tuple[ResolvedSection, ...]:
        role = self._role(alias)
        segmentation = self.segments.get(role)
        return segmentation.sections if segmentation else ()

    def _role_is_present(self, alias: str) -> bool:
        role = self._role(alias)
        if self.present_roles is not None:
            return role in self.present_roles
        return role in self.segments

    def _key(self, section: ResolvedSection) -> tuple[str, str, str | None]:
        return (section.doc_role, section.section_id, section.record_id)

    def _emit(self, section: ResolvedSection, bookmark: str | None) -> None:
        for offset, source_page in enumerate(section.pages):
            transforms = ["copy"]
            orientation = section.orientation_fixes.get(source_page)
            if orientation is not None and self.output.transforms.autorotate:
                transforms.append(f"rotate:{orientation.correcting_rotation}")
            self.plan.append(
                PlanItem(
                    output_page=len(self.plan) + 1,
                    doc_role=section.doc_role,
                    source_page=source_page,
                    section_id=section.section_id,
                    record_id=section.record_id,
                    transforms=tuple(transforms),
                    bookmark=bookmark if offset == 0 else None,
                )
            )
            self.consumed.add(
                (section.doc_role, section.section_id, section.record_id, source_page)
            )

    def _missing(self, leaf: FlowLeaf, address: Address, detail: str) -> None:
        if not leaf.required:
            log.info("resolve.optional_missing", address=address.render())
            return
        self.reasons.append(
            ReviewReason(
                code="missing_required",
                doc_role=self._role(address.source_alias),
                detail=f"{address.render()}: {detail}",
            )
        )

    # -- flow ------------------------------------------------------------------------
    def run(self) -> ResolveResult:
        for item in self.output.flow:
            if isinstance(item, FlowGroup):
                for record in self.prop.records:
                    for leaf in item.for_each_record:
                        self._leaf(leaf, record_id=record.id)
            else:
                self._leaf(item)
        dropped = self._drop()
        self._unmapped(dropped)
        return ResolveResult(
            plan=tuple(self.plan),
            dropped=tuple(dropped),
            reasons=tuple(self.reasons),
            unaccounted_pages=self._unaccounted(dropped),
        )

    def _leaf(self, leaf: FlowLeaf, record_id: str | None = None) -> None:
        address = parse_address(leaf.address)
        if address.is_record_templated:
            if record_id is None:
                raise ResolveError(f"{leaf.address!r} uses {{record}} outside for_each_record")
            address = address.with_record(record_id)

        if not self._role_is_present(address.source_alias):
            self._missing(leaf, address, "source file is absent")
            return

        schema = self._schema_for(address.source_alias)
        candidates = self._select(address, schema)
        if not candidates:
            optional_section = (
                schema is not None
                and not address.is_wildcard
                and address.section_ref in schema.section_ids
                and schema.section(address.section_ref).optional
            )
            if optional_section and not leaf.required:
                return
            detail = "no record matched" if address.record else "section not found in the source"
            self._missing(leaf, address, detail)
            return

        for section in candidates:
            record_name = self._record_name(section.record_id)
            bookmark = _render_bookmark(
                leaf.bookmark,
                section_title=_humanise(section.section_id, schema),
                record_name=record_name,
                prop=self.prop,
                period_label=self.period_label,
            )
            self._emit(section, bookmark)

    def _record_name(self, record_id: str | None) -> str | None:
        """The name to render in a bookmark. A single-record property drops the suffix."""
        if record_id is None or self.prop.is_single_record:
            return None
        return self.prop.record(record_id).pm_name or record_id

    def _select(self, address: Address, schema: SourceSchema | None) -> list[ResolvedSection]:
        sections = list(self._sections_for(address.source_alias))
        if address.is_wildcard:
            dropped_ids = self._dropped_section_ids(address.source_alias)
            return [s for s in sections if s.section_id not in dropped_ids]

        matches = [s for s in sections if s.section_id == address.section_ref]
        if address.occurrence is not None:
            index = address.occurrence - 1
            return [matches[index]] if 0 <= index < len(matches) else []

        if address.record is not None:
            return [s for s in matches if s.record_id == address.record]

        if schema is not None and address.section_ref in schema.section_ids:
            section_def = schema.section(address.section_ref)
            if section_def.cardinality == "per_record":
                # No @record: every record, in properties.yaml order (SPEC §5 rule 2).
                by_record = {s.record_id: s for s in matches}
                ordered = [by_record[r.id] for r in self.prop.records if r.id in by_record]
                return ordered or matches
            if len(matches) > 1:
                self.reasons.append(
                    ReviewReason(
                        code="cardinality_violation",
                        doc_role=matches[0].doc_role,
                        page=matches[0].first_page,
                        detail=(
                            f"{address.render()} matched {len(matches)} instances of a "
                            "'one' section and the flow does not disambiguate with '#n'"
                        ),
                    )
                )
        return matches

    # -- drop and the unmapped-section invariant --------------------------------------
    def _dropped_section_ids(self, alias: str) -> set[str]:
        role = self._role(alias)
        out: set[str] = set()
        for address in self.output.drop:
            parsed = parse_address(address)
            if self._role(parsed.source_alias) == role and not parsed.is_wildcard:
                out.add(parsed.section_ref)
        return out

    def _drop(self) -> list[DroppedSection]:
        out: list[DroppedSection] = []
        for address in self.output.drop:
            parsed = parse_address(address)
            for section in self._sections_for(parsed.source_alias):
                if parsed.is_wildcard or section.section_id == parsed.section_ref:
                    out.append(
                        DroppedSection(
                            section_id=section.section_id,
                            doc_role=section.doc_role,
                            record_id=section.record_id,
                            pages=section.pages,
                        )
                    )
        return out

    def _unmapped(self, dropped: list[DroppedSection]) -> None:
        """Every section found must be consumed by `flow` or listed in `drop` (SPEC §4.2)."""
        placed = {(role, section_id) for role, section_id, _, _ in self.consumed}
        dropped_keys = {(d.doc_role, d.section_id) for d in dropped}
        for segmentation in self.segments.values():
            for section in segmentation.sections:
                key = (section.doc_role, section.section_id)
                if key in placed or key in dropped_keys:
                    continue
                self.reasons.append(
                    ReviewReason(
                        code="unmapped_section",
                        doc_role=section.doc_role,
                        page=section.first_page,
                        detail=(
                            f"{section.section_id!r} was found in the source but is in neither "
                            "`flow` nor `drop`"
                        ),
                    )
                )

    def _unaccounted(self, dropped: list[DroppedSection]) -> dict[str, tuple[int, ...]]:
        accounted: dict[str, set[int]] = {}
        for role, _, _, page in self.consumed:
            accounted.setdefault(role, set()).add(page)
        for d in dropped:
            accounted.setdefault(d.doc_role, set()).update(d.pages)
        for reason in self.reasons:
            if reason.doc_role and reason.page:
                accounted.setdefault(reason.doc_role, set()).add(reason.page)
        out: dict[str, tuple[int, ...]] = {}
        for role, segmentation in self.segments.items():
            seen = accounted.get(role, set())
            missing = sorted(
                page
                for section in segmentation.sections
                for page in section.pages
                if page not in seen
            )
            if missing:
                out[role] = tuple(missing)
        return out


def resolve(
    output: OutputDefinition,
    prop: Property,
    segments: dict[str, Segmentation],
    schemas: dict[str, SourceSchema],
    period_label: str,
    present_roles: set[str] | None = None,
) -> ResolveResult:
    """Expand `output.flow` into an ordered page plan for `prop`.

    `segments` maps doc_role → segmentation. `present_roles` names the roles whose files were
    actually fetched; when None it defaults to the roles in `segments`.
    """
    result = _Resolver(output, prop, segments, schemas, period_label, present_roles).run()
    log.info(
        "resolve.done",
        property=prop.id,
        output_pages=result.page_count,
        dropped_sections=len(result.dropped),
        reasons=sorted({r.code for r in result.reasons}),
    )
    return result
