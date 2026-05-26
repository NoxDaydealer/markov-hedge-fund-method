"""
Tests für Karte A — PIT-Datenpipeline.

Kein Netzwerk. Kein yfinance. Nur lokale Fixtures.
Alle Tests prüfen PIT-Garantien, die alle nachgelagerten Komponenten voraussetzen.
"""

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from trading_hub.data.validators import LookaheadError, validate_pit_compliance
from trading_hub.data.pit_store import PITDataStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_ohlcv(n_days: int = 10, start: str = "2024-01-02") -> pd.DataFrame:
    """Build a minimal OHLCV DataFrame for testing (no network calls)."""
    dates = pd.date_range(start=start, periods=n_days, freq="B")  # business days
    return pd.DataFrame(
        {
            "open": 100.0 + pd.RangeIndex(n_days),
            "high": 105.0 + pd.RangeIndex(n_days),
            "low": 95.0 + pd.RangeIndex(n_days),
            "close": 101.0 + pd.RangeIndex(n_days),
            "volume": 1_000_000,
        },
        index=dates,
    )


@pytest.fixture
def tmp_store(tmp_path):
    return PITDataStore(tmp_path / "pit_store")


@pytest.fixture
def sample_df():
    return _make_ohlcv()


# ---------------------------------------------------------------------------
# 1. validate_pit_compliance — Lookahead wird erkannt
# ---------------------------------------------------------------------------

class TestValidatePitCompliance:

    def test_clean_data_passes(self, sample_df):
        """No exception when all available_at are strictly before signal_time."""
        df = sample_df.copy()
        # available_at = index + 1 business day (normal PITDataStore convention)
        df["available_at"] = df.index + pd.tseries.offsets.BusinessDay(1)
        signal_time = pd.Timestamp("2024-01-20")  # well after all available_at

        validate_pit_compliance(signal_time, df)  # must not raise

    def test_lookahead_raises(self, sample_df):
        """LookaheadError raised when a row has available_at >= signal_time."""
        df = sample_df.copy()
        # available_at same day as signal — this is a lookahead violation
        df["available_at"] = df.index + pd.tseries.offsets.BusinessDay(1)
        signal_time = df["available_at"].iloc[5]  # exactly equal to row 5 → violation

        with pytest.raises(LookaheadError, match="Lookahead detected"):
            validate_pit_compliance(signal_time, df)

    def test_future_available_at_raises(self, sample_df):
        """LookaheadError raised when available_at is after signal_time."""
        df = sample_df.copy()
        df["available_at"] = pd.Timestamp("2025-01-01")  # far future
        signal_time = pd.Timestamp("2024-06-01")

        with pytest.raises(LookaheadError):
            validate_pit_compliance(signal_time, df)

    def test_missing_available_at_column_raises(self, sample_df):
        """LookaheadError raised when available_at column is absent."""
        with pytest.raises(LookaheadError, match="Column 'available_at' missing"):
            validate_pit_compliance(pd.Timestamp("2024-06-01"), sample_df)

    def test_empty_dataframe_passes(self):
        """Empty DataFrame with available_at column does not raise."""
        df = pd.DataFrame(columns=["open", "close", "available_at"])
        validate_pit_compliance(pd.Timestamp("2024-06-01"), df)  # no rows → no violation

    def test_custom_column_name(self, sample_df):
        """Custom available_at column name is respected."""
        df = sample_df.copy()
        df["data_ready"] = pd.Timestamp("2020-01-01")  # well in the past

        validate_pit_compliance(
            pd.Timestamp("2024-06-01"),
            df,
            available_at_col="data_ready",
        )  # must not raise


# ---------------------------------------------------------------------------
# 2. PITDataStore — available_at immer <= as_of
# ---------------------------------------------------------------------------

class TestPITDataStore:

    def test_write_creates_csv(self, tmp_store, sample_df):
        tmp_store.write("SPY", sample_df)
        csv_path = tmp_store._csv_path("SPY")
        assert csv_path.exists()

    def test_write_creates_metadata(self, tmp_store, sample_df):
        tmp_store.write("SPY", sample_df, source="test_fixture")
        meta_path = tmp_store._meta_path("SPY")
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text())
        assert meta["symbol"] == "SPY"
        assert meta["source"] == "test_fixture"
        assert meta["rows"] == len(sample_df)

    def test_read_roundtrip(self, tmp_store, sample_df):
        """Write and read back produces identical close column."""
        tmp_store.write("SPY", sample_df)
        loaded = tmp_store.read("SPY")
        pd.testing.assert_series_equal(
            sample_df["close"].reset_index(drop=True),
            loaded["close"].reset_index(drop=True),
            check_names=False,
        )

    def test_available_at_always_before_or_equal_as_of(self, tmp_store, sample_df):
        """All rows returned by read(as_of=T) satisfy available_at <= T."""
        tmp_store.write("SPY", sample_df)
        as_of = pd.Timestamp("2024-01-10")
        loaded = tmp_store.read("SPY", as_of=as_of)

        assert not loaded.empty, "Expected at least one row before as_of"
        assert (loaded["available_at"] <= as_of).all(), (
            "PITDataStore.read() returned rows with available_at > as_of — "
            "this is a lookahead violation in the store layer."
        )

    def test_read_no_rows_after_as_of_boundary(self, tmp_store, sample_df):
        """read(as_of=very_early) returns empty DataFrame."""
        tmp_store.write("SPY", sample_df)
        as_of = pd.Timestamp("2020-01-01")  # before any data
        loaded = tmp_store.read("SPY", as_of=as_of)
        assert loaded.empty

    def test_eod_available_at_offset(self, tmp_store, sample_df):
        """available_at defaults to date + 1 business day (EOD PIT convention)."""
        tmp_store.write("SPY", sample_df)
        loaded = tmp_store.read("SPY")

        first_date = loaded.index[0]
        expected_available = first_date + pd.tseries.offsets.BusinessDay(1)
        actual_available = loaded["available_at"].iloc[0]

        assert actual_available == expected_available, (
            f"Expected available_at={expected_available}, got {actual_available}. "
            "EOD PIT convention: day-T data available at T+1 business day."
        )

    def test_existing_available_at_preserved(self, tmp_store, sample_df):
        """If DataFrame already has available_at, it is not overwritten."""
        df = sample_df.copy()
        custom_ts = pd.Timestamp("2030-12-31")
        df["available_at"] = custom_ts

        tmp_store.write("SPY", df)
        loaded = tmp_store.read("SPY")

        assert (loaded["available_at"] == custom_ts).all()

    def test_read_unknown_symbol_raises(self, tmp_store):
        with pytest.raises(FileNotFoundError, match="No data for symbol"):
            tmp_store.read("UNKNOWN_XYZ")

    def test_symbols_list(self, tmp_store, sample_df):
        tmp_store.write("SPY", sample_df)
        tmp_store.write("BTC-USD", sample_df)
        syms = set(tmp_store.symbols())
        assert "SPY" in syms
        assert "BTC-USD" in syms

    def test_has_symbol(self, tmp_store, sample_df):
        assert not tmp_store.has_symbol("SPY")
        tmp_store.write("SPY", sample_df)
        assert tmp_store.has_symbol("SPY")


# ---------------------------------------------------------------------------
# 3. Survival Bias — "delisted" asset returns historical data
# ---------------------------------------------------------------------------

class TestSurvivalBias:

    def test_delisted_stub_returns_data(self, tmp_store):
        """A 'delisted' symbol written once still returns its historical data.

        This ensures survival-bias correctness: past backtests must include
        assets that no longer exist. PITDataStore stores data permanently
        regardless of whether the asset is still tradeable.
        """
        # Simulate LUNA's last trading week before delisting
        delisted_df = _make_ohlcv(n_days=5, start="2022-05-05")
        delisted_df["close"] = [85.0, 42.0, 18.0, 6.0, 0.10]  # collapse

        tmp_store.write("LUNA-USD", delisted_df, source="historical_fixture")

        # Much later as_of: data should still be readable for backtesting
        loaded = tmp_store.read("LUNA-USD", as_of=pd.Timestamp("2025-01-01"))

        assert len(loaded) == 5, "Delisted asset's full history must be retrievable"
        assert loaded["close"].iloc[-1] == pytest.approx(0.10)

    def test_delisted_and_active_coexist(self, tmp_store, sample_df):
        """Delisted and active symbols coexist in the store without conflict."""
        delisted_df = _make_ohlcv(n_days=3, start="2022-05-05")
        tmp_store.write("LUNA-USD", delisted_df)
        tmp_store.write("SPY", sample_df)

        syms = tmp_store.symbols()
        assert "LUNA-USD" in syms
        assert "SPY" in syms


# ---------------------------------------------------------------------------
# 4. Integration: write → read → validate_pit_compliance pipeline
# ---------------------------------------------------------------------------

class TestEndToEndPITPipeline:

    def test_full_pipeline_no_lookahead(self, tmp_store, sample_df):
        """Full pipeline: write → read(as_of) → validate_pit_compliance passes."""
        tmp_store.write("SPY", sample_df)
        as_of = pd.Timestamp("2024-01-10")
        features = tmp_store.read("SPY", as_of=as_of)

        # Signal is generated one business day AFTER the last available data
        signal_time = as_of + pd.tseries.offsets.BusinessDay(1)
        validate_pit_compliance(signal_time, features)  # must not raise

    def test_full_pipeline_same_day_signal_raises(self, tmp_store, sample_df):
        """Using data available_at == signal_time raises LookaheadError."""
        tmp_store.write("SPY", sample_df)
        features = tmp_store.read("SPY")  # all rows

        # signal_time == available_at of last row → violation
        last_available_at = features["available_at"].max()
        signal_time = last_available_at  # same instant → lookahead

        with pytest.raises(LookaheadError):
            validate_pit_compliance(signal_time, features)
