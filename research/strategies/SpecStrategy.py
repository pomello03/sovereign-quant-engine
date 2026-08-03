"""The alpha_spec strategy, written by hand.

Faithful to payload_drop/alpha_spec.json and payload_drop/risk_constraints.json,
with two deliberate departures, both forced by the venue decision (Bybit spot):

  - No short side. Spot cannot sell what it does not hold.
  - Sizing and stop share one risk basis. The generated strategy sizes off
    `atr * 2` but places the stop at `price * (1 - sl)`, so the risk it takes is
    not the risk it declares. Here a single stop distance drives both.

Expected outcome on real candles: zero entries. See research/RESULT_P0-1.md.
"""

from jesse import utils
from jesse.strategies import Strategy

import jesse.indicators as ta

RSI_PERIOD = 14
SMA_PERIOD = 50
RSI_OVERSOLD = 30

STOP_LOSS_PCT = 0.02  # risk_constraints.json: stop_loss_value
TAKE_PROFIT_PCT = 0.04  # risk_constraints.json: take_profit_value
RISK_PER_TRADE_PCT = 2.0  # risk_constraints.json: max_position_sizing_pct


class SpecStrategy(Strategy):
    @property
    def rsi(self) -> float:
        return ta.rsi(self.candles, RSI_PERIOD)

    @property
    def sma(self) -> float:
        return ta.sma(self.candles, SMA_PERIOD)

    def should_long(self) -> bool:
        return self.rsi < RSI_OVERSOLD and self.close > self.sma

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
        # Spot rejects exit orders declared in go_long(); they belong here, and
        # they are priced off the *filled* entry rather than the intended one.
        # The generated strategy does it the other way and would raise on the
        # first fill.
        entry = self.position.entry_price
        self.stop_loss = self.position.qty, entry * (1 - STOP_LOSS_PCT)
        self.take_profit = self.position.qty, entry * (1 + TAKE_PROFIT_PCT)
