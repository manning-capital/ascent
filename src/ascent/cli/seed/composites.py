"""Seed composites (spreads, baskets, indices, ratios) and composite metadata."""

from __future__ import annotations

import datetime
import random
import uuid
from typing import Any


def _ts(now: datetime.datetime, days_ago: int) -> datetime.datetime:
    return now.replace(microsecond=0) - datetime.timedelta(days=days_ago)


def seed_composites(client: Any, ctx: dict) -> None:
    now = ctx["now"]
    meta = ctx["meta"]
    ki = ctx["kraken_instruments"]
    ci = ctx["coinbase_instruments"]
    si = ctx["ib_stock_instruments"]
    commi = ctx["ib_commodity_instruments"]
    bi = ctx["ib_bond_instruments"]

    def _members(inst_map, syms):
        return [
            {"instrument_id": uuid.UUID(inst_map[s]["id"]), "order": i + 1}
            for i, s in enumerate(syms)
        ]

    # --- Kraken Spreads ---
    kraken_composites = []
    for syms in [
        ["BTC", "ETH"],
        ["SOL", "AVAX"],
        ["LINK", "DOT"],
        ["ADA", "XRP"],
        ["UNI", "AAVE"],
        ["MATIC", "ARB"],
        ["ATOM", "NEAR"],
        ["INJ", "SUI"],
    ]:
        comp = client.create_composite(
            name=f"KRAKEN_{'_'.join(syms)}_SPREAD",
            display_name=f"Kraken {'-'.join(syms)} Spread",
            composite_type_id=uuid.UUID(ctx["spread_ctype"]["id"]),
            members=_members(ki, syms),
        )
        kraken_composites.append(comp)

    # --- Coinbase Spreads ---
    coinbase_composites = []
    for syms in [["BTC", "ETH"], ["SOL", "AVAX"], ["LINK", "DOT"], ["UNI", "AAVE"]]:
        comp = client.create_composite(
            name=f"COINBASE_{'_'.join(syms)}_SPREAD",
            display_name=f"Coinbase {'-'.join(syms)} Spread",
            composite_type_id=uuid.UUID(ctx["spread_ctype"]["id"]),
            members=_members(ci, syms),
        )
        coinbase_composites.append(comp)

    # --- Cross-exchange spreads ---
    cross_exchange_composites = []
    for sym in ["BTC", "ETH", "SOL"]:
        comp = client.create_composite(
            name=f"CROSS_{sym}_KRAKEN_COINBASE",
            display_name=f"Cross-Exchange {sym} (Kraken vs Coinbase)",
            composite_type_id=uuid.UUID(ctx["cross_exchange_ctype"]["id"]),
            members=[
                {"instrument_id": uuid.UUID(ki[sym]["id"]), "order": 1},
                {"instrument_id": uuid.UUID(ci[sym]["id"]), "order": 2},
            ],
        )
        cross_exchange_composites.append(comp)

    # --- Crypto baskets ---
    defi_basket = client.create_composite(
        name="KRAKEN_DEFI_BASKET",
        display_name="Kraken DeFi Basket",
        composite_type_id=uuid.UUID(ctx["basket_ctype"]["id"]),
        members=_members(ki, ["UNI", "AAVE", "MKR", "CRV", "LDO", "INJ"]),
    )
    l2_basket = client.create_composite(
        name="KRAKEN_L2_BASKET",
        display_name="Kraken Layer 2 Basket",
        composite_type_id=uuid.UUID(ctx["basket_ctype"]["id"]),
        members=_members(ki, ["MATIC", "ARB", "OP"]),
    )

    # --- Stock baskets ---
    tech_basket = client.create_composite(
        name="IB_TECH_BASKET",
        display_name="IB Tech Giants Basket",
        composite_type_id=uuid.UUID(ctx["basket_ctype"]["id"]),
        members=_members(si, ["AAPL", "GOOGL", "MSFT", "AMZN", "NVDA", "META"]),
    )

    # --- Stock spreads ---
    stock_composites = []
    for syms in [["AAPL", "MSFT"], ["NVDA", "META"]]:
        comp = client.create_composite(
            name=f"IB_{'_'.join(syms)}_SPREAD",
            display_name=f"IB {'-'.join(syms)} Spread",
            composite_type_id=uuid.UUID(ctx["spread_ctype"]["id"]),
            members=_members(si, syms),
        )
        stock_composites.append(comp)

    # --- Commodity ratios & spreads ---
    gold_silver_ratio = client.create_composite(
        name="IB_GOLD_SILVER_RATIO",
        display_name="Gold/Silver Ratio",
        composite_type_id=uuid.UUID(ctx["ratio_ctype"]["id"]),
        members=[
            {"instrument_id": uuid.UUID(commi["XAU"]["id"]), "order": 1},
            {"instrument_id": uuid.UUID(commi["XAG"]["id"]), "order": 2},
        ],
    )
    wti_brent_spread = client.create_composite(
        name="IB_WTI_BRENT_SPREAD",
        display_name="WTI-Brent Spread",
        composite_type_id=uuid.UUID(ctx["spread_ctype"]["id"]),
        members=[
            {"instrument_id": uuid.UUID(commi["WTI"]["id"]), "order": 1},
            {"instrument_id": uuid.UUID(commi["BRENT"]["id"]), "order": 2},
        ],
    )

    # --- Bond spread ---
    yield_curve_spread = client.create_composite(
        name="IB_US_2Y_10Y_SPREAD",
        display_name="US 2Y-10Y Yield Curve Spread",
        composite_type_id=uuid.UUID(ctx["spread_ctype"]["id"]),
        members=[
            {"instrument_id": uuid.UUID(bi["US_2Y"]["id"]), "order": 1},
            {"instrument_id": uuid.UUID(bi["US_10Y"]["id"]), "order": 2},
        ],
    )

    # --- Crypto index ---
    crypto_index = client.create_composite(
        name="KRAKEN_CRYPTO_TOP8_INDEX",
        display_name="Kraken Crypto Top 8 Index",
        composite_type_id=uuid.UUID(ctx["index_ctype"]["id"]),
        members=_members(ki, ["BTC", "ETH", "SOL", "ADA", "XRP", "AVAX", "LINK", "DOT"]),
    )

    all_composites = (
        kraken_composites
        + coinbase_composites
        + cross_exchange_composites
        + [defi_basket, l2_basket, tech_basket]
        + stock_composites
        + [gold_silver_ratio, wti_brent_spread, yield_curve_spread, crypto_index]
    )

    # -----------------------------------------------------------------
    # Composite metadata
    # -----------------------------------------------------------------

    # Spread composites
    for comp in kraken_composites + coinbase_composites + stock_composites:
        comp_id = uuid.UUID(comp["id"])
        corr = round(random.uniform(0.6, 0.95), 3)
        half_life = round(random.uniform(5, 30), 1)
        pval = round(random.uniform(0.001, 0.05), 4)
        client.batch_create_composite_metadata(
            comp_id,
            _ts(now, 60).isoformat(),
            [
                {"metadata_id": uuid.UUID(meta["CORRELATION"]["id"]), "value": corr - 0.05},
                {"metadata_id": uuid.UUID(meta["HALF_LIFE"]["id"]), "value": half_life + 3},
            ],
        )
        client.batch_create_composite_metadata(
            comp_id,
            _ts(now, 30).isoformat(),
            [
                {"metadata_id": uuid.UUID(meta["CORRELATION"]["id"]), "value": corr},
                {"metadata_id": uuid.UUID(meta["HALF_LIFE"]["id"]), "value": half_life},
                {"metadata_id": uuid.UUID(meta["COINTEGRATION_PVALUE"]["id"]), "value": pval},
            ],
        )
        client.batch_create_composite_metadata(
            comp_id,
            _ts(now, 0).isoformat(),
            [
                {"metadata_id": uuid.UUID(meta["CORRELATION"]["id"]), "value": corr + 0.01},
                {"metadata_id": uuid.UUID(meta["HALF_LIFE"]["id"]), "value": half_life - 1},
                {"metadata_id": uuid.UUID(meta["COINTEGRATION_PVALUE"]["id"]), "value": pval * 0.9},
            ],
        )

    # Cross-exchange composites
    for comp in cross_exchange_composites:
        corr = round(random.uniform(0.97, 0.999), 4)
        client.batch_create_composite_metadata(
            uuid.UUID(comp["id"]),
            _ts(now, 30).isoformat(),
            [
                {"metadata_id": uuid.UUID(meta["CORRELATION"]["id"]), "value": corr},
            ],
        )

    # Baskets and index
    for comp in [defi_basket, l2_basket, tech_basket, crypto_index]:
        corr = round(random.uniform(0.5, 0.85), 3)
        client.batch_create_composite_metadata(
            uuid.UUID(comp["id"]),
            _ts(now, 30).isoformat(),
            [
                {"metadata_id": uuid.UUID(meta["CORRELATION"]["id"]), "value": corr},
            ],
        )

    # Ratios and other spreads
    for comp in [gold_silver_ratio, wti_brent_spread, yield_curve_spread]:
        corr = round(random.uniform(0.7, 0.95), 3)
        half_life = round(random.uniform(10, 60), 1)
        client.batch_create_composite_metadata(
            uuid.UUID(comp["id"]),
            _ts(now, 30).isoformat(),
            [
                {"metadata_id": uuid.UUID(meta["CORRELATION"]["id"]), "value": corr},
                {"metadata_id": uuid.UUID(meta["HALF_LIFE"]["id"]), "value": half_life},
            ],
        )

    # Store in context
    ctx["kraken_composites"] = kraken_composites
    ctx["coinbase_composites"] = coinbase_composites
    ctx["all_composites"] = all_composites
