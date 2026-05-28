#!/usr/bin/env python3
"""
ADX Regime-Hybrid Strategy — Adaptive Mean Reversion + Breakout

Logic at each bar i (all setup features evaluated on i-1, entry at open[i+1]):
  - regime: classified by ADX(adx_period) on bar i-1
      adx_prev < regime_adx_low   -> RANGING  -> consider MR setup
      adx_prev > regime_adx_high  -> TRENDING -> consider BO setup
      else                        -> NO TRADE (transition zone)
  - MR (long-only): z(close - vwap_60) over z_window <= -z_threshold AND RSI(14) <= mr_rsi_long
  - BO (long-only): close > rolling_max(high, bo_lookback)[shift 1] AND volume > avg_vol * vol_threshold
                    (entry_type 'close_break' uses close; 'intraday_break' uses high)
  - Exit: hold expires OR low <= entry - stop_atr * ATR(14)

Run as nested 4-phase sweep to keep combinatorial cost manageable.

Outputs:
  research/reports/btcusdt_regime_hybrid.csv
  research/reports/ethusdt_regime_hybrid.csv
  research/reports/regime_hybrid_summary.md
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, '/root/trading/markov-strategy')
from research.bybit_intraday_strategy_sprint import add_features, ROUND_TRIP_COST

DATA_DIR = Path('/root/trading/markov-strategy/research/bybit_intraday_strategy_sprint/data')
REPORT_DIR = Path('/root/trading/markov-strategy/research/reports')
BARS_PER_YEAR = 365 * 24 * 60

GO_SHARPE = 1.0
GO_TRADES = 8
GO_NET = 0.0

# Phase 1 defaults (used while sweeping regime thresholds).
DEFAULT_MR = dict(z_window=360, z_threshold=2.0, rsi_long=35, hold=20, stop_atr=1.0)
DEFAULT_BO = dict(lookback=20, vol_threshold=2.0, hold=15, stop_atr=1.0, entry='close_break')

# Sweep grids.
PHASE1_GRID = dict(
    adx_period=[10, 14, 20],
    regime_adx_low=[15, 18, 20, 22, 25],
    regime_adx_high=[25, 28, 30, 35],
)
PHASE2_GRID = dict(  # MR fine-tune
    mr_z_window=[20, 30, 50, 100, 200, 360],
    mr_z_threshold=[1.5, 2.0, 2.5, 3.0],
    mr_rsi_long=[25, 30, 35],
    mr_hold=[10, 15, 20, 25],
    mr_stop_atr=[0.5, 0.8, 1.0, 1.5],
)
PHASE3_GRID = dict(  # BO fine-tune
    bo_lookback=[10, 15, 20, 30],
    bo_vol_threshold=[1.5, 2.0, 2.5],
    bo_hold=[5, 10, 15, 20],
    bo_stop_atr=[0.5, 1.0, 1.5, 2.0],
    bo_entry=['close_break', 'intraday_break'],
)

# Phase 4 fine-tune neighborhood (±1 step around best, narrow).
PHASE4_BAND = 2  # how many alternatives to test per param around best


# --------------------------------------------------------------------- helpers

def adx_series(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> np.ndarray:
    """Wilder's ADX (ewm smoothing, matches sprint module's ATR style)."""
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr_w = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr_w
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr_w
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean().fillna(0.0).to_numpy()


def vwap_window(high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray, window: int) -> np.ndarray:
    typical = (high + low + close) / 3.0
    tpv = pd.Series(typical * volume).rolling(window, min_periods=window).sum().to_numpy()
    vol_sum = pd.Series(volume).rolling(window, min_periods=window).sum().to_numpy()
    with np.errstate(divide='ignore', invalid='ignore'):
        return tpv / vol_sum


def rolling_max_prev(arr: np.ndarray, window: int) -> np.ndarray:
    return pd.Series(arr).rolling(window, min_periods=window).max().shift(1).to_numpy()


def rolling_mean_prev(arr: np.ndarray, window: int) -> np.ndarray:
    return pd.Series(arr).rolling(window, min_periods=window).mean().shift(1).to_numpy()


def zscore_window(series: np.ndarray, window: int) -> np.ndarray:
    s = pd.Series(series)
    mean = s.rolling(window, min_periods=window).mean()
    std = s.rolling(window, min_periods=window).std(ddof=0)
    with np.errstate(divide='ignore', invalid='ignore'):
        return ((s - mean) / std).to_numpy()


# --------------------------------------------------------------------- simulation

def simulate_hybrid(
    opens: np.ndarray, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    atrs: np.ndarray,
    cand_idx: np.ndarray, cand_sources: np.ndarray,  # 0=MR, 1=BO
    mr_hold: int, mr_stop: float,
    bo_hold: int, bo_stop: float,
    n_bars: int,
) -> list[tuple[int, int, int, float, float, int]]:
    """Walk candidate entries in chronological order; non-overlapping.

    Returns list of (entry_bar, exit_bar, side, gross, net, source).
    Side is always +1 (long-only spec). cand_sources distinguishes MR vs BO so
    we can apply per-regime hold/stop without re-tagging trades later.
    """
    trades: list[tuple[int, int, int, float, float, int]] = []
    in_trade_until = -1
    for k in range(len(cand_idx)):
        i = int(cand_idx[k])
        # Entry occurs at next-bar open; we need the i+1 row to exist.
        if i + 1 >= n_bars:
            continue
        if (i + 1) <= in_trade_until:
            continue
        atr_v = float(atrs[i])
        if not np.isfinite(atr_v) or atr_v <= 0:
            continue
        source = int(cand_sources[k])
        if source == 0:
            hold = mr_hold
            stop_mult = mr_stop
        else:
            hold = bo_hold
            stop_mult = bo_stop
        entry_i = i + 1
        entry_price = float(opens[entry_i])
        stop_price = entry_price - stop_mult * atr_v
        end = entry_i + hold
        if end > n_bars - 1:
            end = n_bars - 1
        window_lows = lows[entry_i + 1:end + 1]
        if window_lows.size > 0:
            hits = window_lows <= stop_price
            if hits.any():
                first = int(np.argmax(hits))
                exit_bar = entry_i + 1 + first
                exit_price = stop_price
            else:
                exit_bar = end
                exit_price = float(closes[end])
        else:
            exit_bar = entry_i
            exit_price = float(closes[entry_i])
        gross = (exit_price / entry_price - 1.0)
        net = gross - ROUND_TRIP_COST
        trades.append((entry_i, exit_bar, 1, float(gross), float(net), source))
        in_trade_until = exit_bar
    return trades


def metrics_from_trades(trades: list[tuple[int, int, int, float, float, int]], n_bars: int) -> dict:
    if not trades:
        return {
            'trades': 0, 'mr_trades': 0, 'bo_trades': 0,
            'wins': 0, 'losses': 0, 'win_rate': 0.0,
            'gross_total_return': 0.0, 'net_total_return': 0.0,
            'avg_trade_return_net': 0.0,
            'sharpe_per_bar': 0.0, 'max_drawdown': 0.0,
            'exposure': 0.0,
        }
    grosses = np.array([t[3] for t in trades])
    nets = np.array([t[4] for t in trades])
    sources = np.array([t[5] for t in trades])
    wins = int((nets > 0).sum())
    losses = int((nets < 0).sum())

    per_bar = np.zeros(n_bars, dtype=float)
    exposure_bars = 0
    for entry, exit_bar, _, _, net, _ in trades:
        per_bar[exit_bar] += net
        exposure_bars += exit_bar - entry

    std = float(per_bar.std(ddof=0))
    sharpe = float((per_bar.mean() / std) * np.sqrt(BARS_PER_YEAR)) if std > 0 else 0.0
    equity = np.cumprod(1.0 + per_bar)
    peak = np.maximum.accumulate(equity)
    drawdown = equity / peak - 1.0
    return {
        'trades': int(len(trades)),
        'mr_trades': int((sources == 0).sum()),
        'bo_trades': int((sources == 1).sum()),
        'wins': wins, 'losses': losses,
        'win_rate': wins / len(trades),
        'gross_total_return': float(np.prod(1.0 + grosses) - 1.0),
        'net_total_return': float(equity[-1] - 1.0),
        'avg_trade_return_net': float(nets.mean()),
        'sharpe_per_bar': sharpe,
        'max_drawdown': float(drawdown.min()),
        'exposure': exposure_bars / n_bars,
    }


# --------------------------------------------------------------------- combo runner

@dataclass(frozen=True)
class HybridConfig:
    adx_period: int
    regime_adx_low: float
    regime_adx_high: float
    mr_z_window: int
    mr_z_threshold: float
    mr_rsi_long: float
    mr_hold: int
    mr_stop_atr: float
    bo_lookback: int
    bo_vol_threshold: float
    bo_hold: int
    bo_stop_atr: float
    bo_entry: str

    def asdict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__.keys()}


class Symbol:
    """Holds the per-symbol numpy arrays and caches ADX per period."""

    def __init__(self, name: str, frame: pd.DataFrame) -> None:
        self.name = name
        self.frame = frame
        self.opens = frame['open'].to_numpy()
        self.highs = frame['high'].to_numpy()
        self.lows = frame['low'].to_numpy()
        self.closes = frame['close'].to_numpy()
        self.volumes = frame['volume'].to_numpy()
        self.atrs = frame['atr14'].to_numpy()
        self.rsi = frame['rsi14'].to_numpy()
        self.n_bars = len(frame)
        # Cache shifted ADX per period.
        self._adx_cache: dict[int, np.ndarray] = {}
        # Cache rolling max(high) per bo_lookback.
        self._bo_high_cache: dict[int, np.ndarray] = {}
        self._bo_vol_cache: dict[int, np.ndarray] = {}
        # Cache vwap-distance and zscore per (vwap_window, z_window). vwap_window fixed at 60.
        self._z_cache: dict[int, np.ndarray] = {}
        self._dist60: np.ndarray | None = None

    def adx_prev(self, period: int) -> np.ndarray:
        if period not in self._adx_cache:
            arr = adx_series(self.frame['high'], self.frame['low'], self.frame['close'], period)
            self._adx_cache[period] = pd.Series(arr).shift(1).to_numpy()
        return self._adx_cache[period]

    def bo_high_prev(self, lookback: int) -> np.ndarray:
        if lookback not in self._bo_high_cache:
            self._bo_high_cache[lookback] = rolling_max_prev(self.highs, lookback)
        return self._bo_high_cache[lookback]

    def bo_vol_prev(self, lookback: int) -> np.ndarray:
        if lookback not in self._bo_vol_cache:
            self._bo_vol_cache[lookback] = rolling_mean_prev(self.volumes, lookback)
        return self._bo_vol_cache[lookback]

    def z_prev(self, z_window: int) -> np.ndarray:
        if z_window not in self._z_cache:
            if self._dist60 is None:
                vwap60 = vwap_window(self.highs, self.lows, self.closes, self.volumes, 60)
                with np.errstate(divide='ignore', invalid='ignore'):
                    self._dist60 = self.closes / vwap60 - 1.0
            z = zscore_window(self._dist60, z_window)
            self._z_cache[z_window] = pd.Series(z).shift(1).to_numpy()
        return self._z_cache[z_window]


def evaluate(sym: Symbol, cfg: HybridConfig) -> dict:
    adx_prev = sym.adx_prev(cfg.adx_period)
    ranging = adx_prev < cfg.regime_adx_low
    trending = adx_prev > cfg.regime_adx_high

    # MR setup (long only) on bar i, evaluated using prev-bar features.
    z_prev = sym.z_prev(cfg.mr_z_window)
    rsi_prev = pd.Series(sym.rsi).shift(1).to_numpy()
    mr_signal = (
        ranging
        & np.isfinite(z_prev) & (z_prev <= -cfg.mr_z_threshold)
        & np.isfinite(rsi_prev) & (rsi_prev <= cfg.mr_rsi_long)
    )

    # BO setup (long only).
    bo_high_prev = sym.bo_high_prev(cfg.bo_lookback)
    bo_vol_prev = sym.bo_vol_prev(cfg.bo_lookback)
    vol_ok = sym.volumes > (bo_vol_prev * cfg.bo_vol_threshold)
    if cfg.bo_entry == 'close_break':
        breakout = sym.closes > bo_high_prev
    else:
        breakout = sym.highs > bo_high_prev
    bo_signal = trending & breakout & vol_ok & np.isfinite(bo_high_prev)

    # Combine — MR/BO regimes are mutually exclusive so no conflict by construction.
    sig_any = mr_signal | bo_signal
    cand_idx = np.where(sig_any)[0]
    # source: 0 = MR, 1 = BO. (Both can't be true on same bar — different regime.)
    sources = np.where(bo_signal[cand_idx], 1, 0)

    trades = simulate_hybrid(
        sym.opens, sym.highs, sym.lows, sym.closes, sym.atrs,
        cand_idx, sources,
        cfg.mr_hold, cfg.mr_stop_atr,
        cfg.bo_hold, cfg.bo_stop_atr,
        sym.n_bars,
    )
    m = metrics_from_trades(trades, sym.n_bars)
    return m


def make_cfg(regime: dict, mr: dict, bo: dict) -> HybridConfig:
    return HybridConfig(
        adx_period=int(regime['adx_period']),
        regime_adx_low=float(regime['regime_adx_low']),
        regime_adx_high=float(regime['regime_adx_high']),
        mr_z_window=int(mr['z_window']),
        mr_z_threshold=float(mr['z_threshold']),
        mr_rsi_long=float(mr['rsi_long']),
        mr_hold=int(mr['hold']),
        mr_stop_atr=float(mr['stop_atr']),
        bo_lookback=int(bo['lookback']),
        bo_vol_threshold=float(bo['vol_threshold']),
        bo_hold=int(bo['hold']),
        bo_stop_atr=float(bo['stop_atr']),
        bo_entry=str(bo['entry']),
    )


# --------------------------------------------------------------------- sweep phases

def gate(row: dict) -> str:
    if (
        row['sharpe_per_bar'] >= GO_SHARPE
        and row['trades'] >= GO_TRADES
        and row['net_total_return'] > GO_NET
    ):
        return 'go'
    return 'no_go'


def add_row(rows: list, cfg: HybridConfig, m: dict, phase: int) -> None:
    row = {'phase': phase, **cfg.asdict(), **m}
    row['gate'] = gate(row)
    rows.append(row)


def phase1(sym: Symbol, rows: list, log: list) -> list[dict]:
    """Sweep regime thresholds. Returns sorted list of (regime_dict, metrics)."""
    t0 = time.time()
    combos = list(product(
        PHASE1_GRID['adx_period'],
        PHASE1_GRID['regime_adx_low'],
        PHASE1_GRID['regime_adx_high'],
    ))
    n_total = len(combos)
    log.append(f"[{sym.name}] Phase 1: {n_total} regime combos")
    out: list[tuple[dict, dict, HybridConfig]] = []
    for i, (p, lo, hi) in enumerate(combos):
        if lo >= hi:
            continue
        regime = dict(adx_period=p, regime_adx_low=lo, regime_adx_high=hi)
        cfg = make_cfg(regime, DEFAULT_MR, DEFAULT_BO)
        m = evaluate(sym, cfg)
        add_row(rows, cfg, m, 1)
        out.append((regime, m, cfg))
    # Score: prefer sharpe but require activity.
    out.sort(key=lambda x: (x[1]['sharpe_per_bar'], x[1]['trades']), reverse=True)
    log.append(f"[{sym.name}] Phase 1 done in {time.time()-t0:.1f}s. "
               f"Best: adx={out[0][0]['adx_period']} lo={out[0][0]['regime_adx_low']} hi={out[0][0]['regime_adx_high']} "
               f"sharpe={out[0][1]['sharpe_per_bar']:+.3f} trades={out[0][1]['trades']} net={out[0][1]['net_total_return']:+.4f}")
    return [r for r, _, _ in out[:5]]


def phase2(sym: Symbol, top_regimes: list[dict], rows: list, log: list) -> tuple[dict, dict]:
    """Sweep MR params under each top regime. Returns best (regime, mr_params)."""
    t0 = time.time()
    combos = list(product(
        PHASE2_GRID['mr_z_window'],
        PHASE2_GRID['mr_z_threshold'],
        PHASE2_GRID['mr_rsi_long'],
        PHASE2_GRID['mr_hold'],
        PHASE2_GRID['mr_stop_atr'],
    ))
    n_total = len(combos) * len(top_regimes)
    log.append(f"[{sym.name}] Phase 2: {n_total} MR combos")
    best: tuple[float, dict, dict] | None = None
    eval_count = 0
    for regime in top_regimes:
        for (zw, zt, rsi_l, hold, stp) in combos:
            mr = dict(z_window=zw, z_threshold=zt, rsi_long=rsi_l, hold=hold, stop_atr=stp)
            cfg = make_cfg(regime, mr, DEFAULT_BO)
            m = evaluate(sym, cfg)
            add_row(rows, cfg, m, 2)
            score = m['sharpe_per_bar'] if m['mr_trades'] >= 5 else -1e9
            if best is None or score > best[0]:
                best = (score, regime, mr)
            eval_count += 1
            if eval_count % 1000 == 0:
                log.append(f"[{sym.name}]   Phase 2 {eval_count}/{n_total} t={time.time()-t0:.0f}s")
    assert best is not None
    log.append(f"[{sym.name}] Phase 2 done in {time.time()-t0:.1f}s. "
               f"Best MR score={best[0]:.3f} params={best[2]}")
    return best[1], best[2]


def phase3(sym: Symbol, top_regimes: list[dict], rows: list, log: list) -> tuple[dict, dict]:
    """Sweep BO params under each top regime."""
    t0 = time.time()
    combos = list(product(
        PHASE3_GRID['bo_lookback'],
        PHASE3_GRID['bo_vol_threshold'],
        PHASE3_GRID['bo_hold'],
        PHASE3_GRID['bo_stop_atr'],
        PHASE3_GRID['bo_entry'],
    ))
    n_total = len(combos) * len(top_regimes)
    log.append(f"[{sym.name}] Phase 3: {n_total} BO combos")
    best: tuple[float, dict, dict] | None = None
    eval_count = 0
    for regime in top_regimes:
        for (lb, vt, hold, stp, ent) in combos:
            bo = dict(lookback=lb, vol_threshold=vt, hold=hold, stop_atr=stp, entry=ent)
            cfg = make_cfg(regime, DEFAULT_MR, bo)
            m = evaluate(sym, cfg)
            add_row(rows, cfg, m, 3)
            score = m['sharpe_per_bar'] if m['bo_trades'] >= 5 else -1e9
            if best is None or score > best[0]:
                best = (score, regime, bo)
            eval_count += 1
            if eval_count % 1000 == 0:
                log.append(f"[{sym.name}]   Phase 3 {eval_count}/{n_total} t={time.time()-t0:.0f}s")
    assert best is not None
    log.append(f"[{sym.name}] Phase 3 done in {time.time()-t0:.1f}s. "
               f"Best BO score={best[0]:.3f} params={best[2]}")
    return best[1], best[2]


def phase4(sym: Symbol, best_regime: dict, best_mr: dict, best_bo: dict, rows: list, log: list) -> dict:
    """Fine-tune around combined best settings."""
    t0 = time.time()
    # Build a small neighborhood around best for key params.
    z_thr_band = [max(1.0, best_mr['z_threshold'] - 0.5), best_mr['z_threshold'], best_mr['z_threshold'] + 0.5]
    rsi_band = [max(20, best_mr['rsi_long'] - 5), best_mr['rsi_long'], min(40, best_mr['rsi_long'] + 5)]
    mr_stop_band = [max(0.3, best_mr['stop_atr'] - 0.3), best_mr['stop_atr'], best_mr['stop_atr'] + 0.3]
    mr_hold_band = [max(5, best_mr['hold'] - 5), best_mr['hold'], best_mr['hold'] + 5]
    bo_stop_band = [max(0.3, best_bo['stop_atr'] - 0.3), best_bo['stop_atr'], best_bo['stop_atr'] + 0.3]
    bo_hold_band = [max(3, best_bo['hold'] - 3), best_bo['hold'], best_bo['hold'] + 3]
    combos = list(product(z_thr_band, rsi_band, mr_stop_band, mr_hold_band, bo_stop_band, bo_hold_band))
    n_total = len(combos)
    log.append(f"[{sym.name}] Phase 4: {n_total} fine-tune combos around best")
    best: tuple[float, dict] | None = None
    for (zt, rsi_l, mr_stp, mr_h, bo_stp, bo_h) in combos:
        mr = dict(z_window=best_mr['z_window'], z_threshold=zt, rsi_long=rsi_l, hold=mr_h, stop_atr=mr_stp)
        bo = dict(lookback=best_bo['lookback'], vol_threshold=best_bo['vol_threshold'],
                  hold=bo_h, stop_atr=bo_stp, entry=best_bo['entry'])
        cfg = make_cfg(best_regime, mr, bo)
        m = evaluate(sym, cfg)
        add_row(rows, cfg, m, 4)
        row = rows[-1]
        if best is None or row['sharpe_per_bar'] > best[0]:
            best = (row['sharpe_per_bar'], row)
    assert best is not None
    log.append(f"[{sym.name}] Phase 4 done in {time.time()-t0:.1f}s. "
               f"Best sharpe={best[1]['sharpe_per_bar']:+.3f} trades={best[1]['trades']}")
    return best[1]


# --------------------------------------------------------------------- per-symbol driver

def load_symbol(name: str) -> Symbol:
    path = DATA_DIR / f'{name}_1m.csv'
    frame = pd.read_csv(path)
    frame['ts'] = pd.to_datetime(frame['timestamp'])
    frame = frame.drop(columns=['timestamp']).set_index('ts').sort_index()
    frame = add_features(frame)
    return Symbol(name, frame)


def run_symbol(symbol_name: str) -> dict:
    log: list[str] = []
    t0 = time.time()
    log.append(f"[{symbol_name}] Loading data...")
    sym = load_symbol(symbol_name)
    log.append(f"[{symbol_name}] Bars: {sym.n_bars}  range: {sym.frame.index.min()} -> {sym.frame.index.max()}")

    rows: list[dict] = []
    top_regimes = phase1(sym, rows, log)
    regime_mr, best_mr = phase2(sym, top_regimes, rows, log)
    regime_bo, best_bo = phase3(sym, top_regimes, rows, log)
    # Pick the better regime between MR-best and BO-best by re-evaluating both with each side's best.
    chosen_regime = regime_mr
    cfg_mr_in_bo = make_cfg(regime_bo, best_mr, best_bo)
    m_alt = evaluate(sym, cfg_mr_in_bo)
    cfg_mr = make_cfg(regime_mr, best_mr, best_bo)
    m_mr = evaluate(sym, cfg_mr)
    if m_alt['sharpe_per_bar'] > m_mr['sharpe_per_bar']:
        chosen_regime = regime_bo
        log.append(f"[{symbol_name}] Phase 3-4 bridge: BO-regime wins for combined run.")
    else:
        log.append(f"[{symbol_name}] Phase 3-4 bridge: MR-regime wins for combined run.")

    best_row = phase4(sym, chosen_regime, best_mr, best_bo, rows, log)

    # Save CSV (Go combos + top-30 No-Go by sharpe across all phases).
    go_rows = [r for r in rows if r['gate'] == 'go']
    nogo_rows = [r for r in rows if r['gate'] == 'no_go']
    go_rows.sort(key=lambda r: r['sharpe_per_bar'], reverse=True)
    nogo_rows.sort(key=lambda r: r['sharpe_per_bar'], reverse=True)
    out_rows = go_rows + nogo_rows[:30]
    if not out_rows and rows:
        out_rows = sorted(rows, key=lambda r: r['sharpe_per_bar'], reverse=True)[:30]

    out_path = REPORT_DIR / f'{symbol_name.lower()}_regime_hybrid.csv'
    if out_rows:
        with open(out_path, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
            w.writeheader()
            w.writerows(out_rows)
    log.append(f"[{symbol_name}] CSV: {out_path} ({len(out_rows)} rows; {len(go_rows)} Go / {len(rows)} total)")
    log.append(f"[{symbol_name}] Total elapsed: {time.time()-t0:.1f}s")

    return {
        'symbol': symbol_name,
        'n_total': len(rows),
        'n_go': len(go_rows),
        'best_go': go_rows[0] if go_rows else None,
        'best_overall': sorted(rows, key=lambda r: r['sharpe_per_bar'], reverse=True)[0] if rows else None,
        'best_phase4': best_row,
        'chosen_regime': chosen_regime,
        'best_mr': best_mr,
        'best_bo': best_bo,
        'log': log,
        'csv_path': str(out_path),
        'bars': sym.n_bars,
        'date_start': str(sym.frame.index.min()),
        'date_end': str(sym.frame.index.max()),
    }


# --------------------------------------------------------------------- summary

def write_summary(results: dict) -> Path:
    path = REPORT_DIR / 'regime_hybrid_summary.md'
    lines: list[str] = []
    lines.append('# ADX Regime-Hybrid Strategy — Sweep Summary')
    lines.append('')
    lines.append(f'- Generated: {pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}')
    lines.append(f'- Round-trip cost: {ROUND_TRIP_COST*100:.2f}% (12bps)')
    lines.append(f'- Go criteria: sharpe_per_bar >= {GO_SHARPE}, trades >= {GO_TRADES}, net_return > {GO_NET}')
    lines.append('')
    lines.append('## Strategy logic')
    lines.append('')
    lines.append('Per-bar regime detection via ADX(period) (long-only):')
    lines.append('')
    lines.append('- ADX < regime_adx_low  -> RANGING  -> mean reversion (z-score below threshold + RSI oversold)')
    lines.append('- ADX > regime_adx_high -> TRENDING -> breakout (close above prior range high + volume confirm)')
    lines.append('- Otherwise (transition zone) -> NO TRADE')
    lines.append('')
    lines.append('Exit: hold expires OR low <= entry - stop_atr * ATR(14). Per-regime hold & stop.')
    lines.append('')
    for symbol_name, res in results.items():
        lines.append(f'## {symbol_name}')
        lines.append('')
        lines.append(f'- Bars: {res["bars"]} ({res["date_start"]} -> {res["date_end"]})')
        lines.append(f'- Total combos evaluated: {res["n_total"]}')
        lines.append(f'- Go combos: **{res["n_go"]}**')
        lines.append(f'- CSV: `{res["csv_path"]}`')
        lines.append('')
        if res['best_go']:
            r = res['best_go']
            lines.append('### Best Go')
            lines.append('```')
            lines.append(_fmt_row(r))
            lines.append('```')
        else:
            r = res['best_overall']
            lines.append('### Best overall (No Go combos met all criteria)')
            if r:
                lines.append('```')
                lines.append(_fmt_row(r))
                lines.append('```')
        lines.append('')
        lines.append('### Selected best params after Phase 4')
        lines.append(f"- Regime: ADX({res['chosen_regime']['adx_period']}), low={res['chosen_regime']['regime_adx_low']}, high={res['chosen_regime']['regime_adx_high']}")
        lines.append(f"- MR best:    {res['best_mr']}")
        lines.append(f"- BO best:    {res['best_bo']}")
        lines.append('')
    # Interpretation block.
    lines.append('## Interpretation')
    lines.append('')
    btc = results.get('BTCUSDT', {})
    eth = results.get('ETHUSDT', {})
    btc_go = btc.get('n_go', 0)
    eth_go = eth.get('n_go', 0)
    if btc_go > 0 and eth_go > 0:
        lines.append(
            'The regime-hybrid strategy produces Go configurations on **both BTC and ETH**, '
            'suggesting an adaptive MR/BO switch is more universal than either pure approach.'
        )
    elif eth_go > 0 and btc_go == 0:
        lines.append(
            'ETH retains Go combinations but BTC does not. Hybrid does not rescue BTC '
            "from its sub-fee-hurdle volatility profile."
        )
    elif btc_go > 0 and eth_go == 0:
        lines.append(
            'BTC gains traction from breakout-regime gating, but ETH loses the consistent '
            'edge it had under pure MR — likely because the trending regime triggers cap '
            'too many MR setups.'
        )
    else:
        lines.append(
            'Neither symbol produced Go combinations under this regime split. The transition '
            'zone (between regime_adx_low and regime_adx_high) and per-regime stop/hold '
            'pairing likely need a broader sweep, or the round-trip cost dominates.'
        )
    lines.append('')
    path.write_text('\n'.join(lines), encoding='utf-8')
    return path


def _fmt_row(r: dict) -> str:
    return (
        f"adx_p={r['adx_period']:2d} lo={r['regime_adx_low']:.0f} hi={r['regime_adx_high']:.0f} | "
        f"MR zwin={r['mr_z_window']:>3d} zthr={r['mr_z_threshold']:.1f} rsi<={r['mr_rsi_long']:.0f} "
        f"hold={r['mr_hold']:>2d} stop={r['mr_stop_atr']:.1f}atr | "
        f"BO lb={r['bo_lookback']:>2d} vol={r['bo_vol_threshold']:.1f} hold={r['bo_hold']:>2d} "
        f"stop={r['bo_stop_atr']:.1f}atr ent={r['bo_entry']:14s} | "
        f"trades={r['trades']:>3d}(mr={r['mr_trades']:>3d}/bo={r['bo_trades']:>3d}) "
        f"wr={r['win_rate']:.2f} sharpe={r['sharpe_per_bar']:+.3f} "
        f"net={r['net_total_return']:+.4f} dd={r['max_drawdown']:+.4f}"
    )


# --------------------------------------------------------------------- main

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', choices=['BTCUSDT', 'ETHUSDT'], default=None,
                        help='Run only this symbol (skip the other and skip summary).')
    parser.add_argument('--serial', action='store_true', help='Run symbols serially in-process.')
    args = parser.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    symbols = ['BTCUSDT', 'ETHUSDT'] if args.symbol is None else [args.symbol]

    results: dict[str, dict] = {}
    if len(symbols) == 1 or args.serial:
        for s in symbols:
            res = run_symbol(s)
            results[s] = res
            for line in res['log']:
                print(line)
    else:
        with ProcessPoolExecutor(max_workers=2) as ex:
            futures = {s: ex.submit(run_symbol, s) for s in symbols}
            for s, fut in futures.items():
                res = fut.result()
                results[s] = res
                for line in res['log']:
                    print(line)

    if len(results) == 2:
        path = write_summary(results)
        print(f"\nSummary: {path}")

    # Print short summary block.
    for s, r in results.items():
        print(f"\n=== {s} ===")
        print(f"  Total: {r['n_total']} | Go: {r['n_go']} | CSV: {r['csv_path']}")
        if r['best_go']:
            print(f"  BEST GO: {_fmt_row(r['best_go'])}")
        elif r['best_overall']:
            print(f"  BEST OVERALL: {_fmt_row(r['best_overall'])}")


if __name__ == '__main__':
    main()
