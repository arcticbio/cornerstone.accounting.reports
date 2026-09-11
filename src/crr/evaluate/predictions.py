"""Saving and replaying an eval's per-page predictions (SPEC §8).

`crr eval` throws its labels away with the process, so correcting a *metric* used to cost a
fresh keyed run: the two defects in A-09 and A-10 cost $4.66 and $1.97 to re-measure, on labels
that had not changed at all. The predictions are the expensive part of an eval and the scoring
is pure — so the labels are written beside the report, and `crr eval --from <file>` re-scores
them offline, free and in seconds.

`evidence` is dropped on the way out. It is a model-written sentence about the page, and these
files are committed; SPEC §15 keeps page text out of the repository. Nothing scores it.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from crr.classify.protocol import Usage
from crr.models import PageClassification

FORMAT_VERSION = 1
#: Not persisted: a sentence of model-written page description, and nothing scores it.
DROPPED_FIELDS = ("evidence",)


def predictions_filename(report_name: str) -> str:
    """`<report stem>.predictions.json`, so a report and its labels sort together."""
    return f"{Path(report_name).stem}.predictions.json"


def dump_predictions(result: Any, path: Path) -> None:
    """Write every document's labels beside the report it was scored into."""
    payload = {
        "format_version": FORMAT_VERSION,
        "classifier": result.classifier,
        "model": result.model,
        "prompt_version": result.prompt_version,
        "written_at": datetime.now(UTC).isoformat(timespec="seconds"),
        # Carried so a replayed report still states what the run actually cost. A replay
        # itself calls nothing; the number belongs to the run that produced these labels.
        "usage": asdict(result.usage),
        "documents": [
            {
                "property_id": document.property_id,
                "pm_id": document.pm_id,
                "doc_role": document.doc_role,
                "schema_id": document.schema_id,
                "pages": [_page(page) for page in document.predictions],
            }
            for document in result.documents
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _page(page: PageClassification) -> dict[str, Any]:
    row = page.model_dump(mode="json")
    for field in DROPPED_FIELDS:
        row.pop(field, None)
    return row


def load_predictions(path: Path) -> dict[tuple[str, str], list[PageClassification]]:
    """`(property_id, doc_role)` → labels, for re-scoring without calling the model."""
    payload = json.loads(path.read_text())
    version = payload.get("format_version")
    if version != FORMAT_VERSION:
        raise ValueError(
            f"{path}: predictions format_version {version!r}, expected {FORMAT_VERSION}"
        )
    out: dict[tuple[str, str], list[PageClassification]] = {}
    for document in payload["documents"]:
        key = (document["property_id"], document["doc_role"])
        out[key] = [
            PageClassification(evidence="", **page)
            if "evidence" not in page
            else PageClassification(**page)
            for page in document["pages"]
        ]
    return out


def predictions_header(path: Path) -> tuple[str, str | None, str | None]:
    """`(classifier, model, prompt_version)` of a saved run, for the replayed report."""
    payload = json.loads(path.read_text())
    return payload["classifier"], payload.get("model"), payload.get("prompt_version")


def predictions_usage(path: Path) -> Usage:
    """What the saved run cost. A file written before usage was carried reports zero."""
    saved = json.loads(path.read_text()).get("usage") or {}
    fields = {f: saved[f] for f in Usage().__dict__ if f in saved}
    return Usage(**fields)
