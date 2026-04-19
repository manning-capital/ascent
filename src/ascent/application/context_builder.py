"""Pure function that assembles the strategy evaluation context.

Builds a :class:`Context` dataclass that wraps:

- ``df``: the consolidated DataFrame indexed by ``instrument_id`` (or
  ``(composite_id, instrument_id)`` for composite strategies)
- ``universe``: the strategy's active scope IDs the strategy may open new
  trades on (stringified for ``df.index``-keyed access)
- ``open_only``: IDs present in ``df`` because of a non-terminal trade but
  *not* in ``universe`` — exit-only set, includes both disabled scope rows
  and removed-but-still-open instruments

The function is deliberately pure: all inputs are pre-loaded by the use
case. That makes it trivially testable with dict fixtures — no DB mocking.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from ascent.domain import Trade, TradeState

Scope = Literal["instrument", "composite"]

TRADE_FIELDS = (
    "status",
    "trade_id",
    "direction",
    "entry_price",
    "quantity",
    "unrealized_pnl",
    "entry_at",
    "order_status",
    "filled_quantity",
)


@dataclass(frozen=True)
class FeedFrame:
    feed_id: uuid.UUID
    feed_name: str  # lowercase, becomes the level-0 column tag
    is_composite_scoped: bool
    data: pd.DataFrame  # wide shape: entity_id column + one column per attribute


@dataclass(frozen=True)
class Context:
    """Strategy evaluation context.

    ``df`` is the assembled DataFrame; ``universe`` and ``open_only`` are
    membership sets the strategy can use to decide whether an ID is open-eligible
    or exit-only without inspecting the trade columns.
    """

    df: pd.DataFrame
    universe: frozenset[str]
    open_only: frozenset[str]


def build_context(
    *,
    scope: Scope,
    feed_frames: list[FeedFrame],
    trades: list[Trade],
    composite_members: dict[uuid.UUID, list[uuid.UUID]] | None = None,
    universe_ids: set[uuid.UUID] | None = None,
    open_position_ids: set[uuid.UUID] | None = None,
) -> Context:
    """Build the strategy-evaluation context.

    The frame index is the union of ``universe_ids`` and ``open_position_ids``.
    Universe items without feed data still appear (with NaN feed columns) so
    the strategy can act on them; open positions outside the universe still
    appear so they can be exited.

    - ``instrument`` scope: index is ``instrument_id``.
    - ``composite`` scope: index is ``(composite_id, instrument_id)``.

    All IDs are stringified at the edge so pandas ``.loc`` is consistent.
    """
    universe_ids = set(universe_ids or ())
    open_position_ids = set(open_position_ids or ())
    composite_members = composite_members or {}

    if scope == "composite":
        composite_ids = universe_ids | open_position_ids
        instrument_ids: set[uuid.UUID] = set()
        for comp_id in composite_ids:
            instrument_ids.update(composite_members.get(comp_id, ()))
    else:
        instrument_ids = universe_ids | open_position_ids
        composite_ids = set()

    index = _build_index(scope, instrument_ids, composite_ids, composite_members)

    universe_str = frozenset(str(i) for i in universe_ids)
    open_only_str = frozenset(str(i) for i in (open_position_ids - universe_ids))

    if len(index) == 0:
        return Context(df=pd.DataFrame(), universe=universe_str, open_only=open_only_str)

    trade_df = _build_trade_columns(index, scope, trades, composite_members)
    feed_dfs = [_pivot_feed(frame, index, scope) for frame in feed_frames]
    feed_dfs = [df for df in feed_dfs if df is not None and not df.empty]
    df = pd.concat([trade_df] + feed_dfs, axis=1) if feed_dfs else trade_df
    return Context(df=df, universe=universe_str, open_only=open_only_str)


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------


def _build_index(
    scope: Scope,
    instrument_ids: set[uuid.UUID],
    composite_ids: set[uuid.UUID],
    composite_members: dict[uuid.UUID, list[uuid.UUID]],
) -> pd.Index:
    if scope == "composite":
        tuples: list[tuple[str, str]] = []
        for comp_id in sorted(str(cid) for cid in composite_ids):
            members = composite_members.get(uuid.UUID(comp_id), [])
            for inst_id in members:
                tuples.append((comp_id, str(inst_id)))
        if not tuples:
            return pd.MultiIndex.from_tuples([], names=["composite_id", "instrument_id"])
        return pd.MultiIndex.from_tuples(tuples, names=["composite_id", "instrument_id"])
    if not instrument_ids:
        return pd.Index([], name="instrument_id")
    return pd.Index(sorted(str(iid) for iid in instrument_ids), name="instrument_id")


def _build_trade_columns(
    index: pd.Index,
    scope: Scope,
    trades: list[Trade],
    composite_members: dict[uuid.UUID, list[uuid.UUID]],
) -> pd.DataFrame:
    n = len(index)
    data = pd.DataFrame(
        {
            ("trade", "status"): [TradeState.PENDING.value] * n,
            ("trade", "trade_id"): [None] * n,
            ("trade", "direction"): [None] * n,
            ("trade", "entry_price"): [np.nan] * n,
            ("trade", "quantity"): [np.nan] * n,
            ("trade", "unrealized_pnl"): [np.nan] * n,
            ("trade", "entry_at"): pd.array([pd.NaT] * n, dtype="datetime64[ns, UTC]"),
            ("trade", "order_status"): [None] * n,
            ("trade", "filled_quantity"): [np.nan] * n,
        },
        index=index,
    )
    data.columns = pd.MultiIndex.from_tuples(data.columns.tolist())

    # Default: no active trade → WAITING
    data[("trade", "status")] = "WAITING"

    comp_reverse: dict[frozenset[str], str] = {}
    if scope == "composite":
        for comp_id, members in composite_members.items():
            comp_reverse[frozenset(str(m) for m in members)] = str(comp_id)

    for trade in trades:
        if trade.state.is_terminal:
            continue
        leg_inst_ids = frozenset(str(leg.instrument_id) for leg in trade.legs)
        if scope == "composite":
            comp_id = comp_reverse.get(leg_inst_ids)
            if comp_id is None:
                continue
            for leg in trade.legs:
                key = (comp_id, str(leg.instrument_id))
                if key not in data.index:
                    continue
                _fill_row(data, key, trade, leg)
        else:
            for leg in trade.legs:
                key = str(leg.instrument_id)
                if key not in data.index:
                    continue
                _fill_row(data, key, trade, leg)

    return data


def _fill_row(data: pd.DataFrame, key, trade: Trade, leg) -> None:
    data.loc[key, ("trade", "status")] = trade.state.value
    data.loc[key, ("trade", "trade_id")] = str(trade.id)
    data.loc[key, ("trade", "direction")] = leg.direction.value
    data.loc[key, ("trade", "entry_price")] = (
        leg.entry_price if leg.entry_price is not None else np.nan
    )
    data.loc[key, ("trade", "quantity")] = leg.quantity
    data.loc[key, ("trade", "entry_at")] = trade.entry_at
    if leg.entry_order:
        data.loc[key, ("trade", "order_status")] = leg.entry_order.state.value
        data.loc[key, ("trade", "filled_quantity")] = leg.entry_order.filled_quantity


def _pivot_feed(frame: FeedFrame, index: pd.Index, scope: Scope) -> pd.DataFrame | None:
    """Align a wide feed frame to the strategy-context index.

    Feeds emit wide frames: one row per entity with the entity id in
    ``instrument_id`` or ``composite_id`` and one column per attribute. This
    function promotes the entity column into the index, drops any reserved
    non-attribute columns, and tags the remaining columns with the feed name
    as the level-0 MultiIndex tag so strategies can access values as
    ``ctx.df[(feed_name, attribute)]``.
    """
    df = frame.data
    if df is None or df.empty:
        return None

    entity_col = (
        "composite_id"
        if frame.is_composite_scoped and "composite_id" in df.columns
        else "instrument_id"
        if "instrument_id" in df.columns
        else None
    )
    if entity_col is None:
        return None

    working = df.copy()
    working[entity_col] = working[entity_col].astype(str)
    working = working.drop_duplicates(subset=[entity_col], keep="last").set_index(entity_col)

    drop = [c for c in ("period_id",) if c in working.columns]
    if drop:
        working = working.drop(columns=drop)
    if working.empty or working.shape[1] == 0:
        return None

    working.columns = pd.MultiIndex.from_tuples([(frame.feed_name, col) for col in working.columns])

    if scope == "composite":
        if frame.is_composite_scoped:
            comp_ids = index.get_level_values("composite_id")
            result = working.reindex(comp_ids)
        else:
            inst_ids = index.get_level_values("instrument_id")
            result = working.reindex(inst_ids)
        result.index = index
        return result

    return working.reindex(index)
