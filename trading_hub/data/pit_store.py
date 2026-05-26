"""
PITDataStore — Point-in-Time-konformer lokaler Datenspeicher.

Storage-Entscheidung: pandas CSV + JSON-Sidecar.
  - Kein HDF5/ArcticDB im Projekt-venv vorhanden.
  - CSV ist konsistent mit bestehenden Projekt-Patterns.
  - JSON-Sidecar speichert available_at-Metadaten pro Symbol.
  - Erfordert keine zusätzlichen Abhängigkeiten.

PIT-Konvention für EOD-Daten:
  - Tag-T-Schlusskurs wird als available_at = T + 1 Werktag gestempelt.
  - Signale an Tag T dürfen only Daten mit available_at < T nutzen,
    d.h. faktisch Daten bis einschließlich T-1-Schluss.

Kein Live-Trading. Keine Broker-Anbindung. Kein ccxt-Order-Code.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import pandas as pd

from trading_hub.data.validators import validate_pit_compliance


_EOD_AVAILABLE_AT_OFFSET = pd.tseries.offsets.BusinessDay(1)


class PITDataStore:
    """Local filesystem store for PIT-compliant OHLCV data.

    Layout on disk (per symbol "BTC-USD"):
        <data_dir>/
            BTC-USD.csv           — OHLCV data with available_at column
            BTC-USD_metadata.json — last_updated, symbol, source

    Parameters
    ----------
    data_dir:
        Directory for local CSV storage. Created if it does not exist.
    """

    def __init__(self, data_dir: str | os.PathLike) -> None:
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write(
        self,
        symbol: str,
        df: pd.DataFrame,
        source: str = "local",
        available_at_offset: Optional[pd.tseries.offsets.DateOffset] = None,
    ) -> None:
        """Persist OHLCV DataFrame for symbol with available_at column.

        If the DataFrame already contains an 'available_at' column it is
        kept as-is. Otherwise, available_at is derived as:
            available_at = date_index + available_at_offset
        where the default offset is +1 business day (EOD convention).

        Parameters
        ----------
        symbol:
            Asset identifier, e.g. "SPY" or "BTC-USD".
        df:
            OHLCV DataFrame. Index should be datetime (UTC recommended).
        source:
            Human-readable data source label stored in metadata.
        available_at_offset:
            Override the +1 business day default for non-EOD data.
        """
        df = df.copy()

        if "available_at" not in df.columns:
            offset = available_at_offset if available_at_offset is not None else _EOD_AVAILABLE_AT_OFFSET
            df["available_at"] = df.index + offset

        csv_path = self._csv_path(symbol)
        df.to_csv(csv_path)

        meta = {
            "symbol": symbol,
            "source": source,
            "rows": len(df),
            "first_date": str(df.index.min()),
            "last_date": str(df.index.max()),
        }
        meta_path = self._meta_path(symbol)
        meta_path.write_text(json.dumps(meta, indent=2))

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read(
        self,
        symbol: str,
        as_of: Optional[pd.Timestamp] = None,
    ) -> pd.DataFrame:
        """Load PIT-safe OHLCV data for symbol.

        Returns only rows where available_at <= as_of. If as_of is None,
        all rows are returned (useful for bootstrap/calibration).

        The returned DataFrame always has an 'available_at' column.
        Use validate_pit_compliance(signal_time, df) before consuming
        the data in a signal or backtest.

        Parameters
        ----------
        symbol:
            Asset identifier.
        as_of:
            Cut-off timestamp. Rows with available_at > as_of are filtered out.

        Raises
        ------
        FileNotFoundError
            If no data for symbol exists in the store.
        """
        csv_path = self._csv_path(symbol)
        if not csv_path.exists():
            raise FileNotFoundError(
                f"No data for symbol '{symbol}' in store at {self._dir}. "
                "Call write() or fetch_yfinance() first."
            )

        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        df["available_at"] = pd.to_datetime(df["available_at"])

        if as_of is not None:
            as_of = pd.Timestamp(as_of)
            df = df[df["available_at"] <= as_of]

        return df

    def symbols(self) -> list[str]:
        """Return list of symbols present in the store."""
        return [p.stem for p in self._dir.glob("*.csv")]

    def has_symbol(self, symbol: str) -> bool:
        return self._csv_path(symbol).exists()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _csv_path(self, symbol: str) -> Path:
        safe = symbol.replace("/", "-")
        return self._dir / f"{safe}.csv"

    def _meta_path(self, symbol: str) -> Path:
        safe = symbol.replace("/", "-")
        return self._dir / f"{safe}_metadata.json"


# ------------------------------------------------------------------
# yfinance adapter (read-only, paper/research only)
# ------------------------------------------------------------------

def fetch_yfinance(
    symbol: str,
    start: str,
    end: Optional[str] = None,
    interval: str = "1d",
) -> pd.DataFrame:
    """Fetch OHLCV data via yfinance (read-only).

    Returns a DataFrame with lowercase column names and an 'available_at'
    column stamped as close_date + 1 business day (EOD PIT convention).

    No orders. No trading. No API keys. Read-only.

    Parameters
    ----------
    symbol:
        Asset ticker, e.g. "SPY", "BTC-USD".
    start:
        Start date string, e.g. "2020-01-01".
    end:
        End date string. Defaults to today if None.
    interval:
        Bar interval. Default "1d" (daily).

    Raises
    ------
    ImportError
        If yfinance is not installed (optional dependency).
    """
    try:
        import yfinance as yf  # optional dependency
    except ImportError as exc:
        raise ImportError(
            "yfinance is not installed. Install it with: pip install yfinance\n"
            "Or add it to pyproject.toml optional-dependencies."
        ) from exc

    ticker = yf.Ticker(symbol)
    raw = ticker.history(start=start, end=end, interval=interval, auto_adjust=True)

    if raw.empty:
        raise ValueError(
            f"yfinance returned no data for symbol='{symbol}' "
            f"start='{start}' end='{end}'. "
            "Symbol may be delisted or ticker name is incorrect."
        )

    df = raw.copy()
    df.index = pd.to_datetime(df.index).tz_localize(None)  # normalize to tz-naive UTC
    df.columns = [c.lower() for c in df.columns]

    # EOD PIT convention: day-T data available at T+1 business day open
    df["available_at"] = df.index + _EOD_AVAILABLE_AT_OFFSET

    return df
