"""Seed attributes and metadata types."""

from __future__ import annotations

from typing import Any


def seed_descriptors(client: Any, ctx: dict) -> None:
    print("Creating attributes...")

    ctx["attr_close"] = client.create_attribute(
        name="CLOSE", display_name="Close", description="Close price"
    )
    ctx["attr_open"] = client.create_attribute(
        name="OPEN", display_name="Open", description="Open price"
    )
    ctx["attr_high"] = client.create_attribute(
        name="HIGH", display_name="High", description="High price"
    )
    ctx["attr_low"] = client.create_attribute(
        name="LOW", display_name="Low", description="Low price"
    )
    ctx["attr_volume"] = client.create_attribute(
        name="VOLUME", display_name="Volume", description="Trading volume"
    )
    ctx["attr_spread"] = client.create_attribute(
        name="SPREAD", display_name="Spread", description="Price spread between correlated assets"
    )
    ctx["attr_zscore"] = client.create_attribute(
        name="Z_SCORE", display_name="Z Score", description="Z-score of the spread"
    )
    ctx["attr_rsi"] = client.create_attribute(
        name="RSI", display_name="RSI", description="Relative Strength Index"
    )
    ctx["attr_vwap"] = client.create_attribute(
        name="VWAP", display_name="VWAP", description="Volume Weighted Average Price"
    )
    ctx["attr_atr"] = client.create_attribute(
        name="ATR", display_name="ATR", description="Average True Range volatility indicator"
    )
    ctx["attr_macd"] = client.create_attribute(
        name="MACD", display_name="MACD", description="Moving Average Convergence Divergence"
    )
    ctx["attr_bb_upper"] = client.create_attribute(
        name="BB_UPPER", display_name="Bollinger Upper", description="Upper Bollinger Band"
    )
    ctx["attr_bb_lower"] = client.create_attribute(
        name="BB_LOWER", display_name="Bollinger Lower", description="Lower Bollinger Band"
    )
    ctx["attr_funding_rate"] = client.create_attribute(
        name="FUNDING_RATE", display_name="Funding Rate", description="Perpetual swap funding rate"
    )
    ctx["attr_oi"] = client.create_attribute(
        name="OPEN_INTEREST",
        display_name="Open Interest",
        description="Total number of outstanding derivative contracts",
    )
    ctx["attr_iv"] = client.create_attribute(
        name="IMPLIED_VOL",
        display_name="Implied Volatility",
        description="Market-implied annualized volatility",
    )
    ctx["attr_bid"] = client.create_attribute(
        name="BID", display_name="Bid", description="Best bid price"
    )
    ctx["attr_ask"] = client.create_attribute(
        name="ASK", display_name="Ask", description="Best ask price"
    )

    ctx["all_attributes"] = [
        ctx["attr_close"],
        ctx["attr_open"],
        ctx["attr_high"],
        ctx["attr_low"],
        ctx["attr_volume"],
        ctx["attr_spread"],
        ctx["attr_zscore"],
        ctx["attr_rsi"],
        ctx["attr_vwap"],
        ctx["attr_atr"],
        ctx["attr_macd"],
        ctx["attr_bb_upper"],
        ctx["attr_bb_lower"],
        ctx["attr_funding_rate"],
        ctx["attr_oi"],
        ctx["attr_iv"],
        ctx["attr_bid"],
        ctx["attr_ask"],
    ]

    # --- Metadata types ---
    print("Creating metadata types...")

    meta_defs = [
        ("MARKET_CAP", "Market Cap", "Market capitalization in USD", "float"),
        ("SECTOR", "Sector", "Industry sector classification", "string"),
        ("CIRCULATING_SUPPLY", "Circulating Supply", "Circulating supply of the asset", "float"),
        ("MAX_SUPPLY", "Max Supply", "Maximum supply of the asset", "float"),
        ("LAUNCH_DATE", "Launch Date", "Date the asset was launched", "date"),
        ("IS_STABLECOIN", "Is Stablecoin", "Whether the asset is a stablecoin", "boolean"),
        (
            "CONSENSUS_MECHANISM",
            "Consensus Mechanism",
            "Consensus mechanism (e.g. PoW, PoS)",
            "string",
        ),
        ("WHITEPAPER_URL", "Whitepaper URL", "URL to the project whitepaper", "string"),
        ("PEG_CURRENCY", "Peg Currency", "Currency this stablecoin is pegged to", "string"),
        (
            "COLLATERAL_TYPE",
            "Collateral Type",
            "Type of collateral backing (fiat, crypto, algorithmic)",
            "string",
        ),
        ("ISO_CURRENCY_CODE", "ISO Currency Code", "ISO 4217 currency code", "string"),
        ("ISSUING_COUNTRY", "Issuing Country", "Country that issues the currency", "string"),
        ("PE_RATIO", "P/E Ratio", "Price-to-earnings ratio", "float"),
        ("EPS", "EPS", "Earnings per share", "float"),
        ("DIVIDEND_YIELD", "Dividend Yield", "Annual dividend yield as a percentage", "float"),
        ("REVENUE", "Revenue", "Annual revenue in USD", "float"),
        ("EXCHANGE_LISTING", "Exchange Listing", "Primary stock exchange listing", "string"),
        ("ISIN", "ISIN", "International Securities Identification Number", "string"),
        ("SHARES_OUTSTANDING", "Shares Outstanding", "Total shares outstanding", "float"),
        ("EXPENSE_RATIO", "Expense Ratio", "Annual expense ratio as a percentage", "float"),
        ("NAV", "NAV", "Net asset value per share", "float"),
        ("TRACKING_INDEX", "Tracking Index", "Index the ETF tracks", "string"),
        ("AUM", "AUM", "Assets under management in USD", "float"),
        (
            "UNIT_OF_MEASURE",
            "Unit of Measure",
            "Standard unit (troy oz, barrel, bushel, etc.)",
            "string",
        ),
        (
            "STANDARD_CONTRACT_SIZE",
            "Standard Contract Size",
            "Standard futures contract size",
            "float",
        ),
        ("COUPON_RATE", "Coupon Rate", "Annual coupon rate as a percentage", "float"),
        ("MATURITY_DATE", "Maturity Date", "Bond maturity date", "date"),
        (
            "YIELD_TO_MATURITY",
            "Yield to Maturity",
            "Current yield to maturity as a percentage",
            "float",
        ),
        ("CREDIT_RATING", "Credit Rating", "Credit rating (AAA, AA, A, BBB, etc.)", "string"),
        ("FACE_VALUE", "Face Value", "Par/face value of the bond", "float"),
        ("ISSUER", "Issuer", "Entity that issued the bond", "string"),
        ("API_KEY_NAME", "API Key Name", "Name of the API key environment variable", "string"),
        ("RATE_LIMIT", "Rate Limit", "API rate limit (requests/minute)", "integer"),
        (
            "SUPPORTS_WEBSOCKET",
            "Supports WebSocket",
            "Whether the provider supports WebSocket connections",
            "boolean",
        ),
        ("SYMBOL", "Symbol", "The identifier/symbol used by this provider for the asset", "string"),
        (
            "PROVIDER_TICKER",
            "Provider Ticker",
            "The ticker/symbol used by this provider for the asset",
            "string",
        ),
        (
            "TRADING_PAIR_SYMBOL",
            "Trading Pair Symbol",
            "The trading pair symbol on this provider (e.g. XBTUSD)",
            "string",
        ),
        ("MIN_ORDER_SIZE", "Min Order Size", "Minimum order size on this provider", "float"),
        ("TICK_SIZE", "Tick Size", "Minimum price increment", "float"),
        ("LOT_SIZE", "Lot Size", "Minimum quantity increment", "float"),
        ("CONTRACT_SIZE", "Contract Size", "Number of units per contract", "float"),
        (
            "MARGIN_REQUIREMENT",
            "Margin Requirement",
            "Initial margin requirement as a percentage",
            "float",
        ),
        (
            "TRADING_HOURS",
            "Trading Hours",
            "Hours during which the instrument can be traded",
            "string",
        ),
        (
            "CORRELATION",
            "Correlation",
            "Pearson correlation coefficient between pair members",
            "float",
        ),
        ("HALF_LIFE", "Half Life", "Mean reversion half-life in periods", "float"),
        (
            "COINTEGRATION_PVALUE",
            "Cointegration P-Value",
            "Engle-Granger cointegration test p-value",
            "float",
        ),
        ("EXPIRY_DATE", "Expiry Date", "Contract expiration/settlement date", "date"),
        ("STRIKE_PRICE", "Strike Price", "Option strike price", "float"),
        ("OPTION_TYPE", "Option Type", "Call or Put", "string"),
        (
            "UNDERLYING_INSTRUMENT",
            "Underlying Instrument",
            "Name of the underlying instrument",
            "string",
        ),
    ]
    meta: dict[str, dict] = {}
    for name, display_name, description, value_type in meta_defs:
        m = client.create_metadata_type(
            name=name,
            display_name=display_name,
            description=description,
            value_type=value_type,
        )
        meta[name] = m

    ctx["meta"] = meta
