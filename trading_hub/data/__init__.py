"""
trading_hub.data — PIT-konforme Datenpipeline.

Einstiegspunkte:
  PITDataStore  — lokaler CSV-basierter Store mit available_at-Enforcement
  fetch_yfinance — Read-only yfinance-Adapter (paper/research only)
  validate_pit_compliance — wirft LookaheadError bei Lookahead-Verletzung
  LookaheadError — Exception-Typ für PIT-Verletzungen

Storage-Entscheidung: HDF5/ArcticDB nicht im Projekt-venv vorhanden.
Wir verwenden pandas CSV + JSON-Sidecar (_available_at.json).
Das ist konsistent mit den bestehenden Projekt-Mustern und erfordert
keine zusätzlichen Abhängigkeiten.
"""

from trading_hub.data.validators import LookaheadError, validate_pit_compliance
from trading_hub.data.pit_store import PITDataStore, fetch_yfinance

__all__ = [
    "LookaheadError",
    "validate_pit_compliance",
    "PITDataStore",
    "fetch_yfinance",
]
