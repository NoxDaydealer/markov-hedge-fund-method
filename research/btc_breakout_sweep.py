#!/usr/bin/env python3
"""
BTC Breakout Strategy — Range/Consolidation Breakout Sweep
"""
import pandas as pd
import numpy as np
from itertools import product

DATA_PATH = "/root/trading/markov-strategy/research/bybit_intraday_strategy_sprint/data/BTCUSDT_1m.csv"
OUT_CSV = "/root/trading/markov-strategy/research/reports/btcusdt_breakout_sweep.csv"
OUT_MD = "/root/trading/markov-strategy/research/reports/btcusdt_breakout_sweep.md"
VENV_PY = "/root/trading/markov-strategy/.venv/bin/python"

def load_data():
    df = pd.read_csv(DATA_PATH)
    df.columns = [c.lower() for c in df.columns]
    df['ts'] = pd.to_datetime(df['ts'])
    df = df.sort_values('ts').reset_index(drop=True)
    df['ret'] = df['close'].pct_change()
    df['atr'] = df['high'].rolling(14).max() - df['low'].rolling(14).min()
    df['atr'] = df['atr'].fillna(df['atr'].mean())
    df['volume_ma'] = df['tickvol'].rolling(20).mean()
    df['adx'] = compute_adx(df)
    return df

def compute_adx(df, period=14):
    plus_dm = df['high'].diff()
    minus_dm = -df['low'].diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)
    tr = df['high'].rolling(period).max() - df['low'].rolling(period).min()
    tr = tr.fillna(df['close'].std())
    plus_di = 100 * (plus_dm.rolling(period).mean() / tr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / tr)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(period).mean()
    return adx.fillna(25)

def run_backtest(df, params, warmup):
    lookback, atr_mult, vol_thresh, hold, stop_atr, entry_type, use_adx, adx_thresh, adx_period = params
    
    trades = []
    in_pos = False
    entry_price = 0
    entry_bar = 0
    stop_price = 0
    hold_bars = hold
    
    range_high_arr = df['high'].rolling(lookback).max()
    range_low_arr = df['low'].rolling(lookback).min()
    bb_width = df['close'].rolling(20).std()
    bb_width_ma = bb_width.rolling(100).mean()
    
    for i in range(warmup, len(df)):
        if in_pos:
            bars_held = i - entry_bar
            current_stop = stop_price
            if bars_held >= hold_bars:
                pnl = (df['close'].iloc[i] - entry_price) / entry_price
                trades.append({'entry': entry_price, 'exit': df['close'].iloc[i], 'pnl': pnl, 'type': 'long', 'bars': bars_held, 'exit_reason': 'hold'})
                in_pos = False
            elif df['low'].iloc[i] <= current_stop:
                pnl = (current_stop - entry_price) / entry_price
                trades.append({'entry': entry_price, 'exit': current_stop, 'pnl': pnl, 'type': 'long', 'bars': bars_held, 'exit_reason': 'stop'})
                in_pos = False
        else:
            if use_adx and df['adx'].iloc[i] < adx_thresh:
                continue
            if pd.isna(range_high_arr.iloc[i]) or pd.isna(range_low_arr.iloc[i]):
                continue
            range_high = range_high_arr.iloc[i]
            range_low = range_low_arr.iloc[i]
            avg_vol = df['volume_ma'].iloc[i]
            cur_vol = df['tickvol'].iloc[i]
            atr_val = df['atr'].iloc[i]
            if pd.isna(avg_vol) or avg_vol == 0:
                continue
            vol_ratio = cur_vol / avg_vol if avg_vol > 0 else 0
            price = df['close'].iloc[i]
            prev_price = df['close'].iloc[i-1]
            if vol_ratio < vol_thresh:
                continue
            if price > range_high and vol_ratio >= vol_thresh:
                entry_price = price
                stop_price = price - stop_atr * atr_val
                entry_bar = i
                in_pos = True
    df_trades = pd.DataFrame(trades)
    if len(df_trades) == 0:
        return None
    gross = df_trades['pnl'].sum()
    net = gross - 0.0005  # ~5bps fee per trade (round trip ~10bps)
    sharpe = (df_trades['pnl'].mean() / (df_trades['pnl'].std() + 1e-10)) * np.sqrt(len(df_trades)) if df_trades['pnl'].std() > 0 else 0
    return {
        'total_trades': len(df_trades),
        'gross_return': gross,
        'net_return': net,
        'sharpe': sharpe,
        'win_rate': (df_trades['pnl'] > 0).mean(),
        'avg_win': df_trades.loc[df_trades['pnl'] > 0, 'pnl'].mean() if (df_trades['pnl'] > 0).any() else 0,
        'avg_loss': df_trades.loc[df_trades['pnl'] <= 0, 'pnl'].mean() if (df_trades['pnl'] <= 0).any() else 0,
        'max_drawdown': (df_trades['pnl'].cumsum() - df_trades['pnl'].cumsum().cummax()).min(),
    }

def main():
    print("Loading BTC data...")
    df = load_data()
    warmup = 200
    
    # Parameter grid
    lookbacks = [10, 15, 20, 25, 30, 40, 50]
    atr_mults = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
    vol_thresholds = [1.2, 1.5, 2.0, 2.5]
    holds = [5, 10, 15, 20, 25, 30, 40]
    stop_atrs = [0.5, 0.75, 1.0, 1.25, 1.5]
    entry_types = ['close_break']
    use_adx_opts = [False, True]
    adx_thresholds = [15, 20, 25]
    
    results = []
    combos = list(product(lookbacks, atr_mults, vol_thresholds, holds, stop_atrs, entry_types, use_adx_opts, adx_thresholds))
    print(f"Total combos: {len(combos)}")
    
    for idx, params in enumerate(combos):
        if idx % 5000 == 0:
            print(f"  Progress: {idx}/{len(combos)}")
        r = run_backtest(df, params, warmup)
        if r:
            r['params'] = str(params)
            r['lookback'], r['atr_mult'], r['vol_thresh'], r['hold'], r['stop_atr'], r['entry_type'], r['use_adx'], r['adx_thresh'] = params
            results.append(r)
    
    df_res = pd.DataFrame(results)
    if len(df_res) > 0:
        df_res = df_res.sort_values('sharpe', ascending=False)
        df_res.to_csv(OUT_CSV, index=False)
        print(f"\nGo results (sharpe>=1, trades>=5, net>0): {(df_res['sharpe']>=1).sum()}")
        print(f"Best sharpe: {df_res.iloc[0]['sharpe']:.2f} → {df_res.iloc[0]['params']}")
    
    # Summary markdown
    top_go = df_res[(df_res['sharpe'] >= 1) & (df_res['total_trades'] >= 5) & (df_res['net_return'] > 0)].head(10)
    summary = f"""# BTC Breakout Strategy Sweep Results

## Overview
- Total combos tested: {len(combos)}
- Go results (sharpe>=1, trades>=5, net>0): {len(top_go)}

## Best Results
"""
    for _, row in top_go.iterrows():
        summary += f"""
### sharpe={row['sharpe']:.2f}, net={row['net_return']*100:.2f}%, trades={row['total_trades']}
- lookback={row['lookback']}, atr_mult={row['atr_mult']}, vol_thresh={row['vol_thresh']}
- hold={row['hold']}, stop_atr={row['stop_atr']}, use_adx={row['use_adx']}, adx_thresh={row['adx_thresh']}
- win_rate={row['win_rate']*100:.0f}%, avg_win={row['avg_win']*100:.2f}%, avg_loss={row['avg_loss']*100:.2f}%
"""
    with open(OUT_MD, 'w') as f:
        f.write(summary)
    print(f"\nSaved to {OUT_CSV}")
    print(f"Saved summary to {OUT_MD}")

if __name__ == '__main__':
    main()