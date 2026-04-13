"""Run the sample feed, exchange, and strategy together in a single process."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from ascent.engine.runner import Runner
from exchange import KrakenSecurityExchange
from feed import MarketDataFeed
from strategy import MomentumStrategy

if __name__ == "__main__":
    load_dotenv()
    runner = Runner(
        redis_url=os.environ["ASCENT_REDIS_URL"],
        database_url=os.environ["ASCENT_DATABASE_URL"],
    )
    runner.add(MarketDataFeed)
    runner.add(KrakenSecurityExchange)
    runner.add(MomentumStrategy)
    runner.run()
