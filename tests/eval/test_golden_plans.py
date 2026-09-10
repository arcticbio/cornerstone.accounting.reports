"""The resolver + output definitions, checked against the frozen `expected_output` for all
eight properties — no PDF I/O involved (PLAN Phase 2, SPEC §9.5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from crr.config import load_config
from crr.golden import load_all_golden
from crr.resolve.resolver import resolve
from crr.segment.segmenter import segment

BUNDLE = load_config(Path("config"))
GOLDEN = load_all_golden(Path("eval/golden"))
PROPERTY_IDS = sorted(GOLDEN)


def _plan(property_id: str):  # type: ignore[no-untyped-def]
    golden = GOLDEN[property_id]
    prop = BUNDLE.properties.property(property_id).to_domain()
    output = BUNDLE.output_for_property(property_id)
    segments = {
        doc.role: segment(
            golden.classifications(doc.role), BUNDLE.schemas[doc.schema_id], prop, doc.role
        )
        for doc in golden.documents
    }
    return golden, resolve(
        output, prop, segments, BUNDLE.schemas, BUNDLE.properties.period_label(golden.period)
    )


@pytest.mark.parametrize("property_id", PROPERTY_IDS)
def test_resolved_plan_matches_the_frozen_expected_output(property_id: str) -> None:
    golden, result = _plan(property_id)
    assert golden.expected_output is not None, "expected_output was frozen in Phase 2"
    actual = [
        (i.output_page, i.doc_role, i.section_id, i.record_id, i.source_page) for i in result.plan
    ]
    expected = [
        (e.output_page, e.doc_role, e.section, e.record, e.source_page)
        for e in golden.expected_output
    ]
    assert actual == expected


@pytest.mark.parametrize("property_id", PROPERTY_IDS)
def test_page_count_matches_the_golden_count(property_id: str) -> None:
    golden, result = _plan(property_id)
    assert result.page_count == golden.expected_output_page_count


@pytest.mark.parametrize("property_id", PROPERTY_IDS)
def test_a_golden_build_raises_no_review_reasons(property_id: str) -> None:
    _, result = _plan(property_id)
    assert result.reasons == ()


@pytest.mark.parametrize("property_id", PROPERTY_IDS)
def test_no_source_page_is_silently_lost(property_id: str) -> None:
    """D-11 / SPEC §9.1 — every page is placed, dropped, or a review reason."""
    _, result = _plan(property_id)
    assert result.unaccounted_pages == {}


def test_the_missoula_drop_list_discards_the_reports_the_analysis_names() -> None:
    _, result = _plan("fort-grounds")
    assert {d.section_id for d in result.dropped} == {
        "financial_statement",
        "rent_roll_analysis",
        "general_ledger",
        "actual_budget_fy_analysis",
        "rent_roll_bank",
        "delinquency",
    }


def test_waypointe_emits_records_in_properties_yaml_order() -> None:
    """D-07: source order, not the published package's reversed order."""
    _, result = _plan("waypointe")
    pm_records = [i.record_id for i in result.plan if i.doc_role == "pm_source" and i.record_id]
    assert pm_records == [
        "waypointe-ah-lp",
        "waypointe-ah-lp",
        "waypointe-ah-lp",
        "128-s-5th-street-west",
        "128-s-5th-street-west",
        "128-s-5th-street-west",
    ]


def test_timber_place_front_matter_is_two_pages_and_leads() -> None:
    """D-06: front matter always leads; Timber Place has no distribution schedule."""
    _, result = _plan("timber-place")
    assert [i.doc_role for i in result.plan[:3]] == [
        "cornerstone_balance_sheet",
        "cornerstone_profit_loss_ytd",
        "pm_source",
    ]


def test_the_timber_place_aged_receivable_page_is_rotated_upright() -> None:
    _, result = _plan("timber-place")
    aged = next(i for i in result.plan if i.section_id == "aged_receivable")
    assert aged.transforms == ("copy", "rotate:90")


def test_every_property_starts_with_the_cornerstone_balance_sheet() -> None:
    """D-06, including WayPointe — the published package put its block last; we do not."""
    for property_id in PROPERTY_IDS:
        _, result = _plan(property_id)
        assert result.plan[0].doc_role == "cornerstone_balance_sheet", property_id
