"""InstrumentRepository — minimal lookup for instrument asset metadata.

Two callers today:

- :class:`TradeRouter` uses ``get_assets`` to attach base/quote asset
  *symbols* to outbox payloads so ledger-style exchanges (like
  :class:`PaperExchange`) can debit/credit the right ledger keys on fill.
- :class:`FillProcessor` uses ``get_asset_ids`` to attach the asset's DB
  ``UUID`` to ``Transaction`` rows and ``StrategyAssetHolding`` deltas.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class InstrumentAssetIds:
    from_asset_id: uuid.UUID
    to_asset_id: uuid.UUID


@runtime_checkable
class InstrumentRepository(Protocol):
    async def get_assets(
        self, session: Any, instrument_ids: Iterable[uuid.UUID]
    ) -> dict[uuid.UUID, tuple[str, str]]:
        """Return ``{instrument_id: (from_asset_name, to_asset_name)}``.

        Missing instruments are simply absent from the returned dict; the
        caller decides how to handle that.
        """
        ...

    async def get_asset_ids(
        self, session: Any, instrument_ids: Iterable[uuid.UUID]
    ) -> dict[uuid.UUID, InstrumentAssetIds]:
        """Return ``{instrument_id: InstrumentAssetIds(from, to)}``.

        Missing instruments are absent from the returned dict.
        """
        ...
