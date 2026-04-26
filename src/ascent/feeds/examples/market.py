"""Market data feed — per-instrument OHLCV driven by composite-level OU params.

Triggered by :class:`OUParams`. On each tick this feed reads the latest
``(mu, theta, sigma, beta)`` per composite, evolves a per-composite log-spread
``s = ln(p_a) - beta * ln(p_b)`` one OU step, and splits back into the two
constituent legs.
"""

import hashlib
import math
import os
import random
import uuid
from typing import ClassVar

import pandas as pd
from pandera.typing.pandas import DataFrame
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ascent.feeds import Feed
from ascent.feeds.examples.ou_params import OUParams
from ascent.feeds.output import InstrumentAttributes

BASE_PRICES: dict[str, float] = {
    "BTC": 67500.0,
    "ETH": 3400.0,
    "SOL": 145.0,
    "ADA": 0.45,
    "XRP": 0.52,
}


def _base_price_for(symbol: str) -> float:
    """Return a deterministic starting price for an asset symbol.

    Known symbols come from ``BASE_PRICES``; anything else is hashed into a
    stable synthetic price in roughly ``[0.1, 1000]`` so the sim can run
    against the full seeded universe without needing a hand-curated price
    for every asset class.
    """
    if symbol in BASE_PRICES:
        return BASE_PRICES[symbol]
    digest = hashlib.sha256(symbol.encode()).digest()
    u = int.from_bytes(digest[:8], "big") / 2**64
    return 0.1 * (10.0 ** (4.0 * u))


class _SpreadState:
    __slots__ = ("spread", "anchor_price")

    def __init__(self, spread: float, anchor_price: float) -> None:
        self.spread = spread
        self.anchor_price = anchor_price


class MarketData(Feed):
    """Emits OHLCV market data driven by composite-level OU parameters."""

    class Parameters(BaseModel):
        anchor_volatility: float = Field(
            0.003, description="Per-tick volatility of the anchor (A) leg"
        )
        dt: float = Field(1.0, description="OU time-step per tick (seconds)")

    depends_on = [OUParams]
    output = InstrumentAttributes
    provider = "KRAKEN"
    instrument_type = "SPOT_INSTRUMENT"
    display_name = "Market Data"
    description = "Simulated OU-driven OHLCV market data per instrument."

    _composite_legs: ClassVar[dict[uuid.UUID, tuple[uuid.UUID, uuid.UUID, str, str]]] = {}
    _composite_state: ClassVar[dict[uuid.UUID, _SpreadState]] = {}
    _initialised: ClassVar[bool] = False

    def _ensure_initialised(self) -> None:
        if MarketData._initialised:
            return
        from ascent.database.models.assets import Asset
        from ascent.database.models.composites import Composite, CompositeMember
        from ascent.database.models.instruments import Instrument
        from ascent.database.models.types import CompositeType

        engine = create_engine(os.environ["ASCENT_DATABASE_URL"])
        with Session(engine) as db:
            rows = db.execute(
                select(
                    Composite.id,
                    CompositeMember.order,
                    Instrument.id,
                    Asset.name,
                )
                .join(CompositeType, Composite.composite_type_id == CompositeType.id)
                .join(CompositeMember, CompositeMember.composite_id == Composite.id)
                .join(Instrument, CompositeMember.instrument_id == Instrument.id)
                .join(Asset, Instrument.from_asset_id == Asset.id)
                .where(CompositeType.name == "SPREAD")
                .order_by(Composite.id, CompositeMember.order)
            ).all()

        legs_by_composite: dict[uuid.UUID, dict[int, tuple[uuid.UUID, str]]] = {}
        for composite_id, order, instrument_id, asset_name in rows:
            legs_by_composite.setdefault(composite_id, {})[order] = (instrument_id, asset_name)

        for composite_id, legs in legs_by_composite.items():
            if set(legs.keys()) != {1, 2}:
                continue
            inst_a, sym_a = legs[1]
            inst_b, sym_b = legs[2]
            MarketData._composite_legs[composite_id] = (inst_a, inst_b, sym_a, sym_b)

        MarketData._initialised = True

    def fetch(self) -> DataFrame[InstrumentAttributes]:
        logger = self.get_logger()
        self._ensure_initialised()

        params_df = self.get_feed(OUParams)
        if params_df.empty:
            logger.info("OU params frame is empty; nothing to simulate")
            return pd.DataFrame(columns=["instrument_id", "CLOSE", "VOLUME"])

        dt = self.parameters.dt
        sqrt_dt = math.sqrt(dt)
        anchor_vol = self.parameters.anchor_volatility
        universe_ids = set(self.get_universe())

        rows: list[dict] = []
        for _, params_row in params_df.iterrows():
            cid = uuid.UUID(str(params_row["composite_id"]))
            legs = MarketData._composite_legs.get(cid)
            if legs is None:
                continue
            inst_a, inst_b, sym_a, sym_b = legs

            mu = float(params_row["OU_MU"])
            theta = float(params_row["OU_THETA"])
            sigma = float(params_row["OU_SIGMA"])
            beta = float(params_row["OU_BETA"])
            if mu <= 0 or sigma <= 0 or beta == 0:
                continue

            state = MarketData._composite_state.get(cid)
            if state is None:
                # Start at the OU equilibrium so there's no multi-tick
                # transient. Seeding from log(base_a) - beta*log(base_b)
                # puts spread arbitrarily far from theta; the subsequent
                # mu*(theta - spread)*dt step then produces huge Δspread
                # values, which the exp((ln p_a - spread)/beta) transform
                # amplifies into many-x price swings on leg B until the
                # process settles. Starting at theta avoids all of that.
                base_a = _base_price_for(sym_a)
                state = _SpreadState(spread=theta, anchor_price=base_a)
                MarketData._composite_state[cid] = state

            state.spread += mu * (theta - state.spread) * dt + sigma * sqrt_dt * random.gauss(0, 1)
            state.anchor_price *= math.exp(anchor_vol * sqrt_dt * random.gauss(0, 1))

            price_a = state.anchor_price
            price_b = math.exp((math.log(price_a) - state.spread) / beta)

            if inst_a in universe_ids:
                rows.append(
                    {
                        "instrument_id": str(inst_a),
                        "CLOSE": round(price_a, 6),
                        "VOLUME": round(random.uniform(100, 10000), 2),
                    }
                )
            if inst_b in universe_ids:
                rows.append(
                    {
                        "instrument_id": str(inst_b),
                        "CLOSE": round(price_b, 6),
                        "VOLUME": round(random.uniform(100, 10000), 2),
                    }
                )

        logger.info("Generated market data for %d instrument rows", len(rows))
        return pd.DataFrame(rows, columns=["instrument_id", "CLOSE", "VOLUME"])


if __name__ == "__main__":
    MarketData.run()
