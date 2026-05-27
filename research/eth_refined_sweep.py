#!/usr/bin/env python3
"""
ETHUSDT VWAP RSI Reversion — Verfeinerter Sweep (lokal, pandas)
Nutzt lokale ETHUSDT_1m.csv + existierende Framework-Funktionen.
"""
import sys, os
sys.path.insert(0, '/root/trading/markov-strategy')

import pandas as pd
import csv
from itertools import product
from research.bybit_intraday_strategy_sprint import (
    add_features, split_train_test, evaluate_reversion,
    ReversionParams, simulate_trades, compute_metrics,
)
import research.bybit_intraday_strategy_sprint as sprint

OUT = '/root/trading/markov-strategy/research/reports/ethusdt_vwap_rsi_refined_sweep.csv'

# Lade lokale CSV
print("Lade ETHUSDT von lokaler CSV...")
frame = pd.read_csv('/root/trading/markov-strategy/research/bybit_intraday_strategy_sprint/data/ETHUSDT_1m.csv')
frame['ts'] = pd.to_datetime(frame['timestamp'])
frame = frame.drop(columns=['timestamp']).set_index('ts').sort_index()
print(f"Geladen: {len(frame)} bars | Index: {type(frame.index).__name__}")

print("Berechne Features (pandas vectorized)...")
frame = add_features(frame)
train, test = split_train_test(frame)
print(f"Train: {len(train)} | Test: {len(test)}")

# Coarse Grid (4×3×3×3×3×2×2×2 = 2,592 combos ≈ 4-5 min)
# Fokus: um die beste Zone herum (vwap=120, z=240, zthr=2.0, rsi=35/70)
REFINED = [
    ('vwap_window',    [60, 90, 120, 180]),
    ('z_window',       [120, 240, 360]),
    ('z_threshold',    [1.5, 2.0, 2.5]),
    ('rsi_long',       [30, 35, 40]),
    ('rsi_short',      [65, 70, 75]),
    ('volume_multiple', [1.0, 1.2]),
    ('atr_stop',       [0.8, 1.2]),
    ('max_hold',       [10, 20]),
]

param_lists = [v for _, v in REFINED]
all_combos = list(product(*param_lists))
print(f"\nSweeping {len(all_combos)} Kombinationen (markov_gate='off', nur Longs)...")

rows = []
for i, combo in enumerate(all_combos):
    p = ReversionParams(
        vwap_window=combo[0], z_window=combo[1], z_threshold=combo[2],
        rsi_long=combo[3], rsi_short=combo[4], volume_multiple=combo[5],
        atr_period=14, atr_stop=combo[6], max_hold=combo[7], markov_gate='off',
    )
    try:
        pos, trades, net, train_m, test_m, all_m = evaluate_reversion(frame, p)
        rows.append({
            'vwap_window': combo[0], 'z_window': combo[1], 'z_threshold': combo[2],
            'rsi_long': combo[3], 'rsi_short': combo[4], 'volume_multiple': combo[5],
            'atr_stop': combo[6], 'max_hold': combo[7], 'markov_gate': 'off',
            'train_trades': train_m.trades,
            'test_trades': test_m.trades,
            'test_sharpe': round(test_m.sharpe_per_bar, 6),
            'test_net_return': round(test_m.net_total_return, 6),
            'test_max_drawdown': round(test_m.max_drawdown, 6),
            'test_win_rate': round(test_m.win_rate, 4),
            'train_sharpe': round(train_m.sharpe_per_bar, 6),
            'gate': 'go' if (test_m.sharpe_per_bar > 0.3 and test_m.trades >= 10 and test_m.max_drawdown > -0.10) else 'no_go',
        })
    except Exception as e:
        pass
    if (i + 1) % 100 == 0:
        print(f"  {i+1}/{len(all_combos)} done | Go so far: {sum(1 for r in rows if r['gate']=='go')}")

rows.sort(key=lambda r: r['test_sharpe'], reverse=True)

print(f"\n=== TOP 15 nach Test-Sharpe ===")
for r in rows[:15]:
    print(f"  vwap={r['vwap_window']:3d} z={r['z_window']:3d} zthr={r['z_threshold']:.1f} "
          f"rsi={r['rsi_long']}/{r['rsi_short']} vol={r['volume_multiple']:.1f} "
          f"atr={r['atr_stop']:.1f} hold={r['max_hold']:2d} | "
          f"sharpe={r['test_sharpe']:+.3f} trades={r['test_trades']:3d} "
          f"net={r['test_net_return']:+.4f} dd={r['test_max_drawdown']:+.4f} | {r['gate']}")

go_count = sum(1 for r in rows if r['gate'] == 'go')
print(f"\nGo-Kandidaten: {go_count}")
print(f"CSV: {OUT}")

if rows:
    with open(OUT, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print(f"OK: {len(rows)} rows geschrieben")