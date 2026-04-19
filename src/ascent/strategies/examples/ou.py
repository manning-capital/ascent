"""Ornstein-Uhlenbeck mean-reversion strategy — trades composite spreads."""

from pydantic import BaseModel, Field

from ascent.feeds.examples.composite_market import CompositeMarketData
from ascent.feeds.examples.ou_params import OUParams
from ascent.strategies import Context, Strategy


class OUStrategy(Strategy):
    """Enters on z-score extremes, exits on mean reversion.

    Scoped to composites (e.g. pair spreads). Reads the latest price from
    :class:`CompositeMarketData` and the fitted OU parameters from
    :class:`OUParams`, then enters/exits based on the z-score of the spread.
    """

    class Parameters(BaseModel):
        entry_z: float = Field(2.0, ge=0.5, le=5.0, description="Z-score to enter")
        exit_z: float = Field(0.5, ge=0.0, le=3.0, description="Z-score to exit")
        stop_z: float = Field(4.0, ge=1.0, le=10.0, description="Z-score stop-out")
        quantity: float = Field(1.0, gt=0, description="Units per trade")

    feeds = [CompositeMarketData, OUParams]
    display_name = "OU Strategy"
    description = "Mean-reversion on composite spreads using fitted OU parameters."

    def evaluate(self, ctx: Context) -> None:
        logger = self.get_logger()

        if ctx.df.empty:
            return

        df = ctx.df
        waiting = df[df[("trade", "status")] == "WAITING"]
        in_trade = df[df[("trade", "status")] == "OPEN"]

        logger.info("Waiting: %d, In trade: %d", len(waiting), len(in_trade))


if __name__ == "__main__":
    OUStrategy.run()
