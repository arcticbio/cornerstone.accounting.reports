"""Source repositories: where inputs come from and where outputs go (SPEC §6.1)."""

from crr.repository.drive_client import DriveApi, DriveError, DriveFile, GoogleDriveApi
from crr.repository.google_drive import GoogleDriveRepository
from crr.repository.local_fs import LocalFsRepository
from crr.repository.protocol import RepositoryError, SourceRepository

__all__ = [
    "DriveApi",
    "DriveError",
    "DriveFile",
    "GoogleDriveApi",
    "GoogleDriveRepository",
    "LocalFsRepository",
    "RepositoryError",
    "SourceRepository",
]
