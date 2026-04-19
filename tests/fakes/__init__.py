"""In-memory fakes for every port in :mod:`ascent.ports`.

Used by unit tests for use cases. Fakes are deliberately simple — they only
need to behave consistently with the port Protocol; no production concerns.
"""

from tests.fakes.clock import FakeClock
from tests.fakes.durable_consumer import FakeDurableConsumer
from tests.fakes.durable_publisher import FakeDurablePublisher
from tests.fakes.event_bus import InMemoryEventBus
from tests.fakes.exchange import FakeExchange
from tests.fakes.feed_store import InMemoryFeedStore
from tests.fakes.heartbeat import InMemoryHeartbeat
from tests.fakes.outbox import (
    InMemoryOutboxPublisher,
    InMemoryOutboxReader,
    make_outbox_pair,
)
from tests.fakes.repositories import (
    InMemoryFeedRunRepository,
    InMemoryOrderRepository,
    InMemoryPartitionRepository,
    InMemoryStrategyRunRepository,
    InMemoryStrategyUniverseRepository,
    InMemoryTradeRepository,
)
from tests.fakes.run_tracker import FakeRunTracker
from tests.fakes.state_store import InMemoryStateStore
from tests.fakes.unit_of_work import FakeUnitOfWork, FakeUnitOfWorkFactory

__all__ = [
    "FakeClock",
    "FakeDurableConsumer",
    "FakeDurablePublisher",
    "FakeExchange",
    "FakeRunTracker",
    "FakeUnitOfWork",
    "FakeUnitOfWorkFactory",
    "InMemoryEventBus",
    "InMemoryFeedRunRepository",
    "InMemoryFeedStore",
    "InMemoryHeartbeat",
    "InMemoryOrderRepository",
    "InMemoryOutboxPublisher",
    "InMemoryOutboxReader",
    "InMemoryPartitionRepository",
    "InMemoryStateStore",
    "InMemoryStrategyRunRepository",
    "InMemoryStrategyUniverseRepository",
    "InMemoryTradeRepository",
    "make_outbox_pair",
]
