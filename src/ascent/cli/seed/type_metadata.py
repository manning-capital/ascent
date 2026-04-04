"""Link metadata fields to their owning types."""

from __future__ import annotations

import uuid
from typing import Any


def seed_type_metadata(client: Any, ctx: dict) -> None:
    print("Creating type-metadata field definitions...")

    meta = ctx["meta"]

    def _link(add_fn, type_id: str, pairs: list[tuple[str, bool]]) -> None:
        for i, (name, req) in enumerate(pairs):
            add_fn(
                uuid.UUID(type_id),
                metadata_id=uuid.UUID(meta[name]["id"]),
                is_required=req,
                display_order=i,
            )

    # --- Asset type metadata ---
    _link(
        client.add_asset_type_metadata,
        ctx["currency_type"]["id"],
        [
            ("MARKET_CAP", True),
            ("SECTOR", False),
        ],
    )
    _link(
        client.add_asset_type_metadata,
        ctx["crypto_type"]["id"],
        [
            ("CIRCULATING_SUPPLY", True),
            ("MAX_SUPPLY", False),
            ("LAUNCH_DATE", False),
            ("IS_STABLECOIN", True),
            ("CONSENSUS_MECHANISM", False),
            ("WHITEPAPER_URL", False),
        ],
    )
    _link(
        client.add_asset_type_metadata,
        ctx["stablecoin_type"]["id"],
        [
            ("CIRCULATING_SUPPLY", True),
            ("IS_STABLECOIN", True),
            ("PEG_CURRENCY", True),
            ("COLLATERAL_TYPE", True),
        ],
    )
    _link(
        client.add_asset_type_metadata,
        ctx["fiat_type"]["id"],
        [
            ("ISO_CURRENCY_CODE", True),
            ("ISSUING_COUNTRY", True),
        ],
    )
    _link(
        client.add_asset_type_metadata,
        ctx["equity_type"]["id"],
        [
            ("MARKET_CAP", True),
            ("SECTOR", True),
        ],
    )
    _link(
        client.add_asset_type_metadata,
        ctx["common_stock_type"]["id"],
        [
            ("PE_RATIO", False),
            ("EPS", False),
            ("DIVIDEND_YIELD", False),
            ("REVENUE", False),
            ("EXCHANGE_LISTING", True),
            ("ISIN", False),
            ("SHARES_OUTSTANDING", True),
        ],
    )
    _link(
        client.add_asset_type_metadata,
        ctx["preferred_stock_type"]["id"],
        [
            ("DIVIDEND_YIELD", True),
            ("EXCHANGE_LISTING", True),
            ("ISIN", False),
            ("SHARES_OUTSTANDING", True),
        ],
    )
    _link(
        client.add_asset_type_metadata,
        ctx["etf_type"]["id"],
        [
            ("EXPENSE_RATIO", True),
            ("NAV", True),
            ("TRACKING_INDEX", True),
            ("AUM", True),
            ("EXCHANGE_LISTING", True),
        ],
    )
    _link(
        client.add_asset_type_metadata,
        ctx["adr_type"]["id"],
        [
            ("EXCHANGE_LISTING", True),
            ("ISIN", True),
            ("SHARES_OUTSTANDING", True),
        ],
    )
    _link(
        client.add_asset_type_metadata,
        ctx["commodity_type"]["id"],
        [
            ("UNIT_OF_MEASURE", True),
            ("STANDARD_CONTRACT_SIZE", False),
        ],
    )
    _link(
        client.add_asset_type_metadata,
        ctx["fixed_income_type"]["id"],
        [
            ("COUPON_RATE", True),
            ("MATURITY_DATE", True),
            ("YIELD_TO_MATURITY", True),
            ("FACE_VALUE", True),
        ],
    )
    _link(
        client.add_asset_type_metadata,
        ctx["govt_bond_type"]["id"],
        [
            ("ISSUER", True),
            ("CREDIT_RATING", False),
        ],
    )
    _link(
        client.add_asset_type_metadata,
        ctx["corp_bond_type"]["id"],
        [
            ("ISSUER", True),
            ("CREDIT_RATING", True),
        ],
    )
    _link(
        client.add_asset_type_metadata,
        ctx["muni_bond_type"]["id"],
        [
            ("ISSUER", True),
            ("CREDIT_RATING", False),
        ],
    )

    # --- Provider type metadata ---
    _link(
        client.add_provider_type_metadata,
        ctx["market_participant_type"]["id"],
        [
            ("API_KEY_NAME", True),
            ("RATE_LIMIT", True),
            ("SUPPORTS_WEBSOCKET", False),
        ],
    )

    # --- Asset type provider-asset metadata ---
    _link(
        client.add_asset_type_provider_asset_metadata,
        ctx["currency_type"]["id"],
        [
            ("PROVIDER_TICKER", True),
        ],
    )
    _link(
        client.add_asset_type_provider_asset_metadata,
        ctx["crypto_type"]["id"],
        [
            ("TRADING_PAIR_SYMBOL", True),
            ("MIN_ORDER_SIZE", False),
        ],
    )
    _link(
        client.add_asset_type_provider_asset_metadata,
        ctx["equity_type"]["id"],
        [
            ("PROVIDER_TICKER", True),
        ],
    )
    _link(
        client.add_asset_type_provider_asset_metadata,
        ctx["commodity_type"]["id"],
        [
            ("PROVIDER_TICKER", True),
        ],
    )
    _link(
        client.add_asset_type_provider_asset_metadata,
        ctx["fixed_income_type"]["id"],
        [
            ("PROVIDER_TICKER", True),
        ],
    )

    # --- Instrument type metadata ---
    _link(
        client.add_instrument_type_metadata,
        ctx["security_itype"]["id"],
        [
            ("TICK_SIZE", True),
            ("LOT_SIZE", True),
            ("CONTRACT_SIZE", False),
            ("MARGIN_REQUIREMENT", False),
            ("TRADING_HOURS", False),
        ],
    )
    # Future specific (EXPIRY_DATE is new; CONTRACT_SIZE inherited from SECURITY)
    client.add_instrument_type_metadata(
        uuid.UUID(ctx["future_itype"]["id"]),
        metadata_id=uuid.UUID(meta["EXPIRY_DATE"]["id"]),
        is_required=True,
        display_order=0,
    )
    # Option specific
    _link(
        client.add_instrument_type_metadata,
        ctx["option_itype"]["id"],
        [
            ("EXPIRY_DATE", True),
            ("STRIKE_PRICE", True),
            ("OPTION_TYPE", True),
            ("UNDERLYING_INSTRUMENT", True),
        ],
    )

    # --- Composite type metadata ---
    _link(
        client.add_composite_type_metadata,
        ctx["spread_ctype"]["id"],
        [
            ("CORRELATION", True),
            ("HALF_LIFE", False),
            ("COINTEGRATION_PVALUE", False),
        ],
    )
    _link(
        client.add_composite_type_metadata,
        ctx["basket_ctype"]["id"],
        [
            ("CORRELATION", False),
        ],
    )
    _link(
        client.add_composite_type_metadata,
        ctx["index_ctype"]["id"],
        [
            ("CORRELATION", False),
        ],
    )
    _link(
        client.add_composite_type_metadata,
        ctx["ratio_ctype"]["id"],
        [
            ("CORRELATION", True),
            ("HALF_LIFE", False),
        ],
    )
