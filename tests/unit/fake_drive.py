"""An in-memory Drive: enough of the API for the repository tests (SPEC §15)."""

from __future__ import annotations

import hashlib
import itertools
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from crr.repository.drive_client import FOLDER_MIME, DriveFile

EPOCH = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%S.000Z")


@dataclass
class _Node:
    id: str
    name: str
    mime_type: str
    parent: str | None
    content: bytes = b""
    children: list[str] = field(default_factory=list)
    created: datetime = EPOCH
    modified: datetime = EPOCH
    #: When the current content arrived. A rename moves `modified`, never this.
    revision: datetime = EPOCH


class FakeDrive:
    """Tracks every call, so tests can assert that nothing was deleted or overwritten."""

    def __init__(self, root_name: str = "root") -> None:
        self._ids = itertools.count(1)
        self.root_id = "folder-0"
        self._nodes: dict[str, _Node] = {
            self.root_id: _Node(self.root_id, root_name, FOLDER_MIME, None)
        }
        self.list_calls = 0
        self.uploads: list[tuple[str, str]] = []
        self.created_folders: list[str] = []
        self.deleted: list[str] = []
        self.renames: list[tuple[str, str]] = []
        self.updates: list[str] = []
        self.revision_calls = 0
        #: The fake's clock: what `created`/`modified`/`revision` are stamped with.
        self.now = EPOCH

    # -- construction helpers ---------------------------------------------------------
    def add_folder(self, parent_id: str, name: str) -> str:
        node = _Node(f"folder-{next(self._ids)}", name, FOLDER_MIME, parent_id)
        self._nodes[node.id] = node
        self._nodes[parent_id].children.append(node.id)
        return node.id

    def add_file(
        self,
        parent_id: str,
        name: str,
        content: bytes = b"%PDF-1.4\n",
        *,
        at: datetime | None = None,
        mime: str = "application/pdf",
    ) -> str:
        when = at or self.now
        node = _Node(
            f"file-{next(self._ids)}",
            name,
            mime,
            parent_id,
            content,
            created=when,
            modified=when,
            revision=when,
        )
        self._nodes[node.id] = node
        self._nodes[parent_id].children.append(node.id)
        return node.id

    def add_path(self, *names: str) -> str:
        """`add_path("PM", "Property", "2026-06 June", "inputs")` → the deepest folder id."""
        current = self.root_id
        for name in names:
            existing = next(
                (
                    child
                    for child in self._nodes[current].children
                    if self._nodes[child].name == name
                ),
                None,
            )
            current = existing if existing else self.add_folder(current, name)
        return current

    def names_in(self, folder_id: str) -> list[str]:
        return [self._nodes[child].name for child in self._nodes[folder_id].children]

    def find(self, *names: str) -> str | None:
        current = self.root_id
        for name in names:
            match = next(
                (c for c in self._nodes[current].children if self._nodes[c].name == name), None
            )
            if match is None:
                return None
            current = match
        return current

    # -- DriveApi ---------------------------------------------------------------------
    def list_children(self, folder_id: str) -> list[DriveFile]:
        self.list_calls += 1
        node = self._nodes.get(folder_id)
        if node is None:
            return []
        return [
            DriveFile(
                id=child.id,
                name=child.name,
                mime_type=child.mime_type,
                size=len(child.content) if child.mime_type != FOLDER_MIME else None,
                modified_time=_iso(child.modified),
                created_time=_iso(child.created),
                md5=hashlib.md5(child.content).hexdigest()
                if child.mime_type != FOLDER_MIME
                else None,
            )
            for child in (self._nodes[c] for c in node.children)
        ]

    def download(self, file_id: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self._nodes[file_id].content)
        return dest

    def upload(self, folder_id: str, path: Path, name: str | None = None) -> DriveFile:
        final = name or path.name
        self.uploads.append((folder_id, final))
        file_id = self.add_file(folder_id, final, path.read_bytes())
        return DriveFile(id=file_id, name=final, mime_type="application/pdf")

    def create_folder(self, parent_id: str, name: str) -> DriveFile:
        self.created_folders.append(name)
        folder_id = self.add_folder(parent_id, name)
        return DriveFile(id=folder_id, name=name, mime_type=FOLDER_MIME)

    def trash(self, file_id: str) -> None:
        self.deleted.append(file_id)
        node = self._nodes.pop(file_id, None)
        if node is None:
            return
        for parent in self._nodes.values():
            if file_id in parent.children:
                parent.children.remove(file_id)

    def rename(self, file_id: str, name: str) -> None:
        self.renames.append((file_id, name))
        node = self._nodes[file_id]
        node.name = name
        node.modified = self.now  # Drive moves modifiedTime on a rename…

    def update_content(self, file_id: str, path: Path, name: str | None = None) -> None:
        self.updates.append(file_id)
        node = self._nodes[file_id]
        node.content = path.read_bytes()
        node.modified = node.revision = self.now
        if name:
            node.name = name

    def head_revision_time(self, file_id: str) -> str | None:
        self.revision_calls += 1
        return _iso(self._nodes[file_id].revision)  # …but not the head revision's time

    # -- test helpers -------------------------------------------------------------------
    def content_of(self, file_id: str) -> bytes:
        return self._nodes[file_id].content

    def child_named(self, folder_id: str, name: str) -> str | None:
        return next(
            (c for c in self._nodes[folder_id].children if self._nodes[c].name == name), None
        )
