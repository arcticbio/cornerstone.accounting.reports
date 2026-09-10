"""Page text extraction and the text-layer probe (SPEC §6.2).

Page text is tenant data: it is returned to callers, never logged (SPEC §11, §16).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from pypdf import PdfReader

#: A page counts towards the text layer when it yields at least this many non-whitespace
#: characters (SPEC §6.2 step 1).
MIN_CHARS_PER_PAGE = 40

#: A document has a text layer when at least this fraction of its pages clear the bar.
TEXT_LAYER_PAGE_FRACTION = 0.9

_WHITESPACE = re.compile(r"\s+")
_HORIZONTAL_WS = re.compile(r"[^\S\n]+")


def normalise_text(text: str) -> str:
    """Collapse horizontal whitespace and drop blank lines, keeping the line structure.

    Lines matter: the footer check (SPEC §7.4) reads the report name off the last line of a
    page, so flattening newlines away would cost it its only anchor.
    """
    lines = (_HORIZONTAL_WS.sub(" ", line).strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def sha256_file(path: Path) -> str:
    """Content hash of a file, streamed."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def page_texts(pdf: Path, max_chars: int = 6_000) -> list[str]:
    """Normalised text for every page, capped at `max_chars` (SPEC §6.2 step 4)."""
    reader = PdfReader(str(pdf))
    out: list[str] = []
    for page in reader.pages:
        try:
            raw = page.extract_text() or ""
        except Exception:  # a malformed page must not cost us the whole document
            raw = ""
        out.append(normalise_text(raw)[:max_chars])
    return out


def _non_whitespace_len(text: str) -> int:
    return len(_WHITESPACE.sub("", text))


def has_text_layer(texts: list[str]) -> bool:
    """True when >= 90 % of pages yield >= 40 non-whitespace characters."""
    if not texts:
        return False
    good = sum(1 for t in texts if _non_whitespace_len(t) >= MIN_CHARS_PER_PAGE)
    return good / len(texts) >= TEXT_LAYER_PAGE_FRACTION


def document_text_layer(pdf: Path, max_chars: int = 6_000) -> tuple[list[str], bool]:
    """Return (per-page text, has_text_layer) in one pass."""
    texts = page_texts(pdf, max_chars=max_chars)
    return texts, has_text_layer(texts)


def page_count(pdf: Path) -> int:
    """Number of pages, without extracting any text."""
    return len(PdfReader(str(pdf)).pages)
