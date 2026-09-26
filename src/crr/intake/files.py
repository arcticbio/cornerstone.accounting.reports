"""Which file in a component folder is the current one (SPEC §18.4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

#: Written by the system onto every PDF in a component folder that is not the current one. It
#: is output, never input: the current file is always chosen from all PDFs whatever their
#: names, so deleting the newest file is enough to go back to the one before it (D-21).
SUPERSEDED_PREFIX = "SUPERSEDED - "


@dataclass(frozen=True)
class IntakeFile:
    """One file found in a component folder."""

    id: str
    name: str
    #: When the file's current content arrived — the head revision's time on Drive, which a
    #: rename does not move. Never the file's own modified time (SPEC §18.4).
    uploaded_at: datetime
    md5: str | None = None
    size: int | None = None
    is_pdf: bool = True


@dataclass(frozen=True)
class Choice:
    """The outcome for one component folder."""

    current: IntakeFile | None
    #: The other PDFs, newest first. Each is (or is about to be) named `SUPERSEDED - …`.
    set_aside: tuple[IntakeFile, ...] = ()
    #: Everything that is not a PDF. Listed in the status; never read.
    ignored: tuple[IntakeFile, ...] = ()
    #: (file, new name) for every rename the folder needs to match the choice.
    renames: tuple[tuple[IntakeFile, str], ...] = ()

    @property
    def pdfs(self) -> tuple[IntakeFile, ...]:
        return ((self.current,) if self.current else ()) + self.set_aside

    @property
    def is_empty(self) -> bool:
        return self.current is None and not self.ignored


def strip_prefix(name: str) -> str:
    """`SUPERSEDED - SUPERSEDED - a.pdf` → `a.pdf`. Repeated prefixes come from people copying
    files between folders; strip them all rather than leave a half-marked name."""
    while name.upper().startswith(SUPERSEDED_PREFIX.upper()):
        name = name[len(SUPERSEDED_PREFIX) :]
    return name


def is_superseded_name(name: str) -> bool:
    return name.upper().startswith(SUPERSEDED_PREFIX.upper())


def choose(files: list[IntakeFile]) -> Choice:
    """The newest upload wins; every other PDF is set aside; non-PDFs are ignored.

    An exact tie on upload time — routine on local disk, where `cp -p` or unzip gives files
    the same mtime — breaks on the name *without* the `SUPERSEDED - ` prefix, then on the id.
    Nothing this function renames takes part: breaking on the name as it stands would let the
    rename that marks the loser make it the next run's winner, and the folder would flip, and
    rebuild, on every run.
    """
    pdfs = [f for f in files if f.is_pdf]
    ignored = tuple(sorted((f for f in files if not f.is_pdf), key=lambda f: f.name))
    if not pdfs:
        return Choice(current=None, ignored=ignored)
    ordered = sorted(pdfs, key=lambda f: (f.uploaded_at, strip_prefix(f.name), f.id), reverse=True)
    current, rest = ordered[0], tuple(ordered[1:])
    renames: list[tuple[IntakeFile, str]] = []
    if is_superseded_name(current.name):
        renames.append((current, strip_prefix(current.name)))
    for older in rest:
        if not is_superseded_name(older.name):
            renames.append((older, SUPERSEDED_PREFIX + older.name))
    return Choice(current=current, set_aside=rest, ignored=ignored, renames=tuple(renames))
