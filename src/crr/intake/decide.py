"""Whether to build a property-month, and what its status says (SPEC §18.5, §18.7, §18.8).

A pure function of what the folders hold, what was built before, and the time. The reconciler
gathers the facts; this decides. Each headline here is the name of the status file a reviewer
reads in `output/` — the review surface (D-18).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

from crr.config.loader import Component
from crr.intake.files import Choice, IntakeFile
from crr.intake.state import MonthState, VersionEntry, fingerprint
from crr.models import BuildStatus


class Kind(StrEnum):
    NONE = "none"  # nothing uploaded, nothing built: no status at all
    CURRENT = "current"  # the newest build reflects the current files
    REVIEW = "review"  # … and it needs review
    WAITING = "waiting"  # a required component is missing
    SETTLING = "settling"  # an upload arrived within the settle window
    HELD = "held"  # a file cannot be opened, or the build would cost too much
    FAILED = "failed"  # the last attempt raised; it will be retried
    STOPPED = "stopped"  # failed too often on these files; not retried
    BUILD = "build"  # ready: build now
    READY = "ready"  # ready, but the run ran out of time before starting it: the next run builds
    CLOSED = "closed"  # past the lookback window
    ERROR = "error"  # checking the month raised; nothing was decided; the next run retries


@dataclass(frozen=True)
class ComponentState:
    component: Component
    choice: Choice


@dataclass(frozen=True)
class Verdict:
    kind: Kind
    #: The status file's headline — `STATUS - <headline>.txt` — or None for "write none".
    headline: str | None
    #: One plain sentence for the top of the status body.
    reason: str
    fingerprint: str | None = None

    @property
    def build(self) -> bool:
        return self.kind is Kind.BUILD


def current_files(components: tuple[ComponentState, ...]) -> dict[str, IntakeFile]:
    return {c.component.role: c.choice.current for c in components if c.choice.current is not None}


def built_headline(entry: VersionEntry) -> str:
    if entry.status is BuildStatus.NEEDS_REVIEW:
        return f"Needs review (v{entry.version})"
    return f"Built v{entry.version} (current)"


#: What the headline says about newer files while an older build still stands. "Waiting" asks
#: nothing of anyone; "held" and "failed" mean someone should look (SPEC §18.8).
_STALE = {
    Kind.WAITING: "newer files waiting",
    Kind.SETTLING: "newer files waiting",
    Kind.HELD: "newer files held",
    Kind.FAILED: "newer files failed, will retry",
    Kind.READY: "newer files ready, building next run",
}


def _stale_headline(entry: VersionEntry, kind: Kind) -> str:
    """The newest build still stands, but the files have moved on since."""
    base = (
        f"Needs review (v{entry.version})"
        if entry.status is BuildStatus.NEEDS_REVIEW
        else f"Built v{entry.version}"
    )
    return f"{base} - {_STALE[kind]}"


def _pending(kind: Kind, headline: str, reason: str, state: MonthState, fp: str | None) -> Verdict:
    latest = state.latest
    if latest is not None:
        return Verdict(kind, _stale_headline(latest, kind), reason, fp)
    return Verdict(kind, headline, reason, fp)


def decide(
    components: tuple[ComponentState, ...],
    state: MonthState,
    *,
    now: datetime,
    settle_minutes: int,
    max_failed_attempts: int,
    force: bool = False,
) -> Verdict:
    """Everything up to "build now". Opening the files and the cost ceiling need the files
    themselves, so the reconciler applies those after a `BUILD` verdict (`held`)."""
    current = current_files(components)
    fp = fingerprint(current) if current else None
    latest = state.latest

    if latest is None and all(c.choice.is_empty for c in components):
        return Verdict(Kind.NONE, None, "Nothing has been uploaded for this month yet.")

    if latest is not None and fp == latest.fingerprint and not force:
        kind = Kind.REVIEW if latest.status is BuildStatus.NEEDS_REVIEW else Kind.CURRENT
        reason = f"v{latest.version} was built from exactly the files listed below" + (
            " and needs review — see its REVIEW file." if kind is Kind.REVIEW else "."
        )
        return Verdict(kind, built_headline(latest), reason, fp)

    missing = [
        c.component.label
        for c in components
        if c.component.requirement == "required" and c.choice.current is None
    ]
    if missing:
        return _pending(
            Kind.WAITING,
            "Waiting for " + ", ".join(missing),
            "Nothing new will be built until every required file is here: "
            + ", ".join(missing)
            + ".",
            state,
            fp,
        )

    uploads = [f.uploaded_at for c in components for f in c.choice.pdfs]
    last_upload = max(uploads)
    settled_at = last_upload + timedelta(minutes=settle_minutes)
    if now < settled_at:
        return _pending(
            Kind.SETTLING,
            "Waiting for uploads to settle",
            f"The last upload was at {_stamp(last_upload)}. A build starts once nothing has "
            f"changed for {settle_minutes} minutes, in case more files are on the way.",
            state,
            fp,
        )

    failures = state.failures_for(fp)
    if failures >= max_failed_attempts and not force:
        return Verdict(
            Kind.STOPPED,
            f"Failed {failures} times, stopped retrying",
            f"Building from these files failed {failures} times, so it is no longer retried. "
            "Uploading a new file, or a forced rebuild, will try again.",
            fp,
        )

    return Verdict(Kind.BUILD, None, "Ready to build.", fp)


def deferred(state: MonthState, fp: str | None) -> Verdict:
    """A `BUILD` verdict the run had no time left to start (SPEC §18.9 step 5). Saying so beats
    leaving the last status up: it would still read "Waiting for uploads to settle"."""
    return _pending(
        Kind.READY,
        "Ready - building on the next run",
        "Every file is here and has settled, but this run reached its time limit before it could "
        "start this build. The next run builds it.",
        state,
        fp,
    )


def held(reason: str, detail: str, state: MonthState, fp: str | None) -> Verdict:
    """A `BUILD` verdict that cannot go ahead: a file does not open, or it would cost too much."""
    return _pending(Kind.HELD, f"Held - {reason}", detail, state, fp)


def after_build(
    status: BuildStatus, version: int | None, state: MonthState, fp: str, max_failed: int
) -> Verdict:
    """The status once a build has run. `state` already includes this build or attempt."""
    if status is BuildStatus.FAILED:
        failures = state.failures_for(fp)
        if failures >= max_failed:
            return Verdict(
                Kind.STOPPED,
                f"Failed {failures} times, stopped retrying",
                f"Building from these files failed {failures} times, so it is no longer "
                "retried. Uploading a new file, or a forced rebuild, will try again.",
                fp,
            )
        return _pending(
            Kind.FAILED,
            f"Failed (attempt {failures} of {max_failed}), will retry",
            f"The build failed (attempt {failures} of {max_failed}); the next run tries again.",
            state,
            fp,
        )
    latest = state.latest
    assert latest is not None and latest.version == version
    kind = Kind.REVIEW if status is BuildStatus.NEEDS_REVIEW else Kind.CURRENT
    reason = f"v{version} was built from exactly the files listed below" + (
        " and needs review — see its REVIEW file." if kind is Kind.REVIEW else "."
    )
    return Verdict(kind, built_headline(latest), reason, fp)


def closed(on: date, state: MonthState) -> Verdict:
    latest = state.latest
    tail = f"v{latest.version} is final" if latest else "nothing built"
    return Verdict(
        Kind.CLOSED,
        f"Closed {on.isoformat()} ({tail})",
        f"This month stopped being watched on {on.isoformat()}. Files added or changed after "
        "that are ignored.",
        latest.fingerprint if latest else None,
    )


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M UTC")
