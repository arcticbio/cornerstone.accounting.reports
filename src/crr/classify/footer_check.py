"""The footer check (SPEC §7.4).

Not a classifier: a post-processor that reads the report name a producer prints in the page
footer and compares it to the label the model chose. Disagreement sends the build to review;
it never overrides the model (D-05).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from crr.config.models import SourceSchema
from crr.models import PageClassification


@dataclass(frozen=True)
class FooterVerdict:
    """What the footer says, if anything."""

    #: The schema `footer_label` that matched, verbatim from the YAML.
    label: str | None
    #: The section id that label belongs to.
    section_id: str | None
    #: The line the label was read from — for the review report, never logged.
    line: str | None = None

    @property
    def matched(self) -> bool:
        return self.label is not None


NO_FOOTER = FooterVerdict(label=None, section_id=None)


def _candidate_lines(text: str, footer_regex: str) -> list[str]:
    """The last line matching the footer regex, and the line above it.

    Two producers, two shapes: Rent Manager prints `<Report Name>  <timestamp>  Page N of M
    rentmanager.com ...` on one line, so the matching line itself starts with the report name.
    Cobalt prints the report name on its own line with `Created on <date> Page N` beneath it,
    so the regex matches only the vendor string and the name is the line above (SPEC §7.4).
    """
    lines = [line for line in text.splitlines() if line.strip()]
    pattern = re.compile(footer_regex)
    for index in range(len(lines) - 1, -1, -1):
        if pattern.search(lines[index]):
            out = [lines[index]]
            if index > 0:
                out.append(lines[index - 1])
            return out
    return []


def check_footer(schema: SourceSchema, text: str | None) -> FooterVerdict:
    """Read the report name off the page footer, if this schema prints one."""
    if not text or not schema.fingerprint.footer_regex:
        return NO_FOOTER
    labelled = [(s.footer_label, s.id) for s in schema.sections if s.footer_label]
    if not labelled:
        return NO_FOOTER
    for line in _candidate_lines(text, schema.fingerprint.footer_regex):
        folded = line.casefold()
        # Longest label wins: "Rent Roll - Bank" beats "Rent Roll" on the same line.
        matches = [(lbl, sid) for lbl, sid in labelled if folded.startswith(lbl.casefold())]
        if matches:
            label, section_id = max(matches, key=lambda pair: len(pair[0]))
            return FooterVerdict(label=label, section_id=section_id, line=line)
    return NO_FOOTER


def apply_footer_check(
    classifications: list[PageClassification],
    schema: SourceSchema,
    texts: dict[int, str | None],
) -> list[PageClassification]:
    """Fill `footer_label` / `footer_agrees` on every page that has a readable footer."""
    out: list[PageClassification] = []
    for page in classifications:
        verdict = check_footer(schema, texts.get(page.page))
        if not verdict.matched:
            out.append(page.model_copy(update={"footer_label": None, "footer_agrees": None}))
            continue
        out.append(
            page.model_copy(
                update={
                    "footer_label": verdict.label,
                    "footer_agrees": verdict.section_id == page.section_id,
                }
            )
        )
    return out
