from __future__ import annotations

import os
import uuid

import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from ascent.strategies.base import Strategy


class MomentumStrategy(Strategy):
    """Momentum strategy that opens trades on price moves and closes on P&L targets."""

    class Parameters(BaseModel):
        entry_threshold_pct: float = Field(0.1, description="Min % move to open a trade")
        take_profit_pct: float = Field(0.3, description="% gain to take profit")
        stop_loss_pct: float = Field(0.2, description="% loss to stop out")
        trade_qty: float = Field(0.01, description="Quantity per trade")

    feeds = ["MARKET_DATA_FEED"]
    exchanges = ["KRAKEN_SECURITY_EXCHANGE"]
    portfolio = "MAIN"

    _prev_prices: dict[uuid.UUID, float] = {}

    def evaluate(self, ctx: pd.DataFrame) -> None:
        log = self.get_logger()

        if ctx.empty:
            return

        # --- Phase 1: Check open trades for take-profit / stop-loss ---
        open_trades = ctx[ctx[("trade", "status")] == "OPEN"]
        for _inst_id, row in open_trades.iterrows():
            entry_price = row[("trade", "entry_price")]
            direction = row[("trade", "direction")]
            current_price = row[("market_data_feed", "close")]

            if entry_price is None or pd.isna(entry_price) or pd.isna(current_price):
                continue

            if direction == "LONG":
                pnl_pct = (current_price - entry_price) / entry_price * 100
            else:
                pnl_pct = (entry_price - current_price) / entry_price * 100

            if pnl_pct >= self.parameters.take_profit_pct:
                log.info(
                    "TAKE PROFIT  trade=%s  %s pnl=%+.3f%%",
                    str(row[("trade", "trade_id")])[:8],
                    direction,
                    pnl_pct,
                )
                result = self.close_trade(row[("trade", "trade_id")], close_reason="TAKE_PROFIT")
                log.info("  status=%s", result.state.value)
            elif pnl_pct <= -self.parameters.stop_loss_pct:
                log.info(
                    "STOP LOSS  trade=%s  %s pnl=%+.3f%%",
                    str(row[("trade", "trade_id")])[:8],
                    direction,
                    pnl_pct,
                )
                result = self.close_trade(row[("trade", "trade_id")], close_reason="STOP_LOSS")
                log.info("  status=%s", result.state.value)

        # --- Phase 2: Open new trades on momentum signals ---
        waiting = ctx[ctx[("trade", "status")] == "WAITING"]
        if waiting.empty:
            return

        for inst_id, row in waiting.iterrows():
            price = row[("market_data_feed", "close")]
            if pd.isna(price):
                continue

            prev = self._prev_prices.get(inst_id)
            self._prev_prices[inst_id] = price

            if prev is None:
                continue

            pct_change = (price - prev) / prev * 100

            if pct_change >= self.parameters.entry_threshold_pct:
                log.info("%s  %+.3f%%  → LONG @ %.4f", str(inst_id)[:8], pct_change, price)
                result = self.open_trade(inst_id, "LONG", self.parameters.trade_qty, price=price)
                log.info("  Trade %s  status=%s", str(result.trade_id)[:8], result.state.value)
            elif pct_change <= -self.parameters.entry_threshold_pct:
                log.info("%s  %+.3f%%  → SHORT @ %.4f", str(inst_id)[:8], pct_change, price)
                result = self.open_trade(inst_id, "SHORT", self.parameters.trade_qty, price=price)
                log.info("  Trade %s  status=%s", str(result.trade_id)[:8], result.state.value)


if __name__ == "__main__":
    load_dotenv()
    MomentumStrategy.run(
        redis_url=os.environ["ASCENT_REDIS_URL"],
        database_url=os.environ["ASCENT_DATABASE_URL"],
    )
