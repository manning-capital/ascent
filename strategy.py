"""Pairs-trading strategy over composite SPREAD instruments using OU parameters.

For each composite in the active universe, the strategy reads the hedge
ratio ``OU_BETA``, the long-run mean ``OU_THETA``, and the Leung-Li optimal
spread-space ``OU_ENTRY`` / ``OU_EXIT`` levels from the :class:`OUParams`
feed, computes the current log-spread ``s = ln(P_A) - beta * ln(P_B)`` across
the two legs, and opens or closes a composite-scoped trade when the spread
crosses those levels. Short-side triggers are derived by reflecting the entry
and exit levels around ``theta``.

Because the OU parameters are fixed per composite and the optimal levels are
emitted by the feed, the strategy needs no rolling window and no warmup.
"""

from __future__ import annotations

import math
import os
import uuid
from typing import ClassVar

import pandas as pd
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ascent.strategies import Context, Strategy, TradeView


class PairsOUStrategy(Strategy):
    """Trade mean-reverting composite spreads using feed-published OU levels."""

    class Parameters(BaseModel):
        capital_per_trade: float = Field(
            1000.0,
            gt=0,
            description=(
                "Target capital (USD) per trade. Composite units are sized as "
                "capital_per_trade / (price_a + beta * price_b) for approximate "
                "dollar-neutral pairs exposure."
            ),
        )

    feeds = ["MARKET_DATA", "OUPARAMS", "OUSPREAD"]
    scope = "composite"
    exchanges = ["KRAKEN_SECURITY_EXCHANGE"]
    portfolio = "MAIN"
    display_name = "Pairs OU Strategy"
    description = (
        "Mean-reversion on composite spreads using Leung-Li optimal "
        "entry/exit levels published by the OU parameter feed."
    )
    trade_view = TradeView(
        series=["OU_SPREAD", "OU_THETA", "OU_ENTRY", "OU_EXIT"],
        show_trade_markers=True,
    )

    _composite_legs: ClassVar[dict[uuid.UUID, tuple[uuid.UUID, uuid.UUID]]] = {}
    _initialised: ClassVar[bool] = False

    _DERIVED_COLUMNS: ClassVar[tuple[str, ...]] = (
        "spread",
        "mean",
        "entry_long",
        "exit_long",
        "entry_short",
        "exit_short",
    )

    def _ensure_initialised(self) -> None:
        if PairsOUStrategy._initialised:
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
                PairsOUStrategy._composite_legs[composite_id] = (legs[1], legs[2])

        PairsOUStrategy._initialised = True

    def derive(self, ctx: Context) -> pd.DataFrame:
        """Per-composite spread + feed-published entry/exit levels.

        Pure: no logging, no trade routing. Called both by ``evaluate`` during
        the live loop and by the server's trade-context endpoint when it
        reconstructs this strategy's plottable signals from historical feed
        data. Returned frame shares ``ctx.df.index`` — same value broadcast
        across each composite's two legs; the server de-duplicates.
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
            legs = PairsOUStrategy._composite_legs.get(composite_id)
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
            raw_beta = head[("ouparams", "OU_BETA")]
            raw_theta = head[("ouparams", "OU_THETA")]
            raw_entry = head[("ouparams", "OU_ENTRY")]
            raw_exit = head[("ouparams", "OU_EXIT")]
        except KeyError:
            return None
        if any(v is None or pd.isna(v) for v in (raw_beta, raw_theta, raw_entry, raw_exit)):
            return None
        beta = float(raw_beta)
        theta = float(raw_theta)
        entry_long = float(raw_entry)
        exit_long = float(raw_exit)
        if any(not math.isfinite(v) for v in (beta, theta, entry_long, exit_long)):
            return None
        if beta == 0:
            return None

        try:
            raw_price_a = ctx.df.loc[(composite_str, str(inst_a)), ("market_data", "CLOSE")]
            raw_price_b = ctx.df.loc[(composite_str, str(inst_b)), ("market_data", "CLOSE")]
        except KeyError:
            return None
        if any(v is None or pd.isna(v) for v in (raw_price_a, raw_price_b)):
            return None
        price_a = float(raw_price_a)
        price_b = float(raw_price_b)
        if not (math.isfinite(price_a) and math.isfinite(price_b)):
            return None
        if price_a <= 0 or price_b <= 0:
            return None

        spread = math.log(price_a) - beta * math.log(price_b)
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

        logger.info("evaluate tick: df_rows=%d universe=%d", len(ctx.df), len(ctx.universe))
        if ctx.df.empty:
            logger.info("skip: ctx.df is empty (no feed data arrived yet)")
            return
        self._ensure_initialised()
        logger.info("composite_legs resolved: %d", len(PairsOUStrategy._composite_legs))

        params = self.parameters

        for composite_str in ctx.universe:
            composite_id = uuid.UUID(composite_str)
            legs = PairsOUStrategy._composite_legs.get(composite_id)
            if legs is None:
                logger.info("%s skip: composite not in leg lookup", composite_str[:8])
                continue
            inst_a, inst_b = legs

            try:
                composite_rows = ctx.df.loc[composite_str]
            except KeyError:
                logger.info("%s skip: composite not in ctx.df", composite_str[:8])
                continue
            if composite_rows.empty:
                logger.info("%s skip: composite rows empty", composite_str[:8])
                continue

            head = composite_rows.iloc[0]
            try:
                raw_beta = head[("ouparams", "OU_BETA")]
                raw_theta = head[("ouparams", "OU_THETA")]
                raw_entry = head[("ouparams", "OU_ENTRY")]
                raw_exit = head[("ouparams", "OU_EXIT")]
            except KeyError:
                logger.info(
                    "%s skip: ouparams columns missing (cols=%s)",
                    composite_str[:8],
                    list(head.index),
                )
                continue
            if any(v is None or pd.isna(v) for v in (raw_beta, raw_theta, raw_entry, raw_exit)):
                logger.info(
                    "%s skip: ouparams not yet populated beta=%s theta=%s entry=%s exit=%s",
                    composite_str[:8],
                    raw_beta,
                    raw_theta,
                    raw_entry,
                    raw_exit,
                )
                continue
            beta = float(raw_beta)
            theta = float(raw_theta)
            entry_level = float(raw_entry)
            exit_level = float(raw_exit)
            if any(not math.isfinite(v) for v in (beta, theta, entry_level, exit_level)):
                logger.info(
                    "%s skip: non-finite ouparams beta=%s theta=%s entry=%s exit=%s",
                    composite_str[:8],
                    beta,
                    theta,
                    entry_level,
                    exit_level,
                )
                continue
            if beta == 0:
                logger.info("%s skip: beta is 0", composite_str[:8])
                continue

            entry_short = 2 * theta - entry_level
            exit_short = 2 * theta - exit_level

            try:
                raw_price_a = ctx.df.loc[(composite_str, str(inst_a)), ("market_data", "CLOSE")]
                raw_price_b = ctx.df.loc[(composite_str, str(inst_b)), ("market_data", "CLOSE")]
            except KeyError:
                logger.info(
                    "%s skip: market_data.CLOSE missing for legs a=%s b=%s",
                    composite_str[:8],
                    str(inst_a)[:8],
                    str(inst_b)[:8],
                )
                continue
            if any(v is None or pd.isna(v) for v in (raw_price_a, raw_price_b)):
                logger.info(
                    "%s skip: market_data.CLOSE not yet populated a=%s b=%s",
                    composite_str[:8],
                    raw_price_a,
                    raw_price_b,
                )
                continue
            price_a = float(raw_price_a)
            price_b = float(raw_price_b)
            if not (math.isfinite(price_a) and math.isfinite(price_b)):
                logger.info(
                    "%s skip: non-finite prices a=%s b=%s",
                    composite_str[:8],
                    price_a,
                    price_b,
                )
                continue
            if price_a <= 0 or price_b <= 0:
                logger.info(
                    "%s skip: non-positive prices a=%s b=%s",
                    composite_str[:8],
                    price_a,
                    price_b,
                )
                continue

            spread = math.log(price_a) - beta * math.log(price_b)

            trade_status = str(head[("trade", "status")])
            trade_direction = head[("trade", "direction")]
            trade_id = head[("trade", "trade_id")]

            logger.info(
                "composite=%s spread=%+.6f entry=%+.6f exit=%+.6f theta=%+.6f status=%s",
                composite_str[:8],
                spread,
                entry_level,
                exit_level,
                theta,
                trade_status,
            )

            if trade_status in ("OPENING", "CLOSING", "PENDING", "ERROR"):
                continue

            if trade_status == "WAITING":
                # Beta-hedged sizing: gross notional of a same-quantity pair
                # is qty*(price_a + beta*price_b), so quantity that consumes
                # `capital_per_trade` dollars of gross exposure is:
                gross_per_unit = price_a + beta * price_b
                if gross_per_unit <= 0:
                    logger.info(
                        "%s skip: non-positive gross_per_unit=%s", composite_str[:8], gross_per_unit
                    )
                    continue
                quantity = params.capital_per_trade / gross_per_unit

                if spread <= entry_level:
                    self.open_trade(
                        composite_id,
                        direction="LONG",
                        quantity=quantity,
                        scope="composite",
                        composite_instrument_ids=[inst_a, inst_b],
                    )
                    logger.info(
                        "OPEN LONG composite=%s spread=%+.6f qty=%.6f",
                        composite_str[:8],
                        spread,
                        quantity,
                    )
                elif spread >= entry_short:
                    self.open_trade(
                        composite_id,
                        direction="SHORT",
                        quantity=quantity,
                        scope="composite",
                        composite_instrument_ids=[inst_a, inst_b],
                    )
                    logger.info(
                        "OPEN SHORT composite=%s spread=%+.6f qty=%.6f",
                        composite_str[:8],
                        spread,
                        quantity,
                    )
                continue

            if trade_status == "OPEN":
                if trade_id is None:
                    continue
                if trade_direction == "LONG" and spread >= exit_level:
                    self.close_trade(str(trade_id), close_reason="OPTIMAL_EXIT")
                    logger.info("CLOSE LONG composite=%s spread=%+.6f", composite_str[:8], spread)
                elif trade_direction == "SHORT" and spread <= exit_short:
                    self.close_trade(str(trade_id), close_reason="OPTIMAL_EXIT")
                    logger.info("CLOSE SHORT composite=%s spread=%+.6f", composite_str[:8], spread)


if __name__ == "__main__":
    PairsOUStrategy.run(
        redis_url=os.environ["ASCENT_REDIS_URL"],
        database_url=os.environ["ASCENT_DATABASE_URL"],
    )
