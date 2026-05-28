# Pairs Trading BTC/ETH — Z-Score Spread Reversion Sweep

- **Bars:** 20159 (14.00 days, 1m)
- **BTC/ETH 1m return correlation:** 0.8699
- **Combos tested:** 2520
- **Go combos** (sharpe>=1.0, trades>=10, net>0): **0**
- **Round-trip fee assumption:** 0.10% (maker 5bps × 2 legs)
- **Trailing-stop rule:** when active and max_pnl > 0.1%, exit if pnl falls below 50% of max_pnl

## Strategy
- spread = close_btc / close_eth
- z = (spread - SMA(spread, w)) / std(spread, w)
- z > +entry_zscore → SHORT spread (short BTC, long ETH); expect ratio to fall
- z < -entry_zscore → LONG spread (long BTC, short ETH); expect ratio to rise
- Exit on |z| < exit_zscore, |z| > stop_zscore, bars held >= hold_bars, or trailing stop
- Per-trade net = pos * (spread_exit/spread_entry - 1) - 0.001
- Sharpe annualized via sqrt(trades_per_year), where trades_per_year extrapolates from the sample window

## Baselines (single asset mean reversion)
- BTC mean reversion: -0.0003%/trade (broken)
- ETH mean reversion: +0.0156%/trade

## No Go Combos Found

None of the tested combos cleared sharpe>=1.0 / trades>=10 / net>0.

## Top 20 No-Go (closest to Go)

| sw | ent | ext | hold | stop | trail | trades | net | mean/tr | sharpe | win |
|---:|----:|----:|-----:|-----:|:-----:|-------:|----:|--------:|-------:|----:|
| 50 | 2.0 | 0.0 | 100 | 5.0 | False | 171 | -8.380% | -0.0490% | -9.5573 | 33.9% |
| 20 | 3.0 | 0.0 | 100 | 4.0 | False | 72 | -7.133% | -0.0991% | -11.6307 | 34.7% |
| 20 | 3.0 | 0.0 | 100 | 5.0 | False | 72 | -6.443% | -0.0895% | -12.0092 | 34.7% |
| 360 | 2.5 | 0.0 | 100 | 5.0 | False | 90 | -7.184% | -0.0798% | -13.1657 | 32.2% |
| 20 | 3.0 | 0.0 | 50 | 4.0 | False | 82 | -7.944% | -0.0969% | -14.5473 | 36.6% |
| 20 | 3.0 | 0.0 | 100 | 3.0 | False | 81 | -8.014% | -0.0989% | -14.8436 | 34.6% |
| 360 | 3.0 | 1.0 | 100 | 5.0 | False | 67 | -6.382% | -0.0953% | -15.3526 | 31.3% |
| 20 | 3.0 | 0.0 | 50 | 5.0 | False | 82 | -7.374% | -0.0899% | -15.6253 | 36.6% |
| 360 | 3.0 | 0.5 | 50 | 5.0 | False | 70 | -6.865% | -0.0981% | -16.3214 | 28.6% |
| 360 | 3.0 | 0.0 | 50 | 5.0 | False | 70 | -6.902% | -0.0986% | -16.3225 | 27.1% |
| 360 | 3.0 | 1.0 | 50 | 5.0 | False | 70 | -6.984% | -0.0998% | -16.7265 | 28.6% |
| 20 | 3.0 | 0.0 | 100 | 4.0 | True | 82 | -8.985% | -0.1096% | -16.8166 | 18.3% |
| 360 | 3.0 | 0.0 | 100 | 5.0 | False | 66 | -7.409% | -0.1123% | -16.8615 | 24.2% |
| 360 | 2.5 | 0.5 | 100 | 5.0 | False | 95 | -8.579% | -0.0903% | -16.9707 | 34.7% |
| 360 | 3.0 | 0.5 | 100 | 5.0 | False | 67 | -7.451% | -0.1112% | -17.0839 | 25.4% |
| 20 | 3.0 | 0.0 | 50 | 3.0 | False | 89 | -8.787% | -0.0987% | -17.0889 | 34.8% |
| 360 | 2.5 | 1.0 | 100 | 5.0 | False | 97 | -8.265% | -0.0852% | -17.4891 | 34.0% |
| 200 | 3.0 | 0.0 | 50 | 5.0 | False | 91 | -7.895% | -0.0868% | -17.5144 | 28.6% |
| 50 | 3.0 | 0.0 | 100 | 5.0 | False | 97 | -9.445% | -0.0974% | -17.6433 | 30.9% |
| 360 | 3.0 | 0.5 | 100 | 5.0 | True | 79 | -7.170% | -0.0908% | -17.8243 | 21.5% |

## Verdict: does pairs trading beat single-asset mean-reversion?

- No Go combo. On this dataset/fee model, pairs trading does not beat ETH mean-reversion.