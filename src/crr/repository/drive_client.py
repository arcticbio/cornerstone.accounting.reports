"""A small Drive API surface (SPEC §13).

The repository talks to this, not to `googleapiclient` directly: it is the whole seam the
in-memory fake in the tests replaces, and it keeps the `supportsAllDrives` /
`includeItemsFromAllDrives` flags in exactly one place — forget them on a shared drive and
listing silently returns nothing.
"""

from __future__ import annotations

import base64
import binascii
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from crr.log import get_logger

log = get_logger(__name__)

FOLDER_MIME = "application/vnd.google-apps.folder"
SCOPES = ("https://www.googleapis.com/auth/drive",)
_FIELDS = "files(id, name, mimeType, size, modifiedTime)"


class DriveError(Exception):
    """Drive could not be reached, or credentials are unusable."""


@dataclass(frozen=True)
class DriveFile:
    id: str
    name: str
    mime_type: str
    size: int | None = None
    modified_time: str | None = None

    @property
    def is_folder(self) -> bool:
        return self.mime_type == FOLDER_MIME


class DriveApi(Protocol):
    """What the repository needs from Drive. The fake implements exactly this."""

    def list_children(self, folder_id: str) -> list[DriveFile]: ...

    def download(self, file_id: str, dest: Path) -> Path: ...

    def upload(self, folder_id: str, path: Path, name: str | None = None) -> DriveFile: ...

    def create_folder(self, parent_id: str, name: str) -> DriveFile: ...

    def trash(self, file_id: str) -> None: ...


def credentials_from_b64(encoded: str) -> Any:
    """Service-account credentials from `GOOGLE_SERVICE_ACCOUNT_B64` (SPEC §12).

    The value is base64 so it survives an env var on one line; a raw JSON value is accepted
    too, because that is the mistake everyone makes once.
    """
    from google.oauth2 import service_account

    text = encoded.strip()
    if text.startswith("{"):
        raw = text
    else:
        try:
            raw = base64.b64decode(text, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError) as exc:
            raise DriveError("GOOGLE_SERVICE_ACCOUNT_B64 is neither base64 nor raw JSON") from exc
    try:
        info = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DriveError("GOOGLE_SERVICE_ACCOUNT_B64 does not decode to JSON") from exc
    try:
        # google-auth's constructors are untyped; the return value is opaque to us anyway.
        factory: Any = service_account.Credentials.from_service_account_info
        return factory(info, scopes=list(SCOPES))
    except (ValueError, KeyError) as exc:
        raise DriveError(f"service-account JSON is not usable: {exc}") from exc


class GoogleDriveApi:
    """The real thing."""

    def __init__(self, credentials: Any) -> None:
        from googleapiclient.discovery import build

        self._service = build("drive", "v3", credentials=credentials, cache_discovery=False)

    @classmethod
    def from_b64(cls, encoded: str) -> GoogleDriveApi:
        return cls(credentials_from_b64(encoded))

    def list_children(self, folder_id: str) -> list[DriveFile]:
        out: list[DriveFile] = []
        page_token: str | None = None
        while True:
            response = (
                self._service.files()
                .list(
                    q=f"'{folder_id}' in parents and trashed = false",
                    fields=f"nextPageToken, {_FIELDS}",
                    pageSize=200,
                    pageToken=page_token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            out.extend(
                DriveFile(
                    id=item["id"],
                    name=item["name"],
                    mime_type=item["mimeType"],
                    size=int(item["size"]) if item.get("size") else None,
                    modified_time=item.get("modifiedTime"),
                )
                for item in response.get("files", [])
            )
            page_token = response.get("nextPageToken")
            if not page_token:
                return out

    def download(self, file_id: str, dest: Path) -> Path:
        from googleapiclient.http import MediaIoBaseDownload

        dest.parent.mkdir(parents=True, exist_ok=True)
        request = self._service.files().get_media(fileId=file_id, supportsAllDrives=True)
        buffer = io.FileIO(dest, "wb")
        try:
            downloader = MediaIoBaseDownload(buffer, request, chunksize=4 * 1024 * 1024)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        finally:
            buffer.close()
        return dest

    def upload(self, folder_id: str, path: Path, name: str | None = None) -> DriveFile:
        from googleapiclient.http import MediaFileUpload

        media = MediaFileUpload(str(path), resumable=path.stat().st_size > 5 * 1024 * 1024)
        created = (
            self._service.files()
            .create(
                body={"name": name or path.name, "parents": [folder_id]},
                media_body=media,
                fields="id, name, mimeType, size",
                supportsAllDrives=True,
            )
            .execute()
        )
        return DriveFile(
            id=created["id"],
            name=created["name"],
            mime_type=created["mimeType"],
            size=int(created["size"]) if created.get("size") else None,
        )

    def create_folder(self, parent_id: str, name: str) -> DriveFile:
        created = (
            self._service.files()
            .create(
                body={"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]},
                fields="id, name, mimeType",
                supportsAllDrives=True,
            )
            .execute()
        )
        return DriveFile(id=created["id"], name=created["name"], mime_type=created["mimeType"])

    def trash(self, file_id: str) -> None:
        """Move a file to the trash. Used to clean up the publish preflight probe (SPEC §6.1).

        Trash rather than `files.delete`, which removes permanently: in a **shared drive** only
        a Manager may permanently delete, while a Content manager — the role the runner is meant
        to hold, and the least privilege that lets it publish — may only trash. Using delete
        here made the probe fail to clean up on a correctly configured drive, leaving one file
        behind per run.
        """
        self._service.files().update(
            fileId=file_id, body={"trashed": True}, supportsAllDrives=True
        ).execute()
