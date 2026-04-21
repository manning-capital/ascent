"""Entry point that runs the example feeds shipped with Ascent.

The OU-driven simulator lives in ``ascent.feeds.examples.market``; the
OU-params feed lives in ``ascent.feeds.examples.ou_params``. This script
just wires them into a Runner.
"""

from __future__ import annotations

import os

from ascent.engine.runner import Runner
from ascent.feeds.examples.market import MarketData
from ascent.feeds.examples.ou_params import OUParams

if __name__ == "__main__":
    runner = Runner(
        database_url=os.environ["ASCENT_DATABASE_URL"],
        redis_url=os.environ["ASCENT_REDIS_URL"],
        include_writer=True,
    )
    runner.add(OUParams)
    runner.add(MarketData)
    runner.run()
