"""Every Drive request is retried, and folder creation is retried safely (audit finding 5).

A fake googleapiclient service stands in for Drive: it records how each request was executed
and can fail on cue, so the retry policy is checked without a network.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httplib2
import pytest
from googleapiclient.errors import HttpError

from crr.repository import drive_client
from crr.repository.drive_client import FOLDER_MIME, RETRIES, GoogleDriveApi


def _http_error(status: int) -> HttpError:
    return HttpError(httplib2.Response({"status": status}), b'{"error": {"errors": []}}')


class _Request:
    def __init__(self, service: _Service, kind: str, result: dict[str, Any]) -> None:
        self._service, self._kind, self._result = service, kind, result

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        self._service.executed.append((self._kind, kwargs))
        failures = self._service.fail.get(self._kind)
        if failures:
            failure = failures.pop(0)
            if failure == "created-anyway":  # the request landed, the response did not
                self._service.listing.append(
                    {"id": "made", "name": "2 - Balance Sheet", "mimeType": FOLDER_MIME}
                )
                raise _http_error(503)
            raise failure
        return self._result


class _Service:
    """Just enough of `build("drive", "v3")`."""

    def __init__(self) -> None:
        self.executed: list[tuple[str, dict[str, Any]]] = []
        self.fail: dict[str, list[Any]] = {}
        self.listing: list[dict[str, Any]] = []

    def files(self) -> _Service:
        return self

    def revisions(self) -> _Revisions:
        return _Revisions(self)

    def list(self, **_kwargs: Any) -> _Request:
        return _Request(self, "list", {"files": list(self.listing)})

    def create(self, **kwargs: Any) -> _Request:
        body = kwargs["body"]
        kind = "create-folder" if body.get("mimeType") == FOLDER_MIME else "upload"
        return _Request(self, kind, {"id": "new", "name": body["name"], "mimeType": FOLDER_MIME})

    def update(self, **_kwargs: Any) -> _Request:
        return _Request(self, "update", {})

    def get_media(self, **_kwargs: Any) -> object:
        return object()


class _Revisions:
    def __init__(self, service: _Service) -> None:
        self._service = service

    def list(self, **_kwargs: Any) -> _Request:
        return _Request(self._service, "revisions", {"revisions": []})


@pytest.fixture
def api() -> GoogleDriveApi:
    client = GoogleDriveApi.__new__(GoogleDriveApi)
    client._service = _Service()
    client._sleep = lambda _seconds: None  # type: ignore[method-assign]
    return client


def _service(api: GoogleDriveApi) -> _Service:
    service: _Service = api._service
    return service


def test_every_request_is_sent_with_retries(
    api: GoogleDriveApi, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chunks: list[dict[str, Any]] = []

    class Download:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def next_chunk(self, **kwargs: Any) -> tuple[None, bool]:
            chunks.append(kwargs)
            return None, True

    monkeypatch.setattr("googleapiclient.http.MediaIoBaseDownload", Download)
    local = tmp_path / "status.txt"
    local.write_text("x")
    api.list_children("folder")
    api.upload("folder", local)
    api.trash("file")
    api.rename("file", "new name")
    api.update_content("file", local)
    api.head_revision_time("file")
    api.download("file", tmp_path / "copy")
    executed = _service(api).executed
    assert [kind for kind, _ in executed] == [
        "list", "upload", "update", "update", "update", "revisions"
    ]  # fmt: skip
    assert all(kwargs == {"num_retries": RETRIES} for _, kwargs in executed)
    assert chunks == [{"num_retries": RETRIES}]


def test_a_folder_create_that_landed_is_found_not_repeated(api: GoogleDriveApi) -> None:
    """The create succeeded but its response was lost: a blind retry would make a second
    `2 - Balance Sheet`, and uploads would be split between the two."""
    service = _service(api)
    service.fail["create-folder"] = ["created-anyway"]
    folder = api.create_folder("month", "2 - Balance Sheet")
    assert folder.id == "made"
    assert [kind for kind, _ in service.executed].count("create-folder") == 1


def test_a_folder_create_that_failed_is_tried_again(api: GoogleDriveApi) -> None:
    service = _service(api)
    service.fail["create-folder"] = [_http_error(503), ConnectionResetError()]
    folder = api.create_folder("month", "2 - Balance Sheet")
    assert folder.id == "new"
    assert [kind for kind, _ in service.executed].count("create-folder") == 3


def test_a_permanent_error_is_raised_at_once(api: GoogleDriveApi) -> None:
    service = _service(api)
    slept: list[float] = []
    api._sleep = slept.append  # type: ignore[method-assign]
    service.fail["create-folder"] = [_http_error(403)]
    with pytest.raises(HttpError):
        api.create_folder("month", "2 - Balance Sheet")
    assert [kind for kind, _ in service.executed] == ["create-folder"]
    assert slept == []


def test_retries_are_bounded(api: GoogleDriveApi) -> None:
    service = _service(api)
    service.fail["create-folder"] = [_http_error(503)] * (RETRIES + 1)
    with pytest.raises(HttpError):
        api.create_folder("month", "2 - Balance Sheet")
    assert [kind for kind, _ in service.executed].count("create-folder") == RETRIES + 1


def test_transient_means_what_googleapiclient_retries() -> None:
    assert drive_client._transient(_http_error(500))
    assert drive_client._transient(_http_error(429))
    assert drive_client._transient(TimeoutError())
    assert not drive_client._transient(_http_error(404))
    assert not drive_client._transient(ValueError())
