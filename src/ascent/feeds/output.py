"""Pandera DataFrameModel schemas for standardized feed outputs.

Each schema maps directly to an existing EAV attribute table in the database.
Feeds return ``DataFrame[Schema]`` — Pandera validates columns and types at
runtime. The ``Config.name`` attribute links the schema to the DB table for
auto-persist and auto-cold-start.

Table mapping:

=========================  =====================================
Schema                     DB Table
=========================  =====================================
GroupAttributes            provider_asset_group_attribute
GroupPeriodAttributes      provider_asset_group_period_attribute
=========================  =====================================
"""

import pandera.pandas as pa
from pandera.typing.pandas import Series


class FeedOutput(pa.DataFrameModel):
    """Base schema for all feed outputs. Subclasses set ``Config.name``."""

    class Config:
        strict = True


# ---------------------------------------------------------------------------
# Group-level (per provider asset group)
# ---------------------------------------------------------------------------


class GroupAttributes(FeedOutput):
    """Maps to ``ProviderAssetGroupAttribute`` table."""

    timestamp: Series[pa.DateTime] = pa.Field()
    provider_asset_group_id: Series[int] = pa.Field(ge=1)
    attribute_id: Series[int] = pa.Field(ge=1)
    attribute_value: Series[float] = pa.Field()

    class Config:
        strict = True
        name = "provider_asset_group_attribute"


class GroupPeriodAttributes(FeedOutput):
    """Maps to ``ProviderAssetGroupPeriodAttribute`` table."""

    timestamp: Series[pa.DateTime] = pa.Field()
    provider_asset_group_id: Series[int] = pa.Field(ge=1)
    period_id: Series[int] = pa.Field(ge=1)
    attribute_id: Series[int] = pa.Field(ge=1)
    attribute_value: Series[float] = pa.Field()

    class Config:
        strict = True
        name = "provider_asset_group_period_attribute"
