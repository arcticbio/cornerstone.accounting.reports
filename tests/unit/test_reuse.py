"""Carrying page labels over from the previous version (SPEC §18.7)."""

from __future__ import annotations

from pathlib import Path

from crr.classify.protocol import ClassificationResult, PageInput, Usage
from crr.config import load_config
from crr.config.models import SourceSchema
from crr.intake.reuse import ReusingClassifier
from crr.manifest import BuildManifest, ClassifierBlock, ConfigBlock, ConfigRef, InputRef
from crr.manifest.model import PropertyBlock
from crr.models import BuildStatus, Orientation, PageClassification, ReviewReason, SourceDocument

CONFIG = load_config(Path("config"))
SCHEMA = CONFIG.schemas["cornerstone-qbo"]
SCHEMA_SHA = {"cornerstone-qbo": "schema-sha"}
ROLE = "cornerstone_balance_sheet"


def _label(page: int, classifier: str = "anthropic") -> PageClassification:
    return PageClassification(
        doc_role=ROLE,
        page=page,
        section_id="balance_sheet",
        is_continuation=page > 1,
        record_qualifier=None,
        orientation=Orientation.UPRIGHT,
        confidence=0.97,
        evidence="",
        classifier=classifier,
    )


def _previous(**overrides: object) -> BuildManifest:
    ref = {
        "role": ROLE,
        "file": "b.pdf",
        "sha256": "ocr-output-sha",
        "source_sha256": "uploaded-sha",
        "schema_sha256": "schema-sha",
        "pages": 2,
        "has_text_layer": True,
    }
    ref.update(overrides.pop("ref", {}))  # type: ignore[arg-type]
    return BuildManifest(
        status=BuildStatus.BUILT,
        property=PropertyBlock(id="p", name="P", property_manager="m", owning_entity="e"),
        period="2026-09",
        config=ConfigBlock(
            schema_ref=ConfigRef(id="s", version=1, sha256="x"),
            output=ConfigRef(id="o", version=1, sha256="y"),
            properties_sha256="z",
        ),
        classifier=ClassifierBlock(
            name="anthropic",
            model=str(overrides.get("model", "claude-opus-5")),
            prompt_version=str(overrides.get("prompt", "v3")),
        ),
        inputs=[InputRef(**ref)],  # type: ignore[arg-type]
        classifications=[_label(1), _label(2)],
    )


class Inner:
    name = "anthropic"
    needs_page_images = True
    prompt_version = "v3"

    def __init__(self) -> None:
        self.calls = 0

    def classify(
        self, doc: SourceDocument, schema: SourceSchema, pages: list[PageInput]
    ) -> ClassificationResult:
        self.calls += 1
        return ClassificationResult(pages=[_label(p.page, "fresh") for p in pages], usage=Usage())


def _doc(sha: str = "whatever", source: str | None = "uploaded-sha") -> SourceDocument:
    return SourceDocument(
        role=ROLE,
        schema_id="cornerstone-qbo",
        path=Path("b.pdf"),
        sha256=sha,
        source_sha256=source,
        page_count=2,
        has_text_layer=True,
    )


PAGES = [PageInput(page=1, image_path=Path("1.png")), PageInput(page=2, image_path=Path("2.png"))]


def _classify(
    previous: BuildManifest | None, doc: SourceDocument | None = None
) -> tuple[Inner, ReusingClassifier, ClassificationResult]:
    inner = Inner()
    wrapper = ReusingClassifier(inner, previous, model="claude-opus-5", schema_sha256=SCHEMA_SHA)
    return inner, wrapper, wrapper.classify(doc or _doc(), SCHEMA, PAGES)


def test_an_unchanged_upload_reuses_labels_even_though_ocr_output_differs() -> None:
    inner, wrapper, result = _classify(_previous())
    assert inner.calls == 0 and wrapper.reused == [ROLE]
    assert [p.classifier for p in result.pages] == ["anthropic", "anthropic"]


def test_a_changed_upload_is_classified() -> None:
    inner, wrapper, _ = _classify(_previous(), _doc(source="new-upload"))
    assert inner.calls == 1 and wrapper.reused == []


def test_no_previous_build_means_no_reuse() -> None:
    inner, _, _ = _classify(None)
    assert inner.calls == 1


def test_a_changed_schema_forces_classification() -> None:
    inner, _, _ = _classify(_previous(ref={"schema_sha256": "old-schema"}))
    assert inner.calls == 1


def test_a_changed_prompt_or_model_forces_classification() -> None:
    assert _classify(_previous(prompt="v2"))[0].calls == 1
    assert _classify(_previous(model="claude-sonnet-5"))[0].calls == 1


def test_a_manifest_without_a_label_for_every_page_is_not_trusted() -> None:
    previous = _previous()
    previous.classifications = [_label(1)]
    assert _classify(previous)[0].calls == 1


def test_a_v1_manifest_without_source_hashes_falls_back_to_sha256() -> None:
    previous = _previous(ref={"source_sha256": None, "sha256": "uploaded-sha"})
    assert _classify(previous, _doc(sha="uploaded-sha", source=None))[0].calls == 0


def _uncertain(role: str, page: int) -> ReviewReason:
    return ReviewReason(code="orientation_uncertain", doc_role=role, page=page, detail="open")


def test_reused_labels_carry_only_their_own_open_orientation_questions() -> None:
    """Live-test capacity note: reused labels skip the orientation cross-check, and what it left
    open on these bytes is raised again (SPEC §18.7)."""
    previous = _previous()
    previous.review_reasons = [
        _uncertain(ROLE, 2),
        _uncertain("pm_source", 7),  # another document's question stays with that document
        ReviewReason(code="missing_required", doc_role=ROLE, detail="not an orientation matter"),
    ]
    _, wrapper, _ = _classify(previous)
    carried = wrapper.carried_orientation_reasons(ROLE)
    assert carried is not None and [(r.doc_role, r.page) for r in carried] == [(ROLE, 2)]


def test_labels_made_afresh_are_cross_checked_as_usual() -> None:
    _, wrapper, _ = _classify(_previous(), _doc(source="new-upload"))
    assert wrapper.carried_orientation_reasons(ROLE) is None
    _, clean, _ = _classify(_previous())
    assert clean.carried_orientation_reasons(ROLE) == []  # reused, nothing left open
