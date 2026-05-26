# Bybit Intraday Strategy Sprint Verdict

## Scope

Research-only evaluation for the Trading Hub HFT/paper-trading sprint. No broker keys and no real orders were used.

Data source: Bybit public REST `/v5/market/kline`, `category=linear`, 1m klines, no API key.

Sample:
- BTCUSDT: 20,160 one-minute bars, 2026-05-10 23:43 to 2026-05-24 23:42 UTC-ish naive timestamps.
- ETHUSDT: 20,160 one-minute bars, 2026-05-10 23:44 to 2026-05-24 23:43 UTC-ish naive timestamps.
- Split: 70% train / 30% holdout test.
- Cost model: 12 bps per completed trade, meant to cover taker fee plus spread/slippage placeholder.

Artifacts:
- Runner: `research/bybit_intraday_strategy_sprint.py`
- Machine summary: `research/bybit_intraday_strategy_sprint/summary.json`
- Baseline diagnostics: `research/bybit_intraday_strategy_sprint/baseline_diagnostics.json`
- Raw fetched OHLCV CSVs: `research/bybit_intraday_strategy_sprint/data/`
- Parameter sweeps: `research/bybit_intraday_strategy_sprint/*_sweep.csv`

## Strategies evaluated

1. VWAP + Volume + RSI mean reversion
   - Rolling VWAP distance z-score.
   - RSI oversold/overbought.
   - Volume spike against rolling median.
   - Reclaim/rejection confirmation.
   - Exit at VWAP, ATR stop, or time stop.
   - Markov gate tested as off / neutral-only / contrarian-ok.

2. Bollinger + VWAP momentum breakout
   - Bollinger squeeze percentile.
   - Breakout through band in VWAP direction.
   - Volume confirmation and RSI trend threshold.
   - ATR stop/trailing stop/time stop.
   - Markov gate tested as off / trend-only.

3. Markov usage
   - Markov is only a gate, not standalone alpha.
   - 15m labels from 4h return context produce a walk-forward transition score.
   - Reversion variants use neutral/contrarian filters; breakout variants use trend-only filter.

## Headline results

All train-selected variants failed the after-cost holdout test. Gross returns occasionally looked positive, especially on ETH mean reversion, but the 12 bps round-trip cost model consumed the edge.

### Selected train-first variants

| Symbol | Strategy | Test trades | Test gross return | Test net return | Test avg/trade net | Test profit factor | Trades/day |
|---|---:|---:|---:|---:|---:|---:|---:|
| BTCUSDT | VWAP/Volume/RSI Reversion | 26 | -0.86% | -3.91% | -0.153% | 0.46 | 6.19 |
| BTCUSDT | BB/VWAP Breakout | 32 | +0.17% | -3.60% | -0.115% | 1.45 | 7.62 |
| ETHUSDT | VWAP/Volume/RSI Reversion | 28 | +1.52% | -1.84% | -0.066% | 1.86 | 6.67 |
| ETHUSDT | BB/VWAP Breakout | 50 | +0.21% | -5.62% | -0.116% | 1.27 | 11.91 |

### Baselines and diagnostics

Buy-and-hold during the holdout was also negative:
- BTCUSDT test buy-and-hold: -0.38%.
- ETHUSDT test buy-and-hold: -1.36%.

Random same-frequency entry is strongly negative under 12 bps/trade, which confirms that high turnover dominates unless the gross edge is much larger than costs:
- BTC reversion random test median: -3.07%, p95: -2.73%.
- ETH reversion random test median: -3.30%, p95: -2.82%.
- BTC breakout random test median: -3.78%, p95: -3.38%.
- ETH breakout random test median: -5.83%, p95: -5.15%.

There are isolated grid members with positive holdout net return, but they are too sparse to trust:
- BTC reversion best-by-test net: +0.08% with only 3 test trades.
- ETH reversion best-by-test net: +0.20% with only 12 test trades.

Those fail the sprint's minimum 50-100 trade reliability criterion and are treated as overfit diagnostics, not candidates.

## Verdict: PARTIAL / NO-GO for paper reporting yet

The first implementation path should be VWAP + Volume + RSI mean reversion, not Bollinger/VWAP breakout, but only as a research adapter after the public data collector exists.

Reason:
- VWAP reversion produced more plausible gross behavior than breakout, especially on ETHUSDT.
- It achieved enough signal frequency for iteration, roughly 6-7 trades/day in selected variants.
- It is less dependent on fragile squeeze/breakout definitions and aligns better with the plan's first candidate.
- However, after conservative costs it is still negative on the holdout sample, so it is not ready for daily paper-trading reports or any serious capital path.

Bollinger/VWAP breakout should stay secondary. It generated more trades but worse cost drag and very low win rate in this simple implementation.

L2 orderbook imbalance should remain a feature/data prototype. It should not be promoted to a strategy until the collector can record orderbook/trade streams and the simulator can handle queue/latency assumptions conservatively.

## Implementation recommendation

1. Complete the Bybit public data collector first.
   - Persist 1m klines, public trades, orderbook.50, best bid/ask/spread.
   - This is already represented by child task `t_a24b517e`.

2. Implement `VWAPVolumeRSIReversionAdapter` as the first strategy adapter.
   - Use ETHUSDT and BTCUSDT 1m data.
   - Keep shorts paper-only.
   - Include the Markov gate as an optional filter, default off until it shows clear out-of-sample benefit.
   - Make cost/slippage/spread explicit and configurable.

3. Do not turn on daily paper reports until a longer walk-forward passes:
   - At least 30-60 days train, 7-14 days validation, 7-14 days test.
   - At least 50-100 holdout trades.
   - Positive after costs and still acceptable at 2x slippage.
   - Better than no-trade, buy-hold, random same-frequency, and naive VWAP-only.

4. Next research knobs for the adapter:
   - Lower fee model only if execution is maker-like and realistic; otherwise keep 12 bps conservative.
   - Add spread filter once best bid/ask is available.
   - Test longer VWAP windows and session VWAP resets.
   - Test exits that target partial VWAP reversion rather than full VWAP touch.
   - Segment metrics by Markov regime instead of relying on a single global gate.

## Bottom line

Choice: build the Bybit collector, then implement VWAP + Volume + RSI mean reversion as the first research adapter. It is the least-bad and most aligned candidate, but current evidence says no-go for live-like paper reporting until longer data, spread-aware costs, and walk-forward validation improve the after-cost result.
