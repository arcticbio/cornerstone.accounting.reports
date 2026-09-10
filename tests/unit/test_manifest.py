"""The build manifest and its committed JSON Schema (SPEC §10)."""

from __future__ import annotations

import json
from pathlib import Path

from crr.manifest import (
    MANIFEST_VERSION,
    SCHEMA_PATH,
    BuildManifest,
    ClassifierBlock,
    ConfigBlock,
    ConfigRef,
    json_schema,
    manifest_dict,
    manifest_json,
    write_manifest,
)
from crr.manifest.model import PropertyBlock
from crr.models import BuildStatus


def _manifest() -> BuildManifest:
    return BuildManifest(
        status=BuildStatus.BUILT,
        property=PropertyBlock(
            id="waypointe",
            name="WayPointe",
            property_manager="missoula",
            owning_entity="WayPointe Apartment Homes LP",
        ),
        period="2026-06",
        config=ConfigBlock(
            schema_ref=ConfigRef(id="rentmanager-missoula", version=1, sha256="a" * 64),
            output=ConfigRef(id="missoula-investor-report", version=1, sha256="b" * 64),
            properties_sha256="c" * 64,
        ),
        classifier=ClassifierBlock(name="golden"),
    )


def test_the_wire_format_spells_the_config_key_schema() -> None:
    data = manifest_dict(_manifest())
    assert data["config"]["schema"]["id"] == "rentmanager-missoula"
    assert "schema_ref" not in data["config"]
    assert data["manifest_version"] == MANIFEST_VERSION


def test_a_manifest_round_trips() -> None:
    original = _manifest()
    restored = BuildManifest.model_validate(json.loads(manifest_json(original)))
    assert restored.property.id == original.property.id
    assert restored.status is BuildStatus.BUILT


def test_write_manifest_creates_parents(tmp_path: Path) -> None:
    path = write_manifest(_manifest(), tmp_path / "deep" / "build-manifest.json")
    assert path.is_file()
    assert path.read_text().endswith("\n")


def test_the_committed_schema_matches_the_model() -> None:
    """`schema.json` is generated; regenerate it with
    `uv run python -c 'from crr.manifest import write_json_schema; write_json_schema()'`."""
    committed = json.loads(SCHEMA_PATH.read_text())
    assert committed == json_schema()


def test_every_golden_build_manifest_still_validates() -> None:
    """The eight manifests committed in Phase 4 are the regression fixture for §10."""
    files = sorted(Path("eval/reports/golden-build-2026-06").glob("*.json"))
    assert len(files) == 8
    for path in files:
        manifest = BuildManifest.model_validate(json.loads(path.read_text()))
        assert manifest.status is BuildStatus.BUILT
        assert manifest.output is not None
        assert manifest.output.pages == len(manifest.plan)
        assert manifest.review_reasons == []
