"""Deterministic page-orientation detection with Tesseract OSD (SPEC §7.6).

The vision classifier is unreliable at *naming* a rotation: on the one rotated page in the
golden corpus it answered `rotated_90_cw` where the truth is `rotated_90_ccw` — the opposite
direction — with 0.96 confidence, and kept doing so under two rewrites of the prompt rule. A
wrong name is worse than no name: the composer applies the complementary rotation and the page
ships upside down, past every gate, because the page box comes out the right shape either way.

Tesseract's orientation-and-script detection has no such trouble. It agreed with every one of
the 172 golden pages at 400 DPI. It is, however, sensitive to what it is handed: the same
detector run over the 150 DPI classifier images, ink-cropped and upscaled, called eight upright
pages `rotated_180`, three of them with a *higher* confidence than it reported for the page it
got right. So this module renders the page fresh at its own DPI and does nothing clever to it,
and callers must not treat the confidence as a safety margin — `orientation_check` requires a
second, independent signal to agree before any rotation is applied.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium

from crr.log import get_logger
from crr.models import Orientation

log = get_logger(__name__)

#: Tesseract's own default is 300; 400 is what the golden corpus was measured at.
DEFAULT_OSD_DPI = 400
_PDF_POINTS_PER_INCH = 72.0

#: Tesseract reports `Rotate: N`, the *clockwise* turn that would bring the page upright. That
#: is `Orientation.correcting_rotation`, so the mapping is its inverse.
_ROTATE_TO_ORIENTATION = {
    0: Orientation.UPRIGHT,
    90: Orientation.ROT_90_CCW,
    180: Orientation.ROT_180,
    270: Orientation.ROT_90_CW,
}


@dataclass(frozen=True)
class OsdVerdict:
    """What Tesseract made of one page, or that it could not be asked."""

    orientation: Orientation | None
    confidence: float = 0.0

    @property
    def available(self) -> bool:
        return self.orientation is not None


UNAVAILABLE = OsdVerdict(orientation=None)


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def _parse(stdout: str) -> OsdVerdict:
    rotate: int | None = None
    confidence = 0.0
    for line in stdout.splitlines():
        if line.startswith("Rotate:"):
            try:
                rotate = int(line.split(":", 1)[1])
            except ValueError:
                return UNAVAILABLE
        elif line.startswith("Orientation confidence:"):
            try:
                confidence = float(line.split(":", 1)[1])
            except ValueError:
                confidence = 0.0
    if rotate is None or rotate not in _ROTATE_TO_ORIENTATION:
        return UNAVAILABLE
    return OsdVerdict(orientation=_ROTATE_TO_ORIENTATION[rotate], confidence=confidence)


def detect_orientation(pdf: Path, page: int, *, dpi: int = DEFAULT_OSD_DPI) -> OsdVerdict:
    """Tesseract's reading of how page `page` (1-based) of `pdf` is turned.

    Returns `UNAVAILABLE` — never raises — when tesseract is missing, times out, or answers
    something unparseable. A build without OSD keeps the classifier's label; it does not fail.
    """
    if not tesseract_available():
        return UNAVAILABLE
    try:
        document = pdfium.PdfDocument(str(pdf))
        try:
            pdf_page = document[page - 1]
            image = pdf_page.render(scale=dpi / _PDF_POINTS_PER_INCH).to_pil().convert("L")
        finally:
            document.close()
        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "page.png"
            image.save(png)
            # Fixed argv, no shell, and the only path is one we just wrote.
            completed = subprocess.run(
                ["tesseract", str(png), "-", "--psm", "0", "--dpi", str(dpi)],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
    except (OSError, subprocess.SubprocessError, pdfium.PdfiumError) as exc:
        log.warning("orientation.osd_failed", page=page, error=type(exc).__name__)
        return UNAVAILABLE
    return _parse(completed.stdout)
