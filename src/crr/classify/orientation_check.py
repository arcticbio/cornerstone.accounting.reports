"""The orientation cross-check (SPEC §7.6).

Two independent signals must agree before the composer turns a page:

1. the vision classifier's `orientation`, produced with the rest of the page label, and
2. Tesseract OSD on a fresh 400 DPI render (`crr.preprocess.orientation`).

Neither is trustworthy alone — see the module docstring there for what each gets wrong — but
they fail differently, so agreement is strong evidence and disagreement is a genuine question.
A disagreement is put to an *arbiter*, which does not ask what rotation the page is in but
shows the page in all four rotations and asks which one reads normally. That is a
discrimination, not a mental rotation, and the model is reliable at it: 12 of 12 over upright
and rotated pages with the options shuffled, including the page it names wrongly every time.

With no arbiter available (no key, or the golden classifier) a disagreement keeps the
classifier's label — SPEC §6.4's authority — and raises `orientation_uncertain`, so the package
goes to a human rather than shipping on a coin toss (D-12).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from crr.log import get_logger
from crr.models import Orientation, PageClassification, ReviewReason
from crr.preprocess.orientation import DEFAULT_OSD_DPI, detect_orientation

log = get_logger(__name__)


class OrientationArbiter(Protocol):
    """Settles a disagreement about one page. Returns None when it cannot."""

    def __call__(self, pdf: Path, page: int) -> Orientation | None: ...


def apply_orientation_check(
    classifications: list[PageClassification],
    pdf: Path,
    *,
    doc_role: str,
    dpi: int = DEFAULT_OSD_DPI,
    arbiter: OrientationArbiter | None = None,
) -> tuple[list[PageClassification], list[ReviewReason]]:
    """Correct or flag every page whose two orientation signals disagree.

    Returns the (possibly corrected) labels and any `orientation_uncertain` reasons. Pages the
    two signals agree on are returned untouched, which is all but a handful of any real build.
    """
    out: list[PageClassification] = []
    reasons: list[ReviewReason] = []
    for page in classifications:
        verdict = detect_orientation(pdf, page.page, dpi=dpi)
        osd = verdict.orientation
        if osd is None or osd is page.orientation:
            out.append(page)
            continue

        settled = arbiter(pdf, page.page) if arbiter is not None else None
        log.info(
            "classify.orientation_disagreement",
            doc_role=doc_role,
            page=page.page,
            classifier=page.orientation.value,
            osd=osd.value,
            osd_confidence=round(verdict.confidence, 2),
            arbiter=settled.value if settled is not None else None,
        )
        if settled is None:
            out.append(page)
            reasons.append(
                ReviewReason(
                    code="orientation_uncertain",
                    doc_role=doc_role,
                    page=page.page,
                    detail=(
                        f"classifier says {page.orientation.value}, "
                        f"OSD says {osd.value} "
                        f"(confidence {verdict.confidence:.2f}); not settled"
                    ),
                )
            )
            continue
        out.append(page.model_copy(update={"orientation": settled}))
    return out, reasons
