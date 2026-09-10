"""Run-length segmentation (SPEC §6.4) and record mapping (SPEC §5 rule 3)."""

from __future__ import annotations

import pytest

from crr.config.models import Fingerprint, SectionDef, SourceSchema
from crr.models import Orientation, PageClassification, Property, PropertyRecord
from crr.segment.records import UNRESOLVED, map_qualifier
from crr.segment.segmenter import segment


def _schema() -> SourceSchema:
    return SourceSchema(
        schema_id="test",
        version=1,
        producer="p",
        system="s",
        text_layer="always",
        fingerprint=Fingerprint(description="d"),
        sections=(
            SectionDef(
                id="owner_statement",
                semantic="owner_statement",
                cardinality="one",
                text_cues=("x",),
            ),
            SectionDef(
                id="rent_roll", semantic="rent_roll", cardinality="per_record", text_cues=("x",)
            ),
            SectionDef(id="ledger", semantic="general_ledger", cardinality="one", text_cues=("x",)),
        ),
    )


def _prop(*records: tuple[str, str | None]) -> Property:
    return Property(
        id="p",
        name="P",
        folder="P",
        property_manager="pm",
        owning_entity="E",
        records=tuple(PropertyRecord(id=i, pm_name=n) for i, n in records),
    )


def _page(
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
        confidence=1.0,
        evidence="e",
        classifier="golden",
    )


SINGLE = _prop(("default", "Fort Grounds Apartment Homes"))
MULTI = _prop(("a", "Alpha LP"), ("b", "Beta LP"))


def test_a_continuation_run_becomes_one_section() -> None:
    result = segment(
        [
            _page(1, "owner_statement"),
            _page(2, "owner_statement", True),
            _page(3, "owner_statement", True),
        ],
        _schema(),
        SINGLE,
        "pm_source",
    )
    assert len(result.sections) == 1
    assert result.sections[0].pages == (1, 2, 3)
    assert not result.reasons


def test_continuation_false_breaks_two_back_to_back_instances() -> None:
    result = segment(
        [_page(1, "ledger"), _page(2, "ledger")],  # second page is not a continuation
        _schema(),
        SINGLE,
        "pm_source",
    )
    assert [s.pages for s in result.sections] == [(1,), (2,)]
    # 'ledger' is cardinality one, so two instances is a review reason.
    assert [r.code for r in result.reasons] == ["cardinality_violation"]


def test_a_section_change_breaks_the_run() -> None:
    result = segment(
        [_page(1, "owner_statement"), _page(2, "ledger", True)], _schema(), SINGLE, "pm_source"
    )
    assert [s.section_id for s in result.sections] == ["owner_statement", "ledger"]


def test_record_change_breaks_the_run_even_without_a_title_page() -> None:
    result = segment(
        [
            _page(1, "rent_roll", qualifier="Alpha LP"),
            _page(2, "rent_roll", True, qualifier="Beta LP"),
        ],
        _schema(),
        MULTI,
        "pm_source",
    )
    assert [(s.pages, s.record_id) for s in result.sections] == [((1,), "a"), ((2,), "b")]


def test_a_blank_continuation_page_inherits_the_previous_qualifier() -> None:
    result = segment(
        [_page(1, "rent_roll", qualifier="Alpha LP"), _page(2, "rent_roll", True)],
        _schema(),
        MULTI,
        "pm_source",
    )
    assert len(result.sections) == 1
    assert result.sections[0].pages == (1, 2)
    assert result.sections[0].record_id == "a"


def test_unknown_pages_are_isolated_and_never_merged() -> None:
    result = segment(
        [_page(1, "owner_statement"), _page(2, "unknown"), _page(3, "owner_statement", True)],
        _schema(),
        SINGLE,
        "pm_source",
    )
    assert [s.pages for s in result.sections] == [(1,), (3,)]
    codes = [r.code for r in result.reasons]
    assert codes.count("unknown_page") == 1
    assert "cardinality_violation" in codes  # owner_statement is 'one', now found twice


def test_orientation_fixes_are_carried_on_the_section() -> None:
    result = segment(
        [_page(1, "rent_roll", orientation=Orientation.ROT_90_CCW), _page(2, "rent_roll", True)],
        _schema(),
        SINGLE,
        "pm_source",
    )
    assert result.sections[0].orientation_fixes == {1: Orientation.ROT_90_CCW}


def test_pages_are_segmented_in_document_order_whatever_the_input_order() -> None:
    pages = [_page(3, "ledger"), _page(1, "owner_statement"), _page(2, "owner_statement", True)]
    result = segment(pages, _schema(), SINGLE, "pm_source")
    assert [s.pages for s in result.sections] == [(1, 2), (3,)]


class TestRecordMapping:
    def test_one_cardinality_belongs_to_no_record(self) -> None:
        section = _schema().section("owner_statement")
        assert map_qualifier(MULTI, section, "Alpha LP") is None

    def test_exact_match_is_case_and_whitespace_insensitive(self) -> None:
        section = _schema().section("rent_roll")
        assert map_qualifier(MULTI, section, "  alpha   lp ") == "a"

    def test_null_qualifier_on_a_single_record_property_means_that_record(self) -> None:
        section = _schema().section("rent_roll")
        assert map_qualifier(SINGLE, section, None) == "default"

    def test_null_qualifier_on_a_multi_record_property_is_unresolved(self) -> None:
        section = _schema().section("rent_roll")
        assert map_qualifier(MULTI, section, None) == UNRESOLVED

    def test_an_unknown_qualifier_is_unresolved(self) -> None:
        section = _schema().section("rent_roll")
        assert map_qualifier(MULTI, section, "Gamma LP") == UNRESOLVED

    def test_an_unresolved_record_becomes_a_review_reason(self) -> None:
        result = segment(
            [_page(1, "rent_roll", qualifier="Gamma LP")], _schema(), MULTI, "pm_source"
        )
        assert [r.code for r in result.reasons] == ["unresolved_record"]
        assert result.sections[0].record_id is None


@pytest.mark.parametrize("qualifier", ["Fort Grounds Apartment Homes", None])
def test_single_record_source_with_or_without_a_header(qualifier: str | None) -> None:
    result = segment([_page(1, "rent_roll", qualifier=qualifier)], _schema(), SINGLE, "pm_source")
    assert result.sections[0].record_id == "default"
    assert not result.reasons


def test_a_qualifier_appearing_mid_run_does_not_split_a_one_section() -> None:
    """B-08: the bug that sent both McCathren packages to review.

    The model transcribed the property header on the back half of a seven-page General Ledger
    and not the front half. `general_ledger` is `cardinality: one`, so splitting on the
    qualifier made it appear twice and the correct package was held back on a
    `cardinality_violation`. A qualifier is not part of a one-cardinality section's identity.
    """
    pages = [
        _page(1, "ledger"),
        _page(2, "ledger", True),
        _page(3, "ledger", True, qualifier="Timber Place by the Lake (1000)"),
        _page(4, "ledger", True, qualifier="Timber Place by the Lake (1000)"),
    ]
    result = segment(pages, _schema(), SINGLE, "pm_source")
    assert [s.pages for s in result.sections] == [(1, 2, 3, 4)]
    assert result.sections[0].record_id is None
    assert not result.reasons


def test_a_per_record_section_still_splits_on_a_qualifier_change() -> None:
    """The rule exists for WayPointe's back-to-back per-record runs; it must survive B-08's fix."""
    pages = [
        _page(1, "rent_roll", qualifier="Alpha LP"),
        _page(2, "rent_roll", True, qualifier="Alpha LP"),
        _page(3, "rent_roll", True, qualifier="Beta LP"),
    ]
    result = segment(pages, _schema(), MULTI, "pm_source")
    assert [(s.pages, s.record_id) for s in result.sections] == [((1, 2), "a"), ((3,), "b")]


def test_a_one_section_still_splits_when_a_new_instance_starts() -> None:
    """Guard the other direction: `is_continuation=False` is what starts a second instance."""
    pages = [_page(1, "ledger"), _page(2, "ledger", qualifier="Anything")]
    result = segment(pages, _schema(), SINGLE, "pm_source")
    assert [s.pages for s in result.sections] == [(1,), (2,)]
    assert [r.code for r in result.reasons] == ["cardinality_violation"]
