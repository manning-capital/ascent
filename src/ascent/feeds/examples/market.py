"""Market data feed — OU-driven simulated OHLCV per instrument.

For each configured pair ``(A, B)``, the log-spread ``s_t = ln(P_A) - ln(P_B)``
follows an Ornstein-Uhlenbeck process:

    ds_t = theta * (mu - s_t) * dt + sigma * dW_t

``A`` is advanced as geometric Brownian motion and ``B`` is derived from the
spread so the pair is cointegrated by construction. That gives a strategy
something real to trade against: the spread mean-reverts, so divergence is a
signal.
"""

import math
import os
import random
import uuid
from datetime import datetime
from typing import ClassVar

import pandas as pd
from pandera.typing.pandas import DataFrame
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ascent.feeds import Feed, Schedule
from ascent.feeds.output import InstrumentAttributes

# Anchor prices used as the starting point for the "A" leg of each pair.
BASE_PRICES: dict[str, float] = {
    "BTC": 67500.0,
    "ETH": 3400.0,
    "SOL": 145.0,
    "ADA": 0.45,
    "XRP": 0.52,
}

# Pairs traded by the OU simulator. ``mu`` is the long-run log-spread
# (ln(P_A/P_B)) — computed from BASE_PRICES so each pair starts at its
# equilibrium. ``theta`` controls mean-reversion speed, ``sigma`` the shock.
PAIRS: list[tuple[str, str, float, float]] = [
    ("BTC", "ETH", 0.15, 0.015),
    ("SOL", "ADA", 0.20, 0.020),
    ("XRP", "ADA", 0.25, 0.025),
]


class _PairState:
    __slots__ = ("spread", "anchor_price", "mu")

    def __init__(self, anchor_price: float, mu: float) -> None:
        self.spread = mu
        self.anchor_price = anchor_price
        self.mu = mu


class MarketData(Feed):
    """Emits OHLCV market data driven by pairwise Ornstein-Uhlenbeck spreads."""

    class Parameters(BaseModel):
        anchor_volatility: float = Field(
            0.003, description="Per-tick volatility of the anchor (A) leg"
        )
        dt: float = Field(1.0, description="OU time-step per tick")

    schedule = Schedule(interval=5, start_date=datetime(2024, 1, 1))
    output = InstrumentAttributes
    provider = "KRAKEN"
    instrument_type = "SECURITY"
    display_name = "Market Data"
    description = "Simulated OU-driven OHLCV market data per instrument."

    _instruments: ClassVar[dict[uuid.UUID, str]] = {}
    _pair_states: ClassVar[dict[tuple[str, str], _PairState]] = {}
    _pair_params: ClassVar[dict[tuple[str, str], tuple[float, float]]] = {}
    _initialised: ClassVar[bool] = False

    def _ensure_initialised(self) -> None:
        if MarketData._initialised:
            return
        from ascent.database.models.assets import Asset
        from ascent.database.models.instruments import Instrument

        engine = create_engine(os.environ["ASCENT_DATABASE_URL"])
        with Session(engine) as db:
            rows = db.execute(
                select(Instrument.id, Asset.name).join(
                    Asset, Instrument.from_asset_id == Asset.id
                )
            ).all()
        MarketData._instruments = {
            inst_id: asset_name for inst_id, asset_name in rows if asset_name in BASE_PRICES
        }

        symbol_to_inst = {sym: iid for iid, sym in MarketData._instruments.items()}
        for sym_a, sym_b, theta, sigma in PAIRS:
            if sym_a not in symbol_to_inst or sym_b not in symbol_to_inst:
                continue
            mu = math.log(BASE_PRICES[sym_a] / BASE_PRICES[sym_b])
            MarketData._pair_states[(sym_a, sym_b)] = _PairState(
                anchor_price=BASE_PRICES[sym_a], mu=mu
            )
            MarketData._pair_params[(sym_a, sym_b)] = (theta, sigma)

        MarketData._initialised = True

    def fetch(self) -> DataFrame[InstrumentAttributes]:
        logger = self.get_logger()
        self._ensure_initialised()

        dt = self.parameters.dt
        sqrt_dt = math.sqrt(dt)
        anchor_vol = self.parameters.anchor_volatility
        universe_ids = set(self.get_universe())

        latest_prices: dict[str, float] = {}
        for (sym_a, sym_b), state in MarketData._pair_states.items():
            theta, sigma = MarketData._pair_params[(sym_a, sym_b)]
            state.spread += (
                theta * (state.mu - state.spread) * dt + sigma * sqrt_dt * random.gauss(0, 1)
            )
            state.anchor_price *= math.exp(anchor_vol * sqrt_dt * random.gauss(0, 1))
            latest_prices[sym_a] = state.anchor_price
            latest_prices[sym_b] = state.anchor_price / math.exp(state.spread)

        rows: list[dict] = []
        for inst_id, symbol in MarketData._instruments.items():
            if inst_id not in universe_ids:
                continue
            price = latest_prices.get(symbol)
            if price is None:
                continue
            rows.append(
                {
                    "instrument_id": str(inst_id),
                    "CLOSE": round(price, 6),
                    "VOLUME": round(random.uniform(100, 10000), 2),
                }
            )

        logger.info("Generated market data for %d instruments", len(rows))
        return pd.DataFrame(rows, columns=["instrument_id", "CLOSE", "VOLUME"])


if __name__ == "__main__":
    MarketData.run()
