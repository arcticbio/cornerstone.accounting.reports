"""The ocrmypdf wrapper: argv, version capture, rotation detection, failure modes."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from crr.preprocess import ocr as ocr_mod
from crr.preprocess.ocr import OCR_ARGS, OcrError, ocr_pdf, ocrmypdf_version
from tests.conftest import MakePdf


def test_spec_argv(make_pdf: MakePdf, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = make_pdf("scan.pdf", ["page"])
    dest = tmp_path / "out" / "scan.pdf"
    seen: dict[str, list[str]] = {}

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if argv[1] == "--version":
            return subprocess.CompletedProcess(argv, 0, "15.2.0\n", "")
        seen["argv"] = argv
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(ocr_mod.shutil, "which", lambda _: "/usr/bin/ocrmypdf")
    monkeypatch.setattr(ocr_mod.subprocess, "run", fake_run)

    result = ocr_pdf(src, dest)
    assert seen["argv"][1:-2] == list(OCR_ARGS)
    assert seen["argv"][-2:] == [str(src), str(dest)]
    assert result.version == "15.2.0"
    assert result.rotated_pages is False


def test_rotation_change_is_reported(
    make_pdf: MakePdf, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pypdf import PdfReader, PdfWriter

    src = make_pdf("scan.pdf", ["sideways"])
    dest = tmp_path / "rotated.pdf"

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if argv[1] == "--version":
            return subprocess.CompletedProcess(argv, 0, "15.2.0", "")
        writer = PdfWriter()
        page = PdfReader(str(src)).pages[0]
        page.rotate(90)  # what --rotate-pages does to a sideways scan
        writer.add_page(page)
        with dest.open("wb") as fh:
            writer.write(fh)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(ocr_mod.shutil, "which", lambda _: "/usr/bin/ocrmypdf")
    monkeypatch.setattr(ocr_mod.subprocess, "run", fake_run)

    assert ocr_pdf(src, dest).rotated_pages is True


def test_missing_binary_raises_with_the_install_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr_mod.shutil, "which", lambda _: None)
    with pytest.raises(OcrError, match="apt-get install"):
        ocrmypdf_version()


def test_a_failing_run_raises_and_redacts_paths(
    make_pdf: MakePdf, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = make_pdf("scan.pdf", ["page"])

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if argv[1] == "--version":
            return subprocess.CompletedProcess(argv, 0, "15.2.0", "")
        return subprocess.CompletedProcess(
            argv, 2, "", "TesseractNotFoundError while reading /data/Timber Place/scan.pdf"
        )

    monkeypatch.setattr(ocr_mod.shutil, "which", lambda _: "/usr/bin/ocrmypdf")
    monkeypatch.setattr(ocr_mod.subprocess, "run", fake_run)

    with pytest.raises(OcrError) as excinfo:
        ocr_pdf(src, tmp_path / "out.pdf")
    message = str(excinfo.value)
    assert "TesseractNotFoundError" in message
    assert "Timber Place" not in message  # tenant/property names never leave the process


def test_ocr_is_skipped_when_a_text_layer_already_exists(
    make_pdf: MakePdf, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = make_pdf("digital.pdf", ["page"])

    def explode(*args: object, **kwargs: object) -> None:
        raise AssertionError("ocrmypdf must not be invoked when the document has text")

    monkeypatch.setattr(ocr_mod.subprocess, "run", explode)

    result = ocr_mod.ocr_if_needed(src, tmp_path / "out.pdf", has_text_layer=True, enabled=True)
    assert result.skipped is True
    assert result.path == src


def test_ocr_is_skipped_when_the_output_definition_disables_it(
    make_pdf: MakePdf, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = make_pdf("scan.pdf", ["page"])
    monkeypatch.setattr(ocr_mod.subprocess, "run", lambda *a, **k: pytest.fail("ocrmypdf invoked"))
    result = ocr_mod.ocr_if_needed(src, tmp_path / "out.pdf", has_text_layer=False, enabled=False)
    assert result.skipped is True
