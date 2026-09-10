"""The harness's own self-consistency check (SPEC §8, §15): the golden classifier scored
against the golden labels must be 100 %."""

from __future__ import annotations

from pathlib import Path

import pytest

from crr.classify.golden_classifier import GoldenClassifier
from crr.config import load_config
from crr.evaluate import evaluate, gate_failures, render_report
from crr.golden import load_all_golden
from crr.settings import Settings

CONFIG = load_config(Path("config"))
GOLDEN = load_all_golden(Path("eval/golden"))


@pytest.fixture(scope="module")
def golden_eval(tmp_path_factory: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    settings = Settings(_env_file=None, work_dir=tmp_path_factory.mktemp("eval"))  # type: ignore[call-arg]
    result = evaluate(
        GOLDEN, CONFIG, settings, lambda property_id: GoldenClassifier(GOLDEN[property_id])
    )
    return result, settings


def test_the_harness_is_self_consistent(golden_eval) -> None:  # type: ignore[no-untyped-def]
    result, _ = golden_eval
    overall = result.overall()
    assert overall.page.accuracy == 1.0
    assert overall.continuation.accuracy == 1.0
    assert overall.boundary.f1 == 1.0
    assert result.confusion_pairs() == []


def test_every_golden_document_is_scored(golden_eval) -> None:  # type: ignore[no-untyped-def]
    result, _ = golden_eval
    assert len(result.documents) == 31
    assert result.overall().page.scored == 172  # 149 PM pages + 23 Cornerstone pages


def test_each_manager_meets_both_thresholds(golden_eval) -> None:  # type: ignore[no-untyped-def]
    result, settings = golden_eval
    assert set(result.by_manager()) == {"missoula", "mccathren", "cobalt"}
    assert gate_failures(result, settings) == []


def test_record_accuracy_is_scored_for_missoula_only(golden_eval) -> None:  # type: ignore[no-untyped-def]
    result, _ = golden_eval
    by_manager = result.by_manager()
    assert by_manager["missoula"].record.scored > 0
    assert by_manager["cobalt"].record.scored == 0
    assert by_manager["mccathren"].record.scored == 0


def test_orientation_is_scored_where_the_golden_files_carry_it(golden_eval) -> None:  # type: ignore[no-untyped-def]
    result, _ = golden_eval
    # One page in the whole bundle carries an orientation: Timber Place p3.
    assert result.overall().orientation.scored == 1
    assert result.overall().orientation.accuracy == 1.0


def test_the_report_renders_every_section(golden_eval) -> None:  # type: ignore[no-untyped-def]
    result, settings = golden_eval
    text = render_report(result, settings, gate_failures(result, settings))
    for heading in (
        "# Classifier eval",
        "## Per manager",
        "## Per document",
        "## Confusion pairs",
        "## Cost",
        "## Gate",
    ):
        assert heading in text
    assert "All managers meet both thresholds." in text
    assert "100.00% (172/172)" in text


def test_the_report_names_the_managers_below_threshold(golden_eval) -> None:  # type: ignore[no-untyped-def]
    result, settings = golden_eval
    text = render_report(result, settings, ["missoula: page accuracy 0.9000 < 0.98"])
    assert "**Below threshold:**" in text
    assert "missoula: page accuracy 0.9000" in text


def test_scoping_to_one_manager(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, work_dir=tmp_path)  # type: ignore[call-arg]
    result = evaluate(
        GOLDEN,
        CONFIG,
        settings,
        lambda property_id: GoldenClassifier(GOLDEN[property_id]),
        pm_id="cobalt",
    )
    assert set(result.by_manager()) == {"cobalt"}
    assert {d.property_id for d in result.documents} == {"bridgewater", "salmon-crossing"}
