"""Preprocessing: text-layer probe, OCR, page rendering, page text (SPEC §6.2)."""

from crr.preprocess.inspect import DocumentFacts, PageFacts, inspect_pdf
from crr.preprocess.ocr import OcrError, OcrResult, ocr_if_needed, ocr_pdf, ocrmypdf_version
from crr.preprocess.render import render_page, render_pages
from crr.preprocess.text import (
    document_text_layer,
    normalise_text,
    page_texts,
    sha256_file,
)

__all__ = [
    "DocumentFacts",
    "OcrError",
    "OcrResult",
    "PageFacts",
    "document_text_layer",
    "inspect_pdf",
    "normalise_text",
    "ocr_if_needed",
    "ocr_pdf",
    "ocrmypdf_version",
    "page_texts",
    "render_page",
    "render_pages",
    "sha256_file",
]
