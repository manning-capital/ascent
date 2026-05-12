"""Fixtures for SQL-backed adapter conformance tests.

Builds on the session-scoped Docker TimescaleDB harness from the parent
``tests/integration/conftest.py`` and adds the minimum row seeding needed to
run repository adapters end-to-end.

The goal is NOT to replay every fake contract test against SQL — that would
be over-engineered. The goal is to prove the two specific bugs we've already
hit (fake-vs-real drift on ``set_entry_order`` linking and
``set_external_id`` idempotency) actually hold against a real TimescaleDB.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy.orm import Session, sessionmaker

from ascent.adapters import OrmMappers, TypeCache
from ascent.adapters.sqlalchemy.order_repo import SqlAlchemyOrderRepository
from ascent.adapters.sqlalchemy.trade_repo import SqlAlchemyTradeRepository
from ascent.database.models.assets import Asset
from ascent.database.models.exchanges import Exchange
from ascent.database.models.instruments import Instrument
from ascent.database.models.portfolio import Portfolio
from ascent.database.models.providers import Provider
from ascent.database.models.strategy import Strategy
from ascent.database.models.types import (
    AssetType,
    CompositeType,
    InstrumentType,
    OrderStatusType,
    OrderType,
    ProviderType,
    TradeStatusType,
)


@dataclass(frozen=True)
class SeededIds:
    strategy_id: uuid.UUID
    portfolio_id: uuid.UUID
    exchange_id: uuid.UUID
    instrument_id_a: uuid.UUID
    instrument_id_b: uuid.UUID


@pytest.fixture(scope="function")
def seeded_ids(postgres_engine) -> SeededIds:
    """Seed the minimum set of DB rows the adapters need before any test.

    The ``_reset_db`` autouse fixture has already dropped + recreated the
    schema, so this runs on a clean slate. Only seeds what the repositories
    dereference via FK — no market data, no orders, no trades.
    """
    with Session(postgres_engine) as db:
        # Type lookups used by TypeCache.
        _ensure_type_rows(db)

        asset_type = AssetType(name="CURRENCY", display_name="Currency", is_active=True)
        provider_type = ProviderType(name="EXCHANGE", display_name="Exchange", is_active=True)
        instrument_type = InstrumentType(name="SECURITY", display_name="Security", is_active=True)
        db.add_all([asset_type, provider_type, instrument_type])
        db.flush()

        asset_a = Asset(
            name="BASE",
            display_name="Base",
            asset_type_id=asset_type.id,
        )
        asset_b = Asset(
            name="QUOTE",
            display_name="Quote",
            asset_type_id=asset_type.id,
        )
        db.add_all([asset_a, asset_b])
        db.flush()

        provider = Provider(
            name="TEST_PROVIDER",
            display_name="Test Provider",
            provider_type_id=provider_type.id,
        )
        db.add(provider)
        db.flush()

        inst_a = Instrument(
            name="TEST_INSTRUMENT_A",
            display_name="Test Instrument A",
            instrument_type_id=instrument_type.id,
            provider_id=provider.id,
            from_asset_id=asset_a.id,
            to_asset_id=asset_b.id,
        )
        inst_b = Instrument(
            name="TEST_INSTRUMENT_B",
            display_name="Test Instrument B",
            instrument_type_id=instrument_type.id,
            provider_id=provider.id,
            from_asset_id=asset_a.id,
            to_asset_id=asset_b.id,
        )
        db.add_all([inst_a, inst_b])
        db.flush()

        portfolio = Portfolio(name="TEST_PORTFOLIO", display_name="Test Portfolio")
        db.add(portfolio)
        db.flush()

        strategy = Strategy(
            name="TEST_STRATEGY",
            display_name="Test Strategy",
            strategy_ref="TEST_STRATEGY",
            parameters={},
            parameter_schema={},
        )
        exchange = Exchange(
            name="TEST_EXCHANGE",
            display_name="Test Exchange",
            provider_id=provider.id,
            instrument_type_id=instrument_type.id,
            implementation_class="tests.fakes:TestExchange",
            config={},
        )
        db.add_all([strategy, exchange])
        db.commit()

        return SeededIds(
            strategy_id=strategy.id,
            exchange_id=exchange.id,
            instrument_id_a=inst_a.id,
            instrument_id_b=inst_b.id,
        )


def _ensure_type_rows(db: Session) -> None:
    """Seed all enum-backing type tables TypeCache looks up."""
    trade_status_names = [
        "PENDING",
        "OPENING",
        "OPEN",
        "CLOSING",
        "CLOSED",
        "CANCELLED",
        "ERROR",
    ]
    order_status_names = [
        "SUBMITTED",
        "PARTIALLY_FILLED",
        "FILLED",
        "REJECTED",
        "CANCELLED",
    ]
    order_type_names = ["MARKET", "LIMIT"]

    db.add_all([TradeStatusType(name=n, display_name=n.title()) for n in trade_status_names])
    db.add_all([OrderStatusType(name=n, display_name=n.title()) for n in order_status_names])
    db.add_all([OrderType(name=n, display_name=n.title()) for n in order_type_names])

    # Composite types — not used directly here but some migrations assume rows exist.
    db.add(CompositeType(name="SPREAD", display_name="Spread", min_members=2, max_members=2))

    db.commit()


@pytest.fixture(scope="function")
def sql_session_factory(postgres_engine) -> sessionmaker:
    return sessionmaker(bind=postgres_engine)


@pytest.fixture(scope="function")
def sql_type_cache(sql_session_factory, seeded_ids) -> TypeCache:
    return TypeCache(sql_session_factory)


@pytest.fixture(scope="function")
def sql_mappers(sql_type_cache) -> OrmMappers:
    return OrmMappers(sql_type_cache)


@pytest.fixture(scope="function")
def sql_trade_repo(sql_type_cache, sql_mappers):
    return SqlAlchemyTradeRepository(sql_type_cache, sql_mappers)


@pytest.fixture(scope="function")
def sql_order_repo(sql_type_cache, sql_mappers):
    return SqlAlchemyOrderRepository(sql_type_cache, sql_mappers)


@pytest.fixture(scope="function")
def sql_uow_factory(sql_session_factory):
    from ascent.adapters import SqlAlchemyUnitOfWorkFactory

    return SqlAlchemyUnitOfWorkFactory(sql_session_factory)
