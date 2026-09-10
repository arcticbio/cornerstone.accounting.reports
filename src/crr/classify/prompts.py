"""Prompt rendering and exemplar selection (SPEC §7.2, §7.5).

Prompts are Jinja2 files under `classify/prompts/<schema_id>/v<N>.md`, one directory per
schema so a manager's prompt can be revised — and its `prompt_version` bumped — without
touching the others. The shared body lives in `_shared/` and is included by each.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound

from crr.config.models import SourceSchema
from crr.golden import GoldenProperty
from crr.models import PageClassification

PROMPT_ROOT = Path(__file__).parent / "prompts"
DEFAULT_PROMPT_VERSION = "v1"

#: How many labelled exemplar pages to include per section (SPEC §7.2 point 4).
MAX_EXEMPLARS_PER_SECTION = 2


@lru_cache(maxsize=1)
def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(PROMPT_ROOT),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=False,
    )


def prompt_versions(schema_id: str) -> list[str]:
    """Every prompt version shipped for a schema, oldest first."""
    directory = PROMPT_ROOT / schema_id
    if not directory.is_dir():
        return []
    return sorted(p.stem for p in directory.glob("v*.md"))


def render_system_prompt(schema: SourceSchema, prompt_version: str = DEFAULT_PROMPT_VERSION) -> str:
    """The cached system block: role, fingerprint, record scope and the section catalogue."""
    try:
        template = _environment().get_template(f"{schema.schema_id}/{prompt_version}.md")
    except TemplateNotFound as exc:
        raise FileNotFoundError(
            f"no prompt {prompt_version!r} for schema {schema.schema_id!r} "
            f"(have: {', '.join(prompt_versions(schema.schema_id)) or 'none'})"
        ) from exc
    return template.render(schema=schema)


def render_user_header(
    *, page: int, page_count: int, doc_role: str, previous: PageClassification | None
) -> str:
    return (
        _environment()
        .get_template("_shared/user_header.md")
        .render(page=page, page_count=page_count, doc_role=doc_role, previous=previous)
    )


def render_user_text(text: str | None) -> str:
    return _environment().get_template("_shared/user_text.md").render(text=text)


@dataclass(frozen=True)
class Exemplar:
    """One labelled page image shipped in the cached system block."""

    section_id: str
    is_continuation: bool
    property_id: str
    image_path: Path

    @property
    def caption(self) -> str:
        return (
            f"Exemplar: section_id={self.section_id}, "
            f"continuation={'true' if self.is_continuation else 'false'}"
        )

    def image_base64(self) -> str:
        return base64.standard_b64encode(self.image_path.read_bytes()).decode("ascii")


def select_exemplars(
    schema: SourceSchema,
    golden: dict[str, GoldenProperty],
    images: dict[tuple[str, str, int], Path],
    *,
    for_property: str,
    exemplar_policy: str = "exclude_same_property",
    max_per_section: int = MAX_EXEMPLARS_PER_SECTION,
) -> list[Exemplar]:
    """Up to `max_per_section` labelled pages per section (SPEC §7.2 point 4).

    Pages from a *different* property of the same manager are preferred; the property under
    test is excluded entirely under `exclude_same_property`, which is what keeps an eval run
    from scoring the model against its own answer key.

    `images` maps (property_id, doc_role, page) → rendered PNG; only pages present there can
    be used, so the caller controls what has been rasterised.
    """
    same_manager = [
        g for g in golden.values() if g.schema_id == schema.schema_id or _uses(g, schema)
    ]
    out: list[Exemplar] = []
    for section in schema.sections:
        chosen: list[Exemplar] = []
        for prefer_other_property in (True, False):
            if len(chosen) >= max_per_section:
                break
            for g in sorted(same_manager, key=lambda g: g.property_id):
                if g.property_id == for_property:
                    if exemplar_policy == "exclude_same_property" or prefer_other_property:
                        continue
                elif not prefer_other_property:
                    continue  # already considered in the first pass
                for doc in g.documents:
                    if doc.schema_id != schema.schema_id:
                        continue
                    for page in doc.pages:
                        if page.section != section.id or len(chosen) >= max_per_section:
                            continue
                        image = images.get((g.property_id, doc.role, page.page))
                        if image is None:
                            continue
                        chosen.append(
                            Exemplar(
                                section_id=section.id,
                                is_continuation=page.continuation,
                                property_id=g.property_id,
                                image_path=image,
                            )
                        )
        out.extend(chosen)
    return out


def _uses(golden: GoldenProperty, schema: SourceSchema) -> bool:
    return any(doc.schema_id == schema.schema_id for doc in golden.documents)
