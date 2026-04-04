"""Seed temporal asset metadata entries for all asset classes."""

from __future__ import annotations

import datetime
import random
import uuid
from typing import Any


def _ts(now: datetime.datetime, days_ago: int) -> datetime.datetime:
    return now.replace(microsecond=0) - datetime.timedelta(days=days_ago)


def seed_asset_metadata(client: Any, ctx: dict) -> None:
    print("Creating asset metadata...")

    now = ctx["now"]
    meta = ctx["meta"]
    asset_by_symbol = ctx["asset_by_symbol"]
    random.seed(42)

    # --- Cryptocurrency metadata ---
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

    for symbol, info in crypto_info.items():
        asset = asset_by_symbol.get(symbol)
        if not asset:
            continue
        asset_id = uuid.UUID(asset["id"])
        base_mcap = info["base_mcap"]
        base_supply = info["base_supply"]
        for snap_idx, days_ago in enumerate([90, 60, 30]):
            ts = _ts(now, days_ago)
            growth = 1.0 - (2 - snap_idx) * random.uniform(0.08, 0.20)
            entries = [
                {
                    "metadata_id": uuid.UUID(meta["MARKET_CAP"]["id"]),
                    "value": int(base_mcap * growth),
                },
                {
                    "metadata_id": uuid.UUID(meta["CIRCULATING_SUPPLY"]["id"]),
                    "value": int(
                        base_supply * (1.0 - (2 - snap_idx) * random.uniform(0.001, 0.01))
                    ),
                },
            ]
            if snap_idx == 0:
                entries += [
                    {"metadata_id": uuid.UUID(meta["IS_STABLECOIN"]["id"]), "value": False},
                    {
                        "metadata_id": uuid.UUID(meta["CONSENSUS_MECHANISM"]["id"]),
                        "value": info["consensus"],
                    },
                    {"metadata_id": uuid.UUID(meta["SECTOR"]["id"]), "value": info["sector"]},
                    {
                        "metadata_id": uuid.UUID(meta["LAUNCH_DATE"]["id"]),
                        "value": info["launch_date"],
                    },
                ]
                if info["max_supply"] is not None:
                    entries.append(
                        {
                            "metadata_id": uuid.UUID(meta["MAX_SUPPLY"]["id"]),
                            "value": info["max_supply"],
                        }
                    )
            client.batch_create_asset_metadata(asset_id, timestamp=ts, entries=entries)

    # --- Stablecoin metadata ---
    stablecoin_info = {
        "USDT": {
            "peg": "USD",
            "collateral": "fiat-backed",
            "base_mcap": 110_000_000_000,
            "base_supply": 110_000_000_000,
        },
        "USDC": {
            "peg": "USD",
            "collateral": "fiat-backed",
            "base_mcap": 32_000_000_000,
            "base_supply": 32_000_000_000,
        },
        "DAI": {
            "peg": "USD",
            "collateral": "crypto-collateralized",
            "base_mcap": 5_300_000_000,
            "base_supply": 5_300_000_000,
        },
    }
    for symbol, info in stablecoin_info.items():
        asset_id = uuid.UUID(asset_by_symbol[symbol]["id"])
        for snap_idx, days_ago in enumerate([90, 60, 30]):
            ts = _ts(now, days_ago)
            supply = int(info["base_supply"] * (1.0 + snap_idx * random.uniform(0.01, 0.03)))
            entries = [
                {"metadata_id": uuid.UUID(meta["MARKET_CAP"]["id"]), "value": supply},
                {"metadata_id": uuid.UUID(meta["CIRCULATING_SUPPLY"]["id"]), "value": supply},
            ]
            if snap_idx == 0:
                entries += [
                    {"metadata_id": uuid.UUID(meta["IS_STABLECOIN"]["id"]), "value": True},
                    {"metadata_id": uuid.UUID(meta["PEG_CURRENCY"]["id"]), "value": info["peg"]},
                    {
                        "metadata_id": uuid.UUID(meta["COLLATERAL_TYPE"]["id"]),
                        "value": info["collateral"],
                    },
                    {"metadata_id": uuid.UUID(meta["SECTOR"]["id"]), "value": "Stablecoin"},
                ]
            client.batch_create_asset_metadata(asset_id, timestamp=ts, entries=entries)

    # --- Fiat currency metadata ---
    fiat_info = {
        "USD": ("USD", "United States"),
        "EUR": ("EUR", "European Union"),
        "GBP": ("GBP", "United Kingdom"),
        "JPY": ("JPY", "Japan"),
        "CHF": ("CHF", "Switzerland"),
    }
    for symbol, (iso, country) in fiat_info.items():
        client.batch_create_asset_metadata(
            uuid.UUID(asset_by_symbol[symbol]["id"]),
            timestamp=_ts(now, 90),
            entries=[
                {"metadata_id": uuid.UUID(meta["ISO_CURRENCY_CODE"]["id"]), "value": iso},
                {"metadata_id": uuid.UUID(meta["ISSUING_COUNTRY"]["id"]), "value": country},
                {"metadata_id": uuid.UUID(meta["IS_STABLECOIN"]["id"]), "value": False},
                {"metadata_id": uuid.UUID(meta["MARKET_CAP"]["id"]), "value": 0},
                {"metadata_id": uuid.UUID(meta["SECTOR"]["id"]), "value": "Fiat"},
            ],
        )

    # --- Stock metadata ---
    stock_info = {
        "AAPL": {
            "sector": "Technology",
            "exchange": "NASDAQ",
            "pe": 28.5,
            "eps": 6.42,
            "div_yield": 0.55,
            "revenue": 383_000_000_000,
            "shares": 15_400_000_000,
            "base_mcap": 2_800_000_000_000,
        },
        "GOOGL": {
            "sector": "Technology",
            "exchange": "NASDAQ",
            "pe": 25.1,
            "eps": 5.80,
            "div_yield": 0.0,
            "revenue": 307_000_000_000,
            "shares": 12_300_000_000,
            "base_mcap": 1_900_000_000_000,
        },
        "MSFT": {
            "sector": "Technology",
            "exchange": "NASDAQ",
            "pe": 35.2,
            "eps": 11.05,
            "div_yield": 0.74,
            "revenue": 227_000_000_000,
            "shares": 7_430_000_000,
            "base_mcap": 2_900_000_000_000,
        },
        "AMZN": {
            "sector": "Consumer Discretionary",
            "exchange": "NASDAQ",
            "pe": 60.3,
            "eps": 2.90,
            "div_yield": 0.0,
            "revenue": 575_000_000_000,
            "shares": 10_300_000_000,
            "base_mcap": 1_800_000_000_000,
        },
        "TSLA": {
            "sector": "Consumer Discretionary",
            "exchange": "NASDAQ",
            "pe": 72.8,
            "eps": 3.12,
            "div_yield": 0.0,
            "revenue": 97_000_000_000,
            "shares": 3_200_000_000,
            "base_mcap": 780_000_000_000,
        },
        "NVDA": {
            "sector": "Technology",
            "exchange": "NASDAQ",
            "pe": 65.4,
            "eps": 12.96,
            "div_yield": 0.03,
            "revenue": 61_000_000_000,
            "shares": 24_600_000_000,
            "base_mcap": 2_200_000_000_000,
        },
        "META": {
            "sector": "Technology",
            "exchange": "NASDAQ",
            "pe": 24.9,
            "eps": 14.87,
            "div_yield": 0.40,
            "revenue": 135_000_000_000,
            "shares": 2_560_000_000,
            "base_mcap": 1_200_000_000_000,
        },
        "JPM": {
            "sector": "Financials",
            "exchange": "NYSE",
            "pe": 11.8,
            "eps": 16.23,
            "div_yield": 2.40,
            "revenue": 162_000_000_000,
            "shares": 2_870_000_000,
            "base_mcap": 550_000_000_000,
        },
        "V": {
            "sector": "Financials",
            "exchange": "NYSE",
            "pe": 30.6,
            "eps": 8.77,
            "div_yield": 0.78,
            "revenue": 33_000_000_000,
            "shares": 2_050_000_000,
            "base_mcap": 540_000_000_000,
        },
        "JNJ": {
            "sector": "Healthcare",
            "exchange": "NYSE",
            "pe": 15.2,
            "eps": 9.92,
            "div_yield": 3.10,
            "revenue": 85_000_000_000,
            "shares": 2_410_000_000,
            "base_mcap": 380_000_000_000,
        },
    }
    for symbol, info in stock_info.items():
        asset_id = uuid.UUID(asset_by_symbol[symbol]["id"])
        for snap_idx, days_ago in enumerate([90, 60, 30]):
            ts = _ts(now, days_ago)
            growth = 1.0 - (2 - snap_idx) * random.uniform(0.03, 0.10)
            entries = [
                {
                    "metadata_id": uuid.UUID(meta["MARKET_CAP"]["id"]),
                    "value": int(info["base_mcap"] * growth),
                },
                {"metadata_id": uuid.UUID(meta["SECTOR"]["id"]), "value": info["sector"]},
            ]
            if snap_idx == 0:
                entries += [
                    {"metadata_id": uuid.UUID(meta["PE_RATIO"]["id"]), "value": info["pe"]},
                    {"metadata_id": uuid.UUID(meta["EPS"]["id"]), "value": info["eps"]},
                    {
                        "metadata_id": uuid.UUID(meta["DIVIDEND_YIELD"]["id"]),
                        "value": info["div_yield"],
                    },
                    {"metadata_id": uuid.UUID(meta["REVENUE"]["id"]), "value": info["revenue"]},
                    {
                        "metadata_id": uuid.UUID(meta["EXCHANGE_LISTING"]["id"]),
                        "value": info["exchange"],
                    },
                    {
                        "metadata_id": uuid.UUID(meta["SHARES_OUTSTANDING"]["id"]),
                        "value": info["shares"],
                    },
                ]
            client.batch_create_asset_metadata(asset_id, timestamp=ts, entries=entries)

    # --- ETF metadata ---
    etf_info = {
        "SPY": {
            "sector": "Broad Market",
            "exchange": "NYSE Arca",
            "expense": 0.09,
            "nav": 510.0,
            "tracking": "S&P 500",
            "aum": 520_000_000_000,
            "base_mcap": 520_000_000_000,
        },
        "QQQ": {
            "sector": "Technology",
            "exchange": "NASDAQ",
            "expense": 0.20,
            "nav": 430.0,
            "tracking": "NASDAQ-100",
            "aum": 250_000_000_000,
            "base_mcap": 250_000_000_000,
        },
        "GLD": {
            "sector": "Commodities",
            "exchange": "NYSE Arca",
            "expense": 0.40,
            "nav": 215.0,
            "tracking": "Gold Spot Price",
            "aum": 62_000_000_000,
            "base_mcap": 62_000_000_000,
        },
        "TLT": {
            "sector": "Fixed Income",
            "exchange": "NASDAQ",
            "expense": 0.15,
            "nav": 92.0,
            "tracking": "ICE US Treasury 20+ Year Bond Index",
            "aum": 50_000_000_000,
            "base_mcap": 50_000_000_000,
        },
        "IWM": {
            "sector": "Small Cap",
            "exchange": "NYSE Arca",
            "expense": 0.19,
            "nav": 198.0,
            "tracking": "Russell 2000",
            "aum": 60_000_000_000,
            "base_mcap": 60_000_000_000,
        },
    }
    for symbol, info in etf_info.items():
        asset_id = uuid.UUID(asset_by_symbol[symbol]["id"])
        for snap_idx, days_ago in enumerate([90, 60, 30]):
            ts = _ts(now, days_ago)
            growth = 1.0 - (2 - snap_idx) * random.uniform(0.02, 0.06)
            entries = [
                {
                    "metadata_id": uuid.UUID(meta["MARKET_CAP"]["id"]),
                    "value": int(info["base_mcap"] * growth),
                },
                {"metadata_id": uuid.UUID(meta["SECTOR"]["id"]), "value": info["sector"]},
                {
                    "metadata_id": uuid.UUID(meta["NAV"]["id"]),
                    "value": round(info["nav"] * growth, 2),
                },
                {"metadata_id": uuid.UUID(meta["AUM"]["id"]), "value": int(info["aum"] * growth)},
            ]
            if snap_idx == 0:
                entries += [
                    {
                        "metadata_id": uuid.UUID(meta["EXPENSE_RATIO"]["id"]),
                        "value": info["expense"],
                    },
                    {
                        "metadata_id": uuid.UUID(meta["TRACKING_INDEX"]["id"]),
                        "value": info["tracking"],
                    },
                    {
                        "metadata_id": uuid.UUID(meta["EXCHANGE_LISTING"]["id"]),
                        "value": info["exchange"],
                    },
                ]
            client.batch_create_asset_metadata(asset_id, timestamp=ts, entries=entries)

    # --- Commodity metadata ---
    commodity_info = {
        "XAU": ("troy oz", 100, 2050_000_000_000),
        "XAG": ("troy oz", 5000, 30_000_000_000),
        "XPT": ("troy oz", 50, 8_000_000_000),
        "XPD": ("troy oz", 100, 6_000_000_000),
        "COPPER": ("pound", 25000, 12_000_000_000),
        "ALUMINUM": ("metric ton", 25, 8_000_000_000),
        "ZINC": ("metric ton", 25, 5_000_000_000),
        "NICKEL": ("metric ton", 6, 4_000_000_000),
        "WTI": ("barrel", 1000, 45_000_000_000),
        "BRENT": ("barrel", 1000, 50_000_000_000),
        "NATGAS": ("MMBtu", 10000, 15_000_000_000),
        "HEATING_OIL": ("gallon", 42000, 8_000_000_000),
        "WHEAT": ("bushel", 5000, 3_000_000_000),
        "CORN": ("bushel", 5000, 4_000_000_000),
        "SOYBEANS": ("bushel", 5000, 5_000_000_000),
        "COFFEE": ("pound", 37500, 6_000_000_000),
        "SUGAR": ("pound", 112000, 4_000_000_000),
        "COTTON": ("pound", 50000, 3_000_000_000),
    }
    for symbol, (unit, contract_size, base_mcap) in commodity_info.items():
        asset = asset_by_symbol.get(symbol)
        if not asset:
            continue
        client.batch_create_asset_metadata(
            uuid.UUID(asset["id"]),
            timestamp=_ts(now, 90),
            entries=[
                {"metadata_id": uuid.UUID(meta["UNIT_OF_MEASURE"]["id"]), "value": unit},
                {
                    "metadata_id": uuid.UUID(meta["STANDARD_CONTRACT_SIZE"]["id"]),
                    "value": contract_size,
                },
                {"metadata_id": uuid.UUID(meta["MARKET_CAP"]["id"]), "value": base_mcap},
            ],
        )

    # --- Fixed Income metadata ---
    bond_info = {
        "US_2Y": {
            "coupon": 4.625,
            "maturity": "2026-09-30",
            "ytm": 4.35,
            "face": 1000,
            "issuer": "US Treasury",
            "rating": "AA+",
        },
        "US_10Y": {
            "coupon": 4.125,
            "maturity": "2034-11-15",
            "ytm": 4.25,
            "face": 1000,
            "issuer": "US Treasury",
            "rating": "AA+",
        },
        "US_30Y": {
            "coupon": 4.375,
            "maturity": "2054-05-15",
            "ytm": 4.50,
            "face": 1000,
            "issuer": "US Treasury",
            "rating": "AA+",
        },
        "DE_10Y": {
            "coupon": 2.60,
            "maturity": "2034-02-15",
            "ytm": 2.45,
            "face": 1000,
            "issuer": "German Federal Government",
            "rating": "AAA",
        },
        "UK_10Y": {
            "coupon": 4.25,
            "maturity": "2034-06-07",
            "ytm": 4.10,
            "face": 1000,
            "issuer": "HM Treasury",
            "rating": "AA",
        },
        "CORP_AAA": {
            "coupon": 4.50,
            "maturity": "2034-01-15",
            "ytm": 4.60,
            "face": 1000,
            "issuer": "AAA Corporate Index",
            "rating": "AAA",
        },
        "CORP_BBB": {
            "coupon": 5.25,
            "maturity": "2034-06-15",
            "ytm": 5.40,
            "face": 1000,
            "issuer": "BBB Corporate Index",
            "rating": "BBB",
        },
        "CORP_HY": {
            "coupon": 7.50,
            "maturity": "2031-03-15",
            "ytm": 7.80,
            "face": 1000,
            "issuer": "High Yield Corporate Index",
            "rating": "BB",
        },
    }
    for symbol, info in bond_info.items():
        asset = asset_by_symbol.get(symbol)
        if not asset:
            continue
        asset_id = uuid.UUID(asset["id"])
        for snap_idx, days_ago in enumerate([90, 60, 30]):
            ts = _ts(now, days_ago)
            ytm_shift = (2 - snap_idx) * random.uniform(-0.15, 0.15)
            entries = [
                {
                    "metadata_id": uuid.UUID(meta["YIELD_TO_MATURITY"]["id"]),
                    "value": round(info["ytm"] + ytm_shift, 3),
                },
                {"metadata_id": uuid.UUID(meta["FACE_VALUE"]["id"]), "value": info["face"]},
            ]
            if snap_idx == 0:
                entries += [
                    {"metadata_id": uuid.UUID(meta["COUPON_RATE"]["id"]), "value": info["coupon"]},
                    {
                        "metadata_id": uuid.UUID(meta["MATURITY_DATE"]["id"]),
                        "value": info["maturity"],
                    },
                    {"metadata_id": uuid.UUID(meta["ISSUER"]["id"]), "value": info["issuer"]},
                    {
                        "metadata_id": uuid.UUID(meta["CREDIT_RATING"]["id"]),
                        "value": info["rating"],
                    },
                ]
            client.batch_create_asset_metadata(asset_id, timestamp=ts, entries=entries)
