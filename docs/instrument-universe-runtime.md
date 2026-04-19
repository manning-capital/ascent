# Instrument Universe — Runtime Enforcement Plan

## Goal

The strategy/feed scope tables are already populated via the UI but are not consulted at runtime. This plan wires them into the subsystems that should obey them:

- **Feeds** fetch data only for instruments in their (active) scope.
- **Strategies** evaluate a context DataFrame pre-filtered to the active strategy universe (plus any instruments with open positions).
- **Exchanges** reject orders whose instrument's `(provider, instrument_type)` doesn't match the target exchange, or whose strategy-exchange assignment is disabled. **Exchanges no longer have a configurable instrument universe** — admissibility is purely determined by the provider+type pairing declared on the exchange class.

Rejections are persisted and visible in the UI.

**Phase-out is first-class.** Scope items and strategy-exchange assignments carry an `is_active` flag; entire strategies carry an `is_paused` flag. Disabled/paused rows block *new* trades but allow existing open trades to be managed and exited. Destructive deletes are blocked by an impact check whenever open trades or dependent universe items would be affected — the UI shows the impact and steers the user toward disabling instead.

---

## Current state (what's already in place)

- Six scope tables exist and are CRUD-backed by [universe_service.py](src/ascent/server/services/universe_service.py): `StrategyInstrumentScope`, `StrategyCompositeScope`, `FeedInstrumentScope`, `FeedCompositeScope`, `ExchangeInstrumentScope`, `ExchangeCompositeScope`. **The two `Exchange*Scope` tables become deprecated** — see Phase 0.
- Strategy↔Exchange tradeability validation runs on write ([universe_service.py:32-105](src/ascent/server/services/universe_service.py#L32-L105)). `add_feed_universe_item` ([line 224](src/ascent/server/services/universe_service.py#L224)) has no validation.
- UI universe panel ([universe-panel.component.ts](src/ascent/ui/src/app/components/shared/universe-panel.component.ts)) is reused across exchange/feed/strategy detail pages.
- `Feed.instrument_type` / `composite_type` are class-level type gates ([feeds/base.py:134-138](src/ascent/feeds/base.py#L134-L138)); the instance universe lives in `FeedInstrumentScope` rows but the runtime ignores them.
- `BaseExchange.provider` / `instrument_type` ([exchanges/base.py:114-117](src/ascent/exchanges/base.py#L114-L117)) declare the automatic type gate.
- `build_context()` ([context_builder.py:42-68](src/ascent/application/context_builder.py#L42-L68)) builds the strategy DataFrame from whatever the feed published — no universe filter.
- `TradeRouter.submit` ([route_trade.py:101-212](src/ascent/application/route_trade.py#L101-L212)) writes trade/order rows unconditionally — no scope check.

---

## Target behavior

### Feeds — universe drives what to fetch

The runner loads `FeedInstrumentScope` (or `FeedCompositeScope` per the XOR in [feeds.py:26-28](src/ascent/database/models/feeds.py#L26-L28)) and hands the resolved ID list to the feed instance before each `fetch()` / `stream()` call. User code reads it via `self.get_universe()`, the same pattern as `self.get_feed()` / `self.get_partition()`.

- Empty scope → feed runs but fetches nothing (log at INFO, don't error). This is intentional: the scope is the authoritative instance-level universe.
- Feeds with `composite_type` get a `list[CompositeSpec]` with expanded member IDs so they can drive per-member API calls.

### Strategies — universe pre-filters `ctx`

`build_context()` returns a new `Context` dataclass that wraps the consolidated DataFrame plus universe metadata:

```python
@dataclass(frozen=True)
class Context:
    df: pd.DataFrame              # the existing pivoted/joined frame
    universe: frozenset[str]      # active scope IDs the strategy may OPEN new trades on
    open_only: frozenset[str]     # IDs in df because of an open trade but NOT in universe
```

`df`'s index is filtered to:

    allowed = active_universe_ids ∪ instruments_with_non_terminal_trades

where `active_universe_ids` is the subset of scope rows with `is_active=true`.

The union is load-bearing on both sides:
- Removing or disabling `AAPL` while a position is open → strategy must still see `AAPL` in `df` to manage/exit. `AAPL` lands in `open_only`.
- An active scope row with no open trade → present in `universe` as a candidate for new entries.
- An active scope row with an open trade → present in `universe` (still tradeable for new opens or scales) and *not* in `open_only`.

Strategy code becomes more readable:

```python
def evaluate(self, ctx: Context) -> None:
    for inst_id in ctx.universe:
        price = ctx.df.loc[inst_id, ('market_data', 'close')]
        ...
    for inst_id in ctx.open_only:
        # exit-only logic: never open new positions, just manage existing
        ...
```

Composite strategies work the same way on `StrategyCompositeScope`, keyed on composite IDs (still as stringified UUIDs).

### Exchanges — order-routing gate (no per-exchange universe)

Exchanges no longer carry an instrument universe. Their tradable set is purely the set of instruments whose `(provider_id, instrument_type_id)` matches the exchange's declared pair (from class-level `BaseExchange.provider` / `instrument_type`). This is the same automatic type gate as before; the manually-configured `ExchangeInstrumentScope` / `ExchangeCompositeScope` tables drop out of the runtime entirely.

Check happens in `TradeRouter.submit` **before** any DB write. Two layers — both apply to opens; **closes bypass every gate** because the existence of the trade is itself proof that the routing was previously valid:

1. **Type gate.** Instrument's `(provider_id, instrument_type_id)` must match the target exchange's declared pair.
2. **Strategy-exchange assignment gate.** The `StrategyExchange` row for this (strategy, exchange) pair must have `is_active=true`, AND the strategy itself must have `is_paused=false`. Disabled assignments / paused strategies block new routing but leave existing open trades (already persisted with this `exchange_id`) free to close.

`TradeRouter.close` runs no gates — the legs already carry validated `exchange_id` / `instrument_id` from when the trade was opened. If config has drifted underneath an open trade (instrument retyped, etc.) we still let the close attempt through; any genuine routing failure surfaces as an exchange-side API error through the normal fill path.

On rejection: create a `Trade` row immediately in a new terminal state `TradeState.REJECTED` with `close_reason` holding a structured reason (e.g. `UNIVERSE_SCOPE:provider_mismatch`, `UNIVERSE_SCOPE:assignment_disabled`, `UNIVERSE_SCOPE:strategy_paused`). Return a `TradeDraft(state=REJECTED, leg_summaries=[])`. Rejections appear in the Trades UI with the same visibility as cancelled/closed trades.

For composites: every leg must pass the type gate. If any leg fails, the entire composite trade is rejected — composites are atomic and partial fills aren't acceptable.

---

---

## Lifecycle: active vs disabled, and when removal is blocked

The scope rows and strategy-exchange assignments gain an `is_active` boolean with default `true`. Two state transitions matter:

- **Disable** (`is_active: true → false`). Phase-out. Blocks new trades but lets open trades exit normally.
- **Remove** (DELETE). Destructive. Only permitted when no open trades or downstream configuration would break.

### Remove-block matrix

| Deleting | Blocked when | Suggested alternative |
|---|---|---|
| `StrategyInstrumentScope` row | strategy has non-terminal trade on the instrument | Disable |
| `StrategyCompositeScope` row | strategy has non-terminal trade on the composite | Disable |
| `StrategyExchange` row (strategy ↔ exchange) | (a) strategy has non-terminal trade whose `exchange_id` = this exchange, OR (b) any *active* `StrategyInstrumentScope` / `StrategyCompositeScope` row for this strategy would be orphaned (no remaining exchange on the strategy matches its `(provider_id, instrument_type_id)`) | Disable, or first remove/disable the affected universe items |
| `FeedInstrumentScope` / `FeedCompositeScope` row | any strategy using this feed has an *active* universe item that depends on it (they need the data to evaluate; open trades need it to exit) | Disable, or remove dependent strategy universe items first |

Pausing a strategy (`is_paused = true`) is always allowed — no blockers. It doesn't affect open trades' ability to exit; it only blocks new opens.

Disable is unrestricted **except** for feed-scope items: disabling a `FeedInstrumentScope` row is rejected if any strategy that uses this feed has a non-terminal trade on the instrument. The open trade needs price data to manage and exit; killing the feed for it would strand the position. Same impact-payload structure is returned so the UI can show the blocking trades.

### Impact-check contract

Every delete endpoint first calls a companion `GET .../impact` that returns:

```json
{
  "can_remove": false,
  "reasons": ["2 open trades reference this instrument"],
  "blocking_trades": [
    {"trade_id": "...", "entry_at": "...", "direction": "LONG", "quantity": 0.01}
  ],
  "blocking_scope_items": [
    {"type": "strategy_universe", "strategy_id": "...", "instrument_id": "..."}
  ],
  "suggested_action": "disable"
}
```

The UI hits the impact endpoint on click and opens a modal with the payload. If `can_remove: false`, the primary action is **Disable** (or the nested fix-it, e.g. "Remove 2 dependent universe items first"); **Delete** is disabled. If `can_remove: true`, the modal is a standard confirmation and **Delete** is the primary action.

The DELETE endpoint itself re-runs the same check server-side and returns `409 Conflict` with the same payload on violation — the UI's impact call is an ergonomic optimization, not the trust boundary.

---

## Cross-cutting: drift validation

With per-exchange universes gone, the constraint simplifies. A strategy's universe item is valid iff:

1. The instrument's `(provider_id, instrument_type_id)` matches at least one of the strategy's `StrategyExchange` rows (so an order could route somewhere).
2. The instrument is in at least one of the strategy's feeds' active scope (so the strategy will receive price data for it).

Validation runs at write-time on `POST /strategies/{id}/universe` (extends the existing `_validate_instruments_tradeable` check) and on `POST /feeds/{id}/universe` (currently has no validation — see [universe_service.py:224](src/ascent/server/services/universe_service.py#L224)). The feed-side check enforces type matching against the feed's declared `instrument_type` / `composite_type`.

---

## Implementation plan

Ordered so each phase is independently mergeable and shippable.

### Phase 0 — Remove exchange-side instrument scope

The decision to drop per-exchange universes lands first as a clean removal, before we build new behavior on top.

**Backend**
- [src/ascent/server/routers/exchanges.py](src/ascent/server/routers/exchanges.py) — remove the universe endpoints (`GET/POST/DELETE /exchanges/{id}/universe[...]`, `GET/POST/DELETE /exchanges/{id}/composite-universe[...]`, batch variants, search variants).
- [src/ascent/server/services/universe_service.py](src/ascent/server/services/universe_service.py) — delete `get_exchange_universe`, `get_exchange_universe_paginated`, `add_exchange_universe_item`, `remove_exchange_universe_item`, `batch_add_exchange_instruments`, and the four composite equivalents ([lines 463-617](src/ascent/server/services/universe_service.py#L463-L617)).
- [src/ascent/database/models/exchanges.py](src/ascent/database/models/exchanges.py) — delete the `ExchangeInstrumentScope` and `ExchangeCompositeScope` ORM classes and the `instrument_scopes` / `composite_scopes` relationships on the `Exchange` model.
- [src/ascent/database/models/__init__.py](src/ascent/database/models/__init__.py) — drop the re-exports.
- **Alembic migration** — drop tables `exchange_instrument_scope` and `exchange_composite_scope`. Single forward-only migration; downgrade left empty (this is a deliberate removal). No data preservation — universe configuration moves to the type-gate model.

**Frontend**
- [src/ascent/ui/src/app/components/exchanges/exchange-detail/exchange-detail.component.ts](src/ascent/ui/src/app/components/exchanges/exchange-detail/exchange-detail.component.ts) — remove the Universe tab and the `universeMode` toggle ([line 53, 101-107](src/ascent/ui/src/app/components/exchanges/exchange-detail/exchange-detail.component.ts#L53)).
- Exchange list/detail no longer surfaces universe counts.

**Tests**
- Delete the exchange-scope contract tests under [tests/contract/](tests/contract/).

### Phase 1 — Feed runtime respects `FeedInstrumentScope`

**Files**
- [src/ascent/feeds/base.py](src/ascent/feeds/base.py) — add `self.get_universe()` accessor backed by a new `_current_universe` contextvar in [src/ascent/engine/context.py](src/ascent/engine/context.py).
- [src/ascent/engine/runner.py](src/ascent/engine/runner.py) — `_FeedFetcherBridge.fetch` ([line 735](src/ascent/engine/runner.py#L735)) re-reads the active feed scope (`is_active=true`) from the DB at the top of each tick before invoking user code, then sets `_current_universe`. Per-tick query is cheap (one indexed lookup on `feed_id`); avoids stale-cache bugs when users disable items.
- [src/ascent/application/feed_execution.py](src/ascent/application/feed_execution.py) (wherever `FeedExecutor` lives — check `ascent.application`) — thread the universe through so it survives across scheduled/triggered paths.
- **Example feed** [feed.py](feed.py) — replace the `_instruments` classvar bootstrap with `self.get_universe()`. Remove the `_load_instruments` bootstrap in `__main__`.

**Contract**
```python
# inside a user Feed.fetch()
universe = self.get_universe()           # list[uuid.UUID] for instrument feeds
composites = self.get_universe()         # list[CompositeSpec] for composite feeds
# CompositeSpec = (composite_id, ordered_member_instrument_ids)
```

**Tests**
- Unit: `_current_universe` propagates through the fetcher bridge.
- Contract: adding/removing a `FeedInstrumentScope` row changes the list returned by `self.get_universe()` on the next tick (no restart).
- Integration: a feed with empty scope no-ops but still heartbeats.

### Phase 2 — Strategy context pre-filtering

**Files**
- [src/ascent/application/context_builder.py](src/ascent/application/context_builder.py) —
  - Add a new `Context` frozen dataclass alongside the existing `FeedFrame`: fields `df: pd.DataFrame`, `universe: frozenset[str]`, `open_only: frozenset[str]`.
  - Change `build_context()`'s return type from `pd.DataFrame` to `Context`.
  - Add `universe_ids: set[uuid.UUID] | None = None` and `open_position_ids: set[uuid.UUID] = set()` params.
  - Filter the index after `_build_index`; populate the dataclass with the filtered frame plus the two stringified frozensets.
- [src/ascent/strategies/base.py](src/ascent/strategies/base.py) —
  - Update the `Strategy.evaluate(self, ctx)` abstract method signature: `ctx: Context` (not `pd.DataFrame`).
  - Update the docstring ([lines 102-123](src/ascent/strategies/base.py#L102-L123)) to describe `ctx.df`, `ctx.universe`, `ctx.open_only`.
  - Re-export `Context` from `ascent.strategies` for ergonomic import.
- [src/ascent/application/evaluate_strategy.py](src/ascent/application/evaluate_strategy.py) — `_build_context` ([line 131](src/ascent/application/evaluate_strategy.py#L131)) loads the scope rows for the strategy (via a new repo method, filtering on `is_active=true`) and the non-terminal trades (already loaded on [line 147](src/ascent/application/evaluate_strategy.py#L147)). Derive `open_position_ids` from the trades' legs. Pass both into `build_context`. The `evaluator(ctx, run_id)` callable now receives a `Context`, not a `DataFrame` — update the `Evaluator` type alias on [line 44](src/ascent/application/evaluate_strategy.py#L44).
- [src/ascent/ports/](src/ascent/ports/) — add `StrategyUniverseRepository.get_active_universe(strategy_id) -> set[uuid.UUID]`.
- [src/ascent/adapters/sqlalchemy/](src/ascent/adapters/sqlalchemy/) — SQLA impl reading `StrategyInstrumentScope` / `StrategyCompositeScope` filtered to `is_active=true`.
- [src/ascent/engine/runner.py](src/ascent/engine/runner.py) — `_load_strategy_info` ([line 513](src/ascent/engine/runner.py#L513)) loads the static parts (portfolio, feed bindings, exchange list); active universe is re-queried per tick inside `StrategyEvaluator._build_context` so disable/enable changes apply on the next evaluation without a restart.
- [strategy.py](strategy.py) (example) — update `evaluate(self, ctx)` to use `ctx.df.loc[...]` instead of `ctx.loc[...]`. Single-line change to the existing `_spread()` helper.

**Why a dataclass (vs `df.attrs`)**
- Discoverable: type checkers and IDE autocomplete surface `ctx.universe` immediately. `ctx.attrs['universe']` is a string literal that types can't help with.
- Survives DataFrame operations: pandas `.attrs` is famously unreliable across operations (joins, copies, `.loc` slices often drop it). The dataclass holds the metadata outside the frame.
- Clearer contract: the dataclass declares exactly what the strategy receives. `df.attrs` is a free-form dict.

**Tests**
- Unit on `context_builder`: given a universe of {A, B} and trades on {B, C}, the returned `Context` has `df.index = {A, B, C}`, `universe = {A, B}`, `open_only = {C}`.
- Unit: empty universe with open trades → `df.index = open_only_ids`, `universe = frozenset()`.
- Integration on `evaluate_strategy`: live strategy with 3 instruments in scope and 1 open trade outside scope receives the correct `Context`.
- Type-check sanity: `mypy` / `pyright` run clean against the updated `Strategy.evaluate` signature in [strategies/base.py](src/ascent/strategies/base.py) and the example [strategy.py](strategy.py).

### Phase 3 — Exchange-side order rejection

**Files**
- [src/ascent/domain/](src/ascent/domain/) — add `TradeState.REJECTED` as a terminal state. Update any terminal-state helpers (`is_terminal`).
- [src/ascent/application/route_trade.py](src/ascent/application/route_trade.py) —
  - `TradeRouter.__init__` gains a `route_gate: RouteGate` dep. Gate is constructed with the exchange bindings and a strategy repo.
  - In `submit` ([line 101](src/ascent/application/route_trade.py#L101)), call `gate.validate(instrument_ids, exchange_id, strategy_id)` before building `leg_specs`. On failure, write a single `Trade` row with `state=REJECTED`, `close_reason="UNIVERSE_SCOPE:<reason>"`, no legs, commit, return `TradeDraft(state=REJECTED, ...)`.
  - For composite trades, validate every leg's type pairing; if any fails, reject the entire composite as one `REJECTED` trade row (atomic — no partial fills).
  - For `close`: skip the gate entirely.
- [src/ascent/adapters/sqlalchemy/](src/ascent/adapters/sqlalchemy/) — repo method to load `(StrategyExchange.is_active, Strategy.is_paused)` and exchange `(provider_id, instrument_type_id)` pairs. Cached per (strategy, exchange) tuple at router init; per-tick re-read isn't required because edits to `StrategyExchange.is_active` / `Strategy.is_paused` go through Phase 3.5 endpoints that broadcast cache invalidations (or, simpler v1: re-read on every `submit` — submit is rare relative to evaluate ticks).
- [src/ascent/engine/runner.py](src/ascent/engine/runner.py) — wire the gate in `_start_strategy` ([line 430](src/ascent/engine/runner.py#L430)) when constructing `TradeRouter`.

**Gate behavior** (opens only; `close()` bypasses all gates)
```
type_gate(instrument, exchange):
    instrument.(provider_id, instrument_type_id) == exchange.(provider_id, instrument_type_id)

assignment_gate(strategy, exchange):
    StrategyExchange(strategy, exchange).is_active AND not Strategy(strategy).is_paused
```

**Tests**
- Unit on the gate: type mismatch rejects; empty scope passes; scoped miss rejects; scoped hit passes.
- Integration: strategy calls `open_trade(<out-of-universe>)` → `TradeDraft.state == REJECTED`, one `Trade` row, no `Order` rows, no outbox entry.
- UI smoke: the rejected trade surfaces in the trades table with `close_reason` visible.

### Phase 3.5 — Impact-check + disable flow

The schema + API + UI for disabling items and blocking destructive deletes.

**Schema**
- Alembic migration adds `is_active BOOLEAN NOT NULL DEFAULT TRUE` to five tables: `StrategyInstrumentScope`, `StrategyCompositeScope`, `StrategyExchange`, `FeedInstrumentScope`, `FeedCompositeScope`. Existing rows backfill to `true`.
- Same migration adds `is_paused BOOLEAN NOT NULL DEFAULT FALSE` to the `Strategy` table.
- The two `Exchange*Scope` tables don't gain the column — they're deprecated by Phase 0 and ignored at runtime.

**Files (backend)**
- [src/ascent/database/models/strategy.py](src/ascent/database/models/strategy.py), [feeds.py](src/ascent/database/models/feeds.py) — add `is_active` to the relevant ORM models. Add `is_paused` to the `Strategy` model.
- [src/ascent/server/services/universe_service.py](src/ascent/server/services/universe_service.py) — new module-level helpers:
  - `compute_strategy_universe_impact(db, strategy_id, instrument_id) -> ImpactReport`
  - `compute_strategy_composite_impact(...)`, `compute_strategy_exchange_impact(db, strategy_id, exchange_id)`
  - `compute_feed_universe_impact(db, feed_id, instrument_id)` (+ composite variant)
  - Each returns `(can_remove, reasons, blocking_trades, blocking_scope_items, suggested_action)`.
- Existing `remove_*` helpers call the impact function first and raise `ConflictError` (new 409 exception) with the payload when blocked.
- New `set_*_active(db, ..., is_active: bool)` helpers for the disable/enable transition. **For feed scope**, `set_feed_universe_item_active(..., is_active=false)` runs an additional guard: reject if any strategy that uses this feed has a non-terminal trade on the instrument (open positions need price data to exit). The guard returns the same `ConflictError` payload structure so the UI can surface it identically.
- New `set_strategy_paused(db, strategy_id, is_paused: bool)` helper. No guard — pausing is always allowed. Internally it just flips `Strategy.is_paused`; the runtime gate picks it up on next `submit`.
- [src/ascent/server/routers/strategies.py](src/ascent/server/routers/strategies.py), [feeds.py](src/ascent/server/routers/feeds.py) — wire up:
  - `GET /strategies/{id}/universe/{instrument_id}/impact`
  - `PATCH /strategies/{id}/universe/{instrument_id}` body: `{"is_active": false}`
  - `GET /strategies/{id}/exchanges/{exchange_id}/impact`
  - `PATCH /strategies/{id}/exchanges/{exchange_id}` body: `{"is_active": false}`
  - `PATCH /strategies/{id}/pause` body: `{"is_paused": true}` (or `false` to resume).
  - `GET /feeds/{id}/universe/{instrument_id}/impact`
  - `PATCH /feeds/{id}/universe/{instrument_id}` body: `{"is_active": false}`
  - Same pairs for composite variants across strategies and feeds.
  - Existing DELETE endpoints return 409 with the impact payload on conflict.
- [src/ascent/server/schemas/universe.py](src/ascent/server/schemas/universe.py) — add `ImpactReport`, `BlockingTrade`, `BlockingScopeItem` Pydantic models; extend `UniverseItemSchema` / `CompositeUniverseItemSchema` with `is_active: bool`. Extend `StrategySchema` with `is_paused: bool`.

**Files (frontend)**
- [src/ascent/ui/src/app/components/shared/universe-panel.component.ts](src/ascent/ui/src/app/components/shared/universe-panel.component.ts) — extend the row renderer:
  - Add a status badge (Active / Disabled).
  - Replace the single Remove action with a split: Disable/Enable toggle + Remove.
  - On Remove click, call the impact endpoint; open `<universe-impact-dialog>` with the payload.
- New component: `UniverseImpactDialogComponent` — PrimeNG `p-dialog` showing:
  - Summary (`N open trades`, `M dependent universe items`).
  - Lists of blocking trades (linking to trade detail) and blocking scope items (linking to the relevant detail page).
  - Primary action is either "Remove" (can_remove: true), "Disable" (can_remove: false, user hasn't disabled yet), or "OK" (can_remove: false and already disabled — user must clear blockers).
- Equivalent integration in the Exchanges tab of the strategy detail page (and the feed detail Universe tab).
- **Strategy header pause toggle.** Add a Pause/Resume button to [src/ascent/ui/src/app/components/strategies/strategy-detail/strategy-detail.component.ts](src/ascent/ui/src/app/components/strategies/strategy-detail/strategy-detail.component.ts). When paused, surface a banner across the page: "Strategy is paused — new trades blocked, open trades will exit normally." Pausing is one click with no confirmation modal (it's reversible).
- Services: `strategy.service.ts`, `feed.service.ts` gain `getUniverseItemImpact`, `setUniverseItemActive`, equivalents for composites + strategy-exchange assignments. Add `setStrategyPaused(id, is_paused)` to `strategy.service.ts`.

**Runtime integration**
- Phase 1's `get_universe()` filters by `is_active` (disabled feed-scope items stop being fetched).
- Phase 2's per-tick scope re-read filters by `is_active`.
- Phase 3's gates read `is_active` on `ExchangeInstrumentScope` and `StrategyExchange`.
No additional runtime work beyond what those phases land.

**Tests**
- Service unit tests for each `compute_*_impact` function covering: open-trade block, orphan-universe block, no-block happy path.
- Router contract tests:
  - DELETE with open trade → 409 + payload
  - PATCH `is_active: false` succeeds even with open trades
  - DELETE after disable + trade closure → 200
- UI smoke: click Remove on an item with open trades → dialog appears, Delete is disabled, Disable is primary.

### Phase 4 — Write-time drift validation

**Files**
- [src/ascent/server/services/universe_service.py](src/ascent/server/services/universe_service.py) —
  - Extend `_validate_instruments_tradeable` to also require the instrument be in the union of the strategy's feeds' scopes. Currently only exchange pairs are checked ([lines 32-70](src/ascent/server/services/universe_service.py#L32-L70)).
  - Add equivalent validation to `add_feed_universe_item` / `batch_add_feed_instruments` ([line 224](src/ascent/server/services/universe_service.py#L224), [line 255](src/ascent/server/services/universe_service.py#L255)): reject feed-scope adds where the instrument's `(provider_id, instrument_type_id)` doesn't match the feed's declared type. Currently no validation at all.
- [src/ascent/server/routers/](src/ascent/server/routers/) — no router changes; validation propagates through the existing `BadRequestError` path.

**Tests**
- Contract: adding to strategy universe with an instrument not in any linked feed's scope → 400.
- Contract: adding to feed universe with an instrument of mismatched type → 400.

### Phase 5 — UI polish

Phase 3.5 landed the bulk of the UI (disable toggle, impact dialog, pause toggle). This phase covers the loose ends:

**Files**
- [src/ascent/ui/src/app/components/strategies/strategy-detail/strategy-detail.component.ts](src/ascent/ui/src/app/components/strategies/strategy-detail/strategy-detail.component.ts) — surface write-time drift errors from the universe endpoints verbatim (strings come through `BadRequestError` from Phase 4).
- Trade table — add a `REJECTED` status badge + colour variant in [trade-table.component.ts](src/ascent/ui/src/app/components/trade-table/trade-table.component.ts). Ensure `close_reason` renders the structured `UNIVERSE_SCOPE:*` codes readably (map to friendly text: "Provider mismatch", "Strategy paused", "Exchange assignment disabled", etc.).
- Strategy detail "Universe" tab — show a hint when the strategy's active universe could be expanded (e.g. instruments matching the strategy's exchanges and feeds that haven't been added yet).
- Disabled row styling — greyed-out text + "Disabled" badge in the strategy and feed universe panels, consistent with PrimeNG disabled-state conventions.

### Phase 6 — Startup reconciliation (optional, stretch)

On engine boot, walk each strategy's scope rows; if any instrument is no longer in the intersection of linked exchange + feed scopes, mark the scope row's `is_active=false` and log one line per drifted item. (Requires adding an `is_active` column to the scope tables; low priority — skip unless drift shows up in practice.)

---

## Migration impact

- **New `TradeState.REJECTED`**. Code-only; no schema change (state is a string in the DB).
- **No new tables.**
- **Alembic migration (Phase 3.5)** adds:
  - `is_active BOOLEAN NOT NULL DEFAULT TRUE` to: `strategy_instrument_scope`, `strategy_composite_scope`, `strategy_exchange`, `feed_instrument_scope`, `feed_composite_scope`.
  - `is_paused BOOLEAN NOT NULL DEFAULT FALSE` to `strategy`.
  - All existing rows backfill to safe defaults. No data loss, no app downtime.
- **Phase 0 migration drops** `exchange_instrument_scope` and `exchange_composite_scope` tables outright. Forward-only; downgrade is intentionally empty. The current data isn't migrated anywhere — exchange admissibility is now type-only.

---

## Rollout order

1. **Phase 0** (deprecate exchange-side scope) — delete-only; no new behavior. Smallest possible PR, lands first.
2. **Phase 3.5a — schema only** (Alembic migration adding `is_active` and `is_paused`). Ship next; no behavior change. Unblocks everything that follows.
3. **Phase 4** (drift validation) — server-only; catches bad config before runtime wiring.
4. **Phase 1** (feed runtime) — decoupled; validate with the OU feed.
5. **Phase 2** (strategy context filtering, `is_active`-aware) — depends on Phase 1 for a realistic end-to-end test.
6. **Phase 3** (exchange order-routing gate, pause-aware + close-exempt) — user-visible rejections start here.
7. **Phase 3.5b — impact + disable endpoints + UI + pause toggle** — ships after Phases 1–3 so the rejection/disable story is coherent end-to-end.
8. **Phase 5** (UI polish) — rejection badges, drift hints, disabled-row styling.
9. **Phase 6** (startup reconciliation) — only if drift shows up in practice.

---

## Open questions

Resolved:
- **Live scope reloads** → re-read scope at the top of each tick (Phases 1 and 2). Cheap query, immediate phase-out.
- **Empty exchange scope** → moot. Exchanges no longer have a configurable scope.
- **Feed-level disable** → built fully in Phase 3.5 with the open-trade guard preventing disable while a dependent position exists.
- **Close-path failures** → `close()` bypasses every gate; the trade itself is proof the routing was previously valid. Genuine API failures surface through the normal fill-error path.
- **Composite atomicity** → reject the entire composite if any leg fails the type gate. No partial fills.
- **All-rows-disabled** → moot (no exchange scope).
- **Bulk disable** → strategy-level pause toggle (`Strategy.is_paused`) instead of per-tab bulk action. One switch on the strategy detail page disables all new opens; per-item disable remains for finer phase-out.
- **Per-exchange instrument universe** → removed. Exchange admissibility is type-only.

Still open:
- *(none — all design questions resolved.)*
