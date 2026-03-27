import uuid

import cyclopts

seed = cyclopts.App(name="seed", help="Seed the database with sample data.")


@seed.command()
def run(
    *,
    database_url: str = "postgresql://localhost:5432/ascent",
    server_url: str = "http://localhost:8000",
    drop: bool = False,
):
    """Load fake data into the database for UI testing.

    Parameters
    ----------
    database_url
        PostgreSQL connection string.
    server_url
        Base URL of the running Ascent server (used to reset the connection pool after drop).
    drop
        Drop and recreate all tables before seeding.
    """
    import datetime
    import random

    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from ascent.database.models import (
        Asset,
        AssetMetadata,
        AssetType,
        AssetTypeMetadata,
        Attribute,
        Base,
        FeedDependency,
        FeedPartition,
        FeedRun,
        FeedType,
        Metadata,
        Order,
        OrderStatus,
        OrderStatusType,
        OrderType,
        Portfolio,
        Provider,
        ProviderAssetAttribute,
        ProviderAssetGroup,
        ProviderAssetGroupAttribute,
        ProviderAssetGroupMember,
        ProviderMetadata,
        ProviderType,
        ProviderTypeMetadata,
        Strategy,
        StrategyFeed,
        StrategyRun,
        StrategyRunFeedRun,
        StrategyType,
        Trade,
        TradeCondition,
        TradeDataSeries,
        TradeLeg,
        TradeSnapshot,
        TradeStatus,
        TradeStatusType,
    )
    from ascent.database.models import (
        Feed as FeedModel,
    )

    engine = create_engine(database_url)

    if drop:
        print("Dropping all tables...")
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            # Restore default grants (required after schema recreation)
            conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
            # Re-enable TimescaleDB extension in the fresh schema
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
            conn.commit()

    print("Creating tables...")
    Base.metadata.create_all(bind=engine)

    if drop:
        # Tell the running server to dispose its stale connection pool
        import urllib.request

        try:
            req = urllib.request.Request(f"{server_url}/api/admin/reset-pool", method="POST")
            urllib.request.urlopen(req, timeout=5)
            print("Server connection pool reset.")
        except Exception:
            print(
                "Warning: Could not reach server to reset pool. Restart it manually if you see 500 errors."
            )

    with Session(engine) as db:
        # Check if data already exists
        existing = db.query(AssetType).first()
        if existing:
            print("Database already has data. Use --drop to reset first.")
            return

        # --- Type tables ---
        asset_types = [
            AssetType(name="Cryptocurrency", description="Digital currency"),
            AssetType(name="Fiat Currency", description="Government-issued currency"),
            AssetType(name="Stock", description="Equity share"),
        ]
        db.add_all(asset_types)
        db.flush()

        provider_types = [
            ProviderType(name="Exchange", description="Cryptocurrency or stock exchange"),
            ProviderType(name="Data Vendor", description="Market data provider"),
        ]
        db.add_all(provider_types)
        db.flush()

        strategy_types = [
            StrategyType(
                symbol="PAIRS_TRADING",
                name="Pairs Trading",
                description="Statistical arbitrage between correlated assets",
            ),
            StrategyType(
                symbol="MOMENTUM", name="Momentum", description="Trend-following strategy"
            ),
            StrategyType(
                symbol="MEAN_REVERSION",
                name="Mean Reversion",
                description="Strategy based on price reverting to the mean",
            ),
        ]
        db.add_all(strategy_types)
        db.flush()

        trade_status_types = [
            TradeStatusType(symbol="PENDING", name="Pending", description="Trade is pending entry"),
            TradeStatusType(symbol="OPEN", name="Open", description="Trade is currently open"),
            TradeStatusType(symbol="CLOSED", name="Closed", description="Trade has been closed"),
            TradeStatusType(
                symbol="CANCELLED", name="Cancelled", description="Trade was cancelled"
            ),
        ]
        db.add_all(trade_status_types)
        db.flush()
        status_map = {s.symbol: s for s in trade_status_types}

        order_types = [
            OrderType(symbol="MARKET", name="Market", description="Market order"),
            OrderType(symbol="LIMIT", name="Limit", description="Limit order"),
            OrderType(symbol="STOP", name="Stop", description="Stop order"),
        ]
        db.add_all(order_types)
        db.flush()

        order_status_types = [
            OrderStatusType(symbol="SUBMITTED", name="Submitted", description="Order submitted"),
            OrderStatusType(
                symbol="ACCEPTED", name="Accepted", description="Order accepted by exchange"
            ),
            OrderStatusType(symbol="FILLED", name="Filled", description="Order fully filled"),
            OrderStatusType(symbol="REJECTED", name="Rejected", description="Order rejected"),
            OrderStatusType(symbol="CANCELLED", name="Cancelled", description="Order cancelled"),
        ]
        db.add_all(order_status_types)
        db.flush()
        order_status_map = {s.symbol: s for s in order_status_types}

        # --- Assets ---
        usd = Asset(asset_type_id=asset_types[1].id, name="US Dollar", symbol="USD")
        btc = Asset(asset_type_id=asset_types[0].id, name="Bitcoin", symbol="BTC")
        eth = Asset(asset_type_id=asset_types[0].id, name="Ethereum", symbol="ETH")
        sol = Asset(asset_type_id=asset_types[0].id, name="Solana", symbol="SOL")
        ada = Asset(asset_type_id=asset_types[0].id, name="Cardano", symbol="ADA")
        xrp = Asset(asset_type_id=asset_types[0].id, name="Ripple", symbol="XRP")
        doge = Asset(asset_type_id=asset_types[0].id, name="Dogecoin", symbol="DOGE")
        avax = Asset(asset_type_id=asset_types[0].id, name="Avalanche", symbol="AVAX")
        link = Asset(asset_type_id=asset_types[0].id, name="Chainlink", symbol="LINK")
        dot = Asset(asset_type_id=asset_types[0].id, name="Polkadot", symbol="DOT")
        matic = Asset(asset_type_id=asset_types[0].id, name="Polygon", symbol="MATIC")
        atom = Asset(asset_type_id=asset_types[0].id, name="Cosmos", symbol="ATOM")
        uni = Asset(asset_type_id=asset_types[0].id, name="Uniswap", symbol="UNI")
        apt = Asset(asset_type_id=asset_types[0].id, name="Aptos", symbol="APT")
        arb = Asset(asset_type_id=asset_types[0].id, name="Arbitrum", symbol="ARB")
        op = Asset(asset_type_id=asset_types[0].id, name="Optimism", symbol="OP")
        near = Asset(asset_type_id=asset_types[0].id, name="NEAR Protocol", symbol="NEAR")
        ftm = Asset(asset_type_id=asset_types[0].id, name="Fantom", symbol="FTM")
        aave = Asset(asset_type_id=asset_types[0].id, name="Aave", symbol="AAVE")
        mkr = Asset(asset_type_id=asset_types[0].id, name="Maker", symbol="MKR")
        snx = Asset(asset_type_id=asset_types[0].id, name="Synthetix", symbol="SNX")
        crv = Asset(asset_type_id=asset_types[0].id, name="Curve", symbol="CRV")
        ldo = Asset(asset_type_id=asset_types[0].id, name="Lido DAO", symbol="LDO")
        inj = Asset(asset_type_id=asset_types[0].id, name="Injective", symbol="INJ")
        sui = Asset(asset_type_id=asset_types[0].id, name="Sui", symbol="SUI")
        sei = Asset(asset_type_id=asset_types[0].id, name="Sei", symbol="SEI")
        tia = Asset(asset_type_id=asset_types[0].id, name="Celestia", symbol="TIA")
        jup = Asset(asset_type_id=asset_types[0].id, name="Jupiter", symbol="JUP")
        pendle = Asset(asset_type_id=asset_types[0].id, name="Pendle", symbol="PENDLE")
        assets = [
            usd,
            btc,
            eth,
            sol,
            ada,
            xrp,
            doge,
            avax,
            link,
            dot,
            matic,
            atom,
            uni,
            apt,
            arb,
            op,
            near,
            ftm,
            aave,
            mkr,
            snx,
            crv,
            ldo,
            inj,
            sui,
            sei,
            tia,
            jup,
            pendle,
        ]
        db.add_all(assets)
        db.flush()

        # --- Provider ---
        provider = Provider(
            provider_type_id=provider_types[0].id, name="Kraken", description="Kraken Exchange"
        )
        db.add(provider)
        db.flush()

        # --- Attributes ---
        attr_close = Attribute(name="close", description="Close price")
        attr_spread = Attribute(name="spread", description="Price spread between correlated assets")
        attr_zscore = Attribute(name="z_score", description="Z-score of the spread")
        attr_rsi = Attribute(name="rsi", description="Relative Strength Index")
        attributes = [attr_close, attr_spread, attr_zscore, attr_rsi]
        db.add_all(attributes)
        db.flush()

        now = datetime.datetime.now(datetime.UTC)

        # --- Metadata types ---
        meta_market_cap = Metadata(
            name="market_cap", description="Market capitalization in USD", value_type="number"
        )
        meta_sector = Metadata(
            name="sector", description="Industry sector classification", value_type="string"
        )
        meta_circulating_supply = Metadata(
            name="circulating_supply",
            description="Circulating supply of the asset",
            value_type="number",
        )
        meta_max_supply = Metadata(
            name="max_supply", description="Maximum supply of the asset", value_type="number"
        )
        meta_launch_date = Metadata(
            name="launch_date", description="Date the asset was launched", value_type="date"
        )
        meta_is_stablecoin = Metadata(
            name="is_stablecoin",
            description="Whether the asset is a stablecoin",
            value_type="boolean",
        )
        meta_consensus = Metadata(
            name="consensus_mechanism",
            description="Consensus mechanism (e.g. PoW, PoS)",
            value_type="string",
        )
        meta_whitepaper = Metadata(
            name="whitepaper_url", description="URL to the project whitepaper", value_type="string"
        )
        meta_iso_code = Metadata(
            name="iso_currency_code", description="ISO 4217 currency code", value_type="string"
        )
        meta_country = Metadata(
            name="issuing_country",
            description="Country that issues the currency",
            value_type="string",
        )
        meta_api_key = Metadata(
            name="api_key_name",
            description="Name of the API key environment variable",
            value_type="string",
        )
        meta_rate_limit = Metadata(
            name="rate_limit", description="API rate limit (requests/minute)", value_type="number"
        )
        meta_supports_websocket = Metadata(
            name="supports_websocket",
            description="Whether the provider supports WebSocket connections",
            value_type="boolean",
        )
        meta_supported_markets = Metadata(
            name="supported_markets",
            description="JSON list of supported market types",
            value_type="json",
        )
        meta_fee_schedule = Metadata(
            name="fee_schedule", description="Fee schedule as JSON object", value_type="json"
        )
        metadata_types = [
            meta_market_cap,
            meta_sector,
            meta_circulating_supply,
            meta_max_supply,
            meta_launch_date,
            meta_is_stablecoin,
            meta_consensus,
            meta_whitepaper,
            meta_iso_code,
            meta_country,
            meta_api_key,
            meta_rate_limit,
            meta_supports_websocket,
            meta_supported_markets,
            meta_fee_schedule,
        ]
        db.add_all(metadata_types)
        db.flush()

        # --- Asset type metadata field definitions ---
        # Cryptocurrency fields
        crypto_type = asset_types[0]
        crypto_fields = [
            AssetTypeMetadata(
                asset_type_id=crypto_type.id,
                metadata_id=meta_market_cap.id,
                is_required=True,
                display_order=0,
            ),
            AssetTypeMetadata(
                asset_type_id=crypto_type.id,
                metadata_id=meta_circulating_supply.id,
                is_required=True,
                display_order=1,
            ),
            AssetTypeMetadata(
                asset_type_id=crypto_type.id,
                metadata_id=meta_max_supply.id,
                is_required=False,
                display_order=2,
            ),
            AssetTypeMetadata(
                asset_type_id=crypto_type.id,
                metadata_id=meta_launch_date.id,
                is_required=False,
                display_order=3,
            ),
            AssetTypeMetadata(
                asset_type_id=crypto_type.id,
                metadata_id=meta_is_stablecoin.id,
                is_required=True,
                display_order=4,
            ),
            AssetTypeMetadata(
                asset_type_id=crypto_type.id,
                metadata_id=meta_consensus.id,
                is_required=False,
                display_order=5,
            ),
            AssetTypeMetadata(
                asset_type_id=crypto_type.id,
                metadata_id=meta_sector.id,
                is_required=False,
                display_order=6,
            ),
            AssetTypeMetadata(
                asset_type_id=crypto_type.id,
                metadata_id=meta_whitepaper.id,
                is_required=False,
                display_order=7,
            ),
        ]
        db.add_all(crypto_fields)

        # Fiat Currency fields
        fiat_type = asset_types[1]
        fiat_fields = [
            AssetTypeMetadata(
                asset_type_id=fiat_type.id,
                metadata_id=meta_iso_code.id,
                is_required=True,
                display_order=0,
            ),
            AssetTypeMetadata(
                asset_type_id=fiat_type.id,
                metadata_id=meta_country.id,
                is_required=True,
                display_order=1,
            ),
        ]
        db.add_all(fiat_fields)

        # Stock fields
        stock_type = asset_types[2]
        stock_fields = [
            AssetTypeMetadata(
                asset_type_id=stock_type.id,
                metadata_id=meta_market_cap.id,
                is_required=True,
                display_order=0,
            ),
            AssetTypeMetadata(
                asset_type_id=stock_type.id,
                metadata_id=meta_sector.id,
                is_required=True,
                display_order=1,
            ),
        ]
        db.add_all(stock_fields)
        db.flush()

        # --- Provider type metadata field definitions ---
        # Exchange fields
        exchange_type = provider_types[0]
        exchange_fields = [
            ProviderTypeMetadata(
                provider_type_id=exchange_type.id,
                metadata_id=meta_api_key.id,
                is_required=True,
                display_order=0,
            ),
            ProviderTypeMetadata(
                provider_type_id=exchange_type.id,
                metadata_id=meta_rate_limit.id,
                is_required=True,
                display_order=1,
            ),
            ProviderTypeMetadata(
                provider_type_id=exchange_type.id,
                metadata_id=meta_supports_websocket.id,
                is_required=False,
                display_order=2,
            ),
            ProviderTypeMetadata(
                provider_type_id=exchange_type.id,
                metadata_id=meta_supported_markets.id,
                is_required=False,
                display_order=3,
            ),
            ProviderTypeMetadata(
                provider_type_id=exchange_type.id,
                metadata_id=meta_fee_schedule.id,
                is_required=False,
                display_order=4,
            ),
        ]
        db.add_all(exchange_fields)

        # Data Vendor fields
        vendor_type = provider_types[1]
        vendor_fields = [
            ProviderTypeMetadata(
                provider_type_id=vendor_type.id,
                metadata_id=meta_api_key.id,
                is_required=True,
                display_order=0,
            ),
            ProviderTypeMetadata(
                provider_type_id=vendor_type.id,
                metadata_id=meta_rate_limit.id,
                is_required=True,
                display_order=1,
            ),
            ProviderTypeMetadata(
                provider_type_id=vendor_type.id,
                metadata_id=meta_supports_websocket.id,
                is_required=False,
                display_order=2,
            ),
        ]
        db.add_all(vendor_fields)
        db.flush()

        # --- Sample asset metadata (temporal entries) ---
        asset_metadata_data = [
            (btc, meta_market_cap, 1_320_000_000_000),
            (btc, meta_circulating_supply, 19_700_000),
            (btc, meta_max_supply, 21_000_000),
            (btc, meta_launch_date, "2009-01-03"),
            (btc, meta_is_stablecoin, False),
            (btc, meta_consensus, "Proof of Work"),
            (btc, meta_sector, "Store of Value"),
            (eth, meta_market_cap, 410_000_000_000),
            (eth, meta_circulating_supply, 120_200_000),
            (eth, meta_max_supply, None),
            (eth, meta_launch_date, "2015-07-30"),
            (eth, meta_is_stablecoin, False),
            (eth, meta_consensus, "Proof of Stake"),
            (eth, meta_sector, "Smart Contract Platform"),
            (sol, meta_market_cap, 68_000_000_000),
            (sol, meta_circulating_supply, 440_000_000),
            (sol, meta_is_stablecoin, False),
            (sol, meta_consensus, "Proof of History"),
            (usd, meta_iso_code, "USD"),
            (usd, meta_country, "United States"),
        ]
        for asset_obj, meta_type, value in asset_metadata_data:
            if value is not None:
                db.add(
                    AssetMetadata(
                        timestamp=now - datetime.timedelta(days=30),
                        asset_id=asset_obj.id,
                        metadata_id=meta_type.id,
                        value=value,
                    )
                )
                db.flush()

        # --- Sample provider metadata (temporal entries) ---
        provider_metadata_data = [
            (provider, meta_api_key, "KRAKEN_API_KEY"),
            (provider, meta_rate_limit, 60),
            (provider, meta_supports_websocket, True),
            (
                provider,
                meta_supported_markets,
                ["spot", "futures", "margin"],
            ),
            (
                provider,
                meta_fee_schedule,
                {"maker": 0.0016, "taker": 0.0026, "withdrawal": {"BTC": 0.00015}},
            ),
        ]
        for prov_obj, meta_type, value in provider_metadata_data:
            db.add(
                ProviderMetadata(
                    timestamp=now - datetime.timedelta(days=30),
                    provider_id=prov_obj.id,
                    metadata_id=meta_type.id,
                    value=value,
                )
            )
            db.flush()

        # --- Portfolios ---
        portfolio_main = Portfolio(
            name="Main Portfolio",
            description="Primary trading portfolio",
            base_currency_asset_id=usd.id,
            pricing_provider_id=provider.id,
        )
        portfolio_paper = Portfolio(
            name="Paper Trading",
            description="Simulated trading portfolio",
            base_currency_asset_id=usd.id,
            pricing_provider_id=provider.id,
        )
        db.add_all([portfolio_main, portfolio_paper])
        db.flush()

        random.seed(42)

        # --- Asset Groups & Members ---
        # Pairs: BTC/ETH, SOL/AVAX, LINK/DOT, ADA/XRP, UNI/AAVE
        pairs_definitions = [
            ("BTC-ETH", [(btc, usd), (eth, usd)]),
            ("SOL-AVAX", [(sol, usd), (avax, usd)]),
            ("LINK-DOT", [(link, usd), (dot, usd)]),
            ("ADA-XRP", [(ada, usd), (xrp, usd)]),
            ("UNI-AAVE", [(uni, usd), (aave, usd)]),
        ]
        pair_groups = []
        for _label, members in pairs_definitions:
            grp = ProviderAssetGroup()
            db.add(grp)
            db.flush()
            for order, (from_a, to_a) in enumerate(members, 1):
                db.add(
                    ProviderAssetGroupMember(
                        provider_asset_group_id=grp.id,
                        provider_id=provider.id,
                        from_asset_id=from_a.id,
                        to_asset_id=to_a.id,
                        order=order,
                    )
                )
            pair_groups.append(grp)
        db.flush()

        # Baskets: DeFi Blue Chip, L1 Majors
        basket_definitions = [
            (
                "DeFi Blue Chip",
                [(aave, usd), (mkr, usd), (uni, usd), (snx, usd), (crv, usd), (ldo, usd)],
            ),
            (
                "L1 Majors",
                [
                    (eth, usd),
                    (sol, usd),
                    (avax, usd),
                    (dot, usd),
                    (atom, usd),
                    (near, usd),
                    (apt, usd),
                    (sui, usd),
                ],
            ),
        ]
        basket_groups = []
        for _label, members in basket_definitions:
            grp = ProviderAssetGroup()
            db.add(grp)
            db.flush()
            for order, (from_a, to_a) in enumerate(members, 1):
                db.add(
                    ProviderAssetGroupMember(
                        provider_asset_group_id=grp.id,
                        provider_id=provider.id,
                        from_asset_id=from_a.id,
                        to_asset_id=to_a.id,
                        order=order,
                    )
                )
            basket_groups.append(grp)
        db.flush()

        all_groups = pair_groups + basket_groups

        # --- Feeds ---
        # Build a realistic DAG:
        #
        #   market_data (scheduled 60s) ──┬──> spread (triggered)
        #                                 │
        #   orderbook (scheduled 30s) ────┘
        #
        #   sentiment (scheduled 300s) ───> sentiment_score (triggered)
        #
        #   ou_params (external) ──> half_life (triggered)
        #
        #   funding_rates (external)
        #
        # External feeds have no schedule and no upstream dependencies.
        # Their data is published via AscentClient.publish_feed().
        # Strategies consume different subsets, creating varied DAG shapes.

        from ascent.feeds.examples.market import market_data
        from ascent.feeds.examples.ou_params import ou_params

        feed_types = [
            FeedType(symbol="MARKET_DATA", name="Market Data", description="Real-time market data"),
            FeedType(symbol="DERIVED", name="Derived", description="Computed from other feeds"),
            FeedType(
                symbol="ALTERNATIVE", name="Alternative", description="Alternative data sources"
            ),
            FeedType(
                symbol="EXTERNAL",
                name="External",
                description="Data published via the Ascent API by an external process",
            ),
        ]
        db.add_all(feed_types)
        db.flush()

        # --- Root scheduled feeds ---
        feed_market = FeedModel(
            feed_type_id=feed_types[0].id,
            name="Market Data",
            description="Pulls minutely OHLCV pricing data 1s before each minute close.",
            feed_ref="ascent.feeds.examples.market:market_data",
            parameters={"provider_name": "kraken", "attributes": ["close"], "lookback_minutes": 5},
            parameter_schema=market_data.parameter_schema(),
            output_table="provider_asset_attribute",
            schedule={"interval": 60, "offset": -1.0, "start_date": "2024-01-01T00:00:00+00:00"},
            channel="ascent.feed.market_data",
            is_active=True,
        )
        feed_orderbook = FeedModel(
            feed_type_id=feed_types[0].id,
            name="Order Book",
            description="Snapshots top-of-book bid/ask every 30 seconds.",
            feed_ref="ascent.feeds.examples.orderbook:orderbook",
            parameters={"depth": 10, "provider_name": "kraken"},
            output_table="provider_asset_attribute",
            schedule={"interval": 30, "start_date": "2024-01-01T00:00:00+00:00"},
            channel="ascent.feed.orderbook",
            is_active=True,
        )
        feed_sentiment = FeedModel(
            feed_type_id=feed_types[2].id,
            name="Sentiment",
            description="Aggregated social sentiment scores every 5 minutes.",
            feed_ref="ascent.feeds.examples.sentiment:sentiment",
            parameters={"sources": ["twitter", "reddit"]},
            output_table="provider_asset_attribute",
            schedule={"interval": 300, "start_date": "2024-01-01T00:00:00+00:00"},
            channel="ascent.feed.sentiment",
            is_active=True,
        )
        feed_cointegration = FeedModel(
            feed_type_id=feed_types[1].id,
            name="Cointegration",
            description="Cointegration test statistics for asset pair groups every 5 minutes.",
            feed_ref="ascent.feeds.examples.cointegration:cointegration",
            parameters={"test": "engle_granger", "lookback_days": 30},
            output_table="provider_asset_group_attribute",
            schedule={"interval": 300, "start_date": "2024-01-01T00:00:00+00:00"},
            channel="ascent.feed.cointegration",
            is_active=True,
        )
        db.add_all([feed_market, feed_orderbook, feed_sentiment, feed_cointegration])
        db.flush()

        # --- External feeds (no schedule, no upstream dependencies) ---
        # Data published via AscentClient.publish_feed() from external processes.
        feed_ou = FeedModel(
            feed_type_id=feed_types[3].id,  # EXTERNAL
            name="OU Parameters",
            description="Ornstein-Uhlenbeck parameters computed externally.",
            feed_ref="ascent.feeds.examples.ou_params:ou_params",
            parameters={"lookback_days": 60},
            parameter_schema=ou_params.parameter_schema(),
            output_table="provider_asset_group_attribute",
            schedule=None,
            channel="ascent.feed.ou_params",
            is_active=True,
        )
        feed_funding = FeedModel(
            feed_type_id=feed_types[3].id,  # EXTERNAL
            name="Funding Rates",
            description="Perpetual swap funding rates computed externally.",
            feed_ref="ascent.feeds.examples.funding:funding_rates",
            parameters={"exchanges": ["kraken", "binance"]},
            output_table="provider_asset_attribute",
            schedule=None,
            channel="ascent.feed.funding_rates",
            is_active=True,
        )
        db.add_all([feed_ou, feed_funding])
        db.flush()

        # --- Triggered feeds (depend on upstream feeds) ---
        feed_spread = FeedModel(
            feed_type_id=feed_types[1].id,
            name="Spread Analytics",
            description="Computes bid-ask spread metrics from order book and market data.",
            feed_ref="ascent.feeds.examples.spread:spread_analytics",
            parameters={"window": 20},
            output_table="provider_asset_attribute",
            schedule=None,
            channel="ascent.feed.spread",
            is_active=True,
        )
        feed_sent_score = FeedModel(
            feed_type_id=feed_types[1].id,
            name="Sentiment Score",
            description="Normalised sentiment z-score derived from raw sentiment feed.",
            feed_ref="ascent.feeds.examples.sentiment:sentiment_score",
            parameters={"lookback_hours": 24},
            output_table="provider_asset_attribute",
            schedule=None,
            channel="ascent.feed.sentiment_score",
            is_active=True,
        )
        feed_half_life = FeedModel(
            feed_type_id=feed_types[1].id,
            name="Half-Life",
            description="Mean-reversion half-life estimate derived from OU parameters.",
            feed_ref="ascent.feeds.examples.half_life:half_life",
            parameters={"min_samples": 30},
            output_table="provider_asset_group_attribute",
            schedule=None,
            channel="ascent.feed.half_life",
            is_active=True,
        )
        db.add_all([feed_spread, feed_sent_score, feed_half_life])
        db.flush()

        # --- Feed dependencies ---
        # spread <- market_data, orderbook  (dual parent)
        # sentiment_score <- sentiment
        # half_life <- ou_params  (external -> triggered chain)
        # cointegration <- market_data  (scheduled group feed)
        feed_deps = [
            (feed_spread.id, feed_market.id),
            (feed_spread.id, feed_orderbook.id),
            (feed_sent_score.id, feed_sentiment.id),
            (feed_cointegration.id, feed_market.id),
            (feed_half_life.id, feed_ou.id),
        ]
        for child_id, parent_id in feed_deps:
            db.add(FeedDependency(feed_id=child_id, depends_on_feed_id=parent_id))
        db.flush()

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
        ]

        # Build schedule objects for feeds that have one
        feed_schedules: dict[uuid.UUID, Schedule | None] = {}
        for f in all_feeds:
            if f.schedule is not None:
                feed_schedules[f.id] = Schedule(**f.schedule)
            else:
                feed_schedules[f.id] = None

        # Track partitions per feed to avoid duplicates: (feed_id, partition_key) -> FeedPartition
        partition_cache: dict[tuple[uuid.UUID, datetime.datetime], FeedPartition] = {}

        # Collect feed runs keyed by feed_id, sorted by started_at desc
        feed_runs_by_feed: dict[uuid.UUID, list[FeedRun]] = {f.id: [] for f in all_feeds}
        for feed_obj in all_feeds:
            schedule_obj = feed_schedules[feed_obj.id]
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

                # Create or reuse partition for scheduled feeds
                partition = None
                if schedule_obj is not None:
                    p_key = partition_key_for(schedule_obj, started)
                    cache_key = (feed_obj.id, p_key)
                    if cache_key not in partition_cache:
                        w_start, w_end = partition_window(schedule_obj, p_key)
                        p_status = (
                            "MATERIALIZED"
                            if status == "COMPLETED"
                            else ("FAILED" if status == "FAILED" else "PENDING")
                        )
                        partition = FeedPartition(
                            feed_id=feed_obj.id,
                            partition_key=p_key,
                            window_start=w_start,
                            window_end=w_end,
                            status=p_status,
                        )
                        db.add(partition)
                        db.flush()
                        partition_cache[cache_key] = partition
                    else:
                        partition = partition_cache[cache_key]
                        # Update status if this run is better
                        if status == "COMPLETED" and partition.status != "MATERIALIZED":
                            partition.status = "MATERIALIZED"

                run = FeedRun(
                    feed_id=feed_obj.id,
                    partition_id=partition.id if partition else None,
                    status=status,
                    records_fetched=random.randint(50, 500) if status == "COMPLETED" else None,
                    started_at=started,
                    completed_at=completed,
                    error_message="Connection timeout" if status == "FAILED" else None,
                )
                db.add(run)
                feed_runs_by_feed[feed_obj.id].append(run)
        db.flush()

        # --- Provider Asset Attribute data for MATERIALIZED partitions ---
        # Populate actual rows in the output table so the partition data API has data to show.
        # Only for scheduled feeds whose output_table is 'provider_asset_attribute'.
        ref_prices_seed = {
            btc.id: 67500.0,
            eth.id: 3400.0,
            sol.id: 145.0,
            ada.id: 0.45,
            xrp.id: 0.52,
            doge.id: 0.12,
            avax.id: 35.0,
            link.id: 14.0,
            dot.id: 7.20,
            matic.id: 0.58,
            atom.id: 9.50,
            uni.id: 7.80,
            apt.id: 8.90,
            arb.id: 1.15,
            op.id: 1.85,
            near.id: 5.20,
            ftm.id: 0.42,
            aave.id: 95.0,
            mkr.id: 1450.0,
            snx.id: 2.80,
            crv.id: 0.55,
            ldo.id: 2.10,
            inj.id: 22.0,
            sui.id: 1.35,
            sei.id: 0.38,
            tia.id: 8.50,
            jup.id: 0.85,
            pendle.id: 4.60,
        }
        crypto_assets = [
            btc,
            eth,
            sol,
            ada,
            xrp,
            doge,
            avax,
            link,
            dot,
            matic,
            atom,
            uni,
            apt,
            arb,
            op,
            near,
            ftm,
            aave,
            mkr,
            snx,
            crv,
            ldo,
            inj,
            sui,
            sei,
            tia,
            jup,
            pendle,
        ]
        paa_count = 0
        for (feed_id_key, p_key), partition_obj in partition_cache.items():
            if partition_obj.status != "MATERIALIZED":
                continue
            # Only populate for feeds with output_table == 'provider_asset_attribute'
            feed_for_partition = next((f for f in all_feeds if f.id == feed_id_key), None)
            if (
                feed_for_partition is None
                or feed_for_partition.output_table != "provider_asset_attribute"
            ):
                continue
            # One timestamp per partition — each asset gets a row per attribute.
            window_secs = (partition_obj.window_end - partition_obj.window_start).total_seconds()
            ts = partition_obj.window_start + datetime.timedelta(
                seconds=window_secs * 0.5 + random.uniform(-0.5, 0.5)
            )
            for asset in crypto_assets:
                base = ref_prices_seed.get(asset.id, 100.0)
                for attr in attributes:
                    if attr.name == "close":
                        value = round(base * (1 + random.uniform(-0.02, 0.02)), 4)
                    elif attr.name == "spread":
                        value = round(base * random.uniform(0.0005, 0.003), 4)
                    elif attr.name == "z_score":
                        value = round(random.uniform(-3.0, 3.0), 4)
                    elif attr.name == "rsi":
                        value = round(random.uniform(20.0, 80.0), 4)
                    else:
                        value = round(random.uniform(0, 100), 4)
                    db.add(
                        ProviderAssetAttribute(
                            timestamp=ts,
                            provider_id=provider.id,
                            from_asset_id=asset.id,
                            to_asset_id=usd.id,
                            attribute_id=attr.id,
                            attribute_value=value,
                        )
                    )
                    paa_count += 1
        db.flush()

        # --- Provider Asset Group Attribute data for MATERIALIZED group-feed partitions ---
        # Populate rows for feeds whose output_table is 'provider_asset_group_attribute'.
        paga_count = 0
        group_feed_attrs = [attr_spread, attr_zscore]  # group-level attributes
        for (feed_id_key, p_key), partition_obj in partition_cache.items():
            if partition_obj.status != "MATERIALIZED":
                continue
            feed_for_partition = next((f for f in all_feeds if f.id == feed_id_key), None)
            if (
                feed_for_partition is None
                or feed_for_partition.output_table != "provider_asset_group_attribute"
            ):
                continue
            window_secs = (partition_obj.window_end - partition_obj.window_start).total_seconds()
            ts = partition_obj.window_start + datetime.timedelta(
                seconds=window_secs * 0.5 + random.uniform(-0.5, 0.5)
            )
            for grp in all_groups:
                for attr in group_feed_attrs:
                    if attr.name == "spread":
                        value = round(random.uniform(-500, 500), 4)
                    elif attr.name == "z_score":
                        value = round(random.uniform(-3.0, 3.0), 4)
                    else:
                        value = round(random.uniform(0, 100), 4)
                    db.add(
                        ProviderAssetGroupAttribute(
                            timestamp=ts,
                            provider_asset_group_id=grp.id,
                            attribute_id=attr.id,
                            attribute_value=value,
                        )
                    )
                    paga_count += 1
        db.flush()

        # --- Strategies ---
        from ascent.strategies.examples.momentum import momentum_strategy
        from ascent.strategies.examples.pairs import pairs_strategy

        pairs_schema = pairs_strategy.parameter_schema()
        momentum_schema = momentum_strategy.parameter_schema()

        strategies_data = [
            (
                "BTC-ETH Pairs",
                "Pairs trading BTC/ETH spread",
                strategy_types[0].id,
                "ascent.strategies.examples.pairs:pairs_strategy",
                portfolio_main.id,
                {
                    "lookback": 60,
                    "entry_z": 2.0,
                    "exit_z": 0.5,
                    "hedge_ratio_method": "ols",
                    "max_position_size": 1.0,
                },
                pairs_schema,
                # Deep: market_data -> ou_params -> half_life, plus spread (dual-parent)
                [feed_market, feed_ou, feed_half_life, feed_spread],
            ),
            (
                "SOL Momentum",
                "Momentum strategy on SOL/USD",
                strategy_types[1].id,
                "ascent.strategies.examples.momentum:momentum_strategy",
                portfolio_main.id,
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
                # Mixed: scheduled + external + triggered
                [feed_market, feed_funding, feed_sentiment, feed_sent_score],
            ),
            (
                "ADA Mean Rev",
                "Mean reversion on ADA/USD",
                strategy_types[2].id,
                "ascent.strategies.examples.momentum:momentum_strategy",
                portfolio_main.id,
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
                # Deep chain: market_data -> ou_params -> half_life
                [feed_market, feed_ou, feed_half_life],
            ),
            (
                "XRP-DOGE Pairs",
                "Pairs trading XRP/DOGE spread",
                strategy_types[0].id,
                "ascent.strategies.examples.pairs:pairs_strategy",
                portfolio_main.id,
                {
                    "lookback": 30,
                    "entry_z": 1.8,
                    "exit_z": 0.3,
                    "hedge_ratio_method": "tls",
                    "max_position_size": 2.0,
                },
                pairs_schema,
                # Full kitchen sink: scheduled + external + triggered
                [feed_market, feed_orderbook, feed_funding, feed_ou, feed_spread, feed_half_life],
            ),
            (
                "AVAX Momentum",
                "Momentum strategy on AVAX/USD",
                strategy_types[1].id,
                "ascent.strategies.examples.momentum:momentum_strategy",
                portfolio_paper.id,
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
                # Simple: just market_data + orderbook
                [feed_market, feed_orderbook],
            ),
            (
                "LINK Mean Rev",
                "Mean reversion on LINK/USD",
                strategy_types[2].id,
                "ascent.strategies.examples.pairs:pairs_strategy",
                portfolio_paper.id,
                {
                    "lookback": 14,
                    "entry_z": 2.0,
                    "exit_z": 0.5,
                    "hedge_ratio_method": "kalman",
                    "max_position_size": 0.5,
                },
                pairs_schema,
                # Dual branch: market -> ou, sentiment -> sentiment_score
                [feed_market, feed_ou, feed_sentiment, feed_sent_score],
            ),
        ]
        strategies = []
        for name, desc, st_id, ref, pid, params, schema, feeds in strategies_data:
            s = Strategy(
                strategy_type_id=st_id,
                name=name,
                description=desc,
                strategy_ref=ref,
                portfolio_id=pid,
                parameters=params,
                parameter_schema=schema,
                is_active=True,
            )
            db.add(s)
            strategies.append((s, feeds))
        db.flush()

        # --- Strategy-Feed links ---
        for s, feeds in strategies:
            for order, feed_obj in enumerate(feeds):
                db.add(
                    StrategyFeed(
                        strategy_id=s.id,
                        feed_id=feed_obj.id,
                        is_required=True,
                        order=order,
                    )
                )
        db.flush()

        # --- Strategy Runs ---
        # Collect runs per strategy for linking to feed runs below
        strat_runs_by_strategy: dict[uuid.UUID, list[StrategyRun]] = {}
        for s, _ in strategies:
            strat_runs_by_strategy[s.id] = []
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
                sr = StrategyRun(
                    strategy_id=s.id,
                    status=status,
                    started_at=started,
                    completed_at=completed,
                    error_message=error_msg,
                )
                db.add(sr)
                strat_runs_by_strategy[s.id].append(sr)
        db.flush()

        # --- Strategy Run ↔ Feed Run links ---
        # For each strategy run, find the closest feed run per feed and pick a trigger.
        link_count = 0
        for s, feeds in strategies:
            # Determine leaf feeds for this strategy (feeds with no children in this strategy's set)
            strategy_feed_ids = {f.id for f in feeds}
            child_ids = set()
            for child_id, parent_id in feed_deps:
                if child_id in strategy_feed_ids and parent_id in strategy_feed_ids:
                    child_ids.add(parent_id)  # parent has a child in the set
            leaf_feed_ids = [f.id for f in feeds if f.id not in child_ids]

            for sr in strat_runs_by_strategy[s.id]:
                if sr.status == "PENDING":
                    continue

                # Find most recent feed run before this strategy run for each feed
                linked = []
                for feed_obj in feeds:
                    feed_runs = feed_runs_by_feed.get(feed_obj.id, [])
                    best = None
                    for fr in feed_runs:
                        if fr.started_at <= sr.started_at:
                            best = fr
                            break
                    if best:
                        linked.append((feed_obj.id, best))

                if not linked:
                    continue

                # Pick trigger from leaf feeds
                trigger_candidates = [fid for fid, _ in linked if fid in leaf_feed_ids]
                trigger_feed_id = (
                    random.choice(trigger_candidates) if trigger_candidates else linked[-1][0]
                )

                for feed_id, fr in linked:
                    db.add(
                        StrategyRunFeedRun(
                            strategy_run_id=sr.id,
                            feed_run_id=fr.id,
                            feed_id=feed_id,
                            is_trigger=(feed_id == trigger_feed_id),
                        )
                    )
                    link_count += 1
        db.flush()

        # --- Trades ---
        # Unwrap strategy tuples for trade generation
        strategy_objs = [s for s, _ in strategies]

        # Pairs for trades: (from_asset, to_asset) combinations per strategy
        strategy_pairs = {
            0: [(btc, usd), (eth, usd)],  # BTC-ETH Pairs
            1: [(sol, usd)],  # SOL Momentum
            2: [(ada, usd)],  # ADA Mean Rev
            3: [(xrp, usd), (doge, usd)],  # XRP-DOGE Pairs
            4: [(avax, usd)],  # AVAX Momentum
            5: [(link, usd)],  # LINK Mean Rev
        }

        # Reference prices for realistic data
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

                # Decide status
                status_roll = random.random()
                if status_roll < 0.3:
                    trade_status = status_map["OPEN"]
                    exit_at = None
                    close_reason = None
                elif status_roll < 0.95:
                    trade_status = status_map["CLOSED"]
                    hold_hours = random.randint(1, 72)
                    exit_at = entry_at + datetime.timedelta(hours=hold_hours)
                    close_reason = random.choice(
                        ["MODEL_SIGNAL", "STOP_LOSS", "TAKE_PROFIT", "MANUAL"]
                    )
                else:
                    trade_status = status_map["CANCELLED"]
                    exit_at = None
                    close_reason = "MANUAL"

                is_paper = strat.portfolio_id == portfolio_paper.id

                trade = Trade(
                    strategy_id=strat.id,
                    portfolio_id=strat.portfolio_id,
                    is_paper=is_paper,
                    entry_at=entry_at,
                    exit_at=exit_at,
                    close_reason=close_reason,
                    current_status_type_id=trade_status.id,
                    parameters={"seed_trade": True, "trade_index": t},
                )
                db.add(trade)
                db.flush()

                # Create legs
                legs = []
                for pair_idx, (from_asset, to_asset) in enumerate(pairs):
                    price_key = from_asset.symbol
                    base_price = ref_prices.get(price_key, 100)
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
                    if trade_status.symbol == "CLOSED":
                        pnl_pct = random.uniform(-0.08, 0.12)
                        if direction == "LONG":
                            exit_price = round(entry_price * (1 + pnl_pct), 2)
                            realized_pnl = round((exit_price - entry_price) * quantity, 2)
                        else:
                            exit_price = round(entry_price * (1 - pnl_pct), 2)
                            realized_pnl = round((entry_price - exit_price) * quantity, 2)

                    expected_entry = round(entry_price * random.uniform(0.998, 1.002), 2)
                    expected_exit = (
                        round(exit_price * random.uniform(0.998, 1.002), 2) if exit_price else None
                    )

                    leg = TradeLeg(
                        trade_id=trade.id,
                        from_asset_id=from_asset.id,
                        to_asset_id=to_asset.id,
                        direction=direction,
                        quantity=quantity,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        expected_entry_price=expected_entry,
                        expected_exit_price=expected_exit,
                        realized_pnl=realized_pnl,
                    )
                    db.add(leg)
                    legs.append(leg)

                # Aggregate PnL
                total_pnl = sum(l.realized_pnl for l in legs if l.realized_pnl is not None)
                trade.total_realized_pnl = (
                    round(total_pnl, 2) if trade_status.symbol == "CLOSED" else None
                )
                if trade_status.symbol == "OPEN":
                    trade.total_unrealized_pnl = round(random.uniform(-500, 500), 2)
                trade.total_fees = round(random.uniform(0.5, 25.0), 2)

                # Trade statuses (history)
                ts_pending = TradeStatus(
                    timestamp=entry_at - datetime.timedelta(minutes=random.randint(1, 10)),
                    trade_id=trade.id,
                    trade_status_type_id=status_map["PENDING"].id,
                )
                db.add(ts_pending)

                ts_open = TradeStatus(
                    timestamp=entry_at,
                    trade_id=trade.id,
                    trade_status_type_id=status_map["OPEN"].id,
                )
                db.add(ts_open)

                if trade_status.symbol in ("CLOSED", "CANCELLED"):
                    close_ts = exit_at or (entry_at + datetime.timedelta(minutes=30))
                    ts_close = TradeStatus(
                        timestamp=close_ts,
                        trade_id=trade.id,
                        trade_status_type_id=trade_status.id,
                    )
                    db.add(ts_close)

                all_trades.append(trade)

        db.flush()

        # --- Trade Conditions & Snapshots (for a subset of trades) ---
        for trade in all_trades[:20]:
            # Entry condition
            cond = TradeCondition(
                trade_id=trade.id,
                condition_type="ENTRY",
                attribute_id=attr_zscore.id,
                operator=random.choice(["ABOVE", "BELOW", "CROSSES_ABOVE", "CROSSES_BELOW"]),
                threshold_value=round(random.uniform(1.5, 3.0), 2),
                is_met=True,
                met_at=trade.entry_at,
            )
            db.add(cond)

            if trade.close_reason == "STOP_LOSS":
                sl = TradeCondition(
                    trade_id=trade.id,
                    condition_type="STOP_LOSS",
                    attribute_id=attr_close.id,
                    operator="BELOW",
                    threshold_value=round(random.uniform(50, 60000), 2),
                    is_met=trade.exit_at is not None,
                    met_at=trade.exit_at,
                )
                db.add(sl)

            if trade.close_reason == "TAKE_PROFIT":
                tp = TradeCondition(
                    trade_id=trade.id,
                    condition_type="TAKE_PROFIT",
                    attribute_id=attr_close.id,
                    operator="ABOVE",
                    threshold_value=round(random.uniform(50, 70000), 2),
                    is_met=trade.exit_at is not None,
                    met_at=trade.exit_at,
                )
                db.add(tp)

            # Data series reference
            ds = TradeDataSeries(
                trade_id=trade.id,
                attribute_id=attr_close.id,
                label="Close Price",
                data_source="ASSET_ATTRIBUTE",
            )
            db.add(ds)

            # Entry snapshot
            snap = TradeSnapshot(
                trade_id=trade.id,
                attribute_id=attr_zscore.id,
                snapshot_type="ENTRY",
                attribute_value=round(random.uniform(-3.0, 3.0), 4),
                timestamp=trade.entry_at,
            )
            db.add(snap)

            if trade.exit_at:
                snap_exit = TradeSnapshot(
                    trade_id=trade.id,
                    attribute_id=attr_zscore.id,
                    snapshot_type="EXIT",
                    attribute_value=round(random.uniform(-1.0, 1.0), 4),
                    timestamp=trade.exit_at,
                )
                db.add(snap_exit)

        db.flush()

        # --- Orders (for a subset of trades) ---
        for trade in all_trades[:30]:
            legs_for_trade = list(db.query(TradeLeg).filter(TradeLeg.trade_id == trade.id).all())
            for leg in legs_for_trade:
                if leg.entry_price is None:
                    continue

                # Entry order
                entry_order = Order(
                    timestamp=trade.entry_at,
                    order_type_id=order_types[0].id,  # MARKET
                    side="BUY" if leg.direction == "LONG" else "SELL",
                    provider_id=provider.id,
                    portfolio_id=trade.portfolio_id,
                    from_asset_id=leg.from_asset_id,
                    to_asset_id=leg.to_asset_id,
                    quantity=leg.quantity,
                    price=leg.entry_price,
                    filled_quantity=leg.quantity,
                    average_fill_price=leg.entry_price,
                    external_order_id=f"KRK-{random.randint(100000, 999999)}",
                    time_in_force="GTC",
                    trade_leg_id=leg.id,
                )
                db.add(entry_order)
                db.flush()

                # Order statuses
                db.add(
                    OrderStatus(
                        timestamp=trade.entry_at,
                        order_id=entry_order.id,
                        order_status_type_id=order_status_map["SUBMITTED"].id,
                    )
                )
                db.add(
                    OrderStatus(
                        timestamp=trade.entry_at + datetime.timedelta(seconds=1),
                        order_id=entry_order.id,
                        order_status_type_id=order_status_map["ACCEPTED"].id,
                    )
                )
                db.add(
                    OrderStatus(
                        timestamp=trade.entry_at + datetime.timedelta(seconds=2),
                        order_id=entry_order.id,
                        order_status_type_id=order_status_map["FILLED"].id,
                    )
                )

                # Exit order if closed
                if leg.exit_price and trade.exit_at:
                    exit_order = Order(
                        timestamp=trade.exit_at,
                        order_type_id=order_types[0].id,
                        side="SELL" if leg.direction == "LONG" else "BUY",
                        provider_id=provider.id,
                        portfolio_id=trade.portfolio_id,
                        from_asset_id=leg.from_asset_id,
                        to_asset_id=leg.to_asset_id,
                        quantity=leg.quantity,
                        price=leg.exit_price,
                        filled_quantity=leg.quantity,
                        average_fill_price=leg.exit_price,
                        external_order_id=f"KRK-{random.randint(100000, 999999)}",
                        time_in_force="GTC",
                        trade_leg_id=leg.id,
                    )
                    db.add(exit_order)
                    db.flush()

                    db.add(
                        OrderStatus(
                            timestamp=trade.exit_at,
                            order_id=exit_order.id,
                            order_status_type_id=order_status_map["SUBMITTED"].id,
                        )
                    )
                    db.add(
                        OrderStatus(
                            timestamp=trade.exit_at + datetime.timedelta(seconds=1),
                            order_id=exit_order.id,
                            order_status_type_id=order_status_map["ACCEPTED"].id,
                        )
                    )
                    db.add(
                        OrderStatus(
                            timestamp=trade.exit_at + datetime.timedelta(seconds=2),
                            order_id=exit_order.id,
                            order_status_type_id=order_status_map["FILLED"].id,
                        )
                    )

        db.commit()

        # Print summary
        trade_count = db.query(Trade).count()
        order_count = db.query(Order).count()
        feed_count = db.query(FeedModel).count()
        feed_run_count = db.query(FeedRun).count()
        partition_count = db.query(FeedPartition).count()
        strat_run_count = db.query(StrategyRun).count()
        metadata_type_count = db.query(Metadata).count()
        asset_meta_count = db.query(AssetMetadata).count()
        provider_meta_count = db.query(ProviderMetadata).count()
        at_meta_count = db.query(AssetTypeMetadata).count()
        pt_meta_count = db.query(ProviderTypeMetadata).count()

        print("Seeded successfully:")
        print(f"  {len(asset_types)} asset types, {len(assets)} assets")
        print(f"  {metadata_type_count} metadata types")
        print(f"  {at_meta_count} asset-type field defs, {pt_meta_count} provider-type field defs")
        print(
            f"  {asset_meta_count} asset metadata entries, {provider_meta_count} provider metadata entries"
        )
        print(f"  {feed_count} feeds, {feed_run_count} feed runs, {partition_count} partitions")
        print(
            f"  {len(all_groups)} asset groups ({len(pair_groups)} pairs, {len(basket_groups)} baskets)"
        )
        print(
            f"  {paa_count} provider_asset_attribute rows, {paga_count} provider_asset_group_attribute rows"
        )
        print(
            f"  {len(strategy_objs)} strategies, {strat_run_count} strategy runs, {trade_count} trades"
        )
        print(f"  {link_count} strategy-run ↔ feed-run links")
        print(f"  {order_count} orders")
        print("  2 portfolios, 1 provider")
