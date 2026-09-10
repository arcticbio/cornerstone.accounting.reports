"""The classifier interface (SPEC §7.1).

Two implementations: `AnthropicClassifier` (production) and `GoldenClassifier` (the golden
labels, which lets the whole pipeline run with no API key and is the composer's fixture).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from crr.config.models import SourceSchema
from crr.models import PageClassification, SourceDocument


@dataclass(frozen=True)
class PageInput:
    """One page as the classifier sees it."""

    page: int
    image_path: Path
    #: Extracted or OCR text; None when neither exists.
    text: str | None = None


@dataclass
class Usage:
    """Token accounting for one document (SPEC §7.3)."""

    input_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0
    api_calls: int = 0
    latency_ms: int = 0

    def add(self, other: Usage) -> None:
        self.input_tokens += other.input_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_write_tokens += other.cache_write_tokens
        self.output_tokens += other.output_tokens
        self.api_calls += other.api_calls
        self.latency_ms += other.latency_ms


@dataclass
class ClassificationResult:
    pages: list[PageClassification] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)


class Classifier(Protocol):
    """Labels every page of one document against one schema."""

    name: str

    #: False when the implementation never looks at a page image. The pipeline skips
    #: rasterising for such a classifier, which is what makes a golden build fast enough to
    #: be a test fixture; OCR still runs, because OCR changes what gets composed.
    needs_page_images: bool

    def classify(
        self, doc: SourceDocument, schema: SourceSchema, pages: list[PageInput]
    ) -> ClassificationResult: ...
