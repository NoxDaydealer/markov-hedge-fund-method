#!/usr/bin/env python3
"""
Fine-Tune Parameter-Sweep fuer ETHUSDT VWAP RSI Reversion
Enger Grid um die beste Zone
"""

import sys
import itertools
import pandas as pd
from datetime import datetime

sys.path.insert(0, '/root/trading/markov-strategy')

from research.bybit_intraday_strategy_sprint import (
    add_features, split_train_test, evaluate_reversion, ReversionParams
)

# Fine-Tune Grid (eng um die beste Zone)
GRID = {
    'vwap_window': [50, 55, 60, 65, 70],
    'z_window': [300, 330, 360, 390, 420],
    'z_threshold': [1.8, 2.0, 2.2, 2.5],
    'rsi_long': [30, 32, 35, 38],
    'rsi_short': [60, 62, 65, 68, 70],
    'volume_multiple': [1.0],
    'atr_period': [14],
    'atr_stop': [0.6, 0.8, 1.0],
    'max_hold': [15, 18, 20, 22, 25],
}

MARKOV_GATE = 'off'

print("=" * 60)
print("ETHUSDT VWAP RSI Fine-Tune Parameter-Sweep")
print("=" * 60)
print(f"Startzeit: {datetime.now().strftime('%H:%M:%S')}")

# Daten laden
print("\nLade ETHUSDT Daten...")
data_path = '/root/trading/markov-strategy/research/bybit_intraday_strategy_sprint/data/ETHUSDT_1m.csv'
df = pd.read_csv(data_path, index_col='timestamp', parse_dates=True)
print(f"Geladen: {len(df)} Zeilen, {df.index.min()} bis {df.index.max()}")

# Features hinzufuegen
print("Berechne Features...")
df = add_features(df)

# Grid durchlaufen
keys = list(GRID.keys())
values = list(GRID.values())
total_combinations = 1
for v in values:
    total_combinations *= len(v)
print(f"\nGesamt Kombinationen: {total_combinations}")
print("-" * 60)

results = []
combo_num = 0

for combo in itertools.product(*values):
    combo_num += 1
    params = dict(zip(keys, combo))
    
    rev_params = ReversionParams(
        vwap_window=int(params['vwap_window']),
        z_window=int(params['z_window']),
        z_threshold=float(params['z_threshold']),
        rsi_long=float(params['rsi_long']),
        rsi_short=float(params['rsi_short']),
        volume_multiple=float(params['volume_multiple']),
        atr_period=int(params['atr_period']),
        atr_stop=float(params['atr_stop']),
        max_hold=int(params['max_hold']),
        markov_gate=MARKOV_GATE,
    )
    
    # Evaluierung auf Test-Daten
    pos, trades, net, train_m, test_m, all_m = evaluate_reversion(df, rev_params)
    
    result = {
        'vwap_window': params['vwap_window'],
        'z_window': params['z_window'],
        'z_threshold': params['z_threshold'],
        'rsi_long': params['rsi_long'],
        'rsi_short': params['rsi_short'],
        'volume_multiple': params['volume_multiple'],
        'atr_period': params['atr_period'],
        'atr_stop': params['atr_stop'],
        'max_hold': params['max_hold'],
        'train_trades': train_m.trades,
        'test_trades': test_m.trades,
        'train_sharpe': train_m.sharpe_per_bar,
        'test_sharpe': test_m.sharpe_per_bar,
        'train_max_dd': train_m.max_drawdown * 100,
        'test_max_dd': test_m.max_drawdown * 100,
        'train_total_return': train_m.net_total_return * 100,
        'test_total_return': test_m.net_total_return * 100,
        'train_win_rate': train_m.win_rate * 100,
        'test_win_rate': test_m.win_rate * 100,
        'train_profit_factor': train_m.profit_factor,
        'test_profit_factor': test_m.profit_factor,
    }
    results.append(result)
    
    if combo_num % 100 == 0:
        print(f"Fortschritt: {combo_num}/{total_combinations} ({100*combo_num/total_combinations:.1f}%)")

print(f"\nAbgeschlossen: {combo_num} Kombinationen getestet")
print(f"Endzeit: {datetime.now().strftime('%H:%M:%S')}")

# Ergebnisse sortieren nach Test Sharpe
results_df = pd.DataFrame(results)
results_df = results_df.sort_values('test_sharpe', ascending=False)

# Speichere CSV
output_path = '/root/trading/markov-strategy/research/reports/ethusdt_vwap_rsi_finetune_sweep.csv'
results_df.to_csv(output_path, index=False)
print(f"\nErgebnisse gespeichert: {output_path}")

# Top 10 Go-Kandidaten
print("\n" + "=" * 60)
print("TOP 10 GO-KANDIDATEN")
print("(Sharpe > 0.3, Trades >= 10, Max Drawdown > -10%)")
print("=" * 60)

go_candidates = results_df[
    (results_df['test_sharpe'] > 0.3) &
    (results_df['test_trades'] >= 10) &
    (results_df['test_max_dd'] > -10)
].head(10)

if len(go_candidates) > 0:
    for i, row in go_candidates.iterrows():
        rank = list(go_candidates.index).index(i) + 1
        print(f"\nRang {rank}:")
        print(f"  vwap_window: {int(row['vwap_window'])}")
        print(f"  z_window: {int(row['z_window'])}")
        print(f"  z_threshold: {row['z_threshold']}")
        print(f"  rsi_long: {int(row['rsi_long'])}")
        print(f"  rsi_short: {int(row['rsi_short'])}")
        print(f"  atr_stop: {row['atr_stop']}")
        print(f"  max_hold: {int(row['max_hold'])}")
        print(f"  Test-Trades: {int(row['test_trades'])}")
        print(f"  Test-Sharpe: {row['test_sharpe']:.3f}")
        print(f"  Test-MaxDD: {row['test_max_dd']:.1f}%")
        print(f"  Test-WinRate: {row['test_win_rate']:.1f}%")
        print(f"  Test-Return: {row['test_total_return']:.2f}%")
else:
    print("Keine Go-Kandidaten gefunden.")

print("\n" + "=" * 60)
print("ZUSAMMENFASSUNG")
print("=" * 60)
print(f"Totale Kombinationen: {combo_num}")
print(f"Go-Kandidaten gefunden: {len(go_candidates)}")
if len(results_df) > 0:
    print(f"Bestes Test-Sharpe: {results_df['test_sharpe'].max():.3f}")
    print(f"Bestes Test-MaxDD: {results_df['test_max_dd'].max():.1f}%")