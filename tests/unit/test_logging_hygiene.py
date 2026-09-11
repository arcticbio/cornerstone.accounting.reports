"""Nothing sensitive reaches a log line (SPEC §11, §16).

Input PDFs carry tenant names and financials. The rule is absolute: page text, image bytes,
tenant names, file paths and secrets never appear in a log line, whatever the level.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
import structlog

from crr.classify.golden_classifier import GoldenClassifier
from crr.config import load_config
from crr.golden import load_all_golden
from crr.pipeline import build_property
from crr.preprocess.text import page_texts
from crr.repository.local_fs import LocalFsRepository
from crr.settings import Settings

CONFIG = load_config(Path("config"))
GOLDEN = load_all_golden(Path("eval/golden"))
BUNDLE = Path("data/bundle/2026-06")


@pytest.fixture
def captured_logs() -> Iterator[list[dict]]:
    """Capture structlog output as parsed dicts."""
    records: list[dict] = []

    def capture(logger: object, name: str, event_dict: dict) -> str:
        rendered = json.dumps(event_dict, default=str)
        records.append(json.loads(rendered))
        return rendered

    original = structlog.get_config()
    structlog.configure(processors=[capture], cache_logger_on_first_use=False)
    try:
        yield records
    finally:
        structlog.configure(**original)


def _schema_for_role(prop, role):  # type: ignore[no-untyped-def]
    output = CONFIG.output_for_property(prop.id)
    for source in output.sources.values():
        if source.role == role:
            return source.schema_id
    return CONFIG.properties.manager(prop.property_manager).schema_id


def _build(tmp_path: Path):  # type: ignore[no-untyped-def]
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        work_dir=tmp_path / "work",
        publish_root=tmp_path / "published",
        orientation_check=False,
    )
    prop = CONFIG.properties.property("fort-grounds").to_domain()
    repository = LocalFsRepository(
        settings.bundle_root,
        CONFIG.properties,
        _schema_for_role,
        publish_root=settings.local_publish_root,
    )
    return build_property(
        prop,
        "2026-06",
        config=CONFIG,
        settings=settings,
        repository=repository,
        classifier=GoldenClassifier(GOLDEN["fort-grounds"]),
    )


def test_a_full_build_logs_no_page_text(captured_logs: list[dict], tmp_path: Path) -> None:
    result = _build(tmp_path)
    assert result.output_path is not None
    assert captured_logs, "the build logged nothing at all"

    blob = json.dumps(captured_logs)
    pm_source = BUNDLE / GOLDEN["fort-grounds"].document("pm_source").file
    phrases = [
        line
        for text in page_texts(pm_source)
        for line in text.splitlines()
        if len(line) > 25 and " " in line
    ]
    assert phrases, "the fixture should have text that could leak"
    leaked = [phrase for phrase in phrases if phrase in blob]
    assert not leaked, f"page text reached a log line: {leaked[:2]}"


def test_logs_carry_hashes_not_paths_or_image_bytes(
    captured_logs: list[dict], tmp_path: Path
) -> None:
    _build(tmp_path)
    blob = json.dumps(captured_logs)
    assert "Fort Grounds Apartment Homes" not in blob  # the tenant-facing entity name
    assert ".pdf" not in blob  # SPEC §11: log sha256s, not paths
    assert "%PDF" not in blob
    assert "iVBORw0KGgo" not in blob  # base64 PNG magic
    assert any("sha256" in record for record in captured_logs)  # ... but hashes are logged


def test_a_secret_never_reaches_a_log_line(captured_logs: list[dict]) -> None:
    from crr.log import get_logger

    settings = Settings(_env_file=None, anthropic_api_key="sk-ant-secret-value")  # type: ignore[call-arg]
    get_logger("test").info(
        "classify.start", model=settings.model, effort=settings.classifier_effort
    )
    blob = json.dumps(captured_logs)
    assert "sk-ant" not in blob
    assert settings.model in blob  # the model id is not a secret and is worth having


def test_an_ocr_failure_message_carries_no_path() -> None:
    """ocrmypdf echoes file paths in its stderr, and those carry property names."""
    from crr.preprocess.ocr import _redact

    message = "TesseractNotFoundError while reading /data/bundle/Timber Place/scan.pdf"
    assert "Timber Place" not in _redact(message)
    assert "TesseractNotFoundError" in _redact(message)
