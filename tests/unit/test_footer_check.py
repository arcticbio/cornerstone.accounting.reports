"""The footer check on real page text from the bundle (SPEC §7.4, D-05)."""

from __future__ import annotations

from pathlib import Path

import pytest

from crr.classify.footer_check import apply_footer_check, check_footer
from crr.config import load_config
from crr.models import Orientation, PageClassification
from crr.preprocess.text import page_texts

BUNDLE = Path("data/bundle/2026-06")
CONFIG = load_config(Path("config"))

MISSOULA_PDF = (
    BUNDLE
    / "Missoula Property Management/Fort Grounds/2026-06 June/inputs"
    / "05 PM Source - Missoula PM Baseline.pdf"
)
COBALT_PDF = (
    BUNDLE
    / "Cobalt Properties Group/Bridgewater/2026-06 June/inputs"
    / "05 PM Source - Cobalt Baseline.pdf"
)


@pytest.fixture(scope="module")
def missoula_texts() -> list[str]:
    return page_texts(MISSOULA_PDF)


@pytest.fixture(scope="module")
def cobalt_texts() -> list[str]:
    return page_texts(COBALT_PDF)


def test_rent_manager_footer_names_the_report_on_the_matching_line(
    missoula_texts: list[str],
) -> None:
    """Rent Manager prints '<Report Name> <timestamp> Page N of M rentmanager.com ...'."""
    schema = CONFIG.schemas["rentmanager-missoula"]
    verdicts = [check_footer(schema, text) for text in missoula_texts]
    assert [v.section_id for v in verdicts] == [
        "owner_statement",
        "owner_statement",
        "profit_loss_comparison",
        "unit_availability",
        "unit_availability",
        "financial_statement",
        "financial_statement",
        "rent_roll_analysis",
        "rent_roll_analysis",
        "general_ledger",
        "actual_budget_fy_analysis",
        "actual_budget_fy_analysis",
        "actual_budget_fy_analysis",
        "rent_roll_bank",
        "rent_roll_bank",
        "delinquency",
    ]


def test_cobalt_footer_names_the_report_on_the_line_above(cobalt_texts: list[str]) -> None:
    """Cobalt's regex matches only 'Created on <date> Page N'; the report name is the line
    above it (SPEC §7.4)."""
    schema = CONFIG.schemas["cobalt"]
    verdicts = [check_footer(schema, text) for text in cobalt_texts]
    # Owner statement pages declare no footer_label: 'Page N of M' names no report.
    assert all(v.section_id is None for v in verdicts[:9])
    assert [v.section_id for v in verdicts[9:]] == [
        "cash_flow_12_month",
        "cash_flow_12_month",
        "cash_flow_12_month",
        "cash_flow_12_month",
        "rent_roll",
        "rent_roll",
        "rent_roll",
        "balance_sheet",
        "annual_budget_comparative",
        "annual_budget_comparative",
        "annual_budget_comparative",
        "annual_budget_comparative",
    ]


def test_delinquency_label_matches_a_longer_printed_name() -> None:
    """'Delinquency' is a prefix of 'Delinquency (Detail)' — the label matches (SPEC §7.4)."""
    schema = CONFIG.schemas["rentmanager-missoula"]
    text = (
        "body\nDelinquency (Detail) 06/30/26 04:00 PM Page 1 of "
        "rentmanager.com - property management systems"
    )
    assert check_footer(schema, text).section_id == "delinquency"


def test_the_longest_matching_label_wins() -> None:
    """'Rent Roll - Bank' beats a hypothetical shorter 'Rent Roll' on the same line."""
    schema = CONFIG.schemas["rentmanager-missoula"].model_copy()
    text = "body\nRent Roll - Bank 07/16/26 Page 1 of rentmanager.com - property management systems"
    assert check_footer(schema, text).label == "Rent Roll - Bank"


def test_no_regex_means_no_verdict() -> None:
    """McCathren scans carry no reliable footer; the check must stay silent rather than guess."""
    schema = CONFIG.schemas["mccathren"]
    assert (
        check_footer(schema, "Timber Place by the Lake\nBalance Sheet\nPage 1 of 2").label is None
    )


def test_empty_text_is_not_a_verdict() -> None:
    assert check_footer(CONFIG.schemas["cobalt"], "").label is None
    assert check_footer(CONFIG.schemas["cobalt"], None).label is None


def _label(page: int, section: str) -> PageClassification:
    return PageClassification(
        doc_role="pm_source",
        page=page,
        section_id=section,
        is_continuation=False,
        record_qualifier=None,
        orientation=Orientation.UPRIGHT,
        confidence=0.9,
        evidence="e",
        classifier="test",
    )


def test_agreement_and_disagreement_are_recorded_not_overridden(
    missoula_texts: list[str],
) -> None:
    """D-05: the footer is a checksum on the classifier, never an override."""
    schema = CONFIG.schemas["rentmanager-missoula"]
    labels = [_label(1, "owner_statement"), _label(3, "general_ledger")]  # page 3 is wrong
    texts = {1: missoula_texts[0], 3: missoula_texts[2]}
    out = apply_footer_check(labels, schema, texts)
    assert out[0].footer_label == "Owner Statement"
    assert out[0].footer_agrees is True
    assert out[1].footer_label == "Profit & Loss Comparison"
    assert out[1].footer_agrees is False
    assert out[1].section_id == "general_ledger"  # the label is untouched


def test_a_page_with_no_footer_match_records_none(cobalt_texts: list[str]) -> None:
    out = apply_footer_check(
        [_label(1, "owner_statement")], CONFIG.schemas["cobalt"], {1: cobalt_texts[0]}
    )
    assert out[0].footer_label is None
    assert out[0].footer_agrees is None
