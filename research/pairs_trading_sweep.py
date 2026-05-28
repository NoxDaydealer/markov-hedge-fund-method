#!/usr/bin/env python3
"""
Pairs Trading BTC/ETH — Z-Score based spread reversion
BTC and ETH are loaded, aligned by timestamp, and we trade the BTC/ETH price ratio.
"""
import os
import csv
import numpy as np
import pandas as pd
from itertools import product

DATA_DIR = '/root/trading/markov-strategy/research/bybit_intraday_strategy_sprint/data'
REPORTS_DIR = '/root/trading/markov-strategy/research/reports'

FEE_ROUNDTRIP = 0.001
TRAIL_GIVEBACK = 0.5

PARAM_GRID = {
    'spread_window':     [20, 50, 100, 200, 360],
    'entry_zscore':      [1.5, 2.0, 2.5, 3.0],
    'exit_zscore':       [0.0, 0.5, 1.0],
    'hold_bars':         [5, 10, 15, 20, 30, 50, 100],
    'stop_zscore':       [3.0, 4.0, 5.0],
    'use_trailing_stop': [True, False],
}

print("=" * 70)
print("PAIRS TRADING BTC/ETH SWEEP")
print("=" * 70)

print("\nLoading data...")
btc = pd.read_csv(f'{DATA_DIR}/BTCUSDT_1m.csv', usecols=['timestamp', 'close'])
eth = pd.read_csv(f'{DATA_DIR}/ETHUSDT_1m.csv', usecols=['timestamp', 'close'])
btc['timestamp'] = pd.to_datetime(btc['timestamp'])
eth['timestamp'] = pd.to_datetime(eth['timestamp'])

merged = btc.merge(eth, on='timestamp', suffixes=('_btc', '_eth'), how='inner')
merged = merged.sort_values('timestamp').reset_index(drop=True)
n_bars = len(merged)
n_days = n_bars / 1440.0
print(f"Aligned bars: {n_bars}  |  days: {n_days:.2f}")
corr = merged['close_btc'].pct_change().corr(merged['close_eth'].pct_change())
print(f"1m return correlation: {corr:.4f}")

merged['spread'] = merged['close_btc'] / merged['close_eth']
spread_arr = merged['spread'].to_numpy(dtype=np.float64)
print(f"Spread (BTC/ETH) range: {spread_arr.min():.4f} - {spread_arr.max():.4f}")

print("\nPre-computing z-scores per window...")
z_by_window = {}
for w in PARAM_GRID['spread_window']:
    s = pd.Series(spread_arr)
    sma = s.rolling(w).mean().to_numpy()
    std = s.rolling(w).std().to_numpy()
    z = (spread_arr - sma) / std
    z_by_window[w] = z


def run_strategy(spread, z, entry_z, exit_z, hold_bars, stop_z, use_trailing, warmup_start):
    """Returns list of net per-trade returns (decimal) after fees."""
    n = len(spread)
    position = 0
    entry_idx = -1
    entry_spread = 0.0
    max_pnl = 0.0
    out = []

    for i in range(warmup_start, n):
        zi = z[i]
        if zi != zi:  # NaN check (fast)
            continue

        if position == 0:
            if zi > entry_z:
                position = -1
                entry_idx = i
                entry_spread = spread[i]
                max_pnl = 0.0
            elif zi < -entry_z:
                position = 1
                entry_idx = i
                entry_spread = spread[i]
                max_pnl = 0.0
        else:
            spread_change_pct = (spread[i] - entry_spread) / entry_spread
            pnl = position * spread_change_pct
            if pnl > max_pnl:
                max_pnl = pnl

            abs_z = zi if zi >= 0 else -zi
            bars_held = i - entry_idx

            exit_now = False
            if abs_z > stop_z:
                exit_now = True
            elif abs_z < exit_z:
                exit_now = True
            elif bars_held >= hold_bars:
                exit_now = True
            elif use_trailing and max_pnl > 0.001 and pnl < max_pnl * TRAIL_GIVEBACK:
                exit_now = True

            if exit_now:
                out.append(pnl - FEE_ROUNDTRIP)
                position = 0

    if position != 0:
        spread_change_pct = (spread[-1] - entry_spread) / entry_spread
        pnl = position * spread_change_pct
        out.append(pnl - FEE_ROUNDTRIP)

    return out


combos = list(product(
    PARAM_GRID['spread_window'],
    PARAM_GRID['entry_zscore'],
    PARAM_GRID['exit_zscore'],
    PARAM_GRID['hold_bars'],
    PARAM_GRID['stop_zscore'],
    PARAM_GRID['use_trailing_stop'],
))
print(f"\nTotal combos: {len(combos)}")

results = []
for idx, (sw, ent, ext, hb, stp, trail) in enumerate(combos):
    z = z_by_window[sw]
    warmup = sw + 50
    rets = run_strategy(spread_arr, z, ent, ext, hb, stp, trail, warmup)
    n_trades = len(rets)

    if n_trades == 0:
        results.append({
            'spread_window': sw, 'entry_zscore': ent, 'exit_zscore': ext,
            'hold_bars': hb, 'stop_zscore': stp, 'use_trailing_stop': trail,
            'total_trades': 0, 'net_return': 0.0, 'mean_return': 0.0,
            'std_return': 0.0, 'sharpe': 0.0, 'win_rate': 0.0,
            'gate': 'no_go',
        })
        continue

    arr = np.asarray(rets, dtype=np.float64)
    total = float(arr.sum())
    mean_r = float(arr.mean())
    std_r = float(arr.std(ddof=1)) if n_trades > 1 else 0.0
    win_rate = float((arr > 0).mean())

    if std_r > 0 and n_days > 0:
        trades_per_year = n_trades * (365.0 / n_days)
        sharpe = (mean_r / std_r) * np.sqrt(trades_per_year)
    else:
        sharpe = 0.0

    gate = 'go' if (sharpe >= 1.0 and n_trades >= 10 and total > 0) else 'no_go'

    results.append({
        'spread_window': sw, 'entry_zscore': ent, 'exit_zscore': ext,
        'hold_bars': hb, 'stop_zscore': stp, 'use_trailing_stop': trail,
        'total_trades': n_trades,
        'net_return': round(total, 6),
        'mean_return': round(mean_r, 7),
        'std_return': round(std_r, 7),
        'sharpe': round(float(sharpe), 4),
        'win_rate': round(win_rate, 4),
        'gate': gate,
    })

    if (idx + 1) % 250 == 0:
        n_go = sum(1 for r in results if r['gate'] == 'go')
        print(f"  {idx+1}/{len(combos)} done | Go so far: {n_go}")

results.sort(key=lambda r: (-r['sharpe'], -r['net_return']))
go_results = [r for r in results if r['gate'] == 'go']
no_go_results = [r for r in results if r['gate'] == 'no_go']
top_no_go = no_go_results[:20]

os.makedirs(REPORTS_DIR, exist_ok=True)
csv_path = f'{REPORTS_DIR}/pairs_trading_results.csv'
fields = ['spread_window', 'entry_zscore', 'exit_zscore', 'hold_bars',
          'stop_zscore', 'use_trailing_stop', 'total_trades', 'net_return',
          'mean_return', 'std_return', 'sharpe', 'win_rate', 'gate']
with open(csv_path, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for r in go_results:
        writer.writerow(r)
    for r in top_no_go:
        writer.writerow(r)
print(f"\nWrote CSV: {csv_path}")
print(f"  Go combos:        {len(go_results)}")
print(f"  Top no-go saved:  {len(top_no_go)}")

BTC_MEAN_REV = -0.000003   # -0.0003% per trade (broken)
ETH_MEAN_REV = 0.000156    # +0.0156% per trade

md = []
md.append("# Pairs Trading BTC/ETH — Z-Score Spread Reversion Sweep")
md.append("")
md.append(f"- **Bars:** {n_bars} ({n_days:.2f} days, 1m)")
md.append(f"- **BTC/ETH 1m return correlation:** {corr:.4f}")
md.append(f"- **Combos tested:** {len(combos)}")
md.append(f"- **Go combos** (sharpe>=1.0, trades>=10, net>0): **{len(go_results)}**")
md.append(f"- **Round-trip fee assumption:** {FEE_ROUNDTRIP*100:.2f}% (maker 5bps × 2 legs)")
md.append(f"- **Trailing-stop rule:** when active and max_pnl > 0.1%, exit if pnl falls below {int(TRAIL_GIVEBACK*100)}% of max_pnl")
md.append("")
md.append("## Strategy")
md.append("- spread = close_btc / close_eth")
md.append("- z = (spread - SMA(spread, w)) / std(spread, w)")
md.append("- z > +entry_zscore → SHORT spread (short BTC, long ETH); expect ratio to fall")
md.append("- z < -entry_zscore → LONG spread (long BTC, short ETH); expect ratio to rise")
md.append("- Exit on |z| < exit_zscore, |z| > stop_zscore, bars held >= hold_bars, or trailing stop")
md.append("- Per-trade net = pos * (spread_exit/spread_entry - 1) - 0.001")
md.append("- Sharpe annualized via sqrt(trades_per_year), where trades_per_year extrapolates from the sample window")
md.append("")
md.append("## Baselines (single asset mean reversion)")
md.append("- BTC mean reversion: -0.0003%/trade (broken)")
md.append("- ETH mean reversion: +0.0156%/trade")
md.append("")

if go_results:
    best = go_results[0]
    md.append("## Best Go Combo")
    md.append("")
    md.append(f"| param | value |")
    md.append(f"|---|---|")
    md.append(f"| spread_window | {best['spread_window']} |")
    md.append(f"| entry_zscore | {best['entry_zscore']} |")
    md.append(f"| exit_zscore | {best['exit_zscore']} |")
    md.append(f"| hold_bars | {best['hold_bars']} |")
    md.append(f"| stop_zscore | {best['stop_zscore']} |")
    md.append(f"| use_trailing_stop | {best['use_trailing_stop']} |")
    md.append(f"| total_trades | {best['total_trades']} |")
    md.append(f"| net_return | {best['net_return']*100:.3f}% |")
    md.append(f"| mean_return/trade | {best['mean_return']*100:.4f}% |")
    md.append(f"| std_return/trade | {best['std_return']*100:.4f}% |")
    md.append(f"| win_rate | {best['win_rate']*100:.2f}% |")
    md.append(f"| sharpe (annualized) | {best['sharpe']} |")
    md.append("")
    md.append("## Top 20 Go Combos")
    md.append("")
    md.append("| sw | ent | ext | hold | stop | trail | trades | net | mean/tr | sharpe | win |")
    md.append("|---:|----:|----:|-----:|-----:|:-----:|-------:|----:|--------:|-------:|----:|")
    for r in go_results[:20]:
        md.append(
            f"| {r['spread_window']} | {r['entry_zscore']} | {r['exit_zscore']} | "
            f"{r['hold_bars']} | {r['stop_zscore']} | {r['use_trailing_stop']} | "
            f"{r['total_trades']} | {r['net_return']*100:.3f}% | "
            f"{r['mean_return']*100:.4f}% | {r['sharpe']} | {r['win_rate']*100:.1f}% |"
        )
else:
    md.append("## No Go Combos Found")
    md.append("")
    md.append("None of the tested combos cleared sharpe>=1.0 / trades>=10 / net>0.")

md.append("")
md.append("## Top 20 No-Go (closest to Go)")
md.append("")
md.append("| sw | ent | ext | hold | stop | trail | trades | net | mean/tr | sharpe | win |")
md.append("|---:|----:|----:|-----:|-----:|:-----:|-------:|----:|--------:|-------:|----:|")
for r in top_no_go:
    md.append(
        f"| {r['spread_window']} | {r['entry_zscore']} | {r['exit_zscore']} | "
        f"{r['hold_bars']} | {r['stop_zscore']} | {r['use_trailing_stop']} | "
        f"{r['total_trades']} | {r['net_return']*100:.3f}% | "
        f"{r['mean_return']*100:.4f}% | {r['sharpe']} | {r['win_rate']*100:.1f}% |"
    )

md.append("")
md.append("## Verdict: does pairs trading beat single-asset mean-reversion?")
md.append("")
if go_results:
    best = go_results[0]
    beats_btc = best['mean_return'] > BTC_MEAN_REV
    beats_eth = best['mean_return'] > ETH_MEAN_REV
    md.append(f"- Best mean return/trade: **{best['mean_return']*100:.4f}%**")
    md.append(f"- vs BTC mean-rev (-0.0003%): **{'BEATS' if beats_btc else 'loses'}**")
    md.append(f"- vs ETH mean-rev (+0.0156%): **{'BEATS' if beats_eth else 'loses'}**")
    if beats_eth:
        md.append(f"- ➜ Pairs trading is the strongest signal in this sample window.")
    elif best['mean_return'] > 0:
        md.append(f"- ➜ Pairs trading is profitable but below ETH single-asset reversion.")
else:
    md.append("- No Go combo. On this dataset/fee model, pairs trading does not beat ETH mean-reversion.")

md_path = f'{REPORTS_DIR}/pairs_trading_analysis.md'
with open(md_path, 'w') as f:
    f.write('\n'.join(md))
print(f"Wrote MD:  {md_path}")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"Total combos tested: {len(combos)}")
print(f"Go combos:           {len(go_results)}")
if go_results:
    b = go_results[0]
    print("\nBest Go combo:")
    print(f"  spread_window={b['spread_window']}, entry={b['entry_zscore']}, "
          f"exit={b['exit_zscore']}, hold={b['hold_bars']}, "
          f"stop={b['stop_zscore']}, trailing={b['use_trailing_stop']}")
    print(f"  Sharpe(annualized)={b['sharpe']}  "
          f"NetReturn={b['net_return']*100:.3f}%  "
          f"WinRate={b['win_rate']*100:.2f}%  "
          f"Trades={b['total_trades']}  "
          f"Mean/trade={b['mean_return']*100:+.4f}%")
    print("\nComparison vs single-asset mean reversion:")
    print(f"  BTC mean-rev:   -0.0003%/trade  (broken)")
    print(f"  ETH mean-rev:   +0.0156%/trade")
    print(f"  Pairs (best):   {b['mean_return']*100:+.4f}%/trade")
    if b['mean_return'] > ETH_MEAN_REV:
        print("  ==> Pairs trading BEATS ETH mean-reversion.")
    elif b['mean_return'] > 0:
        print("  ==> Pairs trading is profitable but does NOT beat ETH mean-rev.")
    else:
        print("  ==> Pairs trading is unprofitable.")
else:
    print("\nNo Go combos found.")
    if top_no_go:
        b = top_no_go[0]
        print(f"\nBest non-go combo (reference):")
        print(f"  sw={b['spread_window']} ent={b['entry_zscore']} ext={b['exit_zscore']} "
              f"hold={b['hold_bars']} stop={b['stop_zscore']} trail={b['use_trailing_stop']}")
        print(f"  Sharpe={b['sharpe']} Net={b['net_return']*100:.3f}% "
              f"Win={b['win_rate']*100:.2f}% Trades={b['total_trades']}")
print("=" * 70)
