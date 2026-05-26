"""Targeted tests for trading_hub.backtest_runner — Card D.

Scope: RegimeGatedCombo + run_backtest integration.
Deterministic, offline, no broker imports.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from trading_hub.backtest_runner import (
    BacktestResult,
    RegimeGatedCombo,
    Trade,
    _atr,
    _atr_percentile,
    _bar_returns,
    _classify_regime,
    _generate_strategy_signals,
    _synthetic_ohlcv,
    run_backtest,
)
from trading_hub import ledger
from trading_hub.ledger import reset_ledger


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_ledger():
    reset_ledger()
    yield
    reset_ledger()


# ---------------------------------------------------------------------------
# Synthetic OHLCV helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(
    n: int = 60,
    start: str = "2020-01-01",
    seed: int = 0,
) -> pd.DataFrame:
    """Deterministic OHLCV DataFrame for testing."""
    np.random.seed(seed)
    dates = pd.date_range(start=start, periods=n, freq="D")
    rets = np.random.randn(n) * 0.015
    prices = 100.0 * np.exp(np.cumsum(rets))
    open_ = prices * (1.0 + np.random.randn(n) * 0.005)
    high = np.maximum(open_, prices) * (1.0 + np.abs(np.random.randn(n) * 0.008))
    low = np.minimum(open_, prices) * (1.0 - np.abs(np.random.randn(n) * 0.008))
    close = prices
    volume = np.random.randint(1_000_000, 5_000_000, size=n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


# ---------------------------------------------------------------------------
# _classify_regime
# ---------------------------------------------------------------------------

class TestClassifyRegime:
    def test_low_regime(self):
        assert _classify_regime(0.10, {"low": 0.33, "high": 0.66}) == "low"
        assert _classify_regime(0.33, {"low": 0.33, "high": 0.66}) == "low"

    def test_high_regime(self):
        assert _classify_regime(0.90, {"low": 0.33, "high": 0.66}) == "high"
        assert _classify_regime(0.66, {"low": 0.33, "high": 0.66}) == "high"

    def test_neutral_regime(self):
        assert _classify_regime(0.50, {"low": 0.33, "high": 0.66}) == "neutral"
        assert _classify_regime(0.34, {"low": 0.33, "high": 0.66}) == "neutral"
        assert _classify_regime(0.65, {"low": 0.33, "high": 0.66}) == "neutral"

    def test_custom_thresholds(self):
        assert _classify_regime(0.20, {"low": 0.25, "high": 0.75}) == "low"
        assert _classify_regime(0.80, {"low": 0.25, "high": 0.75}) == "high"
        assert _classify_regime(0.50, {"low": 0.25, "high": 0.75}) == "neutral"


# ---------------------------------------------------------------------------
# _bar_returns
# ---------------------------------------------------------------------------

class TestBarReturns:
    def test_bar_returns_basic(self):
        df = _make_ohlcv(n=10, seed=1)
        rets = _bar_returns(df)
        assert len(rets) == len(df)
        assert rets.iloc[0] == 0.0  # first is NaN -> fill 0
        assert isinstance(rets, pd.Series)

    def test_bar_returns_zeros_if_flat(self):
        df = _make_ohlcv(n=5, seed=42)
        df["close"] = 100.0
        rets = _bar_returns(df)
        assert rets.iloc[1:].abs().sum() == 0.0


# ---------------------------------------------------------------------------
# _atr
# ---------------------------------------------------------------------------

class TestATR:
    def test_atr_length(self):
        df = _make_ohlcv(n=30, seed=5)
        atr = _atr(df, window=14)
        assert len(atr) == len(df)
        # First 13 values may be NaN due to rolling window
        assert atr.iloc[13:].notna().all()

    def test_atr_positive(self):
        df = _make_ohlcv(n=50, seed=6)
        atr = _atr(df, window=14)
        assert (atr.iloc[14:] > 0).all()


# ---------------------------------------------------------------------------
# _atr_percentile
# ---------------------------------------------------------------------------

class TestATRPercentile:
    def test_atr_percentile_in_range(self):
        df = _make_ohlcv(n=100, seed=7)
        atr = _atr(df, window=14)
        pct = _atr_percentile(atr, window=60)
        valid = pct.dropna()
        assert (valid >= 0.0).all()
        assert (valid <= 1.0).all()


# ---------------------------------------------------------------------------
# _generate_strategy_signals
# ---------------------------------------------------------------------------

class TestGenerateStrategySignals:
    def test_mean_reversion_signal_shape(self):
        df = _make_ohlcv(n=50, seed=10)
        returns = _bar_returns(df)
        strategies = [{"name": "mean_reversion"}, {"name": "momentum"}]
        signals = _generate_strategy_signals(strategies, df, returns)
        assert "mean_reversion" in signals
        assert "momentum" in signals
        assert len(signals["mean_reversion"]) == len(df)
        assert set(signals["mean_reversion"].columns) == {"signal", "return"}

    def test_unknown_strategy_gets_zero_signal(self):
        df = _make_ohlcv(n=30, seed=11)
        returns = _bar_returns(df)
        strategies = [{"name": "unknown_strategy"}]
        signals = _generate_strategy_signals(strategies, df, returns)
        assert (signals["unknown_strategy"]["signal"] == 0).all()


# ---------------------------------------------------------------------------
# RegimeGatedCombo — unit
# ---------------------------------------------------------------------------

class TestRegimeGatedComboInit:
    def test_default_thresholds(self):
        combo = RegimeGatedCombo()
        assert combo.regime_thresholds == {"low": 0.33, "high": 0.66}
        assert combo.atr_window == 14
        assert combo.atr_percentile_window == 60

    def test_custom_thresholds(self):
        combo = RegimeGatedCombo(
            regime_thresholds={"low": 0.20, "high": 0.80},
            atr_window=20,
            strategies=[{"name": "mean_reversion"}],
        )
        assert combo.regime_thresholds == {"low": 0.20, "high": 0.80}
        assert combo.atr_window == 20

    def test_no_strategies_raises_on_fit(self):
        combo = RegimeGatedCombo()
        with pytest.raises(ValueError, match="at least one strategy"):
            combo.fit(
                tickers=["BTC-USD"],
                start="2020-01-01",
                end="2020-12-31",
                price_data={},
                strategy_signals={},
            )


class TestRegimeGatedComboPredict:
    def test_not_fitted_raises(self):
        combo = RegimeGatedCombo(strategies=[{"name": "mr"}])
        with pytest.raises(RuntimeError, match="must be fit"):
            combo.predict("BTC-USD", datetime.now(), {"atr_percentile": 0.5})

    def test_neutral_regime_returns_none_strategy(self):
        combo = RegimeGatedCombo(strategies=[{"name": "mr"}])
        combo._fitted = True  # bypass fit for unit test
        combo._regime_strategy_returns = {"low": {}, "neutral": {}, "high": {}}

        result = combo.predict("BTC-USD", datetime.now(), {"atr_percentile": 0.5})
        assert result["regime"] == "neutral"
        assert result["selected_strategy"] == "none"
        assert result["confidence"] == 0.0

    def test_low_regime_picks_best_strategy(self):
        combo = RegimeGatedCombo(strategies=[{"name": "mr"}, {"name": "mom"}])
        combo._fitted = True
        combo._regime_strategy_returns = {
            "low": {"mr": 15.0, "mom": 5.0},
            "neutral": {},
            "high": {},
        }

        result = combo.predict("BTC-USD", datetime.now(), {"atr_percentile": 0.1})
        assert result["regime"] == "low"
        assert result["selected_strategy"] == "mr"
        assert 0.0 < result["confidence"] <= 1.0

    def test_high_regime_picks_best_strategy(self):
        combo = RegimeGatedCombo(strategies=[{"name": "mr"}, {"name": "mom"}])
        combo._fitted = True
        combo._regime_strategy_returns = {
            "low": {},
            "neutral": {},
            "high": {"mom": 20.0, "mr": 8.0},
        }

        result = combo.predict("BTC-USD", datetime.now(), {"atr_percentile": 0.95})
        assert result["regime"] == "high"
        assert result["selected_strategy"] == "mom"
        assert 0.0 < result["confidence"] <= 1.0

    def test_confidence_clamped_to_one(self):
        combo = RegimeGatedCombo(strategies=[{"name": "mr"}])
        combo._fitted = True
        combo._regime_strategy_returns = {
            "low": {"mr": 10.0},
            "neutral": {},
            "high": {},
        }
        result = combo.predict("BTC-USD", datetime.now(), {"atr_percentile": 0.0})
        assert result["confidence"] <= 1.0


# ---------------------------------------------------------------------------
# RegimeGatedCombo — fit with synthetic data
# ---------------------------------------------------------------------------

class TestRegimeGatedComboFit:
    def test_fit_produces_regime_returns(self):
        df = _make_ohlcv(n=120, seed=99)
        returns = _bar_returns(df)
        strategies = [{"name": "mean_reversion"}, {"name": "momentum"}]
        signals = _generate_strategy_signals(strategies, df, returns)

        combo = RegimeGatedCombo(strategies=strategies)
        combo.fit(
            tickers=["SYNTH"],
            start="2020-01-01",
            end="2020-12-31",
            price_data={"SYNTH": df},
            strategy_signals=signals,
        )

        assert combo._fitted is True
        assert "low" in combo._regime_strategy_returns
        assert "high" in combo._regime_strategy_returns


# ---------------------------------------------------------------------------
# _synthetic_ohlcv
# ---------------------------------------------------------------------------

class TestSyntheticOHLCV:
    def test_synthetic_columns(self):
        df = _synthetic_ohlcv("BTC-USD", "2020-01-01", "2020-12-31", "1d")
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert df["high"].max() >= df["close"].max()
        assert df["low"].min() <= df["close"].min()

    def test_synthetic_deterministic(self):
        df1 = _synthetic_ohlcv("BTC-USD", "2020-01-01", "2020-06-01", "1d")
        df2 = _synthetic_ohlcv("BTC-USD", "2020-01-01", "2020-06-01", "1d")
        pd.testing.assert_frame_equal(df1, df2)


# ---------------------------------------------------------------------------
# BacktestResult dataclass
# ---------------------------------------------------------------------------

class TestBacktestResultDataclass:
    def test_backtest_result_fields(self):
        result = BacktestResult(
            total_return=0.05,
            pnl_bps=500.0,
            trade_count=10,
            win_rate=0.6,
            max_drawdown_bps=150.0,
            regime_weights={"low": 0.4, "neutral": 0.3, "high": 0.3},
            trades=[],
            equity_curve=[1.0, 1.01, 1.02],
        )
        assert result.total_return == 0.05
        assert result.pnl_bps == 500.0
        assert result.trade_count == 10
        assert result.win_rate == 0.6
        assert result.regime_weights["low"] == 0.4


# ---------------------------------------------------------------------------
# Trade dataclass
# ---------------------------------------------------------------------------

class TestTradeDataclass:
    def test_trade_fields(self):
        t = Trade(
            ticker="BTC-USD",
            side="long",
            entry_time=datetime(2020, 1, 1),
            exit_time=datetime(2020, 1, 5),
            entry_price=100.0,
            exit_price=105.0,
            size=1.0,
            pnl_bps=500.0,
            gross_return=0.05,
            cost_bps=10.0,
            regime_at_entry="low",
            selected_strategy="mean_reversion",
        )
        assert t.side == "long"
        assert t.pnl_bps == 500.0
        assert t.regime_at_entry == "low"


# ---------------------------------------------------------------------------
# run_backtest — integration
# ---------------------------------------------------------------------------

class TestRunBacktestValidation:
    def test_empty_tickers_raises(self):
        with pytest.raises(ValueError, match="at least one ticker"):
            run_backtest({})

    def test_default_capital(self):
        config: dict = {
            "tickers": ["SYNTH"],
            "start_date": "2020-01-01",
            "end_date": "2020-01-31",
            "interval": "1d",
        }
        result = run_backtest(config)
        assert isinstance(result, BacktestResult)
        # Check result is well-formed regardless of initial_capital field
        assert isinstance(result.total_return, float)
        assert isinstance(result.pnl_bps, float)


class TestRunBacktestSynthetic:
    def test_basic_backtest_runs(self):
        config = {
            "tickers": ["SYNTH"],
            "start_date": "2020-01-01",
            "end_date": "2020-06-30",
            "interval": "1d",
            "initial_capital": 100_000.0,
            "fee_bps": 0.0,
            "spread_bps": 0.0,
            "slippage_bps": 0.0,
            "regime_model": {
                "regime_thresholds": {"low": 0.33, "high": 0.66},
                "atr_window": 14,
            },
            "strategy": {
                "strategies": [
                    {"name": "mean_reversion"},
                    {"name": "momentum"},
                ]
            },
        }
        result = run_backtest(config)
        assert isinstance(result, BacktestResult)
        assert isinstance(result.total_return, float)
        assert isinstance(result.pnl_bps, float)
        assert isinstance(result.trade_count, int)
        assert isinstance(result.win_rate, float)
        assert isinstance(result.max_drawdown_bps, float)
        assert isinstance(result.regime_weights, dict)
        assert isinstance(result.trades, list)
        assert isinstance(result.equity_curve, list)

    def test_regime_weights_sum_to_one(self):
        config = {
            "tickers": ["SYNTH"],
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "interval": "1d",
            "regime_model": {"regime_thresholds": {"low": 0.33, "high": 0.66}},
            "strategy": {"strategies": [{"name": "mean_reversion"}, {"name": "momentum"}]},
        }
        result = run_backtest(config)
        total = sum(result.regime_weights.values())
        assert abs(total - 1.0) < 0.001 or total == 0.0  # 0 bars edge case

    def test_trades_all_have_required_fields(self):
        config = {
            "tickers": ["SYNTH"],
            "start_date": "2020-01-01",
            "end_date": "2020-06-30",
            "interval": "1d",
            "regime_model": {"regime_thresholds": {"low": 0.33, "high": 0.66}},
            "strategy": {"strategies": [{"name": "mean_reversion"}, {"name": "momentum"}]},
        }
        result = run_backtest(config)
        for t in result.trades:
            assert hasattr(t, "ticker")
            assert hasattr(t, "side")
            assert hasattr(t, "entry_price")
            assert hasattr(t, "exit_price")
            assert hasattr(t, "pnl_bps")
            assert t.side in ("long", "short")

    def test_equity_curve_starts_at_one(self):
        config = {
            "tickers": ["SYNTH"],
            "start_date": "2020-01-01",
            "end_date": "2020-03-31",
            "interval": "1d",
            "regime_model": {"regime_thresholds": {"low": 0.33, "high": 0.66}},
            "strategy": {"strategies": [{"name": "mean_reversion"}, {"name": "momentum"}]},
        }
        result = run_backtest(config)
        assert len(result.equity_curve) > 0
        assert result.equity_curve[0] == 1.0

    def test_zero_cost_backtest_positive_trades(self):
        config = {
            "tickers": ["SYNTH"],
            "start_date": "2020-01-01",
            "end_date": "2020-06-30",
            "interval": "1d",
            "fee_bps": 0.0,
            "spread_bps": 0.0,
            "slippage_bps": 0.0,
            "regime_model": {"regime_thresholds": {"low": 0.33, "high": 0.66}},
            "strategy": {"strategies": [{"name": "mean_reversion"}, {"name": "momentum"}]},
        }
        result = run_backtest(config)
        for t in result.trades:
            # With zero costs, gross_return - cost should equal pnl in decimal
            assert abs(t.gross_return - (t.pnl_bps / 10_000.0)) < 0.0001

    def test_custom_capital_scaling(self):
        config = {
            "tickers": ["SYNTH"],
            "start_date": "2020-01-01",
            "end_date": "2020-03-31",
            "interval": "1d",
            "initial_capital": 1_000_000.0,
            "regime_model": {"regime_thresholds": {"low": 0.33, "high": 0.66}},
            "strategy": {"strategies": [{"name": "mean_reversion"}, {"name": "momentum"}]},
        }
        result = run_backtest(config)
        assert isinstance(result.total_return, float)


# ---------------------------------------------------------------------------
# Regime gating logic tests
# ---------------------------------------------------------------------------

class TestRegimeGatingLogic:
    def test_low_vol_uses_mean_reversion(self):
        """Low volatility regime should select mean_reversion as it's better suited."""
        combo = RegimeGatedCombo(
            strategies=[{"name": "mean_reversion"}, {"name": "momentum"}],
            regime_thresholds={"low": 0.33, "high": 0.66},
        )
        combo._fitted = True
        combo._regime_strategy_returns = {
            "low": {"mean_reversion": 20.0, "momentum": 5.0},
            "neutral": {},
            "high": {},
        }
        result = combo.predict("SYNTH", datetime.now(), {"atr_percentile": 0.1})
        assert result["regime"] == "low"
        assert result["selected_strategy"] == "mean_reversion"

    def test_high_vol_uses_momentum(self):
        """High volatility regime should select momentum as trend following benefits."""
        combo = RegimeGatedCombo(
            strategies=[{"name": "mean_reversion"}, {"name": "momentum"}],
            regime_thresholds={"low": 0.33, "high": 0.66},
        )
        combo._fitted = True
        combo._regime_strategy_returns = {
            "low": {},
            "neutral": {},
            "high": {"momentum": 25.0, "mean_reversion": 3.0},
        }
        result = combo.predict("SYNTH", datetime.now(), {"atr_percentile": 0.95})
        assert result["regime"] == "high"
        assert result["selected_strategy"] == "momentum"

    def test_neutral_regime_no_trade(self):
        combo = RegimeGatedCombo(strategies=[{"name": "mr"}])
        combo._fitted = True
        combo._regime_strategy_returns = {"low": {}, "neutral": {}, "high": {}}
        result = combo.predict("SYNTH", datetime.now(), {"atr_percentile": 0.5})
        assert result["regime"] == "neutral"
        assert result["selected_strategy"] == "none"


# ---------------------------------------------------------------------------
# Cost integration with ledger
# ---------------------------------------------------------------------------

class TestCostIntegration:
    def test_nonzero_cost_affects_pnl(self):
        config_zero = {
            "tickers": ["SYNTH"],
            "start_date": "2020-01-01",
            "end_date": "2020-06-30",
            "interval": "1d",
            "fee_bps": 0.0,
            "spread_bps": 0.0,
            "slippage_bps": 0.0,
            "regime_model": {"regime_thresholds": {"low": 0.33, "high": 0.66}},
            "strategy": {"strategies": [{"name": "mean_reversion"}, {"name": "momentum"}]},
        }
        config_cost = dict(config_zero)
        config_cost["fee_bps"] = 10.0
        config_cost["spread_bps"] = 5.0

        result_zero = run_backtest(config_zero)
        result_cost = run_backtest(config_cost)

        # Cost should reduce returns
        assert result_cost.total_return <= result_zero.total_return + 0.001


# ---------------------------------------------------------------------------
# Multi-strategy combo backtest
# ---------------------------------------------------------------------------

class TestThreeStrategyCombo:
    def test_three_strategy_combo_runs(self):
        config = {
            "tickers": ["SYNTH"],
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "interval": "1d",
            "initial_capital": 100_000.0,
            "fee_bps": 1.0,
            "spread_bps": 2.0,
            "slippage_bps": 1.0,
            "regime_model": {
                "regime_thresholds": {"low": 0.30, "high": 0.70},
                "atr_window": 20,
            },
            "strategy": {
                "strategies": [
                    {"name": "mean_reversion"},
                    {"name": "momentum"},
                    {"name": "hold"},
                ]
            },
        }
        result = run_backtest(config)
        assert isinstance(result, BacktestResult)
        assert result.trade_count >= 0
        assert 0.0 <= result.win_rate <= 1.0
        assert len(result.regime_weights) == 3  # low, neutral, high


# ---------------------------------------------------------------------------
# run_backtest output shape
# ---------------------------------------------------------------------------

class TestBacktestResultShape:
    def test_all_fields_present(self):
        config = {
            "tickers": ["SYNTH"],
            "start_date": "2020-01-01",
            "end_date": "2020-06-30",
            "interval": "1d",
            "regime_model": {"regime_thresholds": {"low": 0.33, "high": 0.66}},
            "strategy": {"strategies": [{"name": "mean_reversion"}, {"name": "momentum"}]},
        }
        result = run_backtest(config)
        fields = ["total_return", "pnl_bps", "trade_count", "win_rate",
                  "max_drawdown_bps", "regime_weights", "trades", "equity_curve"]
        for f in fields:
            assert hasattr(result, f), f"missing field: {f}"
        assert isinstance(result.total_return, float)
        assert isinstance(result.pnl_bps, float)
        assert isinstance(result.trade_count, int)
        assert isinstance(result.win_rate, float)
        assert isinstance(result.max_drawdown_bps, float)
        assert isinstance(result.regime_weights, dict)
        assert isinstance(result.trades, list)
        assert isinstance(result.equity_curve, list)

    def test_equity_curve_monotoneish(self):
        """Equity curve should not have NaN or infinite values."""
        config = {
            "tickers": ["SYNTH"],
            "start_date": "2020-01-01",
            "end_date": "2020-06-30",
            "interval": "1d",
            "regime_model": {"regime_thresholds": {"low": 0.33, "high": 0.66}},
            "strategy": {"strategies": [{"name": "mean_reversion"}, {"name": "momentum"}]},
        }
        result = run_backtest(config)
        for e in result.equity_curve:
            assert np.isfinite(e), f"non-finite equity value: {e}"
