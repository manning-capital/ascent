"""Seed all type hierarchies: asset, provider, exchange, strategy, instrument, composite, trade status, order."""

from __future__ import annotations

import uuid
from typing import Any


def seed_types(client: Any, ctx: dict) -> None:
    # --- Asset Types ---
    # CURRENCY
    #   ├── FIAT_CURRENCY
    #   ├── CRYPTOCURRENCY
    #   └── STABLECOIN
    # EQUITY
    #   ├── COMMON_STOCK
    #   ├── PREFERRED_STOCK
    #   ├── ETF
    #   └── ADR
    # COMMODITY
    #   ├── PRECIOUS_METAL
    #   ├── BASE_METAL
    #   ├── ENERGY
    #   └── AGRICULTURAL
    # FIXED_INCOME
    #   ├── GOVERNMENT_BOND
    #   ├── CORPORATE_BOND
    #   └── MUNICIPAL_BOND

    ctx["currency_type"] = client.create_asset_type(
        name="CURRENCY", display_name="Currency", description="Any form of currency"
    )
    ctx["crypto_type"] = client.create_asset_type(
        name="CRYPTOCURRENCY",
        display_name="Cryptocurrency",
        description="Digital or virtual currency secured by cryptography",
        parent_type_id=uuid.UUID(ctx["currency_type"]["id"]),
    )
    ctx["fiat_type"] = client.create_asset_type(
        name="FIAT_CURRENCY",
        display_name="Fiat Currency",
        description="Government-issued currency not backed by a commodity",
        parent_type_id=uuid.UUID(ctx["currency_type"]["id"]),
    )
    ctx["stablecoin_type"] = client.create_asset_type(
        name="STABLECOIN",
        display_name="Stablecoin",
        description="Cryptocurrency pegged to a stable asset such as USD",
        parent_type_id=uuid.UUID(ctx["currency_type"]["id"]),
    )

    ctx["equity_type"] = client.create_asset_type(
        name="EQUITY",
        display_name="Equity",
        description="Ownership interest in a corporation or financial asset",
    )
    ctx["common_stock_type"] = client.create_asset_type(
        name="COMMON_STOCK",
        display_name="Common Stock",
        description="Ordinary shares representing ownership in a corporation with voting rights",
        parent_type_id=uuid.UUID(ctx["equity_type"]["id"]),
    )
    ctx["preferred_stock_type"] = client.create_asset_type(
        name="PREFERRED_STOCK",
        display_name="Preferred Stock",
        description="Shares with priority dividend rights and liquidation preference",
        parent_type_id=uuid.UUID(ctx["equity_type"]["id"]),
    )
    ctx["etf_type"] = client.create_asset_type(
        name="ETF",
        display_name="Exchange-Traded Fund",
        description="Investment fund traded on stock exchanges holding a basket of assets",
        parent_type_id=uuid.UUID(ctx["equity_type"]["id"]),
    )
    ctx["adr_type"] = client.create_asset_type(
        name="ADR",
        display_name="American Depositary Receipt",
        description="Certificate representing shares in a foreign company traded on US exchanges",
        parent_type_id=uuid.UUID(ctx["equity_type"]["id"]),
    )

    ctx["commodity_type"] = client.create_asset_type(
        name="COMMODITY",
        display_name="Commodity",
        description="Basic physical good used in commerce that is interchangeable with other goods of the same type",
    )
    ctx["precious_metal_type"] = client.create_asset_type(
        name="PRECIOUS_METAL",
        display_name="Precious Metal",
        description="Rare metallic elements with high economic value (gold, silver, platinum, palladium)",
        parent_type_id=uuid.UUID(ctx["commodity_type"]["id"]),
    )
    ctx["base_metal_type"] = client.create_asset_type(
        name="BASE_METAL",
        display_name="Base Metal",
        description="Common industrial metals (copper, aluminum, zinc, nickel)",
        parent_type_id=uuid.UUID(ctx["commodity_type"]["id"]),
    )
    ctx["energy_type"] = client.create_asset_type(
        name="ENERGY",
        display_name="Energy",
        description="Energy commodities (crude oil, natural gas, heating oil, gasoline)",
        parent_type_id=uuid.UUID(ctx["commodity_type"]["id"]),
    )
    ctx["agricultural_type"] = client.create_asset_type(
        name="AGRICULTURAL",
        display_name="Agricultural",
        description="Farm-produced commodities (wheat, corn, soybeans, coffee, sugar, cotton)",
        parent_type_id=uuid.UUID(ctx["commodity_type"]["id"]),
    )

    ctx["fixed_income_type"] = client.create_asset_type(
        name="FIXED_INCOME",
        display_name="Fixed Income",
        description="Debt instruments that pay fixed interest over a defined period",
    )
    ctx["govt_bond_type"] = client.create_asset_type(
        name="GOVERNMENT_BOND",
        display_name="Government Bond",
        description="Debt security issued by a government to finance spending",
        parent_type_id=uuid.UUID(ctx["fixed_income_type"]["id"]),
    )
    ctx["corp_bond_type"] = client.create_asset_type(
        name="CORPORATE_BOND",
        display_name="Corporate Bond",
        description="Debt security issued by a corporation to raise capital",
        parent_type_id=uuid.UUID(ctx["fixed_income_type"]["id"]),
    )
    ctx["muni_bond_type"] = client.create_asset_type(
        name="MUNICIPAL_BOND",
        display_name="Municipal Bond",
        description="Debt security issued by a state or local government",
        parent_type_id=uuid.UUID(ctx["fixed_income_type"]["id"]),
    )

    # --- Provider Types ---
    ctx["market_participant_type"] = client.create_provider_type(
        name="MARKET_PARTICIPANT",
        display_name="Market Participant",
        description="Any entity participating in the market",
    )
    ctx["exchange_ptype"] = client.create_provider_type(
        name="EXCHANGE",
        display_name="Exchange",
        description="Cryptocurrency or stock exchange",
        parent_type_id=uuid.UUID(ctx["market_participant_type"]["id"]),
    )
    ctx["data_vendor_ptype"] = client.create_provider_type(
        name="DATA_VENDOR",
        display_name="Data Vendor",
        description="Market data provider or aggregator",
        parent_type_id=uuid.UUID(ctx["market_participant_type"]["id"]),
    )
    client.create_provider_type(
        name="BROKER_DEALER",
        display_name="Broker-Dealer",
        description="Firm that executes trades on behalf of clients and for its own account",
        parent_type_id=uuid.UUID(ctx["market_participant_type"]["id"]),
    )
    client.create_provider_type(
        name="CUSTODIAN",
        display_name="Custodian",
        description="Institution that holds and safeguards financial assets",
        parent_type_id=uuid.UUID(ctx["market_participant_type"]["id"]),
    )

    # --- Instrument Types ---
    ctx["security_itype"] = client.create_instrument_type(
        name="SECURITY",
        display_name="Security",
        description="Base type for all tradeable securities",
    )
    ctx["spot_itype"] = client.create_instrument_type(
        name="SPOT_INSTRUMENT",
        display_name="Spot Instrument",
        description="Instrument for immediate delivery at current market price",
        parent_type_id=uuid.UUID(ctx["security_itype"]["id"]),
    )
    ctx["perpetual_itype"] = client.create_instrument_type(
        name="PERPETUAL_SWAP",
        display_name="Perpetual Swap",
        description="Derivative contract with no expiry that tracks an underlying asset",
        parent_type_id=uuid.UUID(ctx["security_itype"]["id"]),
    )
    ctx["future_itype"] = client.create_instrument_type(
        name="FUTURE_INSTRUMENT",
        display_name="Future",
        description="Standardized contract to buy/sell an asset at a predetermined price at a future date",
        parent_type_id=uuid.UUID(ctx["security_itype"]["id"]),
    )
    ctx["option_itype"] = client.create_instrument_type(
        name="OPTION_INSTRUMENT",
        display_name="Option",
        description="Contract granting the right but not obligation to buy/sell at a strike price",
        parent_type_id=uuid.UUID(ctx["security_itype"]["id"]),
    )

    # --- Composite Types ---
    ctx["spread_ctype"] = client.create_composite_type(
        name="SPREAD",
        display_name="Spread",
        description="Difference between two correlated instruments",
        min_members=2,
        max_members=2,
    )
    client.create_composite_type(
        name="CALENDAR_SPREAD",
        display_name="Calendar Spread",
        description="Spread between same asset at different expiration dates",
        min_members=2,
        max_members=2,
        parent_type_id=uuid.UUID(ctx["spread_ctype"]["id"]),
    )
    ctx["cross_exchange_ctype"] = client.create_composite_type(
        name="CROSS_EXCHANGE_SPREAD",
        display_name="Cross-Exchange Spread",
        description="Price spread of the same asset across different exchanges",
        min_members=2,
        max_members=2,
        parent_type_id=uuid.UUID(ctx["spread_ctype"]["id"]),
    )
    ctx["basket_ctype"] = client.create_composite_type(
        name="BASKET",
        display_name="Basket",
        description="Weighted collection of multiple instruments",
        min_members=2,
        max_members=50,
    )
    client.create_composite_type(
        name="EQUAL_WEIGHT_BASKET",
        display_name="Equal-Weight Basket",
        description="Basket where each member has equal allocation weight",
        min_members=3,
        max_members=50,
        parent_type_id=uuid.UUID(ctx["basket_ctype"]["id"]),
    )
    client.create_composite_type(
        name="MARKET_CAP_BASKET",
        display_name="Market-Cap Basket",
        description="Basket weighted by market capitalization of each member",
        min_members=3,
        max_members=50,
        parent_type_id=uuid.UUID(ctx["basket_ctype"]["id"]),
    )
    ctx["index_ctype"] = client.create_composite_type(
        name="INDEX_COMPOSITE",
        display_name="Index Composite",
        description="Composite that tracks the performance of a market segment or index",
        min_members=2,
        max_members=500,
    )
    ctx["ratio_ctype"] = client.create_composite_type(
        name="RATIO",
        display_name="Ratio",
        description="Price ratio between two instruments (A/B)",
        min_members=2,
        max_members=2,
    )

    # --- Trade Status Types ---
    for name, display_name, desc in [
        ("PENDING", "Pending", "Trade is pending entry"),
        ("OPENING", "Opening", "Entry orders have been submitted"),
        ("OPEN", "Open", "Trade is currently open"),
        ("CLOSING", "Closing", "Exit orders have been submitted"),
        ("CLOSED", "Closed", "Trade has been closed"),
        ("CANCELLED", "Cancelled", "Trade was cancelled"),
        ("REJECTED", "Rejected", "Trade was rejected before any orders were placed"),
        ("ERROR", "Error", "Trade encountered an error"),
    ]:
        client.create_trade_status_type(name=name, display_name=display_name, description=desc)
    ctx["status_map"] = {t["name"]: t for t in client.get_trade_status_types()}

    # --- Order Types ---
    for name, display_name, desc in [
        ("MARKET", "Market", "Execute immediately at best available price"),
        ("LIMIT", "Limit", "Execute at specified price or better"),
        ("STOP", "Stop", "Trigger market order when price reaches stop level"),
        ("STOP_LIMIT", "Stop Limit", "Trigger limit order when price reaches stop level"),
        ("TRAILING_STOP", "Trailing Stop", "Stop level that follows price by a fixed offset"),
        ("ICEBERG", "Iceberg", "Large order split into smaller visible portions"),
    ]:
        client.create_order_type(name=name, display_name=display_name, description=desc)
    ctx["order_type_by_name"] = {t["name"]: t for t in client.get_order_types()}

    # --- Order Status Types ---
    for name, display_name, desc in [
        ("SUBMITTED", "Submitted", "Order submitted to exchange"),
        ("ACCEPTED", "Accepted", "Order accepted by exchange"),
        ("PARTIALLY_FILLED", "Partially Filled", "Order partially filled"),
        ("FILLED", "Filled", "Order fully filled"),
        ("REJECTED", "Rejected", "Order rejected by exchange"),
        ("CANCELLED", "Cancelled", "Order cancelled"),
    ]:
        client.create_order_status_type(name=name, display_name=display_name, description=desc)
    ctx["order_status_map"] = {t["name"]: t for t in client.get_order_status_types()}
