"""The review gate (SPEC §6.8, D-12).

A build is `NEEDS_REVIEW` — never silently `BUILT` — whenever any of the conditions below
holds. `FAILED` is reserved for exceptions, and is set by the pipeline, not here.
"""

from __future__ import annotations

from dataclasses import dataclass

from crr.models import BuildStatus, PageClassification, ReviewReason

#: Every code the gate can emit, in the order SPEC §6.8 lists them.
REVIEW_CODES = (
    "unknown_page",
    "low_confidence",
    "footer_disagrees",
    "unmapped_section",
    "missing_required",
    "unresolved_record",
    "cardinality_violation",
    "orientation_uncertain",
    "page_count_drift",
)

#: Plain-language explanations for REVIEW.md — the review surface for a human (SPEC §17).
EXPLANATIONS: dict[str, str] = {
    "unknown_page": (
        "The classifier could not place this page in any section of the schema. It was left "
        "out of the package. Either the manager added a report the schema does not know "
        "about, or the page is unreadable."
    ),
    "low_confidence": (
        "The classifier chose a section but was not confident. The page may be in the wrong "
        "place in the package, or belong to a neighbouring section."
    ),
    "footer_disagrees": (
        "The report name printed in the page footer does not match the section the classifier "
        "chose. One of the two is wrong; the footer never overrides the classifier, so this "
        "always comes to a human."
    ),
    "unmapped_section": (
        "A section was found in the source that the output definition neither includes nor "
        "drops. Nothing was guessed: add it to `flow` or to `drop` in the output definition."
    ),
    "missing_required": (
        "Something the output definition requires was not there — a required source file, or "
        "a section the flow asks for. The package was built without it."
    ),
    "unresolved_record": (
        "A per-record section carries a property name that matches no record in "
        "`config/properties.yaml`. The manager may have renamed a property."
    ),
    "cardinality_violation": (
        "A section the schema says appears once was found more than once, and the flow does "
        "not say which instance to use."
    ),
    "orientation_uncertain": (
        "The two orientation checks disagree about which way up this page is, and the "
        "tie-breaker could not settle it. Nothing was guessed: an upside-down page reads as "
        "the right shape to every other check, so this always comes to a human."
    ),
    "page_count_drift": (
        "The manager's export changed size sharply since the last period. Worth a look before "
        "this goes to investors."
    ),
}


@dataclass(frozen=True)
class ReviewVerdict:
    status: BuildStatus
    reasons: tuple[ReviewReason, ...]

    @property
    def needs_review(self) -> bool:
        return self.status is BuildStatus.NEEDS_REVIEW


def confidence_reasons(
    classifications: list[PageClassification], min_confidence: float
) -> list[ReviewReason]:
    """`unknown_page`, `low_confidence` and `footer_disagrees`, read off the page labels."""
    out: list[ReviewReason] = []
    for page in classifications:
        if page.is_unknown:
            out.append(
                ReviewReason(
                    code="unknown_page",
                    doc_role=page.doc_role,
                    page=page.page,
                    detail=page.evidence[:200],
                )
            )
        elif page.confidence < min_confidence:
            out.append(
                ReviewReason(
                    code="low_confidence",
                    doc_role=page.doc_role,
                    page=page.page,
                    detail=f"{page.confidence:.2f} < {min_confidence:.2f}",
                )
            )
        if page.footer_agrees is False:
            out.append(
                ReviewReason(
                    code="footer_disagrees",
                    doc_role=page.doc_role,
                    page=page.page,
                    detail=(
                        f"footer says {page.footer_label!r}, classifier says {page.section_id!r}"
                    ),
                )
            )
    return out


def page_count_drift(
    doc_role: str, current_pages: int, previous_pages: int | None, threshold: float = 0.5
) -> list[ReviewReason]:
    """More than a 50 % change against the last built period for this property (SPEC §6.8)."""
    if not previous_pages:
        return []
    change = abs(current_pages - previous_pages) / previous_pages
    if change <= threshold:
        return []
    return [
        ReviewReason(
            code="page_count_drift",
            doc_role=doc_role,
            detail=(
                f"{previous_pages} pages last period, {current_pages} now "
                f"({change * 100:.0f}% change)"
            ),
        )
    ]


def decide(reasons: list[ReviewReason]) -> ReviewVerdict:
    """Any reason at all means the package goes to `review/`, not `output/` (D-12)."""
    ordered = sorted(
        reasons,
        key=lambda r: (
            REVIEW_CODES.index(r.code) if r.code in REVIEW_CODES else 99,
            r.doc_role or "",
            r.page or 0,
        ),
    )
    status = BuildStatus.NEEDS_REVIEW if ordered else BuildStatus.BUILT
    return ReviewVerdict(status=status, reasons=tuple(ordered))
