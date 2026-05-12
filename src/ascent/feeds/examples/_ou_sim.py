"""Shared per-instrument OU simulation constants.

Both :class:`MarketData` and :class:`OUParams` import these so the prices
emitted by the simulator and the OU parameters published to the strategy
describe the same dynamics. With per-instrument log-OU, the realized spread
``s = ln(p_a) - beta * ln(p_b)`` for any pair is itself OU with parameters
derived deterministically from these constants and the per-pair ``beta``.
"""

from __future__ import annotations

import hashlib

# Per-second mean reversion rate of each instrument's log-price.
# Spread half-life ``ln(2)/INST_MU`` ~ 38 min, so trade cycles fall in the
# ~30-90 min range targeted for testing throughput.
INST_MU = 3.0e-4

# Per-sqrt(second) log-price volatility per instrument. Stationary log-price
# std per leg is ``INST_SIGMA / sqrt(2*INST_MU)`` ~ 0.10, so each instrument
# typically wanders within ~10% of its base price. For a pair with beta ~ 1
# the resulting spread stationary std is ``INST_SIGMA * sqrt(2) /
# sqrt(2*INST_MU)`` ~ 0.14 — same visual scale as the legacy per-pair sim.
INST_SIGMA = 2.5e-3

BASE_PRICES: dict[str, float] = {
    "BTC": 67500.0,
    "ETH": 3400.0,
    "SOL": 145.0,
    "ADA": 0.45,
    "XRP": 0.52,
    "USDT": 1.0,
    "USDC": 1.0,
    "DAI": 1.0,
}


def base_price_for(symbol: str) -> float:
    """Return a deterministic starting price for an asset symbol.

    Known symbols come from :data:`BASE_PRICES`; anything else is hashed into
    a stable synthetic price in roughly ``[0.1, 1000]`` so the sim can run
    against the full seeded universe without needing a hand-curated price
    for every asset class.
    """
    if symbol in BASE_PRICES:
        return BASE_PRICES[symbol]
    digest = hashlib.sha256(symbol.encode()).digest()
    u = int.from_bytes(digest[:8], "big") / 2**64
    return 0.1 * (10.0 ** (4.0 * u))
