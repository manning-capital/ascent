"""
Tests for AscentClient — verifies that the database client can read
instrument attributes from TimescaleDB hypertables.

Migrated from tests/no_prefect/database/test_client.py.
Uses the session-scoped test_env fixture from the integration conftest.
"""

import datetime as dt

import pandas as pd
import pytest

from ascent.database.client import AscentClient
from ascent.database.models import (
    Asset,
    AssetType,
    Attribute,
    Instrument,
    InstrumentAttribute,
    InstrumentType,
    Provider,
    ProviderType,
)


@pytest.fixture
def fake_data(postgres_engine, db_session):
    """Create a full test schema with instrument and time-series attribute data."""
    # Create provider type and provider
    provider_type = ProviderType(
        name="CryptoCurrencyExchange",
        display_name="CryptoCurrency Exchange",
        description="CryptoCurrency Exchange Provider Type",
    )
    db_session.add(provider_type)
    db_session.commit()
    db_session.refresh(provider_type)

    provider = Provider(
        provider_type_id=provider_type.id,
        name="Kraken",
        display_name="Kraken",
        description="Kraken CryptoCurrency Exchange Provider",
    )
    db_session.add(provider)
    db_session.commit()
    db_session.refresh(provider)

    # Create asset type and assets
    asset_type = AssetType(
        name="CryptoCurrency",
        display_name="CryptoCurrency",
        description="CryptoCurrency Asset Type",
    )
    db_session.add(asset_type)
    db_session.commit()
    db_session.refresh(asset_type)

    btc_asset = Asset(
        asset_type_id=asset_type.id,
        name="Bitcoin",
        display_name="Bitcoin",
        description="Bitcoin Asset",
    )
    usd_asset = Asset(
        asset_type_id=asset_type.id,
        name="US_Dollar",
        display_name="US Dollar",
        description="US Dollar Asset",
    )
    db_session.add_all([btc_asset, usd_asset])
    db_session.commit()
    db_session.refresh(btc_asset)
    db_session.refresh(usd_asset)

    # Create instrument type and instrument
    instrument_type = InstrumentType(name="TEST_PAIR", display_name="Test Pair")
    db_session.add(instrument_type)
    db_session.commit()
    db_session.refresh(instrument_type)

    instrument = Instrument(
        name="TEST_BTC_USD",
        display_name="Test BTC/USD",
        instrument_type_id=instrument_type.id,
        provider_id=provider.id,
        from_asset_id=btc_asset.id,
        to_asset_id=usd_asset.id,
    )
    db_session.add(instrument)
    db_session.commit()
    db_session.refresh(instrument)

    # Add attributes
    close_attribute = Attribute(
        name="close", display_name="Close", description="The closing price of the asset"
    )
    volume_attribute = Attribute(
        name="volume", display_name="Volume", description="The volume of the asset"
    )
    db_session.add_all([close_attribute, volume_attribute])
    db_session.commit()
    db_session.refresh(close_attribute)
    db_session.refresh(volume_attribute)

    # Add instrument attribute time-series data
    start_timestamp = dt.datetime(2025, 1, 1, 0, 0, 0)
    end_timestamp = start_timestamp + dt.timedelta(days=7)
    timestamps = pd.date_range(start=start_timestamp, end=end_timestamp, freq="1h")

    fake_close_df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "instrument_id": [str(instrument.id)] * len(timestamps),
            "attribute_id": [str(close_attribute.id)] * len(timestamps),
            "attribute_value": [float(i) for i in range(len(timestamps))],
        }
    )
    fake_volume_df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "instrument_id": [str(instrument.id)] * len(timestamps),
            "attribute_id": [str(volume_attribute.id)] * len(timestamps),
            "attribute_value": [10.0 * float(i) for i in range(len(timestamps))],
        }
    )
    fake_df = pd.concat([fake_close_df, fake_volume_df])
    fake_df.to_sql(
        InstrumentAttribute.__tablename__,
        postgres_engine,
        if_exists="append",
        index=False,
    )

    return {"df": fake_df, "instrument_id": instrument.id}


def test_attributes_are_created(fake_data, db_session):
    attributes = db_session.query(Attribute).all()
    assert len(attributes) > 0
    assert "close" in [attribute.name for attribute in attributes]
    assert "volume" in [attribute.name for attribute in attributes]


def test_database_client_can_read_instrument_attributes(fake_data, postgres_engine):
    instrument_id = fake_data["instrument_id"]
    with AscentClient(postgres_engine) as database_client:
        start_timestamp = dt.datetime(2025, 1, 1, 0, 0, 0)
        end_timestamp = start_timestamp + dt.timedelta(days=7)
        group_attributes = database_client.get_instrument_attribute(
            instrument_id=instrument_id,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            attributes=["close", "volume"],
        )
        assert len(group_attributes) > 0
        assert "close" in group_attributes.columns
        assert "volume" in group_attributes.columns
