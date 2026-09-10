"""Shared fixtures. Synthetic PDFs are generated with reportlab so unit tests never touch
the bundle (SPEC §15)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas

MakePdf = Callable[..., Path]


def _write_pdf(
    path: Path,
    pages: Sequence[str],
    *,
    page_size: tuple[float, float] = letter,
    rotate: int = 0,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(path), pagesize=page_size)
    for body in pages:
        if rotate:
            pdf.rotate(rotate)
        text = pdf.beginText(40, page_size[1] - 60 if not rotate else 40)
        for line in body.splitlines():
            text.textLine(line)
        pdf.drawText(text)
        pdf.showPage()
    pdf.save()
    return path


@pytest.fixture
def make_pdf(tmp_path: Path) -> MakePdf:
    """Build a small text PDF: `make_pdf("a.pdf", ["page one", "page two"])`."""

    def _factory(
        name: str,
        pages: Sequence[str],
        *,
        page_size: tuple[float, float] = letter,
        rotate: int = 0,
    ) -> Path:
        return _write_pdf(tmp_path / name, pages, page_size=page_size, rotate=rotate)

    return _factory


@pytest.fixture
def landscape_letter() -> tuple[float, float]:
    return landscape(letter)
