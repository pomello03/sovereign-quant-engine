"""Control strategy: identical risk machinery, a condition that actually fires.

Its only purpose is to make a zero-trade result interpretable. If SpecStrategy
returns zero trades and this one returns zero trades too, the harness is broken.
If this one trades and SpecStrategy does not, the difference is the strategy.

Not a proposed strategy. A plain SMA cross is a textbook example with no claim
to edge, and it is used here precisely because nobody will be tempted to deploy it.
"""

from jesse import utils
from jesse.strategies import Strategy

import jesse.indicators as ta

SMA_PERIOD = 50
STOP_LOSS_PCT = 0.02
TAKE_PROFIT_PCT = 0.04
RISK_PER_TRADE_PCT = 2.0


class ControlStrategy(Strategy):
    @property
    def sma(self) -> float:
        return ta.sma(self.candles, SMA_PERIOD)

    @property
    def prev_close(self) -> float:
        return self.candles[-2][2]

    @property
    def prev_sma(self) -> float:
        return ta.sma(self.candles[:-1], SMA_PERIOD)

    def should_long(self) -> bool:
        return self.prev_close <= self.prev_sma and self.close > self.sma

    def should_short(self) -> bool:
        return False  # spot

    def should_cancel_entry(self) -> bool:
        return True

    def go_long(self) -> None:
        entry = self.price
        stop = entry * (1 - STOP_LOSS_PCT)
        qty = utils.risk_to_qty(
            self.available_margin, RISK_PER_TRADE_PCT, entry, stop, fee_rate=self.fee_rate
        )
        self.buy = qty, entry

    def on_open_position(self, order) -> None:
        entry = self.position.entry_price
        self.stop_loss = self.position.qty, entry * (1 - STOP_LOSS_PCT)
        self.take_profit = self.position.qty, entry * (1 + TAKE_PROFIT_PCT)
