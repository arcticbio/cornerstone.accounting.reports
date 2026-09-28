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
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from crr.log import get_logger

log = get_logger(__name__)

FOLDER_MIME = "application/vnd.google-apps.folder"
SCOPES = ("https://www.googleapis.com/auth/drive",)
_FIELDS = "files(id, name, mimeType, size, modifiedTime, createdTime, md5Checksum)"
PDF_MIME = "application/pdf"

#: Every request is retried this many times on 5xx, 429, a rate-limit 403, and a dropped or
#: timed-out connection, with googleapiclient's randomised exponential backoff (at most ~31 s
#: in all). Without it one transient error cost a month its check for the whole run.
RETRIES = 5


class DriveError(Exception):
    """Drive could not be reached, or credentials are unusable."""


@dataclass(frozen=True)
class DriveFile:
    id: str
    name: str
    mime_type: str
    size: int | None = None
    modified_time: str | None = None
    created_time: str | None = None
    md5: str | None = None

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

    def rename(self, file_id: str, name: str) -> None: ...

    def update_content(self, file_id: str, path: Path, name: str | None = None) -> None: ...

    def head_revision_time(self, file_id: str) -> str | None:
        """When the file's current content was uploaded (RFC 3339). A rename does not move it,
        unlike the file's own `modifiedTime` (SPEC §18.4)."""
        ...


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
    """The real thing. Every request is retried (`RETRIES`); see `create_folder` for the one
    that cannot be retried blindly."""

    #: Between `create_folder` attempts; tests replace it.
    _sleep = staticmethod(time.sleep)

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
                .execute(num_retries=RETRIES)
            )
            out.extend(
                DriveFile(
                    id=item["id"],
                    name=item["name"],
                    mime_type=item["mimeType"],
                    size=int(item["size"]) if item.get("size") else None,
                    modified_time=item.get("modifiedTime"),
                    created_time=item.get("createdTime"),
                    md5=item.get("md5Checksum"),
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
                _, done = downloader.next_chunk(num_retries=RETRIES)
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
            .execute(num_retries=RETRIES)
        )
        return DriveFile(
            id=created["id"],
            name=created["name"],
            mime_type=created["mimeType"],
            size=int(created["size"]) if created.get("size") else None,
        )

    def create_folder(self, parent_id: str, name: str) -> DriveFile:
        """Create a folder — the one request not retried blindly.

        `files.create` is not idempotent: a retry after a response lost in transit would leave
        two folders with one name, and for a component folder that silently splits uploads
        between them. So after a transient failure this looks in the parent first, and returns
        the folder if the failed attempt did in fact create it.
        """
        for attempt in range(RETRIES + 1):
            try:
                created = (
                    self._service.files()
                    .create(
                        body={"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]},
                        fields="id, name, mimeType",
                        supportsAllDrives=True,
                    )
                    .execute()
                )
                return DriveFile(
                    id=created["id"], name=created["name"], mime_type=created["mimeType"]
                )
            except Exception as exc:
                if attempt == RETRIES or not _transient(exc):
                    raise
                log.warning("gdrive.create_folder_retry", attempt=attempt + 1)
                self._sleep(random.random() * 2**attempt)
                made = next(
                    (f for f in self.list_children(parent_id) if f.is_folder and f.name == name),
                    None,
                )
                if made is not None:
                    return made
        raise AssertionError("unreachable")  # pragma: no cover - the loop returns or raises

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
        ).execute(num_retries=RETRIES)

    def rename(self, file_id: str, name: str) -> None:
        self._service.files().update(
            fileId=file_id, body={"name": name}, supportsAllDrives=True
        ).execute(num_retries=RETRIES)

    def update_content(self, file_id: str, path: Path, name: str | None = None) -> None:
        """Replace a file's content in place — for the system's own status, index and summary
        files, which are rewritten rather than multiplied."""
        from googleapiclient.http import MediaFileUpload

        body = {"name": name} if name else {}
        self._service.files().update(
            fileId=file_id,
            body=body,
            media_body=MediaFileUpload(str(path)),
            supportsAllDrives=True,
        ).execute(num_retries=RETRIES)

    def head_revision_time(self, file_id: str) -> str | None:
        times: list[str] = []
        page_token: str | None = None
        while True:
            response = (
                self._service.revisions()
                .list(
                    fileId=file_id,
                    fields="nextPageToken, revisions(id, modifiedTime)",
                    pageSize=200,
                    pageToken=page_token,
                )
                .execute(num_retries=RETRIES)
            )
            times.extend(
                r["modifiedTime"] for r in response.get("revisions", []) if r.get("modifiedTime")
            )
            page_token = response.get("nextPageToken")
            if not page_token:
                return max(times) if times else None


def _transient(exc: Exception) -> bool:
    """What googleapiclient itself retries: 5xx and 429 responses, and a connection that
    dropped or timed out (OSError covers both, and SSL errors)."""
    from googleapiclient.errors import HttpError

    if isinstance(exc, HttpError):
        status = int(getattr(exc.resp, "status", 0) or 0)
        return status >= 500 or status == 429
    return isinstance(exc, OSError)
