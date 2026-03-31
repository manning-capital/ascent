import datetime as dt

import pandas as pd
import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from ascent.database.client import AscentClient
from ascent.database.models import (
    Asset,
    AssetType,
    Attribute,
    Instrument,
    InstrumentAttribute,
    InstrumentMember,
    InstrumentType,
    Provider,
    ProviderType,
)


@pytest.fixture(scope="function", autouse=True)
def fake_data(postgres_engine: Engine):
    # Create the provider type.
    provider_type = ProviderType(
        name="CryptoCurrencyExchange", description="CryptoCurrency Exchange Provider Type"
    )
    with Session(postgres_engine) as session:
        session.add(provider_type)
        session.commit()
        session.refresh(provider_type)

    # Create the provider.
    provider = Provider(
        provider_type_id=provider_type.id,
        name="Kraken",
        description="Kraken CryptoCurrency Exchange Provider",
    )
    with Session(postgres_engine) as session:
        session.add(provider)
        session.commit()
        session.refresh(provider)

    # Create the asset type.
    asset_type = AssetType(name="CryptoCurrency", description="CryptoCurrency Asset Type")
    with Session(postgres_engine) as session:
        session.add(asset_type)
        session.commit()
        session.refresh(asset_type)

    # Create the assets.
    btc_asset = Asset(asset_type_id=asset_type.id, name="Bitcoin", description="Bitcoin Asset")
    usd_asset = Asset(asset_type_id=asset_type.id, name="US Dollar", description="US Dollar Asset")
    with Session(postgres_engine) as session:
        session.add(btc_asset)
        session.add(usd_asset)
        session.commit()
        session.refresh(btc_asset)
        session.refresh(usd_asset)

    # Create an instrument type.
    instrument_type = InstrumentType(name="TEST_PAIR", display_name="Test Pair")
    with Session(postgres_engine) as session:
        session.add(instrument_type)
        session.commit()
        session.refresh(instrument_type)

    # Create a single-member instrument for BTC/USD.
    group = Instrument(
        name="TEST_BTC_USD",
        display_name="Test BTC/USD",
        instrument_type_id=instrument_type.id,
    )
    with Session(postgres_engine) as session:
        session.add(group)
        session.commit()
        session.refresh(group)
    member = InstrumentMember(
        instrument_id=group.id,
        provider_id=provider.id,
        from_asset_id=btc_asset.id,
        to_asset_id=usd_asset.id,
        order=1,
    )
    with Session(postgres_engine) as session:
        session.add(member)
        session.commit()

    # Add attributes.
    close_attribute = Attribute(name="close", description="The closing price of the asset")
    volume_attribute = Attribute(name="volume", description="The volume of the asset")
    with Session(postgres_engine) as session:
        session.add(close_attribute)
        session.add(volume_attribute)
        session.commit()
        session.refresh(close_attribute)
        session.refresh(volume_attribute)

    # Add instrument attribute data.
    with Session(postgres_engine) as session:
        start_timestamp = dt.datetime(2025, 1, 1, 0, 0, 0)
        end_timestamp = start_timestamp + dt.timedelta(days=7)
        timestamps = pd.date_range(start=start_timestamp, end=end_timestamp, freq="1h")
        fake_close_df = pd.DataFrame(
            {
                "timestamp": timestamps,
                "instrument_id": [str(group.id)] * len(timestamps),
                "attribute_id": [str(close_attribute.id)] * len(timestamps),
                "attribute_value": [float(i) for i in range(len(timestamps))],
            }
        )
        fake_volume_df = pd.DataFrame(
            {
                "timestamp": timestamps,
                "instrument_id": [str(group.id)] * len(timestamps),
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

        # Yield the fake data along with the instrument ID.
        yield {"df": fake_df, "instrument_id": group.id}

    # Delete the fake data.
    with Session(postgres_engine) as session:
        session.query(InstrumentAttribute).delete()
        session.query(InstrumentMember).delete()
        session.query(Instrument).delete()
        session.query(InstrumentType).delete()
        session.query(Attribute).delete()
        session.query(Provider).delete()
        session.query(ProviderType).delete()
        session.query(Asset).delete()
        session.query(AssetType).delete()
        session.commit()


def test_attributes_are_created(postgres_engine: Engine):
    with Session(postgres_engine) as session:
        attributes = session.query(Attribute).all()
        assert len(attributes) > 0
        assert "close" in [attribute.name for attribute in attributes]
        assert "volume" in [attribute.name for attribute in attributes]


def test_database_client_can_read_instrument_attributes(fake_data, postgres_engine: Engine):
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
