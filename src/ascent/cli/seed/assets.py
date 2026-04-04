"""Seed all assets across every asset class."""

from __future__ import annotations

import uuid
from typing import Any

# Asset definition lists — (display_name, symbol) tuples, grouped by type.
# Stored in ctx so later modules can iterate over them.

FIAT_DEFS = [
    ("US Dollar", "USD"),
    ("Euro", "EUR"),
    ("British Pound", "GBP"),
    ("Japanese Yen", "JPY"),
    ("Swiss Franc", "CHF"),
]
CRYPTO_DEFS = [
    ("Bitcoin", "BTC"),
    ("Ethereum", "ETH"),
    ("Solana", "SOL"),
    ("Cardano", "ADA"),
    ("Ripple", "XRP"),
    ("Dogecoin", "DOGE"),
    ("Avalanche", "AVAX"),
    ("Chainlink", "LINK"),
    ("Polkadot", "DOT"),
    ("Polygon", "MATIC"),
    ("Cosmos", "ATOM"),
    ("Uniswap", "UNI"),
    ("Aptos", "APT"),
    ("Arbitrum", "ARB"),
    ("Optimism", "OP"),
    ("NEAR Protocol", "NEAR"),
    ("Fantom", "FTM"),
    ("Aave", "AAVE"),
    ("Maker", "MKR"),
    ("Synthetix", "SNX"),
    ("Curve", "CRV"),
    ("Lido DAO", "LDO"),
    ("Injective", "INJ"),
    ("Sui", "SUI"),
    ("Sei", "SEI"),
    ("Celestia", "TIA"),
    ("Jupiter", "JUP"),
    ("Pendle", "PENDLE"),
]
STABLECOIN_DEFS = [
    ("Tether", "USDT"),
    ("USD Coin", "USDC"),
    ("Dai", "DAI"),
]
STOCK_DEFS = [
    ("Apple Inc.", "AAPL"),
    ("Alphabet Inc.", "GOOGL"),
    ("Microsoft Corp.", "MSFT"),
    ("Amazon.com Inc.", "AMZN"),
    ("Tesla Inc.", "TSLA"),
    ("NVIDIA Corp.", "NVDA"),
    ("Meta Platforms Inc.", "META"),
    ("JPMorgan Chase & Co.", "JPM"),
    ("Visa Inc.", "V"),
    ("Johnson & Johnson", "JNJ"),
]
ETF_DEFS = [
    ("SPDR S&P 500 ETF", "SPY"),
    ("Invesco QQQ Trust", "QQQ"),
    ("SPDR Gold Shares", "GLD"),
    ("iShares 20+ Year Treasury Bond ETF", "TLT"),
    ("iShares Russell 2000 ETF", "IWM"),
]
PRECIOUS_METAL_DEFS = [
    ("Gold", "XAU"),
    ("Silver", "XAG"),
    ("Platinum", "XPT"),
    ("Palladium", "XPD"),
]
BASE_METAL_DEFS = [
    ("Copper", "COPPER"),
    ("Aluminum", "ALUMINUM"),
    ("Zinc", "ZINC"),
    ("Nickel", "NICKEL"),
]
ENERGY_DEFS = [
    ("Crude Oil WTI", "WTI"),
    ("Crude Oil Brent", "BRENT"),
    ("Natural Gas", "NATGAS"),
    ("Heating Oil", "HEATING_OIL"),
]
AGRI_DEFS = [
    ("Wheat", "WHEAT"),
    ("Corn", "CORN"),
    ("Soybeans", "SOYBEANS"),
    ("Coffee", "COFFEE"),
    ("Sugar", "SUGAR"),
    ("Cotton", "COTTON"),
]
GOVT_BOND_DEFS = [
    ("US 2-Year Treasury Note", "US_2Y"),
    ("US 10-Year Treasury Note", "US_10Y"),
    ("US 30-Year Treasury Bond", "US_30Y"),
    ("German 10-Year Bund", "DE_10Y"),
    ("UK 10-Year Gilt", "UK_10Y"),
]
CORP_BOND_DEFS = [
    ("US Corporate AAA Index", "CORP_AAA"),
    ("US Corporate BBB Index", "CORP_BBB"),
    ("US High Yield Index", "CORP_HY"),
]


def seed_assets(client: Any, ctx: dict) -> None:
    print("Creating assets...")

    asset_type_map = [
        (ctx["fiat_type"]["id"], FIAT_DEFS),
        (ctx["crypto_type"]["id"], CRYPTO_DEFS),
        (ctx["stablecoin_type"]["id"], STABLECOIN_DEFS),
        (ctx["common_stock_type"]["id"], STOCK_DEFS),
        (ctx["etf_type"]["id"], ETF_DEFS),
        (ctx["precious_metal_type"]["id"], PRECIOUS_METAL_DEFS),
        (ctx["base_metal_type"]["id"], BASE_METAL_DEFS),
        (ctx["energy_type"]["id"], ENERGY_DEFS),
        (ctx["agricultural_type"]["id"], AGRI_DEFS),
        (ctx["govt_bond_type"]["id"], GOVT_BOND_DEFS),
        (ctx["corp_bond_type"]["id"], CORP_BOND_DEFS),
    ]

    assets: dict[str, dict] = {}
    for type_id, defs in asset_type_map:
        for display_name, symbol in defs:
            a = client.create_asset(
                asset_type_id=uuid.UUID(type_id),
                name=symbol.upper(),
                display_name=display_name,
            )
            assets[symbol] = a

    ctx["asset_by_symbol"] = assets
