"""Ornstein-Uhlenbeck parameter feed — triggered by market data."""

import pandas as pd
from pandera.typing.pandas import DataFrame
from pydantic import Field

from ascent.feeds import feed
from ascent.feeds.examples.market import market_data
from ascent.feeds.output import GroupAttributes


@feed(
    depends_on=[market_data],
    display_name="OU Parameters",
    description="Computes Ornstein-Uhlenbeck parameters from market data.",
)
def ou_params(
    lookback_days: int = Field(default=60, ge=7, le=365),
) -> DataFrame[GroupAttributes]:
    from ascent.engine import get_feed, get_logger

    logger = get_logger()
    prices = get_feed(market_data)
    logger.info("Computing OU params from %d rows", len(prices))

    # Placeholder — real implementation would compute OU parameters
    return pd.DataFrame(
        columns=[
            "timestamp",
            "provider_asset_group_id",
            "attribute_id",
            "attribute_value",
        ]
    )
