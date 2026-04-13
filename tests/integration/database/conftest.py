"""
Integration database conftest — composable entity fixtures following
the entity dependency chain.

Each test requests only the fixtures it needs. Fixtures build on each other:
  base_types → base_assets → base_instruments → base_composite → ...
"""

import pytest

from ascent.database.models import (
    Asset,
    AssetType,
    Attribute,
    Composite,
    CompositeMember,
    CompositeType,
    Exchange,
    Feed,
    Instrument,
    InstrumentType,
    Metadata,
    OrderStatusType,
    OrderType,
    Portfolio,
    Provider,
    ProviderType,
    Strategy,
    TradeStatusType,
)
from tests.factories import (
    make_asset,
    make_asset_type,
    make_attribute,
    make_composite,
    make_composite_type,
    make_exchange,
    make_feed,
    make_instrument,
    make_instrument_type,
    make_metadata,
    make_order_status_type,
    make_order_type,
    make_portfolio,
    make_provider,
    make_provider_type,
    make_strategy,
    make_trade_status_type,
)


@pytest.fixture
def base_types(db_session) -> dict:
    """Create all foundational type entities.

    Returns dict with keys:
        asset_type, provider_type, instrument_type,
        composite_type, order_type,
        order_status_type, trade_status_types (dict[str, TradeStatusType])
    """
    asset_type = AssetType(**make_asset_type(name="CRYPTO", display_name="Cryptocurrency"))
    provider_type = ProviderType(**make_provider_type(name="EXCHANGE", display_name="Exchange"))
    instrument_type = InstrumentType(
        **make_instrument_type(name="SPOT_PAIR", display_name="Spot Pair")
    )
    composite_type = CompositeType(**make_composite_type(name="SPREAD", display_name="Spread"))
    order_type = OrderType(**make_order_type(name="MARKET", display_name="Market"))
    order_status_type = OrderStatusType(
        **make_order_status_type(name="SUBMITTED", display_name="Submitted")
    )

    db_session.add_all(
        [
            asset_type,
            provider_type,
            instrument_type,
            composite_type,
            order_type,
            order_status_type,
        ]
    )

    # Trade status types (full state machine)
    trade_status_types = {}
    for name in ["PENDING", "OPENING", "OPEN", "CLOSING", "CLOSED", "CANCELLED", "ERROR"]:
        tst = TradeStatusType(**make_trade_status_type(name))
        db_session.add(tst)
        trade_status_types[name] = tst

    db_session.commit()

    # Refresh all to get server-generated fields
    for obj in [
        asset_type,
        provider_type,
        instrument_type,
        composite_type,
        order_type,
        order_status_type,
    ]:
        db_session.refresh(obj)
    for tst in trade_status_types.values():
        db_session.refresh(tst)

    return {
        "asset_type": asset_type,
        "provider_type": provider_type,
        "instrument_type": instrument_type,
        "composite_type": composite_type,
        "order_type": order_type,
        "order_status_type": order_status_type,
        "trade_status_types": trade_status_types,
    }


@pytest.fixture
def base_assets(db_session, base_types) -> dict:
    """Create BTC, ETH, USD assets.

    Returns dict mapping symbol → Asset.
    """
    at_id = base_types["asset_type"].id
    btc = Asset(**make_asset(at_id, name="BTC", display_name="Bitcoin"))
    eth = Asset(**make_asset(at_id, name="ETH", display_name="Ethereum"))
    usd = Asset(**make_asset(at_id, name="USD", display_name="US Dollar"))

    db_session.add_all([btc, eth, usd])
    db_session.commit()
    for a in [btc, eth, usd]:
        db_session.refresh(a)

    return {"BTC": btc, "ETH": eth, "USD": usd}


@pytest.fixture
def base_metadata_defs(db_session) -> dict:
    """Create Attribute and Metadata definitions.

    Returns dict mapping name → model.
    """
    close_attr = Attribute(**make_attribute(name="CLOSE", display_name="Close"))
    volume_attr = Attribute(**make_attribute(name="VOLUME", display_name="Volume"))
    symbol_meta = Metadata(
        **make_metadata(name="SYMBOL", display_name="Symbol", value_type="string")
    )

    db_session.add_all([close_attr, volume_attr, symbol_meta])
    db_session.commit()
    for obj in [close_attr, volume_attr, symbol_meta]:
        db_session.refresh(obj)

    return {
        "close_attribute": close_attr,
        "volume_attribute": volume_attr,
        "symbol_metadata": symbol_meta,
    }


@pytest.fixture
def base_provider(db_session, base_types) -> Provider:
    """Create a Kraken provider."""
    provider = Provider(
        **make_provider(
            base_types["provider_type"].id,
            name="KRAKEN",
            display_name="Kraken",
        )
    )
    db_session.add(provider)
    db_session.commit()
    db_session.refresh(provider)
    return provider


@pytest.fixture
def base_exchange(db_session, base_types, base_provider) -> Exchange:
    """Create an exchange linked to the provider."""
    exchange = Exchange(
        **make_exchange(
            name="KRAKEN_SPOT",
            display_name="Kraken Spot",
            provider_id=base_provider.id,
            instrument_type_id=base_types["instrument_type"].id,
        )
    )
    db_session.add(exchange)
    db_session.commit()
    db_session.refresh(exchange)
    return exchange


@pytest.fixture
def base_instruments(db_session, base_types, base_assets, base_provider) -> dict:
    """Create BTC/USD and ETH/USD instruments.

    Returns dict mapping name → Instrument.
    """
    it_id = base_types["instrument_type"].id
    p_id = base_provider.id

    btc_usd = Instrument(
        **make_instrument(
            it_id,
            p_id,
            base_assets["BTC"].id,
            base_assets["USD"].id,
            name="KRAKEN_BTC_USD",
            display_name="BTC/USD",
        )
    )
    eth_usd = Instrument(
        **make_instrument(
            it_id,
            p_id,
            base_assets["ETH"].id,
            base_assets["USD"].id,
            name="KRAKEN_ETH_USD",
            display_name="ETH/USD",
        )
    )

    db_session.add_all([btc_usd, eth_usd])
    db_session.commit()
    for inst in [btc_usd, eth_usd]:
        db_session.refresh(inst)

    return {"BTC_USD": btc_usd, "ETH_USD": eth_usd}


@pytest.fixture
def base_composite(db_session, base_types, base_instruments) -> Composite:
    """Create a composite with BTC/USD and ETH/USD as members."""
    composite = Composite(
        **make_composite(
            base_types["composite_type"].id,
            name="BTC_ETH_SPREAD",
            display_name="BTC/ETH Spread",
        )
    )
    db_session.add(composite)
    db_session.flush()

    member1 = CompositeMember(
        composite_id=composite.id,
        instrument_id=base_instruments["BTC_USD"].id,
        order=1,
    )
    member2 = CompositeMember(
        composite_id=composite.id,
        instrument_id=base_instruments["ETH_USD"].id,
        order=2,
    )
    db_session.add_all([member1, member2])
    db_session.commit()
    db_session.refresh(composite)
    return composite


@pytest.fixture
def base_portfolio(db_session) -> Portfolio:
    """Create a portfolio."""
    portfolio = Portfolio(**make_portfolio(name="TEST_PORTFOLIO", display_name="Test Portfolio"))
    db_session.add(portfolio)
    db_session.commit()
    db_session.refresh(portfolio)
    return portfolio


@pytest.fixture
def base_feed(db_session, base_types, base_provider) -> Feed:
    """Create a feed."""
    feed = Feed(
        **make_feed(
            base_provider.id,
            instrument_type_id=base_types["instrument_type"].id,
            name="TEST_MARKET_DATA",
            display_name="Test Market Data",
        )
    )
    db_session.add(feed)
    db_session.commit()
    db_session.refresh(feed)
    return feed


@pytest.fixture
def base_strategy(db_session, base_types, base_portfolio) -> Strategy:
    """Create a strategy."""
    strategy = Strategy(
        **make_strategy(
            base_portfolio.id,
            name="TEST_PAIRS",
            display_name="Test Pairs Trading",
        )
    )
    db_session.add(strategy)
    db_session.commit()
    db_session.refresh(strategy)
    return strategy


@pytest.fixture
def full_scenario(
    base_types,
    base_assets,
    base_metadata_defs,
    base_provider,
    base_exchange,
    base_instruments,
    base_composite,
    base_portfolio,
    base_feed,
    base_strategy,
) -> dict:
    """Convenience fixture that returns a single dict with all entities."""
    return {
        "types": base_types,
        "assets": base_assets,
        "metadata_defs": base_metadata_defs,
        "provider": base_provider,
        "exchange": base_exchange,
        "instruments": base_instruments,
        "composite": base_composite,
        "portfolio": base_portfolio,
        "feed": base_feed,
        "strategy": base_strategy,
    }
