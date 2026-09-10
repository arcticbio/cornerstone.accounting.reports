"""Rendering: DPI, the 1568 px long-edge cap and the render cache (SPEC §6.2 step 3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from crr.preprocess.render import DEFAULT_MAX_EDGE_PX, render_page, render_pages
from crr.preprocess.text import sha256_file
from tests.conftest import MakePdf


def test_letter_page_at_150_dpi_is_not_capped(make_pdf: MakePdf, tmp_path: Path) -> None:
    pdf = make_pdf("one.pdf", ["hello"])
    png = render_page(pdf, sha256_file(pdf), tmp_path / "pages", page=1)
    with Image.open(png) as img:
        # 612x792 pt at 150 dpi = 1275x1650 px; the long edge is capped at 1568.
        assert max(img.size) == DEFAULT_MAX_EDGE_PX
        assert img.mode == "RGB"


def test_long_edge_cap_preserves_aspect_ratio(make_pdf: MakePdf, tmp_path: Path) -> None:
    pdf = make_pdf("wide.pdf", ["hello"], page_size=(1800.0, 600.0))
    png = render_page(pdf, sha256_file(pdf), tmp_path / "pages", page=1)
    with Image.open(png) as img:
        width, height = img.size
    assert width == DEFAULT_MAX_EDGE_PX
    assert height == pytest.approx(DEFAULT_MAX_EDGE_PX * 600 / 1800, abs=1)


def test_a_small_page_is_rendered_at_full_dpi(make_pdf: MakePdf, tmp_path: Path) -> None:
    pdf = make_pdf("small.pdf", ["hello"], page_size=(288.0, 288.0))  # 4x4 inch
    png = render_page(pdf, sha256_file(pdf), tmp_path / "pages", page=1, dpi=150)
    with Image.open(png) as img:
        assert img.size == (600, 600)


def test_render_is_cached_by_sha_page_and_dpi(make_pdf: MakePdf, tmp_path: Path) -> None:
    pdf = make_pdf("two.pdf", ["one", "two"])
    sha = sha256_file(pdf)
    dest = tmp_path / "pages"
    first = render_pages(pdf, sha, dest)
    assert set(first) == {1, 2}
    mtimes = {p: first[p].stat().st_mtime_ns for p in first}

    second = render_pages(pdf, sha, dest)
    assert second == first
    assert {p: second[p].stat().st_mtime_ns for p in second} == mtimes  # not re-rasterised

    # A different DPI is a different cache entry.
    other = render_pages(pdf, sha, dest, dpi=72)
    assert other[1] != first[1]


def test_render_selected_pages_only(make_pdf: MakePdf, tmp_path: Path) -> None:
    pdf = make_pdf("three.pdf", ["a", "b", "c"])
    out = render_pages(pdf, sha256_file(pdf), tmp_path / "pages", pages=[2])
    assert set(out) == {2}
    assert len(list((tmp_path / "pages").iterdir())) == 1
