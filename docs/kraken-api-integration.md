# Kraken API Integration — Research Brief & Manual Test Plan

**Status:** Research brief, pre-implementation.
**Last updated:** 2026-04-19
**Companion doc:** [durable-messaging-and-plugin-contracts.md](./durable-messaging-and-plugin-contracts.md) — this file resolves §Open questions #4.

---

## 0. Important methodological caveat

This brief was assembled from Kraken's publicly documented behaviour as of the assistant's knowledge cutoff (January 2026). **Live web access was unavailable during drafting**, so every concrete number (max length, rate-limit counter, fee bps, error string) below is marked **[VERIFY]** where it hasn't been confirmed against the current docs in this session. The `Manual test plan` (§5) is written so that executing it re-grounds every such value — failing a `[VERIFY]` probe is a bug in this document, not in the platform.

Authoritative sources to cross-check before implementation:

- REST API reference — `https://docs.kraken.com/api/docs/rest-api/`
- WebSocket v2 reference — `https://docs.kraken.com/api/docs/websocket-v2/`
- WS v2 `add_order` — `https://docs.kraken.com/api/docs/websocket-v2/add_order`
- WS v2 `amend_order` / `edit_order` — `https://docs.kraken.com/api/docs/websocket-v2/amend_order`
- WS v2 `cancel_order` — `https://docs.kraken.com/api/docs/websocket-v2/cancel_order`
- WS auth guide — `https://docs.kraken.com/api/docs/guides/spot-ws-auth`
- Rate-limit guide — `https://support.kraken.com/hc/en-us/articles/206548367`
- Fee schedule — `https://www.kraken.com/features/fee-schedule`
- Asset pair naming — `https://support.kraken.com/hc/en-us/articles/360001185506`
- Status/incident page — `https://status.kraken.com/`

All URLs above should be re-opened when the reader has network access; any discrepancy with this doc is the canonical answer.

---

## 1. API reference summary

### 1.1 Endpoints

| Purpose | URL | Notes |
|---|---|---|
| REST API (spot) | `https://api.kraken.com/0/public/<method>` · `https://api.kraken.com/0/private/<method>` | API key signs private methods; Nonce is a monotonic ms counter. |
| WebSocket v2 public | `wss://ws.kraken.com/v2` | Book, trades, ticker, OHLC. |
| WebSocket v2 private | `wss://ws-auth.kraken.com/v2` | `add_order`, `cancel_order`, `amend_order`, `executions`, `balances`, `open_orders`. Requires a token from `GetWebSocketsToken`. |
| Order entry (Futures) | `https://futures.kraken.com/derivatives/api/v3/` | **Out of scope** for spot adapter. Flagged here because our `KrakenSpotExchange` must not accidentally target it. |

### 1.2 Authentication

**REST.** HTTP header `API-Key: <key>`, header `API-Sign: <HMAC-SHA512(path + SHA256(nonce + postdata), base64(secret))>`, POST body includes `nonce=<ms-timestamp>`. Key permissions matter — see §1.4.

**WebSocket v2 (private).** Two-step:
1. Call REST `POST /0/private/GetWebSocketsToken`.
2. Response: `{ "result": { "token": "<15min-token>", "expires": 900 } }`.
3. Connect to `wss://ws-auth.kraken.com/v2` and include `"token": "<token>"` in every authenticated request.

Token lifetime is **15 minutes from issuance** [VERIFY]. Reusing after expiry returns an `EAPI:Invalid token` error. A single token can be used for multiple concurrent WS connections [VERIFY] — the token validates the *session*, not a specific socket. The socket itself remains open after the token's 15-minute validity as long as it was authenticated while the token was valid; private messages continue to flow until the socket is closed. [VERIFY — probe by holding a connection for >15 min while sending heartbeats.]

**Implementation note for platform.** Token refresh must be platform-managed: (a) refresh a few minutes before expiry, (b) if a WS reconnect is required, always pull a fresh token rather than reusing the last one.

### 1.3 WebSocket v2 `add_order`

Canonical request skeleton (from WS v2 docs):

```json
{
  "method": "add_order",
  "params": {
    "order_type":   "limit",
    "side":         "buy",
    "symbol":       "BTC/USD",
    "limit_price":  50000.0,
    "order_qty":    0.0001,
    "cl_ord_id":    "ascent-<uuid-no-dashes>",
    "time_in_force": "gtc",
    "post_only":    false,
    "reduce_only":  false,
    "token":        "<ws-token>"
  },
  "req_id": 12345
}
```

**`cl_ord_id` — the load-bearing field for our idempotency design:**

| Attribute | Expected value | Confidence |
|---|---|---|
| Max length | **18** plain-ASCII chars **or** a 32-hex-char UUID | [VERIFY] — design doc assumes 18/32-hex. |
| Charset | ASCII printable; hex if using UUID mode | [VERIFY] |
| Uniqueness | "Uniquely identifies an **open** order" | [VERIFY exact wording] |
| Reuse after fill | Unclear. Our `lifetime="open_only"` declaration assumes YES (reusable once terminal). | **MUST TEST** (see §5 Live Tier 0 test D). |
| Reuse after cancel | Same as above. | **MUST TEST** |
| Duplicate-while-open rejection | Expected — error code [VERIFY]. | **MUST TEST** |
| Included in responses | Echoed in `add_order` ack; appears in `executions` channel for every fill event | [VERIFY] |
| Queryable by `cl_ord_id` | WS `cancel_order` accepts it; REST `QueryOrders` may not — see §1.5 | [VERIFY] |

**Response (success):**
```json
{
  "method": "add_order",
  "req_id": 12345,
  "result": {
    "order_id": "OQCLML-BW3P3-BUCMWZ",
    "cl_ord_id": "ascent-..."
  },
  "success": true,
  "time_in": "2026-04-19T17:00:00.000Z",
  "time_out": "2026-04-19T17:00:00.010Z"
}
```

- `order_id` == `txid` in the REST world. Same string. (Kraken settled on `order_id` for WS v2; REST still calls it `txid`.) [VERIFY]
- `cl_ord_id` is echoed back; the platform persists it as `exchange_order_id`'s sibling.

**Response (failure):**
```json
{
  "method": "add_order",
  "req_id": 12345,
  "success": false,
  "error": "Cash_order_limit_exceeded"
}
```

Error strings are not fully enumerated in one place in the docs — the set evolves. See §4.

### 1.4 `cancel_order` (WS v2)

Request fields:

```json
{
  "method": "cancel_order",
  "params": {
    "order_id": ["OQCLML-BW3P3-BUCMWZ"],
    "cl_ord_id": ["ascent-..."],
    "token": "<ws-token>"
  }
}
```

Either `order_id` **or** `cl_ord_id` is accepted [VERIFY]. Both are arrays — batch cancel in one call. If both are provided, behaviour is [VERIFY — probe].

### 1.5 `amend_order` (WS v2)

Kraken renamed `edit_order` → `amend_order` in WS v2 [VERIFY]. The older REST `EditOrder` still exists and returns a **new** `txid` (amendment = cancel + re-create). WS v2 `amend_order` preserves the `order_id` [VERIFY] — this matters for our `exchange_order_id` column: if `amend_order` preserves it, we don't need to rewrite history.

Key request params:
```json
{
  "method": "amend_order",
  "params": {
    "order_id":   "OQCLML-BW3P3-BUCMWZ",
    "order_qty":  0.0002,
    "limit_price": 49000,
    "token": "<ws-token>"
  }
}
```

Can `amend_order` reference by `cl_ord_id`? [VERIFY — if yes, our lookup path simplifies.]

### 1.6 `executions` stream (WS v2 private)

Subscribe once per socket:
```json
{
  "method": "subscribe",
  "params": { "channel": "executions", "token": "<token>", "snap_orders": true, "snap_trades": true }
}
```

Emits:
- `exec_type = "new"` — order accepted.
- `exec_type = "trade"` — a fill (partial or full).
- `exec_type = "amended"` — order modified.
- `exec_type = "canceled"` — cancellation confirmed.
- `exec_type = "expired"` — TIF/GTD expiry.
- `exec_type = "status"` — status-only update.
- `exec_type = "pending_new"` / `"pending_replace"` / `"pending_cancel"` — in-flight transitions.
[VERIFY exact enum values]

Each event carries `order_id`, `cl_ord_id`, `order_status`, `exec_id`, `exec_type`, `symbol`, `order_qty`, `cum_qty`, `last_qty`, `last_price`, `avg_price`, `fee_usd_equiv`, `timestamp` [VERIFY].

**Resume semantics:** On reconnect and resubscribe, with `snap_orders=true`, Kraken sends a snapshot of all currently open orders **and** recent executions [VERIFY window — "last N minutes" or "since last sequence"]. We cannot rely on a gap-free incremental stream across reconnects — the platform must (a) resubscribe with snapshot, (b) reconcile against our own DB, (c) for anything submitted during the gap, query REST `ClosedOrders` as a backstop.

Sequence numbers: WS v2 includes `sequence` on each channel message [VERIFY]. If a gap appears, force a full resync via REST.

### 1.7 REST fallback endpoints

| Method | Path | Use |
|---|---|---|
| `AddOrder` | `POST /0/private/AddOrder` | Same order submission; supports `userref` (int32, non-unique) and — newly — `cl_ord_id` on REST [VERIFY: confirm REST now accepts `cl_ord_id`; as of mid-2024 it was WS-only, but 2025 release notes claimed REST parity]. |
| `QueryOrders` | `POST /0/private/QueryOrders` | Lookup by txid (up to 50). Accepts `userref` filter. Accepts `cl_ord_id` [VERIFY]. |
| `OpenOrders` | `POST /0/private/OpenOrders` | All currently-open orders; optional `userref` filter. |
| `ClosedOrders` | `POST /0/private/ClosedOrders` | History; paginated by `ofs`. Default window is 50 records, max 50 per page. |
| `CancelOrder` | `POST /0/private/CancelOrder` | By `txid` or `userref`. |
| `CancelAll` | `POST /0/private/CancelAll` | Nuclear option; used for shutdown-safety. |
| `CancelAllOrdersAfter` | `POST /0/private/CancelAllOrdersAfter` | "Dead-man's switch" — cancels everything if not re-armed within N seconds. Worth adopting for long-running engines. |
| `AssetPairs` | `GET /0/public/AssetPairs` | Pair metadata: `altname`, `wsname`, `pair_decimals`, `lot_decimals`, `ordermin`, `costmin`, `tick_size`, `status`. |
| `Assets` | `GET /0/public/Assets` | Asset codes (XBT, XETH, ZUSD). |
| `TradeVolume` | `POST /0/private/TradeVolume` | 30-day volume + current maker/taker fee schedule. |
| `TradesHistory` | `POST /0/private/TradesHistory` | Per-fill history — for reconciliation. |
| `Balance` | `POST /0/private/Balance` | Account balances. |

### 1.8 API-key permissions

For our adapter, the key needs:

- **Query Funds** (for `Balance`, `TradeVolume`)
- **Query Open Orders & Trades** (for `OpenOrders`, `QueryOrders`, `TradesHistory`)
- **Query Closed Orders & Trades**
- **Create & Modify Orders** (for `AddOrder`, `EditOrder`/`AmendOrder`)
- **Cancel & Close Orders** (for `CancelOrder`, `CancelAll`, `CancelAllOrdersAfter`)
- **WebSocket interface** — without this the WS token endpoint returns `EAPI:Invalid permissions`. [VERIFY exact label on dashboard]

**Do not grant** "Withdraw Funds" or "Deposit Funds" — the adapter never needs them, and keeping them off limits blast radius if the key leaks.

### 1.9 Rate limits (REST)

Counter model, **per-account**:

| Tier | Max counter | Decay | Notes |
|---|---|---|---|
| Starter | 15 | -0.33/s (full decay ≈45 s) | [VERIFY] |
| Intermediate | 20 | -0.5/s | [VERIFY] |
| Pro | 20 | -1.0/s | [VERIFY] |

Endpoint costs (each +1 unless noted):
- `AddOrder`, `CancelOrder`, `AmendOrder` — +1 [VERIFY]
- `QueryOrders`, `OpenOrders` — +1 (low)
- `ClosedOrders`, `TradesHistory` — **+2** (heavier) [VERIFY]
- Public endpoints (`AssetPairs`, etc.) — have a separate IP-based limit (~1/s) [VERIFY]

Breach response: HTTP 200 with `{"error":["EAPI:Rate limit exceeded"]}`. Kraken may also return HTTP 429 in extreme bursts — treat both as `RATE_LIMITED`.

### 1.10 Rate limits (order management — separate counter)

Kraken also maintains a **separate "order-rate" counter** that penalises rapid add/cancel churn (anti-spoofing). The cost of each action depends on age and ratio of cancels to fills. Details: [VERIFY — Kraken calls this the "Advanced Order Management" rate limit.]

Practical takeaway for us:
- For paper-style testing, stay well below 1 add/s per pair to avoid tripping this limit.
- Declare two `RateLimit` entries: one for the HTTP counter, one for the order-management counter.

### 1.11 WebSocket rate limits

- Max connections per IP: [VERIFY — historically ~150]
- Max private subscriptions per socket: no hard cap documented; practically bounded by message rate.
- Per-socket inbound rate: [VERIFY]

---

## 2. Symbol, fee, and order-type mapping

### 2.1 Symbols / pairs

Kraken has three pair-naming schemes; all three appear in different endpoints:

| Scheme | Example for BTC-USD | Where it appears |
|---|---|---|
| Kraken internal | `XXBTZUSD` | REST `AssetPairs` primary key, legacy responses |
| Altname | `XBTUSD` | REST `AddOrder` `pair` field (accepted) |
| WSName | `BTC/USD` | WebSocket v2 `symbol` field (required) |

Mapping: the `AssetPairs` endpoint returns all three per pair. Our `KrakenSpotExchange` should:
1. On startup, fetch `AssetPairs`.
2. Build a map `ascent_symbol ↔ {internal, altname, wsname}`.
3. Use `wsname` for WS, `altname` for REST submit, `internal` for matching historical records.
4. Cache the map and refresh nightly (or on `unknown pair` error).

**Asset code quirks:**
- Bitcoin = `XBT` (not `BTC`) in all Kraken endpoints except WS v2 symbols (which use `BTC`).
- USD = `ZUSD` in internal, `USD` elsewhere.
- Staked / wrapped variants: `.S` (staked), `.B` (bonded), `.F` (flex-stake), `.M` (marginable form). Our spot adapter ignores these unless explicitly configured.
- `.d` dark-pool variants exist on some pairs. [VERIFY current list of `.d` pairs — Kraken has reduced them.] Our adapter should **not** route to `.d` pairs unless the user explicitly opts in — they have different liquidity characteristics.

Canonical platform normalisation:
```
Ascent symbol: "BTC-USD"
Kraken wsname: "BTC/USD"
Kraken altname: "XBTUSD"
Kraken internal: "XXBTZUSD"
```

Unit tests should round-trip every pair in `AssetPairs` through our normaliser.

### 2.2 Asset pair metadata (from `AssetPairs`)

Important fields we must respect:

| Field | Meaning | Platform use |
|---|---|---|
| `status` | `online`, `cancel_only`, `post_only`, `limit_only`, `reduce_only`, `delisted` | If not `online`, reject submission in pre-flight. |
| `pair_decimals` | Max decimals for prices | Round `limit_price` before submit. |
| `lot_decimals` | Max decimals for quantities | Round `order_qty`. |
| `ordermin` | Minimum order size in base asset | Hard-reject below. |
| `costmin` | Minimum order cost in quote | Hard-reject below. |
| `tick_size` | Price grid | Snap `limit_price` to multiples. |
| `leverage_buy` / `leverage_sell` | Allowed leverage levels | Only relevant for margin; spot adapter ignores. |

All of these should be cached on our `Instrument` row (or a sibling metadata table) at onboarding. Re-fetch if an order is rejected with a "precision" or "min size" error.

### 2.3 Fees

Kraken maker/taker on spot (Pro tier for standard pairs, at account 30-day volume $0):

| Tier (USD 30-day vol) | Maker | Taker |
|---|---|---|
| $0 – $10K | 0.25% | 0.40% |
| $10K – $50K | 0.20% | 0.35% |
| $50K – $100K | 0.14% | 0.24% |
| $100K – $250K | 0.12% | 0.22% |
| $250K – $500K | 0.10% | 0.20% |
| $500K – $1M | 0.08% | 0.18% |
| $1M – $2.5M | 0.06% | 0.16% |
| $2.5M – $5M | 0.04% | 0.14% |
| $5M – $10M | 0.02% | 0.12% |
| $10M+ | 0.00% | 0.10% |

[VERIFY against current https://www.kraken.com/features/fee-schedule — stablecoin pairs (USDT/USDC) and "Kraken Pro" pairs use a different schedule.]

**Fetching effective fee at submit time:**

```
POST /0/private/TradeVolume
params: { pair: "XBTUSD", fee-info: true }

→ returns:
{
  "volume": "1234.56",
  "fees": { "XXBTZUSD": { "fee": "0.16", "min_fee": "0.10", "max_fee": "0.40", "tier_volume": "1000000" } },
  "fees_maker": { "XXBTZUSD": { "fee": "0.06", ... } }
}
```

Our `get_trading_fee(request)` calls `TradeVolume` and returns:
- For `LIMIT` + `POST_ONLY`: `fees_maker.<pair>.fee`
- For `MARKET`: `fees.<pair>.fee` (taker)
- For `LIMIT` without post-only: best-effort `fees_maker` (marketable limits aren't knowable pre-submit — actual fee comes from the fill event).

Cache the result for ~1 hour; tiers only change at UTC midnight when the rolling 30-day window recomputes.

**Margin fees:** opening fee 0.01–0.02% + rollover fee every 4 hours. Our spot adapter returns `get_borrow_fee = None` and `get_funding_fee = None` because we don't use margin. If/when margin is added, wire both.

### 2.4 Order type mapping

| Platform `OrderType` | Kraken `order_type` (WS v2) | Notes |
|---|---|---|
| `MARKET` | `market` | Supported. |
| `LIMIT` | `limit` | Supported. |
| `STOP_MARKET` | `stop-loss` | Supported (triggered by `trigger` param). |
| `STOP_LIMIT` | `stop-loss-limit` | Supported. |
| `TRAILING_STOP` | `trailing-stop` | Supported. |
| `TRAILING_STOP_LIMIT` | `trailing-stop-limit` | Supported. |
| `OCO` | — | **Not natively supported.** Emulated as two orders with `CancelAllOrdersAfter`-style logic — don't claim support in `supported_order_types`. |
| `BRACKET` | — | Not supported. |
| `OTO` | — | Not supported. |
| `ICEBERG` | `iceberg` | Supported; requires `display_qty` param. |
| `TWAP` / `VWAP` | — | Not supported on spot API. |

Additional Kraken-native types not in our enum:
- `take-profit`, `take-profit-limit` — mirror of stop-loss but triggered above for longs. If needed, extend our enum.
- `settle-position` — closes a margin position; spot adapter ignores.

**Declaration:**
```python
supported_order_types = frozenset({
    OrderType.MARKET,
    OrderType.LIMIT,
    OrderType.STOP_MARKET,
    OrderType.STOP_LIMIT,
    OrderType.TRAILING_STOP,
    OrderType.TRAILING_STOP_LIMIT,
    OrderType.ICEBERG,
})
```

### 2.5 Time-in-force mapping

| Platform `TimeInForce` | Kraken `time_in_force` | Notes |
|---|---|---|
| `GTC` | `gtc` | Default. |
| `GTD` | `gtd` | Requires `expire_time` (ISO 8601 or epoch). |
| `IOC` | `ioc` | Supported. |
| `DAY` | — | Not natively supported (crypto trades 24/7). Map to `GTD` with end-of-UTC-day expiry, or reject. **Recommend: reject** — don't mask the gap. |
| `FOK` | — | Not supported. Reject. |
| `POST_ONLY` | `gtc` + `post_only=true` | **TIF is GTC; post-only is a separate boolean.** Platform must flatten this when serialising. |

**Declaration:**
```python
supported_tif = frozenset({
    TimeInForce.GTC,
    TimeInForce.GTD,
    TimeInForce.IOC,
    TimeInForce.POST_ONLY,
})
```

---

## 3. Idempotency semantics — the Kraken-specific answer

### 3.1 Tier placement

From the design doc's three-tier framework:

> **Kraken → Tier 1 (with caveats): `NativeClientId(max_length=18, charset="hex", lifetime="open_only")`**

Justification:

| Requirement | Kraken WS v2 | Status |
|---|---|---|
| Broker-side string client ID | `cl_ord_id` | ✅ |
| Rejects duplicates while order is open | Expected | [VERIFY by test §5.C.6] |
| ID echoed in fills | Yes (executions channel) | [VERIFY by test §5.C.3] |
| Lookup by client ID | WS `cancel_order`, REST `QueryOrders` (maybe) | [VERIFY by test §5.C.7] |
| Reuse after terminal state | Unclear — wording says "uniquely identifies an **open** order" | **Assumed YES** [VERIFY by test §5.C.8] |
| REST parity | Added in 2025 [VERIFY] | [VERIFY by test §5.C.9] |

### 3.2 Platform flow with Kraken

```
1. Platform generates cl_ord_id = hex(uuid4())[:18]              # fits Kraken's 18-char cap
2. Platform writes OrderRequest to DB + outbox row (atomic)
3. Dispatcher picks up outbox row, calls plugin.submit_order(...)
4. Plugin.submit_order:
   a. WS send add_order { cl_ord_id, ..., token }
   b. Await ack on same req_id
   c. On success → return OrderResponse(exchange_order_id=order_id)
   d. On duplicate-id error → call plugin.get_order_by_client_id(cl_ord_id)
        - query open_orders (WS) → if found, return it
        - else query REST ClosedOrders (filtered by cl_ord_id) → if found, return it
        - else raise (should not happen; either error-code was misclassified or races exist)
5. Platform records exchange_order_id in DB
6. Fills arrive on executions channel → platform writes to fills table (idempotent on exec_id)
```

### 3.3 Declaration

```python
class KrakenSpotExchange(BaseExchange):
    idempotency = NativeClientId(
        max_length=18,
        charset="hex",
        lifetime="open_only",
    )
    supported_order_types = frozenset({...})   # see §2.4
    supported_tif = frozenset({...})           # see §2.5
    rate_limits = [
        RateLimit(endpoint="*",           capacity=15, refill_per_second=0.33),
        RateLimit(endpoint="submit_order", capacity=60, refill_per_second=1.0),  # order-mgmt limit
    ]
```

### 3.4 Why `lifetime="open_only"` not `"forever"`

If `cl_ord_id` is reusable after a fill/cancel, and we use `order.id` (a UUID) as the source, the probability of the same UUID being regenerated is 2^-128. We're safe from accidental reuse.

The risk direction is the **other** way: if we *assume* lifetime is forever and in fact Kraken recycles, a second submission with the same `cl_ord_id` might silently match an old closed order in some Kraken-side dedup cache and produce confusing responses. Design choice: treat the ID as only authoritative while the order is open; after terminal state, trust `exchange_order_id` as the canonical handle.

### 3.5 Fallback scan (belt + suspenders)

Even with `cl_ord_id`, after any network error on submit:
1. Query `OpenOrders` filtering on `cl_ord_id` / `userref`.
2. Query `ClosedOrders` with a time window of `[submit_start - 10s, now]`.
3. Match on `cl_ord_id`. If found → existing order; if not → safe to retry submit.

This scan must run **before** retry, with a `pg_advisory_xact_lock(order.id)` held throughout to serialise recovery across workers.

---

## 4. Error classification table

Kraken error strings are `EGeneral:Something` / `EAPI:Something` / `EOrder:Something` / `EService:Something`. Incomplete list, classified for our `ExchangeErrorKind`:

| Kraken error | Kind | Retry? | Notes |
|---|---|---|---|
| `EOrder:Cannot open position` | `INSUFFICIENT_FUNDS` | No | Balance too low. |
| `EOrder:Insufficient funds` | `INSUFFICIENT_FUNDS` | No | |
| `EOrder:Insufficient margin` | `INSUFFICIENT_FUNDS` | No | Margin variant. |
| `EOrder:Order minimum not met` | `INVALID_ORDER` | No | Below `ordermin`. |
| `EOrder:Cost minimum not met` | `INVALID_ORDER` | No | Below `costmin`. |
| `EOrder:Tick size check failed` | `INVALID_ORDER` | No | Refresh AssetPairs cache. |
| `EOrder:Orders limit exceeded` | `RATE_LIMITED` | Yes (backoff) | Per-account open-order cap (~80 on Pro). |
| `EOrder:Positions limit exceeded` | `RATE_LIMITED` | Yes | Margin only. |
| `EOrder:Rate limit exceeded` | `RATE_LIMITED` | Yes | Order-management counter. |
| `EOrder:Scheduled orders limit exceeded` | `RATE_LIMITED` | Yes | |
| `EOrder:Unknown position` | `INVALID_ORDER` | No | Margin. |
| `EOrder:Invalid price` | `INVALID_ORDER` | No | |
| `EOrder:Reduce_only order qty exceeds position` | `INVALID_ORDER` | No | |
| `EOrder:Invalid reference id` | `INVALID_ORDER` | No | Bad `cl_ord_id` / `userref`. |
| `EOrder:Duplicate order` **[VERIFY exact string]** | `DUPLICATE_CLIENT_ID` | Special — call `get_order_by_client_id` | **THE one we care about for idempotency.** |
| `EAPI:Invalid key` | `INVALID_ORDER` | No | Config/DLQ. |
| `EAPI:Invalid signature` | `INVALID_ORDER` | No | Config/DLQ. |
| `EAPI:Invalid nonce` | `TRANSIENT` | Yes | Nonce moved backwards; regenerate. |
| `EAPI:Invalid token` | `TRANSIENT` | Yes | WS token expired — refresh. |
| `EAPI:Rate limit exceeded` | `RATE_LIMITED` | Yes | Top-level REST limiter. |
| `EGeneral:Permission denied` | `INVALID_ORDER` | No | API key lacks scope — fix config. |
| `EGeneral:Invalid arguments` | `INVALID_ORDER` | No | Schema error. |
| `EGeneral:Internal error` | `TRANSIENT` | Yes | |
| `EGeneral:Temporary lockout` | `TRANSIENT` | Yes (long backoff, ~15 min) | After too many auth failures. |
| `EService:Unavailable` | `TRANSIENT` | Yes | Maintenance window. |
| `EService:Busy` | `TRANSIENT` | Yes | |
| `EService:Market in cancel_only mode` | `INVALID_ORDER` | No | Pair status changed. |
| `EService:Market in post_only mode` | `INVALID_ORDER` (unless POST_ONLY) | Conditional | If we sent a non-post-only order, invalid. If post-only, should succeed. |
| HTTP 429 | `RATE_LIMITED` | Yes | |
| HTTP 5xx | `TRANSIENT` | Yes | |
| TCP timeout / connection reset | `TRANSIENT` | Yes — **after recovery scan** | Submit-result unknown. |

**[VERIFY]** No fully-enumerated error list exists in one Kraken doc — we must keep this table a living document and extend it as new strings appear in production logs. Every unclassified error defaults to `UNKNOWN` → conservative retry.

**`classify_error` implementation sketch:**
```python
def classify_error(self, exc: Exception) -> ExchangeErrorKind:
    msg = str(exc)
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return ExchangeErrorKind.TRANSIENT
    # Pattern matching on Kraken error strings
    if "Duplicate" in msg or "already exists" in msg:
        return ExchangeErrorKind.DUPLICATE_CLIENT_ID
    if "Rate limit" in msg or "Orders limit" in msg:
        return ExchangeErrorKind.RATE_LIMITED
    if "Insufficient" in msg:
        return ExchangeErrorKind.INSUFFICIENT_FUNDS
    if "Invalid" in msg or "minimum" in msg or "Permission" in msg:
        return ExchangeErrorKind.INVALID_ORDER
    if "Internal" in msg or "Busy" in msg or "Unavailable" in msg or "Invalid nonce" in msg or "Invalid token" in msg:
        return ExchangeErrorKind.TRANSIENT
    return ExchangeErrorKind.UNKNOWN
```

---

## 5. Manual test plan

**Environment:** Kraken live mainnet. No sandbox. All money tests use minimum permitted order sizes on BTC/USD; cleanup step is mandatory.

**Pre-requisites:**
- [ ] Dedicated test API key created with only the minimum permissions enumerated in §1.8
- [ ] Key stored in `~/.ascent/kraken-test.env` (never committed)
- [ ] Account has ≥ $50 USD and ≥ 0.0002 BTC available
- [ ] `CancelAllOrdersAfter(60)` dead-man's-switch active during the session
- [ ] On-hand: rollback script that calls `CancelAll` + flattens any non-zero crypto balance ≥ ordermin

Testing should be run as a single supervised session, not automated — this is exploratory validation, not regression.

### 5.A — Pre-live checks (no money)

| # | Test | Steps | Expected | Pass/Fail |
|---|---|---|---|---|
| A.1 | REST auth | `POST /0/private/Balance` with test key | 200, `error=[]`, `result` present | [ ] |
| A.2 | REST missing-permission rejection | Remove "Query Funds" scope, repeat | `error=["EGeneral:Permission denied"]` | [ ] |
| A.3 | WS token fetch | `POST /0/private/GetWebSocketsToken` | `result.token` non-empty, `result.expires ≈ 900` | [ ] |
| A.4 | WS connect + auth | Connect `wss://ws-auth.kraken.com/v2`, send `{method:"subscribe", params:{channel:"balances", token}}` | Subscription confirmation + initial snapshot | [ ] |
| A.5 | Public market data | Subscribe `book` channel for `BTC/USD` | Ongoing updates > 0/s | [ ] |
| A.6 | `AssetPairs` read | `GET /0/public/AssetPairs?pair=XBTUSD` | `XXBTZUSD` entry, has `wsname=XBT/USD` or `BTC/USD`, `ordermin`, `costmin`, `tick_size` all present | [ ] |
| A.7 | Symbol normalisation | Feed every `AssetPairs` entry through our normaliser; assert round-trip | 0 failures | [ ] |
| A.8 | `TradeVolume` fee read | `POST /0/private/TradeVolume pair=XBTUSD fee-info=true` | `fees` + `fees_maker` both present; numbers match §2.3 tier table | [ ] |
| A.9 | Token expiry behaviour | Fetch token, wait 16 min, attempt private WS action using that token | Expected: `EAPI:Invalid token`. [VERIFY that token doesn't auto-refresh] | [ ] |
| A.10 | Connection held past token expiry | Connect + auth, wait 16 min without reauth, send private op | Expected: server drops connection OR silently errors — **record observed** | [ ] |

### 5.B — Failure-mode probes (no-fill, no money)

All submissions use far-OOM limit prices so they never fill.

| # | Test | Steps | Expected | Pass/Fail |
|---|---|---|---|---|
| B.1 | Invalid pair | `add_order symbol="NOPE/USD"` | Error; `classify_error → INVALID_ORDER` | [ ] |
| B.2 | Below `ordermin` | `add_order` BTC/USD qty=0.0000001 | `EOrder:Order minimum not met`; `classify_error → INVALID_ORDER` | [ ] |
| B.3 | Below `costmin` | `add_order` limit=1, qty=0.00001 | `EOrder:Cost minimum not met`; `INVALID_ORDER` | [ ] |
| B.4 | Bad tick size | limit=49000.12345 (too many decimals) | `EOrder:Tick size check failed`; `INVALID_ORDER` | [ ] |
| B.5 | Bad WS token | Corrupt token string | `EAPI:Invalid token`; `TRANSIENT` | [ ] |
| B.6 | Bad REST signature | Flip a bit in signature | `EAPI:Invalid signature`; `INVALID_ORDER` | [ ] |
| B.7 | Nonce regression | Post with nonce = previous_nonce − 1 | `EAPI:Invalid nonce`; `TRANSIENT` | [ ] |
| B.8 | Rate-limit probe (REST) | Burst 30 × `OpenOrders` in 2 s | At least one `EAPI:Rate limit exceeded`; `RATE_LIMITED` | [ ] |
| B.9 | Rate-limit probe (order-mgmt) | Submit-then-cancel 20× rapidly | Eventually `EOrder:Rate limit exceeded`; `RATE_LIMITED` | [ ] |
| B.10 | Permission denied | Use a key without "Create Orders"; submit | `EGeneral:Permission denied`; `INVALID_ORDER` | [ ] |
| B.11 | Cancel non-existent order | `cancel_order order_id="FAKE-0-0"` | `EOrder:Unknown order`; `INVALID_ORDER` | [ ] |

**Rollback for B.*:** `CancelAll` at end of this section.

### 5.C — Live Tier 0: limit orders, no fill (deep OOM)

All orders on BTC/USD, minimum permitted size (e.g. qty = `ordermin + 1 tick`), limit price far from market (e.g. buy at 50% of mid, sell at 200% of mid) so they cannot fill. We are validating idempotency, not strategy.

| # | Test | Steps | Expected | Pass/Fail |
|---|---|---|---|---|
| C.1 | Submit with `cl_ord_id` | Generate `cid = hex(uuid4())[:18]`; WS `add_order BTC/USD buy limit ordermin @ 0.5×mid cl_ord_id=cid` | `success=true`, response includes `order_id` and `cl_ord_id=cid` | [ ] |
| C.2 | Executions stream sees `new` | Subscribed to `executions` channel during C.1 | Event with `exec_type="new"`, same `order_id`, same `cl_ord_id` | [ ] |
| C.3 | `cl_ord_id` echoed on fills | N/A this tier — deferred to §5.D | — | [ ] |
| C.4 | `OpenOrders` contains cid | `POST /0/private/OpenOrders` | Our `order_id` present; `userref` and/or `cl_ord_id` field populated | [ ] |
| C.5 | `OpenOrders` filter by cid | `POST /0/private/OpenOrders userref=...` or `cl_ord_id=...` if REST supports | Filters correctly. **[VERIFY]** — if REST doesn't support `cl_ord_id` filter, fallback is to pull all open and filter client-side | [ ] |
| C.6 | **Duplicate-while-open rejection (THE test)** | Immediately resubmit same `add_order` with the same `cid`, different `req_id` | `success=false`, error string is [RECORD EXACT VALUE]; `classify_error → DUPLICATE_CLIENT_ID` | [ ] |
| C.7 | `get_order_by_client_id` works | Call our `plugin.get_order_by_client_id(cid)` | Returns the `OrderStatusResponse` for the order from C.1 | [ ] |
| C.8 | Cancel by `cl_ord_id` | WS `cancel_order cl_ord_id=[cid]` | `success=true`; `executions` channel emits `canceled` | [ ] |
| C.9 | `ClosedOrders` search after cancel | `POST /0/private/ClosedOrders`; filter for our `cid` | Order appears with `status="canceled"` | [ ] |
| C.10 | **Reuse `cl_ord_id` after cancel (lifetime probe)** | Submit another `add_order` with the **same** `cid` (new `req_id`) | **RECORD:** does it succeed, or is it rejected? If succeeds → `lifetime="open_only"` is correct. If rejected → change plugin declaration to `lifetime="forever"` and use UUID-per-submit. | [ ] |
| C.11 | REST parity — `cl_ord_id` on REST AddOrder | `POST /0/private/AddOrder cl_ord_id=<new cid>` | **RECORD:** does REST accept the field? If no, REST is `userref`-only and submission must go through WS. | [ ] |
| C.12 | REST `userref` duplicate behaviour | Submit two REST orders with same `userref=12345` | Both succeed (userref is non-unique). Confirms why userref alone is inadequate. | [ ] |
| C.13 | Amend preserves `order_id` | WS `amend_order order_id=... new qty` | New event `exec_type="amended"`, **same `order_id`**, new values | [ ] |
| C.14 | Amend by `cl_ord_id` | WS `amend_order cl_ord_id=cid new qty` (if supported) | [VERIFY] — record whether accepted | [ ] |

**Rollback for C.*:** `CancelAll`. Then re-run `OpenOrders` and assert empty.

### 5.D — Live Tier 1: small real fill

This is money-spending. Use the **smallest** fill that satisfies Kraken's `ordermin` and `costmin` (for BTC/USD, typically $0.50–$5 worth). Budget: expect ≤ $0.10 in fees per round-trip.

**Pre-flight:** record `starting_balance_usd`, `starting_balance_xbt` via REST `Balance`.

| # | Test | Steps | Expected | Pass/Fail |
|---|---|---|---|---|
| D.1 | Market BUY (minimum) | Generate `cid_buy`; WS `add_order BTC/USD buy market order_qty=ordermin cl_ord_id=cid_buy` | `success=true`; `order_id` returned | [ ] |
| D.2 | Fill event on `executions` | Wait ≤ 10 s | Event `exec_type="trade"`, `cl_ord_id=cid_buy`, `cum_qty ≈ ordermin`, `avg_price ≈ mid`, `fee_usd_equiv > 0` | [ ] |
| D.3 | Fee matches tier | Compare `fee_usd_equiv / (qty*price)` to the taker % from `TradeVolume` | Within 1 bps of expected | [ ] |
| D.4 | Balance reflects fill | `Balance` call 5 s after fill | `XBT` increased by `ordermin` (net of fee); `USD` decreased by `ordermin*price + fee` | [ ] |
| D.5 | `TradesHistory` records fill | `POST /0/private/TradesHistory` | New entry with our `order_id` | [ ] |
| D.6 | `ClosedOrders` records fill | `POST /0/private/ClosedOrders` | Our order with `status="closed"`, `vol_exec = ordermin` | [ ] |
| D.7 | **Reuse `cl_ord_id` after fill** | Submit a new `add_order` using `cid_buy` again (different notional) | **RECORD:** does Kraken accept or reject? This settles the `lifetime="open_only"` vs `"forever"` question definitively. | [ ] |
| D.8 | Flatten: Market SELL | `cid_sell`; `add_order BTC/USD sell market qty=<what we just bought, net of fee>` | `success=true`, fills, balance returns to `starting_balance_xbt` ± dust | [ ] |
| D.9 | Reconciliation | Pull `TradesHistory` for the session; compare to our DB | Every fill matched 1:1 on `order_id` + `exec_id`; fees sum equals sum of `fee_usd_equiv` | [ ] |
| D.10 | Net PnL accounting | `starting_balance_usd − ending_balance_usd` | ≈ 2 × taker_fee × notional (both legs paid spread + fee) | [ ] |

**Rollback for D.*:** if `ending_balance_xbt > starting_balance_xbt + dust`, submit a corrective market SELL. If `ending_balance_xbt < starting_balance_xbt − dust`, submit a corrective market BUY.

### 5.E — Reconnect / resume

| # | Test | Steps | Expected | Pass/Fail |
|---|---|---|---|---|
| E.1 | Kill WS mid-stream | Submit a resting limit order; while `executions` is subscribed, physically drop the socket | Socket closes cleanly; no fills observed during gap window | [ ] |
| E.2 | Reconnect with `snap_orders` | Re-auth, resubscribe with `snap_orders=true` | Snapshot contains our still-open order with full state | [ ] |
| E.3 | Missed events during gap | During the gap, have a co-operator cancel our order via the Kraken UI | On resubscribe, do we see the cancel event, or only the snapshot? **RECORD behaviour** | [ ] |
| E.4 | Sequence gap detection | Inspect `sequence` field across reconnect | Gap is detectable; implementation must call REST to fill in | [ ] |
| E.5 | Fresh token on reconnect | Reuse old token on reconnect | Should reject; use fresh token instead succeeds | [ ] |
| E.6 | Long idle then reconnect | Keep socket open idle for 20 min then send request | Expected behaviour [VERIFY] — document any idle-timeout | [ ] |

### 5.F — Dead-man's-switch validation

| # | Test | Steps | Expected | Pass/Fail |
|---|---|---|---|---|
| F.1 | `CancelAllOrdersAfter(60)` | Arm with 60 s; submit a resting limit OOM | Order open immediately | [ ] |
| F.2 | Don't re-arm | Wait 90 s | Order cancelled automatically; `ClosedOrders` shows it with `reason="Cancel-after"` or similar | [ ] |
| F.3 | Re-arm keeps alive | Submit order, re-arm every 30 s for 3 min | Order stays open | [ ] |

### 5.G — Classification coverage

After running sections A–F, compile the set of error strings observed. For each, confirm the `classify_error` routing matches the tables in §4. **Any unclassified error → UPDATE §4 and re-run test.**

- [ ] All error strings observed in session listed in §4
- [ ] No error fell through to `UNKNOWN` in production-reachable paths
- [ ] `DUPLICATE_CLIENT_ID` path exercised at least once (C.6)
- [ ] `RATE_LIMITED` path exercised at least once (B.8 or B.9)

### 5.H — Final cleanup (mandatory)

- [ ] `POST /0/private/CancelAll` → 0 open orders remaining
- [ ] `POST /0/private/Balance` — ending balances documented in test log
- [ ] Any crypto leg left over from a failed round-trip: manually flattened or explicitly accepted as loss
- [ ] Test-session API key rotated if any suspicion of leak

---

## 6. Open questions and risks

1. **[Must verify in session]** Exact `cl_ord_id` max length. Design doc says 18 ASCII chars or 32-hex-char UUID. If the live value differs (e.g. 20 chars, or ASCII-only), update the `NativeClientId(max_length=…)` declaration and re-run C.1.

2. **[Must verify in session]** `cl_ord_id` lifetime semantics (tests C.10, D.7). Three possible outcomes:
   - Reusable after terminal (open-only semantics) → current design.
   - One-time-use forever → change `lifetime="forever"`; platform must ensure uniqueness globally, trivially satisfied by UUID.
   - Reusable only after some TTL → worst case; need explicit `lifetime="ttl"` with duration parameter.

3. **[Must verify in session]** REST parity on `cl_ord_id` (test C.11). If REST doesn't accept it:
   - Submission path must be WS-only. WS failures cannot fall back to REST without losing idempotency.
   - In that case, design for connection-loss recovery relies entirely on `get_order_by_client_id` using `OpenOrders` + `ClosedOrders` filtered scans.

4. **[Must verify in session]** Exact duplicate-rejection error string (test C.6). This is the discriminator for `DUPLICATE_CLIENT_ID` vs generic `INVALID_ORDER` classification. Our error-classification table has a `[VERIFY exact string]` flag that must be resolved in the test session.

5. **[Must verify in session]** Executions channel resume semantics (test E.3). If a `canceled` event during the gap is not re-delivered on reconnect, we cannot rely on the stream alone — every reconnect must trigger a REST `ClosedOrders` sweep covering the gap window.

6. **Bulk-submit atomicity.** WS v2 has `batch_add` and `batch_cancel` [VERIFY]. We don't plan to use them in v1 (per-order dispatch is simpler), but if/when we do, the idempotency wrapping changes: one batch call with N `cl_ord_id`s means partial-success handling must split per-id. Flagged for when the need arises.

7. **`.d` dark-pool pairs.** Pair metadata returns `.d` variants for some major pairs. Our adapter should require explicit opt-in to submit to them (different liquidity profile). Default: strip `.d` suffixes and re-normalise to the primary pair.

8. **Staking assets.** `XBT.S`, `ETH.S`, etc. are not tradeable on the spot endpoint but appear in `Balance`. Our balance-mapper must ignore `.S` / `.B` / `.F` / `.M` suffixes for tradeable-balance calculations, but surface them as held-quantity for accounting.

9. **Futures / derivatives.** Kraken Futures use a completely separate API (`https://futures.kraken.com/derivatives/api/v3/`). This adapter explicitly does not support futures. If/when we add a `KrakenFuturesExchange`, it will be a separate class — code-sharing limited to auth helpers at most.

10. **Feature-flag for staged rollout.** First-live-money activation:
    - Step 1: Adapter deployed, `supported_order_types = frozenset()` — paper-trade only.
    - Step 2: Enable LIMIT only, tiny notional ceiling.
    - Step 3: Add MARKET after 24 h without incident.
    - Step 4: Unlock remaining order types.
    Rollback = flip env var and call `CancelAll`.

11. **Pair metadata staleness.** `AssetPairs` changes rarely but not never (new listings, status flips to `cancel_only`). Refresh cadence: nightly on schedule, plus on any `Tick size` / `minimum` / `Unknown pair` error.

12. **Observability.** For every live test above, platform must log:
    - `req_id` correlator end-to-end
    - Latency `add_order → first executions event`
    - Latency `add_order → first fill`
    - Effective fee bps per fill
    These become our SLOs once the adapter is live.

---

## Appendix A — Mapping summary card (for quick reference during implementation)

```python
# src/ascent/exchanges/kraken.py

class KrakenSpotExchange(BaseExchange):
    provider = "KRAKEN"
    instrument_type = "CRYPTO"
    display_name = "Kraken Spot"

    idempotency = NativeClientId(
        max_length=18,       # VERIFY via test C.1
        charset="hex",
        lifetime="open_only", # VERIFY via tests C.10, D.7
    )
    supported_order_types = frozenset({
        OrderType.MARKET,
        OrderType.LIMIT,
        OrderType.STOP_MARKET,
        OrderType.STOP_LIMIT,
        OrderType.TRAILING_STOP,
        OrderType.TRAILING_STOP_LIMIT,
        OrderType.ICEBERG,
    })
    supported_tif = frozenset({
        TimeInForce.GTC,
        TimeInForce.GTD,
        TimeInForce.IOC,
        TimeInForce.POST_ONLY,
    })
    rate_limits = [
        RateLimit(endpoint="*",            capacity=15, refill_per_second=0.33),   # VERIFY tier
        RateLimit(endpoint="submit_order", capacity=60, refill_per_second=1.0),    # order-mgmt
    ]
    poll_interval = 1.0
```

## Appendix B — Pair-name normaliser (rough)

```python
# Extract from AssetPairs on startup:
#   internal_to_wsname: dict[str, str]   # "XXBTZUSD" → "BTC/USD"
#   altname_to_internal: dict[str, str]  # "XBTUSD"   → "XXBTZUSD"
#   ascent_to_kraken: dict[str, tuple[str,str,str]]  # "BTC-USD" → (internal, altname, wsname)

def ascent_to_ws_symbol(sym: str) -> str:
    internal, altname, wsname = ascent_to_kraken[sym]
    return wsname

def ascent_to_rest_pair(sym: str) -> str:
    internal, altname, wsname = ascent_to_kraken[sym]
    return altname

def kraken_internal_to_ascent(code: str) -> str:
    wsname = internal_to_wsname[code]         # "BTC/USD"
    return wsname.replace("/", "-")           # "BTC-USD"
```
