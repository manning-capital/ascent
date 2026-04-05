"""Seed providers, exchanges, and provider/provider-asset metadata."""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from ascent.cli.seed.assets import (
    CRYPTO_DEFS,
    ENERGY_DEFS,
    ETF_DEFS,
    GOVT_BOND_DEFS,
    PRECIOUS_METAL_DEFS,
    STABLECOIN_DEFS,
    STOCK_DEFS,
)


def _ts(now: datetime.datetime, days_ago: int) -> datetime.datetime:
    return now.replace(microsecond=0) - datetime.timedelta(days=days_ago)


COINBASE_CRYPTO_SYMBOLS = [
    "BTC",
    "ETH",
    "SOL",
    "ADA",
    "XRP",
    "DOGE",
    "AVAX",
    "LINK",
    "DOT",
    "MATIC",
    "ATOM",
    "UNI",
    "ARB",
    "OP",
    "NEAR",
    "AAVE",
    "MKR",
    "SNX",
    "CRV",
    "LDO",
    "INJ",
    "SUI",
    "USDT",
    "USDC",
    "DAI",
]


def seed_providers(client: Any, ctx: dict) -> None:
    print("Creating providers and exchanges...")

    now = ctx["now"]
    meta = ctx["meta"]
    asset_by_symbol = ctx["asset_by_symbol"]

    crypto_symbols = [s for _, s in CRYPTO_DEFS]
    stablecoin_symbols = [s for _, s in STABLECOIN_DEFS]
    all_crypto_symbols = crypto_symbols + stablecoin_symbols

    # --- Providers ---
    kraken_provider = client.create_provider(
        provider_type_id=uuid.UUID(ctx["exchange_ptype"]["id"]),
        name="KRAKEN",
        display_name="Kraken",
        description="Kraken Cryptocurrency Exchange",
    )
    coinbase_provider = client.create_provider(
        provider_type_id=uuid.UUID(ctx["exchange_ptype"]["id"]),
        name="COINBASE",
        display_name="Coinbase",
        description="Coinbase Cryptocurrency Exchange",
    )
    ib_provider = client.create_provider(
        provider_type_id=uuid.UUID(ctx["exchange_ptype"]["id"]),
        name="INTERACTIVE_BROKERS",
        display_name="Interactive Brokers",
        description="Interactive Brokers multi-asset brokerage",
    )
    polygon_provider = client.create_provider(
        provider_type_id=uuid.UUID(ctx["data_vendor_ptype"]["id"]),
        name="POLYGON",
        display_name="Polygon.io",
        description="Financial market data API provider",
    )

    kraken_id = uuid.UUID(kraken_provider["id"])
    coinbase_id = uuid.UUID(coinbase_provider["id"])
    ib_id = uuid.UUID(ib_provider["id"])
    polygon_id = uuid.UUID(polygon_provider["id"])

    # --- Exchanges ---
    # Each exchange is tied to a specific provider + instrument type combination.
    # This means we implement a separate exchange class per provider per instrument type.
    kraken_exchange = client.create_exchange(
        exchange_type_id=uuid.UUID(ctx["spot_etype"]["id"]),
        instrument_type_id=uuid.UUID(ctx["spot_itype"]["id"]),
        name="KRAKEN_SPOT",
        display_name="Kraken Spot",
        description="Kraken spot exchange for crypto instruments",
        provider_id=kraken_id,
        implementation_class="ascent.exchanges.kraken.KrakenSpotExchange",
    )
    coinbase_exchange = client.create_exchange(
        exchange_type_id=uuid.UUID(ctx["spot_etype"]["id"]),
        instrument_type_id=uuid.UUID(ctx["spot_itype"]["id"]),
        name="COINBASE_SPOT",
        display_name="Coinbase Spot",
        description="Coinbase spot exchange for crypto instruments",
        provider_id=coinbase_id,
        implementation_class="ascent.exchanges.coinbase.CoinbaseSpotExchange",
    )
    ib_equity_exchange = client.create_exchange(
        exchange_type_id=uuid.UUID(ctx["spot_etype"]["id"]),
        instrument_type_id=uuid.UUID(ctx["spot_itype"]["id"]),
        name="IB_US_EQUITY",
        display_name="IB US Equity",
        description="Interactive Brokers US Equity routing for spot instruments",
        provider_id=ib_id,
    )
    ib_futures_exchange = client.create_exchange(
        exchange_type_id=uuid.UUID(ctx["futures_etype"]["id"]),
        instrument_type_id=uuid.UUID(ctx["future_itype"]["id"]),
        name="IB_US_FUTURES",
        display_name="IB US Futures",
        description="Interactive Brokers US Futures routing for future instruments",
        provider_id=ib_id,
    )
    client.create_exchange(
        exchange_type_id=uuid.UUID(ctx["paper_etype"]["id"]),
        name="PAPER_TRADING",
        display_name="Paper Trading",
        description="Simulated paper trading exchange",
        implementation_class="ascent.exchanges.paper.PaperExchange",
        config={"initial_balance": 100000},
    )

    # --- Provider metadata ---
    print("Creating provider metadata...")
    provider_meta_history = {
        kraken_id: [
            (90, {"API_KEY_NAME": "KRAKEN_API_KEY", "RATE_LIMIT": 30, "SUPPORTS_WEBSOCKET": True}),
            (60, {"API_KEY_NAME": "KRAKEN_API_KEY", "RATE_LIMIT": 45, "SUPPORTS_WEBSOCKET": True}),
            (30, {"API_KEY_NAME": "KRAKEN_API_KEY", "RATE_LIMIT": 60, "SUPPORTS_WEBSOCKET": True}),
        ],
        coinbase_id: [
            (
                90,
                {"API_KEY_NAME": "COINBASE_API_KEY", "RATE_LIMIT": 25, "SUPPORTS_WEBSOCKET": True},
            ),
            (
                60,
                {"API_KEY_NAME": "COINBASE_API_KEY", "RATE_LIMIT": 40, "SUPPORTS_WEBSOCKET": True},
            ),
            (
                30,
                {"API_KEY_NAME": "COINBASE_API_KEY", "RATE_LIMIT": 50, "SUPPORTS_WEBSOCKET": True},
            ),
        ],
        ib_id: [
            (90, {"API_KEY_NAME": "IB_API_KEY", "RATE_LIMIT": 50, "SUPPORTS_WEBSOCKET": True}),
            (30, {"API_KEY_NAME": "IB_API_KEY", "RATE_LIMIT": 100, "SUPPORTS_WEBSOCKET": True}),
        ],
        polygon_id: [
            (
                90,
                {"API_KEY_NAME": "POLYGON_API_KEY", "RATE_LIMIT": 100, "SUPPORTS_WEBSOCKET": True},
            ),
        ],
    }
    for provider_id, history in provider_meta_history.items():
        for days_ago, values in history:
            ts = _ts(now, days_ago)
            entries = [
                {"metadata_id": uuid.UUID(meta[key]["id"]), "value": value}
                for key, value in values.items()
            ]
            client.batch_create_provider_metadata(provider_id, timestamp=ts, entries=entries)

    # --- Provider-asset metadata ---
    print("Creating provider-asset metadata...")

    kraken_tickers = {"BTC": "XBT", "DOGE": "XDG"}
    min_order_sizes = {
        "BTC": 0.0001,
        "ETH": 0.001,
        "SOL": 0.01,
        "ADA": 1.0,
        "XRP": 1.0,
        "DOGE": 10.0,
        "AVAX": 0.1,
        "LINK": 0.1,
        "DOT": 0.1,
        "MATIC": 1.0,
        "ATOM": 0.1,
        "UNI": 0.1,
        "APT": 0.1,
        "ARB": 1.0,
        "OP": 0.1,
        "NEAR": 0.1,
        "FTM": 1.0,
        "AAVE": 0.01,
        "MKR": 0.001,
        "SNX": 0.1,
        "CRV": 1.0,
        "LDO": 0.1,
        "INJ": 0.01,
        "SUI": 0.1,
        "SEI": 1.0,
        "TIA": 0.1,
        "JUP": 1.0,
        "PENDLE": 0.1,
        "USDT": 1.0,
        "USDC": 1.0,
        "DAI": 1.0,
    }
    pa_ts = _ts(now, 90)

    # Kraken
    for sym in all_crypto_symbols:
        asset = asset_by_symbol.get(sym)
        if not asset:
            continue
        ticker = kraken_tickers.get(sym, sym)
        min_size = min_order_sizes.get(sym, 0.1)
        client.batch_create_provider_asset_metadata(
            kraken_id,
            uuid.UUID(asset["id"]),
            timestamp=pa_ts,
            entries=[
                {"metadata_id": uuid.UUID(meta["SYMBOL"]["id"]), "value": ticker},
                {"metadata_id": uuid.UUID(meta["PROVIDER_TICKER"]["id"]), "value": ticker},
                {
                    "metadata_id": uuid.UUID(meta["TRADING_PAIR_SYMBOL"]["id"]),
                    "value": f"{ticker}USD",
                },
                {"metadata_id": uuid.UUID(meta["MIN_ORDER_SIZE"]["id"]), "value": min_size},
            ],
        )

    # Coinbase
    for sym in COINBASE_CRYPTO_SYMBOLS:
        asset = asset_by_symbol.get(sym)
        if not asset:
            continue
        min_size = min_order_sizes.get(sym, 0.1)
        client.batch_create_provider_asset_metadata(
            coinbase_id,
            uuid.UUID(asset["id"]),
            timestamp=pa_ts,
            entries=[
                {"metadata_id": uuid.UUID(meta["SYMBOL"]["id"]), "value": sym},
                {"metadata_id": uuid.UUID(meta["PROVIDER_TICKER"]["id"]), "value": sym},
                {
                    "metadata_id": uuid.UUID(meta["TRADING_PAIR_SYMBOL"]["id"]),
                    "value": f"{sym}-USD",
                },
                {"metadata_id": uuid.UUID(meta["MIN_ORDER_SIZE"]["id"]), "value": min_size},
            ],
        )

    # IB (stocks, ETFs, commodities, bonds)
    ib_assets = (
        [s for _, s in STOCK_DEFS]
        + [s for _, s in ETF_DEFS]
        + [s for _, s in PRECIOUS_METAL_DEFS]
        + [s for _, s in ENERGY_DEFS]
        + [s for _, s in GOVT_BOND_DEFS]
    )
    for sym in ib_assets:
        asset = asset_by_symbol.get(sym)
        if not asset:
            continue
        client.batch_create_provider_asset_metadata(
            ib_id,
            uuid.UUID(asset["id"]),
            timestamp=pa_ts,
            entries=[
                {"metadata_id": uuid.UUID(meta["SYMBOL"]["id"]), "value": sym},
                {"metadata_id": uuid.UUID(meta["PROVIDER_TICKER"]["id"]), "value": sym},
            ],
        )

    # Polygon (stocks, ETFs)
    for sym in [s for _, s in STOCK_DEFS] + [s for _, s in ETF_DEFS]:
        asset = asset_by_symbol.get(sym)
        if not asset:
            continue
        client.batch_create_provider_asset_metadata(
            polygon_id,
            uuid.UUID(asset["id"]),
            timestamp=pa_ts,
            entries=[
                {"metadata_id": uuid.UUID(meta["SYMBOL"]["id"]), "value": sym},
                {"metadata_id": uuid.UUID(meta["PROVIDER_TICKER"]["id"]), "value": sym},
            ],
        )

    # Store in context
    ctx["kraken_id"] = kraken_id
    ctx["coinbase_id"] = coinbase_id
    ctx["ib_id"] = ib_id
    ctx["polygon_id"] = polygon_id
    ctx["kraken_exchange"] = kraken_exchange
    ctx["coinbase_exchange"] = coinbase_exchange
    ctx["ib_equity_exchange"] = ib_equity_exchange
    ctx["ib_futures_exchange"] = ib_futures_exchange
    ctx["all_crypto_symbols"] = all_crypto_symbols
    ctx["coinbase_crypto_symbols"] = COINBASE_CRYPTO_SYMBOLS
