"""The production classifier (SPEC §7.2, §7.3).

One request per page, sequential within a document because each page's prompt carries the
previous page's label. Two prefixes are identical for every page of a document and each takes
a 1-hour cache breakpoint: the instruction block (system) and the labelled exemplar images
(the head of the user turn). Pages 2..N read both from cache.
"""

from __future__ import annotations

import base64
import time
from typing import Any

from anthropic import Anthropic, APIStatusError, RateLimitError
from anthropic.types import ImageBlockParam, Message, MessageParam, TextBlockParam, ToolParam
from pydantic import ValidationError

from crr.classify.prompts import (
    DEFAULT_PROMPT_VERSION,
    Exemplar,
    render_system_prompt,
    render_user_header,
    render_user_text,
)
from crr.classify.protocol import ClassificationResult, PageInput, Usage
from crr.config.models import SourceSchema
from crr.log import get_logger
from crr.models import Orientation, PageClassification, SourceDocument
from crr.settings import Settings

log = get_logger(__name__)

TOOL_NAME = "classify_page"
MAX_TOKENS = 400
UNKNOWN = "unknown"
#: Backoff for the errors the SDK's own retries do not cover (SPEC §7.3).
BACKOFF_SECONDS = (2, 4, 8, 16)
CACHE_CONTROL: Any = {"type": "ephemeral", "ttl": "1h"}

UserBlock = TextBlockParam | ImageBlockParam


def build_tool(schema: SourceSchema) -> ToolParam:
    """The forced tool. Its enum is the schema's vocabulary plus `unknown`, so an invented
    section is rejected at the API rather than by us (SPEC §7.2)."""
    return {
        "name": TOOL_NAME,
        "description": "Record the classification of exactly one page.",
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "section_id": {
                    "type": "string",
                    "enum": [*[s.id for s in schema.sections], UNKNOWN],
                },
                "is_continuation": {"type": "boolean"},
                "record_qualifier": {"type": ["string", "null"]},
                "orientation": {"type": "string", "enum": [o.value for o in Orientation]},
                # No `minimum`/`maximum` here, and no `maxLength` on the string: the API
                # rejects JSON Schema range and length keywords in a tool's input_schema
                # ("For 'number' type, properties maximum, minimum are not supported").
                # The bounds live in the descriptions for the model, and are enforced for
                # real in `_parse` — PageClassification.confidence is Field(ge=0, le=1), and
                # evidence is truncated. An out-of-range value fails validation, which makes
                # the page `unknown` and sends the build to review (D-12).
                "confidence": {
                    "type": "number",
                    "description": "How certain this label is, from 0.0 to 1.0 inclusive.",
                },
                "evidence": {
                    "type": "string",
                    "description": "What on the page decided it. At most 300 characters.",
                },
            },
            "required": [
                "section_id",
                "is_continuation",
                "record_qualifier",
                "orientation",
                "confidence",
                "evidence",
            ],
        },
        "strict": True,
    }


def _image_block(data_b64: str) -> ImageBlockParam:
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png", "data": data_b64},
    }


def build_system_blocks(schema: SourceSchema, prompt_version: str) -> list[TextBlockParam]:
    """The cached instruction prefix: role, fingerprint, record scope, section catalogue.

    The Messages API's `system` field carries text blocks only, so the exemplar *images* sit
    at the head of the user turn instead (`build_exemplar_blocks`) rather than in the system
    prompt as SPEC §7.2 originally described. Both prefixes are per-document constants and
    both are cached, so the caching behaviour the spec asked for is unchanged.
    """
    return [
        {
            "type": "text",
            "text": render_system_prompt(schema, prompt_version),
            "cache_control": CACHE_CONTROL,
        }
    ]


def build_exemplar_blocks(exemplars: list[Exemplar]) -> list[UserBlock]:
    """Labelled example pages — image then one-line caption — with the cache breakpoint on
    the last block."""
    if not exemplars:
        return []
    blocks: list[UserBlock] = [{"type": "text", "text": "## Labelled example pages"}]
    for exemplar in exemplars:
        blocks.append(_image_block(exemplar.image_base64()))
        blocks.append({"type": "text", "text": exemplar.caption})
    blocks[-1]["cache_control"] = CACHE_CONTROL
    return blocks


def build_page_blocks(
    page: PageInput,
    *,
    page_count: int,
    doc_role: str,
    previous: PageClassification | None,
    image_b64: str,
) -> list[UserBlock]:
    """The uncached tail: previous-page context, this page's image, this page's text."""
    return [
        {
            "type": "text",
            "text": render_user_header(
                page=page.page, page_count=page_count, doc_role=doc_role, previous=previous
            ),
        },
        _image_block(image_b64),
        {"type": "text", "text": render_user_text(page.text)},
    ]


class AnthropicClassifier:
    """Vision classification against a schema's section catalogue."""

    needs_page_images = True

    def __init__(
        self,
        settings: Settings,
        exemplars: list[Exemplar] | None = None,
        prompt_version: str = DEFAULT_PROMPT_VERSION,
        client: Anthropic | None = None,
    ) -> None:
        if client is None and not settings.anthropic_api_key:
            raise RuntimeError(
                "No classifier key: set CRR_ANTHROPIC_API_KEY (or ANTHROPIC_API_KEY); "
                "use --classifier golden to run without one"
            )
        self._settings = settings
        self._exemplars = exemplars or []
        self.prompt_version = prompt_version
        self._client = client or Anthropic(api_key=settings.anthropic_api_key, max_retries=4)

    @property
    def name(self) -> str:
        return f"anthropic:{self._settings.model}:{self.prompt_version}"

    # -- one request -------------------------------------------------------------------
    def _call(
        self, system: list[TextBlockParam], user: list[UserBlock], tool: ToolParam
    ) -> Message:
        """One request, with backoff over rate limits and 5xx on top of the SDK's retries."""
        message: MessageParam = {"role": "user", "content": user}
        last: Exception | None = None
        for attempt, delay in enumerate((0, *BACKOFF_SECONDS)):
            if delay:
                time.sleep(delay)
            try:
                return self._client.messages.create(
                    model=self._settings.model,
                    max_tokens=MAX_TOKENS,
                    output_config={"effort": self._settings.classifier_effort},
                    system=system,
                    messages=[message],
                    tools=[tool],
                    tool_choice={"type": "tool", "name": TOOL_NAME},
                )
            except RateLimitError as exc:
                last = exc
                log.warning("classify.rate_limited", attempt=attempt)
            except APIStatusError as exc:
                if exc.status_code < 500:
                    raise
                last = exc
                log.warning("classify.server_error", attempt=attempt, status=exc.status_code)
        raise RuntimeError(f"classification failed after retries: {last}") from last

    @staticmethod
    def _tool_input(response: Message) -> dict[str, Any] | None:
        if response.stop_reason == "refusal":
            # A safety decline is not a label. Review over guess (D-12): the page becomes
            # `unknown`, which sends the build to the review queue rather than to output/.
            log.warning("classify.refusal")
            return None
        for block in response.content:
            if block.type == "tool_use" and block.name == TOOL_NAME:
                return dict(block.input) if isinstance(block.input, dict) else None
        return None

    @staticmethod
    def _usage(response: Message, latency_ms: int) -> Usage:
        usage = response.usage
        return Usage(
            input_tokens=usage.input_tokens or 0,
            cache_read_tokens=usage.cache_read_input_tokens or 0,
            cache_write_tokens=usage.cache_creation_input_tokens or 0,
            output_tokens=usage.output_tokens or 0,
            api_calls=1,
            latency_ms=latency_ms,
        )

    def _parse(
        self, payload: dict[str, Any] | None, doc_role: str, page: int
    ) -> PageClassification | str:
        """Returns the classification, or a string describing why it could not be built."""
        if payload is None:
            return "no classify_page tool call in the response"
        try:
            return PageClassification(
                doc_role=doc_role,
                page=page,
                section_id=str(payload["section_id"]),
                is_continuation=bool(payload["is_continuation"]),
                record_qualifier=payload.get("record_qualifier"),
                orientation=Orientation(payload["orientation"]),
                confidence=float(payload["confidence"]),
                evidence=str(payload["evidence"])[:300],
                classifier=self.name,
            )
        except (ValidationError, KeyError, ValueError, TypeError) as exc:
            log.warning(
                "classify.parse_failed", doc_role=doc_role, page=page, error=type(exc).__name__
            )
            return f"{type(exc).__name__}: {exc}"

    # -- one document ------------------------------------------------------------------
    def classify(
        self, doc: SourceDocument, schema: SourceSchema, pages: list[PageInput]
    ) -> ClassificationResult:
        tool = build_tool(schema)
        system = build_system_blocks(schema, self.prompt_version)
        exemplars = build_exemplar_blocks(self._exemplars)
        result = ClassificationResult()
        previous: PageClassification | None = None

        for page in pages:
            image_b64 = base64.standard_b64encode(page.image_path.read_bytes()).decode("ascii")
            user: list[UserBlock] = [
                *exemplars,
                *build_page_blocks(
                    page,
                    page_count=doc.page_count,
                    doc_role=doc.role,
                    previous=previous,
                    image_b64=image_b64,
                ),
            ]
            parsed = self._attempt(system, user, tool, result, doc.role, page.page)
            if isinstance(parsed, str):
                # One repair attempt with the validation error appended (SPEC §7.2).
                repair: list[UserBlock] = [
                    *user,
                    {
                        "type": "text",
                        "text": (
                            f"Your previous tool input was rejected: {parsed}. "
                            "Return exactly one valid classify_page call."
                        ),
                    },
                ]
                parsed = self._attempt(system, repair, tool, result, doc.role, page.page)

            label = (
                parsed
                if isinstance(parsed, PageClassification)
                else PageClassification(
                    doc_role=doc.role,
                    page=page.page,
                    section_id=UNKNOWN,
                    is_continuation=False,
                    record_qualifier=None,
                    orientation=Orientation.UPRIGHT,
                    confidence=0.0,
                    evidence="schema_violation",
                    classifier=self.name,
                )
            )
            result.pages.append(label)
            previous = label
            log.info(
                "classify.page",
                doc_role=doc.role,
                page=page.page,
                section_id=label.section_id,
                confidence=round(label.confidence, 3),
                cache_read_tokens=result.usage.cache_read_tokens,
            )
        return result

    def _attempt(
        self,
        system: list[TextBlockParam],
        user: list[UserBlock],
        tool: ToolParam,
        result: ClassificationResult,
        doc_role: str,
        page: int,
    ) -> PageClassification | str:
        started = time.monotonic()
        response = self._call(system, user, tool)
        result.usage.add(self._usage(response, int((time.monotonic() - started) * 1000)))
        return self._parse(self._tool_input(response), doc_role, page)


def estimate_usd(usage: Usage, model: str, settings: Settings) -> float:
    """USD estimate from the settings price table (SPEC §7.3)."""
    price = settings.price_table.get(model)
    if price is None:
        return 0.0
    per_mtok = 1_000_000
    return round(
        usage.input_tokens / per_mtok * price.input
        + usage.cache_read_tokens / per_mtok * price.cache_read
        + usage.cache_write_tokens / per_mtok * price.cache_write
        + usage.output_tokens / per_mtok * price.output,
        6,
    )
