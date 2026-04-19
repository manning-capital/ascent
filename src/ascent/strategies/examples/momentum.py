"""Momentum strategy — trend-following via moving average crossovers."""

from typing import Literal

from pydantic import BaseModel, Field

from ascent.feeds.examples.market import MarketData
from ascent.strategies import Context, Strategy


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

    def evaluate(self, ctx: Context) -> None:
        logger = self.get_logger()

        if ctx.df.empty:
            return

        df = ctx.df
        waiting = df[df[("trade", "status")] == "WAITING"]
        in_trade = df[df[("trade", "status")] == "OPEN"]

        logger.info("Waiting: %d, In trade: %d", len(waiting), len(in_trade))


if __name__ == "__main__":
    MomentumStrategy.run()
