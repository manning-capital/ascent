"""Seed trades, trade conditions/snapshots, and orders."""

from __future__ import annotations

import datetime
import random
import uuid
from typing import Any


def seed_trades(client: Any, ctx: dict) -> None:
    print("Creating trades...")

    now = ctx["now"]
    strategy_objs = ctx["strategy_objs"]
    strategy_pairs = ctx["strategy_pairs"]
    asset_by_symbol = ctx["asset_by_symbol"]
    pair_to_instrument = ctx["pair_to_instrument"]
    status_map = ctx["status_map"]
    order_type_by_name = ctx["order_type_by_name"]
    order_status_map = ctx["order_status_map"]
    kraken_id = ctx["kraken_id"]

    ref_prices = {
        "BTC": 67500,
        "ETH": 3400,
        "SOL": 145,
        "ADA": 0.45,
        "XRP": 0.52,
        "DOGE": 0.12,
        "AVAX": 35,
        "LINK": 14,
        "UNI": 7.80,
        "AAPL": 182,
        "MSFT": 390,
        "NVDA": 880,
        "XAU": 2350,
        "XAG": 28.50,
        "WTI": 78.50,
        "BRENT": 82.30,
    }

    portfolio_provider_map = {
        ctx["portfolio_main"]["id"]: str(kraken_id),
        ctx["portfolio_paper"]["id"]: str(kraken_id),
        ctx["portfolio_coinbase"]["id"]: str(ctx["coinbase_id"]),
        ctx["portfolio_equity"]["id"]: str(ctx["ib_id"]),
        ctx["portfolio_commodity"]["id"]: str(ctx["ib_id"]),
    }
    portfolio_exchange_map = {
        ctx["portfolio_main"]["id"]: ctx["kraken_exchange"]["id"],
        ctx["portfolio_paper"]["id"]: ctx["kraken_exchange"]["id"],
        ctx["portfolio_coinbase"]["id"]: ctx["coinbase_exchange"]["id"],
        ctx["portfolio_equity"]["id"]: ctx["ib_equity_exchange"]["id"],
        ctx["portfolio_commodity"]["id"]: ctx["ib_futures_exchange"]["id"],
    }

    all_trades: list[dict] = []
    for strat_idx, strat in enumerate(strategy_objs):
        pairs = strategy_pairs.get(strat_idx, [("BTC", "USD")])
        is_pairs = len(pairs) > 1
        num_trades = random.randint(8, 20)

        for t in range(num_trades):
            days_ago = random.randint(1, 90)
            entry_at = now - datetime.timedelta(days=days_ago, hours=random.randint(0, 23))

            status_roll = random.random()
            if status_roll < 0.3:
                trade_status = status_map["OPEN"]
                exit_at = None
                close_reason = None
            elif status_roll < 0.95:
                trade_status = status_map["CLOSED"]
                hold_hours = random.randint(1, 72)
                exit_at = entry_at + datetime.timedelta(hours=hold_hours)
                close_reason = random.choice(["MODEL_SIGNAL", "STOP_LOSS", "TAKE_PROFIT", "MANUAL"])
            else:
                trade_status = status_map["CANCELLED"]
                exit_at = None
                close_reason = "MANUAL"

            is_paper = strat.get("portfolio_id") == ctx["portfolio_paper"].get("id")
            trade_provider_id = portfolio_provider_map.get(
                strat.get("portfolio_id", ctx["portfolio_main"]["id"]), str(kraken_id)
            )

            legs = []
            total_pnl = 0.0
            for pair_idx, (from_sym, to_sym) in enumerate(pairs):
                base_price = ref_prices.get(from_sym, 100)
                entry_price = round(base_price + base_price * random.uniform(-0.05, 0.05), 2)
                direction = (
                    random.choice(["LONG", "SHORT"])
                    if not is_pairs
                    else ("LONG" if pair_idx == 0 else "SHORT")
                )
                quantity = round(random.uniform(0.01, 10.0), 4)

                exit_price = None
                realized_pnl = None
                if trade_status["name"] == "CLOSED":
                    pnl_pct = random.uniform(-0.08, 0.12)
                    if direction == "LONG":
                        exit_price = round(entry_price * (1 + pnl_pct), 2)
                        realized_pnl = round((exit_price - entry_price) * quantity, 2)
                    else:
                        exit_price = round(entry_price * (1 - pnl_pct), 2)
                        realized_pnl = round((entry_price - exit_price) * quantity, 2)
                    total_pnl += realized_pnl

                expected_entry = round(entry_price * random.uniform(0.998, 1.002), 2)
                expected_exit = (
                    round(exit_price * random.uniform(0.998, 1.002), 2) if exit_price else None
                )

                leg_key = (
                    trade_provider_id,
                    asset_by_symbol[from_sym]["id"],
                    asset_by_symbol[to_sym]["id"],
                )
                leg_instrument_id = pair_to_instrument.get(leg_key)

                legs.append(
                    {
                        "instrument_id": uuid.UUID(leg_instrument_id)
                        if leg_instrument_id
                        else None,
                        "direction": direction,
                        "quantity": quantity,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "expected_entry_price": expected_entry,
                        "expected_exit_price": expected_exit,
                    }
                )

            trade = client.create_trade(
                strategy_id=uuid.UUID(strat["id"]),
                portfolio_id=uuid.UUID(strat.get("portfolio_id", ctx["portfolio_main"]["id"])),
                is_paper=is_paper,
                entry_at=entry_at,
                parameters={"seed_trade": True, "trade_index": t},
                legs=legs,
            )

            update_kwargs: dict[str, Any] = {"total_fees": round(random.uniform(0.5, 25.0), 2)}
            if trade_status["name"] == "CLOSED":
                update_kwargs["total_realized_pnl"] = round(total_pnl, 2)
                update_kwargs["exit_at"] = exit_at
                update_kwargs["close_reason"] = close_reason
            if trade_status["name"] == "OPEN":
                update_kwargs["total_unrealized_pnl"] = round(random.uniform(-500, 500), 2)
            if trade_status["name"] == "CANCELLED":
                update_kwargs["close_reason"] = close_reason
            client.update_trade(uuid.UUID(trade["id"]), **update_kwargs)

            # Trade statuses
            trade_id = uuid.UUID(trade["id"])
            pending_ts = entry_at - datetime.timedelta(minutes=random.randint(1, 10))
            client.add_trade_status(
                trade_id,
                trade_status_type_id=uuid.UUID(status_map["PENDING"]["id"]),
                timestamp=pending_ts,
            )

            if trade_status["name"] == "CANCELLED":
                client.add_trade_status(
                    trade_id,
                    trade_status_type_id=uuid.UUID(status_map["CANCELLED"]["id"]),
                    timestamp=entry_at + datetime.timedelta(minutes=30),
                )
            else:
                client.add_trade_status(
                    trade_id,
                    trade_status_type_id=uuid.UUID(status_map["OPENING"]["id"]),
                    timestamp=pending_ts + datetime.timedelta(seconds=5),
                )
                client.add_trade_status(
                    trade_id,
                    trade_status_type_id=uuid.UUID(status_map["OPEN"]["id"]),
                    timestamp=entry_at,
                )
                if trade_status["name"] == "CLOSED":
                    close_ts = exit_at or (entry_at + datetime.timedelta(minutes=30))
                    client.add_trade_status(
                        trade_id,
                        trade_status_type_id=uuid.UUID(status_map["CLOSING"]["id"]),
                        timestamp=close_ts - datetime.timedelta(seconds=5),
                    )
                    client.add_trade_status(
                        trade_id,
                        trade_status_type_id=uuid.UUID(status_map["CLOSED"]["id"]),
                        timestamp=close_ts,
                    )

            all_trades.append(trade)

    # -----------------------------------------------------------------
    # Trade conditions & snapshots
    # -----------------------------------------------------------------
    print("Creating trade conditions and snapshots...")

    attr_zscore = ctx["attr_zscore"]
    attr_close = ctx["attr_close"]
    ki = ctx["kraken_instruments"]
    ci = ctx["coinbase_instruments"]
    si = ctx["ib_stock_instruments"]
    commi = ctx["ib_commodity_instruments"]

    for trade in all_trades[:40]:
        trade_id = uuid.UUID(trade["id"])
        trade_entry_at = (
            datetime.datetime.fromisoformat(trade["entry_at"]) if trade.get("entry_at") else now
        )
        trade_exit_at = (
            datetime.datetime.fromisoformat(trade["exit_at"]) if trade.get("exit_at") else None
        )

        client.add_trade_condition(
            trade_id,
            condition_type="ENTRY",
            attribute_id=uuid.UUID(attr_zscore["id"]),
            operator=random.choice(["ABOVE", "BELOW", "CROSSES_ABOVE", "CROSSES_BELOW"]),
            threshold_value=round(random.uniform(1.5, 3.0), 2),
            is_met=True,
            met_at=trade_entry_at,
        )

        strat_idx = next(
            (i for i, s in enumerate(strategy_objs) if s["id"] == trade.get("strategy_id")), 0
        )
        first_pair = strategy_pairs.get(strat_idx, [("BTC", "USD")])
        first_sym = first_pair[0][0]
        ds_inst = (
            ki.get(first_sym) or ci.get(first_sym) or si.get(first_sym) or commi.get(first_sym)
        )
        if ds_inst:
            client.add_trade_data_series(
                trade_id,
                attribute_id=uuid.UUID(attr_close["id"]),
                label="Close Price",
                data_source="INSTRUMENT_ATTRIBUTE",
                instrument_id=uuid.UUID(ds_inst["id"]),
            )

        client.add_trade_snapshot(
            trade_id,
            attribute_id=uuid.UUID(attr_zscore["id"]),
            snapshot_type="ENTRY",
            attribute_value=round(random.uniform(-3.0, 3.0), 4),
            timestamp=trade_entry_at,
        )
        if trade_exit_at:
            client.add_trade_snapshot(
                trade_id,
                attribute_id=uuid.UUID(attr_zscore["id"]),
                snapshot_type="EXIT",
                attribute_value=round(random.uniform(-1.0, 1.0), 4),
                timestamp=trade_exit_at,
            )

    # -----------------------------------------------------------------
    # Orders
    # -----------------------------------------------------------------
    print("Creating orders...")

    for trade in all_trades[:60]:
        trade_entry_at = (
            datetime.datetime.fromisoformat(trade["entry_at"]) if trade.get("entry_at") else now
        )
        trade_exit_at = (
            datetime.datetime.fromisoformat(trade["exit_at"]) if trade.get("exit_at") else None
        )

        strat_idx = next(
            (i for i, s in enumerate(strategy_objs) if s["id"] == trade.get("strategy_id")), 0
        )
        pairs = strategy_pairs.get(strat_idx, [("BTC", "USD")])
        trade_exchange_id = portfolio_exchange_map.get(
            trade.get("portfolio_id"), ctx["kraken_exchange"]["id"]
        )
        order_provider_id = portfolio_provider_map.get(
            trade.get("portfolio_id", ctx["portfolio_main"]["id"]), str(kraken_id)
        )

        for pair_idx, (from_sym, to_sym) in enumerate(pairs):
            base_price = ref_prices.get(from_sym, 100)
            entry_price = round(base_price + base_price * random.uniform(-0.05, 0.05), 2)
            is_pairs_trade = len(pairs) > 1
            direction = (
                random.choice(["LONG", "SHORT"])
                if not is_pairs_trade
                else ("LONG" if pair_idx == 0 else "SHORT")
            )
            quantity = round(random.uniform(0.01, 10.0), 4)

            order_key = (
                order_provider_id,
                asset_by_symbol[from_sym]["id"],
                asset_by_symbol[to_sym]["id"],
            )
            order_instrument_id = pair_to_instrument.get(order_key)

            entry_order = client.create_order(
                timestamp=trade_entry_at,
                order_type_id=uuid.UUID(order_type_by_name["MARKET"]["id"]),
                side="BUY" if direction == "LONG" else "SELL",
                exchange_id=uuid.UUID(trade_exchange_id),
                portfolio_id=uuid.UUID(trade.get("portfolio_id", ctx["portfolio_main"]["id"])),
                instrument_id=uuid.UUID(order_instrument_id) if order_instrument_id else None,
                quantity=quantity,
                price=entry_price,
                time_in_force="GTC",
            )
            eid = uuid.UUID(entry_order["id"])
            client.add_order_status(
                eid,
                order_status_type_id=uuid.UUID(order_status_map["SUBMITTED"]["id"]),
                timestamp=trade_entry_at,
            )
            client.add_order_status(
                eid,
                order_status_type_id=uuid.UUID(order_status_map["ACCEPTED"]["id"]),
                timestamp=trade_entry_at + datetime.timedelta(seconds=1),
            )
            client.add_order_status(
                eid,
                order_status_type_id=uuid.UUID(order_status_map["FILLED"]["id"]),
                timestamp=trade_entry_at + datetime.timedelta(seconds=2),
            )

            if trade_exit_at and trade.get("close_reason"):
                pnl_pct = random.uniform(-0.08, 0.12)
                exit_price = (
                    round(entry_price * (1 + pnl_pct), 2)
                    if direction == "LONG"
                    else round(entry_price * (1 - pnl_pct), 2)
                )
                exit_order = client.create_order(
                    timestamp=trade_exit_at,
                    order_type_id=uuid.UUID(order_type_by_name["MARKET"]["id"]),
                    side="SELL" if direction == "LONG" else "BUY",
                    exchange_id=uuid.UUID(trade_exchange_id),
                    portfolio_id=uuid.UUID(trade.get("portfolio_id", ctx["portfolio_main"]["id"])),
                    instrument_id=uuid.UUID(order_instrument_id) if order_instrument_id else None,
                    quantity=quantity,
                    price=exit_price,
                    time_in_force="GTC",
                )
                xid = uuid.UUID(exit_order["id"])
                client.add_order_status(
                    xid,
                    order_status_type_id=uuid.UUID(order_status_map["SUBMITTED"]["id"]),
                    timestamp=trade_exit_at,
                )
                client.add_order_status(
                    xid,
                    order_status_type_id=uuid.UUID(order_status_map["ACCEPTED"]["id"]),
                    timestamp=trade_exit_at + datetime.timedelta(seconds=1),
                )
                client.add_order_status(
                    xid,
                    order_status_type_id=uuid.UUID(order_status_map["FILLED"]["id"]),
                    timestamp=trade_exit_at + datetime.timedelta(seconds=2),
                )

    ctx["all_trades"] = all_trades
