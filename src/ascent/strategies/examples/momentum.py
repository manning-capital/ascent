"""Momentum strategy — trend-following via moving average crossovers."""

from typing import Literal

from pydantic import Field

from ascent.feeds.examples.market import market_data
from ascent.strategies import strategy


@strategy(
    feeds=[market_data],
    display_name="Momentum",
    description="Enters when fast MA crosses above slow MA, exits on reverse cross.",
)
def momentum_strategy(
    fast_period: int = Field(12, ge=2, le=100, description="Fast moving average period"),
    slow_period: int = Field(26, ge=5, le=500, description="Slow moving average period"),
    ma_type: Literal["sma", "ema", "wma"] = "ema",
    timeframe: Literal["1m", "5m", "15m", "1h", "4h", "1d"] = "4h",
    risk_per_trade: float = Field(
        0.02, ge=0.001, le=0.1, description="Fraction of portfolio to risk"
    ),
    use_trailing_stop: bool = False,
    trailing_stop_pct: float = Field(
        0.03, ge=0.005, le=0.2, description="Trailing stop percentage"
    ),
) -> None:
    from ascent.engine import get_context, get_logger

    ctx = get_context()
    logger = get_logger()

    prices = ctx.get(market_data)

    # Compute moving averages across all groups
    grouped = prices.groupby("group_id")["close"]
    fast_ma = grouped.apply(lambda x: x.rolling(fast_period).mean().iloc[-1])
    slow_ma = grouped.apply(lambda x: x.rolling(slow_period).mean().iloc[-1])

    # Batch signal generation
    waiting = ctx.groups[ctx.groups["state"] == "waiting"].index
    in_trade = ctx.groups[ctx.groups["state"] == "in_trade"].index

    entries = waiting[fast_ma.loc[waiting] > slow_ma.loc[waiting]]
    exits = in_trade[fast_ma.loc[in_trade] < slow_ma.loc[in_trade]]

    logger.info("Entries: %d, Exits: %d", len(entries), len(exits))
