"""Writing the manifest and its JSON Schema (SPEC §10)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from crr.manifest.model import BuildManifest

SCHEMA_PATH = Path(__file__).parent / "schema.json"


def manifest_json(manifest: BuildManifest) -> str:
    """Canonical JSON for a manifest: stable key order, 2-space indent, trailing newline."""
    return json.dumps(manifest_dict(manifest), indent=2, sort_keys=False) + "\n"


def manifest_dict(manifest: BuildManifest) -> dict[str, Any]:
    return manifest.model_dump(mode="json", by_alias=True, exclude_none=False)


def write_manifest(manifest: BuildManifest, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(manifest_json(manifest))
    return dest


def json_schema() -> dict[str, Any]:
    """The JSON Schema generated from the pydantic model, committed at schema.json."""
    return BuildManifest.model_json_schema(by_alias=True)


def write_json_schema(dest: Path = SCHEMA_PATH) -> Path:
    dest.write_text(json.dumps(json_schema(), indent=2) + "\n")
    return dest
