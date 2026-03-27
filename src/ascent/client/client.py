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

    # ------------------------------------------------------------------
    # Feeds
    # ------------------------------------------------------------------

    def get_feeds(self) -> list[dict[str, Any]]:
        """List all registered feeds."""
        resp = self._client.get("/feeds")
        resp.raise_for_status()
        return resp.json()

    def get_feed(self, feed_id: uuid.UUID) -> dict[str, Any]:
        """Get details of a single feed."""
        resp = self._client.get(f"/feeds/{feed_id}")
        resp.raise_for_status()
        return resp.json()

    def get_feed_parameter_schema(self, feed_id: uuid.UUID) -> dict[str, Any]:
        """Get the JSON Schema for a feed's parameters."""
        resp = self._client.get(f"/feeds/{feed_id}/parameter-schema")
        resp.raise_for_status()
        return resp.json()

    def get_feed_runs(
        self,
        feed_id: uuid.UUID,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """Get paginated run history for a feed."""
        resp = self._client.get(
            f"/feeds/{feed_id}/runs",
            params={"page": page, "page_size": page_size},
        )
        resp.raise_for_status()
        return resp.json()

    def publish_feed(
        self,
        feed_id: uuid.UUID,
        data: pd.DataFrame,
        *,
        partition_key: datetime.datetime | None = None,
    ) -> dict[str, Any]:
        """Publish data to a feed partition, triggering downstream consumers.

        The DataFrame is validated against the feed's Pandera schema on the
        server. On success the data is written to Redis and an event is
        published via Redis pub/sub, identical to what the internal engine does
        for scheduled and triggered feeds.

        Args:
            feed_id: The database ID of the feed to publish to.
            data: A pandas DataFrame conforming to the feed's output schema.
            partition_key: Which partition this data belongs to. If ``None``,
                the server computes the partition key from the current time.

        Returns:
            A dict with ``feed_run_id``, ``partition_id``, ``partition_key``,
            ``records_count``, and ``timestamp``.

        Raises:
            httpx.HTTPStatusError: If the server rejects the request (e.g.,
                schema validation failure returns 422).
        """
        records = data.to_dict(orient="records")
        # Normalize datetime objects to ISO strings for JSON serialization
        for record in records:
            for key, value in record.items():
                if isinstance(value, (datetime.datetime, datetime.date)):
                    record[key] = value.isoformat()
                elif isinstance(value, pd.Timestamp):
                    record[key] = value.isoformat()

        payload: dict[str, Any] = {"records": records}
        if partition_key is not None:
            payload["partition_key"] = partition_key.isoformat()

        resp = self._client.post(
            f"/feeds/{feed_id}/publish",
            json=payload,
        )
        resp.raise_for_status()
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
        """List partitions for a feed with optional filters.

        Args:
            feed_id: The database ID of the feed.
            start: Start of the time range to query.
            end: End of the time range to query.
            status: Filter by status (``PENDING``, ``MATERIALIZED``, ``FAILED``).
            page: Page number (1-based).
            page_size: Number of partitions per page.

        Returns:
            Paginated response with ``items``, ``total``, ``page``,
            ``page_size``, and ``total_pages``.
        """
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if start is not None:
            params["start"] = start.isoformat()
        if end is not None:
            params["end"] = end.isoformat()
        if status is not None:
            params["status"] = status
        resp = self._client.get(f"/feeds/{feed_id}/partitions", params=params)
        resp.raise_for_status()
        return resp.json()

    def get_partition_data(
        self,
        feed_id: uuid.UUID,
        partition_id: uuid.UUID,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """Fetch actual data rows for a feed partition from TimescaleDB.

        Args:
            feed_id: The database ID of the feed.
            partition_id: The database ID of the partition.
            page: Page number (1-based).
            page_size: Number of rows per page.

        Returns:
            A dict with ``items``, ``total``, ``page``, ``page_size``,
            and ``total_pages``.
        """
        resp = self._client.get(
            f"/feeds/{feed_id}/partitions/{partition_id}/data",
            params={"page": page, "page_size": page_size},
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Strategies
    # ------------------------------------------------------------------

    def get_strategies(self) -> list[dict[str, Any]]:
        """List all registered strategies."""
        resp = self._client.get("/strategies")
        resp.raise_for_status()
        return resp.json()

    def get_strategy(self, strategy_id: uuid.UUID) -> dict[str, Any]:
        """Get details of a single strategy."""
        resp = self._client.get(f"/strategies/{strategy_id}")
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Trades
    # ------------------------------------------------------------------

    def get_trades(self, **params: Any) -> list[dict[str, Any]]:
        """List trades with optional filters."""
        resp = self._client.get("/trades", params=params)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Portfolios
    # ------------------------------------------------------------------

    def get_portfolios(self) -> list[dict[str, Any]]:
        """List all portfolios."""
        resp = self._client.get("/portfolios")
        resp.raise_for_status()
        return resp.json()

    def get_portfolio(self, portfolio_id: uuid.UUID) -> dict[str, Any]:
        """Get details of a single portfolio."""
        resp = self._client.get(f"/portfolios/{portfolio_id}")
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Assets
    # ------------------------------------------------------------------

    def get_assets(self) -> list[dict[str, Any]]:
        """List all assets."""
        resp = self._client.get("/assets")
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Types
    # ------------------------------------------------------------------

    def get_types(self) -> dict[str, Any]:
        """Get all type definitions."""
        resp = self._client.get("/types")
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def ping(self) -> bool:
        """Check if the Ascent server is reachable."""
        try:
            resp = self._client.get("/feeds")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False
