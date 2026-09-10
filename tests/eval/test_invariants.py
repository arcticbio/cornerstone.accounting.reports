"""The six build invariants (SPEC §9), checked against the eight golden builds.

These run the real pipeline over the real bundle with the golden classifier. They are the
composer's acceptance test, and the drift detector for every quarter after this one.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pypdf import PdfReader

from crr.config import ConfigError, load_config
from crr.golden import load_all_golden
from crr.models import BuildStatus
from crr.pipeline import build_property
from crr.repository.local_fs import LocalFsRepository
from crr.settings import Settings

CONFIG = load_config(Path("config"))
GOLDEN = load_all_golden(Path("eval/golden"))
PROPERTY_IDS = sorted(GOLDEN)
BAD_CONFIG = Path("tests/unit/fixtures/bad-config")


@pytest.fixture(scope="module")
def work_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One work root for the whole module, so the content-addressed OCR cache is shared:
    OCR'ing the two McCathren scans once instead of four times."""
    return tmp_path_factory.mktemp("crr-invariants")


@pytest.fixture(scope="module")
def builds(work_root: Path) -> dict[str, object]:
    """Build all eight once; every invariant reads the same results."""
    from crr.classify.golden_classifier import GoldenClassifier

    work = work_root
    settings = Settings(_env_file=None, work_dir=work, publish_root=work / "published")  # type: ignore[call-arg]
    repository = LocalFsRepository(
        settings.bundle_root,
        CONFIG.properties,
        _schema_for_role,
        publish_root=settings.local_publish_root,
    )
    out: dict[str, object] = {}
    for property_id in PROPERTY_IDS:
        prop = CONFIG.properties.property(property_id).to_domain()
        out[property_id] = build_property(
            prop,
            "2026-06",
            config=CONFIG,
            settings=settings,
            repository=repository,
            classifier=GoldenClassifier(GOLDEN[property_id]),
        )
    return out


def _schema_for_role(prop, role):  # type: ignore[no-untyped-def]
    output = CONFIG.output_for_property(prop.id)
    for source in output.sources.values():
        if source.role == role:
            return source.schema_id
    return CONFIG.properties.manager(prop.property_manager).schema_id


@pytest.mark.parametrize("property_id", PROPERTY_IDS)
def test_invariant_1_no_page_is_silently_lost(property_id: str, builds: dict) -> None:
    """Every input page is in the plan, the drop list, or a review reason (SPEC §9.1, D-11)."""
    result = builds[property_id]
    manifest = result.manifest
    placed: dict[str, set[int]] = {}
    for item in manifest.plan:
        placed.setdefault(item.doc_role, set()).add(item.source_page)
    for dropped in manifest.dropped:
        placed.setdefault(dropped.doc_role, set()).update(dropped.pages)
    for reason in manifest.review_reasons:
        if reason.doc_role and reason.page:
            placed.setdefault(reason.doc_role, set()).add(reason.page)
    for source in manifest.inputs:
        assert placed.get(source.role, set()) == set(range(1, source.pages + 1)), source.role


@pytest.mark.parametrize("property_id", PROPERTY_IDS)
def test_invariant_2_plan_length_equals_output_page_count(property_id: str, builds: dict) -> None:
    result = builds[property_id]
    assert result.output_path is not None
    assert len(PdfReader(str(result.output_path)).pages) == len(result.manifest.plan)
    assert result.manifest.output is not None
    assert result.manifest.output.pages == len(result.manifest.plan)


@pytest.mark.parametrize("property_id", PROPERTY_IDS)
def test_invariant_3_nothing_reads_reference_or_target(property_id: str, builds: dict) -> None:
    """SPEC §9.3: the composer never opens a path under `reference/` or `target/`."""
    result = builds[property_id]
    paths = [source.file for source in result.manifest.inputs]
    assert all("reference" not in p and "target" not in p for p in paths)
    manifest_text = json.dumps(result.manifest.model_dump(mode="json"))
    assert "/reference/" not in manifest_text
    assert "/target/" not in manifest_text


def test_invariant_3_the_composer_opens_only_planned_sources(
    monkeypatch: pytest.MonkeyPatch, work_root: Path
) -> None:
    """Belt and braces: watch every PdfReader the composer constructs."""
    from crr.compose import composer

    opened: list[str] = []
    real_reader = composer.PdfReader

    def spy(path, *args, **kwargs):  # type: ignore[no-untyped-def]
        opened.append(str(path))
        return real_reader(path, *args, **kwargs)

    monkeypatch.setattr(composer, "PdfReader", spy)

    from crr.classify.golden_classifier import GoldenClassifier

    work = work_root
    settings = Settings(_env_file=None, work_dir=work, publish_root=work / "pub")  # type: ignore[call-arg]
    repository = LocalFsRepository(
        settings.bundle_root,
        CONFIG.properties,
        _schema_for_role,
        publish_root=settings.local_publish_root,
    )
    prop = CONFIG.properties.property("timber-place").to_domain()
    build_property(
        prop,
        "2026-06",
        config=CONFIG,
        settings=settings,
        repository=repository,
        classifier=GoldenClassifier(GOLDEN["timber-place"]),
    )
    assert opened
    assert all("reference" not in p and "target" not in p for p in opened)


def test_invariant_4_two_builds_agree_except_for_the_creation_date(work_root: Path) -> None:
    """SPEC §9.4: byte-identical apart from /CreationDate."""
    from crr.classify.golden_classifier import GoldenClassifier

    outputs = []
    for _run in ("one", "two"):
        work = work_root
        settings = Settings(_env_file=None, work_dir=work, publish_root=work / "pub")  # type: ignore[call-arg]
        repository = LocalFsRepository(
            settings.bundle_root,
            CONFIG.properties,
            _schema_for_role,
            publish_root=settings.local_publish_root,
        )
        prop = CONFIG.properties.property("salmon-crossing").to_domain()
        result = build_property(
            prop,
            "2026-06",
            config=CONFIG,
            settings=settings,
            repository=repository,
            classifier=GoldenClassifier(GOLDEN["salmon-crossing"]),
        )
        assert result.output_path is not None
        outputs.append(result.output_path.read_bytes())

    assert len(outputs[0]) == len(outputs[1])
    assert _without_creation_date(outputs[0]) == _without_creation_date(outputs[1])


def _without_creation_date(pdf: bytes) -> bytes:
    import re

    return re.sub(rb"/CreationDate\s*\([^)]*\)", b"/CreationDate()", pdf)


@pytest.mark.parametrize("property_id", PROPERTY_IDS)
def test_invariant_5_golden_builds_match_expected_output(property_id: str, builds: dict) -> None:
    """SPEC §9.5: all eight BUILT and page-for-page equal to the frozen expectation."""
    result = builds[property_id]
    golden = GOLDEN[property_id]
    assert result.status is BuildStatus.BUILT, [r.code for r in result.reasons]
    assert golden.expected_output is not None
    actual = [
        (i.output_page, i.doc_role, i.section_id, i.record_id, i.source_page)
        for i in result.manifest.plan
    ]
    expected = [
        (e.output_page, e.doc_role, e.section, e.record, e.source_page)
        for e in golden.expected_output
    ]
    assert actual == expected
    assert len(actual) == golden.expected_output_page_count


@pytest.mark.parametrize(
    "fixture",
    [
        "unknown-semantic",
        "duplicate-section-id",
        "invalid-cardinality",
        "duplicate-footer-label",
        "undeclared-source-alias",
        "drop-unknown-section",
    ],
)
def test_invariant_6_config_validation_rejects_each_bad_case(fixture: str) -> None:
    """SPEC §9.6."""
    with pytest.raises(ConfigError):
        load_config(BAD_CONFIG / fixture)


# -- the extra acceptance checks PLAN Phase 4 names ---------------------------------------
@pytest.mark.parametrize("property_id", ["timber-place", "river-falls"])
def test_mccathren_packages_ship_searchable(property_id: str, builds: dict) -> None:
    """D-10: the OCR output *is* the composed source."""
    result = builds[property_id]
    assert result.output_path is not None
    reader = PdfReader(str(result.output_path))
    pm_pages = [i.output_page for i in result.manifest.plan if i.doc_role == "pm_source"]
    for output_page in pm_pages:
        text = reader.pages[output_page - 1].extract_text() or ""
        assert len(text.strip()) >= 40, f"page {output_page} has no text layer"
    pm_input = next(i for i in result.manifest.inputs if i.role == "pm_source")
    assert pm_input.ocr_applied is True
    assert pm_input.ocr_version


def test_the_timber_place_aged_receivable_page_lands_upright(builds: dict) -> None:
    result = builds["timber-place"]
    item = next(i for i in result.manifest.plan if i.section_id == "aged_receivable")
    assert item.transforms == ("copy", "rotate:90")
    assert result.output_path is not None
    page = PdfReader(str(result.output_path)).pages[item.output_page - 1]
    rotate = int(page.get("/Rotate", 0) or 0) % 360
    width, height = float(page.mediabox.width), float(page.mediabox.height)
    effective = (height, width) if rotate in (90, 270) else (width, height)
    assert (round(effective[0]), round(effective[1])) == (792, 612)


@pytest.mark.parametrize("property_id", PROPERTY_IDS)
def test_one_bookmark_per_section(property_id: str, builds: dict) -> None:
    result = builds[property_id]
    assert result.output_path is not None
    outline = PdfReader(str(result.output_path)).outline
    sections = {(i.doc_role, i.section_id, i.record_id) for i in result.manifest.plan}
    assert len(outline) == len(sections)


@pytest.mark.parametrize("property_id", PROPERTY_IDS)
def test_the_manifest_records_the_config_it_was_built_from(property_id: str, builds: dict) -> None:
    manifest = builds[property_id].manifest
    assert len(manifest.config.schema_ref.sha256) == 64
    assert len(manifest.config.output.sha256) == 64
    assert len(manifest.config.properties_sha256) == 64
    assert manifest.classifier.name == "golden"
    assert manifest.cost.api_calls == 0


def test_built_packages_are_published_to_output_not_review(builds: dict) -> None:
    result = builds["fort-grounds"]
    assert result.review_path is None
    assert result.status is BuildStatus.BUILT
