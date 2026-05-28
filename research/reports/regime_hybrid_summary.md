# ADX Regime-Hybrid Strategy — Sweep Summary

- Generated: 2026-05-27 17:27
- Round-trip cost: 0.12% (12bps)
- Go criteria: sharpe_per_bar >= 1.0, trades >= 8, net_return > 0.0

## Strategy logic

Per-bar regime detection via ADX(period) (long-only):

- ADX < regime_adx_low  -> RANGING  -> mean reversion (z-score below threshold + RSI oversold)
- ADX > regime_adx_high -> TRENDING -> breakout (close above prior range high + volume confirm)
- Otherwise (transition zone) -> NO TRADE

Exit: hold expires OR low <= entry - stop_atr * ATR(14). Per-regime hold & stop.

## BTCUSDT

- Bars: 20160 (2026-05-10 23:43:00 -> 2026-05-24 23:42:00)
- Total combos evaluated: 8466
- Go combos: **0**
- CSV: `/root/trading/markov-strategy/research/reports/btcusdt_regime_hybrid.csv`

### Best overall (No Go combos met all criteria)
```
adx_p=20 lo=15 hi=35 | MR zwin=360 zthr=2.5 rsi<=30 hold=10 stop=1.2atr | BO lb=15 vol=2.5 hold=13 stop=2.3atr ent=close_break    | trades= 16(mr=  0/bo= 16) wr=0.25 sharpe=-2.533 net=-0.0065 dd=-0.0204
```

### Selected best params after Phase 4
- Regime: ADX(20), low=15, high=35
- MR best:    {'z_window': 360, 'z_threshold': 2.5, 'rsi_long': 35, 'hold': 15, 'stop_atr': 1.5}
- BO best:    {'lookback': 15, 'vol_threshold': 2.5, 'hold': 10, 'stop_atr': 2.0, 'entry': 'close_break'}

## ETHUSDT

- Bars: 20160 (2026-05-10 23:44:00 -> 2026-05-24 23:43:00)
- Total combos evaluated: 8466
- Go combos: **0**
- CSV: `/root/trading/markov-strategy/research/reports/ethusdt_regime_hybrid.csv`

### Best overall (No Go combos met all criteria)
```
adx_p=20 lo=15 hi=30 | MR zwin= 50 zthr=3.0 rsi<=30 hold=20 stop=0.8atr | BO lb=30 vol=2.5 hold=20 stop=1.7atr ent=close_break    | trades= 34(mr=  7/bo= 27) wr=0.38 sharpe=-0.456 net=-0.0021 dd=-0.0232
```

### Selected best params after Phase 4
- Regime: ADX(20), low=15, high=30
- MR best:    {'z_window': 50, 'z_threshold': 3.0, 'rsi_long': 30, 'hold': 20, 'stop_atr': 0.8}
- BO best:    {'lookback': 30, 'vol_threshold': 2.5, 'hold': 20, 'stop_atr': 2.0, 'entry': 'close_break'}

## Interpretation

Neither symbol produced Go combinations under this regime split. The transition zone (between regime_adx_low and regime_adx_high) and per-regime stop/hold pairing likely need a broader sweep, or the round-trip cost dominates.
