"""Ornstein-Uhlenbeck mean-reversion strategy over composite spreads.

Trades composites whose two constituent instruments form a cointegrated pair.
Consumes :class:`MarketData` (instrument-level CLOSE) and :class:`OUParams`
(composite-level mu/theta/sigma/beta). On each tick it builds the log-spread
``s = ln(p_a) - beta * ln(p_b)`` per composite, computes the Leung-Li optimal
entry/exit levels from the known OU parameters, and opens/closes composite-
scoped trades when the spread crosses those levels.
"""

from __future__ import annotations

import math
import os
import uuid
from typing import ClassVar

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ascent.feeds.examples.market import MarketData
from ascent.feeds.examples.ou_params import OUParams
from ascent.feeds.examples.ou_spread import OUSpread
from ascent.math._non_rolling import OrnsteinUhlenbeck
from ascent.strategies import (
    Context,
    Plot,
    PlotSeries,
    SeriesStyle,
    Strategy,
    TradeView,
)


class OUStrategy(Strategy):
    """Mean-reversion on composite spreads using Leung-Li optimal levels."""

    class Parameters(BaseModel):
        discount_rate: float = Field(
            1.0e-3,
            gt=0,
            description=(
                "r in the Leung-Li framework. Per-second rate matching the "
                "per-second mu published by OUParams; r/mu ~ 3 puts the "
                "optimal exit ~0.5 stationary stds from theta."
            ),
        )
        transaction_cost: float = Field(0.01, ge=0, description="c in the Leung-Li framework")
        quantity: float = Field(1.0, gt=0, description="Composite units per trade")

    feeds = [MarketData, OUParams, OUSpread]
    scope = "composite"
    exchanges = ["KRAKEN_SECURITY_EXCHANGE"]
    base_asset = "USD"
    display_name = "OU Strategy"
    description = "Mean-reversion on composite spreads using Leung-Li optimal entry/exit levels."
    trade_view = TradeView(
        plots=[
            Plot(
                id="spread",
                title="OU Spread",
                y_axis_label="Log Spread",
                main_series_name="OU_SPREAD",
                series=[
                    PlotSeries(
                        name="OU_SPREAD",
                        label="Spread",
                        style=SeriesStyle(color="primary", line_width=2.5, opacity=1.0),
                    ),
                    PlotSeries(
                        name="OU_THETA",
                        label="Mean (θ)",
                        style=SeriesStyle(color="info", line_style="dashed", opacity=0.5),
                    ),
                    PlotSeries(
                        name="OU_ENTRY",
                        label="Entry Threshold",
                        style=SeriesStyle(color="warning", line_style="dashed", opacity=0.4),
                    ),
                    PlotSeries(
                        name="OU_EXIT",
                        label="Exit Threshold",
                        style=SeriesStyle(color="warning", line_style="dashed", opacity=0.4),
                    ),
                ],
            ),
        ],
        show_trade_markers=True,
        show_trade_status_overlay=True,
    )

    _composite_legs: ClassVar[dict[uuid.UUID, tuple[uuid.UUID, uuid.UUID]]] = {}
    _initialised: ClassVar[bool] = False

    def _ensure_initialised(self) -> None:
        if OUStrategy._initialised:
            return
        from ascent.database.models.composites import Composite, CompositeMember
        from ascent.database.models.types import CompositeType

        engine = create_engine(os.environ["ASCENT_DATABASE_URL"])
        with Session(engine) as db:
            rows = db.execute(
                select(Composite.id, CompositeMember.order, CompositeMember.instrument_id)
                .join(CompositeType, Composite.composite_type_id == CompositeType.id)
                .join(CompositeMember, CompositeMember.composite_id == Composite.id)
                .where(CompositeType.name == "SPREAD")
                .order_by(Composite.id, CompositeMember.order)
            ).all()

        legs_by_composite: dict[uuid.UUID, dict[int, uuid.UUID]] = {}
        for composite_id, order, instrument_id in rows:
            legs_by_composite.setdefault(composite_id, {})[order] = instrument_id

        for composite_id, legs in legs_by_composite.items():
            if set(legs.keys()) == {1, 2}:
                OUStrategy._composite_legs[composite_id] = (legs[1], legs[2])

        OUStrategy._initialised = True

    _DERIVED_COLUMNS: ClassVar[tuple[str, ...]] = (
        "spread",
        "mean",
        "entry_long",
        "exit_long",
        "entry_short",
        "exit_short",
    )

    def derive(self, ctx: Context) -> pd.DataFrame:
        """Per-composite spread and Leung-Li optimal entry/exit levels.

        Returned frame shares ``ctx.df.index`` (MultiIndex composite_id,
        instrument_id) with the same value broadcast across each composite's
        legs — the UI de-duplicates on the server side when serializing.
        """
        frame = pd.DataFrame(
            index=ctx.df.index,
            columns=list(self._DERIVED_COLUMNS),
            dtype=float,
        )
        if ctx.df.empty:
            return frame

        self._ensure_initialised()

        for composite_str in ctx.df.index.get_level_values("composite_id").unique():
            composite_id = uuid.UUID(composite_str)
            legs = OUStrategy._composite_legs.get(composite_id)
            if legs is None:
                continue
            values = self._compute_composite_row(ctx, composite_str, legs)
            if values is None:
                continue
            for name, value in values.items():
                frame.loc[composite_str, name] = value

        return frame

    def _compute_composite_row(
        self,
        ctx: Context,
        composite_str: str,
        legs: tuple[uuid.UUID, uuid.UUID],
    ) -> dict[str, float] | None:
        inst_a, inst_b = legs
        try:
            composite_rows = ctx.df.loc[composite_str]
        except KeyError:
            return None
        if composite_rows.empty:
            return None

        head = composite_rows.iloc[0]
        try:
            mu = float(head[("ou_params", "OU_MU")])
            theta = float(head[("ou_params", "OU_THETA")])
            sigma = float(head[("ou_params", "OU_SIGMA")])
            beta = float(head[("ou_params", "OU_BETA")])
        except KeyError:
            return None
        if any(not math.isfinite(v) for v in (mu, theta, sigma, beta)):
            return None
        if mu <= 0 or sigma <= 0 or beta == 0:
            return None

        try:
            price_a = float(ctx.df.loc[(composite_str, str(inst_a)), ("market_data", "CLOSE")])
            price_b = float(ctx.df.loc[(composite_str, str(inst_b)), ("market_data", "CLOSE")])
        except KeyError:
            return None
        if not (math.isfinite(price_a) and math.isfinite(price_b)):
            return None
        if price_a <= 0 or price_b <= 0:
            return None

        spread = math.log(price_a) - beta * math.log(price_b)
        params = self.parameters

        exit_long = OrnsteinUhlenbeck.get_optimal_exit_level(
            mu=np.array([mu]),
            sigma=np.array([sigma]),
            theta=np.array([theta]),
            discount_rate=params.discount_rate,
            transaction_cost=params.transaction_cost,
        )[0]
        if not np.isfinite(exit_long):
            return None

        entry_long = OrnsteinUhlenbeck.get_optimal_entry_level(
            mu=np.array([mu]),
            sigma=np.array([sigma]),
            theta=np.array([theta]),
            exit_level=np.array([exit_long]),
            discount_rate=params.discount_rate,
            transaction_cost=params.transaction_cost,
        )[0]
        if not np.isfinite(entry_long):
            return None

        return {
            "spread": spread,
            "mean": theta,
            "entry_long": entry_long,
            "exit_long": exit_long,
            "entry_short": 2 * theta - entry_long,
            "exit_short": 2 * theta - exit_long,
        }

    def evaluate(self, ctx: Context) -> None:
        logger = self.get_logger()

        logger.info(ctx.df)

        if ctx.df.empty:
            return

        derived = self.derive(ctx)
        params = self.parameters

        for composite_str in ctx.universe:
            composite_id = uuid.UUID(composite_str)
            legs = OUStrategy._composite_legs.get(composite_id)
            if legs is None:
                continue
            inst_a, inst_b = legs

            try:
                signal = derived.loc[composite_str].iloc[0]
            except KeyError:
                continue
            if signal.isna().any():
                continue

            spread = float(signal["spread"])
            entry_long = float(signal["entry_long"])
            exit_long = float(signal["exit_long"])
            entry_short = float(signal["entry_short"])
            exit_short = float(signal["exit_short"])

            head = ctx.df.loc[composite_str].iloc[0]
            trade_status = str(head[("trade", "status")])
            trade_direction = head[("trade", "direction")]
            trade_id = head[("trade", "trade_id")]

            has_open_trade = trade_status not in ("WAITING", "PENDING")

            logger.info(
                "composite=%s spread=%+.6f entry_long=%+.6f exit_long=%+.6f "
                "entry_short=%+.6f exit_short=%+.6f status=%s",
                composite_str[:8],
                spread,
                entry_long,
                exit_long,
                entry_short,
                exit_short,
                trade_status,
            )

            if not has_open_trade:
                # Strict dollar-neutral sizing: ``params.quantity`` is leg-A's
                # share count; leg B trades ``quantity * (price_a / price_b)``
                # shares so the dollar notional on each side matches.
                price_a = float(ctx.df.loc[(composite_str, str(inst_a)), ("market_data", "CLOSE")])
                price_b = float(ctx.df.loc[(composite_str, str(inst_b)), ("market_data", "CLOSE")])
                if not (
                    math.isfinite(price_a)
                    and math.isfinite(price_b)
                    and price_a > 0
                    and price_b > 0
                ):
                    continue
                leg_ratios = [1.0, price_a / price_b]
                if spread <= entry_long:
                    self.open_trade(
                        composite_id,
                        direction="LONG",
                        quantity=params.quantity,
                        scope="composite",
                        composite_instrument_ids=[inst_a, inst_b],
                        composite_leg_ratios=leg_ratios,
                    )
                    logger.info("OPEN LONG composite=%s spread=%+.6f", composite_str[:8], spread)
                elif spread >= entry_short:
                    self.open_trade(
                        composite_id,
                        direction="SHORT",
                        quantity=params.quantity,
                        scope="composite",
                        composite_instrument_ids=[inst_a, inst_b],
                        composite_leg_ratios=leg_ratios,
                    )
                    logger.info("OPEN SHORT composite=%s spread=%+.6f", composite_str[:8], spread)
                continue

            if trade_id is None:
                continue
            if trade_direction == "LONG" and spread >= exit_long:
                self.close_trade(str(trade_id), close_reason="OPTIMAL_EXIT")
                logger.info("CLOSE LONG composite=%s spread=%+.6f", composite_str[:8], spread)
            elif trade_direction == "SHORT" and spread <= exit_short:
                self.close_trade(str(trade_id), close_reason="OPTIMAL_EXIT")
                logger.info("CLOSE SHORT composite=%s spread=%+.6f", composite_str[:8], spread)


if __name__ == "__main__":
    OUStrategy.run()
