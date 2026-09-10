"""The golden classifier (SPEC §7.1).

Replays the labels in `eval/golden/`. It costs nothing, is deterministic, and makes every
stage downstream of classification testable on its own — which is what makes the composer's
regression suite possible (SPEC §9.4, §9.5).
"""

from __future__ import annotations

from crr.classify.protocol import ClassificationResult, PageInput, Usage
from crr.config.models import SourceSchema
from crr.golden import GOLDEN_CLASSIFIER_NAME, GoldenProperty
from crr.models import PageClassification, SourceDocument


class GoldenLabelMissing(KeyError):
    """The golden file has no labels for a document the pipeline asked about."""


class GoldenClassifier:
    """Serves one property's golden labels."""

    name = GOLDEN_CLASSIFIER_NAME
    #: Labels come off disk; no page image is ever read.
    needs_page_images = False

    def __init__(self, golden: GoldenProperty) -> None:
        self._golden = golden

    def classify(
        self, doc: SourceDocument, schema: SourceSchema, pages: list[PageInput]
    ) -> ClassificationResult:
        try:
            labels = self._golden.classifications(doc.role)
        except KeyError as exc:
            raise GoldenLabelMissing(
                f"{self._golden.property_id} has no golden labels for role {doc.role!r}"
            ) from exc

        by_page: dict[int, PageClassification] = {label.page: label for label in labels}
        wanted = [p.page for p in pages] if pages else sorted(by_page)
        missing = [page for page in wanted if page not in by_page]
        if missing:
            raise GoldenLabelMissing(
                f"{self._golden.property_id} {doc.role!r}: no golden label for page(s) "
                f"{missing} (the golden file has {len(by_page)})"
            )
        unknown_sections = {
            by_page[page].section_id
            for page in wanted
            if by_page[page].section_id not in schema.section_ids
            and by_page[page].section_id != "unknown"
        }
        if unknown_sections:
            raise GoldenLabelMissing(
                f"{self._golden.property_id} {doc.role!r}: golden labels name section(s) "
                f"{sorted(unknown_sections)} that schema {schema.schema_id!r} does not declare"
            )
        return ClassificationResult(pages=[by_page[page] for page in wanted], usage=Usage())
