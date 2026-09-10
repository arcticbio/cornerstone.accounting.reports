"""Message construction, caching, retries, repair and refusal handling (SPEC §7.2, §7.3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from anthropic import APIStatusError, RateLimitError

from crr.classify.anthropic_classifier import (
    BACKOFF_SECONDS,
    TOOL_NAME,
    AnthropicClassifier,
    build_exemplar_blocks,
    build_system_blocks,
    build_tool,
    estimate_usd,
)
from crr.classify.prompts import Exemplar
from crr.classify.protocol import PageInput, Usage
from crr.config import load_config
from crr.models import SourceDocument
from crr.settings import Settings

CONFIG = load_config(Path("config"))
SCHEMA = CONFIG.schemas["rentmanager-missoula"]


class _Usage:
    def __init__(self, cache_read: int = 0, cache_write: int = 0) -> None:
        self.input_tokens = 100
        self.cache_read_input_tokens = cache_read
        self.cache_creation_input_tokens = cache_write
        self.output_tokens = 40


class _ToolUse:
    type = "tool_use"
    name = TOOL_NAME

    def __init__(self, payload: dict[str, Any]) -> None:
        self.input = payload


class _Response:
    def __init__(
        self, payload: dict[str, Any] | None, *, cache_read: int = 0, stop_reason: str = "tool_use"
    ) -> None:
        self.content = [_ToolUse(payload)] if payload is not None else []
        self.usage = _Usage(cache_read=cache_read)
        self.stop_reason = stop_reason


class _FakeMessages:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class _FakeClient:
    def __init__(self, responses: list[Any]) -> None:
        self.messages = _FakeMessages(responses)


VALID = {
    "section_id": "owner_statement",
    "is_continuation": False,
    "record_qualifier": "Fort Grounds Apartment Homes",
    "orientation": "upright",
    "confidence": 0.93,
    "evidence": "Title block reads Owner Statement.",
}


def _settings() -> Settings:
    return Settings(_env_file=None, anthropic_api_key="sk-test")  # type: ignore[call-arg]


def _doc(pages: int = 2) -> SourceDocument:
    return SourceDocument(
        role="pm_source",
        schema_id=SCHEMA.schema_id,
        path=Path("x.pdf"),
        sha256="a" * 64,
        page_count=pages,
        has_text_layer=True,
    )


@pytest.fixture
def page_images(tmp_path: Path) -> list[PageInput]:
    out = []
    for n in (1, 2):
        path = tmp_path / f"p{n}.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + bytes([n]) * 32)
        out.append(PageInput(page=n, image_path=path, text=f"page {n} text"))
    return out


def test_the_tool_enum_is_the_schema_vocabulary_plus_unknown() -> None:
    tool = build_tool(SCHEMA)
    enum = tool["input_schema"]["properties"]["section_id"]["enum"]  # type: ignore[index]
    assert set(enum) == SCHEMA.section_ids | {"unknown"}
    assert tool["strict"] is True
    assert tool["input_schema"]["additionalProperties"] is False  # type: ignore[index]


def test_the_system_prefix_carries_a_one_hour_cache_breakpoint() -> None:
    blocks = build_system_blocks(SCHEMA, "v1")
    assert blocks[-1]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert "Section catalogue" in blocks[0]["text"]


def test_exemplars_are_image_then_caption_with_one_breakpoint(tmp_path: Path) -> None:
    image = tmp_path / "e.png"
    image.write_bytes(b"x")
    blocks = build_exemplar_blocks(
        [
            Exemplar("owner_statement", False, "lolo-peak-village", image),
            Exemplar("owner_statement", True, "lolo-peak-village", image),
        ]
    )
    types = [b["type"] for b in blocks]
    assert types == ["text", "image", "text", "image", "text"]
    assert sum(1 for b in blocks if "cache_control" in b) == 1
    assert blocks[-1]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert blocks[2]["text"] == "Exemplar: section_id=owner_statement, continuation=false"


def test_no_exemplars_means_no_blocks() -> None:
    assert build_exemplar_blocks([]) == []


def test_the_request_forces_the_tool_and_omits_temperature(page_images: list[PageInput]) -> None:
    client = _FakeClient([_Response(VALID), _Response(VALID, cache_read=900)])
    classifier = AnthropicClassifier(_settings(), client=client)  # type: ignore[arg-type]
    classifier.classify(_doc(), SCHEMA, page_images)

    first = client.messages.calls[0]
    assert first["tool_choice"] == {"type": "tool", "name": TOOL_NAME}
    assert "temperature" not in first  # rejected on this model family (SPEC §7.2, A-02)
    assert first["output_config"] == {"effort": "low"}
    assert first["max_tokens"] == 400


def test_the_cached_prefix_is_byte_identical_across_pages(page_images: list[PageInput]) -> None:
    client = _FakeClient([_Response(VALID), _Response(VALID, cache_read=900)])
    AnthropicClassifier(_settings(), client=client).classify(  # type: ignore[arg-type]
        _doc(), SCHEMA, page_images
    )
    first, second = client.messages.calls
    assert first["system"] == second["system"]
    assert first["tools"] == second["tools"]


def test_the_previous_page_label_is_carried_into_the_next_prompt(
    page_images: list[PageInput],
) -> None:
    client = _FakeClient([_Response(VALID), _Response(VALID)])
    AnthropicClassifier(_settings(), client=client).classify(  # type: ignore[arg-type]
        _doc(), SCHEMA, page_images
    )
    first_header = client.messages.calls[0]["messages"][0]["content"][0]["text"]
    second_header = client.messages.calls[1]["messages"][0]["content"][0]["text"]
    assert "section_id=none" in first_header
    assert "section_id=owner_statement" in second_header
    assert "Fort Grounds Apartment Homes" in second_header


def test_page_text_and_image_are_sent_uncached(page_images: list[PageInput]) -> None:
    client = _FakeClient([_Response(VALID), _Response(VALID)])
    AnthropicClassifier(_settings(), client=client).classify(  # type: ignore[arg-type]
        _doc(), SCHEMA, page_images
    )
    content = client.messages.calls[0]["messages"][0]["content"]
    assert [b["type"] for b in content] == ["text", "image", "text"]
    assert all("cache_control" not in b for b in content)
    assert "page 1 text" in content[2]["text"]


def test_token_usage_is_summed_across_pages(page_images: list[PageInput]) -> None:
    client = _FakeClient([_Response(VALID), _Response(VALID, cache_read=900)])
    result = AnthropicClassifier(_settings(), client=client).classify(  # type: ignore[arg-type]
        _doc(), SCHEMA, page_images
    )
    assert result.usage.api_calls == 2
    assert result.usage.input_tokens == 200
    assert result.usage.cache_read_tokens == 900
    assert result.usage.output_tokens == 80


def test_an_invalid_payload_is_repaired_once_then_recorded_as_unknown(
    page_images: list[PageInput],
) -> None:
    bad = {**VALID, "confidence": 7.5}  # outside 0..1
    client = _FakeClient([_Response(bad), _Response(VALID)])
    result = AnthropicClassifier(
        _settings(), client=client
    ).classify(  # type: ignore[arg-type]
        _doc(1), SCHEMA, page_images[:1]
    )
    assert len(client.messages.calls) == 2
    repair_text = client.messages.calls[1]["messages"][0]["content"][-1]["text"]
    assert "rejected" in repair_text
    assert result.pages[0].section_id == "owner_statement"  # the repair succeeded


def test_two_invalid_payloads_become_a_schema_violation(page_images: list[PageInput]) -> None:
    bad = {**VALID, "orientation": "sideways"}
    client = _FakeClient([_Response(bad), _Response(bad)])
    result = AnthropicClassifier(
        _settings(), client=client
    ).classify(  # type: ignore[arg-type]
        _doc(1), SCHEMA, page_images[:1]
    )
    assert result.pages[0].section_id == "unknown"
    assert result.pages[0].evidence == "schema_violation"
    assert result.pages[0].confidence == 0.0


def test_a_refusal_becomes_unknown_rather_than_a_guess(page_images: list[PageInput]) -> None:
    """D-12: review over guess. A safety decline is not a label."""
    refused = _Response(None, stop_reason="refusal")
    client = _FakeClient([refused, refused])
    result = AnthropicClassifier(
        _settings(), client=client
    ).classify(  # type: ignore[arg-type]
        _doc(1), SCHEMA, page_images[:1]
    )
    assert result.pages[0].section_id == "unknown"


def test_rate_limits_and_server_errors_are_retried(
    page_images: list[PageInput], monkeypatch: pytest.MonkeyPatch
) -> None:
    slept: list[float] = []
    monkeypatch.setattr("crr.classify.anthropic_classifier.time.sleep", slept.append)
    rate_limited = RateLimitError("slow down", response=_HttpResponse(429), body=None)
    server_error = APIStatusError("boom", response=_HttpResponse(503), body=None)
    client = _FakeClient([rate_limited, server_error, _Response(VALID)])
    result = AnthropicClassifier(
        _settings(), client=client
    ).classify(  # type: ignore[arg-type]
        _doc(1), SCHEMA, page_images[:1]
    )
    assert result.pages[0].section_id == "owner_statement"
    assert slept == [BACKOFF_SECONDS[0], BACKOFF_SECONDS[1]]


def test_a_client_error_is_not_retried(page_images: list[PageInput]) -> None:
    client = _FakeClient([APIStatusError("bad request", response=_HttpResponse(400), body=None)])
    with pytest.raises(APIStatusError):
        AnthropicClassifier(_settings(), client=client).classify(  # type: ignore[arg-type]
            _doc(1), SCHEMA, page_images[:1]
        )


def test_missing_api_key_is_refused_at_construction() -> None:
    settings = Settings(_env_file=None, anthropic_api_key=None)  # type: ignore[call-arg]
    with pytest.raises(RuntimeError, match="CRR_ANTHROPIC_API_KEY"):
        AnthropicClassifier(settings)


def test_cost_estimate_uses_the_price_table() -> None:
    settings = _settings()
    usage = Usage(
        input_tokens=1_000_000,
        cache_read_tokens=1_000_000,
        cache_write_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    price = settings.price_table["claude-opus-5"]
    expected = price.input + price.cache_read + price.cache_write + price.output
    assert estimate_usd(usage, "claude-opus-5", settings) == pytest.approx(expected)
    assert estimate_usd(usage, "no-such-model", settings) == 0.0


class _HttpResponse:
    """The minimum an anthropic SDK error needs."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.headers: dict[str, str] = {}
        self.request = None


def test_tool_schema_avoids_keywords_the_api_rejects() -> None:
    """The Messages API rejects JSON Schema range/length keywords in a tool's input_schema.

    This is invisible to every other test in this file, which drives a fake client: the
    schema is only validated server-side. It cost a full round of `pytest -m api` to find
    ("tools.0.custom: For 'number' type, properties maximum, minimum are not supported"),
    so it is pinned here. The bounds are enforced in `_parse` via PageClassification.
    """
    tool = build_tool(SCHEMA)
    banned = {
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "maxLength",
        "minLength",
        "multipleOf",
        "pattern",
        "minItems",
        "maxItems",
    }

    def walk(node: object, path: str = "") -> list[str]:
        found: list[str] = []
        if isinstance(node, dict):
            for key, value in node.items():
                if key in banned:
                    found.append(f"{path}.{key}")
                found.extend(walk(value, f"{path}.{key}"))
        elif isinstance(node, list):
            for i, item in enumerate(node):
                found.extend(walk(item, f"{path}[{i}]"))
        return found

    assert walk(tool["input_schema"]) == []
