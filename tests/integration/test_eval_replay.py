"""A replayed eval must reproduce the run it replays (SPEC §8, A-10).

This is the property the whole predictions file exists for: if `--from` did not give the same
numbers as the run, correcting a metric offline would prove nothing and the next metric defect
would cost another keyed run.
"""

from __future__ import annotations

from pathlib import Path

from crr.config import load_config
from crr.evaluate import evaluate, render_report, report_filename
from crr.evaluate.harness import rescore
from crr.evaluate.predictions import (
    dump_predictions,
    load_predictions,
    predictions_header,
    predictions_usage,
)
from crr.golden import load_all_golden
from crr.settings import Settings

CONFIG = load_config(Path("config"))
GOLDEN = load_all_golden(Path("eval/golden"))


def _live(tmp_path: Path):  # type: ignore[no-untyped-def]
    from crr.classify.golden_classifier import GoldenClassifier

    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, work_dir=tmp_path / "work", orientation_check=False
    )
    result = evaluate(
        GOLDEN,
        CONFIG,
        settings,
        lambda property_id: GoldenClassifier(GOLDEN[property_id]),
    )
    return result, settings


def test_a_replay_reproduces_the_whole_report(tmp_path: Path) -> None:
    live, settings = _live(tmp_path)
    assert len(live.documents) == 31, "the corpus should be all 31 golden documents"

    path = tmp_path / "run.predictions.json"
    dump_predictions(live, path)
    classifier, model, prompt_version = predictions_header(path)
    replayed = rescore(
        load_predictions(path),
        GOLDEN,
        CONFIG,
        classifier=classifier,
        model=model,
        prompt_version=prompt_version,
        usage=predictions_usage(path),
    )

    # Same documents, in the same order — a replayed report has to diff cleanly.
    assert [(d.property_id, d.doc_role) for d in replayed.documents] == [
        (d.property_id, d.doc_role) for d in live.documents
    ]
    live_overall, replayed_overall = live.overall(), replayed.overall()
    for metric in ("page", "continuation", "record", "orientation"):
        assert getattr(replayed_overall, metric) == getattr(live_overall, metric), metric
    assert replayed_overall.boundary == live_overall.boundary
    assert replayed.usage.api_calls == live.usage.api_calls

    # And the rendered report itself, which is what gets committed and diffed.
    def body(text: str) -> list[str]:
        return [ln for ln in text.splitlines() if "Run at" not in ln and "Duration" not in ln]

    assert body(render_report(replayed, settings, [])) == body(render_report(live, settings, []))
    assert report_filename(replayed).endswith(".md")
