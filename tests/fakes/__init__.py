"""In-memory fakes for every port in :mod:`ascent.ports`.

Used by unit tests for use cases. Fakes are deliberately simple — they only
need to behave consistently with the port Protocol; no production concerns.
"""

from tests.fakes.clock import FakeClock
from tests.fakes.event_bus import InMemoryEventBus
from tests.fakes.exchange import FakeExchange
from tests.fakes.feed_store import InMemoryFeedStore
from tests.fakes.heartbeat import InMemoryHeartbeat
from tests.fakes.repositories import (
    InMemoryFeedRunRepository,
    InMemoryOrderRepository,
    InMemoryPartitionRepository,
    InMemoryStrategyRunRepository,
    InMemoryTradeRepository,
)
from tests.fakes.run_tracker import FakeRunTracker
from tests.fakes.state_store import InMemoryStateStore

__all__ = [
    "FakeClock",
    "FakeExchange",
    "FakeRunTracker",
    "InMemoryEventBus",
    "InMemoryFeedRunRepository",
    "InMemoryFeedStore",
    "InMemoryHeartbeat",
    "InMemoryOrderRepository",
    "InMemoryPartitionRepository",
    "InMemoryStateStore",
    "InMemoryStrategyRunRepository",
    "InMemoryTradeRepository",
]
