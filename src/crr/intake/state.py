"""What has been built for one property-month, kept beside the builds (SPEC §18.7).

`output/manifests/state.json` is an index over the `vN.json` manifests plus the failed
attempts, which publish no manifest. It exists so a run can decide and write a status from one
small download instead of every manifest. The manifests remain the record; the index can be
rebuilt from them.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from crr.intake.files import IntakeFile
from crr.models import BuildStatus

_STRICT = ConfigDict(extra="forbid")

STATE_FILE = "state.json"


class InputSig(BaseModel):
    """Enough about one input to tell whether it changed, and to say so in plain words."""

    model_config = _STRICT

    role: str
    file_id: str
    md5: str | None = None
    name: str
    uploaded_at: datetime

    @classmethod
    def of(cls, role: str, file: IntakeFile) -> InputSig:
        return cls(
            role=role, file_id=file.id, md5=file.md5, name=file.name, uploaded_at=file.uploaded_at
        )


class VersionEntry(BaseModel):
    model_config = _STRICT

    version: int
    built_at: datetime
    status: BuildStatus
    fingerprint: str
    output_file: str
    inputs: list[InputSig] = Field(default_factory=list)
    review_codes: list[str] = Field(default_factory=list)


class Attempt(BaseModel):
    """A build that failed with an exception. Nothing was published for it."""

    model_config = _STRICT

    fingerprint: str
    at: datetime
    error: str


class MonthState(BaseModel):
    model_config = _STRICT

    versions: list[VersionEntry] = Field(default_factory=list)
    attempts: list[Attempt] = Field(default_factory=list)

    @property
    def latest(self) -> VersionEntry | None:
        return max(self.versions, key=lambda v: v.version) if self.versions else None

    @property
    def next_version(self) -> int:
        latest = self.latest
        return latest.version + 1 if latest else 1

    def failures_for(self, fingerprint: str | None) -> int:
        return sum(1 for a in self.attempts if a.fingerprint == fingerprint)


def fingerprint(current: dict[str, IntakeFile]) -> str:
    """Identity of an input set: which file, with which content, in which component.

    Drive reports `md5Checksum` without a download, so an unchanged month costs a listing. A
    file without one (never the case for an uploaded PDF) falls back to size and upload time.
    """
    lines = []
    for role in sorted(current):
        f = current[role]
        content = f.md5 or f"{f.size}:{f.uploaded_at.isoformat()}"
        lines.append(f"{role}\t{f.id}\t{content}")
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()
