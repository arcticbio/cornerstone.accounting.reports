"""One real classification per manager (SPEC §15). Skipped without a classifier key."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from crr.classify.anthropic_classifier import AnthropicClassifier
from crr.classify.prompts import select_exemplars
from crr.classify.protocol import PageInput
from crr.config import load_config
from crr.golden import load_all_golden
from crr.models import SourceDocument
from crr.preprocess.render import render_pages
from crr.preprocess.text import document_text_layer, sha256_file
from crr.settings import Settings

pytestmark = [
    pytest.mark.api,
    pytest.mark.skipif(
        not (os.environ.get("CRR_ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")),
        reason="needs CRR_ANTHROPIC_API_KEY (or ANTHROPIC_API_KEY)",
    ),
]

BUNDLE = Path("data/bundle/2026-06")
CONFIG = load_config(Path("config"))
GOLDEN = load_all_golden(Path("eval/golden"))

# One property per manager, plus WayPointe — the two-record package (SPEC §7, PLAN Phase 3).
CASES = [
    ("fort-grounds", "rentmanager-missoula", "owner_statement"),
    ("waypointe", "rentmanager-missoula", "owner_statement"),
    ("timber-place", "mccathren", "cover_letter"),
    ("bridgewater", "cobalt", "owner_statement"),
]


@pytest.mark.parametrize(("property_id", "schema_id", "expected_section"), CASES)
def test_page_one_of_each_pm_source(
    property_id: str, schema_id: str, expected_section: str, tmp_path: Path
) -> None:
    settings = Settings()
    golden = GOLDEN[property_id]
    schema = CONFIG.schemas[schema_id]
    pdf = BUNDLE / golden.document("pm_source").file

    sha = sha256_file(pdf)
    texts, has_text = document_text_layer(pdf, max_chars=settings.page_text_chars)
    images = render_pages(pdf, sha, tmp_path, pages=[1])
    doc = SourceDocument(
        role="pm_source",
        schema_id=schema_id,
        path=pdf,
        sha256=sha,
        page_count=len(texts),
        has_text_layer=has_text,
    )
    exemplar_images = {
        (g.property_id, d.role, p.page): images[1]
        for g in GOLDEN.values()
        for d in g.documents
        for p in d.pages
        if False  # no exemplars: this test checks the zero-shot floor
    }
    exemplars = select_exemplars(
        schema,
        GOLDEN,
        exemplar_images,
        for_property=property_id,
        exemplar_policy=settings.exemplar_policy,
    )
    result = AnthropicClassifier(settings, exemplars=exemplars).classify(
        doc, schema, [PageInput(page=1, image_path=images[1], text=texts[0])]
    )
    assert len(result.pages) == 1
    assert result.pages[0].section_id == expected_section
    assert result.usage.api_calls >= 1


def test_the_cached_prefix_is_read_back_on_page_two(tmp_path: Path) -> None:
    """SPEC §7.3 / PLAN Phase 3 acceptance: cache reads observed on pages 2+."""
    settings = Settings()
    golden = GOLDEN["fort-grounds"]
    schema = CONFIG.schemas["rentmanager-missoula"]
    pdf = BUNDLE / golden.document("pm_source").file

    sha = sha256_file(pdf)
    texts, has_text = document_text_layer(pdf, max_chars=settings.page_text_chars)
    images = render_pages(pdf, sha, tmp_path, pages=[1, 2])
    doc = SourceDocument(
        role="pm_source",
        schema_id=schema.schema_id,
        path=pdf,
        sha256=sha,
        page_count=len(texts),
        has_text_layer=has_text,
    )
    pages = [PageInput(page=n, image_path=images[n], text=texts[n - 1]) for n in (1, 2)]
    result = AnthropicClassifier(settings).classify(doc, schema, pages)
    assert result.usage.cache_read_tokens > 0
