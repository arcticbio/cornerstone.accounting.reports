"""Config loading and validation (SPEC §4)."""

from crr.config.loader import ConfigBundle, ConfigError, load_config
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
from crr.config.properties import PropertyEntry, PropertyManager, PropertyRegistry

__all__ = [
    "SEMANTIC_TAGS",
    "ConfigBundle",
    "ConfigError",
    "FlowGroup",
    "FlowLeaf",
    "OutputDefinition",
    "PropertyEntry",
    "PropertyManager",
    "PropertyRegistry",
    "SectionDef",
    "SourceAlias",
    "SourceSchema",
    "Transforms",
    "load_config",
]
