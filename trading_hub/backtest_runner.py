"""Backtest runner with RegimeGatedCombo for Trading Hub Card D.

Combines:
  - Card A: PIT data pipeline (trading_hub.data.pit_store.PITDataStore)
  - Card B: Cost/slippage model (trading_hub.costs)
  - Card C: Ledger/position tracking (trading_hub.ledger)
  - Regime gating: low-vol -> mean_reversion, high-vol -> momentum

Public API
---------
run_backtest(config) -> BacktestResult
RegimeGatedCombo: fit() / predict() for regime-aware strategy selection

No broker imports. No network calls. Deterministic offline backtesting only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, TypedDict

from trading_hub.costs import estimate_round_trip_cost_bps
from trading_hub.ledger import (
    open_position,
    close_position,
    compute_aggregate_pnl,
    reset_ledger,
    get_position_history,
)
from trading_hub.data.pit_store import PITDataStore


# ---------------------------------------------------------------------------
# Typed dicts / dataclasses
# ---------------------------------------------------------------------------

class BacktestConfig(TypedDict, total=False):
    strategy: dict[str, Any]          # strategy config (ignored for RegimeGatedCombo compat)
    regime_model: dict[str, Any]       # regime model hyper-parameters
    tickers: list[str]
    start_date: str                    # ISO date string e.g. "2020-01-01"
    end_date: str
    interval: str                      # "1d" etc.
    initial_capital: float
    fee_bps: float
    spread_bps: float
    slippage_bps: float


@dataclass(frozen=True)
class Trade:
    """Single closed trade record."""
    ticker: str
    side: Literal["long", "short"]
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    size: float
    pnl_bps: float
    gross_return: float
    cost_bps: float
    regime_at_entry: str
    selected_strategy: str


@dataclass(frozen=True)
class BacktestResult:
    """Aggregated backtest result."""
    total_return: float                # decimal total return
    pnl_bps: float                    # total PnL in bps
    trade_count: int
    win_rate: float                    # fraction 0-1
    max_drawdown_bps: float
    regime_weights: dict[str, float]   # fraction of time in each regime
    trades: list[Trade]
    equity_curve: list[float]          # cumulative 1.0-based values per bar


# ---------------------------------------------------------------------------
# RegimeGatedCombo
# ---------------------------------------------------------------------------

class RegimeGatedCombo:
    """Regime-aware strategy selector.

    Fits historically to learn which strategy performs best per regime,
    then predicts which strategy to use at each bar.

    Regime logic (deterministic, no ML):
      - Low volatility  (ATR percentile < regime_thresholds["low"])  -> mean_reversion
      - High volatility (ATR percentile > regime_thresholds["high"]) -> momentum
      - Neutral         (between)                                  -> hold (0)

    Strategies are named by their ``strategy_name`` field.
    """

    def __init__(
        self,
        regime_thresholds: dict[str, float] | None = None,
        atr_window: int = 14,
        atr_percentile_window: int = 60,
        strategies: list[dict[str, Any]] | None = None,
    ) -> None:
        self.regime_thresholds = regime_thresholds or {"low": 0.33, "high": 0.66}
        self.atr_window = atr_window
        self.atr_percentile_window = atr_percentile_window
        # List of strategy configs; each dict must have at least "name"
        self.strategies = strategies or []
        # Fitted: regime -> {strategy_name: avg_return_bps}
        self._regime_strategy_returns: dict[str, dict[str, float]] = {}
        self._fitted = False

    # ------------------------------------------------------------------
    # fit — learn from historical returns which strategy works per regime
    # ------------------------------------------------------------------

    def fit(
        self,
        tickers: list[str],
        start: str,
        end: str,
        price_data: dict[str, pd.DataFrame] | None = None,
        strategy_signals: dict[str, pd.DataFrame] | None = None,
    ) -> "RegimeGatedCombo":
        """Learn regime-strategy associations from historical data.

        Parameters
        ----------
        tickers:
            Symbols to fit over.
        start, end:
            ISO date strings for the fit window.
        price_data:
            Dict of {ticker: DataFrame} with OHLCV data (index = datetime).
            Used instead of a data_store for synthetic / offline mode.
        strategy_signals:
            Dict of {strategy_name: DataFrame} with columns:
            - "signal": {-1, 0, 1} execution signal aligned to OHLCV index
            - "return": decimal bar return (close-to-close)

        Returns
        -------
        self (fitted)
        """
        if not self.strategies:
            raise ValueError("RegimeGatedCombo must have at least one strategy configured")

        if price_data is None:
            price_data = {}

        if strategy_signals is None:
            strategy_signals = {}

        regime_rets: dict[str, dict[str, list[float]]] = {
            r: {s["name"]: [] for s in self.strategies}
            for r in ("low", "neutral", "high")
        }

        for ticker in tickers:
            df = price_data.get(ticker)
            if df is None:
                continue
            df = df[(df.index >= start) & (df.index <= end)]
            if df.empty:
                continue

            # Compute ATR for regime detection
            atr_s = _atr(df, self.atr_window)
            atr_pct = _atr_percentile(atr_s, self.atr_percentile_window)

            for strat_cfg in self.strategies:
                name = strat_cfg["name"]
                sig_df = strategy_signals.get(name)
                if sig_df is None:
                    continue
                # Align signals to price data index
                sig = sig_df["signal"].reindex(df.index, fill_value=0)
                rets = df.get("return", _bar_returns(df))
                if isinstance(rets, pd.DataFrame):
                    rets = rets.iloc[:, 0]
                rets = rets.reindex(df.index, fill_value=0.0)

                for i, (dt, row) in enumerate(df.iterrows()):
                    regime = _classify_regime(
                        float(atr_pct.iloc[i]) if pd.notna(atr_pct.iloc[i]) else 0.5,
                        self.regime_thresholds,
                    )
                    signal = int(sig.iloc[i]) if pd.notna(sig.iloc[i]) else 0
                    if signal != 0:
                        ret = float(rets.iloc[i]) if pd.notna(rets.iloc[i]) else 0.0
                        regime_rets[regime][name].append(ret)

        # Average return per regime per strategy
        self._regime_strategy_returns = {}
        for regime, strat_dict in regime_rets.items():
            self._regime_strategy_returns[regime] = {}
            for name, rets in strat_dict.items():
                self._regime_strategy_returns[regime][name] = (
                    float(np.mean(rets)) * 10_000.0 if rets else 0.0
                )

        self._fitted = True
        return self

    # ------------------------------------------------------------------
    # predict — return regime + selected strategy for one bar
    # ------------------------------------------------------------------

    def predict(
        self,
        ticker: str,
        date: datetime,
        features: dict[str, Any],
    ) -> dict[str, Any]:
        """Classify regime and select best strategy for a single bar.

        Parameters
        ----------
        ticker:
            Asset ticker.
        date:
            Timestamp of the bar.
        features:
            Dict that must contain "atr_percentile" (float 0-1).
            Optional: "volatility" (float), "return" (float).

        Returns
        -------
        dict with keys: regime, selected_strategy, confidence
        """
        if not self._fitted:
            raise RuntimeError("RegimeGatedCombo must be fit() before predict()")

        atr_pct = float(features.get("atr_percentile", 0.5))
        regime = _classify_regime(atr_pct, self.regime_thresholds)

        if regime == "neutral":
            return {
                "regime": regime,
                "selected_strategy": "none",
                "confidence": 0.0,
            }

        # Pick strategy with highest fitted avg return for this regime
        strat_returns = self._regime_strategy_returns.get(regime, {})
        if not strat_returns:
            return {"regime": regime, "selected_strategy": "none", "confidence": 0.0}

        best_strategy = max(strat_returns, key=strat_returns.__getitem__)
        best_return = strat_returns[best_strategy]

        # Confidence: distance of atr_pct from neutral boundary, normalised
        if regime == "low":
            confidence = float(
                (self.regime_thresholds["low"] - atr_pct) / self.regime_thresholds["low"]
            )
        else:  # high
            confidence = float(
                (atr_pct - self.regime_thresholds["high"])
                / (1.0 - self.regime_thresholds["high"])
            )
        confidence = max(0.0, min(1.0, confidence))

        return {
            "regime": regime,
            "selected_strategy": best_strategy,
            "confidence": round(confidence, 4),
        }


# ---------------------------------------------------------------------------
# run_backtest
# ---------------------------------------------------------------------------

def run_backtest(config: BacktestConfig) -> BacktestResult:
    """Run a regime-gated combo backtest.

    Parameters
    ----------
    config: BacktestConfig dict with keys:
        tickers        : list of ticker strings
        start_date     : ISO date string
        end_date       : ISO date string
        interval       : bar interval string (e.g. "1d")
        initial_capital: float
        fee_bps        : round-trip fee in bps
        spread_bps     : round-trip spread in bps
        slippage_bps   : round-trip slippage in bps
        regime_model   : dict passed to RegimeGatedCombo constructor
        strategy       : dict with optional "strategies" list for RegimeGatedCombo

    Returns
    -------
    BacktestResult
    """
    tickers = config.get("tickers", [])
    start_date = config.get("start_date", "")
    end_date = config.get("end_date", "")
    interval = config.get("interval", "1d")
    initial_capital = float(config.get("initial_capital", 100_000.0))
    fee_bps = float(config.get("fee_bps", 0.0))
    spread_bps = float(config.get("spread_bps", 0.0))
    slippage_bps = float(config.get("slippage_bps", 0.0))
    regime_cfg = config.get("regime_model", {})
    strat_cfg = config.get("strategy", {})

    if not tickers:
        raise ValueError("config must contain at least one ticker in 'tickers'")

    # Cost in bps for round-trip
    cost_bps = estimate_round_trip_cost_bps(
        fee_bps=fee_bps,
        spread_bps=spread_bps,
        slippage_bps=slippage_bps,
    )

    # Build strategies list from config
    strategies = strat_cfg.get("strategies", [
        {"name": "mean_reversion"},
        {"name": "momentum"},
    ])

    # Build combo
    combo = RegimeGatedCombo(
        regime_thresholds=regime_cfg.get("regime_thresholds"),
        atr_window=regime_cfg.get("atr_window", 14),
        atr_percentile_window=regime_cfg.get("atr_percentile_window", 60),
        strategies=strategies,
    )

    # Load PIT data for all tickers
    pit_dir = regime_cfg.get("pit_data_dir")
    if pit_dir is None:
        # Fall back to synthetic data for offline deterministic testing
        data_store: PITDataStore | None = None
        use_synthetic = True
    else:
        data_store = PITDataStore(pit_dir)
        use_synthetic = False

    reset_ledger()

    regime_counts: dict[str, int] = {"low": 0, "neutral": 0, "high": 0}
    trade_meta: dict[str, dict[str, str]] = {}  # pos_id -> {regime, selected_strategy}
    equity_curve: list[float] = [1.0]
    capital = initial_capital

    for ticker in tickers:
        if use_synthetic:
            df = _synthetic_ohlcv(ticker, start_date, end_date, interval)
        else:
            assert data_store is not None
            df = data_store.read(ticker)
            df = df[(df.index >= start_date) & (df.index <= end_date)]

        if df.empty:
            continue

        # Compute bar returns and ATR
        returns = _bar_returns(df)
        atr_s = _atr(df, combo.atr_window)
        atr_pct = _atr_percentile(atr_s, combo.atr_percentile_window)

        # Generate strategy signals
        strategy_signals = _generate_strategy_signals(strategies, df, returns)

        # Fit combo — pass price_data dict for synthetic mode, None for real
        if not combo._fitted:
            price_data_for_fit = {ticker: df} if use_synthetic else None
            combo.fit(
                [ticker], start_date, end_date,
                price_data=price_data_for_fit,
                strategy_signals=strategy_signals,
            )

        prev_capital = capital

        for i, (dt, row) in enumerate(df.iterrows()):
            bar_return = float(returns.iloc[i]) if pd.notna(returns.iloc[i]) else 0.0
            atr_p = float(atr_pct.iloc[i]) if pd.notna(atr_pct.iloc[i]) else 0.5

            pred = combo.predict(ticker, dt, {"atr_percentile": atr_p})

            regime = pred["regime"]
            regime_counts[regime] = regime_counts.get(regime, 0) + 1

            selected = pred["selected_strategy"]
            if selected == "none":
                # No position — capital unchanged
                equity_curve.append(equity_curve[-1])
                continue

            sig_df = strategy_signals.get(selected)
            if sig_df is None:
                equity_curve.append(equity_curve[-1])
                continue

            signal = int(sig_df["signal"].iloc[i]) if i < len(sig_df) else 0
            if signal == 0:
                equity_curve.append(equity_curve[-1])
                continue

            side = "long" if signal > 0 else "short"
            entry_price = float(df["close"].iloc[i])
            exit_price = float(df["close"].iloc[i + 1]) if i + 1 < len(df) else entry_price
            size = capital / entry_price  # fractional notional

            pos_id = open_position(
                ticker=ticker,
                side=side,
                entry_price=entry_price,
                size=size,
                entry_time=dt,
                cost_bps=cost_bps,
            )

            exit_dt = df.index[i + 1] if i + 1 < len(df) else dt
            pnl_bps = close_position(pos_id, exit_price, exit_dt)

            # Log regime/strategy for this trade (to populate Trade fields later)
            trade_meta[pos_id] = {"regime": regime, "selected_strategy": selected}

            # Update capital with PnL
            pnl_return = pnl_bps / 10_000.0
            capital = capital * (1.0 + pnl_return)
            equity_curve.append(equity_curve[-1] * (1.0 + pnl_return))

    total_return = (capital - initial_capital) / initial_capital
    pnl_bps_val = total_return * 10_000.0

    closed = [p for p in get_position_history() if p.is_closed]
    trade_count = len(closed)
    wins = sum(1 for p in closed if (p.pnl_bps or 0) > 0)
    win_rate = wins / trade_count if trade_count else 0.0

    agg = compute_aggregate_pnl()
    max_drawdown_bps = agg.max_drawdown_bps

    total_bars = sum(regime_counts.values())
    regime_weights = {
        k: round(v / total_bars, 4) if total_bars else 0.0
        for k, v in regime_counts.items()
    }

    trades = [
        Trade(
            ticker=p.ticker,
            side=p.side.value,
            entry_time=p.entry_time,
            exit_time=p.exit_time,  # type: ignore[arg-type]
            entry_price=p.entry_price,
            exit_price=p.exit_price,  # type: ignore[arg-type]
            size=p.size,
            pnl_bps=p.pnl_bps or 0.0,
            gross_return=(p.pnl_bps or 0.0) / 10_000.0,
            cost_bps=p.cost_bps,
            regime_at_entry=trade_meta.get(p.position_id, {}).get("regime", "unknown"),
            selected_strategy=trade_meta.get(p.position_id, {}).get("selected_strategy", "combo"),
        )
        for p in closed
    ]

    return BacktestResult(
        total_return=round(total_return, 6),
        pnl_bps=round(pnl_bps_val, 2),
        trade_count=trade_count,
        win_rate=round(win_rate, 4),
        max_drawdown_bps=round(max_drawdown_bps, 2),
        regime_weights=regime_weights,
        trades=trades,
        equity_curve=[round(e, 6) for e in equity_curve],
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _atr(frame: pd.DataFrame, window: int = 14) -> pd.Series:
    high = frame["high"]
    low = frame["low"]
    close = frame["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(window, min_periods=window).mean()


def _atr_percentile(atr: pd.Series, window: int) -> pd.Series:
    return atr.rolling(window, min_periods=window).apply(
        lambda x: float(pd.Series(x).rank(pct=True).iloc[-1]),
        raw=False,
    )


def _classify_regime(atr_percentile: float, thresholds: dict[str, float]) -> str:
    low_thresh = thresholds.get("low", 0.33)
    high_thresh = thresholds.get("high", 0.66)
    if atr_percentile <= low_thresh:
        return "low"
    elif atr_percentile >= high_thresh:
        return "high"
    else:
        return "neutral"


def _bar_returns(df: pd.DataFrame) -> pd.Series:
    return df["close"].pct_change().fillna(0.0)


def _synthetic_ohlcv(
    ticker: str, start: str, end: str, interval: str
) -> pd.DataFrame:
    """Generate deterministic synthetic OHLCV for offline testing."""
    start_dt = pd.Timestamp(start)
    end_dt = pd.Timestamp(end)
    if interval == "1d":
        freq = "D"
    elif interval == "1h":
        freq = "h"
    else:
        freq = "D"

    dates = pd.date_range(start=start_dt, end=end_dt, freq=freq)
    n = len(dates)
    if n < 2:
        dates = pd.date_range(start=start_dt, periods=30, freq="D")

    # Deterministic walk with regime switches
    np.random.seed(42 + hash(ticker) % 2**31)
    rets = np.random.randn(len(dates)) * 0.02
    prices = 100.0 * np.exp(np.cumsum(rets))
    open_ = prices * (1.0 + np.random.randn(len(dates)) * 0.005)
    high = np.maximum(open_, prices) * (1.0 + np.abs(np.random.randn(len(dates)) * 0.01))
    low = np.minimum(open_, prices) * (1.0 - np.abs(np.random.randn(len(dates)) * 0.01))
    close = prices
    volume = np.random.randint(1_000_000, 10_000_000, size=len(dates))

    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )
    df.index.name = "date"
    return df



def _generate_strategy_signals(
    strategies: list[dict[str, Any]],
    df: pd.DataFrame,
    returns: pd.Series,
) -> dict[str, pd.DataFrame]:
    """Generate deterministic signals for each named strategy.

    mean_reversion: buy when return < -1 std, sell when return > +1 std
    momentum: buy when return > +0.5 std (positive momentum)
    """
    signals: dict[str, pd.DataFrame] = {}
    ret_std = returns.rolling(20, min_periods=10).std().fillna(0.01)

    for cfg in strategies:
        name = cfg.get("name", "unknown")
        if name == "mean_reversion":
            sig = pd.Series(0, index=df.index, dtype=int)
            sig.iloc[1:] = np.where(
                returns.iloc[1:] < -ret_std.iloc[1:], 1,
                np.where(returns.iloc[1:] > ret_std.iloc[1:], -1, 0),
            ).astype(int)
        elif name == "momentum":
            sig = pd.Series(0, index=df.index, dtype=int)
            sig.iloc[1:] = np.where(returns.iloc[1:] > 0.005, 1, 0).astype(int)
        else:
            sig = pd.Series(0, index=df.index, dtype=int)

        signals[name] = pd.DataFrame(
            {"signal": sig.shift(1, fill_value=0).fillna(0).astype(int), "return": returns}
        )

    return signals
