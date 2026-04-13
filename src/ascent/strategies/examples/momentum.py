"""Momentum strategy — trend-following via moving average crossovers."""

from typing import Literal

from pydantic import BaseModel, Field

from ascent.feeds.examples.market import MarketData
from ascent.strategies import Strategy


class MomentumStrategy(Strategy):
    """Enters when fast MA crosses above slow MA, exits on reverse cross."""

    class Parameters(BaseModel):
        fast_period: int = Field(12, ge=2, le=100, description="Fast moving average period")
        slow_period: int = Field(26, ge=5, le=500, description="Slow moving average period")
        ma_type: Literal["sma", "ema", "wma"] = "ema"
        timeframe: Literal["1m", "5m", "15m", "1h", "4h", "1d"] = "4h"
        risk_per_trade: float = Field(
            0.02, ge=0.001, le=0.1, description="Fraction of portfolio to risk"
        )
        use_trailing_stop: bool = False
        trailing_stop_pct: float = Field(
            0.03, ge=0.005, le=0.2, description="Trailing stop percentage"
        )

    feeds = [MarketData]
    display_name = "Momentum"
    description = "Enters when fast MA crosses above slow MA, exits on reverse cross."

    def evaluate(self) -> None:
        ctx = self.get_context()
        logger = self.get_logger()

        prices = ctx.get(MarketData)

        # Compute moving averages across all instruments
        grouped = prices.groupby("instrument_id")["close"]
        fast_ma = grouped.apply(lambda x: x.rolling(self.parameters.fast_period).mean().iloc[-1])
        slow_ma = grouped.apply(lambda x: x.rolling(self.parameters.slow_period).mean().iloc[-1])

        # Batch signal generation
        waiting = ctx.instruments[ctx.instruments["state"] == "waiting"].index
        in_trade = ctx.instruments[ctx.instruments["state"] == "in_trade"].index

        entries = waiting[fast_ma.loc[waiting] > slow_ma.loc[waiting]]
        exits = in_trade[fast_ma.loc[in_trade] < slow_ma.loc[in_trade]]

        logger.info("Entries: %d, Exits: %d", len(entries), len(exits))


if __name__ == "__main__":
    MomentumStrategy.run()
