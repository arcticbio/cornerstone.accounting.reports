"""The property registry, `config/properties.yaml` (SPEC §4.3)."""

from __future__ import annotations

import calendar

from pydantic import BaseModel, ConfigDict, model_validator

from crr.models import Property, PropertyRecord

_STRICT = ConfigDict(extra="forbid", frozen=True)


class PropertyManager(BaseModel):
    model_config = _STRICT

    id: str
    name: str
    folder: str
    schema_id: str
    output_definition: str
    pm_source_filename: str

    @model_validator(mode="before")
    @classmethod
    def _rename_schema(cls, data: object) -> object:
        # `schema` shadows a BaseModel attribute; the YAML keeps the friendlier spelling.
        if isinstance(data, dict) and "schema" in data:
            data = dict(data)
            data["schema_id"] = data.pop("schema")
        return data


class PropertyEntry(BaseModel):
    """One property as written in the YAML, before it becomes a domain `Property`."""

    model_config = _STRICT

    id: str
    name: str
    folder: str
    property_manager: str
    owning_entity: str
    records: tuple[PropertyRecord, ...]

    def to_domain(self) -> Property:
        return Property(
            id=self.id,
            name=self.name,
            folder=self.folder,
            property_manager=self.property_manager,
            owning_entity=self.owning_entity,
            records=self.records,
        )


class PropertyRegistry(BaseModel):
    model_config = _STRICT

    period_format: str
    period_folder_template: str
    property_managers: tuple[PropertyManager, ...]
    cornerstone_files: dict[str, str]
    properties: tuple[PropertyEntry, ...]

    @model_validator(mode="after")
    def _cross_references(self) -> PropertyRegistry:
        pm_ids = {pm.id for pm in self.property_managers}
        for prop in self.properties:
            if prop.property_manager not in pm_ids:
                raise ValueError(
                    f"property {prop.id!r} names unknown property_manager {prop.property_manager!r}"
                )
            if not prop.records:
                raise ValueError(f"property {prop.id!r} has no records")
        ids = [p.id for p in self.properties]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate property id(s): {', '.join(dupes)}")
        return self

    def manager(self, pm_id: str) -> PropertyManager:
        for pm in self.property_managers:
            if pm.id == pm_id:
                return pm
        raise KeyError(f"no property manager {pm_id!r}")

    def property(self, property_id: str) -> PropertyEntry:
        for prop in self.properties:
            if prop.id == property_id:
                return prop
        raise KeyError(f"no property {property_id!r}")

    def manager_for(self, property_id: str) -> PropertyManager:
        return self.manager(self.property(property_id).property_manager)

    def period_folder(self, period: str) -> str:
        """`2026-06` → `2026-06 June`, per `period_folder_template`."""
        yyyy, _, mm = period.partition("-")
        if not (len(yyyy) == 4 and yyyy.isdigit() and len(mm) == 2 and mm.isdigit()):
            raise ValueError(f"period {period!r} is not YYYY-MM")
        month = int(mm)
        if not 1 <= month <= 12:
            raise ValueError(f"period {period!r} has no month {month}")
        return self.period_folder_template.format(
            yyyy=yyyy, mm=mm, month_name=calendar.month_name[month]
        )

    def period_label(self, period: str) -> str:
        """`2026-06` → `June 2026`, the label used in titles and filenames."""
        yyyy, _, mm = period.partition("-")
        self.period_folder(period)  # validates
        return f"{calendar.month_name[int(mm)]} {yyyy}"

    def input_filenames(self, property_id: str) -> dict[str, str]:
        """role → expected filename for one property (SPEC §6.1)."""
        pm = self.manager_for(property_id)
        return {"pm_source": pm.pm_source_filename, **self.cornerstone_files}
