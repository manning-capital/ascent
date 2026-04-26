"""Abstract base class for all Ascent trading strategies.

Every strategy deployed to Ascent must subclass ``Strategy`` and define an
inner ``Parameters`` class (a Pydantic BaseModel) that describes the knobs
the strategy exposes.  Ascent uses ``Parameters.model_json_schema()`` to
generate a JSON Schema that the UI renders as a typed form — so users never
have to edit raw JSON.

Example
-------
::

    from pydantic import BaseModel, Field
    from ascent.strategies import Strategy
    from feeds.market import MarketData

    class PairsStrategy(Strategy):
        class Parameters(BaseModel):
            lookback: int = Field(60, description="Rolling window size in bars")
            entry_z: float = Field(2.0, description="Z-score threshold to enter")
            exit_z: float = Field(0.5, description="Z-score threshold to exit")

        feeds = [MarketData]

        def evaluate(self, ctx: Context) -> None:
            for inst_id in ctx.universe:
                price = ctx.df.loc[inst_id, ('market_data', 'close')]
                ...

    if __name__ == "__main__":
        PairsStrategy.run()
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar, Literal

import pandas as pd
from pydantic import BaseModel

if TYPE_CHECKING:
    from ascent.application.context_builder import Context
    from ascent.application.route_trade import TradeDraft, TradeRouter
    from ascent.feeds.base import Feed

Scope = Literal["instrument", "composite"]


class TradeView(BaseModel):
    """Per-strategy trade-detail chart configuration.

    Declared as a class attribute on a ``Strategy`` subclass and persisted as
    JSONB on the strategy DB row at deploy time, mirroring the
    ``parameter_schema`` flow. The trade-detail UI uses this to pick which
    context series to plot by default and whether to overlay vertical
    reference lines at the trade's entry/exit timestamps.
    """

    series: list[str] = []
    series_labels: dict[str, str] = {}
    show_trade_markers: bool = True


class Strategy(ABC):
    """Base class that every Ascent trading strategy must inherit from.

    Subclasses **must** override the inner ``Parameters`` class with a
    Pydantic model describing the strategy's configuration.  The schema
    is extracted at deploy time and stored alongside the model record so
    the UI can render a proper form.
    """

    class Parameters(BaseModel):
        """Override this in your strategy to define typed parameters.

        The default is an empty model (no parameters).  Subclasses replace
        this entirely::

            class MyStrategy(Strategy):
                class Parameters(BaseModel):
                    threshold: float = 1.5
        """

    #: Populated by __init__ with a validated Parameters instance.
    parameters: Parameters

    #: Feeds this strategy depends on.  Each entry can be a feed name
    #: (string), a UUID, or a Feed subclass.  The engine resolves names
    #: and UUIDs at deploy time and subscribes to their Redis channels.
    feeds: ClassVar[list[str | type[Feed]] | None] = None

    #: Entity scope of this strategy's evaluation context.
    #:
    #: - ``"instrument"`` — ``ctx.df`` is indexed by ``instrument_id``.
    #:   Only instrument-scoped feeds may be declared.
    #: - ``"composite"`` — ``ctx.df`` is indexed by
    #:   ``(composite_id, instrument_id)``. Both composite- and
    #:   instrument-scoped feeds are allowed; instrument rows are reindexed
    #:   onto the composite's members.
    #:
    #: Validated at launch: feed scopes must be compatible with this value.
    scope: ClassVar[Scope] = "instrument"

    #: Human-readable name shown in the UI.  Override in subclasses or
    #: leave ``None`` to use the class name.
    display_name: ClassVar[str | None] = None

    #: Optional long description shown in the UI.
    description: ClassVar[str | None] = None

    #: Portfolio name or UUID.  Resolved to a UUID at deploy time.
    portfolio: ClassVar[str | None] = None

    #: Exchanges this strategy can use for order execution.  Each entry
    #: can be an exchange name (string) or a UUID.
    exchanges: ClassVar[list[str] | None] = None

    #: Trade-detail chart configuration.  When set, the trade-detail UI
    #: uses ``series`` to pick default series to plot and overlays
    #: vertical entry/exit reference lines when ``show_trade_markers`` is
    #: true. Persisted as JSONB on the strategy DB row at deploy time.
    trade_view: ClassVar[TradeView | None] = None

    def __init__(self, parameters: Parameters | dict | None = None) -> None:
        if parameters is None:
            parameters = {}
        if isinstance(parameters, dict):
            parameters = self.__class__.Parameters.model_validate(parameters)
        self.parameters = parameters
        self._trade_router: TradeRouter | None = None

    # ------------------------------------------------------------------
    # Core — called by the execution engine on each tick
    # ------------------------------------------------------------------

    @abstractmethod
    def evaluate(self, ctx: Context) -> None:
        """Called on each execution tick with the consolidated context.

        ``ctx`` is a :class:`~ascent.application.context_builder.Context`
        dataclass with three fields:

        - ``ctx.df``: the consolidated DataFrame. Columns are a two-level
          :class:`~pandas.MultiIndex`: level 0 groups by source (``'trade'``
          for trade/order state, or a feed name like ``'market_data'``);
          level 1 holds the individual fields (``'status'``, ``'close'``,
          etc.). Index is ``instrument_id`` for instrument strategies or a
          ``(composite_id, instrument_id)`` MultiIndex for composite
          strategies.
        - ``ctx.universe``: ``frozenset[str]`` of active scope IDs the
          strategy may **open new trades** on. Stringified for ``df.index``
          parity.
        - ``ctx.open_only``: ``frozenset[str]`` of IDs that appear in
          ``df`` only because of a non-terminal trade — exit-only set,
          covers disabled scope rows and instruments whose scope row was
          removed while a position was still open.

        Trade columns (under ``('trade', ...)``):
            ``status``, ``trade_id``, ``direction``, ``entry_price``,
            ``quantity``, ``unrealized_pnl``, ``entry_at``,
            ``order_status``, ``filled_quantity``.

        Feed columns are pivoted from EAV and namespaced by feed name,
        e.g. ``('market_data', 'close')``.

        Must be implemented by subclasses.
        """

    def derive(self, ctx: Context) -> pd.DataFrame:
        """Return derived columns aligned to ``ctx.df.index``.

        This is where a strategy exposes its per-tick computed signals —
        spreads, optimal levels, z-scores, regime flags, anything the
        ``evaluate()`` decision logic reads from. The returned frame has a
        single-level string column index; the trade-context endpoint wraps
        each column under the ``('derived', ...)`` level when merging with
        ``ctx.df`` so the UI can plot them alongside feed columns.

        Must be PURE: no I/O, no order routing, no state mutation. The
        engine calls ``derive()`` inside ``evaluate()``, and the server
        calls it during trade-context reconstruction over historical feed
        data — both paths must produce the same result for the same input.

        Default returns an empty frame aligned to the context index.
        """
        return pd.DataFrame(index=ctx.df.index)

    # ------------------------------------------------------------------
    # Runtime accessors (thin wrappers around contextvars)
    # ------------------------------------------------------------------

    def get_logger(self) -> logging.Logger:
        """Get the current run-scoped logger."""
        from ascent.engine.context import _current_logger

        try:
            return _current_logger.get()
        except LookupError:
            return logging.getLogger(f"ascent.strategies.{type(self).__name__}")

    # ------------------------------------------------------------------
    # Trading
    # ------------------------------------------------------------------

    def _ensure_router(self) -> TradeRouter:
        if self._trade_router is None:
            raise RuntimeError(
                "No exchange is configured for this strategy. "
                "Declare 'exchanges = [\"EXCHANGE_NAME\"]' on your strategy class "
                "and make sure the exchange is deployed and active."
            )
        return self._trade_router

    def open_trade(
        self,
        id: uuid.UUID,
        direction: str,
        quantity: float,
        *,
        scope: Literal["instrument", "composite"] = "instrument",
        composite_instrument_ids: list[uuid.UUID] | None = None,
        price: float | None = None,
        order_type: str = "MARKET",
    ) -> TradeDraft:
        """Open a new trade on an instrument or composite.

        For ``scope='composite'``, pass ``composite_instrument_ids`` as the
        ordered list of member instrument UUIDs (leg 1 first, leg 2 second,
        ...). The router creates one leg per instrument; the first leg takes
        the submitted direction and subsequent legs alternate.

        Returns a :class:`~ascent.application.route_trade.TradeDraft` dataclass
        with ``trade_id`` (UUID), ``state`` (:class:`TradeState`), and
        ``leg_summaries`` (list of per-leg dicts). Fills arrive asynchronously
        via the fill handler; this return value reflects only what has been
        submitted — not final status or realized PnL.
        """
        from ascent.application.route_trade import CompositeSpec

        router = self._ensure_router()
        side = "BUY" if direction == "LONG" else "SELL"

        composite_spec: CompositeSpec | None = None
        if scope == "composite":
            if not composite_instrument_ids:
                raise ValueError(
                    "scope='composite' requires composite_instrument_ids "
                    "(ordered list of member instrument UUIDs)"
                )
            composite_spec = CompositeSpec(
                composite_id=id,
                ordered_instrument_ids=list(composite_instrument_ids),
            )

        return router.submit(
            side=side,
            target_id=id,
            scope=scope,
            quantity=quantity,
            price=price,
            order_type=order_type,
            composite=composite_spec,
        )

    def close_trade(
        self,
        trade_id: str | uuid.UUID,
        *,
        price: float | None = None,
        close_reason: str = "MODEL_SIGNAL",
    ) -> TradeDraft:
        """Close an open trade by submitting exit orders for all legs.

        Returns a :class:`~ascent.application.route_trade.TradeDraft` with
        ``state == TradeState.CLOSING``. The final realized PnL is written to
        the database when exit fills arrive; poll :meth:`get_open_trades` or
        query the trade record if needed.
        """
        router = self._ensure_router()
        return router.close(
            trade_id=uuid.UUID(str(trade_id)),
            price=price,
            close_reason=close_reason,
        )

    def get_open_trades(self) -> list[dict]:
        """Return all OPEN trades for this strategy.

        Returns:
            List of dicts with ``trade_id``, ``entry_at``, ``is_paper``.
        """
        router = self._ensure_router()
        return router.get_open_trades()

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------

    @classmethod
    def parameter_schema(cls) -> dict:
        """Return the JSON Schema for this strategy's Parameters model.

        This is what gets stored in the database and served to the UI.
        """
        return cls.Parameters.model_json_schema()

    @classmethod
    def trade_view_config(cls) -> dict | None:
        """Return the trade-view config as a plain dict, or ``None``.

        Captured at deploy time and persisted on the strategy DB row so the
        server can return it in context responses without importing the
        Python class.
        """
        return cls.trade_view.model_dump() if cls.trade_view is not None else None

    @classmethod
    def ref(cls) -> str:
        """Canonical reference for DB lookup.  Uses the name."""
        return cls.get_name()

    @classmethod
    def get_name(cls) -> str:
        """Return the unique name (``UPPER_SNAKE_CASE``).

        Derives from the class name by inserting underscores before
        uppercase letters and uppercasing
        (e.g. ``TimingStrategy`` -> ``TIMING_STRATEGY``).
        """
        import re

        return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", cls.__name__).upper()

    @classmethod
    def get_display_name(cls) -> str:
        """Return the display name.

        If ``display_name`` is not set, derives it from the class name
        by inserting spaces before each uppercase letter
        (e.g. ``TimingStrategy`` -> ``Timing Strategy``).
        """
        if cls.display_name:
            return cls.display_name
        import re

        return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", cls.__name__)

    @classmethod
    def feed_refs(cls) -> list[str]:
        """Return ``module:ClassName`` references for all declared feeds."""
        if cls.feeds is None:
            return []
        return [f.ref() for f in cls.feeds]

    # ------------------------------------------------------------------
    # Runner
    # ------------------------------------------------------------------

    @classmethod
    def run(
        cls,
        *,
        database_url: str | None = None,
        redis_url: str | None = None,
        log_level: str = "INFO",
    ) -> None:
        """Auto-deploy and run this strategy as a long-running process.

        Registers (or updates) the strategy in the database, then starts
        the engine consumer loop.  Blocks until SIGINT/SIGTERM.
        """
        from ascent.engine.runner import Runner

        runner = Runner(
            database_url=database_url,
            redis_url=redis_url,
            log_level=log_level,
        )
        runner.add(cls)
        runner.run()
