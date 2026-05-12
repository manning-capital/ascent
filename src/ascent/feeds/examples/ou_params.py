"""Ornstein-Uhlenbeck parameter feed.

Publishes ``OU_MU``, ``OU_THETA``, ``OU_SIGMA``, ``OU_BETA`` and the Leung-Li
optimal spread-space entry/exit levels (``OU_ENTRY``, ``OU_EXIT``) per
composite on a 1-second schedule.

Parameters are *derived* from the per-instrument log-OU dynamics defined in
:mod:`ascent.feeds.examples._ou_sim` plus a per-pair hedge ratio ``beta``
sampled deterministically from the composite's UUID. If each leg's log-price
is OU with rate ``INST_MU`` and vol ``INST_SIGMA``, the spread
``s = ln(p_a) - beta * ln(p_b)`` is itself OU with:

- ``mu = INST_MU``
- ``theta = ln(base_a) - beta * ln(base_b)``
- ``sigma = INST_SIGMA * sqrt(1 + beta**2)``

This makes the published OU parameters describe the same process that
``MarketData`` actually evolves, so realized spreads mean-revert to the
published ``theta`` and the strategy's entry/exit thresholds sit where the
spread really oscillates — even when many composites share the same legs.
"""

from __future__ import annotations

import hashlib
import math
import os
import uuid
from datetime import datetime
from typing import ClassVar

import numpy as np
import pandas as pd
from pandera.typing.pandas import DataFrame
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ascent.feeds import Feed, Schedule
from ascent.feeds.examples._ou_sim import INST_MU, INST_SIGMA, base_price_for
from ascent.feeds.output import CompositeAttributes
from ascent.math._non_rolling import OrnsteinUhlenbeck


def _beta_for(composite_id: uuid.UUID) -> float:
    """Deterministic hedge ratio per composite, sampled in [0.8, 1.2]."""
    digest = hashlib.sha256(composite_id.bytes).digest()
    u = int.from_bytes(digest[:8], "big") / 2**64
    return 0.8 + 0.4 * u


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
    # The solver's default n_grid=1000 is conservative against narrow valid
    # windows; for our parameter regime (r/mu ~ 3, theta well-defined per
    # pair) 100 points across 100 stat_stds is ample resolution to land
    # Newton in the right basin and runs ~10x faster.
    exit_levels = OrnsteinUhlenbeck.get_optimal_exit_level(
        mu=mu,
        sigma=sigma,
        theta=theta,
        discount_rate=discount_rate,
        transaction_cost=transaction_cost,
        n_grid=100,
    )
    entry_levels = OrnsteinUhlenbeck.get_optimal_entry_level(
        mu=mu,
        sigma=sigma,
        theta=theta,
        exit_level=exit_levels,
        discount_rate=discount_rate,
        transaction_cost=transaction_cost,
        n_grid=100,
    )
    fallback = 2 * theta - exit_levels
    entry_levels = np.where(np.isfinite(entry_levels), entry_levels, fallback)
    return (entry_levels, exit_levels)


class OUParams(Feed):
    """Emits OU parameters, hedge ratio, and optimal entry/exit per composite."""

    class Parameters(BaseModel):
        discount_rate: float = Field(
            1.0e-3,
            gt=0,
            description=(
                "Leung-Li discount rate r used for optimal levels. Per-second "
                "rate, scaled against INST_MU to give r/mu ~ 3, which puts "
                "the optimal exit ~0.5 stationary stds from theta — narrow "
                "enough that shallow spread excursions still trigger trades."
            ),
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
        "entry/exit levels per composite. Parameters describe the same "
        "process MarketData evolves — the realized spread mean-reverts to "
        "the published theta."
    )

    # Aligned per-composite arrays sized [n_composites]. mu/theta/sigma/beta
    # are static (derived from constants and the composite UUID), so we cache
    # them once in _ensure_initialised and slice into them per tick rather
    # than rebuilding row-by-row.
    _composite_ids: ClassVar[np.ndarray | None] = None
    _mus: ClassVar[np.ndarray | None] = None
    _thetas: ClassVar[np.ndarray | None] = None
    _sigmas: ClassVar[np.ndarray | None] = None
    _betas: ClassVar[np.ndarray | None] = None
    _initialised: ClassVar[bool] = False

    # Entry/exit levels are deterministic from (mu, theta, sigma, r, c) and
    # those inputs are all static per-run. The Leung-Li solver costs ~10s for
    # 465 composites because of its grid + Newton sweep, so we run it once on
    # first fetch and reuse the result. ``_levels_key`` invalidates the cache
    # if (discount_rate, transaction_cost) ever change between calls.
    _entry_arr: ClassVar[np.ndarray | None] = None
    _exit_arr: ClassVar[np.ndarray | None] = None
    _levels_key: ClassVar[tuple[float, float] | None] = None

    _EMPTY_COLUMNS: ClassVar[list[str]] = [
        "composite_id",
        "OU_MU",
        "OU_THETA",
        "OU_SIGMA",
        "OU_BETA",
        "OU_ENTRY",
        "OU_EXIT",
    ]

    def _ensure_initialised(self) -> None:
        if OUParams._initialised:
            return
        from ascent.database.models.assets import Asset
        from ascent.database.models.composites import Composite, CompositeMember
        from ascent.database.models.instruments import Instrument
        from ascent.database.models.types import CompositeType

        engine = create_engine(os.environ["ASCENT_DATABASE_URL"])
        with Session(engine) as db:
            rows = db.execute(
                select(Composite.id, CompositeMember.order, Asset.name)
                .join(CompositeType, Composite.composite_type_id == CompositeType.id)
                .join(CompositeMember, CompositeMember.composite_id == Composite.id)
                .join(Instrument, CompositeMember.instrument_id == Instrument.id)
                .join(Asset, Instrument.from_asset_id == Asset.id)
                .where(CompositeType.name == "SPREAD")
                .order_by(Composite.id, CompositeMember.order)
            ).all()

        legs_by_composite: dict[uuid.UUID, dict[int, str]] = {}
        for composite_id, order, asset_name in rows:
            legs_by_composite.setdefault(composite_id, {})[order] = asset_name

        composite_ids: list[str] = []
        log_base_a: list[float] = []
        log_base_b: list[float] = []
        betas: list[float] = []
        for composite_id, legs in legs_by_composite.items():
            if set(legs.keys()) != {1, 2}:
                continue
            composite_ids.append(str(composite_id))
            log_base_a.append(math.log(base_price_for(legs[1])))
            log_base_b.append(math.log(base_price_for(legs[2])))
            betas.append(_beta_for(composite_id))

        beta_arr = np.array(betas, dtype=float)
        log_a = np.array(log_base_a, dtype=float)
        log_b = np.array(log_base_b, dtype=float)

        OUParams._composite_ids = np.array(composite_ids, dtype=object)
        OUParams._betas = beta_arr
        OUParams._thetas = log_a - beta_arr * log_b
        OUParams._sigmas = INST_SIGMA * np.sqrt(1.0 + beta_arr * beta_arr)
        OUParams._mus = np.full_like(beta_arr, INST_MU)
        OUParams._initialised = True

    def _ensure_levels_cached(self, discount_rate: float, transaction_cost: float) -> None:
        """Run the Leung-Li solver once for all composites and cache the result.

        Re-runs only if (discount_rate, transaction_cost) change vs the cached
        key — for the steady-state case (params static across ticks) this is
        a no-op after the first call.
        """
        key = (discount_rate, transaction_cost)
        if OUParams._levels_key == key and OUParams._entry_arr is not None:
            return

        mu_arr = OUParams._mus
        theta_arr = OUParams._thetas
        sigma_arr = OUParams._sigmas
        n = mu_arr.size

        # Solver's single-element grid-search path breaks on numpy >= 2.x
        # (it does float() on a 1-D array); pad to length 2 so we always
        # take the multi-element branch, then slice the result back down.
        if n == 1:
            mu_solve = np.concatenate([mu_arr, mu_arr])
            theta_solve = np.concatenate([theta_arr, theta_arr])
            sigma_solve = np.concatenate([sigma_arr, sigma_arr])
        else:
            mu_solve = mu_arr
            theta_solve = theta_arr
            sigma_solve = sigma_arr

        entry_solve, exit_solve = _batch_levels(
            mu=mu_solve,
            theta=theta_solve,
            sigma=sigma_solve,
            discount_rate=discount_rate,
            transaction_cost=transaction_cost,
        )
        OUParams._entry_arr = entry_solve[:n]
        OUParams._exit_arr = exit_solve[:n]
        OUParams._levels_key = key

    def fetch(self) -> DataFrame[CompositeAttributes]:
        logger = self.get_logger()
        params = self.parameters

        self._ensure_initialised()

        composite_ids = OUParams._composite_ids
        if composite_ids is None or len(composite_ids) == 0:
            logger.info("No SPREAD composites known — emitting empty frame")
            return pd.DataFrame(columns=self._EMPTY_COLUMNS)

        universe_ids = self.get_universe()
        if not universe_ids:
            logger.info("Universe empty — emitting empty frame")
            return pd.DataFrame(columns=self._EMPTY_COLUMNS)

        self._ensure_levels_cached(params.discount_rate, params.transaction_cost)

        universe_str = {str(u) for u in universe_ids}
        in_universe = np.fromiter(
            (cid in universe_str for cid in composite_ids),
            dtype=bool,
            count=len(composite_ids),
        )
        if not in_universe.any():
            logger.info("No known composites in universe — emitting empty frame")
            return pd.DataFrame(columns=self._EMPTY_COLUMNS)

        df = pd.DataFrame(
            {
                "composite_id": composite_ids[in_universe],
                "OU_MU": np.round(OUParams._mus[in_universe], 8),
                "OU_THETA": np.round(OUParams._thetas[in_universe], 8),
                "OU_SIGMA": np.round(OUParams._sigmas[in_universe], 8),
                "OU_BETA": np.round(OUParams._betas[in_universe], 8),
                "OU_ENTRY": np.round(OUParams._entry_arr[in_universe], 8),
                "OU_EXIT": np.round(OUParams._exit_arr[in_universe], 8),
            }
        )
        logger.info("Generated OU params for %d composites", len(df))
        return df


if __name__ == "__main__":
    OUParams.run()
