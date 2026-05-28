#!/usr/bin/env python3
"""
Z-Score Adaptive Signal Strategy — percentile-based RSI instead of fixed thresholds.

Core innovation: instead of "RSI < 30" use "RSI in bottom X% of its last N values".
This adapts the oversold definition to each asset's own RSI distribution rather
than the canonical 30/70 levels designed for equities.

At each bar i, features are evaluated on bar i-1 and entry occurs at open[i].
Long-only.

Entry signal (two modes):
  - "and": Z-score <= -z_threshold AND RSI percentile rank <= rsi_percentile/100
  - "or" : Z-score <= -z_threshold OR  RSI percentile rank <= rsi_percentile/100

Volume confirmation in Stage 1 is fixed at 20-bar SMA * 1.5x.
Stage 2 fine-tunes around the top 20 configs from Stage 1 and varies the
volume threshold too.

Exit: hold_period bars OR low[t] <= entry_price - stop_atr * ATR14[entry-1].

Outputs:
  research/reports/btcusdt_zscore_adaptive.csv
  research/reports/ethusdt_zscore_adaptive.csv
  research/reports/zscore_adaptive_summary.md
"""
from __future__ import annotations

import argparse
import csv
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
GO_TRADES = 5
GO_NET = 0.0

# ---------------------------------------------------------------- sweep grids

STAGE1_GRID = dict(
    z_window=[20, 50, 100, 200, 360],
    z_threshold=[1.5, 2.0, 2.5, 3.0],
    rsi_percentile=[5, 10, 15, 20, 25],
    rsi_lookback=[14, 20, 30, 50],
    hold=[10, 15, 20, 25, 30, 40],
    stop_atr=[0.5, 0.8, 1.0, 1.5],
    entry_type=['and', 'or'],
)
# Fixed defaults in Stage 1 (per the brief — volume held as a sensible default).
STAGE1_VOL_WINDOW = 20
STAGE1_VOL_THRESHOLD = 1.5
STAGE1_USE_VOLUME = True
STAGE1_ATR_WINDOW = 14

# Stage 2 neighborhood radius (±1 step in the grid, plus extra vol thresholds).
STAGE2_TOP_N = 20

# ---------------------------------------------------------------- helpers


def zscore_window(close: np.ndarray, window: int) -> np.ndarray:
    s = pd.Series(close)
    mean = s.rolling(window, min_periods=window).mean()
    std = s.rolling(window, min_periods=window).std(ddof=0)
    with np.errstate(divide='ignore', invalid='ignore'):
        z = (s - mean) / std
    return z.to_numpy()


def rsi_percentile_rank(rsi: np.ndarray, lookback: int) -> np.ndarray:
    """For each bar, fraction of last `lookback` RSI values <= current.

    A value of 0.05 means current RSI is in the bottom 5% of the window —
    i.e. an "adaptive oversold" signal.
    """
    return pd.Series(rsi).rolling(lookback, min_periods=lookback).rank(pct=True).to_numpy()


def rolling_mean(arr: np.ndarray, window: int) -> np.ndarray:
    return pd.Series(arr).rolling(window, min_periods=window).mean().to_numpy()


def shift1(arr: np.ndarray) -> np.ndarray:
    return pd.Series(arr).shift(1).to_numpy()


# ---------------------------------------------------------------- config


@dataclass(frozen=True)
class Config:
    z_window: int
    z_threshold: float
    rsi_percentile: float
    rsi_lookback: int
    hold: int
    stop_atr: float
    entry_type: str
    use_volume: bool
    vol_window: int
    vol_threshold: float

    def asdict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__.keys()}


# ---------------------------------------------------------------- simulation


def simulate(
    opens: np.ndarray, lows: np.ndarray, closes: np.ndarray, atrs: np.ndarray,
    cand_idx: np.ndarray,
    hold: int, stop_atr_mult: float,
    n_bars: int,
) -> list[tuple[int, int, float, float]]:
    """Non-overlapping long entries at next-bar open; exit on hold OR stop.

    Returns list of (entry_bar, exit_bar, gross, net).
    """
    trades: list[tuple[int, int, float, float]] = []
    in_trade_until = -1
    for k in range(len(cand_idx)):
        i = int(cand_idx[k])
        if i + 1 >= n_bars:
            continue
        if (i + 1) <= in_trade_until:
            continue
        atr_v = float(atrs[i])
        if not np.isfinite(atr_v) or atr_v <= 0:
            continue
        entry_i = i + 1
        entry_price = float(opens[entry_i])
        stop_price = entry_price - stop_atr_mult * atr_v
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
        gross = exit_price / entry_price - 1.0
        net = gross - ROUND_TRIP_COST
        trades.append((entry_i, exit_bar, float(gross), float(net)))
        in_trade_until = exit_bar
    return trades


def metrics_from_trades(trades: list[tuple[int, int, float, float]], n_bars: int) -> dict:
    if not trades:
        return {
            'trades': 0, 'wins': 0, 'losses': 0, 'win_rate': 0.0,
            'gross_total_return': 0.0, 'net_total_return': 0.0,
            'avg_trade_return_net': 0.0,
            'sharpe_per_bar': 0.0, 'max_drawdown': 0.0,
            'exposure': 0.0,
        }
    grosses = np.array([t[2] for t in trades])
    nets = np.array([t[3] for t in trades])
    wins = int((nets > 0).sum())
    losses = int((nets < 0).sum())
    per_bar = np.zeros(n_bars, dtype=float)
    exposure_bars = 0
    for entry, exit_bar, _, net in trades:
        per_bar[exit_bar] += net
        exposure_bars += exit_bar - entry
    std = float(per_bar.std(ddof=0))
    sharpe = float((per_bar.mean() / std) * np.sqrt(BARS_PER_YEAR)) if std > 0 else 0.0
    equity = np.cumprod(1.0 + per_bar)
    peak = np.maximum.accumulate(equity)
    drawdown = equity / peak - 1.0
    return {
        'trades': len(trades),
        'wins': wins, 'losses': losses,
        'win_rate': wins / len(trades),
        'gross_total_return': float(np.prod(1.0 + grosses) - 1.0),
        'net_total_return': float(equity[-1] - 1.0),
        'avg_trade_return_net': float(nets.mean()),
        'sharpe_per_bar': sharpe,
        'max_drawdown': float(drawdown.min()),
        'exposure': exposure_bars / n_bars,
    }


# ---------------------------------------------------------------- symbol container


class Symbol:
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
        # Caches keyed on the parameter that drives the array shape.
        self._z_prev_cache: dict[int, np.ndarray] = {}
        self._rsi_rank_prev_cache: dict[int, np.ndarray] = {}
        self._vol_prev_cache: dict[int, np.ndarray] = {}

    def z_prev(self, window: int) -> np.ndarray:
        if window not in self._z_prev_cache:
            self._z_prev_cache[window] = shift1(zscore_window(self.closes, window))
        return self._z_prev_cache[window]

    def rsi_rank_prev(self, lookback: int) -> np.ndarray:
        if lookback not in self._rsi_rank_prev_cache:
            self._rsi_rank_prev_cache[lookback] = shift1(rsi_percentile_rank(self.rsi, lookback))
        return self._rsi_rank_prev_cache[lookback]

    def vol_ma_prev(self, window: int) -> np.ndarray:
        if window not in self._vol_prev_cache:
            self._vol_prev_cache[window] = shift1(rolling_mean(self.volumes, window))
        return self._vol_prev_cache[window]


# ---------------------------------------------------------------- evaluate


def evaluate(sym: Symbol, cfg: Config) -> dict:
    z_prev = sym.z_prev(cfg.z_window)
    rsi_rank_prev = sym.rsi_rank_prev(cfg.rsi_lookback)

    z_signal = np.isfinite(z_prev) & (z_prev <= -cfg.z_threshold)
    rsi_signal = np.isfinite(rsi_rank_prev) & (rsi_rank_prev <= cfg.rsi_percentile / 100.0)

    if cfg.entry_type == 'and':
        sig = z_signal & rsi_signal
    else:
        sig = z_signal | rsi_signal

    if cfg.use_volume:
        vol_ma_prev = sym.vol_ma_prev(cfg.vol_window)
        # Use prev-bar volume so the entry-bar open isn't peeking into entry-bar volume.
        vol_prev = shift1(sym.volumes)
        with np.errstate(invalid='ignore'):
            vol_ok = np.isfinite(vol_ma_prev) & (vol_prev > vol_ma_prev * cfg.vol_threshold)
        sig = sig & vol_ok

    cand_idx = np.where(sig)[0]
    trades = simulate(
        sym.opens, sym.lows, sym.closes, sym.atrs,
        cand_idx, cfg.hold, cfg.stop_atr, sym.n_bars,
    )
    return metrics_from_trades(trades, sym.n_bars)


# ---------------------------------------------------------------- gating & rows


def gate(row: dict) -> str:
    if (
        row['sharpe_per_bar'] >= GO_SHARPE
        and row['trades'] >= GO_TRADES
        and row['net_total_return'] > GO_NET
    ):
        return 'go'
    return 'no_go'


def make_row(cfg: Config, m: dict, stage: int) -> dict:
    row = {'stage': stage, **cfg.asdict(), **m}
    row['gate'] = gate(row)
    return row


# ---------------------------------------------------------------- stages


def stage1(sym: Symbol, log: list[str]) -> list[dict]:
    grid = STAGE1_GRID
    combos = list(product(
        grid['z_window'], grid['z_threshold'], grid['rsi_percentile'],
        grid['rsi_lookback'], grid['hold'], grid['stop_atr'], grid['entry_type'],
    ))
    n_total = len(combos)
    log.append(f"[{sym.name}] Stage 1: {n_total} combos")
    t0 = time.time()
    rows: list[dict] = []
    for k, (zw, zt, rp, rl, h, sa, et) in enumerate(combos):
        cfg = Config(
            z_window=zw, z_threshold=zt, rsi_percentile=rp, rsi_lookback=rl,
            hold=h, stop_atr=sa, entry_type=et,
            use_volume=STAGE1_USE_VOLUME, vol_window=STAGE1_VOL_WINDOW,
            vol_threshold=STAGE1_VOL_THRESHOLD,
        )
        m = evaluate(sym, cfg)
        rows.append(make_row(cfg, m, 1))
        if (k + 1) % 2000 == 0:
            log.append(f"[{sym.name}]   Stage 1 {k+1}/{n_total} t={time.time()-t0:.0f}s")
    log.append(f"[{sym.name}] Stage 1 done in {time.time()-t0:.1f}s")
    return rows


def neighborhood(value, grid_values):
    """Return value plus its ±1 neighbours in the sorted grid."""
    sorted_vals = sorted(set(grid_values))
    if value not in sorted_vals:
        sorted_vals = sorted(set(sorted_vals + [value]))
    idx = sorted_vals.index(value)
    out = [sorted_vals[idx]]
    if idx > 0:
        out.append(sorted_vals[idx - 1])
    if idx < len(sorted_vals) - 1:
        out.append(sorted_vals[idx + 1])
    return sorted(set(out))


def stage2(sym: Symbol, stage1_rows: list[dict], log: list[str]) -> list[dict]:
    # Pick top 20 valid rows by sharpe (tie-break: trades).
    sorted_rows = sorted(
        [r for r in stage1_rows if r['trades'] > 0],
        key=lambda r: (r['sharpe_per_bar'], r['trades']),
        reverse=True,
    )
    tops = sorted_rows[:STAGE2_TOP_N]
    if not tops:
        log.append(f"[{sym.name}] Stage 2: skipping (no Stage 1 row with trades > 0)")
        return []
    log.append(f"[{sym.name}] Stage 2: building fine-tune grid around top {len(tops)} configs")
    g = STAGE1_GRID
    extra_vol_thresholds = [1.0, 1.5, 2.0]
    seen: set[tuple] = set()
    combos: list[Config] = []
    for top in tops:
        zws = neighborhood(top['z_window'], g['z_window'])
        zts = neighborhood(top['z_threshold'], g['z_threshold'])
        rps = neighborhood(top['rsi_percentile'], g['rsi_percentile'])
        rls = neighborhood(top['rsi_lookback'], g['rsi_lookback'])
        hs = neighborhood(top['hold'], g['hold'])
        sas = neighborhood(top['stop_atr'], g['stop_atr'])
        ets = [top['entry_type']]
        for zw, zt, rp, rl, h, sa, et, vt in product(
            zws, zts, rps, rls, hs, sas, ets, extra_vol_thresholds,
        ):
            key = (zw, zt, rp, rl, h, sa, et, vt)
            if key in seen:
                continue
            seen.add(key)
            combos.append(Config(
                z_window=zw, z_threshold=zt, rsi_percentile=rp, rsi_lookback=rl,
                hold=h, stop_atr=sa, entry_type=et,
                use_volume=True, vol_window=STAGE1_VOL_WINDOW, vol_threshold=vt,
            ))
    log.append(f"[{sym.name}] Stage 2: {len(combos)} unique combos")
    t0 = time.time()
    rows: list[dict] = []
    for k, cfg in enumerate(combos):
        m = evaluate(sym, cfg)
        rows.append(make_row(cfg, m, 2))
        if (k + 1) % 2000 == 0:
            log.append(f"[{sym.name}]   Stage 2 {k+1}/{len(combos)} t={time.time()-t0:.0f}s")
    log.append(f"[{sym.name}] Stage 2 done in {time.time()-t0:.1f}s")
    return rows


# ---------------------------------------------------------------- driver


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
    log.append(f"[{symbol_name}] Bars: {sym.n_bars} range: {sym.frame.index.min()} -> {sym.frame.index.max()}")

    rows1 = stage1(sym, log)
    rows2 = stage2(sym, rows1, log)
    all_rows = rows1 + rows2

    go_rows = [r for r in all_rows if r['gate'] == 'go']
    # When the gate doesn't pass, rank "best No-Go" by sharpe but require trades > 0 —
    # a config with zero trades has sharpe == 0 by construction and would otherwise
    # swamp the top of the report despite never firing.
    nogo_rows = [r for r in all_rows if r['gate'] == 'no_go' and r['trades'] > 0]
    go_rows.sort(key=lambda r: r['sharpe_per_bar'], reverse=True)
    nogo_rows.sort(key=lambda r: r['sharpe_per_bar'], reverse=True)
    out_rows = go_rows + nogo_rows[:50]
    if not out_rows:
        out_rows = sorted(all_rows, key=lambda r: r['sharpe_per_bar'], reverse=True)[:50]

    out_path = REPORT_DIR / f'{symbol_name.lower()}_zscore_adaptive.csv'
    if out_rows:
        with open(out_path, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
            w.writeheader()
            w.writerows(out_rows)
    log.append(f"[{symbol_name}] CSV: {out_path} ({len(out_rows)} rows; {len(go_rows)} Go / {len(all_rows)} total)")
    log.append(f"[{symbol_name}] Total elapsed: {time.time()-t0:.1f}s")

    return {
        'symbol': symbol_name,
        'n_total': len(all_rows),
        'n_stage1': len(rows1),
        'n_stage2': len(rows2),
        'n_go': len(go_rows),
        'best_go': go_rows[0] if go_rows else None,
        'best_overall': max(
            (r for r in all_rows if r['trades'] > 0),
            key=lambda r: r['sharpe_per_bar'],
            default=None,
        ),
        'log': log,
        'csv_path': str(out_path),
        'bars': sym.n_bars,
        'date_start': str(sym.frame.index.min()),
        'date_end': str(sym.frame.index.max()),
    }


# ---------------------------------------------------------------- summary


def _fmt_row(r: dict) -> str:
    return (
        f"stage={r['stage']} zwin={r['z_window']:>3d} zthr={r['z_threshold']:.1f} "
        f"rsi_p={r['rsi_percentile']:.0f}%/{r['rsi_lookback']:>2d}b "
        f"hold={r['hold']:>2d} stop={r['stop_atr']:.1f}atr "
        f"vol={r['vol_threshold']:.1f}x/{r['vol_window']}b "
        f"entry={r['entry_type']:<3s} | "
        f"trades={r['trades']:>3d} wr={r['win_rate']:.2f} "
        f"sharpe={r['sharpe_per_bar']:+.3f} net={r['net_total_return']:+.4f} "
        f"dd={r['max_drawdown']:+.4f}"
    )


def write_summary(results: dict) -> Path:
    path = REPORT_DIR / 'zscore_adaptive_summary.md'
    lines: list[str] = []
    lines.append('# Z-Score + Adaptive RSI-Percentile Sweep — Summary')
    lines.append('')
    lines.append(f'- Generated: {pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}')
    lines.append(f'- Round-trip cost: {ROUND_TRIP_COST*100:.2f}% (12bps)')
    lines.append(f'- Go criteria: sharpe_per_bar >= {GO_SHARPE}, trades >= {GO_TRADES}, net_return > {GO_NET}')
    lines.append('')
    lines.append('## Strategy logic')
    lines.append('')
    lines.append('Long-only entries at next-bar open after both signals (or either, depending on entry_type) trigger.')
    lines.append('')
    lines.append('- Z-score = (close - SMA(z_window)) / std(close, z_window)')
    lines.append('  Buy candidate when Z-score <= -z_threshold (price far below mean).')
    lines.append('- RSI percentile rank = rolling rank (pct=True) of RSI14 over `rsi_lookback` bars.')
    lines.append('  Buy candidate when rank <= rsi_percentile/100 (adaptive oversold).')
    lines.append('- Volume confirmation: prev-bar volume > SMA(vol_window) * vol_threshold.')
    lines.append('- Exit: hold_period bars OR low <= entry - stop_atr * ATR14[entry-1].')
    lines.append('')
    lines.append('## Sweep design')
    lines.append('')
    lines.append('- Stage 1: full coarse grid (z_window x z_threshold x rsi_pct x rsi_lookback x hold x stop_atr x entry_type) = 19,200 combos per symbol, volume fixed at 20-bar / 1.5x.')
    lines.append('- Stage 2: ±1 step neighborhood around top 20 Stage-1 configs, varying vol_threshold across {1.0, 1.5, 2.0}.')
    lines.append('')
    for symbol_name, res in results.items():
        lines.append(f'## {symbol_name}')
        lines.append('')
        lines.append(f'- Bars: {res["bars"]} ({res["date_start"]} -> {res["date_end"]})')
        lines.append(f'- Stage 1 combos: {res["n_stage1"]}, Stage 2 combos: {res["n_stage2"]}, total: {res["n_total"]}')
        lines.append(f'- Go combos: **{res["n_go"]}**')
        lines.append(f'- CSV: `{res["csv_path"]}`')
        lines.append('')
        if res['best_go']:
            lines.append('### Best Go')
            lines.append('```')
            lines.append(_fmt_row(res['best_go']))
            lines.append('```')
        else:
            lines.append('### Best overall (no Go combo met all criteria)')
            if res['best_overall']:
                lines.append('```')
                lines.append(_fmt_row(res['best_overall']))
                lines.append('```')
        lines.append('')

    lines.append('## Interpretation: adaptive vs fixed-RSI')
    lines.append('')
    btc = results.get('BTCUSDT', {})
    eth = results.get('ETHUSDT', {})
    btc_go = btc.get('n_go', 0) if btc else 0
    eth_go = eth.get('n_go', 0) if eth else 0
    if btc_go > 0 and eth_go > 0:
        lines.append(
            'Adaptive percentile entries unlock Go configurations on **both BTC and ETH**, '
            'suggesting that letting the RSI threshold float with each asset\'s own distribution '
            'is genuinely more universal than the fixed 30/70 rule.'
        )
    elif eth_go > 0 and btc_go == 0:
        lines.append(
            'ETH still produces Go combinations but BTC does not — '
            "adaptive RSI alone doesn't rescue BTC's sub-fee-hurdle signal."
        )
    elif btc_go > 0 and eth_go == 0:
        lines.append(
            'BTC now yields Go combinations under adaptive percentile entries — '
            'this is the headline result if it holds up under fine-tune. '
            'Worth re-running on out-of-sample data before celebrating.'
        )
    else:
        lines.append(
            'Neither symbol produced Go combinations. Either the signal is genuinely sub-fee '
            'on this dataset window, or the 19,200-combo coarse grid still misses the relevant '
            'corner of the parameter space.'
        )
    lines.append('')
    path.write_text('\n'.join(lines), encoding='utf-8')
    return path


# ---------------------------------------------------------------- main


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

    for s, r in results.items():
        print(f"\n=== {s} ===")
        print(f"  Total: {r['n_total']} | Go: {r['n_go']} | CSV: {r['csv_path']}")
        if r['best_go']:
            print(f"  BEST GO: {_fmt_row(r['best_go'])}")
        elif r['best_overall']:
            print(f"  BEST OVERALL: {_fmt_row(r['best_overall'])}")


if __name__ == '__main__':
    main()
