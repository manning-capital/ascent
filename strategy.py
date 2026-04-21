"""Pairs-trading strategy over Ornstein-Uhlenbeck simulated spreads.

For each configured pair ``(A, B)``, the strategy tracks a rolling mean and
stddev of the log-spread ``s = ln(P_A) - ln(P_B)``, computes a z-score, and
opens two simultaneous trades when the spread diverges:

    z > entry_z   → SHORT A, LONG B       (spread too high; bet on reversion)
    z < -entry_z  → LONG A, SHORT B       (spread too low)

Both legs are closed together once ``|z|`` falls back inside ``exit_z``,
or if the stop is breached.
"""

from __future__ import annotations

import math
import os
import uuid
from collections import deque
from typing import ClassVar

import pandas as pd
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ascent.strategies import Context, Strategy

PAIRS: list[tuple[str, str]] = [
    ("BTC", "ETH"),
    ("SOL", "ADA"),
    ("XRP", "ADA"),
]


def _load_pair_instrument_ids(
    database_url: str, pairs: list[tuple[str, str]]
) -> list[tuple[uuid.UUID, uuid.UUID, str, str]]:
    """Resolve each ``(sym_a, sym_b)`` pair to instrument UUIDs from the DB."""
    from ascent.database.models.assets import Asset
    from ascent.database.models.instruments import Instrument

    engine = create_engine(database_url)
    symbol_to_inst: dict[str, uuid.UUID] = {}
    with Session(engine) as db:
        rows = db.execute(
            select(Instrument.id, Asset.name).join(Asset, Instrument.from_asset_id == Asset.id)
        ).all()
        for inst_id, asset_name in rows:
            symbol_to_inst[asset_name] = inst_id

    resolved: list[tuple[uuid.UUID, uuid.UUID, str, str]] = []
    for sym_a, sym_b in pairs:
        if sym_a not in symbol_to_inst or sym_b not in symbol_to_inst:
            print(f"Skipping pair {sym_a}/{sym_b} (missing instrument)")
            continue
        resolved.append((symbol_to_inst[sym_a], symbol_to_inst[sym_b], sym_a, sym_b))
    return resolved


class PairsOUStrategy(Strategy):
    """Trade mean-reverting pair spreads using a rolling z-score."""

    class Parameters(BaseModel):
        lookback: int = Field(100, description="Rolling window size for spread stats")
        warmup: int = Field(30, description="Min samples before trading")
        entry_z: float = Field(2.0, description="Absolute z-score to open a pair")
        exit_z: float = Field(0.5, description="Absolute z-score to close a pair")
        stop_z: float = Field(4.0, description="Absolute z-score to hard-stop a pair")
        trade_qty: float = Field(0.01, description="Quantity per leg")

    feeds = ["MARKET_DATA", "OUPARAMS"]
    exchanges = ["KRAKEN_SECURITY_EXCHANGE"]
    portfolio = "MAIN"

    _pairs: ClassVar[list[tuple[uuid.UUID, uuid.UUID, str, str]]] = []
    _spread_history: ClassVar[dict[tuple[str, str], deque[float]]] = {}
    _open_pair_trades: ClassVar[
        dict[tuple[str, str], tuple[uuid.UUID, uuid.UUID, str]]
    ] = {}

    def _spread(self, ctx: Context, inst_a: uuid.UUID, inst_b: uuid.UUID) -> float | None:
        try:
            price_a = ctx.df.loc[str(inst_a), ("market_data_feed", "close")]
            price_b = ctx.df.loc[str(inst_b), ("market_data_feed", "close")]
        except KeyError:
            return None
        if pd.isna(price_a) or pd.isna(price_b) or price_a <= 0 or price_b <= 0:
            return None
        return math.log(price_a) - math.log(price_b)

    def _open_pair(
        self,
        log,
        key: tuple[str, str],
        inst_a: uuid.UUID,
        inst_b: uuid.UUID,
        side_a: str,
    ) -> None:
        """Open both legs of a pair trade simultaneously."""
        side_b = "SHORT" if side_a == "LONG" else "LONG"
        qty = self.parameters.trade_qty

        res_a = self.open_trade(inst_a, side_a, qty)
        res_b = self.open_trade(inst_b, side_b, qty)
        self._open_pair_trades[key] = (res_a.trade_id, res_b.trade_id, side_a)

        log.info(
            "OPEN PAIR  %s/%s  %s %s / %s %s  trades=%s,%s",
            key[0],
            key[1],
            side_a,
            str(inst_a)[:8],
            side_b,
            str(inst_b)[:8],
            str(res_a.trade_id)[:8],
            str(res_b.trade_id)[:8],
        )

    def _close_pair(self, log, key: tuple[str, str], reason: str) -> None:
        trade_a, trade_b, _ = self._open_pair_trades.pop(key)
        try:
            self.close_trade(trade_a, close_reason=reason)
        except Exception:  # noqa: BLE001
            log.exception("Failed to close leg A trade=%s", trade_a)
        try:
            self.close_trade(trade_b, close_reason=reason)
        except Exception:  # noqa: BLE001
            log.exception("Failed to close leg B trade=%s", trade_b)
        log.info("CLOSE PAIR %s/%s  reason=%s", key[0], key[1], reason)

    def evaluate(self, ctx: Context) -> None:
        log = self.get_logger()
        log.info("Evaluating strategy with %d rows of data", len(ctx.df))

        if ctx.df.empty or not self._pairs:
            return

        params = self.parameters

        for inst_a, inst_b, sym_a, sym_b in self._pairs:
            key = (sym_a, sym_b)
            spread = self._spread(ctx, inst_a, inst_b)
            if spread is None:
                continue

            history = self._spread_history.setdefault(key, deque(maxlen=params.lookback))
            history.append(spread)

            if len(history) < params.warmup:
                continue

            series = pd.Series(history)
            mu = series.mean()
            sd = series.std(ddof=0)
            if sd == 0 or pd.isna(sd):
                continue

            z = (spread - mu) / sd

            open_state = self._open_pair_trades.get(key)
            if open_state is not None:
                _, _, side_a = open_state
                diverged_further = (side_a == "SHORT" and z >= params.stop_z) or (
                    side_a == "LONG" and z <= -params.stop_z
                )
                reverted = abs(z) <= params.exit_z
                if reverted:
                    self._close_pair(log, key, reason="MEAN_REVERT")
                elif diverged_further:
                    self._close_pair(log, key, reason="STOP_LOSS")
                else:
                    log.debug("%s/%s  holding  z=%+.2f", sym_a, sym_b, z)
                continue

            if z >= params.entry_z:
                log.info("%s/%s  z=%+.2f  → SHORT %s / LONG %s", sym_a, sym_b, z, sym_a, sym_b)
                self._open_pair(log, key, inst_a, inst_b, side_a="SHORT")
            elif z <= -params.entry_z:
                log.info("%s/%s  z=%+.2f  → LONG %s / SHORT %s", sym_a, sym_b, z, sym_a, sym_b)
                self._open_pair(log, key, inst_a, inst_b, side_a="LONG")


if __name__ == "__main__":
    db_url = os.environ["ASCENT_DATABASE_URL"]
    PairsOUStrategy._pairs = _load_pair_instrument_ids(db_url, PAIRS)
    print(f"Resolved {len(PairsOUStrategy._pairs)} pairs for trading")

    PairsOUStrategy.run(
        redis_url=os.environ["ASCENT_REDIS_URL"],
        database_url=db_url,
    )
