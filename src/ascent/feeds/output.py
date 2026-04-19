"""Pandera DataFrameModel schemas for standardized feed outputs.

Feeds emit **wide** frames: one row per entity (instrument or composite) and
one column per attribute. Column names must match ``Attribute.name`` rows in
the database — the persister does the ``name -> attribute_id`` lookup at
write time and raises on unknown names.

Feeds do **not** emit a ``timestamp`` column. The engine stamps every row
with the current partition's timestamp when it unpivots the wide frame into
the EAV hypertable. Strategies consume the latest snapshot from Redis — no
time column exists there either.

Table mapping (via ``Config.name``):

==============================  =====================================
Schema                          DB Table
==============================  =====================================
InstrumentAttributes            instrument_attribute
InstrumentPeriodAttributes      instrument_period_attribute
CompositeAttributes             composite_attribute
CompositePeriodAttributes       composite_period_attribute
==============================  =====================================
"""

import pandera.pandas as pa
from pandera.typing.pandas import Series


class FeedOutput(pa.DataFrameModel):
    """Base schema for all feed outputs.

    Subclasses set ``Config.name`` to the target EAV table. They are
    deliberately non-strict: the attribute columns vary per-feed and are
    resolved by name at persist time.
    """

    class Config:
        strict = False


# ---------------------------------------------------------------------------
# Instrument-level (per instrument)
# ---------------------------------------------------------------------------


class InstrumentAttributes(FeedOutput):
    """Wide schema for instrument-scoped feeds.

    Required column: ``instrument_id`` (UUID string). Every other column is
    an attribute whose name matches an ``Attribute.name`` row in the DB and
    whose values are floats.
    """

    instrument_id: Series[str] = pa.Field()

    class Config:
        strict = False
        name = "instrument_attribute"


class InstrumentPeriodAttributes(FeedOutput):
    """Wide schema for instrument-period-scoped feeds.

    Required columns: ``instrument_id`` and ``period_id`` (both UUID strings).
    """

    instrument_id: Series[str] = pa.Field()
    period_id: Series[str] = pa.Field()

    class Config:
        strict = False
        name = "instrument_period_attribute"


# ---------------------------------------------------------------------------
# Composite-level (per composite)
# ---------------------------------------------------------------------------


class CompositeAttributes(FeedOutput):
    """Wide schema for composite-scoped feeds.

    Required column: ``composite_id`` (UUID string). Every other column is
    an attribute whose name matches an ``Attribute.name`` row in the DB and
    whose values are floats.
    """

    composite_id: Series[str] = pa.Field()

    class Config:
        strict = False
        name = "composite_attribute"


class CompositePeriodAttributes(FeedOutput):
    """Wide schema for composite-period-scoped feeds."""

    composite_id: Series[str] = pa.Field()
    period_id: Series[str] = pa.Field()

    class Config:
        strict = False
        name = "composite_period_attribute"
