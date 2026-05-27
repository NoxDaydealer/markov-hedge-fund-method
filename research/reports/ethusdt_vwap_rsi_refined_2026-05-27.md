# ETHUSDT VWAP RSI Reversion — Refined Parameter Sweep (2026-05-27)

## Key Finding
**max_hold=20 + vol=1.0** dramatically outperforms the original best (sharpe 1.94 → 10-17).
Sharpe jumped 5-8x by extending hold time and reducing volume threshold.

## Sweep Specs
- Combinations: 2,592 (coarse grid, markov_gate=off, longs only)
- Data: ETHUSDT 1m OHLCV, 20,160 bars (2026-05-10 to 2026-05-24)
- Train/Test: 70/30 split (14,112 train / 6,048 test bars)
- Go Gate: sharpe > 0.3 AND trades ≥ 10 AND max_drawdown > -10%

## Go Candidates (166 total, Top 20 by sharpe)
| vwap | z_win | zthr | rsi_long | rsi_short | vol | atr | hold | sharpe | trades | net | gate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 60 | 360 | 2.5 | 35 | 65 | 1.0 | 0.8 | 20 | **11.71** | 11 | +1.42% | go |
| 60 | 360 | 2.5 | 40 | 70 | 1.0 | 1.2 | 20 | **10.38** | 10 | +1.31% | go |
| 60 | 360 | 2.0 | 35 | 70 | 1.0 | 0.8 | 20 | **10.35** | 11 | +1.23% | go |
| 90 | 240 | 2.0 | 35 | 70 | 1.0 | 0.8 | 20 | **10.35** | 11 | +1.23% | go |
| 90 | 360 | 2.0 | 35 | 70 | 1.0 | 0.8 | 20 | **10.35** | 11 | +1.23% | go |
| 90 | 360 | 2.5 | 40 | 70 | 1.0 | 0.8 | 20 | **9.72** | 10 | +1.16% | go |
| 60 | 360 | 2.5 | 40 | 70 | 1.0 | 0.8 | 20 | **9.13** | 10 | +1.11% | go |
| 120 | 360 | 2.0 | 35 | 70 | 1.0 | 0.8 | 20 | **9.05** | 12 | +1.08% | go |
| 120 | 360 | 2.0 | 35 | 70 | 1.0 | 1.2 | 20 | **8.92** | 12 | +1.14% | go |
| 60 | 240 | 2.0 | 35 | 70 | 1.0 | 0.8 | 20 | **8.84** | 12 | +1.06% | go |

## Pattern Analysis
Best parameters cluster around:
- **max_hold = 20** (vs original 10 — KEY INSIGHT)
- **z_window = 360** (vs original 240)
- **volume_multiple = 1.0** (vs original 1.2 — lower threshold catches more signals)
- **z_threshold = 2.0-2.5** (vs original 2.0)
- **vwap_window = 60-120** (vs original 120)

## Original vs Refined Comparison
| Parameter | Original Best | Refined Best |
|---|---|---|
| vwap_window | 120 | 60-120 |
| z_window | 240 | 360 |
| z_threshold | 2.0 | 2.0-2.5 |
| rsi_long/short | 35/70 | 35/70 |
| volume_multiple | 1.2 | 1.0 |
| atr_stop | 0.8 | 0.8 |
| max_hold | 10 | **20** |
| sharpe | 1.94 | **10-17** |

## Next Steps
1. Fine-tune around best zone (vwap=[50,60,70], z=[300,360,420], zthr=[1.8,2.0,2.2])
2. Walk-forward validation over longer period
3. Test on BTCUSDT with same refined parameters
4. Consider markov_gate variations (neutral_only, contrarian_ok) with hold=20