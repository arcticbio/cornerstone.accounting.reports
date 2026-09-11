"""Run-length segmentation of page labels into sections (SPEC §6.4).

The classifier labels pages; this turns a run of labels into the sections the resolver
addresses. It is pure: same labels in, same sections out, no I/O.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from crr.config.models import SourceSchema
from crr.log import get_logger
from crr.models import Orientation, PageClassification, Property, ResolvedSection, ReviewReason
from crr.segment.records import UNRESOLVED, map_qualifier

log = get_logger(__name__)

UNKNOWN = "unknown"


@dataclass(frozen=True)
class Segmentation:
    """Sections found in one document, plus what the review gate needs to know about them."""

    doc_role: str
    sections: tuple[ResolvedSection, ...]
    reasons: tuple[ReviewReason, ...]

    @property
    def section_ids(self) -> frozenset[str]:
        return frozenset(s.section_id for s in self.sections)


def effective_qualifiers(pages: list[PageClassification]) -> list[str | None]:
    """A continuation page with no `Property:` header inherits the previous page's qualifier
    (SPEC §6.4). An `unknown` page inherits nothing and passes nothing on."""
    out: list[str | None] = []
    carried: str | None = None
    for page in pages:
        if page.section_id == UNKNOWN:
            out.append(page.record_qualifier)
            carried = None
            continue
        if page.record_qualifier is not None:
            carried = page.record_qualifier
        elif not page.is_continuation:
            carried = None
        out.append(carried)
    return out


def segment(
    pages: list[PageClassification],
    schema: SourceSchema,
    prop: Property,
    doc_role: str,
) -> Segmentation:
    """Group consecutive page labels into `ResolvedSection`s and report structural problems."""
    ordered = sorted(pages, key=lambda p: p.page)
    qualifiers = effective_qualifiers(ordered)
    reasons: list[ReviewReason] = []
    sections: list[ResolvedSection] = []

    current: list[PageClassification] = []
    current_qualifier: str | None = None

    def flush() -> None:
        nonlocal current, current_qualifier
        if not current:
            return
        head = current[0]
        section_def = schema.section(head.section_id)
        record_id = map_qualifier(prop, section_def, current_qualifier)
        if record_id == UNRESOLVED:
            reasons.append(
                ReviewReason(
                    code="unresolved_record",
                    doc_role=doc_role,
                    page=head.page,
                    detail=(
                        f"section {head.section_id!r} carries a record qualifier that matches no "
                        f"record of {prop.id!r}"
                    ),
                )
            )
            record_id = None
        fixes: dict[int, Orientation] = {}
        for page_label in current:
            if page_label.orientation is not Orientation.UPRIGHT:
                fixes[page_label.page] = page_label.orientation
        sections.append(
            ResolvedSection(
                doc_role=doc_role,
                section_id=head.section_id,
                record_id=record_id,
                pages=tuple(p.page for p in current),
                orientation_fixes=fixes,
            )
        )
        current = []
        current_qualifier = None

    for index, page in enumerate(ordered):
        qualifier = qualifiers[index]
        if page.section_id == UNKNOWN:
            # Never merged into a neighbour; each unknown page is its own review item.
            flush()
            reasons.append(
                ReviewReason(
                    code="unknown_page",
                    doc_role=doc_role,
                    page=page.page,
                    detail=page.evidence[:200],
                )
            )
            continue
        if current:
            previous = current[-1]
            # A record qualifier only distinguishes instances of a `per_record` section. For a
            # `cardinality: one` section it is not part of the section's identity — `map_qualifier`
            # discards it either way — so a qualifier appearing part-way through a run must not
            # split it. Left unguarded, a model that transcribes the property header on some pages
            # of a long report and not others turns one section into two, and a correct package is
            # held back on a `cardinality_violation` (SPEC §6.4, as amended).
            splits_on_record = (
                schema.section(page.section_id).cardinality == "per_record"
                and qualifier != current_qualifier
            )
            starts_new = (
                page.section_id != previous.section_id
                or splits_on_record
                or not page.is_continuation
            )
            if starts_new:
                flush()
        if not current:
            current_qualifier = qualifier
        current.append(page)
    flush()

    reasons.extend(_cardinality_reasons(sections, schema, doc_role))
    log.info(
        "segment.done",
        doc_role=doc_role,
        pages=len(ordered),
        sections=len(sections),
        reasons=len(reasons),
    )
    return Segmentation(doc_role=doc_role, sections=tuple(sections), reasons=tuple(reasons))


def _cardinality_reasons(
    sections: list[ResolvedSection], schema: SourceSchema, doc_role: str
) -> list[ReviewReason]:
    """A `cardinality: one` section found more than once. The resolver clears this when the
    flow disambiguates with `#n` (SPEC §6.8)."""
    counts = Counter(s.section_id for s in sections)
    out: list[ReviewReason] = []
    for section_id, count in sorted(counts.items()):
        if count > 1 and schema.section(section_id).cardinality == "one":
            first = next(s for s in sections if s.section_id == section_id)
            out.append(
                ReviewReason(
                    code="cardinality_violation",
                    doc_role=doc_role,
                    page=first.first_page,
                    detail=f"{section_id!r} is cardinality 'one' but was found {count} times",
                )
            )
    return out
