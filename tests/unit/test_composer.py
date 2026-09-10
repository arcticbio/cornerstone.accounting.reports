"""The composer: rotation, bookmarks, metadata, filename, determinism (SPEC §6.6, §9)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pypdf import PdfReader
from reportlab.lib.pagesizes import letter

from crr.compose.composer import compose, output_filename, rotation_for
from crr.models import PlanItem
from tests.conftest import MakePdf


def _item(output_page: int, source_page: int, **kwargs: object) -> PlanItem:
    return PlanItem(
        output_page=output_page,
        doc_role=kwargs.pop("doc_role", "pm_source"),  # type: ignore[arg-type]
        source_page=source_page,
        section_id=kwargs.pop("section_id", "owner_statement"),  # type: ignore[arg-type]
        record_id=None,
        **kwargs,  # type: ignore[arg-type]
    )


def test_output_filename_matches_the_spec() -> None:
    assert output_filename("WayPointe", "June 2026") == (
        "WayPointe - Investor Report - June 2026.pdf"
    )


def test_pages_are_placed_in_plan_order(make_pdf: MakePdf, tmp_path: Path) -> None:
    src = make_pdf("src.pdf", ["alpha", "beta", "gamma"])
    plan = [_item(1, 3), _item(2, 1)]
    out = compose(plan, {"pm_source": src}, tmp_path / "out.pdf", title="T")
    reader = PdfReader(str(out.path))
    assert out.page_count == 2
    assert "gamma" in (reader.pages[0].extract_text() or "")
    assert "alpha" in (reader.pages[1].extract_text() or "")


def test_rotation_is_applied_and_the_mediabox_is_preserved(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    src = make_pdf("src.pdf", ["sideways"])
    plan = [_item(1, 1, transforms=("copy", "rotate:90"))]
    out = compose(plan, {"pm_source": src}, tmp_path / "out.pdf", title="T")
    page = PdfReader(str(out.path)).pages[0]
    assert int(page["/Rotate"]) == 90
    # The box is untouched; only the display rotation changes.
    assert (float(page.mediabox.width), float(page.mediabox.height)) == letter


@pytest.mark.parametrize(
    ("transforms", "expected"),
    [(("copy",), 0), (("copy", "rotate:270"), 270), (("ocr", "rotate:180"), 180)],
)
def test_rotation_for_reads_the_transform_list(transforms: tuple[str, ...], expected: int) -> None:
    assert rotation_for(_item(1, 1, transforms=transforms)) == expected


def test_a_bookmark_per_section_at_its_first_page(make_pdf: MakePdf, tmp_path: Path) -> None:
    src = make_pdf("src.pdf", ["a", "b", "c"])
    plan = [
        _item(1, 1, bookmark="Owner Statement"),
        _item(2, 2),
        _item(3, 3, section_id="rent_roll", bookmark="Rent Roll"),
    ]
    out = compose(plan, {"pm_source": src}, tmp_path / "out.pdf", title="T")
    reader = PdfReader(str(out.path))
    assert out.bookmarks == ("Owner Statement", "Rent Roll")
    titles = [entry["/Title"] for entry in reader.outline]  # type: ignore[index]
    assert titles == ["Owner Statement", "Rent Roll"]
    assert reader.get_destination_page_number(reader.outline[1]) == 2  # type: ignore[arg-type]


def test_bookmarks_can_be_turned_off(make_pdf: MakePdf, tmp_path: Path) -> None:
    src = make_pdf("src.pdf", ["a"])
    out = compose(
        [_item(1, 1, bookmark="X")],
        {"pm_source": src},
        tmp_path / "out.pdf",
        title="T",
        add_bookmarks=False,
    )
    assert out.bookmarks == ()
    assert PdfReader(str(out.path)).outline == []


def test_metadata(make_pdf: MakePdf, tmp_path: Path) -> None:
    src = make_pdf("src.pdf", ["a"])
    out = compose(
        [_item(1, 1)],
        {"pm_source": src},
        tmp_path / "out.pdf",
        title="WayPointe - Investor Report - June 2026",
        created_at=datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC),
    )
    meta = PdfReader(str(out.path)).metadata
    assert meta is not None
    assert meta["/Title"] == "WayPointe - Investor Report - June 2026"
    assert str(meta["/Producer"]).startswith("Cornerstone Report Runner")
    assert str(meta["/CreationDate"]) == "D:20260701120000Z"


def test_pages_from_several_documents(make_pdf: MakePdf, tmp_path: Path) -> None:
    pm = make_pdf("pm.pdf", ["pm one"])
    cs = make_pdf("cs.pdf", ["cornerstone one"])
    plan = [_item(1, 1, doc_role="cornerstone_balance_sheet"), _item(2, 1)]
    out = compose(
        plan, {"pm_source": pm, "cornerstone_balance_sheet": cs}, tmp_path / "out.pdf", title="T"
    )
    reader = PdfReader(str(out.path))
    assert "cornerstone one" in (reader.pages[0].extract_text() or "")


def test_the_same_plan_twice_is_byte_identical_apart_from_the_creation_date(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    """SPEC §9.4."""
    src = make_pdf("src.pdf", ["a", "b"])
    plan = [_item(1, 1, bookmark="A"), _item(2, 2)]
    when = datetime(2026, 7, 1, tzinfo=UTC)
    first = compose(plan, {"pm_source": src}, tmp_path / "one.pdf", title="T", created_at=when)
    second = compose(plan, {"pm_source": src}, tmp_path / "two.pdf", title="T", created_at=when)
    assert first.path.read_bytes() == second.path.read_bytes()

    later = compose(
        plan,
        {"pm_source": src},
        tmp_path / "three.pdf",
        title="T",
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    assert later.path.read_bytes() != first.path.read_bytes()


def test_an_empty_plan_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="empty plan"):
        compose([], {}, tmp_path / "out.pdf", title="T")


def test_a_missing_source_role_is_refused(make_pdf: MakePdf, tmp_path: Path) -> None:
    src = make_pdf("src.pdf", ["a"])
    with pytest.raises(KeyError, match="cornerstone_balance_sheet"):
        compose(
            [_item(1, 1), _item(2, 1, doc_role="cornerstone_balance_sheet")],
            {"pm_source": src},
            tmp_path / "out.pdf",
            title="T",
        )


def test_a_page_beyond_the_source_is_refused(make_pdf: MakePdf, tmp_path: Path) -> None:
    src = make_pdf("src.pdf", ["a"])
    with pytest.raises(IndexError, match="plan asks for page 4"):
        compose([_item(1, 4)], {"pm_source": src}, tmp_path / "out.pdf", title="T")
