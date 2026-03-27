"""Market data feed — minutely OHLCV pricing data."""

from datetime import datetime

import pandas as pd
from pandera.typing.pandas import DataFrame
from pydantic import Field

from ascent.feeds import Schedule, feed
from ascent.feeds.output import AssetAttributes


@feed(
    schedule=Schedule(interval=60, offset=-1.0, start_date=datetime(2024, 1, 1)),
    display_name="Market Data",
    description="Pulls minutely OHLCV pricing data 1s before each minute close.",
)
def market_data(
    provider_name: str = "kraken",
    attributes: list[str] = Field(default=["close"]),
    lookback_minutes: int = Field(default=5, ge=1, le=1440),
) -> DataFrame[AssetAttributes]:
    from ascent.engine import get_logger

    logger = get_logger()
    logger.info("Fetching %d minutes from %s", lookback_minutes, provider_name)

    # Placeholder — real implementation would call provider API
    return pd.DataFrame(
        columns=[
            "timestamp",
            "provider_id",
            "from_asset_id",
            "to_asset_id",
            "attribute_id",
            "attribute_value",
        ]
    )
