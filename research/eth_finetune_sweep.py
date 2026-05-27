#!/usr/bin/env python3
"""ETHUSDT VWAP RSI — Fine-Tune Sweep (540 combos)"""
import sys
sys.path.insert(0, '/root/trading/markov-strategy')

import pandas as pd
from itertools import product
import csv
from research.bybit_intraday_strategy_sprint import (
    add_features, split_train_test, evaluate_reversion, ReversionParams
)

OUT = '/root/trading/markov-strategy/research/reports/ethusdt_vwap_rsi_finetune_sweep.csv'

# Fine-tune grid around best zone (vwap=60, z=360, zthr=2.0-2.5, rsi=35/65-70, vol=1.0, hold=20)
GRID = [
    ('vwap_window',    [50, 55, 60, 65, 70]),
    ('z_window',       [300, 330, 360, 390, 420]),
    ('z_threshold',    [1.8, 2.0, 2.2, 2.5]),
    ('rsi_long',       [30, 32, 35, 38]),
    ('rsi_short',      [60, 62, 65, 68, 70]),
    ('volume_multiple', [1.0]),
    ('atr_stop',       [0.6, 0.8, 1.0]),
    ('max_hold',       [15, 18, 20, 22, 25]),
]

print("Lade ETHUSDT...")
frame = pd.read_csv('/root/trading/markov-strategy/research/bybit_intraday_strategy_sprint/data/ETHUSDT_1m.csv')
frame['ts'] = pd.to_datetime(frame['timestamp'])
frame = frame.drop(columns=['timestamp']).set_index('ts').sort_index()
print(f"Bars: {len(frame)}")

print("Berechne Features...")
frame = add_features(frame)
train, test = split_train_test(frame)

params = [v for _, v in GRID]
combos = list(product(*params))
field_names = [n for n, _ in GRID]
print(f"Sweeping {len(combos)} combos...")

rows = []
for i, c in enumerate(combos):
    p = ReversionParams(
        vwap_window=c[0], z_window=c[1], z_threshold=c[2],
        rsi_long=c[3], rsi_short=c[4], volume_multiple=c[5],
        atr_period=14, atr_stop=c[6], max_hold=c[7], markov_gate='off'
    )
    try:
        pos, trades, net, train_m, test_m, all_m = evaluate_reversion(frame, p)
        rows.append({
            'vwap_window': c[0], 'z_window': c[1], 'z_threshold': c[2],
            'rsi_long': c[3], 'rsi_short': c[4], 'volume_multiple': c[5],
            'atr_stop': c[6], 'max_hold': c[7],
            'test_sharpe': round(test_m.sharpe_per_bar, 6),
            'test_trades': test_m.trades,
            'test_net_return': round(test_m.net_total_return, 6),
            'test_max_drawdown': round(test_m.max_drawdown, 6),
            'test_win_rate': round(test_m.win_rate, 4),
            'gate': 'go' if (test_m.sharpe_per_bar > 0.3 and test_m.trades >= 10 and test_m.max_drawdown > -0.10) else 'no_go',
        })
    except:
        pass
    if (i + 1) % 100 == 0:
        go_so_far = sum(1 for r in rows if r['gate'] == 'go')
        print(f"  {i+1}/{len(combos)} | Go: {go_so_far}")

rows.sort(key=lambda r: r['test_sharpe'], reverse=True)
go_rows = [r for r in rows if r['gate'] == 'go']
print(f"\n=== TOP 10 (von {len(go_rows)} Go-Kandidaten) ===")
for r in rows[:10]:
    print(f"  vwap={r['vwap_window']:2d} z={r['z_window']:3d} zthr={r['z_threshold']:.1f} "
          f"rsi={r['rsi_long']}/{r['rsi_short']} vol={r['volume_multiple']:.1f} "
          f"atr={r['atr_stop']:.1f} hold={r['max_hold']:2d} | "
          f"sharpe={r['test_sharpe']:+.3f} trades={r['test_trades']:>2d} "
          f"net={r['test_net_return']:+.4f} dd={r['test_max_drawdown']:+.4f} | {r['gate']}")

if rows:
    with open(OUT, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print(f"\nCSV: {OUT}")
