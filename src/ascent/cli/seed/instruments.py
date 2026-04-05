"""Seed instruments and instrument metadata."""

from __future__ import annotations

import datetime
import random
import uuid
from typing import Any

from ascent.cli.seed.assets import ETF_DEFS, GOVT_BOND_DEFS, STOCK_DEFS


def _ts(now: datetime.datetime, days_ago: int) -> datetime.datetime:
    return now.replace(microsecond=0) - datetime.timedelta(days=days_ago)


def seed_instruments(client: Any, ctx: dict) -> None:
    print("Creating instruments...")
    random.seed(42)

    now = ctx["now"]
    meta = ctx["meta"]
    asset_by_symbol = ctx["asset_by_symbol"]
    usd = asset_by_symbol["USD"]
    kraken_id = ctx["kraken_id"]
    coinbase_id = ctx["coinbase_id"]
    ib_id = ctx["ib_id"]

    # --- Kraken crypto spot ---
    kraken_instruments: dict[str, dict] = {}
    for sym in ctx["all_crypto_symbols"]:
        asset = asset_by_symbol[sym]
        inst = client.create_instrument(
            name=f"KRAKEN_{sym}_USD",
            display_name=f"Kraken {asset['display_name']}/USD",
            instrument_type_id=uuid.UUID(ctx["spot_itype"]["id"]),
            provider_id=kraken_id,
            from_asset_id=uuid.UUID(asset["id"]),
            to_asset_id=uuid.UUID(usd["id"]),
        )
        kraken_instruments[sym] = inst

    # --- Coinbase crypto spot ---
    coinbase_instruments: dict[str, dict] = {}
    for sym in ctx["coinbase_crypto_symbols"]:
        asset = asset_by_symbol[sym]
        inst = client.create_instrument(
            name=f"COINBASE_{sym}_USD",
            display_name=f"Coinbase {asset['display_name']}/USD",
            instrument_type_id=uuid.UUID(ctx["spot_itype"]["id"]),
            provider_id=coinbase_id,
            from_asset_id=uuid.UUID(asset["id"]),
            to_asset_id=uuid.UUID(usd["id"]),
        )
        coinbase_instruments[sym] = inst

    # --- IB stock spot ---
    ib_stock_instruments: dict[str, dict] = {}
    for _, sym in STOCK_DEFS:
        asset = asset_by_symbol[sym]
        inst = client.create_instrument(
            name=f"IB_{sym}_USD",
            display_name=f"IB {asset['display_name']}",
            instrument_type_id=uuid.UUID(ctx["spot_itype"]["id"]),
            provider_id=ib_id,
            from_asset_id=uuid.UUID(asset["id"]),
            to_asset_id=uuid.UUID(usd["id"]),
        )
        ib_stock_instruments[sym] = inst

    # --- IB ETF ---
    ib_etf_instruments: dict[str, dict] = {}
    for _, sym in ETF_DEFS:
        asset = asset_by_symbol[sym]
        inst = client.create_instrument(
            name=f"IB_{sym}_USD",
            display_name=f"IB {asset['display_name']}",
            instrument_type_id=uuid.UUID(ctx["spot_itype"]["id"]),
            provider_id=ib_id,
            from_asset_id=uuid.UUID(asset["id"]),
            to_asset_id=uuid.UUID(usd["id"]),
        )
        ib_etf_instruments[sym] = inst

    # --- IB commodity futures ---
    ib_commodity_instruments: dict[str, dict] = {}
    for sym in ["XAU", "XAG", "WTI", "BRENT", "NATGAS"]:
        asset = asset_by_symbol[sym]
        inst = client.create_instrument(
            name=f"IB_{sym}_USD",
            display_name=f"IB {asset['display_name']} Future",
            instrument_type_id=uuid.UUID(ctx["future_itype"]["id"]),
            provider_id=ib_id,
            from_asset_id=uuid.UUID(asset["id"]),
            to_asset_id=uuid.UUID(usd["id"]),
        )
        ib_commodity_instruments[sym] = inst

    # --- IB bond futures ---
    ib_bond_instruments: dict[str, dict] = {}
    for _, sym in GOVT_BOND_DEFS:
        asset = asset_by_symbol[sym]
        inst = client.create_instrument(
            name=f"IB_{sym}",
            display_name=f"IB {asset['display_name']}",
            instrument_type_id=uuid.UUID(ctx["future_itype"]["id"]),
            provider_id=ib_id,
            from_asset_id=uuid.UUID(asset["id"]),
            to_asset_id=uuid.UUID(usd["id"]),
        )
        ib_bond_instruments[sym] = inst

    # --- Option instruments (IB) ---
    # Demonstrates the reference metadata type (UNDERLYING_INSTRUMENT).
    # DB enforces unique (provider_id, from_asset_id, to_asset_id), so we can only
    # create one option per underlying asset per provider.  We use assets that
    # don't already have IB spot instruments (crypto assets).
    option_instruments: dict[str, dict] = {}
    option_defs_raw = [
        ("BTC", "Call", 70000.0, 90),
        ("ETH", "Put", 3000.0, 60),
        ("SOL", "Call", 200.0, 30),
        ("ADA", "Put", 0.30, 90),
        ("XRP", "Call", 0.80, 60),
        ("AVAX", "Put", 25.0, 30),
    ]
    option_defs = []
    for underlying_sym, opt_type, strike, expiry_days in option_defs_raw:
        expiry_dt = now + datetime.timedelta(days=expiry_days)
        date_str = expiry_dt.strftime("%y%m%d")
        strike_label = f"{int(strike / 1000)}K" if strike >= 1000 else str(int(strike))
        opt_name = f"{underlying_sym}_{date_str}_{strike_label}_{opt_type[0]}"
        opt_display = (
            f"IB {underlying_sym} {expiry_dt.strftime('%d%b%y').upper()} ${strike_label} {opt_type}"
        )
        option_defs.append((opt_name, opt_display, underlying_sym, opt_type, strike, expiry_days))

    for opt_name, opt_display, underlying_sym, _opt_type, _strike, _expiry_days in option_defs:
        underlying_asset = asset_by_symbol[underlying_sym]
        inst = client.create_instrument(
            name=f"IB_{opt_name}",
            display_name=opt_display,
            instrument_type_id=uuid.UUID(ctx["option_itype"]["id"]),
            provider_id=ib_id,
            from_asset_id=uuid.UUID(underlying_asset["id"]),
            to_asset_id=uuid.UUID(usd["id"]),
        )
        option_instruments[opt_name] = inst

    all_instruments = (
        list(kraken_instruments.values())
        + list(coinbase_instruments.values())
        + list(ib_stock_instruments.values())
        + list(ib_etf_instruments.values())
        + list(ib_commodity_instruments.values())
        + list(ib_bond_instruments.values())
        + list(option_instruments.values())
    )

    pair_to_instrument: dict[tuple, str] = {}
    for inst in all_instruments:
        key = (inst["provider_id"], inst["from_asset_id"], inst["to_asset_id"])
        pair_to_instrument[key] = inst["id"]

    # -----------------------------------------------------------------
    # Instrument metadata
    # -----------------------------------------------------------------
    print("Creating instrument metadata history...")

    # Kraken crypto spot
    for inst in kraken_instruments.values():
        inst_id = uuid.UUID(inst["id"])
        tick = round(random.uniform(0.01, 0.5), 2)
        lot = round(random.uniform(0.0001, 0.01), 4)
        client.batch_create_instrument_metadata(
            inst_id,
            _ts(now, 90).isoformat(),
            [
                {"metadata_id": uuid.UUID(meta["TICK_SIZE"]["id"]), "value": tick * 2},
                {"metadata_id": uuid.UUID(meta["LOT_SIZE"]["id"]), "value": lot * 2},
            ],
        )
        client.batch_create_instrument_metadata(
            inst_id,
            _ts(now, 30).isoformat(),
            [
                {"metadata_id": uuid.UUID(meta["TICK_SIZE"]["id"]), "value": tick},
                {"metadata_id": uuid.UUID(meta["LOT_SIZE"]["id"]), "value": lot},
            ],
        )
        client.batch_create_instrument_metadata(
            inst_id,
            _ts(now, 0).isoformat(),
            [
                {"metadata_id": uuid.UUID(meta["TICK_SIZE"]["id"]), "value": tick},
                {"metadata_id": uuid.UUID(meta["LOT_SIZE"]["id"]), "value": lot},
                {"metadata_id": uuid.UUID(meta["CONTRACT_SIZE"]["id"]), "value": 1.0},
                {"metadata_id": uuid.UUID(meta["TRADING_HOURS"]["id"]), "value": "24/7"},
            ],
        )

    # Coinbase crypto spot
    for inst in coinbase_instruments.values():
        inst_id = uuid.UUID(inst["id"])
        tick = round(random.uniform(0.01, 0.5), 2)
        lot = round(random.uniform(0.0001, 0.01), 4)
        client.batch_create_instrument_metadata(
            inst_id,
            _ts(now, 60).isoformat(),
            [
                {"metadata_id": uuid.UUID(meta["TICK_SIZE"]["id"]), "value": tick},
                {"metadata_id": uuid.UUID(meta["LOT_SIZE"]["id"]), "value": lot},
            ],
        )
        client.batch_create_instrument_metadata(
            inst_id,
            _ts(now, 0).isoformat(),
            [
                {"metadata_id": uuid.UUID(meta["TICK_SIZE"]["id"]), "value": tick},
                {"metadata_id": uuid.UUID(meta["LOT_SIZE"]["id"]), "value": lot},
                {"metadata_id": uuid.UUID(meta["CONTRACT_SIZE"]["id"]), "value": 1.0},
                {"metadata_id": uuid.UUID(meta["TRADING_HOURS"]["id"]), "value": "24/7"},
            ],
        )

    # IB stock + ETF
    for instruments in (ib_stock_instruments, ib_etf_instruments):
        for inst in instruments.values():
            client.batch_create_instrument_metadata(
                uuid.UUID(inst["id"]),
                _ts(now, 90).isoformat(),
                [
                    {"metadata_id": uuid.UUID(meta["TICK_SIZE"]["id"]), "value": 0.01},
                    {"metadata_id": uuid.UUID(meta["LOT_SIZE"]["id"]), "value": 1.0},
                    {"metadata_id": uuid.UUID(meta["CONTRACT_SIZE"]["id"]), "value": 1.0},
                    {
                        "metadata_id": uuid.UUID(meta["TRADING_HOURS"]["id"]),
                        "value": "09:30-16:00 ET",
                    },
                ],
            )

    # IB commodity futures
    commodity_contract_sizes = {
        "XAU": 100,
        "XAG": 5000,
        "WTI": 1000,
        "BRENT": 1000,
        "NATGAS": 10000,
    }
    for sym, inst in ib_commodity_instruments.items():
        cs = commodity_contract_sizes.get(sym, 100)
        client.batch_create_instrument_metadata(
            uuid.UUID(inst["id"]),
            _ts(now, 90).isoformat(),
            [
                {"metadata_id": uuid.UUID(meta["TICK_SIZE"]["id"]), "value": 0.01},
                {"metadata_id": uuid.UUID(meta["LOT_SIZE"]["id"]), "value": 1.0},
                {"metadata_id": uuid.UUID(meta["CONTRACT_SIZE"]["id"]), "value": float(cs)},
                {
                    "metadata_id": uuid.UUID(meta["MARGIN_REQUIREMENT"]["id"]),
                    "value": round(random.uniform(5.0, 15.0), 1),
                },
                {
                    "metadata_id": uuid.UUID(meta["TRADING_HOURS"]["id"]),
                    "value": "18:00-17:00 ET (Sun-Fri)",
                },
            ],
        )

    # IB bond futures
    for inst in ib_bond_instruments.values():
        client.batch_create_instrument_metadata(
            uuid.UUID(inst["id"]),
            _ts(now, 90).isoformat(),
            [
                {"metadata_id": uuid.UUID(meta["TICK_SIZE"]["id"]), "value": 0.015625},
                {"metadata_id": uuid.UUID(meta["LOT_SIZE"]["id"]), "value": 1.0},
                {"metadata_id": uuid.UUID(meta["CONTRACT_SIZE"]["id"]), "value": 100000.0},
                {
                    "metadata_id": uuid.UUID(meta["MARGIN_REQUIREMENT"]["id"]),
                    "value": round(random.uniform(2.0, 5.0), 1),
                },
                {
                    "metadata_id": uuid.UUID(meta["TRADING_HOURS"]["id"]),
                    "value": "18:00-17:00 ET (Sun-Fri)",
                },
            ],
        )

    # Option instruments (IB) — demonstrate enum + reference metadata
    for opt_name, _opt_display, underlying_sym, opt_type, strike, expiry_days in option_defs:
        inst = option_instruments[opt_name]
        inst_id = uuid.UUID(inst["id"])
        underlying_spot = kraken_instruments.get(underlying_sym)
        expiry_date = (now + datetime.timedelta(days=expiry_days)).strftime("%Y-%m-%d")

        entries = [
            {"metadata_id": uuid.UUID(meta["TICK_SIZE"]["id"]), "value": 0.01},
            {"metadata_id": uuid.UUID(meta["LOT_SIZE"]["id"]), "value": 0.1},
            {"metadata_id": uuid.UUID(meta["CONTRACT_SIZE"]["id"]), "value": 1.0},
            {"metadata_id": uuid.UUID(meta["TRADING_HOURS"]["id"]), "value": "24/7"},
            # Option-specific fields (enum + date + float + reference)
            {"metadata_id": uuid.UUID(meta["OPTION_TYPE"]["id"]), "value": opt_type},
            {"metadata_id": uuid.UUID(meta["STRIKE_PRICE"]["id"]), "value": strike},
            {"metadata_id": uuid.UUID(meta["EXPIRY_DATE"]["id"]), "value": expiry_date},
        ]
        # UNDERLYING_INSTRUMENT: reference to the spot instrument UUID
        if underlying_spot:
            entries.append(
                {
                    "metadata_id": uuid.UUID(meta["UNDERLYING_INSTRUMENT"]["id"]),
                    "value": underlying_spot["id"],
                }
            )
        client.batch_create_instrument_metadata(inst_id, _ts(now, 0).isoformat(), entries)

    # Store in context
    ctx["kraken_instruments"] = kraken_instruments
    ctx["coinbase_instruments"] = coinbase_instruments
    ctx["ib_stock_instruments"] = ib_stock_instruments
    ctx["ib_etf_instruments"] = ib_etf_instruments
    ctx["ib_commodity_instruments"] = ib_commodity_instruments
    ctx["ib_bond_instruments"] = ib_bond_instruments
    ctx["option_instruments"] = option_instruments
    ctx["all_instruments"] = all_instruments
    ctx["pair_to_instrument"] = pair_to_instrument
