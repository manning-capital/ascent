"""Pairs trading strategy — stat arb via z-score signals."""

from typing import Literal

from pydantic import Field

from ascent.feeds.examples.market import market_data
from ascent.feeds.examples.ou_params import ou_params
from ascent.strategies import strategy


@strategy(
    feeds=[market_data, ou_params],
    display_name="Pairs Trading",
    description="Trades the spread between two correlated assets using z-score signals.",
)
def pairs_strategy(
    lookback: int = Field(60, ge=10, le=500, description="Rolling window size in bars"),
    entry_z: float = Field(2.0, ge=0.5, le=5.0, description="Z-score threshold to enter"),
    exit_z: float = Field(0.5, ge=0.0, le=3.0, description="Z-score threshold to exit"),
    hedge_ratio_method: Literal["ols", "tls", "kalman"] = "ols",
    max_position_size: float = Field(1.0, gt=0, description="Maximum position size"),
) -> None:
    from ascent.engine import get_context, get_logger

    ctx = get_context()
    logger = get_logger()

    # Feed data as DataFrames — vectorized across ALL instruments
    prices = ctx.get(market_data)
    ctx.get(ou_params)

    # Vectorized z-score computation across all instruments at once
    z_scores = prices.groupby("instrument_id")["close"].apply(
        lambda x: (x.iloc[-1] - x.rolling(lookback).mean().iloc[-1])
        / x.rolling(lookback).std().iloc[-1]
    )

    # Batch signal generation using instrument states
    waiting = ctx.instruments[ctx.instruments["state"] == "waiting"].index
    in_trade = ctx.instruments[ctx.instruments["state"] == "in_trade"].index

    entries = waiting[z_scores.loc[waiting].abs() > entry_z]
    exits = in_trade[z_scores.loc[in_trade].abs() < exit_z]

    logger.info("Entries: %d, Exits: %d", len(entries), len(exits))
