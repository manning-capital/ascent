"""Seed attributes and metadata types."""

from __future__ import annotations

from typing import Any


def seed_descriptors(client: Any, ctx: dict) -> None:
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
    ctx["attr_ou_mu"] = client.create_attribute(
        name="OU_MU",
        display_name="OU Mu",
        description="OU mean-reversion speed (kappa) — rate at which the spread returns to theta",
    )
    ctx["attr_ou_theta"] = client.create_attribute(
        name="OU_THETA",
        display_name="OU Theta",
        description="OU long-run mean — the equilibrium level the spread reverts to",
    )
    ctx["attr_ou_sigma"] = client.create_attribute(
        name="OU_SIGMA",
        display_name="OU Sigma",
        description="OU diffusion coefficient — per-unit-time volatility of the spread",
    )
    ctx["attr_ou_beta"] = client.create_attribute(
        name="OU_BETA",
        display_name="OU Beta",
        description="Hedge ratio used in the log-spread: s = ln(p_a) - beta * ln(p_b)",
    )
    ctx["attr_ou_entry"] = client.create_attribute(
        name="OU_ENTRY",
        display_name="OU Entry",
        description="Leung-Li optimal spread level at which to open a mean-reversion trade",
    )
    ctx["attr_ou_exit"] = client.create_attribute(
        name="OU_EXIT",
        display_name="OU Exit",
        description="Leung-Li optimal spread level at which to close a mean-reversion trade",
    )
    ctx["attr_ou_spread"] = client.create_attribute(
        name="OU_SPREAD",
        display_name="OU Spread",
        description="Per-tick log-spread s = ln(p_a) - beta*ln(p_b) for the composite",
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
        ctx["attr_ou_mu"],
        ctx["attr_ou_theta"],
        ctx["attr_ou_sigma"],
        ctx["attr_ou_beta"],
        ctx["attr_ou_entry"],
        ctx["attr_ou_exit"],
        ctx["attr_ou_spread"],
    ]

    # --- Metadata types ---

    # Each entry: (name, display_name, description, value_type, config_or_None)
    meta_defs: list[tuple[str, str, str, str, dict | None]] = [
        # --- Float ---
        ("MARKET_CAP", "Market Cap", "Market capitalization in USD", "float", None),
        (
            "CIRCULATING_SUPPLY",
            "Circulating Supply",
            "Circulating supply of the asset",
            "float",
            None,
        ),
        ("MAX_SUPPLY", "Max Supply", "Maximum supply of the asset", "float", None),
        ("PE_RATIO", "P/E Ratio", "Price-to-earnings ratio", "float", None),
        ("EPS", "EPS", "Earnings per share", "float", None),
        (
            "DIVIDEND_YIELD",
            "Dividend Yield",
            "Annual dividend yield as a percentage",
            "float",
            None,
        ),
        ("REVENUE", "Revenue", "Annual revenue in USD", "float", None),
        ("SHARES_OUTSTANDING", "Shares Outstanding", "Total shares outstanding", "float", None),
        ("EXPENSE_RATIO", "Expense Ratio", "Annual expense ratio as a percentage", "float", None),
        ("NAV", "NAV", "Net asset value per share", "float", None),
        ("AUM", "AUM", "Assets under management in USD", "float", None),
        (
            "STANDARD_CONTRACT_SIZE",
            "Standard Contract Size",
            "Standard futures contract size",
            "float",
            None,
        ),
        ("COUPON_RATE", "Coupon Rate", "Annual coupon rate as a percentage", "float", None),
        (
            "YIELD_TO_MATURITY",
            "Yield to Maturity",
            "Current yield to maturity as a percentage",
            "float",
            None,
        ),
        ("FACE_VALUE", "Face Value", "Par/face value of the bond", "float", None),
        ("MIN_ORDER_SIZE", "Min Order Size", "Minimum order size on this provider", "float", None),
        ("TICK_SIZE", "Tick Size", "Minimum price increment", "float", None),
        ("LOT_SIZE", "Lot Size", "Minimum quantity increment", "float", None),
        ("CONTRACT_SIZE", "Contract Size", "Number of units per contract", "float", None),
        (
            "MARGIN_REQUIREMENT",
            "Margin Requirement",
            "Initial margin requirement as a percentage",
            "float",
            None,
        ),
        (
            "CORRELATION",
            "Correlation",
            "Pearson correlation coefficient between pair members",
            "float",
            None,
        ),
        ("HALF_LIFE", "Half Life", "Mean reversion half-life in periods", "float", None),
        (
            "COINTEGRATION_PVALUE",
            "Cointegration P-Value",
            "Engle-Granger cointegration test p-value",
            "float",
            None,
        ),
        ("STRIKE_PRICE", "Strike Price", "Option strike price", "float", None),
        # --- Integer ---
        ("RATE_LIMIT", "Rate Limit", "API rate limit (requests/minute)", "integer", None),
        # --- Boolean ---
        ("IS_STABLECOIN", "Is Stablecoin", "Whether the asset is a stablecoin", "boolean", None),
        (
            "SUPPORTS_WEBSOCKET",
            "Supports WebSocket",
            "Whether the provider supports WebSocket connections",
            "boolean",
            None,
        ),
        # --- Date ---
        ("LAUNCH_DATE", "Launch Date", "Date the asset was launched", "date", None),
        ("MATURITY_DATE", "Maturity Date", "Bond maturity date", "date", None),
        ("EXPIRY_DATE", "Expiry Date", "Contract expiration/settlement date", "date", None),
        # --- String ---
        ("WHITEPAPER_URL", "Whitepaper URL", "URL to the project whitepaper", "string", None),
        ("ISO_CURRENCY_CODE", "ISO Currency Code", "ISO 4217 currency code", "string", None),
        ("ISSUING_COUNTRY", "Issuing Country", "Country that issues the currency", "string", None),
        ("ISIN", "ISIN", "International Securities Identification Number", "string", None),
        ("TRACKING_INDEX", "Tracking Index", "Index the ETF tracks", "string", None),
        ("ISSUER", "Issuer", "Entity that issued the bond", "string", None),
        (
            "API_KEY_NAME",
            "API Key Name",
            "Name of the API key environment variable",
            "string",
            None,
        ),
        (
            "SYMBOL",
            "Symbol",
            "The identifier/symbol used by this provider for the asset",
            "string",
            None,
        ),
        (
            "PROVIDER_TICKER",
            "Provider Ticker",
            "The ticker/symbol used by this provider for the asset",
            "string",
            None,
        ),
        (
            "TRADING_PAIR_SYMBOL",
            "Trading Pair Symbol",
            "The trading pair symbol on this provider (e.g. XBTUSD)",
            "string",
            None,
        ),
        # --- Enum ---
        (
            "SECTOR",
            "Sector",
            "Industry sector classification",
            "enum",
            {
                "type": "enum",
                "options": [
                    "Technology",
                    "Financials",
                    "Healthcare",
                    "Consumer Discretionary",
                    "Broad Market",
                    "Small Cap",
                    "Fixed Income",
                    "Commodities",
                    "Store of Value",
                    "Smart Contract Platform",
                    "DeFi",
                    "Layer 2",
                    "Oracle",
                    "Interoperability",
                    "Payments",
                    "Meme",
                    "Data Availability",
                    "Fiat",
                    "Stablecoin",
                ],
            },
        ),
        (
            "CONSENSUS_MECHANISM",
            "Consensus Mechanism",
            "Consensus mechanism used by the network",
            "enum",
            {
                "type": "enum",
                "options": [
                    "Proof of Work",
                    "Proof of Stake",
                    "Delegated Proof of Stake",
                    "Proof of History",
                    "Nominated Proof of Stake",
                    "Tendermint BFT",
                    "Avalanche Consensus",
                    "AptosBFT",
                    "Optimistic Rollup",
                    "Nightshade PoS",
                    "Lachesis aBFT",
                    "Narwhal/Bullshark",
                    "Twin-Turbo Consensus",
                    "XRP Ledger Consensus",
                    "N/A (ERC-20)",
                    "N/A (Solana SPL)",
                ],
            },
        ),
        (
            "COLLATERAL_TYPE",
            "Collateral Type",
            "Type of collateral backing",
            "enum",
            {
                "type": "enum",
                "options": [
                    "fiat-backed",
                    "crypto-collateralized",
                    "algorithmic",
                    "commodity-backed",
                ],
            },
        ),
        (
            "PEG_CURRENCY",
            "Peg Currency",
            "Currency this stablecoin is pegged to",
            "enum",
            {
                "type": "enum",
                "options": ["USD", "EUR", "GBP", "JPY", "CHF", "XAU"],
            },
        ),
        (
            "CREDIT_RATING",
            "Credit Rating",
            "Credit rating",
            "enum",
            {
                "type": "enum",
                "options": [
                    "AAA",
                    "AA+",
                    "AA",
                    "AA-",
                    "A+",
                    "A",
                    "A-",
                    "BBB+",
                    "BBB",
                    "BBB-",
                    "BB+",
                    "BB",
                    "BB-",
                    "B+",
                    "B",
                    "B-",
                    "CCC",
                    "CC",
                    "C",
                    "D",
                ],
            },
        ),
        (
            "EXCHANGE_LISTING",
            "Exchange Listing",
            "Primary stock exchange listing",
            "enum",
            {
                "type": "enum",
                "options": [
                    "NYSE",
                    "NASDAQ",
                    "NYSE Arca",
                    "LSE",
                    "TSE",
                    "HKEX",
                    "Euronext",
                    "XETRA",
                ],
            },
        ),
        (
            "OPTION_TYPE",
            "Option Type",
            "Call or Put",
            "enum",
            {
                "type": "enum",
                "options": ["Call", "Put"],
            },
        ),
        (
            "UNIT_OF_MEASURE",
            "Unit of Measure",
            "Standard unit of measurement",
            "enum",
            {
                "type": "enum",
                "options": [
                    "troy oz",
                    "pound",
                    "metric ton",
                    "barrel",
                    "gallon",
                    "MMBtu",
                    "bushel",
                ],
            },
        ),
        (
            "TRADING_HOURS",
            "Trading Hours",
            "Hours during which the instrument can be traded",
            "enum",
            {
                "type": "enum",
                "options": [
                    "24/7",
                    "09:30-16:00 ET",
                    "18:00-17:00 ET (Sun-Fri)",
                    "08:00-16:30 GMT",
                ],
            },
        ),
        # --- Reference ---
        (
            "UNDERLYING_INSTRUMENT",
            "Underlying Instrument",
            "The underlying instrument this derivative is based on",
            "reference",
            {
                "type": "reference",
                "ref_table": "instrument",
            },
        ),
    ]
    meta: dict[str, dict] = {}
    for name, display_name, description, value_type, config in meta_defs:
        m = client.create_metadata_type(
            name=name,
            display_name=display_name,
            description=description,
            value_type=value_type,
            config=config,
        )
        meta[name] = m

    ctx["meta"] = meta
