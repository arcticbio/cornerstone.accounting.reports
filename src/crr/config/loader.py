"""Loading and validating the config tree (SPEC §4, §9.6).

`load_config` never half-loads: it collects every problem it can see across all three formats
and raises one `ConfigError` listing them, so `crr validate-config` reports a fixable set
rather than the first thing that broke.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from crr.config.models import OutputDefinition, SourceSchema
from crr.config.properties import PropertyRegistry
from crr.preprocess.text import sha256_file
from crr.resolve.address import AddressError, parse_address


class ConfigError(Exception):
    """One or more configuration problems. `problems` is the human-readable list."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems) if problems else "invalid configuration")

    def __str__(self) -> str:
        return "\n".join(f"- {p}" for p in self.problems)


@dataclass(frozen=True)
class ConfigBundle:
    """Everything in `config/`, validated and cross-checked."""

    schemas: dict[str, SourceSchema]
    outputs: dict[str, OutputDefinition]
    properties: PropertyRegistry
    sha256: dict[str, str]

    def schema_for_property(self, property_id: str) -> SourceSchema:
        return self.schemas[self.properties.manager_for(property_id).schema_id]

    def output_for_property(self, property_id: str) -> OutputDefinition:
        return self.outputs[self.properties.manager_for(property_id).output_definition]


def _load_yaml(path: Path) -> object:
    with path.open("rb") as fh:
        return yaml.safe_load(fh)


def _describe(exc: ValidationError, path: Path) -> list[str]:
    out: list[str] = []
    for error in exc.errors():
        location = ".".join(str(p) for p in error["loc"]) or "(root)"
        out.append(f"{path.name}: {location}: {error['msg']}")
    return out


def load_config(config_dir: Path) -> ConfigBundle:
    """Load `config/` and validate it. Raises `ConfigError` with every problem found."""
    problems: list[str] = []
    shas: dict[str, str] = {}

    schemas: dict[str, SourceSchema] = {}
    for path in sorted((config_dir / "schemas").glob("*.yaml")):
        shas[f"schemas/{path.name}"] = sha256_file(path)
        try:
            schema = SourceSchema.model_validate(_load_yaml(path))
        except ValidationError as exc:
            problems.extend(_describe(exc, path))
            continue
        if schema.schema_id != path.stem:
            problems.append(
                f"{path.name}: schema_id {schema.schema_id!r} does not match the filename"
            )
        schemas[schema.schema_id] = schema

    outputs: dict[str, OutputDefinition] = {}
    for path in sorted((config_dir / "outputs").glob("*.yaml")):
        shas[f"outputs/{path.name}"] = sha256_file(path)
        try:
            output = OutputDefinition.model_validate(_load_yaml(path))
        except ValidationError as exc:
            problems.extend(_describe(exc, path))
            continue
        if output.output_id != path.stem:
            problems.append(
                f"{path.name}: output_id {output.output_id!r} does not match the filename"
            )
        outputs[output.output_id] = output

    registry: PropertyRegistry | None = None
    properties_path = config_dir / "properties.yaml"
    if not properties_path.exists():
        problems.append("properties.yaml is missing")
    else:
        shas["properties.yaml"] = sha256_file(properties_path)
        try:
            registry = PropertyRegistry.model_validate(_load_yaml(properties_path))
        except ValidationError as exc:
            problems.extend(_describe(exc, properties_path))

    problems.extend(_cross_validate(schemas, outputs, registry))

    if problems or registry is None:
        raise ConfigError(problems or ["properties.yaml could not be loaded"])
    return ConfigBundle(schemas=schemas, outputs=outputs, properties=registry, sha256=shas)


def _cross_validate(
    schemas: dict[str, SourceSchema],
    outputs: dict[str, OutputDefinition],
    registry: PropertyRegistry | None,
) -> list[str]:
    """Rules that span files: declared schemas exist, addresses name real sections, every
    manager has the schema and output definition it claims."""
    problems: list[str] = []

    for output in outputs.values():
        for alias, source in output.sources.items():
            if source.schema_id not in schemas:
                problems.append(
                    f"{output.output_id}: source {alias!r} names unknown schema "
                    f"{source.schema_id!r}"
                )
        problems.extend(_check_addresses(output, schemas))

    if registry is not None:
        for pm in registry.property_managers:
            if pm.schema_id not in schemas:
                problems.append(f"properties.yaml: {pm.id} names unknown schema {pm.schema_id!r}")
            if pm.output_definition not in outputs:
                problems.append(
                    f"properties.yaml: {pm.id} names unknown output definition "
                    f"{pm.output_definition!r}"
                )
            declared = outputs.get(pm.output_definition)
            if declared is not None and declared.property_manager != pm.id:
                problems.append(
                    f"{pm.output_definition}: property_manager is "
                    f"{declared.property_manager!r} but properties.yaml assigns it to {pm.id!r}"
                )
        for prop in registry.properties:
            record_ids = {r.id for r in prop.records}
            prop_output = outputs.get(registry.manager_for(prop.id).output_definition)
            if prop_output is None:
                continue
            for leaf in prop_output.leaves:
                try:
                    parsed = parse_address(leaf.address)
                except AddressError:
                    continue  # already reported by the model validator
                templated = parsed.is_record_templated
                if parsed.record and not templated and parsed.record not in record_ids:
                    problems.append(
                        f"{prop_output.output_id}: {leaf.address!r} names record "
                        f"{parsed.record!r}, which {prop.id!r} does not have"
                    )
    return problems


def _check_addresses(output: OutputDefinition, schemas: dict[str, SourceSchema]) -> list[str]:
    problems: list[str] = []
    entries = [(leaf.address, "flow") for leaf in output.leaves]
    entries += [(address, "drop") for address in output.drop]
    for address, where in entries:
        try:
            parsed = parse_address(address)
        except AddressError as exc:
            problems.append(f"{output.output_id}: {where}: {exc}")
            continue
        source = output.sources.get(parsed.source_alias)
        if source is None:
            problems.append(
                f"{output.output_id}: {where}: {address!r} names undeclared source alias "
                f"{parsed.source_alias!r}"
            )
            continue
        schema = schemas.get(source.schema_id)
        if schema is None:
            continue  # unknown schema already reported
        if not parsed.is_wildcard and parsed.section_ref not in schema.section_ids:
            problems.append(
                f"{output.output_id}: {where}: {address!r} names section "
                f"{parsed.section_ref!r}, which schema {schema.schema_id!r} does not declare"
            )
    return problems
