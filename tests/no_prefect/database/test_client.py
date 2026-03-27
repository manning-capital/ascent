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
    Provider,
    ProviderAssetAttribute,
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

    # Create the asset.
    btc_asset = Asset(asset_type_id=asset_type.id, name="Bitcoin", description="Bitcoin Asset")
    with Session(postgres_engine) as session:
        session.add(btc_asset)
        session.commit()
        session.refresh(btc_asset)

    # Create the asset.
    eth_asset = Asset(asset_type_id=asset_type.id, name="Ethereum", description="Ethereum Asset")
    with Session(postgres_engine) as session:
        session.add(eth_asset)
        session.commit()
        session.refresh(eth_asset)

    # Create the asset.
    usd_asset = Asset(asset_type_id=asset_type.id, name="US Dollar", description="US Dollar Asset")
    with Session(postgres_engine) as session:
        session.add(usd_asset)
        session.commit()
        session.refresh(usd_asset)

    # Add provider asset attributes.
    close_attribute = Attribute(name="close", description="The closing price of the asset")
    volume_attribute = Attribute(name="volume", description="The volume of the asset")
    with Session(postgres_engine) as session:
        session.add(close_attribute)
        session.add(volume_attribute)
        session.commit()
        session.refresh(close_attribute)
        session.refresh(volume_attribute)

    # Add provider asset attributes.
    with Session(postgres_engine) as session:
        start_timestamp = dt.datetime(2025, 1, 1, 0, 0, 0)
        end_timestamp = start_timestamp + dt.timedelta(days=7)
        timestamps = pd.date_range(start=start_timestamp, end=end_timestamp, freq="1h")
        fake_close_df = pd.DataFrame(
            {
                "timestamp": timestamps,
                "provider_id": [provider.id] * len(timestamps),
                "from_asset_id": [usd_asset.id] * len(timestamps),
                "to_asset_id": [btc_asset.id] * len(timestamps),
                "attribute_id": [close_attribute.id] * len(timestamps),
                "attribute_value": [float(i) for i in range(len(timestamps))],
            }
        )
        fake_volume_df = pd.DataFrame(
            {
                "timestamp": timestamps,
                "provider_id": [provider.id] * len(timestamps),
                "from_asset_id": [usd_asset.id] * len(timestamps),
                "to_asset_id": [btc_asset.id] * len(timestamps),
                "attribute_id": [volume_attribute.id] * len(timestamps),
                "attribute_value": [10.0 * float(i) for i in range(len(timestamps))],
            }
        )
        fake_df = pd.concat([fake_close_df, fake_volume_df])
        fake_df.to_sql(
            ProviderAssetAttribute.__tablename__, postgres_engine, if_exists="append", index=False
        )

        # Yield the fake data.
        yield fake_df

    # Delete the fake data.
    with Session(postgres_engine) as session:
        session.query(ProviderAssetAttribute).delete()
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


def test_database_client_can_read_provider_asset_attributes(postgres_engine: Engine):
    with AscentClient(postgres_engine) as database_client:
        start_timestamp = dt.datetime(2025, 1, 1, 0, 0, 0)
        end_timestamp = start_timestamp + dt.timedelta(days=7)
        provider_asset_attributes = database_client.get_provider_asset_attribute(
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            attributes=["close", "volume"],
        )
        assert len(provider_asset_attributes) > 0
        assert "close" in provider_asset_attributes.columns
        assert "volume" in provider_asset_attributes.columns
