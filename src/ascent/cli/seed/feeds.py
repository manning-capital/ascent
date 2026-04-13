"""Seed feeds, feed dependencies, feed runs/partitions, and instrument/composite attribute data."""

from __future__ import annotations

import datetime
import random
import uuid
from typing import Any

from ascent.cli.seed.trades import _VOLATILITIES, _compute_rsi, _gbm_daily_prices

# Reference prices for all tradeable assets
_REF_PRICES: dict[str, float] = {
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
    "USDT": 1.00,
    "USDC": 1.00,
    "DAI": 1.00,
    "AAPL": 182.0,
    "GOOGL": 155.0,
    "MSFT": 390.0,
    "AMZN": 175.0,
    "TSLA": 245.0,
    "NVDA": 880.0,
    "META": 470.0,
    "JPM": 192.0,
    "V": 265.0,
    "JNJ": 152.0,
    "SPY": 510.0,
    "QQQ": 430.0,
    "GLD": 215.0,
    "TLT": 92.0,
    "IWM": 198.0,
    "XAU": 2350.0,
    "XAG": 28.50,
    "XPT": 1020.0,
    "XPD": 1050.0,
    "WTI": 78.50,
    "BRENT": 82.30,
    "NATGAS": 2.15,
    "US_2Y": 99.85,
    "US_10Y": 97.50,
    "US_30Y": 95.20,
    "DE_10Y": 98.10,
    "UK_10Y": 96.80,
    "HEATING_OIL": 2.55,
    "WHEAT": 6.50,
    "CORN": 4.80,
    "SOYBEANS": 12.50,
    "COFFEE": 1.95,
    "SUGAR": 0.22,
    "COTTON": 0.82,
    "CORP_AAA": 100.50,
    "CORP_BBB": 99.20,
    "CORP_HY": 95.80,
}


def _ensure_price_paths(ctx: dict) -> None:
    """Generate GBM price paths once and store in ctx for reuse by trades seed."""
    if "price_paths" in ctx:
        return
    num_days = 91
    price_paths: dict[str, list[float]] = {}
    rsi_paths: dict[str, list[float]] = {}
    for sym, s0 in _REF_PRICES.items():
        mu, sigma = _VOLATILITIES.get(sym, (0.0, 0.50))
        seed = hash(sym) & 0xFFFFFFFF
        prices = _gbm_daily_prices(s0, num_days, mu=mu, sigma=sigma, seed=seed)
        price_paths[sym] = prices
        rsi_paths[sym] = _compute_rsi(prices)
    ctx["price_paths"] = price_paths
    ctx["rsi_paths"] = rsi_paths
    ctx["ref_prices"] = _REF_PRICES


def seed_feeds(client: Any, ctx: dict) -> None:
    # Generate shared GBM price paths (used here and by trades seed)
    _ensure_price_paths(ctx)

    now = ctx["now"]
    asset_by_symbol = ctx["asset_by_symbol"]
    all_instruments = ctx["all_instruments"]
    all_composites = ctx["all_composites"]
    all_attributes = ctx["all_attributes"]

    # --- Feed Types ---
    feed_types_created = []
    for name, display_name, desc in [
        ("MARKET_DATA", "Market Data", "Real-time market data"),
        ("DERIVED", "Derived", "Computed from other feeds"),
        ("ALTERNATIVE", "Alternative", "Alternative data sources"),
        ("EXTERNAL", "External", "Data published via the Ascent API by an external process"),
    ]:
        ft = client.create_feed_type(name=name, display_name=display_name, description=desc)
        feed_types_created.append(ft)

    ft_market = feed_types_created[0]["id"]
    ft_derived = feed_types_created[1]["id"]
    ft_alt = feed_types_created[2]["id"]
    ft_external = feed_types_created[3]["id"]

    # Provider and type IDs for feed scope constraints
    kraken_id = ctx["kraken_id"]
    coinbase_id = ctx["coinbase_id"]
    ib_id = ctx["ib_id"]
    spot_itype_id = uuid.UUID(ctx["spot_itype"]["id"])
    spread_ctype_id = uuid.UUID(ctx["spread_ctype"]["id"])

    from ascent.feeds.examples.market import market_data
    from ascent.feeds.examples.ou_params import ou_params

    market_schema = market_data.parameter_schema()
    ou_schema = ou_params.parameter_schema()

    # --- Kraken feeds ---
    feed_market = client.create_feed(
        name="MARKET_DATA",
        display_name="Market Data",
        feed_type_id=uuid.UUID(ft_market),
        provider_id=kraken_id,
        scope_type="instrument",
        scope_type_id=spot_itype_id,
        feed_ref="ascent.feeds.examples.market:market_data",
        output_table="instrument_attribute",
        channel="ascent.feed.market_data",
        description="Pulls minutely OHLCV pricing data 1s before each minute close.",
        parameters={"provider_name": "kraken", "attributes": ["close"], "lookback_minutes": 5},
        parameter_schema=market_schema,
        schedule={"interval": 60, "offset": -1.0, "start_date": "2024-01-01T00:00:00+00:00"},
    )
    feed_orderbook = client.create_feed(
        name="ORDER_BOOK",
        display_name="Order Book",
        feed_type_id=uuid.UUID(ft_market),
        provider_id=kraken_id,
        scope_type="instrument",
        scope_type_id=spot_itype_id,
        feed_ref="ascent.feeds.examples.orderbook:orderbook",
        output_table="instrument_attribute",
        channel="ascent.feed.orderbook",
        description="Snapshots top-of-book bid/ask every 30 seconds.",
        parameters={"depth": 10, "provider_name": "kraken"},
        schedule={"interval": 30, "start_date": "2024-01-01T00:00:00+00:00"},
    )
    feed_sentiment = client.create_feed(
        name="SENTIMENT",
        display_name="Sentiment",
        feed_type_id=uuid.UUID(ft_alt),
        provider_id=kraken_id,
        scope_type="instrument",
        scope_type_id=spot_itype_id,
        feed_ref="ascent.feeds.examples.sentiment:sentiment",
        output_table="instrument_attribute",
        channel="ascent.feed.sentiment",
        description="Aggregated social sentiment scores every 5 minutes.",
        parameters={"sources": ["twitter", "reddit"]},
        schedule={"interval": 300, "start_date": "2024-01-01T00:00:00+00:00"},
    )
    feed_cointegration = client.create_feed(
        name="COINTEGRATION",
        display_name="Cointegration",
        feed_type_id=uuid.UUID(ft_derived),
        provider_id=kraken_id,
        scope_type="instrument",
        scope_type_id=spot_itype_id,
        feed_ref="ascent.feeds.examples.cointegration:cointegration",
        output_table="instrument_attribute",
        channel="ascent.feed.cointegration",
        description="Cointegration test statistics for asset pair groups every 5 minutes.",
        parameters={"test": "engle_granger", "lookback_days": 30},
        schedule={"interval": 300, "start_date": "2024-01-01T00:00:00+00:00"},
    )
    feed_ou = client.create_feed(
        name="OU_PARAMETERS",
        display_name="OU Parameters",
        feed_type_id=uuid.UUID(ft_external),
        provider_id=kraken_id,
        scope_type="instrument",
        scope_type_id=spot_itype_id,
        feed_ref="ascent.feeds.examples.ou_params:ou_params",
        output_table="instrument_attribute",
        channel="ascent.feed.ou_params",
        description="Ornstein-Uhlenbeck parameters computed externally.",
        parameters={"lookback_days": 60},
        parameter_schema=ou_schema,
        schedule={"interval": 3600, "start_date": "2024-01-01T00:00:00+00:00"},
    )
    feed_funding = client.create_feed(
        name="FUNDING_RATES",
        display_name="Funding Rates",
        feed_type_id=uuid.UUID(ft_external),
        provider_id=kraken_id,
        scope_type="instrument",
        scope_type_id=spot_itype_id,
        feed_ref="ascent.feeds.examples.funding:funding_rates",
        output_table="instrument_attribute",
        channel="ascent.feed.funding_rates",
        description="Perpetual swap funding rates computed externally.",
        parameters={"exchanges": ["kraken", "binance"]},
        schedule={"interval": 28800, "start_date": "2024-01-01T00:00:00+00:00"},
    )
    feed_spread = client.create_feed(
        name="SPREAD_ANALYTICS",
        display_name="Spread Analytics",
        feed_type_id=uuid.UUID(ft_derived),
        provider_id=kraken_id,
        scope_type="instrument",
        scope_type_id=spot_itype_id,
        feed_ref="ascent.feeds.examples.spread:spread_analytics",
        output_table="instrument_attribute",
        channel="ascent.feed.spread",
        description="Computes bid-ask spread metrics from order book and market data.",
        parameters={"window": 20},
        schedule={"interval": 60, "start_date": "2024-01-01T00:00:00+00:00"},
    )
    feed_sent_score = client.create_feed(
        name="SENTIMENT_SCORE",
        display_name="Sentiment Score",
        feed_type_id=uuid.UUID(ft_derived),
        provider_id=kraken_id,
        scope_type="instrument",
        scope_type_id=spot_itype_id,
        feed_ref="ascent.feeds.examples.sentiment:sentiment_score",
        output_table="instrument_attribute",
        channel="ascent.feed.sentiment_score",
        description="Normalised sentiment z-score derived from raw sentiment feed.",
        parameters={"lookback_hours": 24},
        schedule={"interval": 300, "start_date": "2024-01-01T00:00:00+00:00"},
    )
    feed_half_life = client.create_feed(
        name="HALF_LIFE",
        display_name="Half-Life",
        feed_type_id=uuid.UUID(ft_derived),
        provider_id=kraken_id,
        scope_type="instrument",
        scope_type_id=spot_itype_id,
        feed_ref="ascent.feeds.examples.half_life:half_life",
        output_table="instrument_attribute",
        channel="ascent.feed.half_life",
        description="Mean-reversion half-life estimate derived from OU parameters.",
        parameters={"min_samples": 30},
        schedule={"interval": 3600, "start_date": "2024-01-01T00:00:00+00:00"},
    )

    # --- Coinbase feeds ---
    feed_cb_market = client.create_feed(
        name="MARKET_DATA_COINBASE",
        display_name="Market Data (Coinbase)",
        feed_type_id=uuid.UUID(ft_market),
        provider_id=coinbase_id,
        scope_type="instrument",
        scope_type_id=spot_itype_id,
        feed_ref="ascent.feeds.examples.market:market_data",
        output_table="instrument_attribute",
        channel="ascent.feed.coinbase_market_data",
        description="Minutely OHLCV pricing data from Coinbase.",
        parameters={"provider_name": "coinbase", "attributes": ["close"], "lookback_minutes": 5},
        parameter_schema=market_schema,
        schedule={"interval": 60, "offset": -1.0, "start_date": "2024-01-01T00:00:00+00:00"},
    )
    feed_cb_orderbook = client.create_feed(
        name="ORDER_BOOK_COINBASE",
        display_name="Order Book (Coinbase)",
        feed_type_id=uuid.UUID(ft_market),
        provider_id=coinbase_id,
        scope_type="instrument",
        scope_type_id=spot_itype_id,
        feed_ref="ascent.feeds.examples.orderbook:orderbook",
        output_table="instrument_attribute",
        channel="ascent.feed.coinbase_orderbook",
        description="Snapshots top-of-book bid/ask from Coinbase every 30 seconds.",
        parameters={"depth": 10, "provider_name": "coinbase"},
        schedule={"interval": 30, "start_date": "2024-01-01T00:00:00+00:00"},
    )

    # --- IB / Equity feeds ---
    feed_ib_market = client.create_feed(
        name="MARKET_DATA_IB",
        display_name="Market Data (IB)",
        feed_type_id=uuid.UUID(ft_market),
        provider_id=ib_id,
        scope_type="instrument",
        scope_type_id=spot_itype_id,
        feed_ref="ascent.feeds.examples.market:market_data",
        output_table="instrument_attribute",
        channel="ascent.feed.ib_market_data",
        description="Minutely OHLCV pricing data from Interactive Brokers.",
        parameters={
            "provider_name": "interactive_brokers",
            "attributes": ["close"],
            "lookback_minutes": 5,
        },
        parameter_schema=market_schema,
        schedule={"interval": 60, "offset": -1.0, "start_date": "2024-01-01T00:00:00+00:00"},
    )

    # --- Cross-cutting derived feeds ---
    feed_vol_surface = client.create_feed(
        name="VOLATILITY_SURFACE",
        display_name="Volatility Surface",
        feed_type_id=uuid.UUID(ft_derived),
        provider_id=kraken_id,
        scope_type="instrument",
        scope_type_id=spot_itype_id,
        feed_ref="ascent.feeds.examples.volatility:vol_surface",
        output_table="instrument_attribute",
        channel="ascent.feed.vol_surface",
        description="Implied volatility surface computed from options and historical data.",
        parameters={"lookback_days": 30, "strike_range": 0.2},
        schedule={"interval": 3600, "start_date": "2024-01-01T00:00:00+00:00"},
    )
    feed_volume_profile = client.create_feed(
        name="VOLUME_PROFILE",
        display_name="Volume Profile",
        feed_type_id=uuid.UUID(ft_derived),
        provider_id=kraken_id,
        scope_type="instrument",
        scope_type_id=spot_itype_id,
        feed_ref="ascent.feeds.examples.volume:volume_profile",
        output_table="instrument_attribute",
        channel="ascent.feed.volume_profile",
        description="Volume distribution across price levels over a session.",
        parameters={"num_bins": 50, "session_hours": 24},
        schedule={"interval": 3600, "start_date": "2024-01-01T00:00:00+00:00"},
    )
    feed_correlation = client.create_feed(
        name="CORRELATION_MATRIX",
        display_name="Correlation Matrix",
        feed_type_id=uuid.UUID(ft_derived),
        provider_id=kraken_id,
        scope_type="composite",
        scope_type_id=spread_ctype_id,
        feed_ref="ascent.feeds.examples.correlation:correlation_matrix",
        output_table="composite_attribute",
        channel="ascent.feed.correlation",
        description="Rolling pairwise correlation matrix across instrument universe.",
        parameters={"lookback_days": 30, "min_observations": 20},
        schedule={"interval": 3600, "start_date": "2024-01-01T00:00:00+00:00"},
    )
    feed_macro = client.create_feed(
        name="MACRO_INDICATORS",
        display_name="Macro Indicators",
        feed_type_id=uuid.UUID(ft_external),
        provider_id=kraken_id,
        scope_type="instrument",
        scope_type_id=spot_itype_id,
        feed_ref="ascent.feeds.examples.macro:macro_indicators",
        output_table="instrument_attribute",
        channel="ascent.feed.macro",
        description="Macroeconomic indicators (interest rates, CPI, PMI) from external source.",
        parameters={"indicators": ["FED_RATE", "CPI_YOY", "PMI"]},
        schedule={"interval": 86400, "start_date": "2024-01-01T00:00:00+00:00"},
    )
    feed_tech_indicators = client.create_feed(
        name="TECHNICAL_INDICATORS",
        display_name="Technical Indicators",
        feed_type_id=uuid.UUID(ft_derived),
        provider_id=kraken_id,
        scope_type="instrument",
        scope_type_id=spot_itype_id,
        feed_ref="ascent.feeds.examples.technicals:tech_indicators",
        output_table="instrument_attribute",
        channel="ascent.feed.technicals",
        description="RSI, MACD, Bollinger Bands, ATR computed from market data.",
        parameters={"rsi_period": 14, "macd_fast": 12, "macd_slow": 26, "bb_period": 20},
        schedule={"interval": 60, "start_date": "2024-01-01T00:00:00+00:00"},
    )

    # --- Feed dependencies ---
    feed_deps = [
        (feed_spread["id"], feed_market["id"]),
        (feed_spread["id"], feed_orderbook["id"]),
        (feed_sent_score["id"], feed_sentiment["id"]),
        (feed_cointegration["id"], feed_market["id"]),
        (feed_half_life["id"], feed_ou["id"]),
        (feed_vol_surface["id"], feed_market["id"]),
        (feed_volume_profile["id"], feed_market["id"]),
        (feed_correlation["id"], feed_market["id"]),
        (feed_tech_indicators["id"], feed_market["id"]),
    ]
    for child_id, parent_id in feed_deps:
        client.create_feed_dependency(uuid.UUID(child_id), depends_on_feed_id=uuid.UUID(parent_id))

    # -----------------------------------------------------------------
    # Feed runs & partitions — runs spaced at each feed's actual
    # schedule interval, capped at 200 runs per feed.
    # -----------------------------------------------------------------

    from ascent.feeds.partition import partition_key_for, partition_window
    from ascent.feeds.schedule import Schedule

    MAX_RUNS_PER_FEED = 500

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
        feed_ib_market,
        feed_vol_surface,
        feed_volume_profile,
        feed_correlation,
        feed_macro,
        feed_tech_indicators,
    ]

    feed_schedules = {}
    for f in all_feeds:
        sched = f.get("schedule")
        feed_schedules[f["id"]] = Schedule(**sched) if sched else None

    partition_cache: dict = {}
    feed_runs_by_feed: dict[str, list] = {f["id"]: [] for f in all_feeds}

    progress = ctx.get("progress")
    runs_task = None
    if progress:
        runs_task = progress.add_task("Feed runs", total=len(all_feeds) * MAX_RUNS_PER_FEED)

    for feed_obj in all_feeds:
        schedule_obj = feed_schedules[feed_obj["id"]]
        interval_secs = schedule_obj.interval if schedule_obj and schedule_obj.interval else 3600

        for i in range(MAX_RUNS_PER_FEED):
            secs_ago = i * interval_secs
            started = now - datetime.timedelta(seconds=secs_ago)

            # Most recent run may be RUNNING; the rest mostly COMPLETED
            # with ~5% failure rate
            if i == 0:
                status = random.choice(["COMPLETED"] * 8 + ["RUNNING"] * 2)
            else:
                status = "COMPLETED" if random.random() < 0.95 else "FAILED"

            completed = (
                started + datetime.timedelta(seconds=random.uniform(0.5, 5.0))
                if status == "COMPLETED"
                else None
            )

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
            if progress and runs_task is not None:
                progress.advance(runs_task)

    if progress and runs_task is not None:
        progress.update(runs_task, visible=False)

    # -----------------------------------------------------------------
    # Instrument & composite attribute data — prices from GBM paths
    # generated in the trades seed, with intraday interpolation.
    # -----------------------------------------------------------------

    price_paths = ctx.get("price_paths", {})
    rsi_paths = ctx.get("rsi_paths", {})

    inst_attr_attrs = [a for a in all_attributes if a["name"] in ("CLOSE", "RSI")]
    comp_attr_attrs = [a for a in all_attributes if a["name"] in ("SPREAD", "Z_SCORE")]

    def _sym_for_instrument(inst: dict) -> str | None:
        return next(
            (s for s, a in asset_by_symbol.items() if a["id"] == inst.get("from_asset_id")),
            None,
        )

    def _make_aware(ts: datetime.datetime) -> datetime.datetime:
        """Ensure a datetime is timezone-aware (UTC)."""
        if ts.tzinfo is None:
            return ts.replace(tzinfo=datetime.UTC)
        return ts

    def _price_for_ts(sym: str, ts: datetime.datetime) -> float:
        """Look up GBM daily price for a timestamp, adding intraday noise."""
        path = price_paths.get(sym)
        if not path:
            return 100.0
        days_ago = max(0, (now - _make_aware(ts)).days)
        idx = min(days_ago, len(path) - 1)
        base = path[idx]
        return round(base * (1 + random.uniform(-0.003, 0.003)), 6)

    def _rsi_for_ts(sym: str, ts: datetime.datetime) -> float:
        """Look up RSI for the day corresponding to *ts*."""
        path = rsi_paths.get(sym)
        if not path:
            return round(random.uniform(30.0, 70.0), 2)
        days_ago = max(0, (now - _make_aware(ts)).days)
        idx = min(days_ago, len(path) - 1)
        return path[idx]

    paga_batch: list[dict] = []
    paga_count = 0
    comp_batch: list[dict] = []
    comp_count = 0
    seen_inst_keys: set[tuple] = set()
    seen_comp_keys: set[tuple] = set()

    # Only generate attribute data for the primary market data feeds (one per
    # provider) to avoid PK collisions from feeds with overlapping intervals.
    attr_feed_ids = {
        feed_market["id"],  # Kraken instrument_attribute
        feed_cb_market["id"],  # Coinbase instrument_attribute
        feed_ib_market["id"],  # IB instrument_attribute
        feed_correlation["id"],  # composite_attribute
    }

    materialized = [
        k
        for k, v in partition_cache.items()
        if v["status"] == "MATERIALIZED" and k[0] in attr_feed_ids
    ]
    attr_task = None
    if progress:
        attr_task = progress.add_task("Attribute data", total=len(materialized))

    for cache_key, partition_obj in partition_cache.items():
        if partition_obj["status"] != "MATERIALIZED":
            continue
        feed_id_key = cache_key[0]
        if feed_id_key not in attr_feed_ids:
            continue
        feed_for_partition = next((f for f in all_feeds if f["id"] == feed_id_key), None)
        if feed_for_partition is None:
            continue

        w_start = datetime.datetime.fromisoformat(partition_obj["window_start"])
        w_end = datetime.datetime.fromisoformat(partition_obj["window_end"])
        window_secs = (w_end - w_start).total_seconds()
        ts = w_start + datetime.timedelta(seconds=window_secs * 0.5)

        output_table = feed_for_partition.get("output_table", "")

        if output_table == "instrument_attribute":
            for inst in all_instruments:
                sym = _sym_for_instrument(inst)
                for attr in inst_attr_attrs:
                    key = (ts.isoformat(), inst["id"], attr["id"])
                    if key in seen_inst_keys:
                        continue
                    seen_inst_keys.add(key)
                    if attr["name"] == "CLOSE":
                        value = (
                            _price_for_ts(sym, ts)
                            if sym
                            else round(100 * (1 + random.uniform(-0.02, 0.02)), 4)
                        )
                    else:  # RSI
                        value = (
                            _rsi_for_ts(sym, ts) if sym else round(random.uniform(30.0, 70.0), 2)
                        )
                    paga_batch.append(
                        {
                            "timestamp": ts,
                            "instrument_id": uuid.UUID(inst["id"]),
                            "attribute_id": uuid.UUID(attr["id"]),
                            "attribute_value": value,
                        }
                    )
                    paga_count += 1
                    if len(paga_batch) >= 1000:
                        client.batch_create_instrument_attributes(paga_batch)
                        paga_batch = []

        if output_table == "composite_attribute":
            for comp in all_composites:
                for attr in comp_attr_attrs:
                    key = (ts.isoformat(), comp["id"], attr["id"])
                    if key in seen_comp_keys:
                        continue
                    seen_comp_keys.add(key)
                    value = (
                        round(random.uniform(-500, 500), 4)
                        if attr["name"] == "SPREAD"
                        else round(random.uniform(-3.0, 3.0), 4)
                    )
                    comp_batch.append(
                        {
                            "timestamp": ts,
                            "composite_id": uuid.UUID(comp["id"]),
                            "attribute_id": uuid.UUID(attr["id"]),
                            "attribute_value": value,
                        }
                    )
                    comp_count += 1
                    if len(comp_batch) >= 1000:
                        client.batch_create_composite_attributes(comp_batch)
                        comp_batch = []

        if progress and attr_task is not None:
            progress.advance(attr_task)

    if paga_batch:
        client.batch_create_instrument_attributes(paga_batch)
    if comp_batch:
        client.batch_create_composite_attributes(comp_batch)

    if progress and attr_task is not None:
        progress.update(attr_task, visible=False)

    # Store in context
    ctx["all_feeds"] = all_feeds
    ctx["feed_deps"] = feed_deps
    ctx["feed_runs_by_feed"] = feed_runs_by_feed
    ctx["paga_count"] = paga_count
    ctx["comp_count"] = comp_count
    # Individual feeds needed by strategies
    ctx["feed_market"] = feed_market
    ctx["feed_orderbook"] = feed_orderbook
    ctx["feed_sentiment"] = feed_sentiment
    ctx["feed_cointegration"] = feed_cointegration
    ctx["feed_ou"] = feed_ou
    ctx["feed_funding"] = feed_funding
    ctx["feed_spread"] = feed_spread
    ctx["feed_sent_score"] = feed_sent_score
    ctx["feed_half_life"] = feed_half_life
    ctx["feed_cb_market"] = feed_cb_market
    ctx["feed_cb_orderbook"] = feed_cb_orderbook
    ctx["feed_ib_market"] = feed_ib_market
    ctx["feed_vol_surface"] = feed_vol_surface
    ctx["feed_volume_profile"] = feed_volume_profile
    ctx["feed_correlation"] = feed_correlation
    ctx["feed_macro"] = feed_macro
    ctx["feed_tech_indicators"] = feed_tech_indicators
