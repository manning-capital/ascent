"""Exchange runner — listens for order requests via Redis and dispatches them."""

from __future__ import annotations

import logging
import signal
import threading
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ascent.engine.cache import EngineCache

if TYPE_CHECKING:
    from ascent.exchanges.base import BaseExchange

logger = logging.getLogger(__name__)


def run_exchange(
    exchange_id: uuid.UUID,
    *,
    database_url: str = "postgresql://localhost:5432/ascent",
    redis_url: str = "redis://localhost:6379/0",
    shutdown_event: threading.Event | None = None,
    exchange_cls: type[BaseExchange] | None = None,
) -> None:
    """Run an exchange as a long-running order-dispatch service.

    Subscribes to a Redis channel ``ascent.exchange.{exchange_id}`` and
    dispatches incoming order requests to the exchange implementation.

    Args:
        exchange_id: The database ID of the exchange.
        database_url: PostgreSQL connection string.
        redis_url: Redis connection URL.
        exchange_cls: The exchange class (avoids import-by-ref).
    """
    from ascent.database.models.exchanges import Exchange as ExchangeModel

    engine = create_engine(database_url)
    cache = EngineCache(redis_url)

    # Load exchange record
    with Session(engine) as db:
        record = db.get(ExchangeModel, exchange_id)
        if record is None:
            raise ValueError(f"Exchange {exchange_id} not found in database")
        config = record.config or {}
        exchange_name = record.name

    # Instantiate
    if exchange_cls is None:
        raise ValueError(
            f"Exchange {exchange_name}: no exchange class provided and "
            "import-by-ref is not supported for exchanges."
        )
    exchange_instance = exchange_cls(config)

    # Subscribe to order channel
    channel = f"ascent.exchange.{exchange_id}"
    pubsub = cache.subscribe([channel])

    logger.info(
        "Exchange %s (%s) listening on %s",
        exchange_name,
        exchange_id,
        channel,
    )

    shutdown = shutdown_event or threading.Event()

    if shutdown_event is None:

        def _signal_handler(signum, _frame):
            logger.info("Received signal %s, shutting down exchange %s", signum, exchange_name)
            shutdown.set()

        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)

    while not shutdown.is_set():
        event = cache.poll(pubsub, timeout=1.0)
        if event is None:
            continue

        action = event.get("action")
        try:
            if action == "submit_order":
                from ascent.exchanges.base import OrderRequest

                request = OrderRequest(**event["order"])
                response = exchange_instance.submit_order(request)
                logger.info(
                    "Order submitted: %s %s %s/%s qty=%s → %s",
                    response.exchange_order_id,
                    request.side,
                    request.from_asset_symbol,
                    request.to_asset_symbol,
                    request.quantity,
                    response.status,
                )
                # Publish response back with correlation IDs
                cache.publish(
                    f"{channel}.responses",
                    {
                        "action": "order_response",
                        "exchange_id": str(exchange_id),
                        "order_id": event.get("order_id"),
                        "trade_id": event.get("trade_id"),
                        "trade_leg_id": event.get("trade_leg_id"),
                        "response": response.model_dump(),
                    },
                )

            elif action == "cancel_order":
                response = exchange_instance.cancel_order(event["exchange_order_id"])
                logger.info("Order cancelled: %s → %s", event["exchange_order_id"], response.status)

            elif action == "get_balances":
                balances = exchange_instance.get_balances()
                logger.info("Balances: %d assets", len(balances))

            else:
                logger.warning("Unknown action '%s' on exchange %s", action, exchange_name)

        except Exception:
            logger.exception("Error processing %s on exchange %s", action, exchange_name)

    pubsub.close()
    logger.info("Exchange %s shut down cleanly", exchange_name)
