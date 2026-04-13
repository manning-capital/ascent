"""
Integration API conftest — seed helpers that create data through the
TestClient (end-to-end through the real FastAPI stack).
"""

import pytest


@pytest.fixture
def seed_types(client) -> dict:
    """POST types via /api/types/* endpoints.

    Returns dict mapping type category + name → UUID, e.g.:
        {"asset_type_CRYPTO": uuid, "provider_type_EXCHANGE": uuid, ...}
    """
    type_configs = [
        ("asset-types", {"name": "CRYPTO", "display_name": "Cryptocurrency"}),
        ("provider-types", {"name": "EXCHANGE", "display_name": "Exchange"}),
        ("exchange-types", {"name": "SPOT", "display_name": "Spot"}),
        ("instrument-types", {"name": "SPOT_PAIR", "display_name": "Spot Pair"}),
        ("composite-types", {"name": "SPREAD", "display_name": "Spread"}),
        ("feed-types", {"name": "MARKET_DATA", "display_name": "Market Data"}),
        ("strategy-types", {"name": "PAIRS_TRADING", "display_name": "Pairs Trading"}),
        ("trade-status-types", {"name": "PENDING", "display_name": "Pending"}),
        ("trade-status-types", {"name": "OPENING", "display_name": "Opening"}),
        ("trade-status-types", {"name": "OPEN", "display_name": "Open"}),
        ("trade-status-types", {"name": "CLOSING", "display_name": "Closing"}),
        ("trade-status-types", {"name": "CLOSED", "display_name": "Closed"}),
        ("trade-status-types", {"name": "CANCELLED", "display_name": "Cancelled"}),
        ("trade-status-types", {"name": "ERROR", "display_name": "Error"}),
        ("order-types", {"name": "MARKET", "display_name": "Market"}),
        ("order-status-types", {"name": "SUBMITTED", "display_name": "Submitted"}),
    ]

    result = {}
    for endpoint, data in type_configs:
        resp = client.post(f"/api/types/{endpoint}", json=data)
        assert resp.status_code == 200, f"Failed to create {endpoint}: {resp.text}"
        body = resp.json()
        key = f"{endpoint}_{data['name']}"
        result[key] = body["id"]

    return result


@pytest.fixture
def seed_base_data(client, seed_types) -> dict:
    """POST assets, provider, and instruments via API.

    Returns dict of entity IDs.
    """
    # Create assets
    assets = {}
    for name, display in [("BTC", "Bitcoin"), ("ETH", "Ethereum"), ("USD", "US Dollar")]:
        resp = client.post(
            "/api/assets",
            json={
                "asset_type_id": seed_types["asset-types_CRYPTO"],
                "name": name,
                "display_name": display,
            },
        )
        assert resp.status_code == 200, f"Failed to create asset {name}: {resp.text}"
        assets[name] = resp.json()["id"]

    # Create provider
    resp = client.post(
        "/api/providers",
        json={
            "provider_type_id": seed_types["provider-types_EXCHANGE"],
            "name": "KRAKEN",
            "display_name": "Kraken",
        },
    )
    assert resp.status_code == 200, f"Failed to create provider: {resp.text}"
    provider_id = resp.json()["id"]

    # Create instruments
    instruments = {}
    for name, display, from_asset, to_asset in [
        ("KRAKEN_BTC_USD", "BTC/USD", "BTC", "USD"),
        ("KRAKEN_ETH_USD", "ETH/USD", "ETH", "USD"),
    ]:
        resp = client.post(
            "/api/instruments",
            json={
                "instrument_type_id": seed_types["instrument-types_SPOT_PAIR"],
                "provider_id": provider_id,
                "from_asset_id": assets[from_asset],
                "to_asset_id": assets[to_asset],
                "name": name,
                "display_name": display,
            },
        )
        assert resp.status_code == 200, f"Failed to create instrument {name}: {resp.text}"
        instruments[name] = resp.json()["id"]

    return {
        "types": seed_types,
        "assets": assets,
        "provider_id": provider_id,
        "instruments": instruments,
    }
