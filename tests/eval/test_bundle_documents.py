"""Phase 1 acceptance: every golden document is on disk, has the page count the golden labels
claim, and probes as text-layer or not exactly where SPEC §6.2 says it should."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crr.preprocess.inspect import inspect_pdf

BUNDLE = Path("data/bundle/2026-06")
GOLDEN = Path("eval/golden")


def _documents() -> list[tuple[str, str, str, Path, int]]:
    out: list[tuple[str, str, str, Path, int]] = []
    for golden_file in sorted(GOLDEN.glob("*/*.json")):
        golden = json.loads(golden_file.read_text())
        for doc in golden["documents"]:
            out.append(
                (
                    golden["property_id"],
                    golden["pm_id"],
                    doc["role"],
                    BUNDLE / doc["file"],
                    len(doc["pages"]),
                )
            )
    return out


DOCUMENTS = _documents()


def test_the_bundle_holds_thirty_one_documents() -> None:
    assert len(DOCUMENTS) == 31
    assert sum(1 for d in DOCUMENTS if d[2] == "pm_source") == 8


@pytest.mark.parametrize(
    ("property_id", "pm_id", "role", "path", "golden_pages"),
    DOCUMENTS,
    ids=[f"{d[0]}-{d[2]}" for d in DOCUMENTS],
)
def test_page_count_and_text_layer_match_golden(
    property_id: str, pm_id: str, role: str, path: Path, golden_pages: int
) -> None:
    facts = inspect_pdf(path)
    assert facts.page_count == golden_pages
    # Only the two McCathren PM baselines are flat scans (ANALYSIS, D-04).
    expect_text = not (pm_id == "mccathren" and role == "pm_source")
    assert facts.has_text_layer is expect_text
