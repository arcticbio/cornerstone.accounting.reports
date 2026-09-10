"""One property, end to end (SPEC §6).

    fetch → preprocess → classify → segment → resolve → plan → compose → manifest → review → publish

Every stage writes its artefacts under `work/<period>/<property_id>/`, so a build that goes to
review can be inspected without re-running anything.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from crr.classify.footer_check import apply_footer_check
from crr.classify.orientation_check import OrientationArbiter, apply_orientation_check
from crr.classify.protocol import Classifier, PageInput, Usage
from crr.compose.composer import compose, output_filename
from crr.config.loader import ConfigBundle
from crr.log import get_logger
from crr.manifest.model import (
    BuildManifest,
    ClassifierBlock,
    ConfigBlock,
    ConfigRef,
    CostBlock,
    DroppedRef,
    InputRef,
    OutputRef,
    PropertyBlock,
    Timings,
    TokenCounts,
)
from crr.manifest.writer import write_manifest
from crr.models import (
    BuildStatus,
    PageClassification,
    PeriodId,
    Property,
    ReviewReason,
    SourceDocument,
)
from crr.preprocess.ocr import ocr_if_needed
from crr.preprocess.render import render_pages
from crr.preprocess.text import page_texts, sha256_file
from crr.repository.protocol import SourceRepository
from crr.resolve.resolver import ResolveResult, resolve
from crr.review.report import render_review
from crr.review.rules import confidence_reasons, decide, page_count_drift
from crr.segment.segmenter import Segmentation, segment
from crr.settings import Settings

log = get_logger(__name__)


@dataclass
class BuildResult:
    property_id: str
    status: BuildStatus
    manifest: BuildManifest
    manifest_path: Path
    output_path: Path | None = None
    review_path: Path | None = None

    @property
    def reasons(self) -> list[ReviewReason]:
        return list(self.manifest.review_reasons)


@dataclass
class _Stage:
    """Wall-clock per stage, for the manifest's `timings_ms`."""

    timings: Timings = field(default_factory=Timings)

    def time(self, name: str, started: float) -> None:
        setattr(self.timings, name, int((time.monotonic() - started) * 1000))


def build_property(
    prop: Property,
    period: PeriodId,
    *,
    config: ConfigBundle,
    settings: Settings,
    repository: SourceRepository,
    classifier: Classifier,
    arbiter: OrientationArbiter | None = None,
    dry_run: bool = False,
    previous_pm_pages: int | None = None,
) -> BuildResult:
    """Build one property's package. Never raises for data problems — those become review
    reasons or a `FAILED` manifest (SPEC §6.8)."""
    work = settings.work_dir / period / prop.id
    work.mkdir(parents=True, exist_ok=True)
    manifest_path = work / "build-manifest.json"
    output_def = config.output_for_property(prop.id)
    schema_ref, output_ref = _config_refs(config, prop)
    stages = _Stage()

    manifest = BuildManifest(
        status=BuildStatus.FAILED,
        property=PropertyBlock(
            id=prop.id,
            name=prop.name,
            property_manager=prop.property_manager,
            owning_entity=prop.owning_entity,
        ),
        period=period,
        config=ConfigBlock(
            schema_ref=schema_ref,
            output=output_ref,
            properties_sha256=config.sha256.get("properties.yaml", ""),
        ),
        classifier=ClassifierBlock(
            name=classifier.name,
            model=settings.model if classifier.name.startswith("anthropic") else None,
            prompt_version=getattr(classifier, "prompt_version", None),
            effort=settings.classifier_effort if classifier.name.startswith("anthropic") else None,
        ),
    )

    if previous_pm_pages is None:
        previous_pm_pages = _previous_pm_pages(repository, prop, period, settings)

    try:
        started = time.monotonic()
        documents = repository.fetch_inputs(prop, period, work / "inputs")
        stages.time("fetch", started)

        started = time.monotonic()
        documents, page_text, page_images = _preprocess(
            documents,
            output_def,
            settings,
            work,
            render_images=getattr(classifier, "needs_page_images", True),
        )
        stages.time("preprocess", started)
        manifest.inputs = [_input_ref(doc) for doc in documents]

        started = time.monotonic()
        classifications, usage, orientation_reasons = _classify(
            documents, page_text, page_images, config, classifier, settings, arbiter
        )
        stages.time("classify", started)
        manifest.classifications = classifications
        manifest.cost = _cost(usage, settings, classifier)

        segments = _segment(documents, classifications, config, prop)
        manifest.sections = [s for seg in segments.values() for s in seg.sections]

        plan_result = resolve(
            output_def,
            prop,
            segments,
            config.schemas,
            config.properties.period_label(period),
            present_roles={doc.role for doc in documents},
        )
        manifest.plan = list(plan_result.plan)
        manifest.dropped = [
            DroppedRef(
                section_id=d.section_id,
                doc_role=d.doc_role,
                record_id=d.record_id,
                pages=list(d.pages),
            )
            for d in plan_result.dropped
        ]

        reasons = orientation_reasons + _all_reasons(
            classifications, segments, plan_result, settings, documents, previous_pm_pages
        )
        verdict = decide(reasons)
        manifest.review_reasons = list(verdict.reasons)
        manifest.status = verdict.status

        if dry_run:
            log.info("build.dry_run", property=prop.id, pages=len(plan_result.plan))
            manifest.timings_ms = stages.timings
            return BuildResult(
                prop.id, manifest.status, manifest, write_manifest(manifest, manifest_path)
            )

        started = time.monotonic()
        composed = compose(
            list(plan_result.plan),
            {doc.role: doc.path for doc in documents},
            work / output_filename(prop.name, config.properties.period_label(period)),
            title=output_def.title_template.format(
                property=prop.name,
                period=period,
                period_label=config.properties.period_label(period),
                owning_entity=prop.owning_entity,
            ),
            add_bookmarks=output_def.transforms.add_bookmarks,
        )
        stages.time("compose", started)
        manifest.output = OutputRef(
            file=composed.path.name,
            sha256=sha256_file(composed.path),
            pages=composed.page_count,
        )
        manifest.timings_ms = stages.timings
        write_manifest(manifest, manifest_path)

        review_path: Path | None = None
        if verdict.needs_review:
            review_path = work / "REVIEW.md"
            review_path.write_text(render_review(manifest))

        started = time.monotonic()
        publishable = [composed.path, manifest_path, *([review_path] if review_path else [])]
        repository.publish(prop, period, publishable, manifest.status)
        stages.time("publish", started)
        manifest.timings_ms = stages.timings
        write_manifest(manifest, manifest_path)

        log.info(
            "build.done",
            property=prop.id,
            status=manifest.status.value,
            pages=composed.page_count,
            reasons=sorted({r.code for r in verdict.reasons}),
        )
        return BuildResult(
            prop.id, manifest.status, manifest, manifest_path, composed.path, review_path
        )

    except Exception as exc:
        # FAILED is for exceptions only (SPEC §6.8): an unreadable PDF, a missing PM source
        # (RepositoryError), OCR that cannot run (OcrError), API errors after retries. Broad
        # on purpose: one property's failure must not abort a run over the other seven. The
        # manifest is still written so the failure is inspectable, and nothing is published.
        manifest.status = BuildStatus.FAILED
        manifest.error = f"{type(exc).__name__}: {exc}"
        manifest.timings_ms = stages.timings
        log.error("build.failed", property=prop.id, error=type(exc).__name__)
        return BuildResult(
            prop.id, BuildStatus.FAILED, manifest, write_manifest(manifest, manifest_path)
        )


def _previous_pm_pages(
    repository: SourceRepository, prop: Property, period: PeriodId, settings: Settings
) -> int | None:
    """Ask the repository what the last built period looked like, if it can say.

    Both repositories implement `previous_pm_pages`, but the protocol does not require it: a
    repository that cannot look backwards simply never triggers the drift check.
    """
    lookup = getattr(repository, "previous_pm_pages", None)
    if lookup is None:
        return None
    try:
        pages = lookup(prop, period, settings.work_dir)
    except Exception:  # a history lookup must never fail a build
        log.warning("build.previous_manifest_unavailable", property=prop.id)
        return None
    return int(pages) if pages else None


# -- stages ----------------------------------------------------------------------------
def _preprocess(
    documents: list[SourceDocument],
    output_def: object,
    settings: Settings,
    work: Path,
    render_images: bool = True,
) -> tuple[list[SourceDocument], dict[str, list[str]], dict[str, dict[int, Path]]]:
    """OCR where the output definition asks for it, then render and extract text.

    The OCR'd file replaces the source everywhere downstream, composition included, so a
    scanned package ships searchable (D-10).
    """
    ocr_enabled = bool(getattr(getattr(output_def, "transforms", None), "ocr_if_no_text", False))
    processed: list[SourceDocument] = []
    texts: dict[str, list[str]] = {}
    images: dict[str, dict[int, Path]] = {}

    for doc in documents:
        result = ocr_if_needed(
            doc.path,
            # Content-addressed and shared across builds: the same scan is never OCR'd twice.
            settings.work_dir / "ocr-cache" / f"{doc.sha256[:16]}.pdf",
            has_text_layer=doc.has_text_layer,
            enabled=ocr_enabled,
        )
        current = doc
        if not result.skipped:
            sha = sha256_file(result.path)
            current = doc.model_copy(
                update={
                    "path": result.path,
                    "sha256": sha,
                    "has_text_layer": True,
                    "ocr_applied": True,
                    "ocr_version": result.version,
                    "ocr_rotated_pages": result.rotated_pages,
                }
            )
        page_text = page_texts(current.path, max_chars=settings.page_text_chars)
        texts[current.role] = page_text
        page_dir = work / "pages" / current.role
        if render_images:
            images[current.role] = render_pages(
                current.path,
                current.sha256,
                page_dir,
                dpi=settings.render_dpi,
                max_edge=settings.render_max_edge_px,
            )
        else:
            # The classifier never opens these; name where they would be so the rest of the
            # pipeline is identical either way.
            images[current.role] = {
                n: page_dir / f"{current.sha256[:16]}-p{n:04d}.png"
                for n in range(1, current.page_count + 1)
            }
        processed.append(current)
    return processed, texts, images


def _classify(
    documents: list[SourceDocument],
    texts: dict[str, list[str]],
    images: dict[str, dict[int, Path]],
    config: ConfigBundle,
    classifier: Classifier,
    settings: Settings,
    arbiter: OrientationArbiter | None = None,
) -> tuple[list[PageClassification], Usage, list[ReviewReason]]:
    """Label every page of every input, then run the footer and orientation checks over it."""
    labels: list[PageClassification] = []
    usage = Usage()
    orientation_reasons: list[ReviewReason] = []
    for doc in documents:
        schema = config.schemas[doc.schema_id]
        pages = [
            PageInput(page=n, image_path=images[doc.role][n], text=texts[doc.role][n - 1] or None)
            for n in sorted(images[doc.role])
        ]
        result = classifier.classify(doc, schema, pages)
        usage.add(result.usage)
        checked = apply_footer_check(
            result.pages,
            schema,
            {n: texts[doc.role][n - 1] for n in sorted(images[doc.role])},
        )
        if settings.orientation_check:
            checked, reasons = apply_orientation_check(
                checked,
                doc.path,
                doc_role=doc.role,
                dpi=settings.osd_dpi,
                arbiter=arbiter,
            )
            orientation_reasons.extend(reasons)
        labels.extend(checked)
    return labels, usage, orientation_reasons


def _segment(
    documents: list[SourceDocument],
    classifications: list[PageClassification],
    config: ConfigBundle,
    prop: Property,
) -> dict[str, Segmentation]:
    out: dict[str, Segmentation] = {}
    for doc in documents:
        pages = [c for c in classifications if c.doc_role == doc.role]
        out[doc.role] = segment(pages, config.schemas[doc.schema_id], prop, doc.role)
    return out


def _all_reasons(
    classifications: list[PageClassification],
    segments: dict[str, Segmentation],
    plan_result: ResolveResult,
    settings: Settings,
    documents: list[SourceDocument],
    previous_pm_pages: int | None,
) -> list[ReviewReason]:
    reasons = confidence_reasons(classifications, settings.min_confidence)
    for segmentation in segments.values():
        reasons.extend(segmentation.reasons)
    reasons.extend(plan_result.reasons)
    pm_source = next((d for d in documents if d.role == "pm_source"), None)
    if pm_source is not None:
        reasons.extend(page_count_drift("pm_source", pm_source.page_count, previous_pm_pages))
    # D-11: a page that reached neither the plan, the drop list nor a reason is a bug in this
    # code, not a data problem — surface it rather than shipping a package that lost a page.
    for role, pages in plan_result.unaccounted_pages.items():
        reasons.append(
            ReviewReason(
                code="unmapped_section",
                doc_role=role,
                page=pages[0],
                detail=f"pages {list(pages)} were neither placed, dropped nor reported",
            )
        )
    return _deduplicate(reasons)


def _deduplicate(reasons: list[ReviewReason]) -> list[ReviewReason]:
    seen: set[tuple[str, str | None, int | None, str]] = set()
    out: list[ReviewReason] = []
    for reason in reasons:
        key = (reason.code, reason.doc_role, reason.page, reason.detail)
        if key not in seen:
            seen.add(key)
            out.append(reason)
    return out


# -- manifest helpers --------------------------------------------------------------------
def _config_refs(config: ConfigBundle, prop: Property) -> tuple[ConfigRef, ConfigRef]:
    manager = config.properties.manager(prop.property_manager)
    schema = config.schemas[manager.schema_id]
    output = config.outputs[manager.output_definition]
    return (
        ConfigRef(
            id=schema.schema_id,
            version=schema.version,
            sha256=config.sha256.get(f"schemas/{schema.schema_id}.yaml", ""),
        ),
        ConfigRef(
            id=output.output_id,
            version=output.version,
            sha256=config.sha256.get(f"outputs/{output.output_id}.yaml", ""),
        ),
    )


def _input_ref(doc: SourceDocument) -> InputRef:
    return InputRef(
        role=doc.role,
        file=doc.path.name,
        sha256=doc.sha256,
        pages=doc.page_count,
        has_text_layer=doc.has_text_layer,
        ocr_applied=doc.ocr_applied,
        ocr_version=doc.ocr_version,
        ocr_rotated_pages=doc.ocr_rotated_pages,
    )


def _cost(usage: Usage, settings: Settings, classifier: Classifier) -> CostBlock:
    from crr.classify.anthropic_classifier import estimate_usd

    return CostBlock(
        tokens=TokenCounts(
            input=usage.input_tokens,
            cache_read=usage.cache_read_tokens,
            cache_write=usage.cache_write_tokens,
            output=usage.output_tokens,
        ),
        usd_estimate=estimate_usd(usage, settings.model, settings)
        if classifier.name.startswith("anthropic")
        else 0.0,
        api_calls=usage.api_calls,
    )


def utcnow() -> datetime:
    return datetime.now(UTC)


__all__ = ["BuildResult", "build_property"]
