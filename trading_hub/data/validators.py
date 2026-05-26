"""
PIT-Compliance-Validator.

Regel: Ein Signal zum Zeitpunkt T darf ausschließlich auf Daten basieren,
die zum Zeitpunkt T bereits "available_at" sind, d.h. available_at < T.

Verletzung → LookaheadError (keine stille Fortsetzung).
"""

from __future__ import annotations

import pandas as pd


class LookaheadError(Exception):
    """Raised when a feature DataFrame contains future data relative to signal_time."""


def validate_pit_compliance(
    signal_time: pd.Timestamp,
    feature_df: pd.DataFrame,
    available_at_col: str = "available_at",
) -> None:
    """Raise LookaheadError if any row has available_at >= signal_time.

    Parameters
    ----------
    signal_time:
        The timestamp at which the signal is generated.
        Must be timezone-aware (UTC) or timezone-naive consistently with feature_df.
    feature_df:
        DataFrame that must have an `available_at` column (or the column named
        by available_at_col). Each row represents a data point used as a feature.
    available_at_col:
        Name of the column holding the timestamp when the data became available.

    Raises
    ------
    LookaheadError
        If available_at_col is missing, or if any row violates available_at < signal_time.
    """
    if available_at_col not in feature_df.columns:
        raise LookaheadError(
            f"Column '{available_at_col}' missing from feature_df. "
            "All feature DataFrames must carry an available_at column."
        )

    violations = feature_df[feature_df[available_at_col] >= signal_time]
    if not violations.empty:
        first = violations[available_at_col].iloc[0]
        raise LookaheadError(
            f"Lookahead detected: {len(violations)} row(s) have "
            f"available_at >= signal_time ({signal_time}). "
            f"First violation: available_at={first}."
        )
