"""PaperExchange — ledger correctness and SQLite persistence."""

from __future__ import annotations

import os
import tempfile
import uuid
from decimal import Decimal

import pytest

from ascent.exchanges.base import OrderRequest
from ascent.exchanges.paper import PaperExchange


def _make_request(*, side: str, quantity: float, price: float) -> OrderRequest:
    return OrderRequest(
        order_type="MARKET",
        side=side,
        instrument_id=uuid.uuid4(),
        quantity=quantity,
        price=price,
        client_order_id=str(uuid.uuid4()),
        from_asset_symbol="BTC",
        to_asset_symbol="USD",
    )


@pytest.fixture
def memory_exchange() -> PaperExchange:
    """In-memory paper exchange, isolated per test."""
    return PaperExchange(config={"db_path": ":memory:"})


def test_buy_credits_base_and_debits_quote(memory_exchange: PaperExchange) -> None:
    response = memory_exchange.submit_order(_make_request(side="BUY", quantity=0.5, price=50000.0))

    assert response.status == "FILLED"
    assert response.filled_quantity == 0.5
    assert response.average_fill_price == 50000.0

    balances = {b.asset_symbol: b.total for b in memory_exchange.get_balances()}
    assert balances["BTC"] == 0.5
    assert balances["USD"] == -25000.0


def test_sell_debits_base_and_credits_quote(memory_exchange: PaperExchange) -> None:
    memory_exchange.submit_order(_make_request(side="BUY", quantity=1.0, price=40000.0))
    memory_exchange.submit_order(_make_request(side="SELL", quantity=0.4, price=42000.0))

    balances = {b.asset_symbol: b.total for b in memory_exchange.get_balances()}
    assert balances["BTC"] == pytest.approx(0.6)
    assert balances["USD"] == pytest.approx(-40000.0 + 16800.0)


def test_short_position_stores_negative_base_balance(memory_exchange: PaperExchange) -> None:
    """Selling without owning any base creates a short position."""
    response = memory_exchange.submit_order(
        _make_request(side="SELL", quantity=0.25, price=60000.0)
    )

    assert response.status == "FILLED"
    balances = {b.asset_symbol: b.total for b in memory_exchange.get_balances()}
    assert balances["BTC"] == -0.25
    assert balances["USD"] == 15000.0


def test_market_order_without_price_is_rejected(memory_exchange: PaperExchange) -> None:
    bad = OrderRequest(
        order_type="MARKET",
        side="BUY",
        instrument_id=uuid.uuid4(),
        quantity=1.0,
        price=None,
        from_asset_symbol="BTC",
        to_asset_symbol="USD",
    )
    response = memory_exchange.submit_order(bad)
    assert response.status == "REJECTED"
    assert response.error_message and "price" in response.error_message.lower()


def test_missing_asset_symbols_rejects_order(memory_exchange: PaperExchange) -> None:
    bad = OrderRequest(
        order_type="MARKET",
        side="BUY",
        instrument_id=uuid.uuid4(),
        quantity=1.0,
        price=100.0,
    )
    response = memory_exchange.submit_order(bad)
    assert response.status == "REJECTED"
    assert response.error_message and "asset_symbol" in response.error_message


def test_get_order_status_returns_not_found_for_unknown_id(memory_exchange: PaperExchange) -> None:
    status = memory_exchange.get_order_status("does-not-exist")
    assert status.status == "NOT_FOUND"


def test_cancel_filled_order_is_rejected(memory_exchange: PaperExchange) -> None:
    response = memory_exchange.submit_order(_make_request(side="BUY", quantity=0.1, price=1000.0))

    cancel = memory_exchange.cancel_order(response.exchange_order_id)
    assert cancel.status == "REJECTED"
    assert cancel.error_message == "Cannot cancel a filled order"


def test_get_order_by_client_id_round_trip(memory_exchange: PaperExchange) -> None:
    request = _make_request(side="BUY", quantity=0.1, price=1000.0)
    response = memory_exchange.submit_order(request)

    found = memory_exchange.get_order_by_client_id(request.client_order_id)
    assert found is not None
    assert found.exchange_order_id == response.exchange_order_id
    assert found.status == "FILLED"


def test_balances_persist_across_instances(tmp_path) -> None:
    """A second PaperExchange against the same SQLite file inherits the first's
    state — exactly the property the reconciliation sweep relies on."""
    db_path = str(tmp_path / "paper.sqlite")
    first = PaperExchange(config={"db_path": db_path})
    first.submit_order(_make_request(side="BUY", quantity=0.5, price=50000.0))

    second = PaperExchange(config={"db_path": db_path})
    balances = {b.asset_symbol: b.total for b in second.get_balances()}
    assert balances["BTC"] == 0.5
    assert balances["USD"] == -25000.0


def test_seed_balances_is_one_time(tmp_path) -> None:
    """``config["balances"]`` only seeds an empty store. A subsequent restart
    with different seed config must NOT overwrite live balances."""
    db_path = str(tmp_path / "paper.sqlite")
    first = PaperExchange(
        config={
            "db_path": db_path,
            "balances": [{"asset_symbol": "USD", "total": "100000"}],
        }
    )
    first.submit_order(_make_request(side="BUY", quantity=0.1, price=1000.0))
    snapshot = {b.asset_symbol: Decimal(str(b.total)) for b in first.get_balances()}

    second = PaperExchange(
        config={
            "db_path": db_path,
            "balances": [{"asset_symbol": "USD", "total": "999999"}],
        }
    )
    after = {b.asset_symbol: Decimal(str(b.total)) for b in second.get_balances()}
    assert after == snapshot
    assert after["USD"] != Decimal("999999")


def test_default_db_path_uses_home_directory(monkeypatch) -> None:
    """When no ``db_path`` is configured, fall back to ``~/.ascent/`` so dev
    instances persist across restarts without per-deployment plumbing."""
    with tempfile.TemporaryDirectory() as fake_home:
        monkeypatch.setattr(os.path, "expanduser", lambda p: fake_home if p == "~/.ascent" else p)
        ex = PaperExchange()
        assert ex._store.path.startswith(fake_home)
        assert os.path.exists(ex._store.path)
