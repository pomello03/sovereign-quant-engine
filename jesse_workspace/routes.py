# jesse_workspace/routes.py
# Reference: https://docs.jesse.trade/
#
# Venue decision, 2026-08-03: Bybit spot (PROJECT_STATE.md D1/D2).
# This file previously said 'Binance Perpetual' while docs/ said Bybit, and the
# two were never reconciled because no backtest ever ran.
#
# Spot has no short side. entry_short_conditions in alpha_spec.json is not
# executable here.

routes = [
    ('Bybit Spot', 'BTC-USDT', '4h', 'SovereignStrategy'),
]

extra_candles = []
