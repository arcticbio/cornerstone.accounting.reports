"""Eval scoring (SPEC §8)."""

from __future__ import annotations

from crr.evaluate.metrics import (
    BoundaryScore,
    Tally,
    score_boundaries,
    score_document,
)
from crr.golden import GoldenDocument, GoldenPage
from crr.models import Orientation, PageClassification, ResolvedSection


def _golden(*pages: tuple[int, str, bool, str | None, str | None]) -> GoldenDocument:
    return GoldenDocument(
        role="pm_source",
        schema_id="rentmanager-missoula",
        file="x.pdf",
        pages=tuple(
            GoldenPage(
                page=page,
                section=section,
                continuation=continuation,
                record=record,
                orientation=Orientation(orientation) if orientation else None,
            )
            for page, section, continuation, record, orientation in pages
        ),
    )


def _pred(
    page: int,
    section: str,
    continuation: bool = False,
    qualifier: str | None = None,
    orientation: Orientation = Orientation.UPRIGHT,
) -> PageClassification:
    return PageClassification(
        doc_role="pm_source",
        page=page,
        section_id=section,
        is_continuation=continuation,
        record_qualifier=qualifier,
        orientation=orientation,
        confidence=0.9,
        evidence="e",
        classifier="test",
    )


NAMES = {"default": "Fort Grounds Apartment Homes", None: None}


def test_a_perfect_document_scores_one() -> None:
    golden = _golden(
        (1, "owner_statement", False, None, None), (2, "owner_statement", True, None, None)
    )
    scores = score_document(
        golden,
        [_pred(1, "owner_statement"), _pred(2, "owner_statement", True)],
        score_record=False,
        golden_record_names=NAMES,
    )
    assert scores.page.accuracy == 1.0
    assert scores.continuation.accuracy == 1.0
    assert scores.confusion == {}


def test_a_wrong_section_is_counted_and_recorded_as_a_confusion_pair() -> None:
    golden = _golden(
        (1, "owner_statement", False, None, None), (2, "rent_roll_analysis", False, None, None)
    )
    scores = score_document(
        golden,
        [_pred(1, "owner_statement"), _pred(2, "rent_roll_bank")],
        score_record=False,
        golden_record_names=NAMES,
    )
    assert scores.page.accuracy == 0.5
    assert scores.confusion == {("rent_roll_analysis", "rent_roll_bank"): 1}


def test_a_page_the_classifier_never_returned_counts_as_wrong() -> None:
    golden = _golden(
        (1, "owner_statement", False, None, None), (2, "owner_statement", True, None, None)
    )
    scores = score_document(
        golden, [_pred(1, "owner_statement")], score_record=False, golden_record_names=NAMES
    )
    assert scores.page.accuracy == 0.5
    assert scores.confusion == {("owner_statement", "<missing>"): 1}
    assert scores.continuation.accuracy == 0.5


def test_record_accuracy_compares_against_the_printed_property_name() -> None:
    golden = _golden((1, "profit_loss_comparison", False, "default", None))
    ok = score_document(
        golden,
        [_pred(1, "profit_loss_comparison", qualifier="fort grounds apartment  homes")],
        score_record=True,
        golden_record_names=NAMES,
    )
    assert ok.record.accuracy == 1.0  # whitespace- and case-insensitive
    wrong = score_document(
        golden,
        [_pred(1, "profit_loss_comparison", qualifier="Some Other LP")],
        score_record=True,
        golden_record_names=NAMES,
    )
    assert wrong.record.accuracy == 0.0


def test_record_is_not_scored_when_the_source_prints_no_property_header() -> None:
    golden = _golden((1, "cover_letter", False, None, None))
    scores = score_document(
        golden,
        [_pred(1, "cover_letter", qualifier="anything")],
        score_record=False,
        golden_record_names=NAMES,
    )
    assert scores.record.scored == 0
    assert scores.record.accuracy is None


def test_orientation_is_scored_only_where_the_golden_file_says_so() -> None:
    golden = _golden(
        (1, "aged_receivable", False, None, "rotated_90_ccw"),
        (2, "rent_roll_lease_charges", False, None, None),
    )
    scores = score_document(
        golden,
        [
            _pred(1, "aged_receivable", orientation=Orientation.ROT_90_CCW),
            _pred(2, "rent_roll_lease_charges", orientation=Orientation.ROT_180),
        ],
        score_record=False,
        golden_record_names=NAMES,
    )
    assert scores.orientation.scored == 1
    assert scores.orientation.accuracy == 1.0


def _section(section_id: str, pages: tuple[int, ...], record: str | None = None) -> ResolvedSection:
    return ResolvedSection(
        doc_role="pm_source", section_id=section_id, record_id=record, pages=pages
    )


def test_identical_segmentations_score_one() -> None:
    sections = [_section("owner_statement", (1, 2)), _section("rent_roll", (3,))]
    score = score_boundaries(sections, list(sections))
    assert score.f1 == 1.0


def test_a_boundary_one_page_off_costs_two_segments() -> None:
    golden = [_section("owner_statement", (1, 2)), _section("rent_roll", (3, 4))]
    predicted = [_section("owner_statement", (1, 2, 3)), _section("rent_roll", (4,))]
    score = score_boundaries(golden, predicted)
    assert score.true_positive == 0
    assert score.f1 == 0.0


def test_a_partially_correct_segmentation() -> None:
    golden = [_section("a", (1,)), _section("b", (2,)), _section("c", (3,))]
    predicted = [_section("a", (1,)), _section("b", (2, 3))]
    score = score_boundaries(golden, predicted)
    assert score.true_positive == 1
    assert score.precision == 0.5
    assert score.recall == 1 / 3


def test_a_segment_under_the_wrong_record_is_not_a_match() -> None:
    golden = [_section("profit_loss_comparison", (1,), "waypointe-ah-lp")]
    predicted = [_section("profit_loss_comparison", (1,), "128-s-5th-street-west")]
    assert score_boundaries(golden, predicted).f1 == 0.0


def test_empty_tallies_report_no_accuracy_rather_than_zero() -> None:
    assert Tally().accuracy is None
    assert BoundaryScore().f1 is None
