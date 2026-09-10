"""Live Drive checks (SPEC §13). Skipped without service-account credentials.

These read; they never write. The folder skeleton is created by hand once per period, not by
a test run.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from crr.config import load_config
from crr.repository.drive_client import GoogleDriveApi
from crr.repository.google_drive import GoogleDriveRepository

pytestmark = [
    pytest.mark.gdrive,
    pytest.mark.skipif(
        not (
            os.environ.get("GOOGLE_SERVICE_ACCOUNT_B64")
            and os.environ.get("CRR_GDRIVE_ROOT_FOLDER_ID")
        ),
        reason="needs GOOGLE_SERVICE_ACCOUNT_B64 and CRR_GDRIVE_ROOT_FOLDER_ID",
    ),
]

CONFIG = load_config(Path("config"))


@pytest.fixture(scope="module")
def api() -> GoogleDriveApi:
    return GoogleDriveApi.from_b64(os.environ["GOOGLE_SERVICE_ACCOUNT_B64"])


@pytest.fixture(scope="module")
def repository(api: GoogleDriveApi) -> GoogleDriveRepository:
    return GoogleDriveRepository(api, os.environ["CRR_GDRIVE_ROOT_FOLDER_ID"], CONFIG.properties)


def test_the_root_folder_is_reachable(api: GoogleDriveApi) -> None:
    children = api.list_children(os.environ["CRR_GDRIVE_ROOT_FOLDER_ID"])
    assert isinstance(children, list)


def test_manager_folder_names_match_the_registry(api: GoogleDriveApi) -> None:
    """Folder names are contractual (SPEC §4.3): a rename in Drive breaks every build."""
    present = {
        child.name
        for child in api.list_children(os.environ["CRR_GDRIVE_ROOT_FOLDER_ID"])
        if child.is_folder
    }
    expected = {pm.folder for pm in CONFIG.properties.property_managers}
    unexpected = present - expected
    assert not unexpected, f"folders in the Drive root that no manager claims: {unexpected}"


def test_listing_a_period_never_raises(repository: GoogleDriveRepository) -> None:
    for entry in CONFIG.properties.properties:
        prop = entry.to_domain()
        periods = repository.list_periods(prop)
        assert all(len(p) == 7 and p[4] == "-" for p in periods)
        for period in periods:
            present = repository.present_inputs(prop, period)
            assert set(present) == set(CONFIG.properties.input_filenames(prop.id))
