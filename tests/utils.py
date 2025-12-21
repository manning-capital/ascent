import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir, "src"))

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from ascent.database.models import (
    Asset,
    Provider,
    AssetType,
    ProviderType,
)
from ascent.database.testing.utilties import clear_database


def create_base_data(
    engine: Engine,
) -> tuple[AssetType, Asset, Asset, Asset, ProviderType, Provider]:
    # Create a new asset type.
    with Session(engine) as session:
        # Clear the database.
        clear_database(engine)

        # Create a new asset type.
        asset_type = AssetType(
            name="CryptoCurrency",
            description="CryptoCurrency Asset Type",
        )
        session.add(asset_type)
        session.commit()
        session.refresh(asset_type)

    with Session(engine) as session:
        # Create a from asset.
        btc_asset = Asset(
            asset_type_id=asset_type.id,
            name="Bitcoin",
            description="Bitcoin Asset",
            symbol="BTC",
            is_active=True,
        )
        session.add(btc_asset)
        session.commit()
        session.refresh(btc_asset)

    with Session(engine) as session:
        # Create a to asset.
        eth_asset = Asset(
            asset_type_id=asset_type.id,
            name="Ethereum",
            description="Ethereum Asset",
            symbol="ETH",
            is_active=True,
        )
        session.add(eth_asset)
        session.commit()
        session.refresh(eth_asset)

    with Session(engine) as session:
        # Create the USD asset.
        usd_asset = Asset(
            asset_type_id=asset_type.id,
            name="US Dollar",
            description="US Dollar Asset",
            symbol="USD",
            is_active=True,
        )
        session.add(usd_asset)
        session.commit()
        session.refresh(usd_asset)

    with Session(engine) as session:
        # Create a new provider type.
        provider_type = ProviderType(
            name="CryptoCurrencyExchange",
            description="CryptoCurrency Exchange Provider Type",
        )
        session.add(provider_type)
        session.commit()
        session.refresh(provider_type)

    with Session(engine) as session:
        # Create a new provider.
        provider = Provider(
            provider_type_id=provider_type.id,
            name="Kraken",
            description="Kraken CryptoCurrency Exchange Provider",
        )
        session.add(provider)
        session.commit()
        session.refresh(provider)

    return asset_type, btc_asset, eth_asset, usd_asset, provider_type, provider
