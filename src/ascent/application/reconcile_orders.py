"""OrderReconciler — startup reconciliation of stale orders against the exchange.

For each non-terminal order whose parent trade is non-terminal, asks the
exchange what happened to it, then feeds a synthetic ``FillEvent`` through
the :class:`FillProcessor`. One code path for live fills and reconciliation.

After per-order processing, a balance-based sweep terminates trades that
the exchange's reported balances can't actually back. See
:meth:`OrderReconciler._sweep_phantom_trades` for the rationale.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from ascent.application.process_fill import FillProcessor
from ascent.domain import FillEvent, OrderState, PositionType, Trade, TradeState
from ascent.exchanges.base import OrderStatusResponse
from ascent.ports import (
    EventBus,
    ExchangePort,
    OrderRepository,
    TradeRepository,
    UnitOfWorkFactory,
)

logger = logging.getLogger(__name__)

UI_CHANNEL = "ascent.trades.updates"

#: Tolerance for "balance covers claim" comparisons. Tuned for typical
#: instrument lot sizes; tighten per-instrument in a follow-up if the
#: ledger ever needs sub-1e-6 precision.
_BALANCE_EPSILON = Decimal("1e-6")

ORPHAN_REASON = "RECONCILIATION_ORPHAN"


@dataclass(frozen=True)
class _LegClaim:
    trade_id: uuid.UUID
    asset_symbol: str
    signed_claim: Decimal


class OrderReconciler:
    def __init__(
        self,
        *,
        order_repo: OrderRepository,
        fill_processor: FillProcessor,
        uow_factory: UnitOfWorkFactory,
        trade_repo: TradeRepository | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._orders = order_repo
        self._fills = fill_processor
        self._uow_factory = uow_factory
        # Optional: self-heal legacy trades with missing entry_order_id linkage.
        # Required for the phantom-trade sweep — without a trade repo, the
        # sweep is skipped silently.
        self._trades = trade_repo
        self._bus = event_bus

    async def reconcile(
        self,
        *,
        exchange: ExchangePort,
        exchange_id: uuid.UUID,
        now: datetime,
    ) -> int:
        async with self._uow_factory() as uow:
            stale = await self._orders.list_for_exchange(
                uow.session, exchange_id, only_non_terminal_trades=True
            )

        count = 0
        if stale:
            logger.info("Reconciliation: checking %d stale order(s)", len(stale))
            for order, leg_id, trade_id in stale:
                if self._trades is not None:
                    await self._heal_linkage(order=order, leg_id=leg_id, trade_id=trade_id)
                status = await self._lookup(exchange, order)
                event = _to_fill_event(order.id, status)
                if event is None:
                    continue
                await self._fills.process(trade_id=trade_id, event=event, now=now)
                count += 1
            logger.info("Reconciliation: processed %d fill events", count)
        else:
            logger.info("Reconciliation: no stale orders on exchange %s", exchange_id)

        await self._sweep_phantom_trades(exchange=exchange, exchange_id=exchange_id, now=now)
        return count

    async def _heal_linkage(
        self,
        *,
        order,
        leg_id: uuid.UUID,
        trade_id: uuid.UUID,
    ) -> None:
        """Backfill ``TradeLeg.entry_order_id`` / ``exit_order_id`` when the
        original submit path left them NULL. Safe to run repeatedly — only
        writes when the slot is empty.
        """
        async with self._uow_factory() as uow:
            trade = await self._trades.get(uow.session, trade_id)
            if trade is None:
                return
            leg = next((leg_ for leg_ in trade.legs if leg_.id == leg_id), None)
            if leg is None:
                return
            if leg.entry_order is None:
                await self._trades.set_entry_order(uow.session, leg_id, order.id)
            elif leg.exit_order is None and leg.entry_order.id != order.id:
                await self._trades.set_exit_order(uow.session, leg_id, order.id)

    async def _lookup(self, exchange: ExchangePort, order) -> OrderStatusResponse | None:
        if order.external_order_id:
            return await exchange.get_order_status(order.external_order_id)
        try:
            return await exchange.get_order_by_client_id(str(order.id))
        except NotImplementedError:
            return None

    # ------------------------------------------------------------------
    # Phantom-trade sweep
    # ------------------------------------------------------------------

    async def _sweep_phantom_trades(
        self,
        *,
        exchange: ExchangePort,
        exchange_id: uuid.UUID,
        now: datetime,
    ) -> None:
        """Terminate non-terminal trades whose claimed positions aren't backed
        by the exchange's reported balances.

        The state machine's ``CLOSING → OPEN`` revert (see
        :func:`ascent.domain.state_machine._resolve_closing`) is correct in
        production when an exchange transiently cancels exit orders — the
        strategy will reissue and the trade closes normally. But after a
        paper-exchange restart, every previously-submitted order returns
        ``NOT_FOUND``; the reverted-to-OPEN trade then has no active orders
        and no path forward, blocking new positions on the same composite.

        The sweep treats the exchange's ``get_balances()`` as the source of
        truth: if Ascent's claimed positions aggregate to more than the
        exchange holds (signed; longs and shorts net), the excess is
        attributed to candidate trades and they're terminated. Candidates
        are non-terminal trades with no active orders; trades whose orders
        are still working are never touched.

        Selection is deterministic: candidates are sorted by ``(no realized
        PnL, newest first)`` so the cheapest-to-cancel trades go first.

        Caveat — this rule is necessary but not sufficient. A phantom trade
        whose claim happens to be balanced by unrelated activity (manual
        trades on the same account, other bots) won't be detected. For the
        :class:`PaperExchange` ledger this isn't an issue because the
        ledger is exclusively Ascent's; on real exchanges it's a documented
        limitation that a follow-up can tighten with strategy-level
        position attribution.
        """
        if self._trades is None:
            return

        async with self._uow_factory() as uow:
            trades = await self._trades.list_non_terminal_for_exchange(uow.session, exchange_id)

        if not trades:
            return

        balances = await exchange.get_balances()
        balance_total: dict[str, Decimal] = {
            entry.asset_symbol: Decimal(str(entry.total)) for entry in balances
        }

        claims = list(_collect_claims(trades))
        if not claims:
            return

        aggregate: dict[str, Decimal] = {}
        for claim in claims:
            aggregate[claim.asset_symbol] = (
                aggregate.get(claim.asset_symbol, Decimal("0")) + claim.signed_claim
            )

        candidates = [t for t in trades if not _has_active_orders(t)]
        if not candidates:
            return

        phantom_ids = _select_phantoms(
            candidates=candidates,
            aggregate=aggregate,
            balance=balance_total,
            epsilon=_BALANCE_EPSILON,
        )
        if not phantom_ids:
            return

        terminated = 0
        for trade in candidates:
            if trade.id not in phantom_ids:
                continue
            await self._terminate_phantom(trade, now=now)
            terminated += 1

        if terminated:
            logger.info(
                "Reconciliation: swept %d phantom trade(s) on exchange %s",
                terminated,
                exchange_id,
            )

    async def _terminate_phantom(self, trade: Trade, *, now: datetime) -> None:
        any_exit_filled = any(
            leg.realized_pnl is not None or (leg.exit_order and leg.exit_order.filled_quantity > 0)
            for leg in trade.legs
        )
        if any_exit_filled:
            new_state = TradeState.CLOSED
            total_pnl = round(sum(leg.realized_pnl or 0.0 for leg in trade.legs), 6)
            exit_at: datetime | None = now
        else:
            new_state = TradeState.CANCELLED
            total_pnl = None
            exit_at = None

        async with self._uow_factory() as uow:
            await self._trades.set_state(
                uow.session,
                trade.id,
                new_state=new_state,
                at=now,
                exit_at=exit_at,
                total_realized_pnl=total_pnl,
                close_reason=ORPHAN_REASON,
            )

        if self._bus is not None:
            await self._bus.publish(
                UI_CHANNEL, {"event": "trade_updated", "trade_id": str(trade.id)}
            )


# ---------------------------------------------------------------------------
# Pure helpers (no I/O, easy to unit-test)
# ---------------------------------------------------------------------------


def _to_fill_event(order_id: uuid.UUID, status: OrderStatusResponse | None) -> FillEvent | None:
    if status is None or status.status == "NOT_FOUND":
        return FillEvent(order_id=order_id, state=OrderState.CANCELLED)
    try:
        state = OrderState(status.status)
    except ValueError:
        logger.warning("Reconciliation: unknown exchange status '%s'", status.status)
        return None
    return FillEvent(
        order_id=order_id,
        state=state,
        filled_quantity=status.filled_quantity or 0.0,
        average_fill_price=status.average_fill_price,
        external_order_id=status.exchange_order_id,
        error_message=status.error_message,
    )


def _has_active_orders(trade: Trade) -> bool:
    for leg in trade.legs:
        if leg.entry_order is not None and leg.entry_order.state.is_active:
            return True
        if leg.exit_order is not None and leg.exit_order.state.is_active:
            return True
    return False


def _collect_claims(trades: list[Trade]):
    """Yield :class:`_LegClaim` for every leg that has a base-asset position."""
    for trade in trades:
        for leg in trade.legs:
            asset = leg.from_asset_symbol
            if asset is None:
                # Without an asset symbol we can't compare to the balance.
                # Don't crash; just skip — the sweep is best-effort.
                continue
            entry_filled = (
                Decimal(str(leg.entry_order.filled_quantity))
                if leg.entry_order is not None
                else Decimal("0")
            )
            exit_filled = (
                Decimal(str(leg.exit_order.filled_quantity))
                if leg.exit_order is not None
                else Decimal("0")
            )
            net = entry_filled - exit_filled
            if net == 0:
                continue
            signed = net if leg.direction == PositionType.LONG else -net
            yield _LegClaim(trade_id=trade.id, asset_symbol=asset, signed_claim=signed)


def _select_phantoms(
    *,
    candidates: list[Trade],
    aggregate: dict[str, Decimal],
    balance: dict[str, Decimal],
    epsilon: Decimal,
) -> set[uuid.UUID]:
    """Return ids of candidate trades whose claims aren't backed by balance.

    Walks candidates in ``(no realized PnL, newest first)`` order, removing
    each from the aggregate until the per-asset mismatch falls within
    ``epsilon``. Trades removed in that walk are phantoms.
    """
    # Per-asset signed mismatch. Positive → Ascent claims more longs (or
    # fewer shorts) than the exchange holds.
    mismatch: dict[str, Decimal] = {}
    for asset, claim in aggregate.items():
        diff = claim - balance.get(asset, Decimal("0"))
        if abs(diff) > epsilon:
            mismatch[asset] = diff

    if not mismatch:
        return set()

    ordered = _termination_order(candidates)
    phantoms: set[uuid.UUID] = set()

    for trade in ordered:
        if not mismatch:
            break
        contribution = _trade_claim_by_asset(trade)
        # A candidate is phantom if removing its contribution moves the
        # mismatch closer to zero on at least one asset that still mismatches.
        helps = False
        for asset, signed_claim in contribution.items():
            current = mismatch.get(asset)
            if current is None:
                continue
            new_value = current - signed_claim
            if abs(new_value) < abs(current):
                helps = True
                break
        if not helps:
            continue
        phantoms.add(trade.id)
        for asset, signed_claim in contribution.items():
            if asset not in mismatch:
                continue
            mismatch[asset] = mismatch[asset] - signed_claim
            if abs(mismatch[asset]) <= epsilon:
                mismatch.pop(asset, None)

    return phantoms


def _trade_claim_by_asset(trade: Trade) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for leg in trade.legs:
        asset = leg.from_asset_symbol
        if asset is None:
            continue
        entry_filled = (
            Decimal(str(leg.entry_order.filled_quantity))
            if leg.entry_order is not None
            else Decimal("0")
        )
        exit_filled = (
            Decimal(str(leg.exit_order.filled_quantity))
            if leg.exit_order is not None
            else Decimal("0")
        )
        net = entry_filled - exit_filled
        if net == 0:
            continue
        signed = net if leg.direction == PositionType.LONG else -net
        out[asset] = out.get(asset, Decimal("0")) + signed
    return out


def _termination_order(candidates: list[Trade]) -> list[Trade]:
    """Sort candidates so cheapest-to-cancel go first.

    Trades with no realized PnL on any leg (no exit fills) come before
    trades that have filled exits. Within each group, newest entries (by
    ``entry_at``) come first so freshly-orphaned trades take precedence
    over older ones that may have been intentionally left open.
    """

    def has_filled_exit(trade: Trade) -> bool:
        for leg in trade.legs:
            if leg.realized_pnl is not None:
                return True
            if leg.exit_order is not None and leg.exit_order.filled_quantity > 0:
                return True
        return False

    return sorted(
        candidates,
        key=lambda t: (
            has_filled_exit(t),  # False (no fills) before True
            -(t.entry_at.timestamp() if t.entry_at else 0),
        ),
    )


_ = datetime  # re-export anchor
