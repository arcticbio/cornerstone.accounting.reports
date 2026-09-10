"""ocrmypdf wrapper (SPEC §6.2 step 2, D-10).

The OCR'd file replaces the source for every later stage *and* is what gets composed, so a
McCathren package ships searchable. ocrmypdf is invoked as a subprocess — it is a system tool
(tesseract + ghostscript), not a library dependency of this package.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from crr.log import get_logger

log = get_logger(__name__)

#: The ocrmypdf entry point. Overridable with CRR_OCRMYPDF_BIN for environments where the
#: distribution entry point is broken or lives off PATH (SPEC §12).
OCRMYPDF_BIN = os.environ.get("CRR_OCRMYPDF_BIN", "ocrmypdf")

#: SPEC §6.2: skip pages that already carry text, let ocrmypdf take a first pass at
#: orientation, and keep the output a plain PDF rather than PDF/A.
OCR_ARGS = ("--skip-text", "--rotate-pages", "--optimize", "1", "--output-type", "pdf")

_TIMEOUT_S = 1800


class OcrError(RuntimeError):
    """OCR could not be run, or ocrmypdf failed. Never swallowed: a McCathren build that
    cannot OCR fails with a clear message rather than silently shipping an image-only PDF
    (QUESTIONS.md, pre-answered defaults)."""


@dataclass(frozen=True)
class OcrResult:
    path: Path
    version: str
    rotated_pages: bool
    skipped: bool = False


def ocrmypdf_version(bin_path: str | None = None) -> str:
    """Version string of the installed ocrmypdf, or raise OcrError if it cannot be run."""
    exe = bin_path or OCRMYPDF_BIN
    if shutil.which(exe) is None:
        raise OcrError(
            f"{exe!r} is not on PATH. Install it with: apt-get install -y tesseract-ocr "
            "tesseract-ocr-eng tesseract-ocr-osd ocrmypdf ghostscript"
        )
    try:
        proc = subprocess.run(  # fixed argv, no shell
            [exe, "--version"], capture_output=True, text=True, timeout=60, check=False
        )
    except OSError as exc:  # pragma: no cover - depends on a broken install
        raise OcrError(f"could not run {exe}: {exc}") from exc
    if proc.returncode != 0:
        raise OcrError(f"{exe} --version exited {proc.returncode}: {proc.stderr.strip()[:400]}")
    return proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else "unknown"


def _page_rotations(pdf: Path) -> list[int]:
    reader = PdfReader(str(pdf))
    return [int(page.get("/Rotate", 0) or 0) % 360 for page in reader.pages]


def ocr_pdf(
    src: Path,
    dest: Path,
    *,
    bin_path: str | None = None,
    extra_args: tuple[str, ...] = (),
) -> OcrResult:
    """Run ocrmypdf over `src`, writing `dest`. Returns the version and whether
    `--rotate-pages` changed any page's /Rotate value."""
    exe = bin_path or OCRMYPDF_BIN
    version = ocrmypdf_version(exe)
    dest.parent.mkdir(parents=True, exist_ok=True)
    argv = [exe, *OCR_ARGS, *extra_args, str(src), str(dest)]
    log.info("ocr.start", version=version, args=list(OCR_ARGS + extra_args))
    try:
        proc = subprocess.run(  # fixed argv, no shell
            argv, capture_output=True, text=True, timeout=_TIMEOUT_S, check=False
        )
    except subprocess.TimeoutExpired as exc:  # pragma: no cover - long-running failure path
        raise OcrError(f"ocrmypdf timed out after {_TIMEOUT_S}s") from exc
    if proc.returncode != 0 or not dest.exists():
        stderr = _redact(proc.stderr)
        raise OcrError(f"ocrmypdf exited {proc.returncode}: {stderr[:600]}")
    rotated = _page_rotations(src) != _page_rotations(dest)
    log.info("ocr.done", rotated_pages=rotated)
    return OcrResult(path=dest, version=version, rotated_pages=rotated)


def ocr_if_needed(
    src: Path,
    dest: Path,
    *,
    has_text_layer: bool,
    enabled: bool,
    bin_path: str | None = None,
) -> OcrResult:
    """Run OCR only when the output definition asks for it and the document has no text layer
    (SPEC §6.2 step 2). Otherwise return a skipped result pointing at the untouched source."""
    if not enabled or has_text_layer:
        log.info("ocr.skip", enabled=enabled, has_text_layer=has_text_layer)
        return OcrResult(path=src, version="", rotated_pages=False, skipped=True)
    return ocr_pdf(src, dest, bin_path=bin_path)


_PATHish = re.compile(r"(/[^\s'\"]{4,})")


def _redact(stderr: str) -> str:
    """ocrmypdf echoes file paths, which carry tenant and property names (SPEC §16)."""
    return _PATHish.sub("<path>", stderr).strip()
