"""Page rendering with pypdfium2 (SPEC §6.2 step 3, D-10).

150 DPI, RGB, PNG, one file per page, long edge capped at 1568 px — Anthropic's resize
threshold — so the model sees exactly the image that is cached on disk. Rendered pages are
cached by (sha256, page, dpi, max_edge): re-running a build never re-rasterises.
"""

from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium

from crr.log import get_logger

log = get_logger(__name__)

DEFAULT_DPI = 150
DEFAULT_MAX_EDGE_PX = 1568
_PDF_POINTS_PER_INCH = 72.0


def _cache_name(sha256: str, page: int, dpi: int, max_edge: int) -> str:
    return f"{sha256[:16]}-p{page:04d}-{dpi}dpi-{max_edge}px.png"


def scale_for(width_pt: float, height_pt: float, dpi: int, max_edge: int) -> float:
    """Points-to-pixels scale at `dpi`, reduced so the long edge fits `max_edge`."""
    scale = dpi / _PDF_POINTS_PER_INCH
    long_edge_px = max(width_pt, height_pt) * scale
    if long_edge_px > max_edge:
        scale *= max_edge / long_edge_px
    return scale


def render_pages(
    pdf: Path,
    sha256: str,
    dest: Path,
    pages: list[int] | None = None,
    dpi: int = DEFAULT_DPI,
    max_edge: int = DEFAULT_MAX_EDGE_PX,
) -> dict[int, Path]:
    """Render `pages` (1-based; all pages when None) of `pdf` into `dest`.

    Returns a mapping of page number to PNG path. Existing cache entries are reused.
    """
    dest.mkdir(parents=True, exist_ok=True)
    doc = pdfium.PdfDocument(str(pdf))
    try:
        wanted = pages if pages is not None else list(range(1, len(doc) + 1))
        out: dict[int, Path] = {}
        rendered = 0
        for page_no in wanted:
            target = dest / _cache_name(sha256, page_no, dpi, max_edge)
            out[page_no] = target
            if target.exists():
                continue
            page = doc[page_no - 1]
            try:
                scale = scale_for(page.get_width(), page.get_height(), dpi, max_edge)
                bitmap = page.render(scale=scale, rev_byteorder=False, draw_annots=True)
                try:
                    image = bitmap.to_pil().convert("RGB")
                    image.save(target, format="PNG")
                finally:
                    bitmap.close()
            finally:
                page.close()
            rendered += 1
        log.info(
            "render.pages",
            sha256=sha256,
            pages=len(wanted),
            rendered=rendered,
            dpi=dpi,
            max_edge=max_edge,
        )
        return out
    finally:
        doc.close()


def render_page(
    pdf: Path,
    sha256: str,
    dest: Path,
    page: int,
    dpi: int = DEFAULT_DPI,
    max_edge: int = DEFAULT_MAX_EDGE_PX,
) -> Path:
    """Render a single 1-based page; returns its PNG path."""
    return render_pages(pdf, sha256, dest, pages=[page], dpi=dpi, max_edge=max_edge)[page]
