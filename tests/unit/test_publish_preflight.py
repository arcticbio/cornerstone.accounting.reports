"""The publish preflight (SPEC §6.1, B-09).

`publish` is the last stage of a build, so an unwritable repository is discovered after OCR,
classification and composition have already been paid for. On Drive that is not hypothetical:
a service account has no storage quota of its own, so every upload fails
`403 storageQuotaExceeded` while folder creation and reads keep working — and the setup looks
healthy right up until the first byte. A full eight-property run costs ~$4.72 in classification
before that happens, every time.

The probe writes a byte and removes it. Nothing cheaper is trustworthy: the folder's
`capabilities.canAddChildren` reads `true` in exactly the failing case, because creating a
*folder* really is permitted — folders consume no quota.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crr.config import load_config
from crr.repository.drive_client import DriveFile
from crr.repository.google_drive import GoogleDriveRepository
from crr.repository.local_fs import LocalFsRepository
from crr.repository.protocol import RepositoryError
from tests.unit.fake_drive import FakeDrive

CONFIG = load_config(Path("config"))
REGISTRY = CONFIG.properties

#: The message Drive actually returns when the root is a My Drive folder (B-09).
QUOTA_ERROR = (
    "Service Accounts do not have storage quota. Leverage shared drives, or use OAuth "
    "delegation instead."
)


class _RefusesUploads(FakeDrive):
    """A Drive that lets you make folders but not files — the B-09 shape exactly."""

    def upload(self, folder_id: str, path: Path, name: str | None = None) -> DriveFile:
        raise RuntimeError(f'<HttpError 403> "{QUOTA_ERROR}"')


class _RefusesDeletes(FakeDrive):
    def delete(self, file_id: str) -> None:
        raise RuntimeError("<HttpError 403> insufficientFilePermissions")


class TestDrive:
    def test_a_writable_drive_passes(self) -> None:
        drive = FakeDrive()
        GoogleDriveRepository(drive, drive.root_id, REGISTRY).preflight_publish()
        assert len(drive.uploads) == 1

    def test_the_probe_is_removed_again(self) -> None:
        """A preflight that littered the root every run would be its own bug report."""
        drive = FakeDrive()
        GoogleDriveRepository(drive, drive.root_id, REGISTRY).preflight_publish()
        assert drive.deleted, "the probe was uploaded and never deleted"
        assert drive.names_in(drive.root_id) == []

    def test_the_probe_is_named_so_a_human_knows_what_it_is(self) -> None:
        drive = FakeDrive()
        GoogleDriveRepository(drive, drive.root_id, REGISTRY).preflight_publish()
        _, name = drive.uploads[0]
        assert name.startswith(".crr-preflight-")

    def test_a_refused_upload_is_a_repository_error(self) -> None:
        drive = _RefusesUploads()
        repo = GoogleDriveRepository(drive, drive.root_id, REGISTRY)
        with pytest.raises(RepositoryError) as caught:
            repo.preflight_publish()
        message = str(caught.value)
        # The message has to carry the remedy: whoever sees it is not the person who wrote it.
        assert "storage" in message.lower()
        assert "shared drive" in message
        assert "docs/SETUP-GOOGLE-DRIVE.md" in message

    def test_a_failed_cleanup_does_not_fail_the_run(self) -> None:
        """The probe is what mattered and it passed; a leftover byte is not worth a failure."""
        drive = _RefusesDeletes()
        GoogleDriveRepository(drive, drive.root_id, REGISTRY).preflight_publish()
        assert len(drive.uploads) == 1

    def test_nothing_is_left_on_local_disk(self, tmp_path: Path) -> None:
        """The probe is written to a temp file to upload it; it must not survive."""
        drive = FakeDrive()
        GoogleDriveRepository(drive, drive.root_id, REGISTRY).preflight_publish()
        _, name = drive.uploads[0]
        assert not (Path("/tmp") / name).exists()


class TestLocal:
    def test_a_writable_root_passes(self, tmp_path: Path) -> None:
        repo = LocalFsRepository(tmp_path / "bundle", REGISTRY, publish_root=tmp_path / "out")
        repo.preflight_publish()
        assert list((tmp_path / "out").iterdir()) == [], "the probe was left behind"

    def test_an_unwritable_root_is_a_repository_error(self, tmp_path: Path) -> None:
        blocked = tmp_path / "blocked"
        blocked.write_text("this is a file, so it cannot also be a directory")
        repo = LocalFsRepository(tmp_path / "bundle", REGISTRY, publish_root=blocked / "out")
        with pytest.raises(RepositoryError, match="cannot write to the publish root"):
            repo.preflight_publish()


def test_the_default_is_a_no_op_not_a_failure() -> None:
    """A repository that cannot be probed cheaply simply does not, and still builds."""
    from crr.repository.protocol import SourceRepository

    assert SourceRepository.preflight_publish(object()) is None  # type: ignore[arg-type]


class TestTheRunStopsBeforeSpending:
    """The whole point: a run against an unwritable repository must cost nothing."""

    def test_build_exits_one_and_makes_no_model_calls(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from typer.testing import CliRunner

        from crr import cli

        classifiers_built: list[str] = []

        def _explode(*args: object, **kwargs: object) -> None:
            raise AssertionError("a classifier was constructed after a failed preflight")

        def _unwritable(*args: object, **kwargs: object) -> object:
            class _Repo:
                name = "gdrive"

                def preflight_publish(self) -> None:
                    raise RepositoryError("Service Accounts do not have storage quota")

            return _Repo()

        monkeypatch.setattr(cli, "_make_repository", _unwritable)
        monkeypatch.setattr(cli, "_make_classifier", _explode)
        result = CliRunner().invoke(
            cli.app, ["build", "--period", "2026-06", "--classifier", "golden"]
        )
        assert result.exit_code == 1
        assert classifiers_built == []
        assert "cannot publish" in result.output
        assert "no model calls were made" in result.output
