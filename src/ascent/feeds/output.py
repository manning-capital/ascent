"""Pandera DataFrameModel schemas for standardized feed outputs.

Each schema maps directly to an existing EAV attribute table in the database.
Feeds return ``DataFrame[Schema]`` — Pandera validates columns and types at
runtime. The ``Config.name`` attribute links the schema to the DB table for
auto-persist and auto-cold-start.

Table mapping:

==============================  =====================================
Schema                          DB Table
==============================  =====================================
InstrumentAttributes            instrument_attribute
InstrumentPeriodAttributes      instrument_period_attribute
==============================  =====================================
"""

import pandera.pandas as pa
from pandera.typing.pandas import Series


class FeedOutput(pa.DataFrameModel):
    """Base schema for all feed outputs. Subclasses set ``Config.name``."""

    class Config:
        strict = True


# ---------------------------------------------------------------------------
# Instrument-level (per instrument)
# ---------------------------------------------------------------------------


class InstrumentAttributes(FeedOutput):
    """Maps to ``InstrumentAttribute`` table."""

    timestamp: Series[pa.DateTime] = pa.Field()
    instrument_id: Series[int] = pa.Field(ge=1)
    attribute_id: Series[int] = pa.Field(ge=1)
    attribute_value: Series[float] = pa.Field()

    class Config:
        strict = True
        name = "instrument_attribute"


class InstrumentPeriodAttributes(FeedOutput):
    """Maps to ``InstrumentPeriodAttribute`` table."""

    timestamp: Series[pa.DateTime] = pa.Field()
    instrument_id: Series[int] = pa.Field(ge=1)
    period_id: Series[int] = pa.Field(ge=1)
    attribute_id: Series[int] = pa.Field(ge=1)
    attribute_value: Series[float] = pa.Field()

    class Config:
        strict = True
        name = "instrument_period_attribute"


# ---------------------------------------------------------------------------
# Composite-level (per composite)
# ---------------------------------------------------------------------------


class CompositeAttributes(FeedOutput):
    """Maps to ``CompositeAttribute`` table."""

    timestamp: Series[pa.DateTime] = pa.Field()
    composite_id: Series[int] = pa.Field(ge=1)
    attribute_id: Series[int] = pa.Field(ge=1)
    attribute_value: Series[float] = pa.Field()

    class Config:
        strict = True
        name = "composite_attribute"


class CompositePeriodAttributes(FeedOutput):
    """Maps to ``CompositePeriodAttribute`` table."""

    timestamp: Series[pa.DateTime] = pa.Field()
    composite_id: Series[int] = pa.Field(ge=1)
    period_id: Series[int] = pa.Field(ge=1)
    attribute_id: Series[int] = pa.Field(ge=1)
    attribute_value: Series[float] = pa.Field()

    class Config:
        strict = True
        name = "composite_period_attribute"
