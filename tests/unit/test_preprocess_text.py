"""Text extraction, normalisation and the text-layer probe (SPEC §6.2)."""

from __future__ import annotations

from pathlib import Path

from crr.preprocess.text import (
    MIN_CHARS_PER_PAGE,
    document_text_layer,
    has_text_layer,
    normalise_text,
    page_count,
    page_texts,
    sha256_file,
)
from tests.conftest import MakePdf


def test_normalise_collapses_horizontal_space_but_keeps_lines() -> None:
    raw = "Owner   Statement \t 07/01/26\n\n\n  rentmanager.com   rev.12  \n"
    assert normalise_text(raw) == "Owner Statement 07/01/26\nrentmanager.com rev.12"


def test_page_texts_are_capped(make_pdf: MakePdf) -> None:
    pdf = make_pdf("long.pdf", ["word " * 400])
    (text,) = page_texts(pdf, max_chars=50)
    assert len(text) == 50


def test_text_probe_threshold_is_ninety_percent_of_pages() -> None:
    rich = "x" * MIN_CHARS_PER_PAGE
    thin = "x" * (MIN_CHARS_PER_PAGE - 1)
    # 9 of 10 pages clear the bar -> exactly at the threshold, counts as a text layer.
    assert has_text_layer([rich] * 9 + [thin])
    # 8 of 10 does not.
    assert not has_text_layer([rich] * 8 + [thin] * 2)
    assert not has_text_layer([])


def test_a_page_needs_forty_non_whitespace_characters() -> None:
    spaced = " ".join("x" * (MIN_CHARS_PER_PAGE - 1))  # 39 characters, lots of spaces
    assert not has_text_layer([spaced])
    assert has_text_layer([spaced + " x"])


def test_document_text_layer_on_a_born_digital_pdf(make_pdf: MakePdf) -> None:
    pdf = make_pdf("digital.pdf", ["Owner Statement " * 6, "Financial Statement " * 6])
    texts, has_text = document_text_layer(pdf)
    assert has_text
    assert len(texts) == 2
    assert page_count(pdf) == 2


def test_sha256_is_content_addressed(make_pdf: MakePdf, tmp_path: Path) -> None:
    a = make_pdf("a.pdf", ["same bytes here"])
    copy = tmp_path / "copy.pdf"
    copy.write_bytes(a.read_bytes())
    assert sha256_file(a) == sha256_file(copy)
    assert len(sha256_file(a)) == 64
