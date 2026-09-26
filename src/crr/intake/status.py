"""The status file: the review surface (SPEC §18.8, D-18).

Its *name* is the headline, so a reviewer reads the state from the folder listing. Its body is
plain text for someone who has never seen this system: which file was used for each component,
what was set aside or ignored and why, and what each version changed. It never contains page
text, tenant names or figures (SPEC §16) — only filenames, times, and version numbers.
"""

from __future__ import annotations

from datetime import date, datetime

from crr.intake.decide import ComponentState, Verdict
from crr.intake.files import SUPERSEDED_PREFIX, is_superseded_name
from crr.intake.state import InputSig, MonthState, VersionEntry
from crr.models import BuildStatus

STATUS_PREFIX = "STATUS - "
ROOT_SUMMARY = "_STATUS - All properties.txt"


def status_filename(headline: str) -> str:
    return f"{STATUS_PREFIX}{_safe(headline)}.txt"


def is_status_filename(name: str) -> bool:
    return name.startswith(STATUS_PREFIX) and name.endswith(".txt")


def headline_of(filename: str) -> str:
    return filename[len(STATUS_PREFIX) : -len(".txt")]


def render_status(
    *,
    property_name: str,
    period_label: str,
    verdict: Verdict,
    components: tuple[ComponentState, ...],
    state: MonthState,
    closes: date,
    settle_minutes: int,
) -> str:
    assert verdict.headline is not None
    labels = {c.component.role: c.component.label for c in components}
    lines = [
        f"{property_name} - {period_label}",
        f"Status: {verdict.headline}",
        "",
        verdict.reason,
        "",
        "Files",
    ]
    for c in components:
        label = c.component.label
        current = c.choice.current
        if current is not None:
            lines.append(
                f"  {label}: {_quote(current.name)} (uploaded {_stamp(current.uploaded_at)})"
            )
        elif c.component.requirement == "required":
            lines.append(f"  {label}: missing - required; nothing new is built without it")
        else:
            lines.append(f"  {label}: none - optional; the report is built without it")
        for older in c.choice.set_aside:
            name = older.name if is_superseded_name(older.name) else SUPERSEDED_PREFIX + older.name
            lines.append(
                f"      set aside: {_quote(name)} (uploaded {_stamp(older.uploaded_at)}) - "
                "a newer file is in this folder"
            )
        for other in c.choice.ignored:
            lines.append(f"      ignored: {_quote(other.name)} - not a PDF")

    if state.versions:
        lines += ["", "Versions (newest first)"]
        ordered = sorted(state.versions, key=lambda v: v.version)
        previous: VersionEntry | None = None
        history: list[str] = []
        for entry in ordered:
            history.append(
                f"  v{entry.version} - {_stamp(entry.built_at)} - {_status_word(entry.status)} - "
                + _changes(previous, entry, labels)
            )
            previous = entry
        lines += reversed(history)

    if state.attempts:
        lines += ["", "Failed attempts (nothing was published for these)"]
        for attempt in sorted(state.attempts, key=lambda a: a.at, reverse=True)[:5]:
            lines.append(f"  {_stamp(attempt.at)} - {attempt.error}")

    lines += [
        "",
        "How this folder works",
        "  Put one PDF in each numbered folder. Any filename is fine.",
        "  If a folder holds more than one PDF, the newest upload is used and the others are",
        f'  renamed "{SUPERSEDED_PREFIX}...". To go back to an older file, delete the newer one.',
        f"  A new version is built about {settle_minutes} minutes after the last upload, and",
        "  older versions stay in this folder.",
        f"  Changes after {closes.isoformat()} are ignored.",
        "",
    ]
    return "\n".join(lines)


def summary_line(property_name: str, period_label: str, headline: str) -> str:
    return f"{property_name} - {period_label} - {headline}"


def render_summary(lines: list[str], as_of: datetime) -> str:
    body = [
        "Investor report status - one line per property, newest month with any files",
        "",
        *lines,
        "",
        f"Last checked {_stamp(as_of)}. Open a property's month folder, then output/, for detail.",
        "",
    ]
    return "\n".join(body)


def _changes(previous: VersionEntry | None, entry: VersionEntry, labels: dict[str, str]) -> str:
    if previous is None:
        return "first build"
    before = {i.role: i for i in previous.inputs}
    after = {i.role: i for i in entry.inputs}
    notes: list[str] = []
    for role in [*labels, *sorted((set(before) | set(after)) - set(labels))]:
        label = labels.get(role, role)
        old, new = before.get(role), after.get(role)
        if old is None and new is not None:
            notes.append(f"{label} added (uploaded {_stamp(new.uploaded_at)})")
        elif old is not None and new is None:
            notes.append(f"{label} removed")
        elif old is not None and new is not None and not _same(old, new):
            notes.append(f"{label} replaced (uploaded {_stamp(new.uploaded_at)})")
    return "; ".join(notes) if notes else "same files, rebuilt on request"


def _same(a: InputSig, b: InputSig) -> bool:
    return a.file_id == b.file_id and a.md5 == b.md5


def _status_word(status: BuildStatus) -> str:
    return {
        BuildStatus.BUILT: "built",
        BuildStatus.NEEDS_REVIEW: "needs review",
        BuildStatus.FAILED: "failed",
    }[status]


def _quote(name: str) -> str:
    return f'"{name}"'


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M UTC")


def _safe(headline: str) -> str:
    """A headline becomes a filename on Drive and on local disk: no path separators."""
    return headline.replace("/", "-").replace("\\", "-").replace(":", "-")
