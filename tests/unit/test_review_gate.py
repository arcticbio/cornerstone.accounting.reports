"""The review gate and REVIEW.md (SPEC §6.8, §6.9, D-12)."""

from __future__ import annotations

from crr.manifest.model import (
    BuildManifest,
    ClassifierBlock,
    ConfigBlock,
    ConfigRef,
    InputRef,
    PropertyBlock,
)
from crr.models import BuildStatus, Orientation, PageClassification, ReviewReason
from crr.review.report import render_review
from crr.review.rules import (
    EXPLANATIONS,
    REVIEW_CODES,
    confidence_reasons,
    decide,
    page_count_drift,
)


def _page(page: int, **kwargs: object) -> PageClassification:
    base = {
        "doc_role": "pm_source",
        "page": page,
        "section_id": "owner_statement",
        "is_continuation": False,
        "record_qualifier": None,
        "orientation": Orientation.UPRIGHT,
        "confidence": 0.99,
        "evidence": "title block",
        "classifier": "golden",
    }
    base.update(kwargs)
    return PageClassification(**base)  # type: ignore[arg-type]


def test_a_clean_build_is_built() -> None:
    assert decide([]).status is BuildStatus.BUILT
    assert not decide([]).needs_review


def test_any_reason_holds_the_package_back() -> None:
    verdict = decide([ReviewReason(code="unknown_page", doc_role="pm_source", page=3)])
    assert verdict.status is BuildStatus.NEEDS_REVIEW


def test_unknown_pages_and_low_confidence() -> None:
    pages = [
        _page(1),
        _page(2, section_id="unknown", evidence="no title block"),
        _page(3, confidence=0.5),
    ]
    reasons = confidence_reasons(pages, min_confidence=0.85)
    assert [(r.code, r.page) for r in reasons] == [("unknown_page", 2), ("low_confidence", 3)]


def test_an_unknown_page_is_not_also_low_confidence() -> None:
    """One page, one primary reason: `unknown` already says the page needs a human."""
    reasons = confidence_reasons([_page(1, section_id="unknown", confidence=0.0)], 0.85)
    assert [r.code for r in reasons] == ["unknown_page"]


def test_footer_disagreement_is_reported_alongside_the_label() -> None:
    pages = [_page(1, footer_label="Rent Roll Analysis", footer_agrees=False)]
    reasons = confidence_reasons(pages, 0.85)
    assert [r.code for r in reasons] == ["footer_disagrees"]
    assert "Rent Roll Analysis" in reasons[0].detail


def test_footer_agreement_is_not_a_reason() -> None:
    pages = [_page(1, footer_label="Owner Statement", footer_agrees=True)]
    assert confidence_reasons(pages, 0.85) == []


def test_page_count_drift_only_fires_beyond_fifty_percent() -> None:
    assert page_count_drift("pm_source", 16, None) == []
    assert page_count_drift("pm_source", 20, 16) == []  # +25 %
    assert page_count_drift("pm_source", 40, 16) != []  # +150 %
    assert page_count_drift("pm_source", 4, 16) != []  # -75 %


def test_reasons_are_ordered_by_severity_then_position() -> None:
    reasons = [
        ReviewReason(code="missing_required", detail="a"),
        ReviewReason(code="unknown_page", doc_role="pm_source", page=9),
        ReviewReason(code="unknown_page", doc_role="pm_source", page=2),
    ]
    verdict = decide(reasons)
    assert [(r.code, r.page) for r in verdict.reasons] == [
        ("unknown_page", 2),
        ("unknown_page", 9),
        ("missing_required", None),
    ]


def test_every_code_has_a_plain_language_explanation() -> None:
    assert set(EXPLANATIONS) == set(REVIEW_CODES)


def _manifest(reasons: list[ReviewReason]) -> BuildManifest:
    return BuildManifest(
        status=BuildStatus.NEEDS_REVIEW,
        review_reasons=reasons,
        property=PropertyBlock(
            id="waypointe",
            name="WayPointe",
            property_manager="missoula",
            owning_entity="WayPointe Apartment Homes LP",
        ),
        period="2026-06",
        config=ConfigBlock(
            schema_ref=ConfigRef(id="rentmanager-missoula", version=1, sha256="a" * 64),
            output=ConfigRef(id="missoula-investor-report", version=1, sha256="b" * 64),
            properties_sha256="c" * 64,
        ),
        classifier=ClassifierBlock(name="golden"),
        inputs=[
            InputRef(
                role="pm_source", file="pm.pdf", sha256="d" * 64, pages=16, has_text_layer=True
            )
        ],
    )


def test_review_md_explains_each_finding_in_plain_language() -> None:
    text = render_review(
        _manifest(
            [
                ReviewReason(code="unknown_page", doc_role="pm_source", page=7, detail="no title"),
                ReviewReason(code="footer_disagrees", doc_role="pm_source", page=9, detail="x"),
            ]
        )
    )
    assert "# Review needed — WayPointe, 2026-06" in text
    assert EXPLANATIONS["unknown_page"][:40] in text
    assert EXPLANATIONS["footer_disagrees"][:40] in text
    assert "| pm_source | 7 | no title |" in text
    assert "What to do next" in text
    assert "pm.pdf" not in text or "`dddddddddddd`" in text  # inputs table renders the sha


def test_review_md_groups_repeated_codes() -> None:
    text = render_review(
        _manifest(
            [
                ReviewReason(code="unknown_page", doc_role="pm_source", page=3),
                ReviewReason(code="unknown_page", doc_role="pm_source", page=4),
            ]
        )
    )
    assert "Unknown page (2)" in text
