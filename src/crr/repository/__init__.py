"""Source repositories: where inputs come from and where outputs go (SPEC §6.1)."""

from crr.repository.local_fs import LocalFsRepository
from crr.repository.protocol import RepositoryError, SourceRepository

__all__ = ["LocalFsRepository", "RepositoryError", "SourceRepository"]
