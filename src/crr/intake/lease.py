"""One run at a time (SPEC §18.9).

Container Apps starts a scheduled execution even while the previous one runs (A-14), and
`Build a period` runs the same image from Actions alongside Azure. Two runs over the same
month publish the same files twice, create the same folder twice, and overwrite each other's
index. So a run first takes a lease: a small system file at the root, written, then read back
to confirm this run is the one that wrote it. A second run that finds a live lease does
nothing. A crashed run's lease lapses on its own after `CRR_RUN_LEASE_S` — the replica
timeout — so it can hold up at most one scheduled run.

Drive has no atomic create-if-absent, so this is a lease, not a lock: the write-then-read-back
settles near-simultaneous starts, a run re-checks it before each build, and the reconciler's
re-read before publishing (§18.9 step 4) remains the backstop.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, ValidationError

#: At the root, beside the summary. Rewritten in place; never more than one kept.
LEASE_FILE = "_LEASE - reconcile run (do not edit).json"


class Lease(BaseModel):
    model_config = ConfigDict(extra="ignore")

    owner: str
    #: For a person reading the file: which machine is running.
    host: str = ""
    acquired_at: datetime
    expires_at: datetime
    released_at: datetime | None = None

    def held_at(self, now: datetime) -> bool:
        return self.released_at is None and now < self.expires_at


def parse(text: str | None) -> Lease | None:
    """The lease in `text`, or None when there is none — including when the file cannot be
    read as one: a damaged lease must never stop every run for good."""
    if not text:
        return None
    try:
        return Lease.model_validate_json(text)
    except ValidationError:
        return None
