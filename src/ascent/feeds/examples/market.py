"""Market data feed — minutely OHLCV pricing data."""

from datetime import datetime

import pandas as pd
from pandera.typing.pandas import DataFrame
from pydantic import BaseModel, Field

from ascent.feeds import Feed, Schedule
from ascent.feeds.output import InstrumentAttributes


class MarketData(Feed):
    """Pulls minutely OHLCV pricing data 1s before each minute close."""

    class Parameters(BaseModel):
        provider_name: str = "kraken"
        attributes: list[str] = Field(default=["close"])
        lookback_minutes: int = Field(default=5, ge=1, le=1440)

    schedule = Schedule(interval=60, offset=-1.0, start_date=datetime(2024, 1, 1))
    output = InstrumentAttributes
    display_name = "Market Data"
    description = "Pulls minutely OHLCV pricing data 1s before each minute close."

    def fetch(self) -> DataFrame[InstrumentAttributes]:
        logger = self.get_logger()
        logger.info(
            "Fetching %d minutes from %s",
            self.parameters.lookback_minutes,
            self.parameters.provider_name,
        )

        # Placeholder — real implementation would call provider API
        return pd.DataFrame(
            columns=[
                "timestamp",
                "instrument_id",
                "attribute_id",
                "attribute_value",
            ]
        )


if __name__ == "__main__":
    MarketData.run()
