"""Composite market data feed — OU-simulated spread values per composite.

For each composite in the active universe, emits a simulated Ornstein-Uhlenbeck
spread value as the ``CLOSE`` attribute. OU parameters (mu, theta, sigma) are
derived deterministically from the composite's UUID so a given pair always
gets the same dynamics across restarts.
"""

import hashlib
import math
import random
import uuid
from datetime import datetime
from typing import ClassVar

import pandas as pd
from pandera.typing.pandas import DataFrame
from pydantic import BaseModel, Field

from ascent.feeds import Feed, Schedule
from ascent.feeds.output import CompositeAttributes


def _params_for(composite_id: uuid.UUID) -> tuple[float, float, float]:
    """Derive deterministic OU parameters ``(mu, theta, sigma)`` from a UUID."""
    digest = hashlib.sha256(composite_id.bytes).digest()

    def _u(i: int) -> float:
        return int.from_bytes(digest[i * 8 : (i + 1) * 8], "big") / 2**64

    mu = 0.05 + 0.20 * _u(0)
    theta = -0.05 + 0.10 * _u(1)
    sigma = 0.01 + 0.04 * _u(2)
    return (mu, theta, sigma)


class CompositeMarketData(Feed):
    """Emits OU-simulated spread values per composite on every tick."""

    class Parameters(BaseModel):
        dt: float = Field(5.0, description="OU time-step per tick (seconds)")

    schedule = Schedule(interval=5, start_date=datetime(2024, 1, 1))
    output = CompositeAttributes
    provider = "KRAKEN"
    composite_type = "SPREAD"
    display_name = "Composite Market Data"
    description = "Simulated OU spread values per composite."

    _state: ClassVar[dict[uuid.UUID, float]] = {}

    def fetch(self) -> DataFrame[CompositeAttributes]:
        logger = self.get_logger()
        universe_ids = self.get_universe()
        dt = self.parameters.dt

        rows: list[dict] = []
        for cid in universe_ids:
            mu, theta, sigma = _params_for(cid)
            x = CompositeMarketData._state.get(cid, theta)
            decay = math.exp(-mu * dt)
            noise_std = sigma * math.sqrt((1 - math.exp(-2 * mu * dt)) / (2 * mu))
            x = x * decay + theta * (1 - decay) + noise_std * random.gauss(0, 1)
            CompositeMarketData._state[cid] = x
            rows.append({"composite_id": str(cid), "CLOSE": round(x, 8)})

        logger.info("Generated OU spreads for %d composites", len(rows))
        return pd.DataFrame(rows, columns=["composite_id", "CLOSE"])


if __name__ == "__main__":
    CompositeMarketData.run()
