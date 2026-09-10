"""PDF composition (SPEC §6.6).

Deterministic: the same plan over the same inputs produces the same bytes apart from
`/CreationDate` (SPEC §9.4). Nothing here reads a path under `reference/` or `target/` —
the composer only ever opens the files named in the plan (SPEC §9.3).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from crr import __version__
from crr.log import get_logger
from crr.models import PlanItem

log = get_logger(__name__)

PRODUCER = f"Cornerstone Report Runner {__version__}"
ROTATE_PREFIX = "rotate:"


@dataclass(frozen=True)
class ComposedOutput:
    path: Path
    page_count: int
    bookmarks: tuple[str, ...]


def output_filename(property_name: str, period_label: str) -> str:
    """`"<Property> - Investor Report - <Month YYYY>.pdf"` (SPEC §6.6)."""
    return f"{property_name} - Investor Report - {period_label}.pdf"


def rotation_for(item: PlanItem) -> int:
    """The clockwise rotation this plan item asks for, or 0."""
    for transform in item.transforms:
        if transform.startswith(ROTATE_PREFIX):
            return int(transform[len(ROTATE_PREFIX) :]) % 360
    return 0


def compose(
    plan: list[PlanItem],
    sources: dict[str, Path],
    dest: Path,
    *,
    title: str,
    add_bookmarks: bool = True,
    created_at: datetime | None = None,
) -> ComposedOutput:
    """Write the output PDF for `plan`.

    `sources` maps doc_role → the file to copy pages from. For a document that was OCR'd, that
    is the OCR'd file: the OCR output *is* what gets composed, so the package ships searchable
    (D-10).
    """
    if not plan:
        raise ValueError("cannot compose an empty plan")
    missing = sorted({item.doc_role for item in plan} - set(sources))
    if missing:
        raise KeyError(f"no source file for doc_role(s): {', '.join(missing)}")

    readers = {role: PdfReader(str(path)) for role, path in sources.items()}
    writer = PdfWriter()
    bookmarks: list[str] = []

    for index, item in enumerate(plan):
        reader = readers[item.doc_role]
        if not 1 <= item.source_page <= len(reader.pages):
            raise IndexError(
                f"{item.doc_role} has {len(reader.pages)} pages; plan asks for page "
                f"{item.source_page}"
            )
        page = writer.add_page(reader.pages[item.source_page - 1])
        rotation = rotation_for(item)
        if rotation:
            page.rotate(rotation)
        if add_bookmarks and item.bookmark:
            writer.add_outline_item(item.bookmark, index)
            bookmarks.append(item.bookmark)

    writer.add_metadata(
        {
            "/Title": title,
            "/Producer": PRODUCER,
            "/Creator": PRODUCER,
            "/CreationDate": _pdf_date(created_at or datetime.now(UTC)),
        }
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as fh:
        writer.write(fh)
    log.info("compose.done", pages=len(plan), bookmarks=len(bookmarks))
    return ComposedOutput(path=dest, page_count=len(plan), bookmarks=tuple(bookmarks))


def _pdf_date(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("D:%Y%m%d%H%M%SZ")
