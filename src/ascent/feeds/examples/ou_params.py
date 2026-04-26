"""Ornstein-Uhlenbeck parameter feed.

Publishes ``OU_MU``, ``OU_THETA``, ``OU_SIGMA``, ``OU_BETA`` and the Leung-Li
optimal spread-space entry/exit levels (``OU_ENTRY``, ``OU_EXIT``) per
composite on a 1-second schedule. Parameters are derived deterministically
from each composite's UUID so a given pair always gets the same dynamics
across restarts.
"""

import hashlib
import uuid
from datetime import datetime

import numpy as np
import pandas as pd
from pandera.typing.pandas import DataFrame
from pydantic import BaseModel, Field

from ascent.feeds import Feed, Schedule
from ascent.feeds.output import CompositeAttributes
from ascent.math._non_rolling import OrnsteinUhlenbeck


def _params_for(composite_id: uuid.UUID) -> tuple[float, float, float, float]:
    """Return deterministic ``(mu, theta, sigma, beta)`` for a composite.

    Ranges are tuned to:
    - keep the spread scale (~sigma) comfortably above the default
      transaction cost (0.01) so Leung-Li's entry-level solve stays in a
      profitable region;
    - keep ``beta`` near 1 so the ``price_b = exp((ln p_a - spread) / beta)``
      transform in the market-data feed doesn't amplify per-tick spread
      noise into huge price swings on leg B.
    """
    digest = hashlib.sha256(composite_id.bytes).digest()

    def _u(i: int) -> float:
        return int.from_bytes(digest[i * 8 : (i + 1) * 8], "big") / 2**64

    mu = 0.05 + 0.15 * _u(0)
    theta = -0.05 + 0.10 * _u(1)
    sigma = 0.02 + 0.03 * _u(2)
    beta = 0.8 + 0.4 * _u(3)
    return (mu, theta, sigma, beta)


def _batch_levels(
    mu: np.ndarray,
    theta: np.ndarray,
    sigma: np.ndarray,
    discount_rate: float,
    transaction_cost: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute Leung-Li optimal ``(entry, exit)`` spread levels elementwise.

    Inputs must be 1-D numpy arrays of equal length; the solver's grid search
    requires length >= 2 to broadcast cleanly. For composites where the entry
    Newton solve fails to converge (numerical instability for some parameter
    combinations), fall back to ``2*theta - exit`` so the strategy still has a
    usable symmetric entry threshold.
    """
    exit_levels = OrnsteinUhlenbeck.get_optimal_exit_level(
        mu=mu,
        sigma=sigma,
        theta=theta,
        discount_rate=discount_rate,
        transaction_cost=transaction_cost,
    )
    entry_levels = OrnsteinUhlenbeck.get_optimal_entry_level(
        mu=mu,
        sigma=sigma,
        theta=theta,
        exit_level=exit_levels,
        discount_rate=discount_rate,
        transaction_cost=transaction_cost,
    )
    fallback = 2 * theta - exit_levels
    entry_levels = np.where(np.isfinite(entry_levels), entry_levels, fallback)
    return (entry_levels, exit_levels)


class OUParams(Feed):
    """Emits OU parameters, hedge ratio, and optimal entry/exit per composite."""

    class Parameters(BaseModel):
        discount_rate: float = Field(
            0.01, gt=0, description="Leung-Li discount rate r used for optimal levels"
        )
        transaction_cost: float = Field(
            0.002, ge=0, description="Leung-Li transaction cost c used for optimal levels"
        )

    schedule = Schedule(interval=1, start_date=datetime(2024, 1, 1))
    output = CompositeAttributes
    provider = "KRAKEN"
    composite_type = "SPREAD"
    display_name = "OU Parameters"
    description = (
        "Emits OU mu/theta/sigma, hedge ratio beta, and Leung-Li optimal "
        "entry/exit levels per composite."
    )

    def fetch(self) -> DataFrame[CompositeAttributes]:
        logger = self.get_logger()
        universe_ids = list(self.get_universe())
        params = self.parameters

        all_params = [(cid, *_params_for(cid)) for cid in universe_ids]

        # No composites in scope yet — emit an empty frame so the engine
        # records the run cleanly. Happens at cold-start before scope rows
        # are seeded.
        if not all_params:
            logger.info("No composites in scope — emitting empty frame")
            return pd.DataFrame(
                columns=[
                    "composite_id",
                    "OU_MU",
                    "OU_THETA",
                    "OU_SIGMA",
                    "OU_BETA",
                    "OU_ENTRY",
                    "OU_EXIT",
                ],
            )

        # Solver's single-element grid-search path breaks on numpy >= 2.x
        # (it does float() on a 1-D array); pad to length 2 so we always
        # take the multi-element branch.
        padded = all_params if len(all_params) >= 2 else all_params + [all_params[0]]
        mu_arr = np.array([p[1] for p in padded])
        theta_arr = np.array([p[2] for p in padded])
        sigma_arr = np.array([p[3] for p in padded])

        entry_arr, exit_arr = _batch_levels(
            mu=mu_arr,
            theta=theta_arr,
            sigma=sigma_arr,
            discount_rate=params.discount_rate,
            transaction_cost=params.transaction_cost,
        )

        rows: list[dict] = []
        for i, (cid, mu, theta, sigma, beta) in enumerate(all_params):
            rows.append(
                {
                    "composite_id": str(cid),
                    "OU_MU": round(mu, 8),
                    "OU_THETA": round(theta, 8),
                    "OU_SIGMA": round(sigma, 8),
                    "OU_BETA": round(beta, 8),
                    "OU_ENTRY": round(float(entry_arr[i]), 8),
                    "OU_EXIT": round(float(exit_arr[i]), 8),
                }
            )

        logger.info("Generated OU params for %d composites", len(rows))
        return pd.DataFrame(
            rows,
            columns=[
                "composite_id",
                "OU_MU",
                "OU_THETA",
                "OU_SIGMA",
                "OU_BETA",
                "OU_ENTRY",
                "OU_EXIT",
            ],
        )


if __name__ == "__main__":
    OUParams.run()
