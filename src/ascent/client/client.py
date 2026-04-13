"""Ascent API client — Python interface for the Ascent REST API.

Provides programmatic access to the Ascent platform from external processes
such as Jupyter notebooks, scripts, or external orchestration tools.

Usage::

    from ascent.client import AscentClient

    client = AscentClient("http://localhost:8000")

    # List feeds
    feeds = client.get_feeds()

    # Publish data to an external feed
    client.publish_feed(feed_id=feed_uuid, data=df)
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any

import httpx
import pandas as pd


def _str(v: Any) -> str:
    """Convert UUIDs and datetimes to strings for JSON payloads."""
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, (datetime.datetime, datetime.date, datetime.time)):
        return v.isoformat()
    return v


def _body(**kwargs: Any) -> dict[str, Any]:
    """Build a JSON body, dropping None values and stringifying UUIDs/datetimes."""
    out: dict[str, Any] = {}
    for k, v in kwargs.items():
        if v is None:
            continue
        if isinstance(v, uuid.UUID):
            out[k] = str(v)
        elif isinstance(v, (datetime.datetime, datetime.date, datetime.time)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


class AscentClient:
    """HTTP client for the Ascent REST API.

    Args:
        base_url: The base URL of the Ascent server (e.g., ``http://localhost:8000``).
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        *,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=f"{self._base_url}/api",
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )

    def __enter__(self) -> AscentClient:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        self.close()
        return False

    def close(self) -> None:
        """Close the underlying HTTP connection."""
        self._client.close()

    @staticmethod
    def _raise(resp: httpx.Response) -> None:
        """Raise with the response body included in the message."""
        if resp.is_success:
            return
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise httpx.HTTPStatusError(
            f"{resp.status_code}: {detail}",
            request=resp.request,
            response=resp,
        )

    # ------------------------------------------------------------------
    # Types
    # ------------------------------------------------------------------

    def get_asset_types(self) -> list[dict[str, Any]]:
        resp = self._client.get("/types/asset-types")
        self._raise(resp)
        return resp.json()

    def create_asset_type(self, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post("/types/asset-types", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def get_provider_types(self) -> list[dict[str, Any]]:
        resp = self._client.get("/types/provider-types")
        self._raise(resp)
        return resp.json()

    def create_provider_type(self, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post("/types/provider-types", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def get_trade_status_types(self) -> list[dict[str, Any]]:
        resp = self._client.get("/types/trade-statuses")
        self._raise(resp)
        return resp.json()

    def create_trade_status_type(self, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post("/types/trade-statuses", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def get_order_types(self) -> list[dict[str, Any]]:
        resp = self._client.get("/types/order-types")
        self._raise(resp)
        return resp.json()

    def create_order_type(self, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post("/types/order-types", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def get_order_status_types(self) -> list[dict[str, Any]]:
        resp = self._client.get("/types/order-statuses")
        self._raise(resp)
        return resp.json()

    def create_order_status_type(self, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post("/types/order-statuses", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def get_metadata_types(self) -> list[dict[str, Any]]:
        resp = self._client.get("/metadata", params={"page_size": 10000})
        self._raise(resp)
        return resp.json()["items"]

    def create_metadata_type(self, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post("/metadata", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def get_instrument_types(self) -> list[dict[str, Any]]:
        resp = self._client.get("/types/instrument-types")
        self._raise(resp)
        return resp.json()

    def create_instrument_type(self, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post("/types/instrument-types", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def get_composite_types(self) -> list[dict[str, Any]]:
        resp = self._client.get("/types/composite-types")
        self._raise(resp)
        return resp.json()

    def create_composite_type(self, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post("/types/composite-types", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    # Type-metadata links

    def add_asset_type_metadata(self, asset_type_id: uuid.UUID, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post(
            f"/types/asset-types/{asset_type_id}/metadata", json=_body(**kwargs)
        )
        self._raise(resp)
        return resp.json()

    def add_provider_type_metadata(
        self, provider_type_id: uuid.UUID, **kwargs: Any
    ) -> dict[str, Any]:
        resp = self._client.post(
            f"/types/provider-types/{provider_type_id}/metadata", json=_body(**kwargs)
        )
        self._raise(resp)
        return resp.json()

    def add_instrument_type_metadata(
        self, instrument_type_id: uuid.UUID, **kwargs: Any
    ) -> dict[str, Any]:
        resp = self._client.post(
            f"/types/instrument-types/{instrument_type_id}/metadata", json=_body(**kwargs)
        )
        self._raise(resp)
        return resp.json()

    def add_composite_type_metadata(
        self, composite_type_id: uuid.UUID, **kwargs: Any
    ) -> dict[str, Any]:
        resp = self._client.post(
            f"/types/composite-types/{composite_type_id}/metadata", json=_body(**kwargs)
        )
        self._raise(resp)
        return resp.json()

    def add_asset_type_provider_asset_metadata(
        self, asset_type_id: uuid.UUID, **kwargs: Any
    ) -> dict[str, Any]:
        resp = self._client.post(
            f"/types/asset-types/{asset_type_id}/provider-asset-metadata",
            json=_body(**kwargs),
        )
        self._raise(resp)
        return resp.json()

    # ------------------------------------------------------------------
    # Assets
    # ------------------------------------------------------------------

    def get_assets(self) -> list[dict[str, Any]]:
        resp = self._client.get("/assets", params={"page_size": 10000})
        self._raise(resp)
        return resp.json()["items"]

    def create_asset(self, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post("/assets", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def create_asset_metadata(self, asset_id: uuid.UUID, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post(f"/assets/{asset_id}/metadata", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def batch_create_asset_metadata(
        self,
        asset_id: uuid.UUID,
        *,
        timestamp: datetime.datetime,
        entries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        payload = {
            "timestamp": timestamp.isoformat(),
            "entries": [{k: _str(v) for k, v in e.items()} for e in entries],
        }
        resp = self._client.post(f"/assets/{asset_id}/metadata/batch", json=payload)
        self._raise(resp)
        return resp.json()

    # ------------------------------------------------------------------
    # Providers
    # ------------------------------------------------------------------

    def get_providers(self) -> list[dict[str, Any]]:
        resp = self._client.get("/providers", params={"page_size": 10000})
        self._raise(resp)
        return resp.json()["items"]

    def create_provider(self, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post("/providers", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def create_provider_metadata(self, provider_id: uuid.UUID, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post(f"/providers/{provider_id}/metadata", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def batch_create_provider_metadata(
        self,
        provider_id: uuid.UUID,
        *,
        timestamp: datetime.datetime,
        entries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        payload = {
            "timestamp": timestamp.isoformat(),
            "entries": [{k: _str(v) for k, v in e.items()} for e in entries],
        }
        resp = self._client.post(f"/providers/{provider_id}/metadata/batch", json=payload)
        self._raise(resp)
        return resp.json()

    # ------------------------------------------------------------------
    # Provider-Assets
    # ------------------------------------------------------------------

    def create_provider_asset_metadata(
        self, provider_id: uuid.UUID, asset_id: uuid.UUID, **kwargs: Any
    ) -> dict[str, Any]:
        resp = self._client.post(
            f"/provider-assets/{provider_id}/{asset_id}/metadata",
            json=_body(**kwargs),
        )
        self._raise(resp)
        return resp.json()

    def batch_create_provider_asset_metadata(
        self,
        provider_id: uuid.UUID,
        asset_id: uuid.UUID,
        *,
        timestamp: datetime.datetime,
        entries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        payload = {
            "timestamp": timestamp.isoformat(),
            "entries": [{k: _str(v) for k, v in e.items()} for e in entries],
        }
        resp = self._client.post(
            f"/provider-assets/{provider_id}/{asset_id}/metadata/batch",
            json=payload,
        )
        self._raise(resp)
        return resp.json()

    # ------------------------------------------------------------------
    # Exchanges
    # ------------------------------------------------------------------

    def get_exchanges(self) -> list[dict[str, Any]]:
        resp = self._client.get("/exchanges")
        self._raise(resp)
        return resp.json()

    def create_exchange(self, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post("/exchanges", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    # ------------------------------------------------------------------
    # Attributes
    # ------------------------------------------------------------------

    def get_attributes(self) -> list[dict[str, Any]]:
        resp = self._client.get("/attributes", params={"page_size": 10000})
        self._raise(resp)
        return resp.json()["items"]

    def create_attribute(self, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post("/attributes", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    # ------------------------------------------------------------------
    # Portfolios
    # ------------------------------------------------------------------

    def get_portfolios(self) -> list[dict[str, Any]]:
        resp = self._client.get("/portfolios")
        self._raise(resp)
        return resp.json()

    def get_portfolio(self, portfolio_id: uuid.UUID) -> dict[str, Any]:
        resp = self._client.get(f"/portfolios/{portfolio_id}")
        self._raise(resp)
        return resp.json()

    def create_portfolio(self, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post("/portfolios", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    # ------------------------------------------------------------------
    # Instruments
    # ------------------------------------------------------------------

    def get_instruments(self) -> list[dict[str, Any]]:
        resp = self._client.get("/instruments", params={"page_size": 10000})
        self._raise(resp)
        return resp.json()["items"]

    def create_instrument(self, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post("/instruments", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def get_instrument_metadata(self, instrument_id: uuid.UUID) -> list[dict[str, Any]]:
        resp = self._client.get(f"/instruments/{instrument_id}/metadata")
        self._raise(resp)
        return resp.json()

    def batch_create_instrument_metadata(
        self, instrument_id: uuid.UUID, timestamp: str, entries: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        payload = {
            "timestamp": timestamp,
            "entries": [{k: _str(v) for k, v in e.items()} for e in entries],
        }
        resp = self._client.post(f"/instruments/{instrument_id}/metadata/batch", json=payload)
        self._raise(resp)
        return resp.json()

    # ------------------------------------------------------------------
    # Composites
    # ------------------------------------------------------------------

    def get_composites(self) -> list[dict[str, Any]]:
        resp = self._client.get("/composites", params={"page_size": 10000})
        self._raise(resp)
        return resp.json()["items"]

    def create_composite(self, **kwargs: Any) -> dict[str, Any]:
        body = _body(**kwargs)
        if "members" in body:
            body["members"] = [{k: _str(v) for k, v in m.items()} for m in body["members"]]
        resp = self._client.post("/composites", json=body)
        self._raise(resp)
        return resp.json()

    def add_composite_member(self, composite_id: uuid.UUID, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post(f"/composites/{composite_id}/members", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def batch_create_composite_metadata(
        self, composite_id: uuid.UUID, timestamp: str, entries: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        payload = {
            "timestamp": timestamp,
            "entries": [{k: _str(v) for k, v in e.items()} for e in entries],
        }
        resp = self._client.post(f"/composites/{composite_id}/metadata/batch", json=payload)
        self._raise(resp)
        return resp.json()

    # ------------------------------------------------------------------
    # Feeds
    # ------------------------------------------------------------------

    def get_feeds(self) -> list[dict[str, Any]]:
        resp = self._client.get("/feeds")
        self._raise(resp)
        return resp.json()

    def get_feed(self, feed_id: uuid.UUID) -> dict[str, Any]:
        resp = self._client.get(f"/feeds/{feed_id}")
        self._raise(resp)
        return resp.json()

    def create_feed(self, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post("/feeds", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def create_feed_dependency(self, feed_id: uuid.UUID, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post(f"/feeds/{feed_id}/dependencies", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def get_feed_parameter_schema(self, feed_id: uuid.UUID) -> dict[str, Any]:
        resp = self._client.get(f"/feeds/{feed_id}/parameter-schema")
        self._raise(resp)
        return resp.json()

    def get_feed_runs(
        self,
        feed_id: uuid.UUID,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        resp = self._client.get(
            f"/feeds/{feed_id}/runs",
            params={"page": page, "page_size": page_size},
        )
        self._raise(resp)
        return resp.json()

    def publish_feed(
        self,
        feed_id: uuid.UUID,
        data: pd.DataFrame,
        *,
        partition_key: datetime.datetime | None = None,
    ) -> dict[str, Any]:
        """Publish data to a feed partition, triggering downstream consumers."""
        records = data.to_dict(orient="records")
        for record in records:
            for key, value in record.items():
                if isinstance(value, (datetime.datetime, datetime.date)):
                    record[key] = value.isoformat()
                elif isinstance(value, pd.Timestamp):
                    record[key] = value.isoformat()

        payload: dict[str, Any] = {"records": records}
        if partition_key is not None:
            payload["partition_key"] = partition_key.isoformat()

        resp = self._client.post(f"/feeds/{feed_id}/publish", json=payload)
        self._raise(resp)
        return resp.json()

    def get_partitions(
        self,
        feed_id: uuid.UUID,
        *,
        start: datetime.datetime | None = None,
        end: datetime.datetime | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if start is not None:
            params["start"] = start.isoformat()
        if end is not None:
            params["end"] = end.isoformat()
        if status is not None:
            params["status"] = status
        resp = self._client.get(f"/feeds/{feed_id}/partitions", params=params)
        self._raise(resp)
        return resp.json()

    def get_partition_data(
        self,
        feed_id: uuid.UUID,
        partition_id: uuid.UUID,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        resp = self._client.get(
            f"/feeds/{feed_id}/partitions/{partition_id}/data",
            params={"page": page, "page_size": page_size},
        )
        self._raise(resp)
        return resp.json()

    # ------------------------------------------------------------------
    # Strategies
    # ------------------------------------------------------------------

    def get_strategies(self) -> list[dict[str, Any]]:
        resp = self._client.get("/strategies")
        self._raise(resp)
        return resp.json()

    def get_strategy(self, strategy_id: uuid.UUID) -> dict[str, Any]:
        resp = self._client.get(f"/strategies/{strategy_id}")
        self._raise(resp)
        return resp.json()

    def create_strategy(self, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post("/strategies", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def add_strategy_feed(self, strategy_id: uuid.UUID, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post(f"/strategies/{strategy_id}/feeds", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    # ------------------------------------------------------------------
    # Trades
    # ------------------------------------------------------------------

    def get_trades(self, **params: Any) -> list[dict[str, Any]]:
        resp = self._client.get("/trades", params=params)
        self._raise(resp)
        return resp.json()

    def create_trade(self, **kwargs: Any) -> dict[str, Any]:
        body = _body(**kwargs)
        if "legs" in body:
            body["legs"] = [{k: _str(v) for k, v in leg.items()} for leg in body["legs"]]
        resp = self._client.post("/trades", json=body)
        self._raise(resp)
        return resp.json()

    def update_trade(self, trade_id: uuid.UUID, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.put(f"/trades/{trade_id}", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def add_trade_status(self, trade_id: uuid.UUID, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post(f"/trades/{trade_id}/statuses", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def add_trade_condition(self, trade_id: uuid.UUID, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post(f"/trades/{trade_id}/conditions", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def add_trade_snapshot(self, trade_id: uuid.UUID, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post(f"/trades/{trade_id}/snapshots", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def add_trade_data_series(self, trade_id: uuid.UUID, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post(f"/trades/{trade_id}/data-series", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def create_order(self, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post("/orders", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def update_order(self, order_id: uuid.UUID, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.put(f"/orders/{order_id}", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def add_order_status(self, order_id: uuid.UUID, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post(f"/orders/{order_id}/statuses", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    # ------------------------------------------------------------------
    # Admin / Seed helpers
    # ------------------------------------------------------------------

    def reset_pool(self) -> dict[str, Any]:
        resp = self._client.post("/admin/reset-pool")
        self._raise(resp)
        return resp.json()

    def reset_database(self) -> dict[str, Any]:
        resp = self._client.post("/admin/reset-database")
        self._raise(resp)
        return resp.json()

    def create_feed_partition(self, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post("/admin/feed-partitions", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def create_feed_run(self, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post("/admin/feed-runs", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def create_strategy_run(self, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post("/admin/strategy-runs", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def create_strategy_run_feed_run(self, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post("/admin/strategy-run-feed-runs", json=_body(**kwargs))
        self._raise(resp)
        return resp.json()

    def batch_create_instrument_attributes(self, entries: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {"entries": [{k: _str(v) for k, v in e.items()} for e in entries]}
        resp = self._client.post("/admin/instrument-attributes/batch", json=payload)
        self._raise(resp)
        return resp.json()

    def batch_create_composite_attributes(self, entries: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {"entries": [{k: _str(v) for k, v in e.items()} for e in entries]}
        resp = self._client.post("/admin/composite-attributes/batch", json=payload)
        self._raise(resp)
        return resp.json()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def ping(self) -> bool:
        """Check if the Ascent server is reachable."""
        try:
            resp = self._client.get("/admin/health")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    def wait_until_ready(self, timeout: float = 60.0, interval: float = 2.0) -> None:
        """Block until the server health check passes or timeout is reached."""
        import time

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.ping():
                return
            time.sleep(interval)
        raise TimeoutError(f"Server at {self._base_url} did not become ready within {timeout}s")
