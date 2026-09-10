"""Document inspection: the facts `crr inspect` prints and the pipeline needs (SPEC §11)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict
from pypdf import PdfReader

from crr.preprocess.text import (
    MIN_CHARS_PER_PAGE,
    document_text_layer,
    has_text_layer,
    sha256_file,
)


class PageFacts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    page: int
    width_pt: float
    height_pt: float
    rotate: int
    #: Effective size after /Rotate, i.e. what a reader displays.
    effective_width_pt: float
    effective_height_pt: float
    text_chars: int
    #: Last non-empty line of page text; the footer is the classifier's cross-check (SPEC §7.4).
    footer_line: str | None


class DocumentFacts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: Path
    sha256: str
    page_count: int
    has_text_layer: bool
    pages: tuple[PageFacts, ...]

    @property
    def is_landscape_dominant(self) -> bool:
        landscape = sum(1 for p in self.pages if p.effective_width_pt > p.effective_height_pt)
        return landscape * 2 > len(self.pages)


def _footer_line(text: str) -> str | None:
    """The last line of the page text. pypdf emits pages in content order, so the printed
    footer is the last line for every producer in this bundle."""
    lines = text.splitlines()
    return lines[-1] if lines else None


def inspect_pdf(pdf: Path, max_chars: int = 6_000) -> DocumentFacts:
    """Page geometry, text-layer probe and footer lines for one PDF."""
    texts, doc_has_text = document_text_layer(pdf, max_chars=max_chars)
    reader = PdfReader(str(pdf))
    pages: list[PageFacts] = []
    for index, page in enumerate(reader.pages, start=1):
        box = page.mediabox
        width, height = float(box.width), float(box.height)
        rotate = int(page.get("/Rotate", 0) or 0) % 360
        eff_w, eff_h = (height, width) if rotate in (90, 270) else (width, height)
        text = texts[index - 1] if index <= len(texts) else ""
        pages.append(
            PageFacts(
                page=index,
                width_pt=width,
                height_pt=height,
                rotate=rotate,
                effective_width_pt=eff_w,
                effective_height_pt=eff_h,
                text_chars=len(text.replace(" ", "").replace("\n", "")),
                footer_line=_footer_line(text),
            )
        )
    return DocumentFacts(
        path=pdf,
        sha256=sha256_file(pdf),
        page_count=len(reader.pages),
        has_text_layer=doc_has_text,
        pages=tuple(pages),
    )


__all__ = ["MIN_CHARS_PER_PAGE", "DocumentFacts", "PageFacts", "has_text_layer", "inspect_pdf"]
