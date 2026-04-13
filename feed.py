from __future__ import annotations

import os
import random
import uuid
from datetime import datetime
from typing import ClassVar

import pandas as pd
from dotenv import load_dotenv
from pandera.typing.pandas import DataFrame
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ascent.feeds.base import Feed
from ascent.feeds.output import InstrumentAttributes
from ascent.feeds.schedule import Schedule

# Attribute IDs — these must match the DB attribute records.
# For the sample we use integers as placeholders; a real feed
# would query the attribute table.
ATTR_CLOSE = 1
ATTR_VOLUME = 2

# Base prices for simulation keyed by asset symbol
BASE_PRICES: dict[str, float] = {
    "BTC": 67500.0,
    "ETH": 3400.0,
    "SOL": 145.0,
    "ADA": 0.45,
    "XRP": 0.52,
}


def _load_instruments(database_url: str) -> dict[uuid.UUID, str]:
    """Load instrument UUIDs and their base-asset symbols from the DB."""
    from ascent.database.models.assets import Asset
    from ascent.database.models.instruments import Instrument

    engine = create_engine(database_url)
    instruments: dict[uuid.UUID, str] = {}
    with Session(engine) as db:
        rows = db.execute(
            select(Instrument.id, Asset.name).join(Asset, Instrument.from_asset_id == Asset.id)
        ).all()
        for inst_id, asset_name in rows:
            if asset_name in BASE_PRICES:
                instruments[inst_id] = asset_name
    return instruments


class MarketDataFeed(Feed):
    """Emits fake OHLCV market data for instruments found in the database."""

    class Parameters(BaseModel):
        volatility: float = Field(0.002, description="Per-tick price volatility (std dev)")

    schedule = Schedule(interval=15, start_date=datetime(2024, 1, 1))
    output = InstrumentAttributes
    provider = "KRAKEN"
    instrument_type = "SECURITY"

    # Populated at startup from the database
    _instruments: ClassVar[dict[uuid.UUID, str]] = {}
    _prices: ClassVar[dict[uuid.UUID, float]] = {}

    def fetch(self) -> DataFrame[InstrumentAttributes]:
        now = pd.Timestamp.now(tz="UTC")
        vol = self.parameters.volatility
        rows = []

        for inst_id, symbol in self._instruments.items():
            base_price = BASE_PRICES.get(symbol, 100.0)
            if inst_id not in self._prices:
                self._prices[inst_id] = base_price
            self._prices[inst_id] *= 1 + random.gauss(0, vol)
            price = self._prices[inst_id]

            rows.append(
                {
                    "timestamp": now,
                    "instrument_id": str(inst_id),
                    "attribute_id": ATTR_CLOSE,
                    "attribute_value": round(price, 6),
                }
            )
            rows.append(
                {
                    "timestamp": now,
                    "instrument_id": str(inst_id),
                    "attribute_id": ATTR_VOLUME,
                    "attribute_value": round(random.uniform(100, 10000), 2),
                }
            )

        return pd.DataFrame(rows)


if __name__ == "__main__":
    load_dotenv()
    db_url = os.environ["ASCENT_DATABASE_URL"]

    # Load real instrument UUIDs from the database
    MarketDataFeed._instruments = _load_instruments(db_url)
    if not MarketDataFeed._instruments:
        print("No instruments found in DB. Run 'ascent seed run --drop --profile base' first.")
        raise SystemExit(1)
    print(f"Loaded {len(MarketDataFeed._instruments)} instruments")

    MarketDataFeed.run(
        redis_url=os.environ["ASCENT_REDIS_URL"],
        database_url=db_url,
    )
