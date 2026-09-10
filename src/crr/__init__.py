"""Cornerstone Report Runner — assembles quarterly investor report PDFs."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

try:  # pragma: no cover - trivial packaging fallback
    __version__ = _version("crr")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
