# Feed Partitions → Runs Refactor

**Status:** Scoped, awaiting implementation
**Motivation:** Map feed data at time T to the trades made by strategies as a result of that data. `FeedPartition` is a middleman that isn't on this chain; its grid goes stale on schedule changes; its status duplicates `FeedRun.status`.

## Decision Summary

Drop `FeedPartition` entirely. Move the snapshot timestamp onto `FeedRun` as the primary data identity. The provenance chain becomes `Trade → StrategyRun → StrategyRunFeedRun → FeedRun → output rows`.

User-approved decisions:

- **Gap detection UX:** drop entirely. Backfill becomes an explicit CLI/API action (no persistent "PENDING partition" concept).
- **Migration:** wipe and rebuild in dev. No Alembic migration — one `docker compose down -v && docker compose up -d` once merged.
- **Trade↔FeedRun UI:** include in this PR. The user-visible payoff ships with the plumbing.

## Key Audit Findings

- EAV upsert dedup is `(timestamp, entity_id, attribute_id)` — `FeedPartition` is not in the idempotency path ([timescale_feed_store.py:63](../src/ascent/adapters/timescale_feed_store.py#L63)).
- `partition_key_for`, `partition_window` are pure math — stay (renamed).
- `find_gaps` / `generate_keys` only called from the UI list endpoint, never the live path.
- **Live-path bug discovered during scoping:** `strategy_run_repo.link_feed_runs` is declared ([trade_repo.py:150](../src/ascent/ports/trade_repo.py#L150)) and implemented ([strategy_run_repo.py:29](../src/ascent/adapters/sqlalchemy/strategy_run_repo.py#L29)), but **no caller exists** in the engine path. `StrategyRunFeedRun` rows are never written today, so the "which trades came from this feed run" chain is dead schema. Phase 2 fixes this.

## Scope

### Phase 1 — schema + engine core

- `FeedRun`: add `snapshot_timestamp` NOT NULL, drop `partition_id` column + FK
- Delete: `FeedPartition` model, `PartitionRepository` port, `SqlAlchemyPartitionRepository` adapter, `PartitionInfo`, `partition_window`, `find_gaps`, `generate_keys`, `_current_partition` contextvar
- Rename `partition_key_for` → `snapshot_timestamp_for`
- `FeedExecutor.execute()` computes snapshot inline, passes to `track_feed_run` at create time
- Delete `FeedRunRepository.link_partition` + `RunTrackerPort.link_feed_run_partition` (yesterday's post-hoc backfill — now unnecessary since we know the snapshot before creating the run)
- Event bus payload: `partition_key` → `snapshot_timestamp`; drop duplicate `timestamp` field

### Phase 2 — strategy provenance wiring (the live-path bug)

- `StrategyEvaluator._handle_event`: capture `feed_run_id` per parent feed (already in event payload, just not consumed)
- After `strategy.evaluate()` completes, call `strategy_run_repo.link_feed_runs(strategy_run_id, feed_run_ids={feed_id: run_id, ...}, trigger_feed_id=...)`
- This populates `strategy_run_feed_run` rows on every strategy tick, so the UI chain works

### Phase 3 — server API

**Delete:**
- `GET /feeds/{id}/partitions`
- `GET /feeds/{id}/partitions/{partition_id}/data`
- `POST /admin/feed-partitions`
- `FeedPartitionItem`, `FeedPartitionCreate`, `FeedPartitionSchema` Pydantic schemas
- `list_partitions`, `get_partition_data` service functions

**Add:**
- `GET /feeds/{id}/runs/{run_id}/data` — query `WHERE timestamp = run.snapshot_timestamp` on output table, pivot same way as old partition-data endpoint
- `GET /feeds/{id}/runs/{run_id}/trades` — joins `feed_run → strategy_run_feed_run → strategy_run → trade`
- `GET /trades/{trade_id}/feed-runs` — reverse direction; lists the feed runs the evaluating strategy run consulted

### Phase 4 — UI

**Modify:**
- [feed-run-detail.component.ts](../src/ascent/ui/src/app/components/feeds/feed-run-detail/feed-run-detail.component.ts): Partition tab → **Data** tab (calls new runs-data endpoint) + **Caused Trades** panel
- [feed-detail.component.ts](../src/ascent/ui/src/app/components/feeds/feed-detail/feed-detail.component.ts): Timeline tab becomes simple runs list (no grid)
- Trade detail component: add **Source Data** panel listing the feed runs consulted
- [feed.service.ts](../src/ascent/ui/src/app/services/feed.service.ts): drop `loadPartitions` / `loadPartitionData`; add `loadRunData`, `loadRunTrades`
- [feed.model.ts](../src/ascent/ui/src/app/models/feed.model.ts): drop `FeedPartitionItem`

**Delete:**
- [partition-timeline.component.ts](../src/ascent/ui/src/app/components/shared/partition-timeline.component.ts)

### Phase 5 — tests

**Delete:**
- All `PartitionRepository` unit tests
- `find_gaps` / `generate_keys` tests
- `tests/integration/engine/test_feed_persistence.py::test_feed_run_is_linked_to_its_partition`
- `InMemoryPartitionRepository` fake

**Update:**
- `test_feed_persistence.py` — replace `partition_id` assertions with `snapshot_timestamp`; rename UI endpoint test from `test_ui_partition_data_endpoint_sees_persisted_rows` → `test_ui_run_data_endpoint_sees_persisted_rows`
- `test_persistence_service.py` — drop `partition_key` references, use `snapshot_timestamp` field

**Add:**
- `StrategyEvaluator` populates `strategy_run_feed_run` per evaluation (catches the phase-2 bug if it ever regresses)
- `GET /trades/{id}/feed-runs` returns the source feed runs for a trade
- `GET /feeds/{id}/runs/{run_id}/trades` returns trades caused by strategies that evaluated this feed run

### Phase 6 — dev reset

- No Alembic migration
- `Base.metadata.create_all` automatically stops creating `feed_partition` table
- Once merged: `docker compose down -v && docker compose up -d`

## Estimated size

Medium-large single PR.

- Phases 1–2: highest-leverage, smallest (core engine + the provenance wiring)
- Phases 3–4: bulk of lines changed (server endpoints + UI components)
- Phase 5: mostly deletions plus two new provenance tests

## Non-goals

- No backfill tooling in this PR. "Backfill range [T1, T2]" as an explicit CLI/API is a follow-up.
- No production migration. Dev wipe only.
- No archival of existing `feed_partition` rows.
