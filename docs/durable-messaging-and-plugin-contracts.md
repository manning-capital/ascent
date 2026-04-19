# Durable Messaging & Plugin Contracts — Design Doc

**Status:** Design phase, not yet implemented. Decisions recorded; code follows.
**Last updated:** 2026-04-16

## Context

Ascent currently uses Redis pub/sub for the engine's event bus ([src/ascent/ports/event_bus.py](../src/ascent/ports/event_bus.py), [src/ascent/adapters/redis_asyncio.py](../src/ascent/adapters/redis_asyncio.py)). That gives at-most-once, lossy delivery — fine for feed wake-ups and UI pings, unsafe for real-money flows (order dispatch, fill handling) where a dropped event means position desync or double-submitted orders.

This doc captures the end-to-end design for:
1. **Durable messaging** for money-affecting channels (outbox → NATS JetStream).
2. **Plugin contracts** (`BaseExchange`, `Strategy`, `Feed`) that keep infrastructure concerns out of user-authored code.

Scope boundary: feed and UI channels stay on Redis pub/sub. Only dispatch and fill channels need durability.

---

## Key decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | Use **transactional outbox** pattern, not direct broker publish | Solves the DB-vs-queue dual-write problem. Broker alone can't. |
| 2 | Add **NATS JetStream** on top of the outbox | Broker provides consumer groups, acks, DLQ, replay — all of which we'd otherwise hand-roll. |
| 3 | Outbox table is a **TimescaleDB hypertable** | Constant-time purge via `drop_chunks`, reuses existing infra. |
| 4 | Retention is **consumer-guarded**, not wall-clock | Chunks drop only after every cursor has passed + grace period. Disk alarms also alert us to stuck consumers. |
| 5 | `OrderStatus` is a **platform-owned enum**; plugins map broker values to it | Platform must reason about trade state without broker-specific knowledge. |
| 6 | Error classification via plugin-side `classify_error(exc) → ExchangeErrorKind` method | Plugins don't import platform exceptions; SDK errors bubble through as-is. |
| 7 | `IdempotencyCapability` is a **class hierarchy**, not an enum | Carries both the tier label and its parameters (max_length, lifetime, scope). |
| 8 | **Platform** generates `client_order_id`, not plugins | Plugin shape constraints declared via `client_id_format`; platform produces IDs that fit. |
| 9 | Fee endpoints on plugin (`get_trading_fee`, `get_funding_fee`, `get_borrow_fee`) | Feeds PnL calc; funding/borrow matter for shorts/perps held overnight. |
| 10 | Rate limits declared on plugin, enforced via **Redis token bucket** in platform | Per-account, shared across processes. Plugins don't handle limits. |

---

## Architecture overview

Three layers, strict separation:

```
┌────────────────────────────────────────────────────────────────┐
│ PLUGIN SURFACE (user-authored)                                 │
│   BaseExchange  Strategy  Feed                                 │
│   — domain logic only, no infra awareness                      │
└────────────────────────────────────────────────────────────────┘
                             ↕ declarations + abstract methods
┌────────────────────────────────────────────────────────────────┐
│ PLATFORM (library code)                                        │
│   Outbox relay • Idempotency wrappers (Tier 1/2/3)             │
│   Rate limiter • Unit of Work • Dispatcher • Fee scheduler     │
│   Consumer framework • Audit • Retry / DLQ                     │
└────────────────────────────────────────────────────────────────┘
                             ↕
┌────────────────────────────────────────────────────────────────┐
│ INFRASTRUCTURE                                                 │
│   Postgres/TimescaleDB • Redis • NATS JetStream                │
└────────────────────────────────────────────────────────────────┘
```

**Litmus test** for any new design: *"would a plugin author have to care about this?"* If yes, it's leaked into the wrong layer.

---

## Durable messaging

### The dual-write problem

Without an outbox:
1. Exchange receives fill
2. Write fill to Postgres ✅
3. Publish event to bus ❌ (crash, network blip)

→ DB and downstream consumers desynced. No broker — Kafka, NATS, RabbitMQ — fixes this on its own. The DB write and the event write must be in the **same transaction**.

### Outbox schema

```python
class EventOutbox(Base):
    __tablename__ = "event_outbox"
    id: Mapped[int] = mapped_column(BigInteger, autoincrement=True)
    created_at: Mapped[datetime]  # hypertable partitioning column
    channel: Mapped[str]          # "ascent.exchange.<uuid>" etc.
    subject: Mapped[str]          # JetStream subject
    payload: Mapped[dict]         # JSONB
    __table_args__ = (
        PrimaryKeyConstraint("id", "created_at"),
        Index("idx_event_outbox_channel_time", "channel", "created_at", "id"),
    )
```

Hypertable setup at startup:
```sql
SELECT create_hypertable('event_outbox', by_range('created_at', INTERVAL '1 day'), if_not_exists => TRUE);
```

### Consumer cursor schema (only if not using JetStream durable consumers)

If JetStream is in the picture, **skip this table** — JetStream tracks consumer cursors natively. Keep the table only for non-broker consumers that poll the outbox directly (feed/UI tier, if we ever route those through the outbox).

```python
class EventCursor(Base):
    __tablename__ = "event_cursor"
    consumer_name: Mapped[str]
    channel: Mapped[str]
    last_event_id: Mapped[int]
    last_event_created_at: Mapped[datetime]
    # PK (consumer_name, channel)
```

### Publisher flow

Publishers write business data + outbox row in **one** SQLAlchemy transaction:

```python
async with unit_of_work() as session:
    trade_repo.create(session, trade)
    order_repo.create(session, order)
    outbox.enqueue(session, channel="ascent.exchange.kraken", subject="...", payload={...})
# Commit here — all four writes are atomic.
```

### Relay → JetStream

Single relay process polls outbox with `FOR UPDATE SKIP LOCKED`, publishes to JetStream with `Nats-Msg-Id: <outbox.id>` for dedup (2-minute window), marks rows relayed.

```python
rows = session.execute(
    select(EventOutbox)
    .where(EventOutbox.created_at < func.now() - text("interval '100 ms'"))  # commit-visibility lag
    .with_for_update(skip_locked=True)
    .limit(100)
).scalars().all()

for row in rows:
    await js.publish(row.subject, row.payload_bytes, headers={"Nats-Msg-Id": str(row.id)})

# Mark relayed (or delete, depending on audit policy — see §Retention)
```

### Consumer flow (JetStream durable consumers)

Consumers subscribe to a JetStream stream with a durable consumer name. JetStream handles cursor, redelivery on `ack_wait` timeout, DLQ via `max_deliver`. Consumer code:

```python
async for msg in durable_consumer:
    try:
        await process(msg)       # includes idempotent DB writes
        await msg.ack()
    except RetriableError:
        await msg.nak()          # redelivered after ack_wait
    except PermanentError:
        await msg.term()         # goes to DLQ stream
```

### Retention (consumer-guarded)

Chunks drop only when every registered consumer cursor has passed:

```python
async def drop_consumed_chunks(session):
    # Minimum progress across all JetStream consumers on the streams we care about
    min_id = min_consumer_position_across_streams()
    min_created_at = session.execute(
        select(EventOutbox.created_at).where(EventOutbox.id == min_id)
    ).scalar_one_or_none()
    if min_created_at:
        session.execute(text(
            "SELECT drop_chunks('event_outbox', older_than => :ts)"
        ), {"ts": min_created_at - timedelta(days=2)})  # grace
```

A stuck consumer → disk grows → natural alarm.

### Key guarantee: at-least-once

JetStream redelivery means consumers may see the same message twice. Every consumer handler must be idempotent. For the dispatcher specifically, this requires broker-side idempotency — see below.

---

## Idempotency tiers

### Why tiers exist

At-least-once + exchange APIs = "submit an order, crash before ack, replay submits a second order." The only safe fix is a **broker-side client order ID**. Different brokers support this differently.

### Tier 1 — Native string client ID (clean)

| Broker | Field | Notes |
|---|---|---|
| Binance / Binance.US | `newClientOrderId` | 36-char limit |
| Coinbase Advanced | `client_order_id` | Returns existing on duplicate |
| KuCoin | `clientOid` | UUID-friendly |
| Bybit | `orderLinkId` | 36-char |
| OKX | `clOrdId` | 32-char alphanumeric |
| Gemini | `client_order_id` | Unique forever |
| Crypto.com | `client_oid` | Clean |
| HTX (Huobi) | `client-order-id` | Clean |
| MEXC | `newClientOrderId` | Clean |
| Alpaca | `client_order_id` | Clean |

**Pattern:** platform submits with `client_order_id=str(order.id)`. On duplicate error, platform calls plugin's `get_order_by_client_id(...)` and uses the existing record.

### Tier 2 — Integer counter

| Broker | Field | Quirk |
|---|---|---|
| Interactive Brokers | `orderId` | Session-scoped int; `reqIds()` on reconnect |
| Bitfinex | `cid` | int64, day-scoped |
| dYdX v4 | `clientId` | uint32 |

Platform maintains a mapping table:

```sql
CREATE TABLE broker_client_id (
    broker TEXT NOT NULL,
    order_id UUID NOT NULL,
    client_int BIGINT NOT NULL,
    PRIMARY KEY (broker, order_id),
    UNIQUE (broker, client_int)
);
```

Mapping is **committed before submit** — if we crashed after submit-to-broker but before writing the mapping, replay would allocate a second int and double-submit.

### Tier 3 — No client-id idempotency (dangerous)

| Broker | Why it fails |
|---|---|
| Kraken's old `userref` | int32 **not unique**. (Kraken now also has `cl_ord_id` on WS v2 — see Kraken notes below.) |
| TD Ameritrade / Schwab | No client-idempotency field on order entry |
| E*TRADE | Same |
| Tradier | Tag field, no dedup enforcement |

**Policy:** Tier 3 brokers are **manual-approval only** — no auto-dispatch. If forced to use one, platform uses `pg_advisory_xact_lock` + pre-submit scan + broker `exchange_order_id` guard in our DB. Still has a small residual race window (submit timeout + recovery scan returning stale). Not absolute-money safe.

### Kraken — special case worth naming

Kraken's current WebSocket v2 `add_order` supports `cl_ord_id` (up to 18 chars or 32-hex UUID) that "uniquely identifies an **open** order." This moves Kraken from Tier 3 → "Tier 1 with caveats":

- **Use WS v2** (not REST) for submission — better documented cl_ord_id behavior.
- **Lifetime gotcha:** "uniquely identifies an open order" suggests the ID may be reusable after fill/cancel. Declared via `lifetime="open_only"` on the plugin's `IdempotencyCapability`.
- **Lookup must search both open and closed** orders (`query_open_orders` + `query_closed_orders`).
- **DB guard on `exchange_order_id`** is load-bearing, not decorative.

Verify in sandbox before live: (1) duplicate `cl_ord_id` rejection behavior, (2) reusability after fill, (3) REST parity with WS v2.

---

## Plugin contract: `BaseExchange`

### Final shape

```python
class BaseExchange(ABC):
    # --- Class-level declarations (platform reads these) ---
    idempotency: ClassVar[IdempotencyCapability]
    supported_order_types: ClassVar[frozenset[OrderType]]
    supported_tif: ClassVar[frozenset[TimeInForce]]
    rate_limits: ClassVar[list[RateLimit]]
    poll_interval: ClassVar[float] = 1.0
    # existing metadata
    provider: ClassVar[str | None]
    instrument_type: ClassVar[str | None]
    display_name: ClassVar[str | None]
    description: ClassVar[str | None]

    # --- Required methods ---
    @abstractmethod
    def submit_order(self, request: OrderRequest) -> OrderResponse: ...
    @abstractmethod
    def cancel_order(self, exchange_order_id: str) -> OrderResponse: ...
    @abstractmethod
    def get_order_status(self, exchange_order_id: str) -> OrderStatusResponse: ...
    @abstractmethod
    def get_balances(self) -> list[BalanceEntry]: ...
    @abstractmethod
    def get_order_by_client_id(self, client_order_id: str) -> OrderStatusResponse | None: ...
    @abstractmethod
    def get_trading_fee(self, request: OrderRequest) -> FeeQuote: ...

    def classify_error(self, exc: Exception) -> ExchangeErrorKind:
        return ExchangeErrorKind.UNKNOWN

    # --- Optional overrides ---
    def get_open_orders(self) -> list[OrderStatusResponse]:
        raise NotImplementedError
    def connect_order_stream(self, shutdown: threading.Event) -> Iterator[OrderEvent]:
        raise NotImplementedError
    def get_funding_fee(self, symbol, notional, side, as_of) -> FeeQuote | None:
        return None
    def get_borrow_fee(self, symbol, notional, as_of) -> FeeQuote | None:
        return None
    def on_start(self) -> None: ...
    def on_stop(self) -> None: ...
```

### Supporting types

#### `OrderStatus` (canonical, platform-owned)

```python
class OrderStatus(str, Enum):
    PENDING = "PENDING"                  # pre-submit, in our queue
    ACCEPTED = "ACCEPTED"                # broker acknowledged
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
```

Plugin returns canonical values; broker-specific mapping lives in the plugin.

#### `ExchangeErrorKind`

```python
class ExchangeErrorKind(Enum):
    DUPLICATE_CLIENT_ID = "DUPLICATE_CLIENT_ID"
    RATE_LIMITED        = "RATE_LIMITED"
    INSUFFICIENT_FUNDS  = "INSUFFICIENT_FUNDS"
    INVALID_ORDER       = "INVALID_ORDER"       # → DLQ, don't retry
    TRANSIENT           = "TRANSIENT"           # → retry with backoff
    UNKNOWN             = "UNKNOWN"             # → retry conservatively
```

#### `IdempotencyCapability` (sealed class hierarchy)

```python
class IdempotencyCapability:
    """Base marker. Platform dispatches on concrete subclass."""

class NativeClientId(IdempotencyCapability):
    def __init__(self, *, max_length: int,
                 charset: Literal["ascii", "hex", "uuid"],
                 lifetime: Literal["forever", "open_only", "ttl"]):
        ...

class IntCounter(IdempotencyCapability):
    def __init__(self, *, scope: Literal["account", "session", "day"],
                 min_value: int, max_value: int):
        ...

class PreSubmitScan(IdempotencyCapability):
    def __init__(self, *, tag_field: str | None = None):
        ...
```

**Example declarations:**

```python
class AlpacaExchange(BaseExchange):
    idempotency = NativeClientId(max_length=48, charset="ascii", lifetime="forever")

class KrakenExchange(BaseExchange):
    idempotency = NativeClientId(max_length=18, charset="hex", lifetime="open_only")

class IBKRExchange(BaseExchange):
    idempotency = IntCounter(scope="session", min_value=1, max_value=2**31 - 1)
```

#### `OrderType` / `TimeInForce` (union across brokers)

```python
class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    STOP_LIMIT = "STOP_LIMIT"
    TRAILING_STOP = "TRAILING_STOP"
    TRAILING_STOP_LIMIT = "TRAILING_STOP_LIMIT"
    OCO = "OCO"
    BRACKET = "BRACKET"
    OTO = "OTO"
    ICEBERG = "ICEBERG"
    TWAP = "TWAP"
    VWAP = "VWAP"

class TimeInForce(str, Enum):
    GTC = "GTC"
    GTD = "GTD"
    DAY = "DAY"
    IOC = "IOC"
    FOK = "FOK"
    POST_ONLY = "POST_ONLY"
```

Platform pre-flight-validates every `OrderRequest` against the plugin's `supported_order_types` / `supported_tif`. Rejects before the broker is hit.

#### `RateLimit`

```python
@dataclass(frozen=True)
class RateLimit:
    endpoint: str              # "submit_order" | "cancel_order" | "*"
    weight: float = 1.0
    capacity: int              # burst
    refill_per_second: float   # steady state
```

Enforced via Redis token bucket (Lua script for atomicity). Key: `ratelimit:{exchange_db_id}:{endpoint}` — **exchange DB record id, not class** (rate limits are account-scoped; two accounts on the same broker each get their own budget).

#### `FeeQuote`

```python
@dataclass(frozen=True)
class FeeQuote:
    fee_asset: str               # "USD", "USDT", "BTC"
    fee_amount: float
    fee_rate: float | None       # effective bps, for reporting
    source: Literal["static", "api_quote"]
```

Feeds into PnL:
```
At fill:              realized_pnl -= get_trading_fee(...)
At funding cycle:     realized_pnl -= get_funding_fee(...)   # perps, recurring
At daily close:       realized_pnl -= get_borrow_fee(...)    # spot shorts
```

Funding and borrow fee loops are **platform-scheduled jobs** — plugin just answers "how much?" when asked.

---

## Platform responsibilities

The platform provides (none of this is visible in plugin code):

| Concern | Platform component |
|---|---|
| Outbox writes during business txn | `OutboxPublisher` port, `SqlAlchemyOutboxPublisher` adapter |
| Relay outbox → JetStream | Long-running background task, `FOR UPDATE SKIP LOCKED` |
| Dispatcher with idempotency wrapping | `ExchangeAdapter` — reads `IdempotencyCapability` from plugin, applies right strategy |
| Int-counter mapping for Tier 2 | `broker_client_id` table + repo |
| Rate limiting | Redis token bucket, wraps every SDK call |
| Error classification → retry/DLQ routing | Platform calls plugin's `classify_error`, maps to behavior |
| Order-type pre-flight validation | Before `submit_order`, check declared `supported_order_types` |
| Funding / borrow fee scheduling | Per-broker cadence job, calls plugin's `get_funding_fee` / `get_borrow_fee` |
| Consumer framework (retry, ack, DLQ) | JetStream durable consumers |
| Audit trail | JetStream stream with 30+ day retention, or separate `event_audit` table (TBD) |
| Run tracking, heartbeats | Existing `FeedRun` / `StrategyRun` tables + `HeartbeatStore` |
| Unit of Work | New context manager; refactor existing repos to accept `Session` param |

---

## Plugin contracts: `Strategy` and `Feed` (TBD)

Not yet designed. Same principle applies: domain logic only, no infra awareness. Existing [src/ascent/strategies/base.py](../src/ascent/strategies/base.py) and [src/ascent/feeds/base.py](../src/ascent/feeds/base.py) are the starting points — same refinement exercise as `BaseExchange` will produce their final contracts.

Placeholder rough shapes:

```python
class Strategy(ABC):
    feeds: ClassVar[list[str]]
    @abstractmethod
    def evaluate(self, context: StrategyContext) -> list[TradeSignal]: ...

class Feed(ABC):
    schedule: ClassVar[Schedule]
    output_schema: ClassVar[Schema]
    @abstractmethod
    def fetch(self, params: FeedParams) -> pd.DataFrame: ...
```

Full designs pending.

---

## Open questions

1. **Audit log**: separate immutable `event_audit` table, or rely on JetStream stream + 90-day outbox retention? Decide based on regulatory/forensic requirements.
2. **Multi-replica consumers**: single-process engine today; when we scale out, consumer framework needs leader election or partition-by-key for exclusive consumers (dispatcher), and broadcast for non-exclusive (UI, audit).
3. **Strategy and Feed contracts**: not yet refined. Same exercise as `BaseExchange` pending.
4. **Kraken sandbox validation**: before first live money flow, run the three-test probe for `cl_ord_id` behavior (duplicate, lifetime, REST parity). See [kraken-api-integration.md](./kraken-api-integration.md) for the full research brief and manual test plan (§5.C.6, §5.C.10, §5.C.11, §5.D.7 are the probes that resolve this question).
5. **Credentials management**: today `config` JSONB on Exchange record holds API keys; rotation / env-var fallback not yet designed.

---

## Rollout plan

1. Add `event_outbox` table + `OutboxPublisher` port/adapter. No behavior change yet.
2. Introduce `UnitOfWork` context manager; migrate existing repos to accept `Session` param.
3. Add NATS JetStream service; stream provisioning at startup.
4. Write relay process (outbox → JetStream).
5. Refine `BaseExchange` contract — add declarations, canonical enums.
6. Migrate existing Kraken / Coinbase / Paper exchanges to new contract.
7. Implement idempotency wrapping in `ExchangeAdapter` — Tier 1 first.
8. Switch dispatch (`ascent.exchange.*`) off Redis pub/sub → JetStream. Paper-trade for a week.
9. Switch fills (`ascent.exchange.*.responses`) off Redis pub/sub → JetStream. Paper-trade.
10. Add Tier 2 support (`broker_client_id` table, IBKR adapter).
11. Rate limiter. Fee scheduling. Audit table (if needed).
12. Refine `Strategy` and `Feed` contracts.
13. Feed + UI channels stay on Redis pub/sub indefinitely unless requirements change.

---

## Appendix: channel tier summary

| Channel | Money impact | Infra | Durability |
|---|---|---|---|
| `ascent.exchange.{id}` (dispatch) | Direct | Outbox → JetStream | Absolute |
| `ascent.exchange.{id}.responses` (fills) | Direct | Outbox → JetStream | Absolute |
| `ascent.feed.{uuid}` | None (replayable) | Redis pub/sub | At-most-once OK |
| `ascent.trades.updates` (UI) | None | Redis pub/sub | At-most-once OK |
