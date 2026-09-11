"""structlog wiring. JSON lines to stderr; the human summary goes to stdout via Typer.

Never log page text, image bytes, tenant names or secrets (SPEC §11, §16). Log document
sha256s rather than paths at INFO.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

_configured = False


class _Stderr:
    """A stand-in for `sys.stderr` that resolves it on every write.

    `PrintLoggerFactory(file=sys.stderr)` captures the stream object at configure time — the
    first `get_logger` call in the process. That binds the logger to whatever stderr happened
    to be installed then, which under Typer's `CliRunner` is a per-invocation buffer: the next
    invocation writes to a closed file and the command dies with `ValueError: I/O operation on
    closed file`, in a test whose subject has nothing to do with logging. Resolving late also
    means redirection works the way anyone would expect.
    """

    def write(self, message: str) -> int:
        return sys.stderr.write(message)

    def flush(self) -> None:
        sys.stderr.flush()


def configure(level: str = "INFO") -> None:
    """Configure structlog once per process. Idempotent."""
    global _configured
    if _configured:
        return
    logging.basicConfig(format="%(message)s", stream=sys.stderr, level=getattr(logging, level))
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
        logger_factory=structlog.PrintLoggerFactory(file=_Stderr()),  # type: ignore[arg-type]
        cache_logger_on_first_use=False,
    )
    _configured = True


def get_logger(name: str) -> Any:
    """Return a bound logger; configures logging on first use."""
    configure()
    return structlog.get_logger(name)
