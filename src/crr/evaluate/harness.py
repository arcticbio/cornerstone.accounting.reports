"""The eval harness (SPEC §8).

For every golden document: preprocess exactly as `build` does — OCR first for scanned
sources, so the classifier sees the same page images a build would — run the classifier, and
score the result against the golden labels.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field

from crr.classify.orientation_check import OrientationArbiter, apply_orientation_check
from crr.classify.protocol import Classifier, PageInput, Usage
from crr.config.loader import ConfigBundle
from crr.evaluate.metrics import Scores, score_boundaries, score_document
from crr.golden import GoldenProperty
from crr.log import get_logger
from crr.models import PageClassification, Property, SourceDocument
from crr.preprocess.ocr import ocr_if_needed
from crr.preprocess.render import render_pages
from crr.preprocess.text import page_texts, sha256_file
from crr.segment.segmenter import segment
from crr.settings import Settings

log = get_logger(__name__)

#: `record_qualifier` accuracy is only meaningful where a source prints a `Property:` header
#: (SPEC §8: "Missoula only").
RECORD_SCORED_SCHEMAS = frozenset({"rentmanager-missoula"})


@dataclass
class DocumentResult:
    property_id: str
    pm_id: str
    doc_role: str
    schema_id: str
    pages: int
    scores: Scores
    predictions: list[PageClassification] = field(default_factory=list)


@dataclass
class EvalResult:
    classifier: str
    model: str | None
    prompt_version: str | None
    documents: list[DocumentResult] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    duration_s: float = 0.0

    def by_manager(self) -> dict[str, Scores]:
        out: dict[str, Scores] = {}
        for doc in self.documents:
            out.setdefault(doc.pm_id, Scores()).merge(doc.scores)
        return out

    def overall(self) -> Scores:
        total = Scores()
        for doc in self.documents:
            total.merge(doc.scores)
        return total

    def confusion_pairs(self, limit: int = 20) -> list[tuple[tuple[str, str], int]]:
        counter: Counter[tuple[str, str]] = Counter()
        for doc in self.documents:
            counter.update(doc.scores.confusion)
        return counter.most_common(limit)


def evaluate(
    golden: dict[str, GoldenProperty],
    config: ConfigBundle,
    settings: Settings,
    classifier_for: object,
    *,
    property_ids: list[str] | None = None,
    pm_id: str | None = None,
    arbiter: OrientationArbiter | None = None,
) -> EvalResult:
    """Score `classifier_for(property_id)` over every golden document in scope."""
    started = time.monotonic()
    wanted = sorted(property_ids or golden)
    result = EvalResult(classifier="", model=None, prompt_version=None)
    for property_id in wanted:
        entry = golden.get(property_id)
        if entry is None or (pm_id and entry.pm_id != pm_id):
            continue
        prop = config.properties.property(property_id).to_domain()
        classifier: Classifier = classifier_for(property_id)  # type: ignore[operator]
        result.classifier = classifier.name
        result.model = settings.model if classifier.name.startswith("anthropic") else None
        result.prompt_version = getattr(classifier, "prompt_version", None)
        documents, usage = _evaluate_property(entry, prop, config, settings, classifier, arbiter)
        result.documents.extend(documents)
        result.usage.add(usage)
        log.info("eval.property_done", property=property_id)
    result.duration_s = time.monotonic() - started
    return result


def _evaluate_property(
    golden: GoldenProperty,
    prop: Property,
    config: ConfigBundle,
    settings: Settings,
    classifier: Classifier,
    arbiter: OrientationArbiter | None = None,
) -> tuple[list[DocumentResult], Usage]:
    out: list[DocumentResult] = []
    usage = Usage()
    work = settings.work_dir / "eval" / golden.property_id
    output_def = config.output_for_property(golden.property_id)
    needs_images = getattr(classifier, "needs_page_images", True)

    for golden_doc in golden.documents:
        schema = config.schemas[golden_doc.schema_id]
        source = settings.bundle_root / golden_doc.file
        sha = sha256_file(source)
        # SPEC §8: preprocess exactly as `build` does, so the model sees the images a build
        # would. A classifier that reads no images (the golden one) needs neither the OCR
        # pass nor the rasterising, and skipping both is what keeps the CI self-consistency
        # run cheap.
        ocr = ocr_if_needed(
            source,
            settings.work_dir / "ocr-cache" / f"{sha[:16]}.pdf",
            has_text_layer=schema.text_layer != "never",
            enabled=(
                needs_images
                and output_def.transforms.ocr_if_no_text
                and schema.text_layer == "never"
            ),
        )
        path = ocr.path
        current_sha = sha if ocr.skipped else sha256_file(path)
        texts = page_texts(path, max_chars=settings.page_text_chars)
        if needs_images:
            images = render_pages(
                path,
                current_sha,
                work / golden_doc.role,
                dpi=settings.render_dpi,
                max_edge=settings.render_max_edge_px,
            )
        else:
            images = {
                n: work / golden_doc.role / f"{current_sha[:16]}-p{n:04d}.png"
                for n in range(1, len(texts) + 1)
            }
        doc = SourceDocument(
            role=golden_doc.role,
            schema_id=golden_doc.schema_id,
            path=path,
            sha256=current_sha,
            page_count=len(texts),
            has_text_layer=True if not ocr.skipped else schema.text_layer != "never",
            ocr_applied=not ocr.skipped,
        )
        pages = [
            PageInput(page=n, image_path=images[n], text=texts[n - 1] or None)
            for n in sorted(images)
        ]
        classified = classifier.classify(doc, schema, pages)
        usage.add(classified.usage)
        # Score what would ship, not the raw label: the orientation a build applies is the one
        # the §7.6 cross-check settled. Skipped for a classifier that reads no images — the
        # golden one, whose labels are the answer key — so the CI self-consistency run stays
        # free.
        predictions = classified.pages
        if settings.orientation_check and needs_images:
            predictions, _ = apply_orientation_check(
                predictions,
                path,
                doc_role=golden_doc.role,
                dpi=settings.osd_dpi,
                arbiter=arbiter,
            )

        scores = score_document(
            golden_doc,
            predictions,
            score_record=golden_doc.schema_id in RECORD_SCORED_SCHEMAS,
            golden_record_names={r.id: r.pm_name for r in golden.records} | {None: None},
        )
        golden_labels = golden.classifications(golden_doc.role)
        scores.boundary = score_boundaries(
            list(segment(golden_labels, schema, prop, golden_doc.role).sections),
            list(segment(predictions, schema, prop, golden_doc.role).sections),
        )
        out.append(
            DocumentResult(
                property_id=golden.property_id,
                pm_id=golden.pm_id,
                doc_role=golden_doc.role,
                schema_id=golden_doc.schema_id,
                pages=len(golden_doc.pages),
                scores=scores,
                predictions=predictions,
            )
        )
    return out, usage


def gate_failures(result: EvalResult, settings: Settings) -> list[str]:
    """Managers below threshold, as human-readable lines (SPEC §8)."""
    failures: list[str] = []
    for manager, scores in sorted(result.by_manager().items()):
        accuracy = scores.page.accuracy
        if accuracy is not None and accuracy < settings.eval_min_page_accuracy:
            failures.append(
                f"{manager}: page accuracy {accuracy:.4f} < {settings.eval_min_page_accuracy}"
            )
        f1 = scores.boundary.f1
        if f1 is not None and f1 < settings.eval_min_boundary_f1:
            failures.append(f"{manager}: boundary F1 {f1:.4f} < {settings.eval_min_boundary_f1}")
    return failures
