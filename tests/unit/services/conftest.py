"""
Unit service test conftest — provides lightweight mock model fixtures
for service unit tests.
"""

import uuid
from unittest.mock import MagicMock

import pytest

from ascent.database.models import (
    Asset,
    AssetType,
    Instrument,
    InstrumentType,
    Provider,
    ProviderType,
    TradeStatusType,
)


@pytest.fixture
def mock_asset_type():
    """MagicMock(spec=AssetType) with realistic attributes."""
    at = MagicMock(spec=AssetType)
    at.id = uuid.uuid4()
    at.name = "CRYPTO"
    at.display_name = "Cryptocurrency"
    at.description = "Cryptocurrency assets"
    at.is_active = True
    at.parent_type_id = None
    return at


@pytest.fixture
def mock_asset(mock_asset_type):
    """MagicMock(spec=Asset) wired to mock_asset_type."""
    a = MagicMock(spec=Asset)
    a.id = uuid.uuid4()
    a.name = "BTC"
    a.display_name = "Bitcoin"
    a.description = "Bitcoin asset"
    a.asset_type_id = mock_asset_type.id
    a.asset_type = mock_asset_type
    a.is_active = True
    a.underlying_asset_id = None
    return a


@pytest.fixture
def mock_provider_type():
    """MagicMock(spec=ProviderType) with realistic attributes."""
    pt = MagicMock(spec=ProviderType)
    pt.id = uuid.uuid4()
    pt.name = "EXCHANGE"
    pt.display_name = "Exchange"
    pt.description = "Exchange provider type"
    pt.is_active = True
    pt.parent_type_id = None
    return pt


@pytest.fixture
def mock_provider(mock_provider_type):
    """MagicMock(spec=Provider) wired to mock_provider_type."""
    p = MagicMock(spec=Provider)
    p.id = uuid.uuid4()
    p.name = "KRAKEN"
    p.display_name = "Kraken"
    p.description = "Kraken exchange"
    p.provider_type_id = mock_provider_type.id
    p.provider_type = mock_provider_type
    p.is_active = True
    return p


@pytest.fixture
def mock_instrument_type():
    """MagicMock(spec=InstrumentType) with realistic attributes."""
    it = MagicMock(spec=InstrumentType)
    it.id = uuid.uuid4()
    it.name = "SPOT_PAIR"
    it.display_name = "Spot Pair"
    it.description = "Spot trading pair"
    it.is_active = True
    it.parent_type_id = None
    return it


@pytest.fixture
def mock_instrument(mock_instrument_type, mock_provider, mock_asset):
    """MagicMock(spec=Instrument) wired to mock_instrument_type, mock_provider, mock_asset."""
    inst = MagicMock(spec=Instrument)
    inst.id = uuid.uuid4()
    inst.name = "KRAKEN_BTC_USD"
    inst.display_name = "BTC/USD"
    inst.instrument_type_id = mock_instrument_type.id
    inst.instrument_type = mock_instrument_type
    inst.provider_id = mock_provider.id
    inst.provider = mock_provider
    inst.from_asset_id = mock_asset.id
    inst.is_active = True
    return inst


@pytest.fixture
def mock_trade_status_types():
    """Dict mapping status name → MagicMock(spec=TradeStatusType)."""
    statuses = {}
    for name in ["PENDING", "OPENING", "OPEN", "CLOSING", "CLOSED", "CANCELLED", "ERROR"]:
        ts = MagicMock(spec=TradeStatusType)
        ts.id = uuid.uuid4()
        ts.name = name
        ts.display_name = name.title()
        ts.is_active = True
        statuses[name] = ts
    return statuses
