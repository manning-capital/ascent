import uuid

import cyclopts

seed = cyclopts.App(name="seed", help="Seed the database with sample data.")


@seed.command()
def run(
    *,
    server_url: str = "http://localhost:8000",
    drop: bool = False,
):
    """Load fake data into the database for UI testing.

    Parameters
    ----------
    server_url
        Base URL of the running Ascent server.
    drop
        If True, instructs the user to restart the server with --drop first.
    """
    import datetime
    import random

    from ascent.client import AscentClient

    client = AscentClient(server_url)

    print("Waiting for server...")
    client.wait_until_ready()
    print("Server is ready.")

    if drop:
        print("Dropping and recreating all tables...")
        client.reset_database()
        print("Database reset complete.")

    # Check if data already exists
    existing = client.get_asset_types()
    if existing:
        print("Database already has data. Use --drop to reset first.")
        return

    now = datetime.datetime.now(datetime.UTC)

    def _ts(days_ago: int) -> datetime.datetime:
        return now.replace(microsecond=0) - datetime.timedelta(days=days_ago)

    print("Creating types...")
    # --- Type tables ---
    currency_type = client.create_asset_type(name="Currency", description="Any form of currency")
    crypto_type = client.create_asset_type(
        name="Cryptocurrency",
        description="Digital currency",
        parent_type_id=uuid.UUID(currency_type["id"]),
    )
    fiat_type = client.create_asset_type(
        name="Fiat Currency",
        description="Government-issued currency",
        parent_type_id=uuid.UUID(currency_type["id"]),
    )
    stock_type = client.create_asset_type(name="Stock", description="Equity share")

    market_participant_type = client.create_provider_type(
        name="Market Participant", description="Any entity participating in the market"
    )
    exchange_ptype = client.create_provider_type(
        name="Exchange",
        description="Cryptocurrency or stock exchange",
        parent_type_id=uuid.UUID(market_participant_type["id"]),
    )
    client.create_provider_type(
        name="Data Vendor",
        description="Market data provider",
        parent_type_id=uuid.UUID(market_participant_type["id"]),
    )

    spot_etype = client.create_exchange_type(name="Spot", description="Spot/cash market exchange")
    client.create_exchange_type(name="Futures", description="Futures/derivatives exchange")
    paper_etype = client.create_exchange_type(
        name="Paper", description="Paper/simulated trading exchange"
    )
    client.create_exchange_type(name="OTC", description="Over-the-counter trading")

    client.create_strategy_type(
        symbol="PAIRS_TRADING",
        name="Pairs Trading",
        description="Statistical arbitrage between correlated assets",
    )
    client.create_strategy_type(
        symbol="MOMENTUM", name="Momentum", description="Trend-following strategy"
    )
    client.create_strategy_type(
        symbol="MEAN_REVERSION",
        name="Mean Reversion",
        description="Strategy based on price reverting to the mean",
    )
    strategy_types = client.get_strategy_types()
    strategy_type_by_symbol = {t["symbol"]: t for t in strategy_types}

    trade_status_symbols = [
        ("PENDING", "Pending", "Trade is pending entry"),
        ("OPENING", "Opening", "Entry orders have been submitted"),
        ("OPEN", "Open", "Trade is currently open"),
        ("CLOSING", "Closing", "Exit orders have been submitted"),
        ("CLOSED", "Closed", "Trade has been closed"),
        ("CANCELLED", "Cancelled", "Trade was cancelled"),
        ("ERROR", "Error", "Trade encountered an error"),
    ]
    for sym, name, desc in trade_status_symbols:
        client.create_trade_status_type(symbol=sym, name=name, description=desc)
    trade_status_types = client.get_trade_status_types()
    status_map = {t["symbol"]: t for t in trade_status_types}

    order_type_symbols = [
        ("MARKET", "Market", "Market order"),
        ("LIMIT", "Limit", "Limit order"),
        ("STOP", "Stop", "Stop order"),
    ]
    for sym, name, desc in order_type_symbols:
        client.create_order_type(symbol=sym, name=name, description=desc)
    order_types = client.get_order_types()
    order_type_by_symbol = {t["symbol"]: t for t in order_types}

    order_status_symbols = [
        ("SUBMITTED", "Submitted", "Order submitted"),
        ("ACCEPTED", "Accepted", "Order accepted by exchange"),
        ("PARTIALLY_FILLED", "Partially Filled", "Order partially filled"),
        ("FILLED", "Filled", "Order fully filled"),
        ("REJECTED", "Rejected", "Order rejected"),
        ("CANCELLED", "Cancelled", "Order cancelled"),
    ]
    for sym, name, desc in order_status_symbols:
        client.create_order_status_type(symbol=sym, name=name, description=desc)
    order_status_types = client.get_order_status_types()
    order_status_map = {t["symbol"]: t for t in order_status_types}

    print("Creating assets...")
    # --- Assets ---
    asset_defs = [
        (fiat_type["id"], "US Dollar", "USD"),
        (crypto_type["id"], "Bitcoin", "BTC"),
        (crypto_type["id"], "Ethereum", "ETH"),
        (crypto_type["id"], "Solana", "SOL"),
        (crypto_type["id"], "Cardano", "ADA"),
        (crypto_type["id"], "Ripple", "XRP"),
        (crypto_type["id"], "Dogecoin", "DOGE"),
        (crypto_type["id"], "Avalanche", "AVAX"),
        (crypto_type["id"], "Chainlink", "LINK"),
        (crypto_type["id"], "Polkadot", "DOT"),
        (crypto_type["id"], "Polygon", "MATIC"),
        (crypto_type["id"], "Cosmos", "ATOM"),
        (crypto_type["id"], "Uniswap", "UNI"),
        (crypto_type["id"], "Aptos", "APT"),
        (crypto_type["id"], "Arbitrum", "ARB"),
        (crypto_type["id"], "Optimism", "OP"),
        (crypto_type["id"], "NEAR Protocol", "NEAR"),
        (crypto_type["id"], "Fantom", "FTM"),
        (crypto_type["id"], "Aave", "AAVE"),
        (crypto_type["id"], "Maker", "MKR"),
        (crypto_type["id"], "Synthetix", "SNX"),
        (crypto_type["id"], "Curve", "CRV"),
        (crypto_type["id"], "Lido DAO", "LDO"),
        (crypto_type["id"], "Injective", "INJ"),
        (crypto_type["id"], "Sui", "SUI"),
        (crypto_type["id"], "Sei", "SEI"),
        (crypto_type["id"], "Celestia", "TIA"),
        (crypto_type["id"], "Jupiter", "JUP"),
        (crypto_type["id"], "Pendle", "PENDLE"),
    ]
    assets = {}
    for type_id, name, symbol in asset_defs:
        a = client.create_asset(asset_type_id=uuid.UUID(type_id), name=name, symbol=symbol)
        assets[symbol] = a
    asset_by_symbol = assets

    print("Creating providers and exchanges...")
    # --- Providers ---
    kraken_provider = client.create_provider(
        provider_type_id=uuid.UUID(exchange_ptype["id"]),
        name="Kraken",
        description="Kraken Exchange",
    )
    coinbase_provider = client.create_provider(
        provider_type_id=uuid.UUID(exchange_ptype["id"]),
        name="Coinbase",
        description="Coinbase Exchange",
    )

    # --- Exchanges ---
    kraken_exchange = client.create_exchange(
        exchange_type_id=uuid.UUID(spot_etype["id"]),
        name="Kraken",
        description="Kraken Spot Exchange",
        provider_id=uuid.UUID(kraken_provider["id"]),
    )
    coinbase_exchange = client.create_exchange(
        exchange_type_id=uuid.UUID(spot_etype["id"]),
        name="Coinbase",
        description="Coinbase Spot Exchange",
        provider_id=uuid.UUID(coinbase_provider["id"]),
    )
    client.create_exchange(
        exchange_type_id=uuid.UUID(paper_etype["id"]),
        name="Paper Trading",
        description="Simulated paper trading exchange",
        implementation_class="ascent.exchanges.paper.PaperExchange",
        config={"initial_balance": 100000},
    )

    print("Creating attributes and metadata types...")
    # --- Attributes ---
    attr_close = client.create_attribute(name="close", description="Close price")
    attr_spread = client.create_attribute(
        name="spread", description="Price spread between correlated assets"
    )
    attr_zscore = client.create_attribute(name="z_score", description="Z-score of the spread")
    attr_rsi = client.create_attribute(name="rsi", description="Relative Strength Index")
    all_attributes = [attr_close, attr_spread, attr_zscore, attr_rsi]

    # --- Metadata types ---
    meta_defs = [
        ("market_cap", "Market Cap", "Market capitalization in USD", "float"),
        ("sector", "Sector", "Industry sector classification", "string"),
        ("circulating_supply", "Circulating Supply", "Circulating supply of the asset", "float"),
        ("max_supply", "Max Supply", "Maximum supply of the asset", "float"),
        ("launch_date", "Launch Date", "Date the asset was launched", "date"),
        ("is_stablecoin", "Is Stablecoin", "Whether the asset is a stablecoin", "boolean"),
        (
            "consensus_mechanism",
            "Consensus Mechanism",
            "Consensus mechanism (e.g. PoW, PoS)",
            "string",
        ),
        ("whitepaper_url", "Whitepaper URL", "URL to the project whitepaper", "string"),
        ("iso_currency_code", "ISO Currency Code", "ISO 4217 currency code", "string"),
        ("issuing_country", "Issuing Country", "Country that issues the currency", "string"),
        ("api_key_name", "API Key Name", "Name of the API key environment variable", "string"),
        ("rate_limit", "Rate Limit", "API rate limit (requests/minute)", "integer"),
        (
            "supports_websocket",
            "Supports WebSocket",
            "Whether the provider supports WebSocket connections",
            "boolean",
        ),
        ("symbol", "Symbol", "The identifier/symbol used by this provider for the asset", "string"),
        (
            "provider_ticker",
            "Provider Ticker",
            "The ticker/symbol used by this provider for the asset",
            "string",
        ),
        (
            "trading_pair_symbol",
            "Trading Pair Symbol",
            "The trading pair symbol on this provider (e.g. XBTUSD)",
            "string",
        ),
        ("min_order_size", "Min Order Size", "Minimum order size on this provider", "float"),
    ]
    meta = {}
    for name, display_name, description, value_type in meta_defs:
        m = client.create_metadata_type(
            name=name, display_name=display_name, description=description, value_type=value_type
        )
        meta[name] = m

    print("Creating type-metadata field definitions...")
    # --- Asset type metadata field definitions ---
    # Currency (parent) fields
    client.add_asset_type_metadata(
        uuid.UUID(currency_type["id"]),
        metadata_id=uuid.UUID(meta["market_cap"]["id"]),
        is_required=True,
        display_order=0,
    )
    client.add_asset_type_metadata(
        uuid.UUID(currency_type["id"]),
        metadata_id=uuid.UUID(meta["sector"]["id"]),
        is_required=False,
        display_order=1,
    )

    # Cryptocurrency own fields
    for i, (name, req) in enumerate(
        [
            ("circulating_supply", True),
            ("max_supply", False),
            ("launch_date", False),
            ("is_stablecoin", True),
            ("consensus_mechanism", False),
            ("whitepaper_url", False),
        ]
    ):
        client.add_asset_type_metadata(
            uuid.UUID(crypto_type["id"]),
            metadata_id=uuid.UUID(meta[name]["id"]),
            is_required=req,
            display_order=i,
        )

    # Fiat Currency own fields
    client.add_asset_type_metadata(
        uuid.UUID(fiat_type["id"]),
        metadata_id=uuid.UUID(meta["iso_currency_code"]["id"]),
        is_required=True,
        display_order=0,
    )
    client.add_asset_type_metadata(
        uuid.UUID(fiat_type["id"]),
        metadata_id=uuid.UUID(meta["issuing_country"]["id"]),
        is_required=True,
        display_order=1,
    )

    # Stock fields
    client.add_asset_type_metadata(
        uuid.UUID(stock_type["id"]),
        metadata_id=uuid.UUID(meta["market_cap"]["id"]),
        is_required=True,
        display_order=0,
    )
    client.add_asset_type_metadata(
        uuid.UUID(stock_type["id"]),
        metadata_id=uuid.UUID(meta["sector"]["id"]),
        is_required=True,
        display_order=1,
    )

    # --- Provider type metadata field definitions ---
    # Market Participant (parent) fields
    for i, (name, req) in enumerate(
        [
            ("api_key_name", True),
            ("rate_limit", True),
            ("supports_websocket", False),
        ]
    ):
        client.add_provider_type_metadata(
            uuid.UUID(market_participant_type["id"]),
            metadata_id=uuid.UUID(meta[name]["id"]),
            is_required=req,
            display_order=i,
        )

    # --- Asset type provider-asset metadata field definitions ---
    client.add_asset_type_provider_asset_metadata(
        uuid.UUID(currency_type["id"]),
        metadata_id=uuid.UUID(meta["provider_ticker"]["id"]),
        is_required=True,
        display_order=0,
    )
    client.add_asset_type_provider_asset_metadata(
        uuid.UUID(crypto_type["id"]),
        metadata_id=uuid.UUID(meta["trading_pair_symbol"]["id"]),
        is_required=True,
        display_order=0,
    )
    client.add_asset_type_provider_asset_metadata(
        uuid.UUID(crypto_type["id"]),
        metadata_id=uuid.UUID(meta["min_order_size"]["id"]),
        is_required=False,
        display_order=1,
    )

    print("Creating asset metadata...")
    # --- Sample asset metadata (temporal entries with history) ---
    crypto_info = {
        "BTC": {
            "sector": "Store of Value",
            "consensus": "Proof of Work",
            "launch_date": "2009-01-03",
            "max_supply": 21_000_000,
            "base_mcap": 1_300_000_000_000,
            "base_supply": 19_700_000,
        },
        "ETH": {
            "sector": "Smart Contract Platform",
            "consensus": "Proof of Stake",
            "launch_date": "2015-07-30",
            "max_supply": None,
            "base_mcap": 410_000_000_000,
            "base_supply": 120_200_000,
        },
        "SOL": {
            "sector": "Smart Contract Platform",
            "consensus": "Proof of History",
            "launch_date": "2020-03-16",
            "max_supply": None,
            "base_mcap": 68_000_000_000,
            "base_supply": 440_000_000,
        },
        "ADA": {
            "sector": "Smart Contract Platform",
            "consensus": "Proof of Stake",
            "launch_date": "2017-09-29",
            "max_supply": 45_000_000_000,
            "base_mcap": 16_000_000_000,
            "base_supply": 35_000_000_000,
        },
        "XRP": {
            "sector": "Payments",
            "consensus": "XRP Ledger Consensus",
            "launch_date": "2012-06-02",
            "max_supply": 100_000_000_000,
            "base_mcap": 32_000_000_000,
            "base_supply": 53_000_000_000,
        },
        "DOGE": {
            "sector": "Meme",
            "consensus": "Proof of Work",
            "launch_date": "2013-12-06",
            "max_supply": None,
            "base_mcap": 24_000_000_000,
            "base_supply": 143_000_000_000,
        },
        "AVAX": {
            "sector": "Smart Contract Platform",
            "consensus": "Avalanche Consensus",
            "launch_date": "2020-09-21",
            "max_supply": 720_000_000,
            "base_mcap": 14_000_000_000,
            "base_supply": 380_000_000,
        },
        "LINK": {
            "sector": "Oracle",
            "consensus": "Delegated Proof of Stake",
            "launch_date": "2017-09-19",
            "max_supply": 1_000_000_000,
            "base_mcap": 10_000_000_000,
            "base_supply": 587_000_000,
        },
        "DOT": {
            "sector": "Interoperability",
            "consensus": "Nominated Proof of Stake",
            "launch_date": "2020-05-26",
            "max_supply": None,
            "base_mcap": 9_000_000_000,
            "base_supply": 1_400_000_000,
        },
        "MATIC": {
            "sector": "Layer 2",
            "consensus": "Proof of Stake",
            "launch_date": "2019-04-26",
            "max_supply": 10_000_000_000,
            "base_mcap": 8_000_000_000,
            "base_supply": 9_300_000_000,
        },
        "ATOM": {
            "sector": "Interoperability",
            "consensus": "Tendermint BFT",
            "launch_date": "2019-03-14",
            "max_supply": None,
            "base_mcap": 4_000_000_000,
            "base_supply": 390_000_000,
        },
        "UNI": {
            "sector": "DeFi",
            "consensus": "N/A (ERC-20)",
            "launch_date": "2020-09-16",
            "max_supply": 1_000_000_000,
            "base_mcap": 6_000_000_000,
            "base_supply": 600_000_000,
        },
        "APT": {
            "sector": "Smart Contract Platform",
            "consensus": "AptosBFT",
            "launch_date": "2022-10-12",
            "max_supply": None,
            "base_mcap": 4_500_000_000,
            "base_supply": 470_000_000,
        },
        "ARB": {
            "sector": "Layer 2",
            "consensus": "Optimistic Rollup",
            "launch_date": "2023-03-23",
            "max_supply": 10_000_000_000,
            "base_mcap": 3_000_000_000,
            "base_supply": 3_400_000_000,
        },
        "OP": {
            "sector": "Layer 2",
            "consensus": "Optimistic Rollup",
            "launch_date": "2022-05-31",
            "max_supply": 4_294_967_296,
            "base_mcap": 2_800_000_000,
            "base_supply": 1_100_000_000,
        },
        "NEAR": {
            "sector": "Smart Contract Platform",
            "consensus": "Nightshade PoS",
            "launch_date": "2020-04-22",
            "max_supply": 1_000_000_000,
            "base_mcap": 5_500_000_000,
            "base_supply": 1_100_000_000,
        },
        "FTM": {
            "sector": "Smart Contract Platform",
            "consensus": "Lachesis aBFT",
            "launch_date": "2019-12-27",
            "max_supply": 3_175_000_000,
            "base_mcap": 2_000_000_000,
            "base_supply": 2_800_000_000,
        },
        "AAVE": {
            "sector": "DeFi",
            "consensus": "N/A (ERC-20)",
            "launch_date": "2020-10-02",
            "max_supply": 16_000_000,
            "base_mcap": 4_200_000_000,
            "base_supply": 14_900_000,
        },
        "MKR": {
            "sector": "DeFi",
            "consensus": "N/A (ERC-20)",
            "launch_date": "2017-11-25",
            "max_supply": 1_005_577,
            "base_mcap": 2_500_000_000,
            "base_supply": 900_000,
        },
        "SNX": {
            "sector": "DeFi",
            "consensus": "N/A (ERC-20)",
            "launch_date": "2018-03-11",
            "max_supply": 300_000_000,
            "base_mcap": 800_000_000,
            "base_supply": 320_000_000,
        },
        "CRV": {
            "sector": "DeFi",
            "consensus": "N/A (ERC-20)",
            "launch_date": "2020-08-13",
            "max_supply": 3_030_000_000,
            "base_mcap": 700_000_000,
            "base_supply": 1_900_000_000,
        },
        "LDO": {
            "sector": "DeFi",
            "consensus": "N/A (ERC-20)",
            "launch_date": "2020-12-17",
            "max_supply": 1_000_000_000,
            "base_mcap": 1_800_000_000,
            "base_supply": 890_000_000,
        },
        "INJ": {
            "sector": "DeFi",
            "consensus": "Tendermint BFT",
            "launch_date": "2020-10-21",
            "max_supply": 100_000_000,
            "base_mcap": 2_500_000_000,
            "base_supply": 93_000_000,
        },
        "SUI": {
            "sector": "Smart Contract Platform",
            "consensus": "Narwhal/Bullshark",
            "launch_date": "2023-05-03",
            "max_supply": 10_000_000_000,
            "base_mcap": 3_800_000_000,
            "base_supply": 2_700_000_000,
        },
        "SEI": {
            "sector": "Smart Contract Platform",
            "consensus": "Twin-Turbo Consensus",
            "launch_date": "2023-08-15",
            "max_supply": 10_000_000_000,
            "base_mcap": 1_500_000_000,
            "base_supply": 3_600_000_000,
        },
        "TIA": {
            "sector": "Data Availability",
            "consensus": "Tendermint BFT",
            "launch_date": "2023-10-31",
            "max_supply": 1_000_000_000,
            "base_mcap": 2_000_000_000,
            "base_supply": 210_000_000,
        },
        "JUP": {
            "sector": "DeFi",
            "consensus": "N/A (Solana SPL)",
            "launch_date": "2024-01-31",
            "max_supply": 10_000_000_000,
            "base_mcap": 1_600_000_000,
            "base_supply": 1_350_000_000,
        },
        "PENDLE": {
            "sector": "DeFi",
            "consensus": "N/A (ERC-20)",
            "launch_date": "2021-04-28",
            "max_supply": 258_000_000,
            "base_mcap": 1_200_000_000,
            "base_supply": 161_000_000,
        },
    }

    random.seed(42)
    for symbol, info in crypto_info.items():
        asset = asset_by_symbol.get(symbol)
        if not asset:
            continue
        asset_id = uuid.UUID(asset["id"])
        base_mcap = info["base_mcap"]
        base_supply = info["base_supply"]

        for snap_idx, days_ago in enumerate([90, 60, 30]):
            ts = _ts(days_ago)
            growth = 1.0 - (2 - snap_idx) * random.uniform(0.08, 0.20)
            mcap = int(base_mcap * growth)
            supply = int(base_supply * (1.0 - (2 - snap_idx) * random.uniform(0.001, 0.01)))

            entries = [
                {"metadata_id": uuid.UUID(meta["market_cap"]["id"]), "value": mcap},
                {"metadata_id": uuid.UUID(meta["circulating_supply"]["id"]), "value": supply},
            ]

            if snap_idx == 0:
                entries.append(
                    {"metadata_id": uuid.UUID(meta["is_stablecoin"]["id"]), "value": False}
                )
                entries.append(
                    {
                        "metadata_id": uuid.UUID(meta["consensus_mechanism"]["id"]),
                        "value": info["consensus"],
                    }
                )
                entries.append(
                    {"metadata_id": uuid.UUID(meta["sector"]["id"]), "value": info["sector"]}
                )
                entries.append(
                    {
                        "metadata_id": uuid.UUID(meta["launch_date"]["id"]),
                        "value": info["launch_date"],
                    }
                )
                if info["max_supply"] is not None:
                    entries.append(
                        {
                            "metadata_id": uuid.UUID(meta["max_supply"]["id"]),
                            "value": info["max_supply"],
                        }
                    )

            client.batch_create_asset_metadata(asset_id, timestamp=ts, entries=entries)

    # USD (Fiat): single snapshot
    usd = asset_by_symbol["USD"]
    usd_id = uuid.UUID(usd["id"])
    client.batch_create_asset_metadata(
        usd_id,
        timestamp=_ts(90),
        entries=[
            {"metadata_id": uuid.UUID(meta["iso_currency_code"]["id"]), "value": "USD"},
            {"metadata_id": uuid.UUID(meta["issuing_country"]["id"]), "value": "United States"},
            {"metadata_id": uuid.UUID(meta["is_stablecoin"]["id"]), "value": False},
            {"metadata_id": uuid.UUID(meta["market_cap"]["id"]), "value": 0},
            {"metadata_id": uuid.UUID(meta["sector"]["id"]), "value": "Fiat"},
        ],
    )

    print("Creating provider metadata...")
    # --- Provider metadata (Kraken history) ---
    kraken_id = uuid.UUID(kraken_provider["id"])
    coinbase_id = uuid.UUID(coinbase_provider["id"])
    kraken_history = [
        (
            90,
            {
                "api_key_name": "KRAKEN_API_KEY",
                "rate_limit": 30,
                "supports_websocket": True,
            },
        ),
        (
            60,
            {
                "api_key_name": "KRAKEN_API_KEY",
                "rate_limit": 45,
                "supports_websocket": True,
            },
        ),
        (
            30,
            {
                "api_key_name": "KRAKEN_API_KEY",
                "rate_limit": 60,
                "supports_websocket": True,
            },
        ),
    ]
    for days_ago, values in kraken_history:
        ts = _ts(days_ago)
        entries = [
            {"metadata_id": uuid.UUID(meta[key]["id"]), "value": value}
            for key, value in values.items()
        ]
        client.batch_create_provider_metadata(kraken_id, timestamp=ts, entries=entries)

    # --- Provider metadata (Coinbase history) ---
    coinbase_history = [
        (90, {"api_key_name": "COINBASE_API_KEY", "rate_limit": 25, "supports_websocket": True}),
        (60, {"api_key_name": "COINBASE_API_KEY", "rate_limit": 40, "supports_websocket": True}),
        (30, {"api_key_name": "COINBASE_API_KEY", "rate_limit": 50, "supports_websocket": True}),
    ]
    for days_ago, values in coinbase_history:
        ts = _ts(days_ago)
        entries = [
            {"metadata_id": uuid.UUID(meta[key]["id"]), "value": value}
            for key, value in values.items()
        ]
        client.batch_create_provider_metadata(coinbase_id, timestamp=ts, entries=entries)

    print("Creating provider-asset metadata...")
    # --- Provider-asset metadata (per asset-provider link) ---
    crypto_symbols = [
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
        "APT",
        "ARB",
        "OP",
        "NEAR",
        "FTM",
        "AAVE",
        "MKR",
        "SNX",
        "CRV",
        "LDO",
        "INJ",
        "SUI",
        "SEI",
        "TIA",
        "JUP",
        "PENDLE",
    ]
    kraken_tickers = {
        "BTC": "XBT",
        "ETH": "ETH",
        "SOL": "SOL",
        "ADA": "ADA",
        "XRP": "XRP",
        "DOGE": "XDG",
        "AVAX": "AVAX",
        "LINK": "LINK",
        "DOT": "DOT",
        "MATIC": "MATIC",
        "ATOM": "ATOM",
        "UNI": "UNI",
        "APT": "APT",
        "ARB": "ARB",
        "OP": "OP",
        "NEAR": "NEAR",
        "FTM": "FTM",
        "AAVE": "AAVE",
        "MKR": "MKR",
        "SNX": "SNX",
        "CRV": "CRV",
        "LDO": "LDO",
        "INJ": "INJ",
        "SUI": "SUI",
        "SEI": "SEI",
        "TIA": "TIA",
        "JUP": "JUP",
        "PENDLE": "PENDLE",
    }
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
    }
    pa_ts = _ts(90)
    # Kraken provider-asset metadata
    for sym in crypto_symbols:
        asset = asset_by_symbol.get(sym)
        if not asset:
            continue
        asset_id = uuid.UUID(asset["id"])
        ticker = kraken_tickers.get(sym, sym)
        min_size = min_order_sizes.get(sym, 0.1)
        client.batch_create_provider_asset_metadata(
            kraken_id,
            asset_id,
            timestamp=pa_ts,
            entries=[
                {"metadata_id": uuid.UUID(meta["symbol"]["id"]), "value": ticker},
                {"metadata_id": uuid.UUID(meta["provider_ticker"]["id"]), "value": ticker},
                {
                    "metadata_id": uuid.UUID(meta["trading_pair_symbol"]["id"]),
                    "value": f"{ticker}USD",
                },
                {"metadata_id": uuid.UUID(meta["min_order_size"]["id"]), "value": min_size},
            ],
        )

    # Coinbase provider-asset metadata (subset — Coinbase uses standard symbols)
    coinbase_symbols = [
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
    ]
    coinbase_min_order_sizes = {
        "BTC": 0.00001,
        "ETH": 0.0001,
        "SOL": 0.01,
        "ADA": 1.0,
        "XRP": 1.0,
        "DOGE": 1.0,
        "AVAX": 0.01,
        "LINK": 0.1,
        "DOT": 0.01,
        "MATIC": 1.0,
        "ATOM": 0.01,
        "UNI": 0.1,
        "ARB": 1.0,
        "OP": 0.1,
        "NEAR": 0.1,
        "AAVE": 0.001,
        "MKR": 0.0001,
        "SNX": 0.1,
        "CRV": 1.0,
        "LDO": 0.1,
        "INJ": 0.01,
        "SUI": 0.1,
    }
    for sym in coinbase_symbols:
        asset = asset_by_symbol.get(sym)
        if not asset:
            continue
        asset_id = uuid.UUID(asset["id"])
        min_size = coinbase_min_order_sizes.get(sym, 0.1)
        client.batch_create_provider_asset_metadata(
            coinbase_id,
            asset_id,
            timestamp=pa_ts,
            entries=[
                {"metadata_id": uuid.UUID(meta["symbol"]["id"]), "value": sym},
                {"metadata_id": uuid.UUID(meta["provider_ticker"]["id"]), "value": sym},
                {
                    "metadata_id": uuid.UUID(meta["trading_pair_symbol"]["id"]),
                    "value": f"{sym}-USD",
                },
                {"metadata_id": uuid.UUID(meta["min_order_size"]["id"]), "value": min_size},
            ],
        )

    print("Creating portfolios and asset groups...")
    # --- Portfolios ---
    portfolio_main = client.create_portfolio(
        name="Main Portfolio",
        description="Primary trading portfolio",
        base_currency_asset_id=uuid.UUID(usd["id"]),
        pricing_provider_id=kraken_id,
    )
    portfolio_paper = client.create_portfolio(
        name="Paper Trading",
        description="Simulated trading portfolio",
        base_currency_asset_id=uuid.UUID(usd["id"]),
        pricing_provider_id=kraken_id,
    )
    portfolio_coinbase = client.create_portfolio(
        name="Coinbase Portfolio",
        description="Coinbase trading portfolio",
        base_currency_asset_id=uuid.UUID(usd["id"]),
        pricing_provider_id=coinbase_id,
    )

    random.seed(42)

    # --- Single-member Asset Groups (Kraken) ---
    single_member_groups = {}
    for sym in crypto_symbols:
        asset = asset_by_symbol[sym]
        grp = client.create_asset_group(
            members=[
                {
                    "provider_id": kraken_id,
                    "from_asset_id": uuid.UUID(asset["id"]),
                    "to_asset_id": uuid.UUID(usd["id"]),
                    "order": 1,
                }
            ]
        )
        single_member_groups[asset["id"]] = grp

    # --- Single-member Asset Groups (Coinbase) ---
    coinbase_single_member_groups = {}
    for sym in coinbase_symbols:
        asset = asset_by_symbol[sym]
        grp = client.create_asset_group(
            members=[
                {
                    "provider_id": coinbase_id,
                    "from_asset_id": uuid.UUID(asset["id"]),
                    "to_asset_id": uuid.UUID(usd["id"]),
                    "order": 1,
                }
            ]
        )
        coinbase_single_member_groups[asset["id"]] = grp

    # --- Multi-member Asset Groups (Kraken) ---
    pair_defs = [
        ("BTC-ETH", ["BTC", "ETH"]),
        ("SOL-AVAX", ["SOL", "AVAX"]),
        ("LINK-DOT", ["LINK", "DOT"]),
        ("ADA-XRP", ["ADA", "XRP"]),
        ("UNI-AAVE", ["UNI", "AAVE"]),
    ]
    pair_groups = []
    for _label, syms in pair_defs:
        members = [
            {
                "provider_id": kraken_id,
                "from_asset_id": uuid.UUID(asset_by_symbol[s]["id"]),
                "to_asset_id": uuid.UUID(usd["id"]),
                "order": i + 1,
            }
            for i, s in enumerate(syms)
        ]
        grp = client.create_asset_group(members=members)
        pair_groups.append(grp)

    basket_defs = [
        ("DeFi Blue Chip", ["AAVE", "MKR", "UNI", "SNX", "CRV", "LDO"]),
        ("L1 Majors", ["ETH", "SOL", "AVAX", "DOT", "ATOM", "NEAR", "APT", "SUI"]),
    ]
    basket_groups = []
    for _label, syms in basket_defs:
        members = [
            {
                "provider_id": kraken_id,
                "from_asset_id": uuid.UUID(asset_by_symbol[s]["id"]),
                "to_asset_id": uuid.UUID(usd["id"]),
                "order": i + 1,
            }
            for i, s in enumerate(syms)
        ]
        grp = client.create_asset_group(members=members)
        basket_groups.append(grp)

    # --- Multi-member Asset Groups (Coinbase) ---
    coinbase_pair_defs = [
        ("BTC-ETH", ["BTC", "ETH"]),
        ("SOL-AVAX", ["SOL", "AVAX"]),
        ("LINK-DOT", ["LINK", "DOT"]),
    ]
    coinbase_pair_groups = []
    for _label, syms in coinbase_pair_defs:
        members = [
            {
                "provider_id": coinbase_id,
                "from_asset_id": uuid.UUID(asset_by_symbol[s]["id"]),
                "to_asset_id": uuid.UUID(usd["id"]),
                "order": i + 1,
            }
            for i, s in enumerate(syms)
        ]
        grp = client.create_asset_group(members=members)
        coinbase_pair_groups.append(grp)

    all_groups = (
        list(single_member_groups.values())
        + pair_groups
        + basket_groups
        + list(coinbase_single_member_groups.values())
        + coinbase_pair_groups
    )

    print("Creating feeds...")
    # --- Feed Types ---
    feed_type_defs = [
        ("MARKET_DATA", "Market Data", "Real-time market data"),
        ("DERIVED", "Derived", "Computed from other feeds"),
        ("ALTERNATIVE", "Alternative", "Alternative data sources"),
        ("EXTERNAL", "External", "Data published via the Ascent API by an external process"),
    ]
    feed_types_created = []
    for sym, name, desc in feed_type_defs:
        ft = client.create_feed_type(symbol=sym, name=name, description=desc)
        feed_types_created.append(ft)

    # --- Feeds ---
    from ascent.feeds.examples.market import market_data
    from ascent.feeds.examples.ou_params import ou_params

    feed_market = client.create_feed(
        name="Market Data",
        feed_type_id=uuid.UUID(feed_types_created[0]["id"]),
        feed_ref="ascent.feeds.examples.market:market_data",
        output_table="provider_asset_group_attribute",
        channel="ascent.feed.market_data",
        description="Pulls minutely OHLCV pricing data 1s before each minute close.",
        parameters={"provider_name": "kraken", "attributes": ["close"], "lookback_minutes": 5},
        parameter_schema=market_data.parameter_schema(),
        schedule={"interval": 60, "offset": -1.0, "start_date": "2024-01-01T00:00:00+00:00"},
    )
    feed_orderbook = client.create_feed(
        name="Order Book",
        feed_type_id=uuid.UUID(feed_types_created[0]["id"]),
        feed_ref="ascent.feeds.examples.orderbook:orderbook",
        output_table="provider_asset_group_attribute",
        channel="ascent.feed.orderbook",
        description="Snapshots top-of-book bid/ask every 30 seconds.",
        parameters={"depth": 10, "provider_name": "kraken"},
        schedule={"interval": 30, "start_date": "2024-01-01T00:00:00+00:00"},
    )
    feed_sentiment = client.create_feed(
        name="Sentiment",
        feed_type_id=uuid.UUID(feed_types_created[2]["id"]),
        feed_ref="ascent.feeds.examples.sentiment:sentiment",
        output_table="provider_asset_group_attribute",
        channel="ascent.feed.sentiment",
        description="Aggregated social sentiment scores every 5 minutes.",
        parameters={"sources": ["twitter", "reddit"]},
        schedule={"interval": 300, "start_date": "2024-01-01T00:00:00+00:00"},
    )
    feed_cointegration = client.create_feed(
        name="Cointegration",
        feed_type_id=uuid.UUID(feed_types_created[1]["id"]),
        feed_ref="ascent.feeds.examples.cointegration:cointegration",
        output_table="provider_asset_group_attribute",
        channel="ascent.feed.cointegration",
        description="Cointegration test statistics for asset pair groups every 5 minutes.",
        parameters={"test": "engle_granger", "lookback_days": 30},
        schedule={"interval": 300, "start_date": "2024-01-01T00:00:00+00:00"},
    )
    feed_ou = client.create_feed(
        name="OU Parameters",
        feed_type_id=uuid.UUID(feed_types_created[3]["id"]),
        feed_ref="ascent.feeds.examples.ou_params:ou_params",
        output_table="provider_asset_group_attribute",
        channel="ascent.feed.ou_params",
        description="Ornstein-Uhlenbeck parameters computed externally.",
        parameters={"lookback_days": 60},
        parameter_schema=ou_params.parameter_schema(),
    )
    feed_funding = client.create_feed(
        name="Funding Rates",
        feed_type_id=uuid.UUID(feed_types_created[3]["id"]),
        feed_ref="ascent.feeds.examples.funding:funding_rates",
        output_table="provider_asset_group_attribute",
        channel="ascent.feed.funding_rates",
        description="Perpetual swap funding rates computed externally.",
        parameters={"exchanges": ["kraken", "binance"]},
    )
    feed_spread = client.create_feed(
        name="Spread Analytics",
        feed_type_id=uuid.UUID(feed_types_created[1]["id"]),
        feed_ref="ascent.feeds.examples.spread:spread_analytics",
        output_table="provider_asset_group_attribute",
        channel="ascent.feed.spread",
        description="Computes bid-ask spread metrics from order book and market data.",
        parameters={"window": 20},
    )
    feed_sent_score = client.create_feed(
        name="Sentiment Score",
        feed_type_id=uuid.UUID(feed_types_created[1]["id"]),
        feed_ref="ascent.feeds.examples.sentiment:sentiment_score",
        output_table="provider_asset_group_attribute",
        channel="ascent.feed.sentiment_score",
        description="Normalised sentiment z-score derived from raw sentiment feed.",
        parameters={"lookback_hours": 24},
    )
    feed_half_life = client.create_feed(
        name="Half-Life",
        feed_type_id=uuid.UUID(feed_types_created[1]["id"]),
        feed_ref="ascent.feeds.examples.half_life:half_life",
        output_table="provider_asset_group_attribute",
        channel="ascent.feed.half_life",
        description="Mean-reversion half-life estimate derived from OU parameters.",
        parameters={"min_samples": 30},
    )

    # Coinbase-specific feeds
    feed_cb_market = client.create_feed(
        name="Market Data (Coinbase)",
        feed_type_id=uuid.UUID(feed_types_created[0]["id"]),
        feed_ref="ascent.feeds.examples.market:market_data",
        output_table="provider_asset_group_attribute",
        channel="ascent.feed.coinbase_market_data",
        description="Minutely OHLCV pricing data from Coinbase.",
        parameters={"provider_name": "coinbase", "attributes": ["close"], "lookback_minutes": 5},
        parameter_schema=market_data.parameter_schema(),
        schedule={"interval": 60, "offset": -1.0, "start_date": "2024-01-01T00:00:00+00:00"},
    )
    feed_cb_orderbook = client.create_feed(
        name="Order Book (Coinbase)",
        feed_type_id=uuid.UUID(feed_types_created[0]["id"]),
        feed_ref="ascent.feeds.examples.orderbook:orderbook",
        output_table="provider_asset_group_attribute",
        channel="ascent.feed.coinbase_orderbook",
        description="Snapshots top-of-book bid/ask from Coinbase every 30 seconds.",
        parameters={"depth": 10, "provider_name": "coinbase"},
        schedule={"interval": 30, "start_date": "2024-01-01T00:00:00+00:00"},
    )

    # --- Feed dependencies ---
    feed_deps = [
        (feed_spread["id"], feed_market["id"]),
        (feed_spread["id"], feed_orderbook["id"]),
        (feed_sent_score["id"], feed_sentiment["id"]),
        (feed_cointegration["id"], feed_market["id"]),
        (feed_half_life["id"], feed_ou["id"]),
    ]
    for child_id, parent_id in feed_deps:
        client.create_feed_dependency(uuid.UUID(child_id), depends_on_feed_id=uuid.UUID(parent_id))

    print("Creating feed runs and partitions...")
    # --- Feed runs (sample history for all feeds) ---
    from ascent.feeds.partition import partition_key_for, partition_window
    from ascent.feeds.schedule import Schedule

    all_feeds = [
        feed_market,
        feed_orderbook,
        feed_sentiment,
        feed_cointegration,
        feed_ou,
        feed_funding,
        feed_spread,
        feed_sent_score,
        feed_half_life,
        feed_cb_market,
        feed_cb_orderbook,
    ]

    feed_schedules = {}
    for f in all_feeds:
        sched = f.get("schedule")
        feed_schedules[f["id"]] = Schedule(**sched) if sched else None

    partition_cache = {}
    feed_runs_by_feed = {f["id"]: [] for f in all_feeds}

    for feed_obj in all_feeds:
        schedule_obj = feed_schedules[feed_obj["id"]]
        for i in range(100):
            hours_ago = i * 4
            started = now - datetime.timedelta(hours=hours_ago)
            status = random.choice(
                ["COMPLETED"] * 8 + ["FAILED"] + ["RUNNING"]
                if i == 0
                else ["COMPLETED"] * 9 + ["FAILED"]
            )
            completed = (
                started + datetime.timedelta(seconds=random.uniform(0.5, 5.0))
                if status == "COMPLETED"
                else None
            )

            partition = None
            partition_id = None
            if schedule_obj is not None:
                p_key = partition_key_for(schedule_obj, started)
                cache_key = (feed_obj["id"], p_key.isoformat())
                if cache_key not in partition_cache:
                    w_start, w_end = partition_window(schedule_obj, p_key)
                    p_status = (
                        "MATERIALIZED"
                        if status == "COMPLETED"
                        else ("FAILED" if status == "FAILED" else "PENDING")
                    )
                    partition = client.create_feed_partition(
                        feed_id=uuid.UUID(feed_obj["id"]),
                        partition_key=p_key,
                        window_start=w_start,
                        window_end=w_end,
                        status=p_status,
                    )
                    partition_cache[cache_key] = partition
                else:
                    partition = partition_cache[cache_key]
                partition_id = uuid.UUID(partition["id"])

            run = client.create_feed_run(
                feed_id=uuid.UUID(feed_obj["id"]),
                partition_id=partition_id,
                status=status,
                records_fetched=random.randint(50, 500) if status == "COMPLETED" else None,
                started_at=started,
                completed_at=completed,
                error_message="Connection timeout" if status == "FAILED" else None,
            )
            feed_runs_by_feed[feed_obj["id"]].append(run)

    print("Creating provider asset group attribute data...")
    # --- Provider Asset Group Attribute data for MATERIALIZED partitions ---
    ref_prices_seed = {
        "BTC": 67500.0,
        "ETH": 3400.0,
        "SOL": 145.0,
        "ADA": 0.45,
        "XRP": 0.52,
        "DOGE": 0.12,
        "AVAX": 35.0,
        "LINK": 14.0,
        "DOT": 7.20,
        "MATIC": 0.58,
        "ATOM": 9.50,
        "UNI": 7.80,
        "APT": 8.90,
        "ARB": 1.15,
        "OP": 1.85,
        "NEAR": 5.20,
        "FTM": 0.42,
        "AAVE": 95.0,
        "MKR": 1450.0,
        "SNX": 2.80,
        "CRV": 0.55,
        "LDO": 2.10,
        "INJ": 22.0,
        "SUI": 1.35,
        "SEI": 0.38,
        "TIA": 8.50,
        "JUP": 0.85,
        "PENDLE": 4.60,
    }

    paga_batch = []
    paga_count = 0
    for cache_key, partition_obj in partition_cache.items():
        if partition_obj["status"] != "MATERIALIZED":
            continue
        feed_id_key = cache_key[0]
        feed_for_partition = next((f for f in all_feeds if f["id"] == feed_id_key), None)
        if (
            feed_for_partition is None
            or feed_for_partition.get("output_table") != "provider_asset_group_attribute"
        ):
            continue
        w_start = datetime.datetime.fromisoformat(partition_obj["window_start"])
        w_end = datetime.datetime.fromisoformat(partition_obj["window_end"])
        window_secs = (w_end - w_start).total_seconds()
        ts = w_start + datetime.timedelta(seconds=window_secs * 0.5 + random.uniform(-0.5, 0.5))

        for grp in all_groups:
            for attr in all_attributes:
                if attr["name"] == "close":
                    base = 100.0
                    for asset_id_str, smg in single_member_groups.items():
                        if smg["id"] == grp["id"]:
                            sym_for_price = next(
                                (s for s, a in asset_by_symbol.items() if a["id"] == asset_id_str),
                                None,
                            )
                            if sym_for_price:
                                base = ref_prices_seed.get(sym_for_price, 100.0)
                            break
                    value = round(base * (1 + random.uniform(-0.02, 0.02)), 4)
                elif attr["name"] == "spread":
                    value = round(random.uniform(-500, 500), 4)
                elif attr["name"] == "z_score":
                    value = round(random.uniform(-3.0, 3.0), 4)
                elif attr["name"] == "rsi":
                    value = round(random.uniform(20.0, 80.0), 4)
                else:
                    value = round(random.uniform(0, 100), 4)
                paga_batch.append(
                    {
                        "timestamp": ts,
                        "provider_asset_group_id": uuid.UUID(grp["id"]),
                        "attribute_id": uuid.UUID(attr["id"]),
                        "attribute_value": value,
                    }
                )
                paga_count += 1
                # Flush in batches of 1000
                if len(paga_batch) >= 1000:
                    client.batch_create_paga(paga_batch)
                    paga_batch = []
    if paga_batch:
        client.batch_create_paga(paga_batch)

    print("Creating strategies...")
    # --- Strategies ---
    from ascent.strategies.examples.momentum import momentum_strategy
    from ascent.strategies.examples.pairs import pairs_strategy

    pairs_schema = pairs_strategy.parameter_schema()
    momentum_schema = momentum_strategy.parameter_schema()

    strategies_data = [
        (
            "BTC-ETH Pairs",
            "Pairs trading BTC/ETH spread",
            "PAIRS_TRADING",
            "ascent.strategies.examples.pairs:pairs_strategy",
            portfolio_main["id"],
            {
                "lookback": 60,
                "entry_z": 2.0,
                "exit_z": 0.5,
                "hedge_ratio_method": "ols",
                "max_position_size": 1.0,
            },
            pairs_schema,
            [feed_market, feed_ou, feed_half_life, feed_spread],
        ),
        (
            "SOL Momentum",
            "Momentum strategy on SOL/USD",
            "MOMENTUM",
            "ascent.strategies.examples.momentum:momentum_strategy",
            portfolio_main["id"],
            {
                "fast_period": 12,
                "slow_period": 26,
                "ma_type": "ema",
                "timeframe": "4h",
                "risk_per_trade": 0.02,
                "use_trailing_stop": False,
                "trailing_stop_pct": 0.03,
            },
            momentum_schema,
            [feed_market, feed_funding, feed_sentiment, feed_sent_score],
        ),
        (
            "ADA Mean Rev",
            "Mean reversion on ADA/USD",
            "MEAN_REVERSION",
            "ascent.strategies.examples.momentum:momentum_strategy",
            portfolio_main["id"],
            {
                "fast_period": 9,
                "slow_period": 21,
                "ma_type": "sma",
                "timeframe": "1h",
                "risk_per_trade": 0.01,
                "use_trailing_stop": True,
                "trailing_stop_pct": 0.05,
            },
            momentum_schema,
            [feed_market, feed_ou, feed_half_life],
        ),
        (
            "XRP-DOGE Pairs",
            "Pairs trading XRP/DOGE spread",
            "PAIRS_TRADING",
            "ascent.strategies.examples.pairs:pairs_strategy",
            portfolio_main["id"],
            {
                "lookback": 30,
                "entry_z": 1.8,
                "exit_z": 0.3,
                "hedge_ratio_method": "tls",
                "max_position_size": 2.0,
            },
            pairs_schema,
            [feed_market, feed_orderbook, feed_funding, feed_ou, feed_spread, feed_half_life],
        ),
        (
            "AVAX Momentum (Coinbase)",
            "Momentum strategy on AVAX/USD via Coinbase",
            "MOMENTUM",
            "ascent.strategies.examples.momentum:momentum_strategy",
            portfolio_coinbase["id"],
            {
                "fast_period": 9,
                "slow_period": 21,
                "ma_type": "ema",
                "timeframe": "1h",
                "risk_per_trade": 0.02,
                "use_trailing_stop": False,
                "trailing_stop_pct": 0.03,
            },
            momentum_schema,
            [feed_cb_market, feed_cb_orderbook],
        ),
        (
            "LINK Mean Rev (Coinbase)",
            "Mean reversion on LINK/USD via Coinbase",
            "MEAN_REVERSION",
            "ascent.strategies.examples.pairs:pairs_strategy",
            portfolio_coinbase["id"],
            {
                "lookback": 14,
                "entry_z": 2.0,
                "exit_z": 0.5,
                "hedge_ratio_method": "kalman",
                "max_position_size": 0.5,
            },
            pairs_schema,
            [feed_cb_market, feed_sentiment, feed_sent_score],
        ),
    ]
    strategies = []
    for name, desc, st_sym, ref, pid, params, schema, feeds in strategies_data:
        s = client.create_strategy(
            name=name,
            description=desc,
            strategy_type_id=uuid.UUID(strategy_type_by_symbol[st_sym]["id"]),
            strategy_ref=ref,
            portfolio_id=uuid.UUID(pid),
            parameters=params,
            parameter_schema=schema,
        )
        strategies.append((s, feeds))

    # --- Strategy-Feed links ---
    for s, feeds in strategies:
        for order, feed_obj in enumerate(feeds):
            client.add_strategy_feed(
                uuid.UUID(s["id"]),
                feed_id=uuid.UUID(feed_obj["id"]),
                is_required=True,
                order=order,
            )

    print("Creating strategy runs...")
    # --- Strategy Runs ---
    strat_runs_by_strategy = {}
    for s, _ in strategies:
        strat_runs_by_strategy[s["id"]] = []
        for i in range(100):
            hours_ago = i * 3
            started = now - datetime.timedelta(hours=hours_ago, minutes=random.randint(0, 59))
            status_roll = random.random()
            if i == 0 and random.random() < 0.3:
                status = "RUNNING"
            elif status_roll < 0.8:
                status = "COMPLETED"
            elif status_roll < 0.95:
                status = "FAILED"
            else:
                status = "PENDING"
            completed = None
            error_msg = None
            if status == "COMPLETED":
                completed = started + datetime.timedelta(seconds=random.uniform(1, 30))
            elif status == "FAILED":
                completed = started + datetime.timedelta(seconds=random.uniform(0.5, 5))
                error_msg = random.choice(
                    [
                        "Timeout connecting to Redis",
                        "Insufficient data for lookback window",
                        "Portfolio limit exceeded",
                        "Feed data stale: last update > 5m ago",
                    ]
                )
            sr = client.create_strategy_run(
                strategy_id=uuid.UUID(s["id"]),
                status=status,
                started_at=started,
                completed_at=completed,
                error_message=error_msg,
            )
            strat_runs_by_strategy[s["id"]].append(sr)

    # --- Strategy Run ↔ Feed Run links ---
    link_count = 0
    for s, feeds in strategies:
        strategy_feed_ids = {f["id"] for f in feeds}
        child_ids = set()
        for child_id, parent_id in feed_deps:
            if child_id in strategy_feed_ids and parent_id in strategy_feed_ids:
                child_ids.add(parent_id)
        leaf_feed_ids = [f["id"] for f in feeds if f["id"] not in child_ids]

        for sr in strat_runs_by_strategy[s["id"]]:
            if sr["status"] == "PENDING":
                continue

            sr_started = datetime.datetime.fromisoformat(sr["started_at"])
            linked = []
            for feed_obj in feeds:
                feed_runs = feed_runs_by_feed.get(feed_obj["id"], [])
                best = None
                for fr in feed_runs:
                    fr_started = datetime.datetime.fromisoformat(fr["started_at"])
                    if fr_started <= sr_started:
                        best = fr
                        break
                if best:
                    linked.append((feed_obj["id"], best))

            if not linked:
                continue

            trigger_candidates = [fid for fid, _ in linked if fid in leaf_feed_ids]
            trigger_feed_id = (
                random.choice(trigger_candidates) if trigger_candidates else linked[-1][0]
            )

            for feed_id_str, fr in linked:
                client.create_strategy_run_feed_run(
                    strategy_run_id=uuid.UUID(sr["id"]),
                    feed_run_id=uuid.UUID(fr["id"]),
                    feed_id=uuid.UUID(feed_id_str),
                    is_trigger=(feed_id_str == trigger_feed_id),
                )
                link_count += 1

    print("Creating trades...")
    # --- Trades ---
    strategy_objs = [s for s, _ in strategies]
    strategy_pairs = {
        0: [("BTC", "USD"), ("ETH", "USD")],
        1: [("SOL", "USD")],
        2: [("ADA", "USD")],
        3: [("XRP", "USD"), ("DOGE", "USD")],
        4: [("AVAX", "USD")],
        5: [("LINK", "USD")],
    }
    ref_prices = {
        "BTC": 67500,
        "ETH": 3400,
        "SOL": 145,
        "ADA": 0.45,
        "XRP": 0.52,
        "DOGE": 0.12,
        "AVAX": 35,
        "LINK": 14,
    }

    all_trades = []
    for strat_idx, strat in enumerate(strategy_objs):
        pairs = strategy_pairs[strat_idx]
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

            is_paper = strat.get("portfolio_id") == portfolio_paper.get("id")

            legs = []
            total_pnl = 0.0
            for pair_idx, (from_sym, to_sym) in enumerate(pairs):
                base_price = ref_prices.get(from_sym, 100)
                noise = base_price * random.uniform(-0.05, 0.05)
                entry_price = round(base_price + noise, 2)
                direction = (
                    random.choice(["LONG", "SHORT"])
                    if not is_pairs
                    else ("LONG" if pair_idx == 0 else "SHORT")
                )
                quantity = round(random.uniform(0.01, 10.0), 4)

                exit_price = None
                realized_pnl = None
                if trade_status["symbol"] == "CLOSED":
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

                legs.append(
                    {
                        "from_asset_id": uuid.UUID(asset_by_symbol[from_sym]["id"]),
                        "to_asset_id": uuid.UUID(asset_by_symbol[to_sym]["id"]),
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
                portfolio_id=uuid.UUID(strat.get("portfolio_id", portfolio_main["id"])),
                is_paper=is_paper,
                entry_at=entry_at,
                parameters={"seed_trade": True, "trade_index": t},
                legs=legs,
            )

            # Update PnL fields
            update_kwargs = {"total_fees": round(random.uniform(0.5, 25.0), 2)}
            if trade_status["symbol"] == "CLOSED":
                update_kwargs["total_realized_pnl"] = round(total_pnl, 2)
                update_kwargs["exit_at"] = exit_at
                update_kwargs["close_reason"] = close_reason
            if trade_status["symbol"] == "OPEN":
                update_kwargs["total_unrealized_pnl"] = round(random.uniform(-500, 500), 2)
            if trade_status["symbol"] == "CANCELLED":
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

            if trade_status["symbol"] == "CANCELLED":
                # PENDING → CANCELLED
                close_ts = entry_at + datetime.timedelta(minutes=30)
                client.add_trade_status(
                    trade_id,
                    trade_status_type_id=uuid.UUID(status_map["CANCELLED"]["id"]),
                    timestamp=close_ts,
                )
            else:
                # PENDING → OPENING → OPEN
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

                if trade_status["symbol"] == "CLOSED":
                    # OPEN → CLOSING → CLOSED
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

    print("Creating trade conditions and snapshots...")
    # --- Trade Conditions & Snapshots (for a subset of trades) ---
    for trade in all_trades[:20]:
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

        # Data series reference
        first_pair = strategy_pairs[all_trades.index(trade) % len(strategy_pairs)]
        first_asset_id = asset_by_symbol[first_pair[0][0]]["id"]
        ds_group = single_member_groups.get(first_asset_id)
        if ds_group:
            client.add_trade_data_series(
                trade_id,
                attribute_id=uuid.UUID(attr_close["id"]),
                label="Close Price",
                data_source="GROUP_ATTRIBUTE",
                provider_asset_group_id=uuid.UUID(ds_group["id"]),
            )

        # Entry snapshot
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

    print("Creating orders...")
    # --- Orders (for a subset of trades) ---
    # Map portfolio to exchange
    portfolio_exchange_map = {
        portfolio_main["id"]: kraken_exchange["id"],
        portfolio_paper["id"]: kraken_exchange["id"],
        portfolio_coinbase["id"]: coinbase_exchange["id"],
    }
    for trade in all_trades[:30]:
        trade_entry_at = (
            datetime.datetime.fromisoformat(trade["entry_at"]) if trade.get("entry_at") else now
        )
        trade_exit_at = (
            datetime.datetime.fromisoformat(trade["exit_at"]) if trade.get("exit_at") else None
        )

        strat_idx = next(
            (i for i, s in enumerate(strategy_objs) if s["id"] == trade.get("strategy_id")),
            0,
        )
        pairs = strategy_pairs.get(strat_idx, [("BTC", "USD")])
        trade_exchange_id = portfolio_exchange_map.get(
            trade.get("portfolio_id"), kraken_exchange["id"]
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

            entry_order = client.create_order(
                timestamp=trade_entry_at,
                order_type_id=uuid.UUID(order_type_by_symbol["MARKET"]["id"]),
                side="BUY" if direction == "LONG" else "SELL",
                exchange_id=uuid.UUID(trade_exchange_id),
                portfolio_id=uuid.UUID(trade.get("portfolio_id", portfolio_main["id"])),
                from_asset_id=uuid.UUID(asset_by_symbol[from_sym]["id"]),
                to_asset_id=uuid.UUID(asset_by_symbol[to_sym]["id"]),
                quantity=quantity,
                price=entry_price,
                time_in_force="GTC",
            )
            entry_order_id = uuid.UUID(entry_order["id"])

            client.add_order_status(
                entry_order_id,
                order_status_type_id=uuid.UUID(order_status_map["SUBMITTED"]["id"]),
                timestamp=trade_entry_at,
            )
            client.add_order_status(
                entry_order_id,
                order_status_type_id=uuid.UUID(order_status_map["ACCEPTED"]["id"]),
                timestamp=trade_entry_at + datetime.timedelta(seconds=1),
            )
            client.add_order_status(
                entry_order_id,
                order_status_type_id=uuid.UUID(order_status_map["FILLED"]["id"]),
                timestamp=trade_entry_at + datetime.timedelta(seconds=2),
            )

            # Exit order if trade is closed
            if trade_exit_at and trade.get("close_reason"):
                pnl_pct = random.uniform(-0.08, 0.12)
                exit_price = (
                    round(entry_price * (1 + pnl_pct), 2)
                    if direction == "LONG"
                    else round(entry_price * (1 - pnl_pct), 2)
                )

                exit_order = client.create_order(
                    timestamp=trade_exit_at,
                    order_type_id=uuid.UUID(order_type_by_symbol["MARKET"]["id"]),
                    side="SELL" if direction == "LONG" else "BUY",
                    exchange_id=uuid.UUID(trade_exchange_id),
                    portfolio_id=uuid.UUID(trade.get("portfolio_id", portfolio_main["id"])),
                    from_asset_id=uuid.UUID(asset_by_symbol[from_sym]["id"]),
                    to_asset_id=uuid.UUID(asset_by_symbol[to_sym]["id"]),
                    quantity=quantity,
                    price=exit_price,
                    time_in_force="GTC",
                )
                exit_order_id = uuid.UUID(exit_order["id"])

                client.add_order_status(
                    exit_order_id,
                    order_status_type_id=uuid.UUID(order_status_map["SUBMITTED"]["id"]),
                    timestamp=trade_exit_at,
                )
                client.add_order_status(
                    exit_order_id,
                    order_status_type_id=uuid.UUID(order_status_map["ACCEPTED"]["id"]),
                    timestamp=trade_exit_at + datetime.timedelta(seconds=1),
                )
                client.add_order_status(
                    exit_order_id,
                    order_status_type_id=uuid.UUID(order_status_map["FILLED"]["id"]),
                    timestamp=trade_exit_at + datetime.timedelta(seconds=2),
                )

    client.close()

    # Print summary
    print("Seeded successfully:")
    print(f"  4 asset types, {len(assets)} assets")
    print(f"  {len(meta)} metadata types")
    print(f"  {len(feed_type_defs)} feed types, {len(all_feeds)} feeds")
    print(
        f"  {len(all_groups)} asset groups ({len(single_member_groups)} single-member, {len(pair_groups)} pairs, {len(basket_groups)} baskets)"
    )
    print(f"  {paga_count} provider_asset_group_attribute rows")
    print(f"  {len(strategy_objs)} strategies")
    print(f"  {link_count} strategy-run ↔ feed-run links")
    print(f"  {len(all_trades)} trades")
    print("  2 portfolios, 1 provider")
