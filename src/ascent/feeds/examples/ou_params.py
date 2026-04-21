"""Ornstein-Uhlenbeck parameter feed.

Publishes ``OU_MU``, ``OU_THETA``, ``OU_SIGMA``, ``OU_BETA`` per composite on a
5-second schedule. Parameters are derived deterministically from each
composite's UUID so a given pair always gets the same dynamics across restarts.
"""

import hashlib
import uuid
from datetime import datetime

import pandas as pd
from pandera.typing.pandas import DataFrame
from pydantic import BaseModel

from ascent.feeds import Feed, Schedule
from ascent.feeds.output import CompositeAttributes


def _params_for(composite_id: uuid.UUID) -> tuple[float, float, float, float]:
    """Return deterministic ``(mu, theta, sigma, beta)`` for a composite."""
    digest = hashlib.sha256(composite_id.bytes).digest()

    def _u(i: int) -> float:
        return int.from_bytes(digest[i * 8 : (i + 1) * 8], "big") / 2**64

    mu = 0.05 + 0.20 * _u(0)
    theta = -0.05 + 0.10 * _u(1)
    sigma = 0.01 + 0.04 * _u(2)
    beta = 0.5 + 1.0 * _u(3)
    return (mu, theta, sigma, beta)


class OUParams(Feed):
    """Emits OU parameters and hedge ratio per composite on each tick."""

    class Parameters(BaseModel):
        pass

    schedule = Schedule(interval=5, start_date=datetime(2024, 1, 1))
    output = CompositeAttributes
    provider = "KRAKEN"
    composite_type = "SPREAD"
    display_name = "OU Parameters"
    description = "Emits OU mu/theta/sigma and hedge ratio beta per composite."

    def fetch(self) -> DataFrame[CompositeAttributes]:
        logger = self.get_logger()
        universe_ids = self.get_universe()

        rows: list[dict] = []
        for cid in universe_ids:
            mu, theta, sigma, beta = _params_for(cid)
            rows.append(
                {
                    "composite_id": str(cid),
                    "OU_MU": round(mu, 8),
                    "OU_THETA": round(theta, 8),
                    "OU_SIGMA": round(sigma, 8),
                    "OU_BETA": round(beta, 8),
                }
            )

        logger.info("Generated OU params for %d composites", len(rows))
        return pd.DataFrame(
            rows, columns=["composite_id", "OU_MU", "OU_THETA", "OU_SIGMA", "OU_BETA"]
        )


if __name__ == "__main__":
    OUParams.run()
