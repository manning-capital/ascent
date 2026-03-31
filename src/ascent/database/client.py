import datetime as dt
import uuid

import pandas as pd
from sqlalchemy import Engine, select

from ascent.database.models import Attribute
from ascent.database.models.instruments import InstrumentAttribute


class AscentClient:
    def __init__(self, engine: Engine):
        self.engine = engine

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def get_instrument_attribute(
        self,
        instrument_id: uuid.UUID,
        start_timestamp: dt.datetime,
        end_timestamp: dt.datetime,
        attributes: list[str],
    ) -> pd.DataFrame:
        # Read the data from the database.
        unpivotted_df: pd.DataFrame = pd.read_sql(
            select(
                InstrumentAttribute.timestamp,
                InstrumentAttribute.instrument_id,
                Attribute.name.label("attribute_name"),
                InstrumentAttribute.attribute_value.label("attribute_value"),
            )
            .select_from(InstrumentAttribute)
            .join(Attribute, InstrumentAttribute.attribute_id == Attribute.id)
            .where(InstrumentAttribute.instrument_id == instrument_id)
            .where(Attribute.name.in_(attributes))
            .where(InstrumentAttribute.timestamp >= start_timestamp)
            .where(InstrumentAttribute.timestamp <= end_timestamp),
            self.engine,
        )

        # Pivot the data and flatten the columns.
        df = unpivotted_df.pivot(
            index=["timestamp", "instrument_id"],
            columns="attribute_name",
            values="attribute_value",
        )
        return df.reset_index()
