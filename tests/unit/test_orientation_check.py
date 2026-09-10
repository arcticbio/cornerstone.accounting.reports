"""The orientation cross-check (SPEC §7.6).

The defect these guard against: the classifier named the one rotated page in the corpus
`rotated_90_cw` when it is `rotated_90_ccw`, and the composer duly turned it 270° instead of
90°, shipping it upside down. Every other gate passed, because both rotations produce a page
of exactly the same shape.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crr.classify.orientation_check import apply_orientation_check
from crr.models import Orientation, PageClassification
from crr.preprocess import orientation as osd_module
from crr.preprocess.orientation import UNAVAILABLE, OsdVerdict, _parse

PDF = Path("does-not-matter.pdf")


def _page(page: int, orientation: Orientation) -> PageClassification:
    return PageClassification(
        doc_role="pm_source",
        page=page,
        section_id="aged_receivable",
        is_continuation=False,
        record_qualifier=None,
        orientation=orientation,
        confidence=0.96,
        evidence="title",
        classifier="test",
    )


@pytest.fixture
def osd(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Stub Tesseract: a dict of page -> verdict, so no subprocess runs in unit tests."""
    verdicts: dict[int, OsdVerdict] = {}

    def fake(pdf: Path, page: int, *, dpi: int = 400) -> OsdVerdict:
        return verdicts.get(page, UNAVAILABLE)

    monkeypatch.setattr("crr.classify.orientation_check.detect_orientation", fake)
    return verdicts


class TestParse:
    def test_reads_rotation_and_confidence(self) -> None:
        verdict = _parse("Orientation in degrees: 270\nRotate: 90\nOrientation confidence: 1.35\n")
        assert verdict.orientation is Orientation.ROT_90_CCW
        assert verdict.confidence == pytest.approx(1.35)

    @pytest.mark.parametrize(
        ("rotate", "expected"),
        [
            (0, Orientation.UPRIGHT),
            (90, Orientation.ROT_90_CCW),
            (180, Orientation.ROT_180),
            (270, Orientation.ROT_90_CW),
        ],
    )
    def test_rotate_is_the_correcting_turn(self, rotate: int, expected: Orientation) -> None:
        """Tesseract's `Rotate:` is the clockwise turn that fixes the page, which is exactly
        `correcting_rotation` — invert it and you get the orientation the page is in."""
        assert _parse(f"Rotate: {rotate}\n").orientation is expected
        assert expected.correcting_rotation == rotate

    def test_unparseable_output_is_unavailable(self) -> None:
        assert _parse("Too few characters. Skipping this page\n") is UNAVAILABLE
        assert _parse("Rotate: 45\n") is UNAVAILABLE

    def test_missing_tesseract_never_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(osd_module, "tesseract_available", lambda: False)
        assert osd_module.detect_orientation(PDF, 1) is UNAVAILABLE


class TestCrossCheck:
    def test_agreement_leaves_the_page_untouched(self, osd: dict[int, OsdVerdict]) -> None:
        osd[1] = OsdVerdict(Orientation.UPRIGHT, 2.4)
        pages, reasons = apply_orientation_check(
            [_page(1, Orientation.UPRIGHT)], PDF, doc_role="pm_source"
        )
        assert reasons == []
        assert pages[0].orientation is Orientation.UPRIGHT

    def test_arbiter_settles_a_disagreement(self, osd: dict[int, OsdVerdict]) -> None:
        """The real case: the model says cw, OSD says ccw, the arbiter picks ccw."""
        osd[3] = OsdVerdict(Orientation.ROT_90_CCW, 1.35)
        pages, reasons = apply_orientation_check(
            [_page(3, Orientation.ROT_90_CW)],
            PDF,
            doc_role="pm_source",
            arbiter=lambda pdf, page: Orientation.ROT_90_CCW,
        )
        assert reasons == []
        assert pages[0].orientation is Orientation.ROT_90_CCW
        assert pages[0].orientation.correcting_rotation == 90

    def test_arbiter_may_side_with_the_classifier(self, osd: dict[int, OsdVerdict]) -> None:
        """OSD is not authoritative either — it called eight upright pages `rotated_180`."""
        osd[9] = OsdVerdict(Orientation.ROT_180, 3.24)
        pages, reasons = apply_orientation_check(
            [_page(9, Orientation.UPRIGHT)],
            PDF,
            doc_role="pm_source",
            arbiter=lambda pdf, page: Orientation.UPRIGHT,
        )
        assert reasons == []
        assert pages[0].orientation is Orientation.UPRIGHT

    def test_unsettled_disagreement_goes_to_review(self, osd: dict[int, OsdVerdict]) -> None:
        osd[3] = OsdVerdict(Orientation.ROT_90_CCW, 1.35)
        pages, reasons = apply_orientation_check(
            [_page(3, Orientation.ROT_90_CW)], PDF, doc_role="pm_source", arbiter=None
        )
        assert [r.code for r in reasons] == ["orientation_uncertain"]
        assert reasons[0].page == 3
        # The label is left alone: review over guess (D-12).
        assert pages[0].orientation is Orientation.ROT_90_CW

    def test_arbiter_that_cannot_answer_goes_to_review(self, osd: dict[int, OsdVerdict]) -> None:
        osd[3] = OsdVerdict(Orientation.ROT_90_CCW, 1.35)
        _, reasons = apply_orientation_check(
            [_page(3, Orientation.ROT_90_CW)],
            PDF,
            doc_role="pm_source",
            arbiter=lambda pdf, page: None,
        )
        assert [r.code for r in reasons] == ["orientation_uncertain"]

    def test_no_osd_keeps_the_classifier_label(self, osd: dict[int, OsdVerdict]) -> None:
        """Without tesseract the build still runs, on SPEC §6.4's authority."""
        pages, reasons = apply_orientation_check(
            [_page(3, Orientation.ROT_90_CW)], PDF, doc_role="pm_source"
        )
        assert reasons == []
        assert pages[0].orientation is Orientation.ROT_90_CW

    def test_detail_never_carries_page_content(self, osd: dict[int, OsdVerdict]) -> None:
        """Review details are logged and committed; they name signals, not the page."""
        osd[3] = OsdVerdict(Orientation.ROT_90_CCW, 1.35)
        _, reasons = apply_orientation_check(
            [_page(3, Orientation.ROT_90_CW)], PDF, doc_role="pm_source"
        )
        assert "rotated_90_cw" in reasons[0].detail
        assert "rotated_90_ccw" in reasons[0].detail
