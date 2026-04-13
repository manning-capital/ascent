"""Abstract base class for all Ascent data feeds.

Every feed deployed to Ascent must subclass ``Feed`` and define an inner
``Parameters`` class (a Pydantic BaseModel) that describes the knobs the
feed exposes.  Ascent uses ``Parameters.model_json_schema()`` to generate
a JSON Schema that the UI renders as a typed form.

Subclasses override either ``fetch()`` (for scheduled/triggered feeds) or
``stream()`` (for streaming feeds).  The engine detects the mode from the
class definition and runs the appropriate loop.

Example
-------
Scheduled (polling) feed::

    from pydantic import BaseModel, Field
    from pandera.typing import DataFrame
    from ascent.feeds import Feed, Schedule
    from ascent.feeds.output import InstrumentAttributes

    class MarketData(Feed):
        class Parameters(BaseModel):
            provider_name: str = "kraken"
            lookback_minutes: int = Field(5, ge=1, le=1440)

        schedule = Schedule(interval=60, offset=-1.0, start_date=datetime(2024, 1, 1))
        output = InstrumentAttributes
        display_name = "Market Data"

        def fetch(self) -> DataFrame[InstrumentAttributes]:
            ...

Streaming feed::

    class LiveTrades(Feed):
        class Parameters(BaseModel):
            pairs: list[str] = ["BTC/USD"]

        schedule = Schedule(interval=60, start_date=datetime(2024, 1, 1))
        output = InstrumentAttributes

        def stream(self) -> Iterator[DataFrame[InstrumentAttributes]]:
            ws = websocket.create_connection("wss://...")
            while True:
                yield parse(ws.recv())

        def aggregate(self, raw: DataFrame) -> DataFrame:
            return raw.groupby("instrument_id").agg(...)

Triggered feed::

    class OUParams(Feed):
        depends_on = [MarketData]
        output = InstrumentAttributes

        def fetch(self) -> DataFrame[InstrumentAttributes]:
            prices = self.get_feed(MarketData)
            ...
"""

from __future__ import annotations

import logging
from abc import ABC
from collections.abc import Iterator
from typing import TYPE_CHECKING, ClassVar

import pandas as pd
from pydantic import BaseModel

from ascent.feeds.output import FeedOutput
from ascent.feeds.schedule import Schedule

if TYPE_CHECKING:
    from pandera.typing import DataFrame

    from ascent.engine.context import PartitionInfo


class Feed(ABC):
    """Base class that every Ascent data feed must inherit from.

    Subclasses override either ``fetch()`` (for scheduled/triggered feeds)
    or ``stream()`` (for streaming feeds).  The engine detects the mode:

    - ``stream()`` overridden → streaming mode (buffer + flush on tick)
    - ``schedule`` set and ``fetch()`` overridden → polling mode
    - ``depends_on`` set → triggered mode (parent events → ``fetch()``)
    """

    # ------------------------------------------------------------------
    # User overrides (class-level configuration)
    # ------------------------------------------------------------------

    class Parameters(BaseModel):
        """Override this in your feed to define typed parameters.

        The default is an empty model (no parameters).  Subclasses replace
        this entirely::

            class MyFeed(Feed):
                class Parameters(BaseModel):
                    window: int = 60
        """

    #: Which EAV output table this feed writes to.  Must be a
    #: :class:`~ascent.feeds.output.FeedOutput` subclass.
    output: ClassVar[type[FeedOutput]]

    #: When to fire (interval + offset + anchor).  Required for polling
    #: and streaming feeds.  Not used for triggered feeds.
    schedule: ClassVar[Schedule | None] = None

    #: How often to persist to TimescaleDB.  Defaults to ``schedule``
    #: if not set.  Allows fast Redis emit with slower DB batching.
    persist_schedule: ClassVar[Schedule | None] = None

    #: Parent feeds that trigger this feed (AND logic).
    #: Must not be combined with ``schedule``.
    depends_on: ClassVar[list[type[Feed]] | None] = None

    #: Human-readable name shown in the UI.  Falls back to class name.
    display_name: ClassVar[str | None] = None

    #: Long description shown in the UI.
    description: ClassVar[str | None] = None

    #: Provider name or UUID.  Resolved to a UUID at deploy time.
    provider: ClassVar[str | None] = None

    #: Instrument type name or UUID.  Mutually exclusive with ``composite_type``.
    instrument_type: ClassVar[str | None] = None

    #: Composite type name or UUID.  Mutually exclusive with ``instrument_type``.
    composite_type: ClassVar[str | None] = None

    #: Seconds to wait before reconnecting a streaming feed after disconnect.
    reconnect_delay: ClassVar[float] = 5.0

    # ------------------------------------------------------------------
    # Instance state (set by engine at runtime)
    # ------------------------------------------------------------------

    #: Populated by ``__init__`` with a validated Parameters instance.
    parameters: Parameters

    def __init__(self, parameters: Parameters | dict | None = None) -> None:
        if parameters is None:
            parameters = {}
        if isinstance(parameters, dict):
            parameters = self.__class__.Parameters.model_validate(parameters)
        self.parameters = parameters

    # ------------------------------------------------------------------
    # Core methods — override ONE of these
    # ------------------------------------------------------------------

    def fetch(self) -> DataFrame:
        """Override for scheduled or triggered feeds.

        Called on each timer tick (scheduled) or when all parent feeds
        have fresh data (triggered).  Must return a DataFrame matching
        the ``output`` schema.
        """
        raise NotImplementedError(f"{type(self).__name__} must override fetch() or stream()")

    def stream(self) -> Iterator[pd.DataFrame]:
        """Override for streaming feeds (WebSocket, SSE, etc.).

        Must be a generator that yields DataFrames as data arrives.
        Yields are BUFFERED by the engine — not published directly.
        On each partition tick (driven by ``schedule``), the buffer is
        drained, concatenated, passed through ``aggregate()``, and
        published as a single DataFrame.

        The engine wraps this in a reconnect loop: if the generator
        exits or raises, ``on_disconnect()`` is called.  If it returns
        ``True``, the engine waits ``reconnect_delay`` seconds and
        calls ``stream()`` again.
        """
        raise NotImplementedError(f"{type(self).__name__} must override fetch() or stream()")

    # ------------------------------------------------------------------
    # Optional hooks
    # ------------------------------------------------------------------

    def aggregate(self, raw: pd.DataFrame) -> pd.DataFrame:
        """Reduce buffered stream messages before emit.

        Only called for streaming feeds.  Default: return raw unchanged.
        Override to e.g. convert raw trades → OHLCV candles::

            def aggregate(self, raw):
                return raw.groupby("instrument_id").agg(
                    open=("price", "first"),
                    close=("price", "last"),
                    volume=("quantity", "sum"),
                ).reset_index()
        """
        return raw

    def on_start(self) -> None:  # noqa: B027
        """Called once before the first tick or stream connection."""

    def on_error(self, error: Exception) -> None:  # noqa: B027
        """Called when ``fetch()`` or ``stream()`` raises an exception."""

    def on_shutdown(self) -> None:  # noqa: B027
        """Called on graceful shutdown (SIGINT/SIGTERM)."""

    def on_disconnect(self) -> bool:
        """Called when a streaming feed's connection drops.

        Return ``True`` to reconnect (after ``reconnect_delay``),
        ``False`` to stop.  Default: ``True`` (always reconnect).
        """
        return True

    def persist(self, data: pd.DataFrame, db) -> None:  # noqa: B027
        """Custom persistence logic run after auto-persist.

        Override to add archival, aggregation, notifications, etc.
        The ``db`` argument is a SQLAlchemy ``Session``.
        """

    # ------------------------------------------------------------------
    # Runtime accessors (thin wrappers around contextvars)
    # ------------------------------------------------------------------

    def get_logger(self) -> logging.Logger:
        """Get the current run-scoped logger."""
        from ascent.engine.context import _current_logger

        try:
            return _current_logger.get()
        except LookupError:
            return logging.getLogger(f"ascent.feeds.{type(self).__name__}")

    def get_partition(self) -> PartitionInfo:
        """Get the current partition window."""
        from ascent.engine.context import _current_partition

        try:
            return _current_partition.get()
        except LookupError:
            raise RuntimeError("get_partition() called outside of a feed run context.") from None

    def get_feed(self, feed_cls: type[Feed]) -> pd.DataFrame:
        """Get a parent feed's latest data inside a triggered feed.

        Args:
            feed_cls: The parent Feed class to retrieve data for.

        The engine populates the feeds context as a ``dict[str, DataFrame]``
        keyed by feed ref string (``"module:ClassName"``).
        """
        from ascent.engine.context import _current_feeds

        try:
            feeds = _current_feeds.get()
        except LookupError:
            raise RuntimeError("get_feed() called outside of a triggered feed context.") from None

        ref = feed_cls.ref()
        if ref not in feeds:
            raise KeyError(
                f"Feed {feed_cls.__name__!r} (ref={ref!r}) not found in current feeds context. "
                f"Make sure it is listed in depends_on."
            )
        return feeds[ref]

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------

    @classmethod
    def parameter_schema(cls) -> dict:
        """Return the JSON Schema for this feed's Parameters model."""
        return cls.Parameters.model_json_schema()

    @classmethod
    def data_schema(cls) -> dict:
        """Return the Pandera schema for this feed's output as a dict."""
        import json

        return json.loads(cls.output.to_schema().to_json())

    @classmethod
    def output_table(cls) -> str:
        """Return the DB table name this feed's output maps to."""
        return cls.output.Config.name

    @classmethod
    def ref(cls) -> str:
        """Canonical reference for DB lookup.  Uses the name."""
        return cls.get_name()

    @classmethod
    def get_name(cls) -> str:
        """Return the unique name (``UPPER_SNAKE_CASE``).

        Derives from the class name by inserting underscores before
        uppercase letters and uppercasing
        (e.g. ``TimingFeed`` -> ``TIMING_FEED``).
        """
        import re

        return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", cls.__name__).upper()

    @classmethod
    def get_display_name(cls) -> str:
        """Return the display name.

        If ``display_name`` is not set, derives it from the class name
        by inserting spaces before each uppercase letter
        (e.g. ``TimingFeed`` -> ``Timing Feed``).
        """
        if cls.display_name:
            return cls.display_name
        import re

        return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", cls.__name__)

    # ------------------------------------------------------------------
    # Mode detection
    # ------------------------------------------------------------------

    @classmethod
    def is_streaming(cls) -> bool:
        """True if this feed overrides ``stream()`` (vs ``fetch()``)."""
        return cls.stream is not Feed.stream

    # ------------------------------------------------------------------
    # Runner
    # ------------------------------------------------------------------

    @classmethod
    def run(
        cls,
        *,
        database_url: str | None = None,
        redis_url: str | None = None,
        include_writer: bool = False,
        log_level: str = "INFO",
    ) -> None:
        """Auto-deploy and run this feed as a long-running process.

        Registers (or updates) the feed in the database, then starts
        the appropriate engine loop (scheduled, streaming, or triggered).
        Blocks until SIGINT/SIGTERM.

        The ``provider``, ``instrument_type``, and ``composite_type``
        class attributes are resolved at deploy time — they accept either
        a UUID or a name string that is looked up in the database.
        """
        from ascent.engine.runner import Runner

        runner = Runner(
            database_url=database_url,
            redis_url=redis_url,
            include_writer=include_writer,
            log_level=log_level,
        )
        runner.add(cls)
        runner.run()
