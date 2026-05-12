"""Seed strategies, strategy-feed links, strategy runs, and strategy-run-feed-run links."""

from __future__ import annotations

import datetime
import random
import uuid
from typing import Any


def seed_strategies(client: Any, ctx: dict) -> None:
    now = ctx["now"]
    feed_deps = ctx["feed_deps"]
    feed_runs_by_feed = ctx["feed_runs_by_feed"]

    from ascent.strategies.examples.momentum import MomentumStrategy
    from ascent.strategies.examples.ou import OUStrategy

    pairs_schema = OUStrategy.parameter_schema()
    momentum_schema = MomentumStrategy.parameter_schema()

    # (name, display, desc, ref, params, schema, feeds)
    strategies_data = [
        (
            "BTC_ETH_PAIRS",
            "BTC-ETH Pairs",
            "Pairs trading BTC/ETH spread on Kraken",
            "ascent.strategies.examples.pairs:pairs_strategy",
            {
                "lookback": 60,
                "entry_z": 2.0,
                "exit_z": 0.5,
                "hedge_ratio_method": "ols",
                "max_position_size": 1.0,
            },
            pairs_schema,
            [ctx["feed_market"], ctx["feed_ou"], ctx["feed_half_life"], ctx["feed_spread"]],
        ),
        (
            "SOL_MOMENTUM",
            "SOL Momentum",
            "Momentum strategy on SOL/USD via Kraken",
            "ascent.strategies.examples.momentum:momentum_strategy",
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
            [
                ctx["feed_market"],
                ctx["feed_funding"],
                ctx["feed_sentiment"],
                ctx["feed_sent_score"],
                ctx["feed_tech_indicators"],
            ],
        ),
        (
            "ADA_MEAN_REV",
            "ADA Mean Rev",
            "Mean reversion on ADA/USD via Kraken",
            "ascent.strategies.examples.momentum:momentum_strategy",
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
            [
                ctx["feed_market"],
                ctx["feed_ou"],
                ctx["feed_half_life"],
                ctx["feed_tech_indicators"],
            ],
        ),
        (
            "XRP_DOGE_PAIRS",
            "XRP-DOGE Pairs",
            "Pairs trading XRP/DOGE spread on Kraken",
            "ascent.strategies.examples.pairs:pairs_strategy",
            {
                "lookback": 30,
                "entry_z": 1.8,
                "exit_z": 0.3,
                "hedge_ratio_method": "tls",
                "max_position_size": 2.0,
            },
            pairs_schema,
            [
                ctx["feed_market"],
                ctx["feed_orderbook"],
                ctx["feed_funding"],
                ctx["feed_ou"],
                ctx["feed_spread"],
                ctx["feed_half_life"],
            ],
        ),
        (
            "BTC_GRID",
            "BTC Grid Trading",
            "Grid trading on BTC/USD with 0.5% grid spacing",
            "ascent.strategies.examples.pairs:pairs_strategy",
            {
                "lookback": 20,
                "entry_z": 1.5,
                "exit_z": 0.2,
                "hedge_ratio_method": "ols",
                "max_position_size": 0.5,
            },
            pairs_schema,
            [ctx["feed_market"], ctx["feed_orderbook"], ctx["feed_tech_indicators"]],
        ),
        (
            "CRYPTO_STAT_ARB",
            "Crypto Statistical Arb",
            "Multi-pair statistical arbitrage across crypto spreads",
            "ascent.strategies.examples.pairs:pairs_strategy",
            {
                "lookback": 90,
                "entry_z": 2.5,
                "exit_z": 0.5,
                "hedge_ratio_method": "kalman",
                "max_position_size": 1.0,
            },
            pairs_schema,
            [
                ctx["feed_market"],
                ctx["feed_cointegration"],
                ctx["feed_ou"],
                ctx["feed_half_life"],
                ctx["feed_correlation"],
            ],
        ),
        (
            "ETH_BREAKOUT",
            "ETH Breakout",
            "Breakout strategy on ETH/USD using Bollinger Bands",
            "ascent.strategies.examples.momentum:momentum_strategy",
            {
                "fast_period": 20,
                "slow_period": 50,
                "ma_type": "sma",
                "timeframe": "1h",
                "risk_per_trade": 0.015,
                "use_trailing_stop": True,
                "trailing_stop_pct": 0.04,
            },
            momentum_schema,
            [
                ctx["feed_market"],
                ctx["feed_vol_surface"],
                ctx["feed_tech_indicators"],
                ctx["feed_volume_profile"],
            ],
        ),
        (
            "DEFI_MOMENTUM",
            "DeFi Momentum",
            "Momentum strategy across DeFi basket tokens",
            "ascent.strategies.examples.momentum:momentum_strategy",
            {
                "fast_period": 10,
                "slow_period": 30,
                "ma_type": "ema",
                "timeframe": "4h",
                "risk_per_trade": 0.02,
                "use_trailing_stop": False,
                "trailing_stop_pct": 0.05,
            },
            momentum_schema,
            [
                ctx["feed_market"],
                ctx["feed_sentiment"],
                ctx["feed_sent_score"],
                ctx["feed_tech_indicators"],
            ],
        ),
        (
            "FUNDING_CARRY",
            "Funding Rate Carry",
            "Carry trade exploiting perpetual swap funding rate differentials",
            "ascent.strategies.examples.momentum:momentum_strategy",
            {
                "fast_period": 8,
                "slow_period": 24,
                "ma_type": "sma",
                "timeframe": "8h",
                "risk_per_trade": 0.01,
                "use_trailing_stop": False,
                "trailing_stop_pct": 0.02,
            },
            momentum_schema,
            [ctx["feed_market"], ctx["feed_funding"], ctx["feed_tech_indicators"]],
        ),
        (
            "AVAX_MOMENTUM_COINBASE",
            "AVAX Momentum (Coinbase)",
            "Momentum strategy on AVAX/USD via Coinbase",
            "ascent.strategies.examples.momentum:momentum_strategy",
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
            [ctx["feed_cb_market"], ctx["feed_cb_orderbook"]],
        ),
        (
            "LINK_MEAN_REV_COINBASE",
            "LINK Mean Rev (Coinbase)",
            "Mean reversion on LINK/USD via Coinbase",
            "ascent.strategies.examples.pairs:pairs_strategy",
            {
                "lookback": 14,
                "entry_z": 2.0,
                "exit_z": 0.5,
                "hedge_ratio_method": "kalman",
                "max_position_size": 0.5,
            },
            pairs_schema,
            [ctx["feed_cb_market"], ctx["feed_sentiment"], ctx["feed_sent_score"]],
        ),
        (
            "CROSS_BTC_ARB",
            "Cross-Exchange BTC Arb",
            "Cross-exchange arbitrage on BTC between Kraken and Coinbase",
            "ascent.strategies.examples.pairs:pairs_strategy",
            {
                "lookback": 10,
                "entry_z": 3.0,
                "exit_z": 0.1,
                "hedge_ratio_method": "ols",
                "max_position_size": 2.0,
            },
            pairs_schema,
            [
                ctx["feed_market"],
                ctx["feed_cb_market"],
                ctx["feed_orderbook"],
                ctx["feed_cb_orderbook"],
            ],
        ),
        (
            "AAPL_MSFT_PAIRS",
            "AAPL-MSFT Pairs",
            "Pairs trading Apple vs Microsoft",
            "ascent.strategies.examples.pairs:pairs_strategy",
            {
                "lookback": 60,
                "entry_z": 2.0,
                "exit_z": 0.5,
                "hedge_ratio_method": "ols",
                "max_position_size": 1.0,
            },
            pairs_schema,
            [ctx["feed_ib_market"], ctx["feed_tech_indicators"], ctx["feed_correlation"]],
        ),
        (
            "TECH_TREND",
            "Tech Trend Following",
            "Trend following strategy on top tech stocks",
            "ascent.strategies.examples.momentum:momentum_strategy",
            {
                "fast_period": 20,
                "slow_period": 50,
                "ma_type": "ema",
                "timeframe": "1d",
                "risk_per_trade": 0.01,
                "use_trailing_stop": True,
                "trailing_stop_pct": 0.05,
            },
            momentum_schema,
            [ctx["feed_ib_market"], ctx["feed_tech_indicators"], ctx["feed_macro"]],
        ),
        (
            "GOLD_SILVER_RATIO",
            "Gold/Silver Ratio Trade",
            "Mean reversion on the gold/silver price ratio",
            "ascent.strategies.examples.pairs:pairs_strategy",
            {
                "lookback": 90,
                "entry_z": 2.0,
                "exit_z": 0.5,
                "hedge_ratio_method": "ols",
                "max_position_size": 1.0,
            },
            pairs_schema,
            [ctx["feed_ib_market"], ctx["feed_tech_indicators"]],
        ),
        (
            "WTI_BRENT_SPREAD",
            "WTI-Brent Spread",
            "Trading the spread between WTI and Brent crude oil",
            "ascent.strategies.examples.pairs:pairs_strategy",
            {
                "lookback": 30,
                "entry_z": 1.5,
                "exit_z": 0.3,
                "hedge_ratio_method": "tls",
                "max_position_size": 2.0,
            },
            pairs_schema,
            [ctx["feed_ib_market"], ctx["feed_tech_indicators"], ctx["feed_macro"]],
        ),
    ]

    strategies = []
    for name, display_name, desc, ref, params, schema, feeds in strategies_data:
        s = client.create_strategy(
            name=name,
            display_name=display_name,
            description=desc,
            strategy_ref=ref,
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

    # -----------------------------------------------------------------
    # Strategy runs
    # -----------------------------------------------------------------

    MAX_RUNS_PER_STRATEGY = 500

    progress = ctx.get("progress")
    runs_task = None
    if progress:
        runs_task = progress.add_task(
            "Strategy runs", total=len(strategies) * MAX_RUNS_PER_STRATEGY
        )

    strat_runs_by_strategy: dict[str, list] = {}
    for s, _ in strategies:
        strat_runs_by_strategy[s["id"]] = []
        for i in range(MAX_RUNS_PER_STRATEGY):
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
                        "Position size exceeds risk limit",
                        "Exchange API rate limit exceeded",
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
            if progress and runs_task is not None:
                progress.advance(runs_task)

    if progress and runs_task is not None:
        progress.update(runs_task, visible=False)

    # --- Strategy Run <-> Feed Run links ---
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
                    if datetime.datetime.fromisoformat(fr["started_at"]) <= sr_started:
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

    # Store in context
    strategy_objs = [s for s, _ in strategies]
    ctx["strategies"] = strategies
    ctx["strategy_objs"] = strategy_objs
    ctx["strat_runs_by_strategy"] = strat_runs_by_strategy
    ctx["link_count"] = link_count

    # Strategy-to-pairs mapping (by index)
    ctx["strategy_pairs"] = {
        0: [("BTC", "USD"), ("ETH", "USD")],
        1: [("SOL", "USD")],
        2: [("ADA", "USD")],
        3: [("XRP", "USD"), ("DOGE", "USD")],
        4: [("BTC", "USD")],
        5: [("BTC", "USD"), ("ETH", "USD")],
        6: [("ETH", "USD")],
        7: [("UNI", "USD")],
        8: [("BTC", "USD")],
        9: [("AVAX", "USD")],
        10: [("LINK", "USD")],
        11: [("BTC", "USD")],
        12: [("AAPL", "USD"), ("MSFT", "USD")],
        13: [("NVDA", "USD")],
        14: [("XAU", "USD"), ("XAG", "USD")],
        15: [("WTI", "USD"), ("BRENT", "USD")],
    }
