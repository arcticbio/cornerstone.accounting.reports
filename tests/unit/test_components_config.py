"""Component folders and per-property requirements (SPEC §18.3, §18.5)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from crr.config import ConfigError, load_config

CONFIG = Path("config")


def _config_with(tmp_path: Path, edit) -> Path:  # type: ignore[no-untyped-def]
    root = tmp_path / "config"
    shutil.copytree(CONFIG, root)
    path = root / "properties.yaml"
    data = yaml.safe_load(path.read_text())
    edit(data)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return root


def _property(data: dict, property_id: str) -> dict:  # type: ignore[type-arg]
    return next(p for p in data["properties"] if p["id"] == property_id)


def test_every_property_gets_its_components_in_output_order() -> None:
    bundle = load_config(CONFIG)
    components = bundle.components_for("fort-grounds")
    assert [c.role for c in components] == [
        "pm_source",
        "cornerstone_balance_sheet",
        "cornerstone_profit_loss_ytd",
        "cornerstone_distribution_schedule",
    ]
    assert [c.requirement for c in components] == ["required", "required", "required", "optional"]
    assert components[0].schema_id == "rentmanager-missoula"
    assert components[1].folder == "2 - Balance Sheet"


def test_a_label_drops_the_sort_number() -> None:
    bundle = load_config(CONFIG)
    labels = [c.label for c in bundle.components_for("waypointe")]
    assert labels == [
        "Property Manager Report",
        "Balance Sheet",
        "Profit and Loss",
        "Distribution Schedule",
    ]


def test_a_property_can_override_a_requirement(tmp_path: Path) -> None:
    def edit(data: dict) -> None:  # type: ignore[type-arg]
        _property(data, "timber-place")["components"] = {
            "cornerstone_distribution_schedule": "not_used",
            "cornerstone_profit_loss_ytd": "optional",
        }

    bundle = load_config(_config_with(tmp_path, edit))
    components = {c.role: c.requirement for c in bundle.components_for("timber-place")}
    assert "cornerstone_distribution_schedule" not in components  # not_used: no folder at all
    assert components["cornerstone_profit_loss_ytd"] == "optional"
    assert components["pm_source"] == "required"
    # Other properties keep the output definition's defaults.
    river = {c.role: c.requirement for c in bundle.components_for("river-falls")}
    assert river["cornerstone_distribution_schedule"] == "optional"


def test_an_override_for_a_component_the_property_does_not_have_is_rejected(
    tmp_path: Path,
) -> None:
    def edit(data: dict) -> None:  # type: ignore[type-arg]
        _property(data, "fort-grounds")["components"] = {"rent_roll": "required"}

    with pytest.raises(ConfigError, match="does not use"):
        load_config(_config_with(tmp_path, edit))


def test_an_unknown_requirement_is_rejected(tmp_path: Path) -> None:
    def edit(data: dict) -> None:  # type: ignore[type-arg]
        _property(data, "fort-grounds")["components"] = {"pm_source": "sometimes"}

    with pytest.raises(ConfigError):
        load_config(_config_with(tmp_path, edit))


def test_a_role_without_a_folder_is_rejected(tmp_path: Path) -> None:
    def edit(data: dict) -> None:  # type: ignore[type-arg]
        del data["component_folders"]["cornerstone_balance_sheet"]

    with pytest.raises(ConfigError, match="no folder for role 'cornerstone_balance_sheet'"):
        load_config(_config_with(tmp_path, edit))


@pytest.mark.parametrize("name", ["output", "SUPERSEDED - x", "3 - Profit and Loss"])
def test_a_folder_name_that_would_collide_is_rejected(tmp_path: Path, name: str) -> None:
    def edit(data: dict) -> None:  # type: ignore[type-arg]
        data["component_folders"]["cornerstone_balance_sheet"] = name

    with pytest.raises(ConfigError):
        load_config(_config_with(tmp_path, edit))


def test_a_property_that_uses_nothing_is_rejected(tmp_path: Path) -> None:
    def edit(data: dict) -> None:  # type: ignore[type-arg]
        _property(data, "fort-grounds")["components"] = dict.fromkeys(
            data["component_folders"], "not_used"
        )

    with pytest.raises(ConfigError, match="uses no components"):
        load_config(_config_with(tmp_path, edit))
