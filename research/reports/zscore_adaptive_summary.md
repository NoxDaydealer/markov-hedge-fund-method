# Z-Score + Adaptive RSI-Percentile Sweep — Summary

- Generated: 2026-05-28 09:43
- Round-trip cost: 0.12% (12bps)
- Go criteria: sharpe_per_bar >= 1.0, trades >= 5, net_return > 0.0

## Strategy logic

Long-only entries at next-bar open after both signals (or either, depending on entry_type) trigger.

- Z-score = (close - SMA(z_window)) / std(close, z_window)
  Buy candidate when Z-score <= -z_threshold (price far below mean).
- RSI percentile rank = rolling rank (pct=True) of RSI14 over `rsi_lookback` bars.
  Buy candidate when rank <= rsi_percentile/100 (adaptive oversold).
- Volume confirmation: prev-bar volume > SMA(vol_window) * vol_threshold.
- Exit: hold_period bars OR low <= entry - stop_atr * ATR14[entry-1].

## Sweep design

- Stage 1: full coarse grid (z_window x z_threshold x rsi_pct x rsi_lookback x hold x stop_atr x entry_type) = 19,200 combos per symbol, volume fixed at 20-bar / 1.5x.
- Stage 2: ±1 step neighborhood around top 20 Stage-1 configs, varying vol_threshold across {1.0, 1.5, 2.0}.

## BTCUSDT

- Bars: 20160 (2026-05-10 23:43:00 -> 2026-05-24 23:42:00)
- Stage 1 combos: 19200, Stage 2 combos: 1488, total: 20688
- Go combos: **0**
- CSV: `/root/trading/markov-strategy/research/reports/btcusdt_zscore_adaptive.csv`

### Best overall (no Go combo met all criteria)
```
stage=2 zwin=360 zthr=3.0 rsi_p=5%/50b hold=10 stop=1.5atr vol=1.0x/20b entry=and | trades= 42 wr=0.26 sharpe=-7.778 net=-0.0231 dd=-0.0248
```

## ETHUSDT

- Bars: 20160 (2026-05-10 23:44:00 -> 2026-05-24 23:43:00)
- Stage 1 combos: 19200, Stage 2 combos: 1944, total: 21144
- Go combos: **0**
- CSV: `/root/trading/markov-strategy/research/reports/ethusdt_zscore_adaptive.csv`

### Best overall (no Go combo met all criteria)
```
stage=2 zwin=360 zthr=3.0 rsi_p=10%/30b hold=10 stop=0.5atr vol=2.0x/20b entry=and | trades= 65 wr=0.23 sharpe=-8.720 net=-0.0375 dd=-0.0375
```

## Interpretation: adaptive vs fixed-RSI

Neither symbol produced Go combinations. Either the signal is genuinely sub-fee on this dataset window, or the 19,200-combo coarse grid still misses the relevant corner of the parameter space.
