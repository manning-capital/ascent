"""Seed portfolios."""

from __future__ import annotations

import uuid
from typing import Any


def seed_portfolios(client: Any, ctx: dict) -> None:
    usd_id = uuid.UUID(ctx["asset_by_symbol"]["USD"]["id"])

    ctx["portfolio_main"] = client.create_portfolio(
        name="MAIN_PORTFOLIO",
        display_name="Main Portfolio",
        description="Primary crypto trading portfolio (Kraken)",
        base_currency_asset_id=usd_id,
        pricing_provider_id=ctx["kraken_id"],
    )
    ctx["portfolio_paper"] = client.create_portfolio(
        name="PAPER_TRADING",
        display_name="Paper Trading",
        description="Simulated trading portfolio",
        base_currency_asset_id=usd_id,
        pricing_provider_id=ctx["kraken_id"],
    )
    ctx["portfolio_coinbase"] = client.create_portfolio(
        name="COINBASE_PORTFOLIO",
        display_name="Coinbase Portfolio",
        description="Coinbase crypto trading portfolio",
        base_currency_asset_id=usd_id,
        pricing_provider_id=ctx["coinbase_id"],
    )
    ctx["portfolio_equity"] = client.create_portfolio(
        name="EQUITY_PORTFOLIO",
        display_name="Equity Portfolio",
        description="US equity and ETF portfolio (Interactive Brokers)",
        base_currency_asset_id=usd_id,
        pricing_provider_id=ctx["ib_id"],
    )
    ctx["portfolio_commodity"] = client.create_portfolio(
        name="COMMODITY_PORTFOLIO",
        display_name="Commodity Portfolio",
        description="Commodity futures portfolio (Interactive Brokers)",
        base_currency_asset_id=usd_id,
        pricing_provider_id=ctx["ib_id"],
    )
