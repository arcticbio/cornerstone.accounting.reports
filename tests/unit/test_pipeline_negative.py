"""What the pipeline does when the data is wrong (SPEC §6.8, D-12).

Everything here runs on synthetic PDFs and a stub classifier: no bundle, no network.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from crr.classify.protocol import ClassificationResult, PageInput, Usage
from crr.config.loader import ConfigBundle
from crr.config.models import (
    Fingerprint,
    FlowLeaf,
    OutputDefinition,
    SectionDef,
    SourceAlias,
    SourceSchema,
    Transforms,
)
from crr.config.properties import PropertyEntry, PropertyManager, PropertyRegistry
from crr.models import (
    BuildStatus,
    Orientation,
    PageClassification,
    Property,
    PropertyRecord,
    SourceDocument,
)
from crr.pipeline import build_property
from crr.repository.local_fs import LocalFsRepository
from crr.settings import Settings
from tests.conftest import MakePdf

SCHEMA = SourceSchema(
    schema_id="testschema",
    version=1,
    producer="Test PM",
    system="test",
    text_layer="always",
    fingerprint=Fingerprint(description="test fingerprint"),
    sections=(
        SectionDef(
            id="owner_statement",
            semantic="owner_statement",
            cardinality="one",
            text_cues=("Owner Statement",),
        ),
        SectionDef(
            id="rent_roll", semantic="rent_roll", cardinality="one", text_cues=("Rent Roll",)
        ),
        SectionDef(
            id="ledger", semantic="general_ledger", cardinality="one", text_cues=("Ledger",)
        ),
    ),
)

OUTPUT = OutputDefinition(
    output_id="test-output",
    version=1,
    property_manager="testpm",
    title_template="{property} - Investor Report - {period_label}",
    sources={"pm": SourceAlias(schema="testschema", role="pm_source")},
    flow=(
        FlowLeaf(address="pm:owner_statement", bookmark="Owner Statement"),
        FlowLeaf(address="pm:rent_roll", bookmark="Rent Roll"),
    ),
    drop=(),
    transforms=Transforms(ocr_if_no_text=False, autorotate=True, add_bookmarks=True),
)

PROPERTY = Property(
    id="testprop",
    name="Test Property",
    folder="Test Property",
    property_manager="testpm",
    owning_entity="Test LP",
    records=(PropertyRecord(id="default", pm_name="Test Property"),),
)


class StubClassifier:
    """Returns whatever labels the test hands it."""

    name = "golden"
    needs_page_images = False

    def __init__(self, sections: Sequence[tuple[str, bool, float]]) -> None:
        self._sections = sections

    def classify(
        self, doc: SourceDocument, schema: SourceSchema, pages: list[PageInput]
    ) -> ClassificationResult:
        if doc.role != "pm_source":
            return ClassificationResult(pages=[], usage=Usage())
        return ClassificationResult(
            pages=[
                PageClassification(
                    doc_role=doc.role,
                    page=index,
                    section_id=section,
                    is_continuation=continuation,
                    record_qualifier=None,
                    orientation=Orientation.UPRIGHT,
                    confidence=confidence,
                    evidence="stub",
                    classifier=self.name,
                )
                for index, (section, continuation, confidence) in enumerate(self._sections, start=1)
            ],
            usage=Usage(),
        )


def _registry() -> PropertyRegistry:
    return PropertyRegistry(
        period_format="YYYY-MM",
        period_folder_template="{yyyy}-{mm} {month_name}",
        property_managers=(
            PropertyManager(
                id="testpm",
                name="Test PM",
                folder="Test PM",
                schema_id="testschema",
                output_definition="test-output",
                pm_source_filename="pm.pdf",
            ),
        ),
        cornerstone_files={},
        properties=(
            PropertyEntry(
                id="testprop",
                name="Test Property",
                folder="Test Property",
                property_manager="testpm",
                owning_entity="Test LP",
                records=(PropertyRecord(id="default", pm_name="Test Property"),),
            ),
        ),
    )


def _bundle() -> ConfigBundle:
    return ConfigBundle(
        schemas={"testschema": SCHEMA},
        outputs={"test-output": OUTPUT},
        properties=_registry(),
        sha256={
            "properties.yaml": "0" * 64,
            "schemas/testschema.yaml": "1" * 64,
            "outputs/test-output.yaml": "2" * 64,
        },
    )


@pytest.fixture
def repo_root(tmp_path: Path, make_pdf: MakePdf) -> Path:
    """A miniature repository with one property, one period, one three-page PM source."""
    root = tmp_path / "repo"
    inputs = root / "Test PM" / "Test Property" / "2026-06 June" / "inputs"
    inputs.mkdir(parents=True)
    source = make_pdf("pm.pdf", ["Owner Statement page", "Rent Roll page", "Ledger page"])
    (inputs / "pm.pdf").write_bytes(source.read_bytes())
    return root


def _build(repo_root: Path, tmp_path: Path, classifier: StubClassifier):  # type: ignore[no-untyped-def]
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, work_dir=tmp_path / "work", publish_root=tmp_path / "published"
    )
    bundle = _bundle()
    repository = LocalFsRepository(
        repo_root, bundle.properties, publish_root=settings.local_publish_root
    )
    return build_property(
        PROPERTY,
        "2026-06",
        config=bundle,
        settings=settings,
        repository=repository,
        classifier=classifier,
    )


def test_a_clean_run_builds(repo_root: Path, tmp_path: Path) -> None:
    result = _build(
        repo_root,
        tmp_path,
        StubClassifier(
            [("owner_statement", False, 1.0), ("rent_roll", False, 1.0), ("ledger", False, 1.0)]
        ),
    )
    # 'ledger' is in neither flow nor drop, so even this is held back — see the next test.
    assert result.status is BuildStatus.NEEDS_REVIEW
    assert {r.code for r in result.reasons} == {"unmapped_section"}


def test_a_section_in_neither_flow_nor_drop_needs_review(repo_root: Path, tmp_path: Path) -> None:
    """SPEC §4.2: the unmapped-section invariant."""
    result = _build(
        repo_root,
        tmp_path,
        StubClassifier(
            [("owner_statement", False, 1.0), ("rent_roll", False, 1.0), ("ledger", False, 1.0)]
        ),
    )
    reason = next(r for r in result.reasons if r.code == "unmapped_section")
    assert reason.page == 3
    assert "ledger" in reason.detail
    assert result.review_path is not None
    assert "Unmapped section" in result.review_path.read_text()


def test_an_unknown_page_needs_review(repo_root: Path, tmp_path: Path) -> None:
    result = _build(
        repo_root,
        tmp_path,
        StubClassifier(
            [("owner_statement", False, 1.0), ("rent_roll", False, 1.0), ("unknown", False, 0.2)]
        ),
    )
    assert result.status is BuildStatus.NEEDS_REVIEW
    assert "unknown_page" in {r.code for r in result.reasons}
    # The package is still composed, minus the page nobody could place.
    assert result.output_path is not None
    assert len(result.manifest.plan) == 2


def test_a_missing_required_section_needs_review(repo_root: Path, tmp_path: Path) -> None:
    result = _build(
        repo_root,
        tmp_path,
        StubClassifier(
            [
                ("owner_statement", False, 1.0),
                ("owner_statement", True, 1.0),
                ("owner_statement", True, 1.0),
            ]
        ),
    )
    assert result.status is BuildStatus.NEEDS_REVIEW
    assert "missing_required" in {r.code for r in result.reasons}


def test_low_confidence_needs_review(repo_root: Path, tmp_path: Path) -> None:
    result = _build(
        repo_root,
        tmp_path,
        StubClassifier(
            [("owner_statement", False, 0.4), ("rent_roll", False, 1.0), ("rent_roll", True, 1.0)]
        ),
    )
    assert "low_confidence" in {r.code for r in result.reasons}


def test_a_missing_pm_source_fails(repo_root: Path, tmp_path: Path) -> None:
    """SPEC §6.1: a missing PM source is a hard failure for that property."""
    (repo_root / "Test PM" / "Test Property" / "2026-06 June" / "inputs" / "pm.pdf").unlink()
    result = _build(repo_root, tmp_path, StubClassifier([]))
    assert result.status is BuildStatus.FAILED
    assert result.manifest.error is not None
    assert "PM source" in result.manifest.error
    assert result.output_path is None
    # The manifest is still written, and nothing is published.
    assert result.manifest_path.is_file()
    assert not (tmp_path / "published").exists()


def test_a_needs_review_package_is_published_to_review(repo_root: Path, tmp_path: Path) -> None:
    result = _build(
        repo_root,
        tmp_path,
        StubClassifier(
            [("owner_statement", False, 1.0), ("rent_roll", False, 1.0), ("unknown", False, 0.1)]
        ),
    )
    published = tmp_path / "published" / "Test PM" / "Test Property" / "2026-06 June"
    assert (published / "review").is_dir()
    assert not (published / "output").exists()
    names = sorted(p.name for p in (published / "review").iterdir())
    assert names == [
        "REVIEW.md",
        "Test Property - Investor Report - June 2026.pdf",
        "build-manifest.json",
    ]
    assert result.status is BuildStatus.NEEDS_REVIEW


def test_publishing_twice_never_overwrites(repo_root: Path, tmp_path: Path) -> None:
    labels = StubClassifier(
        [("owner_statement", False, 1.0), ("rent_roll", False, 1.0), ("unknown", False, 0.1)]
    )
    _build(repo_root, tmp_path, labels)
    _build(repo_root, tmp_path, labels)
    review = tmp_path / "published" / "Test PM" / "Test Property" / "2026-06 June" / "review"
    names = sorted(p.name for p in review.iterdir())
    assert "Test Property - Investor Report - June 2026 (build 2).pdf" in names
    assert "Test Property - Investor Report - June 2026.pdf" in names
