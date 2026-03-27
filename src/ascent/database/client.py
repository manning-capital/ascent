import datetime as dt

import pandas as pd
from sqlalchemy import Engine, select

from ascent.database.models import Attribute, ProviderAssetAttribute


class AscentClient:
    def __init__(self, engine: Engine):
        self.engine = engine

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def get_provider_asset_attribute(
        self, start_timestamp: dt.datetime, end_timestamp: dt.datetime, attributes: list[str]
    ) -> pd.DataFrame:
        # Read the data from the database.
        unpivotted_df: pd.DataFrame = pd.read_sql(
            select(
                ProviderAssetAttribute.timestamp,
                ProviderAssetAttribute.provider_id,
                ProviderAssetAttribute.from_asset_id,
                ProviderAssetAttribute.to_asset_id,
                Attribute.name.label("attribute_name"),
                ProviderAssetAttribute.attribute_value.label("attribute_value"),
            )
            .select_from(ProviderAssetAttribute)
            .join(Attribute, ProviderAssetAttribute.attribute_id == Attribute.id)
            .where(Attribute.name.in_(attributes))
            .where(ProviderAssetAttribute.timestamp >= start_timestamp)
            .where(ProviderAssetAttribute.timestamp <= end_timestamp),
            self.engine,
        )

        # Pivot the data and flatten the columns.
        df = unpivotted_df.pivot(
            index=["timestamp", "provider_id", "from_asset_id", "to_asset_id"],
            columns="attribute_name",
            values="attribute_value",
        )
        return df.reset_index()
