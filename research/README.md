# research/

Measurement, kept deliberately outside the pipeline.

Nothing here imports `core_engine`. That is the point: when the pipeline says a
strategy is good, something that does not share its code has to be able to check.

## Environment

Jesse lives in its own interpreter, `.venv-jesse`, not in the project venv. It
pins `pytest~=6.2.5`, which fights the test suite's tooling, and installing it in
the main environment would put a framework that imports and executes generated
code into the same process as everything else.

```bash
python -m venv .venv-jesse
.venv-jesse/Scripts/python.exe -m pip install jesse jsonschema
```

The project venv is expected *not* to have Jesse. Running the pipeline there
produces `NO_DATA`, which is the correct answer: no framework, no measurement.

## Data

Candles come from Bybit's public market-data endpoint. No credentials, read-only.

```bash
# 4h, for signal analysis — small, stored as JSON
.venv-jesse/Scripts/python.exe research/fetch_bybit_candles.py \
    --interval 240 --start 2021-01-01 --end 2026-08-01

# 1m, for the simulator — Jesse aggregates upward and asserts on 1m input
.venv-jesse/Scripts/python.exe research/fetch_bybit_candles.py \
    --interval 1 --start 2023-12-01 --end 2026-08-01 --format npy --pause 0.08
```

Each fetch writes a `.meta.json` beside the data with the window, candle count,
completeness, gap report and a sha256 of the series. The data files are
gitignored; **the meta files are tracked**, because they are what makes a result
re-checkable a year from now.

1-minute input is not pedantry. With a 2% stop and a 4% target, a 4h bar whose
range spans both tells you nothing about which was hit first, and assuming the
favourable one is how a losing strategy backtests as a winner.

## Scripts

| | |
|---|---|
| `fetch_bybit_candles.py` | download + integrity report + provenance |
| `count_signals.py` | how often the entry conditions fire. Stdlib only, no framework |
| `crosscheck_indicators.py` | the same question through Jesse's indicators, as an independent check on the above |
| `run_backtest.py` | full simulation via `jesse.research.backtest()` |
| `strategies/SpecStrategy.py` | the alpha_spec strategy, hand-written |
| `strategies/ControlStrategy.py` | same risk machinery, a condition that fires |

```bash
.venv-jesse/Scripts/python.exe research/count_signals.py
.venv-jesse/Scripts/python.exe research/crosscheck_indicators.py
.venv-jesse/Scripts/python.exe research/run_backtest.py --strategy ControlStrategy \
    --start 2024-01-01 --end 2026-07-01
```

## Why there are two strategies

A backtest that reports zero trades has two possible causes, and they look
identical from the outside: the strategy never enters, or the harness is broken.
`ControlStrategy` separates them. It shares the stop, the target and the sizing
with `SpecStrategy` and differs only in the entry condition, so if it trades and
`SpecStrategy` does not, the difference is the strategy.

It is not a proposal. It is a textbook SMA cross with no claim to edge, chosen
because nobody will be tempted to deploy it.

## Results

`results/*.json` carries, for every run: the verdict, the data sha256, the window,
the fee rate, the strategy file's own sha256, the Jesse version, and the list of
per-trade returns. A result that cannot say where its numbers came from is not a
result.

Findings so far: [`RESULT_P0-1.md`](RESULT_P0-1.md).
