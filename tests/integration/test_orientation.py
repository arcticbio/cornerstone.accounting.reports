"""Tesseract OSD against the real corpus (SPEC §7.6).

The golden-build fixtures switch `orientation_check` off for speed, so this is the only place
the real detector meets a real page. It is deliberately narrow: the one rotated page in the
bundle, and a handful of upright ones for false positives.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crr.models import Orientation
from crr.preprocess.orientation import detect_orientation, tesseract_available

BUNDLE = Path("data/bundle/2026-06")
TIMBER = (
    BUNDLE
    / "McCathren Management and Real Estate Services/Timber Place/2026-06 June/inputs"
    / "05 PM Source - McCathren Baseline.pdf"
)

pytestmark = [
    pytest.mark.skipif(not tesseract_available(), reason="tesseract not installed"),
    pytest.mark.skipif(not TIMBER.exists(), reason="bundle fixture not present"),
]


def test_the_rotated_page_is_read_as_ccw() -> None:
    """Timber Place page 3, the aged receivable, is turned counter-clockwise.

    The vision classifier calls this `rotated_90_cw` — the opposite — at 0.96 confidence, so
    the composer turned it 270° and shipped it upside down. OSD reads it correctly, which is
    what the cross-check is built on.
    """
    verdict = detect_orientation(TIMBER, 3)
    assert verdict.orientation is Orientation.ROT_90_CCW
    assert verdict.orientation.correcting_rotation == 90


@pytest.mark.parametrize("page", [1, 2, 4, 17])
def test_upright_pages_are_not_flagged(page: int) -> None:
    """False positives cost real builds: at 150 DPI with an ink crop this detector called
    eight upright pages `rotated_180`, some with high confidence."""
    assert detect_orientation(TIMBER, page).orientation is Orientation.UPRIGHT


def test_golden_orientation_matches_osd_on_every_labelled_page() -> None:
    """Every page golden bothers to label an orientation for, OSD must agree with."""
    labelled: list[tuple[Path, int, str]] = []
    for golden_file in sorted(Path("eval/golden").glob("*/*.json")):
        golden = json.loads(golden_file.read_text())
        for doc in golden["documents"]:
            for page in doc["pages"]:
                if page.get("orientation"):
                    labelled.append((BUNDLE / doc["file"], page["page"], page["orientation"]))
    assert labelled, "no golden page carries an orientation"
    for pdf, page, expected in labelled:
        verdict = detect_orientation(pdf, page)
        assert verdict.orientation is Orientation(expected), (pdf.name, page)
