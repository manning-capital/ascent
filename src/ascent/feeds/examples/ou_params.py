"""Ornstein-Uhlenbeck parameter feed — triggered by composite market data.

Emits the OU parameters ``OU_MU``, ``OU_THETA``, ``OU_SIGMA`` plus the current
``OU_Z_SCORE`` per composite, using the same deterministic params as
:mod:`ascent.feeds.examples.composite_market` so each pair's dynamics stay
consistent across feeds.
"""

import uuid

import pandas as pd
from pandera.typing.pandas import DataFrame
from pydantic import BaseModel, Field

from ascent.feeds import Feed
from ascent.feeds.examples.composite_market import CompositeMarketData, _params_for
from ascent.feeds.output import CompositeAttributes


class OUParams(Feed):
    """Emits OU parameters and z-score per composite on each trigger."""

    class Parameters(BaseModel):
        lookback_days: int = Field(default=60, ge=7, le=365)

    depends_on = [CompositeMarketData]
    output = CompositeAttributes
    provider = "KRAKEN"
    composite_type = "SPREAD"
    display_name = "OU Parameters"
    description = "Emits OU mu/theta/sigma and current z-score per composite."

    def fetch(self) -> DataFrame[CompositeAttributes]:
        logger = self.get_logger()
        prices = self.get_feed(CompositeMarketData)
        logger.info("Computing OU params from %d rows", len(prices))

        if prices.empty:
            return pd.DataFrame(
                columns=["composite_id", "OU_MU", "OU_THETA", "OU_SIGMA", "OU_Z_SCORE"]
            )

        rows: list[dict] = []
        for _, price_row in prices.iterrows():
            cid = uuid.UUID(str(price_row["composite_id"]))
            spread = float(price_row["CLOSE"])
            mu, theta, sigma = _params_for(cid)
            z = (spread - theta) / sigma if sigma > 0 else 0.0
            rows.append(
                {
                    "composite_id": str(cid),
                    "OU_MU": round(mu, 8),
                    "OU_THETA": round(theta, 8),
                    "OU_SIGMA": round(sigma, 8),
                    "OU_Z_SCORE": round(z, 8),
                }
            )

        return pd.DataFrame(
            rows, columns=["composite_id", "OU_MU", "OU_THETA", "OU_SIGMA", "OU_Z_SCORE"]
        )


if __name__ == "__main__":
    OUParams.run()
