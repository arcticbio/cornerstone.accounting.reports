"""Config loading and validation (SPEC §4)."""

from crr.config.loader import Component, ConfigBundle, ConfigError, load_config
from crr.config.models import (
    SEMANTIC_TAGS,
    FlowGroup,
    FlowLeaf,
    OutputDefinition,
    SectionDef,
    SourceAlias,
    SourceSchema,
    Transforms,
)
from crr.config.properties import PropertyEntry, PropertyManager, PropertyRegistry, Requirement

__all__ = [
    "SEMANTIC_TAGS",
    "Component",
    "ConfigBundle",
    "ConfigError",
    "FlowGroup",
    "FlowLeaf",
    "OutputDefinition",
    "PropertyEntry",
    "PropertyManager",
    "PropertyRegistry",
    "Requirement",
    "SectionDef",
    "SourceAlias",
    "SourceSchema",
    "Transforms",
    "load_config",
]
