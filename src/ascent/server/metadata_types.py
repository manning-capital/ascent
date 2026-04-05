"""Polymorphic Pydantic models for metadata type configuration.

Each metadata value_type has a corresponding config subclass that encapsulates
type-specific behaviour: validation, parsing, and configuration.  The config
is stored as JSONB on the ``Metadata`` row and deserialized via the
:func:`for_value_type` factory.
"""

from __future__ import annotations

import datetime
from typing import Any, Literal

from pydantic import BaseModel

ALLOWED_REF_TABLES = frozenset({"asset", "instrument", "composite", "provider"})


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class MetadataTypeConfig(BaseModel):
    """Base config — every subclass carries a ``type`` discriminator."""

    type: str

    def validate_value(self, value: Any) -> Any:
        """Validate *value* is acceptable for this type.  Returns the
        (possibly coerced) value, or raises ``ValueError``."""
        return value

    def parse_value(self, raw: Any) -> Any:
        """Coerce a raw value (often a string from the UI) into the
        canonical Python type for storage."""
        return raw

    @staticmethod
    def for_value_type(
        value_type: str,
        config: dict | None = None,
    ) -> MetadataTypeConfig:
        """Factory — build the correct subclass from *value_type* and an
        optional *config* dict (from the JSONB column)."""
        cls = _REGISTRY.get(value_type)
        if cls is None:
            raise ValueError(f"Unknown metadata value_type: {value_type!r}")
        if config:
            return cls.model_validate(config)
        return cls(type=value_type)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Concrete types
# ---------------------------------------------------------------------------


class StringConfig(MetadataTypeConfig):
    type: Literal["string"] = "string"

    def validate_value(self, value: Any) -> Any:
        if value is not None and not isinstance(value, str):
            raise ValueError(f"Expected string, got {type(value).__name__}")
        return value

    def parse_value(self, raw: Any) -> Any:
        return str(raw) if raw is not None else None


class IntegerConfig(MetadataTypeConfig):
    type: Literal["integer"] = "integer"

    def validate_value(self, value: Any) -> Any:
        if value is not None and not isinstance(value, int):
            raise ValueError(f"Expected integer, got {type(value).__name__}")
        return value

    def parse_value(self, raw: Any) -> Any:
        if raw is None or raw == "":
            return None
        return int(raw)


class FloatConfig(MetadataTypeConfig):
    type: Literal["float"] = "float"

    def validate_value(self, value: Any) -> Any:
        if value is not None and not isinstance(value, (int, float)):
            raise ValueError(f"Expected float, got {type(value).__name__}")
        return value

    def parse_value(self, raw: Any) -> Any:
        if raw is None or raw == "":
            return None
        return float(raw)


class BooleanConfig(MetadataTypeConfig):
    type: Literal["boolean"] = "boolean"

    def validate_value(self, value: Any) -> Any:
        if value is not None and not isinstance(value, bool):
            raise ValueError(f"Expected boolean, got {type(value).__name__}")
        return value

    def parse_value(self, raw: Any) -> Any:
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            return raw.lower() == "true"
        return bool(raw) if raw is not None else None


class DateConfig(MetadataTypeConfig):
    type: Literal["date"] = "date"

    def validate_value(self, value: Any) -> Any:
        if value is not None and not isinstance(value, (str, datetime.date)):
            raise ValueError(f"Expected date string, got {type(value).__name__}")
        return value

    def parse_value(self, raw: Any) -> Any:
        if isinstance(raw, datetime.date):
            return raw.isoformat()
        return str(raw) if raw is not None else None


class TimeConfig(MetadataTypeConfig):
    type: Literal["time"] = "time"

    def validate_value(self, value: Any) -> Any:
        if value is not None and not isinstance(value, (str, datetime.time)):
            raise ValueError(f"Expected time string, got {type(value).__name__}")
        return value

    def parse_value(self, raw: Any) -> Any:
        if isinstance(raw, datetime.time):
            return raw.isoformat()
        return str(raw) if raw is not None else None


class DatetimeConfig(MetadataTypeConfig):
    type: Literal["datetime"] = "datetime"

    def validate_value(self, value: Any) -> Any:
        if value is not None and not isinstance(value, (str, datetime.datetime)):
            raise ValueError(f"Expected datetime string, got {type(value).__name__}")
        return value

    def parse_value(self, raw: Any) -> Any:
        if isinstance(raw, datetime.datetime):
            return raw.isoformat()
        return str(raw) if raw is not None else None


class EnumConfig(MetadataTypeConfig):
    """Constrained set of allowed string values."""

    type: Literal["enum"] = "enum"
    options: list[str]

    def validate_value(self, value: Any) -> Any:
        if value is not None and value not in self.options:
            raise ValueError(f"Value {value!r} not in allowed options: {self.options}")
        return value

    def parse_value(self, raw: Any) -> Any:
        return str(raw) if raw is not None else None


class ReferenceConfig(MetadataTypeConfig):
    """Value is a UUID referencing a row in another entity table."""

    type: Literal["reference"] = "reference"
    ref_table: str  # one of ALLOWED_REF_TABLES

    def validate_value(self, value: Any) -> Any:
        if value is not None and not isinstance(value, str):
            raise ValueError(f"Expected UUID string, got {type(value).__name__}")
        return value

    def parse_value(self, raw: Any) -> Any:
        return str(raw) if raw is not None else None


# ---------------------------------------------------------------------------
# Registry — maps value_type string → config class
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type[MetadataTypeConfig]] = {
    "string": StringConfig,
    "integer": IntegerConfig,
    "float": FloatConfig,
    "boolean": BooleanConfig,
    "date": DateConfig,
    "time": TimeConfig,
    "datetime": DatetimeConfig,
    "enum": EnumConfig,
    "reference": ReferenceConfig,
}
