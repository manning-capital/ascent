from __future__ import annotations

import os
import uuid

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from ascent.strategies.base import Strategy

ATTR_CLOSE = 1


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

    def evaluate(self) -> None:
        ctx = self.get_context()
        log = self.get_logger()
        data = ctx.get("MARKET_DATA_FEED")

        if data is None or data.empty:
            return

        # Build current price map from feed data
        closes = data[data["attribute_id"] == ATTR_CLOSE]
        current_prices: dict[uuid.UUID, float] = {}
        for _, row in closes.iterrows():
            inst_id = row["instrument_id"]
            if isinstance(inst_id, str):
                inst_id = uuid.UUID(inst_id)
            current_prices[inst_id] = float(row["attribute_value"])

        # --- Phase 1: Check open trades for take-profit / stop-loss ---
        open_trades = self.get_open_trades()
        for trade in open_trades:
            for leg in trade["legs"]:
                inst_id = uuid.UUID(leg["instrument_id"])
                entry_price = leg["entry_price"]
                if entry_price is None or inst_id not in current_prices:
                    continue

                price = current_prices[inst_id]
                if leg["direction"] == "LONG":
                    pnl_pct = (price - entry_price) / entry_price * 100
                else:
                    pnl_pct = (entry_price - price) / entry_price * 100

                if pnl_pct >= self.parameters.take_profit_pct:
                    log.info(
                        "TAKE PROFIT  trade=%s  %s pnl=%+.3f%%",
                        trade["trade_id"][:8],
                        leg["direction"],
                        pnl_pct,
                    )
                    result = self.close_trade(trade["trade_id"], close_reason="TAKE_PROFIT")
                    log.info("  status=%s  pnl=%s", result["status"], result.get("total_pnl"))
                    break
                elif pnl_pct <= -self.parameters.stop_loss_pct:
                    log.info(
                        "STOP LOSS  trade=%s  %s pnl=%+.3f%%",
                        trade["trade_id"][:8],
                        leg["direction"],
                        pnl_pct,
                    )
                    result = self.close_trade(trade["trade_id"], close_reason="STOP_LOSS")
                    log.info("  status=%s  pnl=%s", result["status"], result.get("total_pnl"))
                    break

        # --- Phase 2: Open new trades on momentum signals ---
        for inst_id, price in current_prices.items():
            prev = self._prev_prices.get(inst_id)
            self._prev_prices[inst_id] = price

            if prev is None:
                continue

            pct_change = (price - prev) / prev * 100

            if pct_change >= self.parameters.entry_threshold_pct:
                log.info("%s  %+.3f%%  → LONG @ %.4f", str(inst_id)[:8], pct_change, price)
                result = self.open_trade(inst_id, "LONG", self.parameters.trade_qty, price=price)
                log.info("  Trade %s  status=%s", result["trade_id"][:8], result["status"])
            elif pct_change <= -self.parameters.entry_threshold_pct:
                log.info("%s  %+.3f%%  → SHORT @ %.4f", str(inst_id)[:8], pct_change, price)
                result = self.open_trade(inst_id, "SHORT", self.parameters.trade_qty, price=price)
                log.info("  Trade %s  status=%s", result["trade_id"][:8], result["status"])


if __name__ == "__main__":
    load_dotenv()
    MomentumStrategy.run(
        redis_url=os.environ["ASCENT_REDIS_URL"],
        database_url=os.environ["ASCENT_DATABASE_URL"],
    )
