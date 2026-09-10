"""`REVIEW.md` — the plain-language review surface (SPEC §6.9, §17)."""

from __future__ import annotations

from collections import defaultdict

from crr.manifest.model import BuildManifest
from crr.models import ReviewReason
from crr.review.rules import EXPLANATIONS


def render_review(manifest: BuildManifest) -> str:
    """A short document a human can act on without reading the manifest JSON."""
    lines: list[str] = [
        f"# Review needed — {manifest.property.name}, {manifest.period}",
        "",
        f"The package was built but held back from `output/` because of "
        f"{len(manifest.review_reasons)} finding(s). Nothing was guessed: every item below is "
        "a decision the system declined to make on its own.",
        "",
        f"- **Property:** {manifest.property.name} ({manifest.property.id})",
        f"- **Manager:** {manifest.property.property_manager}",
        f"- **Owning entity:** {manifest.property.owning_entity}",
        f"- **Built at:** {manifest.built_at.isoformat()}",
        f"- **Classifier:** {manifest.classifier.name}",
        f"- **Pages in the package:** {len(manifest.plan)}",
        "",
    ]

    grouped: dict[str, list[ReviewReason]] = defaultdict(list)
    for reason in manifest.review_reasons:
        grouped[reason.code].append(reason)

    lines.append("## What to look at")
    lines.append("")
    for code, reasons in grouped.items():
        lines.append(f"### {code.replace('_', ' ').capitalize()} ({len(reasons)})")
        lines.append("")
        lines.append(EXPLANATIONS.get(code, "No explanation recorded for this code."))
        lines.append("")
        lines.append("| Document | Page | Detail |")
        lines.append("|---|---|---|")
        for reason in reasons:
            page = str(reason.page) if reason.page else "—"
            lines.append(f"| {reason.doc_role or '—'} | {page} | {reason.detail or '—'} |")
        lines.append("")

    lines.extend(
        [
            "## The inputs this was built from",
            "",
            "| Role | Pages | Text layer | OCR | sha256 |",
            "|---|---|---|---|---|",
        ]
    )
    for source in manifest.inputs:
        lines.append(
            f"| {source.role} | {source.pages} | {'yes' if source.has_text_layer else 'no'} | "
            f"{'yes' if source.ocr_applied else 'no'} | `{source.sha256[:12]}` |"
        )
    lines.extend(
        [
            "",
            "## What to do next",
            "",
            "1. Open the PDF beside this file and check the pages listed above.",
            "2. If the package is right, move it to `output/` by hand.",
            "3. If a label is wrong, the fix belongs in config — a schema's `visual_cues` or "
            "the output definition's `flow`/`drop` — not in the PDF.",
            "",
            "`build-manifest.json` beside this file records every page label, the resolved "
            "sections and the exact page plan.",
            "",
        ]
    )
    return "\n".join(lines)
