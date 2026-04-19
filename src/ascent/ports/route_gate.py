"""Port for the trade-routing gate.

The gate validates that an exchange can accept an open-trade request from
a strategy. It runs three checks in sequence:

1. **Type gate**: each instrument's ``(provider_id, instrument_type_id)``
   matches the exchange's pair.
2. **Assignment gate**: the ``StrategyExchange(strategy, exchange)`` row
   exists and has ``is_active=True``.
3. **Strategy pause gate**: the strategy itself has ``is_paused=False``.

``close()`` calls bypass the gate entirely — the trade's existence is proof
the routing was previously valid.
"""

from __future__ import annotations

import uuid
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class RouteGate(Protocol):
    """Validate that an open-trade request is admissible.

    Returns ``None`` on success, or a short structured rejection code when
    the request must be rejected. Rejection codes are stored verbatim in
    ``Trade.close_reason`` (prefixed with ``UNIVERSE_SCOPE:``) so the UI can
    map them to friendly text.

    Recognised codes (extend as needed):

    - ``provider_mismatch`` — instrument's (provider, type) doesn't match
      the exchange.
    - ``assignment_missing`` — strategy isn't linked to this exchange.
    - ``assignment_disabled`` — strategy-exchange link is disabled.
    - ``strategy_paused`` — the strategy has ``is_paused=True``.
    - ``exchange_missing`` — exchange row doesn't exist (data corruption).
    - ``instrument_missing`` — instrument row doesn't exist (data corruption).
    """

    async def validate_open(
        self,
        session: Any,
        *,
        strategy_id: uuid.UUID,
        exchange_id: uuid.UUID,
        instrument_ids: list[uuid.UUID],
    ) -> str | None: ...
