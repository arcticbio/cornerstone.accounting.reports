"""The eval report (SPEC §8). Markdown, committed, and diffable between runs."""

from __future__ import annotations

from datetime import UTC, datetime

from crr.evaluate.harness import EvalResult
from crr.evaluate.metrics import Scores, Tally
from crr.settings import Settings


def _pct(tally: Tally) -> str:
    if tally.accuracy is None:
        return "—"
    return f"{tally.accuracy * 100:.2f}% ({tally.correct}/{tally.scored})"


def _f1(scores: Scores) -> str:
    value = scores.boundary.f1
    return "—" if value is None else f"{value:.4f}"


def report_filename(result: EvalResult) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    model = (result.model or result.classifier).replace(":", "-").replace("/", "-")
    return f"{stamp}-{model}-{result.prompt_version or 'na'}.md"


def render_report(result: EvalResult, settings: Settings, failures: list[str]) -> str:
    overall = result.overall()
    lines = [
        "# Classifier eval",
        "",
        f"- **Classifier:** `{result.classifier}`",
        f"- **Model:** `{result.model or '—'}`",
        f"- **Prompt version:** `{result.prompt_version or '—'}`",
        f"- **Run at:** {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"- **Documents:** {len(result.documents)} · "
        f"**Pages:** {overall.page.scored} · **Duration:** {result.duration_s:.1f}s",
        f"- **Thresholds:** page accuracy ≥ {settings.eval_min_page_accuracy}, "
        f"boundary F1 ≥ {settings.eval_min_boundary_f1}",
        "",
        "## Per manager",
        "",
        "| Manager | Pages | Page accuracy | Continuation | Record | Orientation | Boundary F1 |",
        "|---|---:|---|---|---|---|---|",
    ]
    for manager, scores in sorted(result.by_manager().items()):
        lines.append(
            f"| {manager} | {scores.page.scored} | {_pct(scores.page)} | "
            f"{_pct(scores.continuation)} | {_pct(scores.record)} | "
            f"{_pct(scores.orientation)} | {_f1(scores)} |"
        )
    lines.append(
        f"| **overall** | {overall.page.scored} | {_pct(overall.page)} | "
        f"{_pct(overall.continuation)} | {_pct(overall.record)} | "
        f"{_pct(overall.orientation)} | {_f1(overall)} |"
    )

    lines += [
        "",
        "## Per document",
        "",
        "| Property | Role | Pages | Page accuracy | Boundary F1 |",
        "|---|---|---:|---|---|",
    ]
    for doc in result.documents:
        lines.append(
            f"| {doc.property_id} | {doc.doc_role} | {doc.pages} | "
            f"{_pct(doc.scores.page)} | {_f1(doc.scores)} |"
        )

    pairs = result.confusion_pairs()
    lines += ["", "## Confusion pairs", ""]
    if pairs:
        lines += ["| Golden section | Predicted as | Pages |", "|---|---|---:|"]
        lines += [f"| {golden} | {predicted} | {count} |" for (golden, predicted), count in pairs]
    else:
        lines.append("None — every page was labelled as the golden file has it.")

    from crr.classify.anthropic_classifier import estimate_usd

    usd = estimate_usd(result.usage, result.model or "", settings) if result.model else 0.0
    lines += [
        "",
        "## Cost",
        "",
        "| Input | Cache read | Cache write | Output | API calls | USD estimate |",
        "|---:|---:|---:|---:|---:|---:|",
        f"| {result.usage.input_tokens} | {result.usage.cache_read_tokens} | "
        f"{result.usage.cache_write_tokens} | {result.usage.output_tokens} | "
        f"{result.usage.api_calls} | ${usd:.2f} |",
        "",
        "## Gate",
        "",
    ]
    if failures:
        lines.append("**Below threshold:**")
        lines.append("")
        lines += [f"- {failure}" for failure in failures]
    else:
        lines.append("All managers meet both thresholds.")
    lines.append("")
    return "\n".join(lines)
