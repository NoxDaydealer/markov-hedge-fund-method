#!/usr/bin/env python3
"""
ETHUSDT VWAP RSI Reversion — Verfeinerter Parameter-Sweep
Optimiert: Vorab-Berechnung der teuren Indikatoren.
"""

import csv
import math
import datetime
import time
from typing import List, Dict, Any, Optional, Tuple

# ============================================================================
# DATA LOADING
# ============================================================================

def lade_ohlcv_1m(csv_pfad: str) -> List[Dict]:
    """Lädt ETHUSDT 1m OHLCV CSV."""
    rows = []
    with open(csv_pfad, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts_str = row['timestamp'].strip()
            try:
                ts = datetime.datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                continue
            try:
                rows.append({
                    'ts': ts,
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row['volume']),
                })
            except:
                continue
    return rows


# ============================================================================
# EFFIZIENTE ROLLING BERECHNUNGEN
# ============================================================================

def compute_vwap_efficient(tps: List[float], vols: List[float], window: int) -> List[Optional[float]]:
    """Effiziente VWAP-Berechnung mit kumulativer Summe."""
    n = len(tps)
    tp_vol_cumsum = [0.0] * (n + 1)
    vol_cumsum = [0.0] * (n + 1)
    
    for i in range(n):
        tp_vol_cumsum[i + 1] = tp_vol_cumsum[i] + tps[i] * vols[i]
        vol_cumsum[i + 1] = vol_cumsum[i] + vols[i]
    
    result = []
    for i in range(n):
        if i < window - 1:
            result.append(None)
        else:
            start = i - window + 1
            tp_vol = tp_vol_cumsum[i + 1] - tp_vol_cumsum[start]
            vol = vol_cumsum[i + 1] - vol_cumsum[start]
            result.append(tp_vol / vol if vol != 0 else None)
    return result


def rolling_mean_efficient(values: List[float], window: int) -> List[Optional[float]]:
    """Effiziente rolling mean mit kumulativer Summe (ignoriert None)."""
    n = len(values)
    cumsum = [0.0] * (n + 1)
    for i in range(n):
        v = values[i] if values[i] is not None else 0.0
        cumsum[i + 1] = cumsum[i] + v
    
    result = []
    for i in range(n):
        if i < window - 1:
            result.append(None)
        else:
            start = i - window + 1
            s = cumsum[i + 1] - cumsum[start]
            result.append(s / window)
    return result


def rolling_std_efficient(values: List[float], window: int) -> List[Optional[float]]:
    """Effiziente rolling std mit kumulativer Summe (ignoriert None)."""
    n = len(values)
    cumsum = [0.0] * (n + 1)
    cumsum_sq = [0.0] * (n + 1)
    for i in range(n):
        v = values[i] if values[i] is not None else 0.0
        cumsum[i + 1] = cumsum[i] + v
        cumsum_sq[i + 1] = cumsum_sq[i] + v * v
    
    result = []
    for i in range(n):
        if i < window - 1:
            result.append(None)
        else:
            start = i - window + 1
            count = window
            mean = (cumsum[i + 1] - cumsum[start]) / count
            mean_sq = (cumsum_sq[i + 1] - cumsum_sq[start]) / count
            variance = mean_sq - mean * mean
            result.append(math.sqrt(max(0.0, variance)))
    return result


def rolling_median_efficient(values: List[float], window: int) -> List[Optional[float]]:
    """Approximated rolling median - nutze Mittelpunkt der sortierten Window."""
    result = []
    for i in range(len(values)):
        if i < window - 1:
            result.append(None)
        else:
            start = i - window + 1
            window_vals = sorted(values[start:i + 1])
            mid = window // 2
            if window % 2 == 0:
                result.append((window_vals[mid - 1] + window_vals[mid]) / 2.0)
            else:
                result.append(window_vals[mid])
    return result


def ewm_rsi_approx(closes: List[float], period: int) -> List[float]:
    """RSI mit EWM-Approximation."""
    if len(closes) < 2:
        return [50.0] * len(closes)
    
    alpha = 2.0 / (period + 1)
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    deltas.insert(0, 0.0)
    
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]
    
    first_gain_avg = sum(gains[:period]) / period if period > 0 else 0.0
    first_loss_avg = sum(losses[:period]) / period if period > 0 else 0.0
    
    result = [50.0]
    gain_avg = first_gain_avg
    loss_avg = first_loss_avg
    
    for i in range(1, len(closes)):
        gain_avg = alpha * gains[i] + (1 - alpha) * gain_avg
        loss_avg = alpha * losses[i] + (1 - alpha) * loss_avg
        
        if loss_avg == 0:
            rs = 100.0
        else:
            rs = gain_avg / loss_avg
        
        rsi = 100.0 - (100.0 / (1.0 + rs))
        result.append(max(0.0, min(100.0, rsi)))
    
    return result


def stochrsi(rsi_values: List[float], period: int) -> List[float]:
    """Stochastic RSI."""
    result = []
    for i in range(len(rsi_values)):
        if i < period - 1:
            result.append(0.5)
        else:
            start = i - period + 1
            window = rsi_values[start:i + 1]
            rsi_min = min(window)
            rsi_max = max(window)
            if rsi_max == rsi_min:
                result.append(0.5)
            else:
                stoch = (rsi_values[i] - rsi_min) / (rsi_max - rsi_min)
                result.append(max(0.0, min(1.0, stoch)))
    return result


def compute_atr_efficient(highs: List[float], lows: List[float], closes: List[float], period: int) -> List[float]:
    """Effiziente ATR-Berechnung mit EWM-Approximation."""
    n = len(highs)
    if n < 2:
        return [0.0] * n
    
    trs = [highs[0] - lows[0]]
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        trs.append(max(hl, hc, lc))
    
    alpha = 2.0 / (period + 1)
    result = [trs[0]]
    for i in range(1, n):
        result.append(alpha * trs[i] + (1 - alpha) * result[i - 1])
    
    return result


def rolling_min_efficient(values: List[float], window: int) -> List[Optional[float]]:
    """Effiziente rolling min mit Deque-ähnlicher Logik."""
    result = []
    for i in range(len(values)):
        if i < window - 1:
            result.append(None)
        else:
            start = i - window + 1
            result.append(min(values[start:i + 1]))
    return result


def rolling_max_efficient(values: List[float], window: int) -> List[Optional[float]]:
    """Effiziente rolling max."""
    result = []
    for i in range(len(values)):
        if i < window - 1:
            result.append(None)
        else:
            start = i - window + 1
            result.append(max(values[start:i + 1]))
    return result


# ============================================================================
# PRE-COMPUTATION (teure Indikatoren einmalig)
# ============================================================================

def precompute_base_indicators(rows: List[Dict]) -> Dict:
    """Berechnet alle teuren Basis-Indikatoren vorab."""
    n = len(rows)
    highs = [r['high'] for r in rows]
    lows = [r['low'] for r in rows]
    closes = [r['close'] for r in rows]
    vols = [r['volume'] for r in rows]
    tps = [(highs[i] + lows[i] + closes[i]) / 3.0 for i in range(n)]
    
    print("  RSI...")
    rsi_vals = ewm_rsi_approx(closes, 14)
    
    print("  StochRSI...")
    stoch_vals = stochrsi(rsi_vals, 14)
    
    print("  ATR...")
    atr_vals = compute_atr_efficient(highs, lows, closes, 14)
    
    print("  Volume Median (window=60)...")
    vol_median = rolling_median_efficient(vols, 60)
    
    # Vorab-Berechnung für verschiedene vwap_windows
    print("  VWAP für windows [60, 90, 120, 180]...")
    vwap_windows = [60, 90, 120, 180]
    vwap_cache = {}
    for w in vwap_windows:
        vwap_cache[w] = compute_vwap_efficient(tps, vols, w)
    
    # Vorab-Berechnung für verschiedene z_windows
    print("  Z-score Komponenten für windows [120, 180, 240, 360]...")
    z_windows = [120, 180, 240, 360]
    dist_mean_cache = {}
    dist_std_cache = {}
    for w in z_windows:
        # VWAP distance für das default vwap_window=120
        vwap_120 = vwap_cache[120]
        dist = [closes[i] / vwap_120[i] - 1.0 if vwap_120[i] and vwap_120[i] != 0 else None for i in range(n)]
        dist_mean_cache[w] = rolling_mean_efficient(dist, w)
        dist_std_cache[w] = rolling_std_efficient(dist, w)
    
    # Z-score für verschiedene z_windows basierend auf VWAP distance mit window=120
    zscore_cache = {}
    for w in z_windows:
        vwap_120 = vwap_cache[120]
        dist = [closes[i] / vwap_120[i] - 1.0 if vwap_120[i] and vwap_120[i] != 0 else None for i in range(n)]
        dm = dist_mean_cache[w]
        ds = dist_std_cache[w]
        zscore_cache[w] = [
            (dist[i] - dm[i]) / ds[i] if dist[i] is not None and dm[i] is not None and ds[i] and ds[i] != 0 else 0.0
            for i in range(n)
        ]
    
    # Previous high/low
    prev_high = [None] + highs[:-1]
    prev_low = [None] + lows[:-1]
    
    return {
        'highs': highs,
        'lows': lows,
        'closes': closes,
        'vols': vols,
        'tps': tps,
        'rsi': rsi_vals,
        'stochrsi': stoch_vals,
        'atr': atr_vals,
        'vol_median': vol_median,
        'vwap': vwap_cache,
        'dist_mean': dist_mean_cache,
        'dist_std': dist_std_cache,
        'zscore': zscore_cache,
        'prev_high': prev_high,
        'prev_low': prev_low,
    }


# ============================================================================
# SIGNAL GENERATION (parametrisierte Version)
# ============================================================================

def generiere_signale(
    base: Dict,
    vwap_window: int,
    z_window: int,
    z_threshold: float,
    rsi_long: float,
    rsi_short: float,
    stochrsi_long: float,
    stochrsi_short: float,
    volume_multiple: float,
    atr_stop_multiple: float,
    atr_target_multiple: float,
    local_extreme_lookback: int,
) -> Tuple[List[int], List[Optional[float]], List[Optional[float]]]:
    """Generiert Signale basierend auf base indicators + parameter."""
    n = len(base['closes'])
    closes = base['closes']
    highs = base['highs']
    lows = base['lows']
    
    # Holen uns die gecachten Indikatoren
    vwap = base['vwap'][vwap_window]
    zscore = base['zscore'][z_window]
    rsi_vals = base['rsi']
    stoch_vals = base['stochrsi']
    atr_vals = base['atr']
    vol_median = base['vol_median']
    prev_high = base['prev_high']
    prev_low = base['prev_low']
    
    # Recent z-score min/max
    recent_z_min = rolling_min_efficient(zscore, local_extreme_lookback + 1)
    recent_z_max = rolling_max_efficient(zscore, local_extreme_lookback + 1)
    
    # Setup low/high for stop/target
    setup_low = rolling_min_efficient(lows, local_extreme_lookback)
    setup_high = rolling_max_efficient(highs, local_extreme_lookback)
    
    # Volume spike
    vol_spike = []
    for i in range(n):
        vm = vol_median[i]
        if vm is not None:
            vol_spike.append(base['vols'][i] >= volume_multiple * vm)
        else:
            vol_spike.append(False)
    
    # Rohsignale
    raw_signal = [0] * n
    
    for i in range(n):
        ph = prev_high[i]
        pl = prev_low[i]
        close = closes[i]
        o = base['tps'][i] * 3 - highs[i] - lows[i]  # approximiert
        
        if ph is None or pl is None or close is None:
            continue
        
        open_price = base['tps'][i] * 3 - highs[i] - lows[i]
        z = zscore[i]
        rsi = rsi_vals[i]
        stoch = stoch_vals[i]
        spike = vol_spike[i]
        vw = vwap[i]
        
        if vw is None:
            continue
        
        # Reclaim check
        reclaimed_long = (close > ph) and (close > open_price)
        reclaimed_short = (close < pl) and (close < open_price)
        
        long_setup = (
            (recent_z_min[i] is not None and recent_z_min[i] <= -z_threshold) and
            (rsi <= rsi_long) and
            (stoch <= stochrsi_long) and
            spike and
            reclaimed_long
        )
        
        short_setup = (
            (recent_z_max[i] is not None and recent_z_max[i] >= z_threshold) and
            (rsi >= rsi_short) and
            (stoch >= stochrsi_short) and
            spike and
            reclaimed_short
        )
        
        if long_setup and not short_setup:
            raw_signal[i] = 1
        elif short_setup and not long_setup:
            raw_signal[i] = -1
    
    # Execution signals (shifted by 1)
    execution_signal = [0] + raw_signal[:-1]
    
    # Stop/target prices
    stop_prices = [None] * n
    target_prices = [None] * n
    
    for i in range(1, n):
        if execution_signal[i] == 0:
            continue
        
        exec_price = base['tps'][i] * 3 - highs[i] - lows[i]
        prev_atr = atr_vals[i - 1]
        sl = setup_low[i - 1] if setup_low[i - 1] is not None else lows[i - 1]
        sh = setup_high[i - 1] if setup_high[i - 1] is not None else highs[i - 1]
        vw = vwap[i - 1]
        
        if prev_atr is None:
            continue
        
        if execution_signal[i] == 1:  # Long
            atr_stop = exec_price - atr_stop_multiple * prev_atr
            stop_price = max(atr_stop, sl)
            atr_target = exec_price + atr_target_multiple * prev_atr
            target_price = min(atr_target, vw if vw is not None else float('inf'))
            stop_prices[i] = stop_price
            target_prices[i] = target_price
            
        elif execution_signal[i] == -1:  # Short
            atr_stop = exec_price + atr_stop_multiple * prev_atr
            stop_price = min(atr_stop, sh)
            atr_target = exec_price - atr_target_multiple * prev_atr
            target_price = max(atr_target, vw if vw is not None else float('-inf'))
            stop_prices[i] = stop_price
            target_prices[i] = target_price
    
    return execution_signal, stop_prices, target_prices


# ============================================================================
# BACKTEST
# ============================================================================

def run_backtest(
    rows: List[Dict],
    execution_signals: List[int],
    stop_prices: List[Optional[float]],
    target_prices: List[Optional[float]],
    fee_bps: float = 2.0,
    spread_bps: float = 1.0,
) -> Dict[str, Any]:
    """Einfacher Backtest mit Trade-Tracking."""
    n = len(rows)
    closes = [r['close'] for r in rows]
    
    cost_pct = (fee_bps + spread_bps) / 10000.0
    equity_curve = [1.0]
    capital = 1.0
    trades = []
    position = None
    peak_capital = 1.0
    max_drawdown = 0.0
    
    for i in range(1, n):
        bar_return = 0.0
        
        if position is not None:
            entry_price = position['entry_price']
            entry_idx = position['entry_idx']
            side = position['side']
            current_price = closes[i]
            stop = stop_prices[i]
            target = target_prices[i]
            bars_held = i - entry_idx
            
            exit_this_bar = False
            exit_price = current_price
            exit_reason = 'end'
            
            if side == 1:  # Long
                if stop is not None and current_price <= stop:
                    exit_price = stop
                    exit_this_bar = True
                    exit_reason = 'stop'
                elif target is not None and current_price >= target:
                    exit_price = target
                    exit_this_bar = True
                    exit_reason = 'target'
            else:  # Short
                if stop is not None and current_price >= stop:
                    exit_price = stop
                    exit_this_bar = True
                    exit_reason = 'stop'
                elif target is not None and current_price <= target:
                    exit_price = target
                    exit_this_bar = True
                    exit_reason = 'target'
            
            if exit_this_bar:
                if side == 1:
                    pnl_pct = (exit_price - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - exit_price) / entry_price
                
                pnl_after_cost = pnl_pct - cost_pct
                trades.append({
                    'side': 'long' if side == 1 else 'short',
                    'pnl_pct': pnl_pct,
                })
                bar_return = pnl_after_cost
                position = None
        
        if position is None and execution_signals[i] != 0:
            side = execution_signals[i]
            entry_price = rows[i]['open']
            position = {'side': side, 'entry_idx': i, 'entry_price': entry_price}
        
        capital = capital * (1.0 + bar_return)
        equity_curve.append(capital)
        
        if capital > peak_capital:
            peak_capital = capital
        drawdown = (peak_capital - capital) / peak_capital
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    
    # Close open position at end
    if position is not None:
        last_close = closes[-1]
        entry_price = position['entry_price']
        side = position['side']
        if side == 1:
            pnl_pct = (last_close - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - last_close) / entry_price
        pnl_after_cost = pnl_pct - cost_pct
        capital = capital * (1.0 + pnl_after_cost)
        equity_curve[-1] = capital
    
    total_return = capital - 1.0
    pnl_bps = total_return * 10000.0
    trade_count = len(trades)
    wins = sum(1 for t in trades if t['pnl_pct'] > 0)
    win_rate = wins / trade_count if trade_count > 0 else 0.0
    max_drawdown_bps = max_drawdown * 10000.0
    
    # Sharpe
    if trade_count > 0 and len(equity_curve) > 1:
        returns = [equity_curve[i] / equity_curve[i-1] - 1.0 for i in range(1, len(equity_curve))]
        if len(returns) > 1:
            mean_ret = sum(returns) / len(returns)
            variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
            std_ret = math.sqrt(variance) if variance > 0 else 0.0
            if std_ret > 0:
                sharpe = (mean_ret / std_ret) * math.sqrt(50400)  # annualized
            else:
                sharpe = 0.0
        else:
            sharpe = 0.0
    else:
        sharpe = 0.0
    
    return {
        'net_total_return': total_return,
        'pnl_bps': pnl_bps,
        'trade_count': trade_count,
        'win_rate': win_rate,
        'max_drawdown_bps': max_drawdown_bps,
        'sharpe': sharpe,
    }


# ============================================================================
# PARAMETER SWEEP
# ============================================================================

def sweep_parameter():
    """Hauptfunktion: Parameter-Sweep durchführen."""
    data_pfad = '/root/trading/markov-strategy/research/bybit_intraday_strategy_sprint/data/ETHUSDT_1m.csv'
    output_pfad = '/root/trading/markov-strategy/research/reports/ethusdt_vwap_rsi_refined_sweep.csv'
    
    print("Lade Daten...")
    rows = lade_ohlcv_1m(data_pfad)
    print(f"Geladen: {len(rows)} Bars")
    
    # Precompute teure Indikatoren
    print("\nPre-compute Basis-Indikatoren...")
    start_precompute = time.time()
    base = precompute_base_indicators(rows)
    print(f"Vorab-Berechnung fertig in {time.time() - start_precompute:.1f}s")
    
    # Parameter-Ranges
    vwap_windows = [60, 90, 120, 180]
    z_windows = [120, 180, 240, 360]
    z_thresholds = [1.5, 2.0, 2.5, 3.0]
    rsi_longs = [25, 30, 35, 40, 45]
    rsi_shorts = [60, 65, 70, 75, 80]
    volume_multiples = [1.0, 1.2, 1.5]
    atr_stops = [0.6, 0.8, 1.0, 1.2]
    max_holds = [8, 10, 15, 20]
    markov_gates = ['off']
    
    # Fixed values
    stochrsi_long = 0.20
    stochrsi_short = 0.80
    atr_target_multiple = 1.5
    
    total = (
        len(vwap_windows) * len(z_windows) * len(z_thresholds) *
        len(rsi_longs) * len(rsi_shorts) * len(volume_multiples) *
        len(atr_stops) * len(max_holds) * len(markov_gates)
    )
    print(f"Total Kombinationen: {total}")
    
    results = []
    count = 0
    start_sweep = time.time()
    
    for vwap_win in vwap_windows:
        for z_win in z_windows:
            for z_thresh in z_thresholds:
                for rsi_l in rsi_longs:
                    for rsi_s in rsi_shorts:
                        for vol_mult in volume_multiples:
                            for atr_stop in atr_stops:
                                for max_hold in max_holds:
                                    for markov_gate in markov_gates:
                                        count += 1
                                        
                                        exec_signals, stop_prices, target_prices = generiere_signale(
                                            base,
                                            vwap_window=vwap_win,
                                            z_window=z_win,
                                            z_threshold=z_thresh,
                                            rsi_long=rsi_l,
                                            rsi_short=rsi_s,
                                            stochrsi_long=stochrsi_long,
                                            stochrsi_short=stochrsi_short,
                                            volume_multiple=vol_mult,
                                            atr_stop_multiple=atr_stop,
                                            atr_target_multiple=atr_target_multiple,
                                            local_extreme_lookback=max_hold,
                                        )
                                        
                                        bt = run_backtest(rows, exec_signals, stop_prices, target_prices)
                                        
                                        results.append({
                                            'vwap_window': vwap_win,
                                            'z_window': z_win,
                                            'z_threshold': z_thresh,
                                            'rsi_long': rsi_l,
                                            'rsi_short': rsi_s,
                                            'volume_multiple': vol_mult,
                                            'atr_stop': atr_stop,
                                            'max_hold': max_hold,
                                            'markov_gate': markov_gate,
                                            'test_sharpe': round(bt['sharpe'], 3),
                                            'test_trades': bt['trade_count'],
                                            'test_net_total_return': round(bt['net_total_return'], 6),
                                            'test_max_drawdown': round(bt['max_drawdown_bps'], 2),
                                            'win_rate': round(bt['win_rate'], 4),
                                        })
    
    elapsed = time.time() - start_sweep
    print(f"\nSweep fertig in {elapsed:.1f}s ({elapsed/count*1000:.1f}ms per Kombination)")
    
    # Sortiere nach Sharpe
    results.sort(key=lambda x: x['test_sharpe'], reverse=True)
    
    print("\n=== TOP 5 PARAMETER-SETS ===")
    for i, r in enumerate(results[:5]):
        print(f"{i+1}. sharpe={r['test_sharpe']}, trades={r['test_trades']}, "
              f"net={r['test_net_total_return']*100:.3f}%, dd={r['test_max_drawdown']:.1f}bps")
        print(f"   vwap={r['vwap_window']}, z={r['z_window']}, z_thresh={r['z_threshold']}, "
              f"rsi={r['rsi_long']}/{r['rsi_short']}, vol={r['volume_multiple']}, "
              f"atr={r['atr_stop']}, hold={r['max_hold']}")
    
    # Speichere CSV
    print(f"\nSpeichere {len(results)} Ergebnisse...")
    feldnamen = [
        'vwap_window', 'z_window', 'z_threshold', 'rsi_long', 'rsi_short',
        'volume_multiple', 'atr_stop', 'max_hold', 'markov_gate',
        'test_sharpe', 'test_trades', 'test_net_total_return', 'test_max_drawdown', 'win_rate'
    ]
    
    with open(output_pfad, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=feldnamen)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"Ergebnis gespeichert: {output_pfad}")
    return results


if __name__ == '__main__':
    sweep_parameter()