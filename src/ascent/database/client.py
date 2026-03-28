import datetime as dt
import uuid

import pandas as pd
from sqlalchemy import Engine, select

from ascent.database.models import Attribute, ProviderAssetGroupAttribute


class AscentClient:
    def __init__(self, engine: Engine):
        self.engine = engine

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def get_group_attribute(
        self,
        provider_asset_group_id: uuid.UUID,
        start_timestamp: dt.datetime,
        end_timestamp: dt.datetime,
        attributes: list[str],
    ) -> pd.DataFrame:
        # Read the data from the database.
        unpivotted_df: pd.DataFrame = pd.read_sql(
            select(
                ProviderAssetGroupAttribute.timestamp,
                ProviderAssetGroupAttribute.provider_asset_group_id,
                Attribute.name.label("attribute_name"),
                ProviderAssetGroupAttribute.attribute_value.label("attribute_value"),
            )
            .select_from(ProviderAssetGroupAttribute)
            .join(Attribute, ProviderAssetGroupAttribute.attribute_id == Attribute.id)
            .where(ProviderAssetGroupAttribute.provider_asset_group_id == provider_asset_group_id)
            .where(Attribute.name.in_(attributes))
            .where(ProviderAssetGroupAttribute.timestamp >= start_timestamp)
            .where(ProviderAssetGroupAttribute.timestamp <= end_timestamp),
            self.engine,
        )

        # Pivot the data and flatten the columns.
        df = unpivotted_df.pivot(
            index=["timestamp", "provider_asset_group_id"],
            columns="attribute_name",
            values="attribute_value",
        )
        return df.reset_index()
