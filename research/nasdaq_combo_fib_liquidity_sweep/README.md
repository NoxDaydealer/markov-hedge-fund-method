# NASDAQ combo_fib_liquidity parameter sweep

Research-only follow-up for kanban task `t_7f686aea`. This does not touch broker APIs or live execution.

## Objective

The default `combo_fib_liquidity` settings were too sparse on NASDAQ proxies over five years: QQQ produced one trade, ^IXIC produced zero trades, and NQ=F produced one trade. This sweep tests whether a looser liquidity/fib variant can produce enough trades to be useful while remaining no-lookahead and cost-adjusted.

## Data and assumptions

- Assets: QQQ, ^IXIC, NQ=F via yfinance daily OHLCV.
- Window: 5y daily data fetched 2026-05-25, covering roughly 2021-05-24 through 2026-05-22/24.
- Split: first 60% train, last 40% held-out test.
- Execution: setup on bar close, shifted one bar, enter at next open, exit at following open.
- Combo trade cost: 10 bps round trip per completed one-bar trade.
- Markov-only baseline: walk-forward rolling-return Markov signal, shifted one bar, directional long/short daily exposure; modelled with 2 bps daily in-market friction.
- Buy-and-hold baseline: open-to-open long exposure.

## Parameter grid

The research script reimplements the existing strategy semantics but exposes sparse-rule knobs for exploration:

- lookback: 3, 5, 8, 10, 13, 20, 34
- fib_level: 0.382, 0.5, 0.618, 0.786
- require_candle_direction: true/false
- allow_shorts: true/false
- markov_gate: off, long_nonnegative, directional
- markov_window: 20, 40
- markov_threshold: 0.03, 0.05
- min_train for Markov matrix: 126, 252

Selection is by train Sharpe among variants with at least 8 train trades and max drawdown better than -25%. Test results are then reported out-of-sample.

## Train-selected out-of-sample results

| Asset | Selected params | Train trades / net / Sharpe | Test trades / net / Sharpe / maxDD | Buy-hold test net / Sharpe / maxDD | Markov-only test net / Sharpe / maxDD |
|---|---|---:|---:|---:|---:|
| QQQ | lookback=3, fib=0.382, no candle direction, shorts on, directional Markov, window=40, threshold=0.03, min_train=126 | 31 / +17.77% / 1.11 | 31 / +1.10% / 0.14 / -5.75% | +58.50% / 1.17 / -24.28% | +22.97% / 0.97 / -14.89% |
| ^IXIC | lookback=10, fib=0.786, no candle direction, shorts on, long_nonnegative Markov, window=20, threshold=0.05, min_train=252 | 10 / +5.89% / 1.08 | 0 / +0.00% / 0.00 / 0.00% | +57.63% / 1.12 / -25.54% | +28.61% / 1.13 / -11.39% |
| NQ=F | lookback=10, fib=0.382, no candle direction, shorts off, long_nonnegative Markov, window=40, threshold=0.05, min_train=126 | 13 / +6.57% / 1.17 | 10 / +2.93% / 0.69 / -1.09% | +57.35% / 1.13 / -23.10% | +25.52% / 1.02 / -11.30% |

## Default-settings sanity check

Closest default-compatible research setting, `lookback=20`, `fib_level=0.618`, candle direction required, shorts off, long allowed only when Markov non-negative:

| Asset | Trades | Gross total | Net after 10 bps/trade | Exposure |
|---|---:|---:|---:|---:|
| QQQ | 1 | +0.1925% | +0.0925% | 0.08% |
| ^IXIC | 0 | 0.0000% | 0.0000% | 0.00% |
| NQ=F | 1 | +0.1151% | +0.0151% | 0.08% |

This validates the original concern: default rules are effectively inert on NASDAQ daily data.

## Diagnostic best-test variants (not train-selected)

These are not deployable selections because they are chosen on the test set, but they show the rough ceiling under this grid:

- QQQ: best test Sharpe variant `lookback=8`, `fib=0.618`, no candle direction, shorts on, Markov off: 11 test trades, +5.90% net, Sharpe 1.25, maxDD -0.41%. Its train result was essentially flat (+0.04%, Sharpe 0.02), so it is not robust.
- ^IXIC: best test Sharpe variants cluster around `lookback=3`, `fib=0.786`, no candle direction, shorts on, Markov gated: 6 test trades, +2.44% net, Sharpe 0.99, maxDD -0.77%. Train was weak/negative for many variants.
- NQ=F: best test Sharpe variants cluster around `lookback=8`, `fib=0.5`, no candle direction, mostly long-only/Markov-gated: 12 test trades, +8.29% net, Sharpe 1.42, maxDD -1.27%. Train was negative, so it looks regime-specific rather than stable.

## Interpretation

1. Lower lookbacks and removing the candle-color requirement fix sparsity, but not alpha. QQQ activity improves from 1 trade to 31 held-out trades; NQ=F improves from 1 to 10; ^IXIC remains too sparse under train-selected rules.
2. Out-of-sample combo performance does not beat buy-and-hold or Markov-only on return or Sharpe for any asset. It does have far lower drawdown and very low exposure, so it is more of a rare tactical entry filter than a standalone allocation strategy.
3. Train-selected settings are unstable across proxies. QQQ wants very short lookback plus directional Markov; ^IXIC selects a short-only train artifact that disappears in test; NQ=F wants long-only Markov-gated lookback=10.
4. The Markov-only baseline is stronger than combo in held-out data on all three proxies, despite higher exposure and drawdown.

## Recommendation

Do not promote `combo_fib_liquidity` as a standalone NASDAQ daily strategy from this sweep. If it is kept, use it only as a low-exposure tactical overlay or alert generator, and prefer a simpler candidate for a second validation pass:

- Long-only NQ=F/QQQ variant: lookback 8-10, fib 0.5 or 0.382, no candle-color requirement, Markov long gate on.
- Require a minimum out-of-sample trade count per walk-forward fold before trusting Sharpe.
- Test multi-day holding/ATR stop-take-profit semantics next, because the current one-bar exit may be too short for liquidity-sweep setups.
- Keep Markov-only as the baseline to beat; the combo variant has not beaten it yet.

## Artifacts

- Script: `research/nasdaq_combo_fib_liquidity_sweep.py`
- Summary JSON: `research/nasdaq_combo_fib_liquidity_sweep/summary.json`
- Full sweep CSV: `research/nasdaq_combo_fib_liquidity_sweep/all_sweep_results.csv`
- Per-asset sweeps: `QQQ_sweep.csv`, `IXIC_sweep.csv`, `NQ_F_sweep.csv`
- Cached OHLCV data: `research/nasdaq_combo_fib_liquidity_sweep/data/`
