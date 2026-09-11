"""Saving and replaying eval predictions (SPEC §8, A-10).

The point of this file is that a *metric* can be corrected without paying for the labels again.
Both metric defects found on 2026-09-11 cost a fresh keyed run to re-measure — $4.66 and $1.97
— on labels that had not changed at all.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crr.classify.protocol import Usage
from crr.evaluate.harness import DocumentResult, EvalResult
from crr.evaluate.metrics import Scores
from crr.evaluate.predictions import (
    FORMAT_VERSION,
    dump_predictions,
    load_predictions,
    predictions_filename,
    predictions_header,
    predictions_usage,
)
from crr.models import Orientation, PageClassification


def _page(page: int, *, evidence: str = "a title and a footer") -> PageClassification:
    return PageClassification(
        doc_role="pm_source",
        page=page,
        section_id="owner_statement",
        is_continuation=page > 1,
        record_qualifier="Fort Grounds Apartment Homes" if page == 1 else None,
        orientation=Orientation.UPRIGHT,
        confidence=0.97,
        evidence=evidence,
        classifier="anthropic:claude-opus-5:v1",
    )


def _result() -> EvalResult:
    result = EvalResult(
        classifier="anthropic:claude-opus-5:v1", model="claude-opus-5", prompt_version="v1"
    )
    result.usage = Usage(
        input_tokens=695835,
        cache_read_tokens=608447,
        cache_write_tokens=0,
        output_tokens=34961,
        api_calls=172,
        latency_ms=1_115_000,
    )
    result.documents.append(
        DocumentResult(
            property_id="fort-grounds",
            pm_id="missoula",
            doc_role="pm_source",
            schema_id="rentmanager-missoula",
            pages=2,
            scores=Scores(),
            predictions=[_page(1), _page(2)],
        )
    )
    return result


class TestRoundTrip:
    def test_labels_survive_unchanged(self, tmp_path: Path) -> None:
        path = tmp_path / "run.predictions.json"
        dump_predictions(_result(), path)
        loaded = load_predictions(path)
        pages = loaded[("fort-grounds", "pm_source")]
        assert [p.page for p in pages] == [1, 2]
        assert pages[0].record_qualifier == "Fort Grounds Apartment Homes"
        assert pages[1].record_qualifier is None
        assert pages[1].is_continuation is True
        assert pages[0].orientation is Orientation.UPRIGHT
        assert pages[0].confidence == pytest.approx(0.97)

    def test_evidence_never_reaches_the_file(self, tmp_path: Path) -> None:
        """It is a model-written sentence about the page, and these files are committed."""
        path = tmp_path / "run.predictions.json"
        dump_predictions(_result(), path)
        raw = path.read_text()
        assert "a title and a footer" not in raw
        assert "evidence" not in raw
        assert load_predictions(path)[("fort-grounds", "pm_source")][0].evidence == ""

    def test_the_run_cost_is_carried(self, tmp_path: Path) -> None:
        """A replay calls nothing, but the report must still state what the run cost."""
        path = tmp_path / "run.predictions.json"
        dump_predictions(_result(), path)
        usage = predictions_usage(path)
        assert usage.api_calls == 172
        assert usage.input_tokens == 695835
        assert usage.cache_read_tokens == 608447
        assert usage.output_tokens == 34961

    def test_header_identifies_the_run(self, tmp_path: Path) -> None:
        path = tmp_path / "run.predictions.json"
        dump_predictions(_result(), path)
        assert predictions_header(path) == ("anthropic:claude-opus-5:v1", "claude-opus-5", "v1")

    def test_document_order_is_preserved(self, tmp_path: Path) -> None:
        """A replayed report has to diff cleanly against the one it replays."""
        result = _result()
        for role in ("cornerstone_balance_sheet", "aaa_sorts_first"):
            result.documents.append(
                DocumentResult(
                    property_id="fort-grounds",
                    pm_id="missoula",
                    doc_role=role,
                    schema_id="cornerstone-qbo",
                    pages=1,
                    scores=Scores(),
                    predictions=[_page(1)],
                )
            )
        path = tmp_path / "run.predictions.json"
        dump_predictions(result, path)
        assert [role for _, role in load_predictions(path)] == [
            "pm_source",
            "cornerstone_balance_sheet",
            "aaa_sorts_first",
        ]


class TestRefusals:
    def test_a_future_format_is_refused_rather_than_guessed(self, tmp_path: Path) -> None:
        path = tmp_path / "run.predictions.json"
        dump_predictions(_result(), path)
        payload = json.loads(path.read_text())
        payload["format_version"] = FORMAT_VERSION + 1
        path.write_text(json.dumps(payload))
        with pytest.raises(ValueError, match="format_version"):
            load_predictions(path)

    def test_a_file_without_usage_reports_zero(self, tmp_path: Path) -> None:
        path = tmp_path / "run.predictions.json"
        dump_predictions(_result(), path)
        payload = json.loads(path.read_text())
        del payload["usage"]
        path.write_text(json.dumps(payload))
        assert predictions_usage(path).api_calls == 0


def test_the_predictions_file_sits_beside_its_report() -> None:
    assert predictions_filename("20260911T000734Z-golden-na.md") == (
        "20260911T000734Z-golden-na.predictions.json"
    )
