"""
SovereignStrategy v2 - params.py
================================

Regime-keyed hyperparameters for SovereignStrategy v2.

Each regime has its own:
- indicator periods (rsi, ema periods -- though most are hardcoded as
  constants in the strategy for clarity; only the tunable ones live here)
- risk parameters: position sizing, ATR multiplier, stop-loss type

Regimes detected by current_regime property:
- trending_bullish:    strong uptrend (ADX>25, Hurst>0.55, price>EMA200)
- trending_bearish:    strong downtrend
- ranging_low_vol:     chop with low realized vol (ADX<20, rvol_pct<0.75)
- ranging_high_vol:    chop with high realized vol (DANGER: stand aside)
- transitional:        weak signal (ADX 20-25 or Hurst ~0.5)

Tuning rationale
----------------
- Position sizing scales DOWN in dangerous regimes.
- ATR multiplier scales UP in transitional (wider stops = less whipsaw).
- Only trending regimes allow normal 1.0x sizing.
- ranging_high_vol has 0% sizing -- strategy stands aside entirely.
"""

params = {
    "default": {
        "indicators": {
            "ema200_period": 200,
            "ema50_period": 50,
            "ema20_period": 20,
            "rsi_period": 14,
            "atr_period": 14,
            "adx_period": 14,
            "volume_sma_period": 20,
        },
        "risk": {
            "max_drawdown_limit_pct": 2.0,
            "max_position_sizing_pct": 0.5,  # 0.5% risk per trade (was 0.125 -- untraderable)
            "atr_multiplier": 2.0,           # stop = entry - ATR*2 (matches sizing)
            "stop_loss_type": "atr",         # ATR trailing after TP1
            "stop_loss_value": 0.02,         # legacy field, ignored when atr_multiplier is used
        },
    },

    "trending_bullish": {
        "indicators": {
            "ema200_period": 200,
            "ema50_period": 50,
            "ema20_period": 20,
            "rsi_period": 14,
            "atr_period": 14,
            "adx_period": 14,
            "volume_sma_period": 20,
        },
        "risk": {
            "max_drawdown_limit_pct": 2.0,
            "max_position_sizing_pct": 1.0,   # full size in clean trends
            "atr_multiplier": 2.0,
            "stop_loss_type": "atr",
            "stop_loss_value": 0.02,
        },
    },

    "trending_bearish": {
        "indicators": {
            "ema200_period": 200,
            "ema50_period": 50,
            "ema20_period": 20,
            "rsi_period": 14,
            "atr_period": 14,
            "adx_period": 14,
            "volume_sma_period": 20,
        },
        "risk": {
            "max_drawdown_limit_pct": 2.0,
            "max_position_sizing_pct": 0.5,   # half size for shorts (funding risk)
            "atr_multiplier": 2.5,            # wider stop: bear moves are sharper
            "stop_loss_type": "atr",
            "stop_loss_value": 0.025,
        },
    },

    "ranging_low_vol": {
        "indicators": {
            "ema200_period": 200,
            "ema50_period": 50,
            "ema20_period": 20,
            "rsi_period": 14,
            "atr_period": 14,
            "adx_period": 14,
            "volume_sma_period": 20,
        },
        "risk": {
            "max_drawdown_limit_pct": 2.0,
            "max_position_sizing_pct": 0.3,   # reduced size in chop
            "atr_multiplier": 2.5,            # wider stop to survive range noise
            "stop_loss_type": "atr",
            "stop_loss_value": 0.025,
        },
    },

    "ranging_high_vol": {
        "indicators": {
            "ema200_period": 200,
            "ema50_period": 50,
            "ema20_period": 20,
            "rsi_period": 14,
            "atr_period": 14,
            "adx_period": 14,
            "volume_sma_period": 20,
        },
        "risk": {
            "max_drawdown_limit_pct": 2.0,
            "max_position_sizing_pct": 0.0,   # STAND ASIDE: vol explosion = death
            "atr_multiplier": 3.0,
            "stop_loss_type": "atr",
            "stop_loss_value": 0.03,
        },
    },

    "transitional": {
        "indicators": {
            "ema200_period": 200,
            "ema50_period": 50,
            "ema20_period": 20,
            "rsi_period": 14,
            "atr_period": 14,
            "adx_period": 14,
            "volume_sma_period": 20,
        },
        "risk": {
            "max_drawdown_limit_pct": 2.0,
            "max_position_sizing_pct": 0.4,   # reduced: signal is weak
            "atr_multiplier": 2.5,
            "stop_loss_type": "atr",
            "stop_loss_value": 0.025,
        },
    },
}
