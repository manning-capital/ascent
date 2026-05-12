"""SQLAlchemy adapter for :class:`ascent.ports.InstrumentRepository`."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ascent.database.models.instruments import Instrument as InstrumentRow
from ascent.ports import InstrumentAssetIds, InstrumentRepository


class SqlAlchemyInstrumentRepository(InstrumentRepository):
    async def get_assets(
        self, session: Session, instrument_ids: Iterable[uuid.UUID]
    ) -> dict[uuid.UUID, tuple[str, str]]:
        ids = list(instrument_ids)
        if not ids:
            return {}
        return await asyncio.to_thread(self._get_assets_sync, session, ids)

    async def get_asset_ids(
        self, session: Session, instrument_ids: Iterable[uuid.UUID]
    ) -> dict[uuid.UUID, InstrumentAssetIds]:
        ids = list(instrument_ids)
        if not ids:
            return {}
        return await asyncio.to_thread(self._get_asset_ids_sync, session, ids)

    @staticmethod
    def _get_assets_sync(
        db: Session, instrument_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, tuple[str, str]]:
        rows = (
            db.execute(
                select(InstrumentRow)
                .options(joinedload(InstrumentRow.from_asset), joinedload(InstrumentRow.to_asset))
                .where(InstrumentRow.id.in_(instrument_ids))
            )
            .scalars()
            .all()
        )
        return {row.id: (row.from_asset.name, row.to_asset.name) for row in rows}

    @staticmethod
    def _get_asset_ids_sync(
        db: Session, instrument_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, InstrumentAssetIds]:
        rows = (
            db.execute(select(InstrumentRow).where(InstrumentRow.id.in_(instrument_ids)))
            .scalars()
            .all()
        )
        return {
            row.id: InstrumentAssetIds(
                from_asset_id=row.from_asset_id,
                to_asset_id=row.to_asset_id,
            )
            for row in rows
        }
