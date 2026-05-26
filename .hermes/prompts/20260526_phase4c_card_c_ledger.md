Du bist Claude Code Opus im Implementierungsmodus. Arbeite präzise, architektur-bewusst und testgetrieben.

Aufgabe: Implementiere NUR Karte C — Ledger/Position-Tracking-Modul für Trading Hub Paper-Trading.

Kontext / Stand:
- Karte A PIT-Datenpipeline ist abgeschlossen.
- Karte B Cost/Slippage Model ist abgeschlossen.
  - trading_hub/costs.py mit apply_cost_to_return(), estimate_round_trip_cost_bps(), build_slippage_sensitivity_matrix()
  - tests/test_cost_model.py: 17/17 Tests grün, Suite 118/118 grün.
- Karte C soll bewusst unabhängig von Backtest Runner, Strategie, Reporting und Discord bleiben.

Bitte zuerst lesen:
1. /root/trading/markov-strategy/.hermes/plans/20260526_phase1_books_to_paper_trading_plan.md falls vorhanden.
2. /root/trading/markov-strategy/.hermes/plans/20260526_phase2_opus_plan_review.md falls vorhanden.
3. tests/test_cost_model.py als Testmuster.
4. trading_hub/costs.py — Ledger nutzt apply_cost_to_return() aus Card B.
5. pyproject.toml.

Nicht lesen / nicht anfassen:
- Keine full_text.md Buchdateien.
- Keine Exchange-/Broker-Codepfade.
- Keine Secrets / .env / Auth-Dateien.
- Keine Discord-/Telegram-Anbindung.
- Keine weitere Card.

Ziel für Karte C:
Erstelle ein reines In-Memory Ledger-Modul:
- trading_hub/ledger.py
- tests/test_ledger.py

Gewünschte Public API:
1. open_position(ticker, side, entry_price, size, entry_time, cost_bps) -> position_id
   - Bucht eine neue offene Position.
   - Position-ID ist ein简短 deterministic hash oder UUID.
   - Erfasst: ticker, side (long SHORT), entry_price, size, entry_time, cost_bps.
   - Setzt status="open".

2. close_position(position_id, exit_price, exit_time) -> pnl_bps
   - Schließt eine offene Position zum exit_price.
   - Nutzt apply_cost_to_return() aus trading_hub.costs für Brutto-Rendite.
   - Berechnet: entry_cost + exit_cost + slippage (aus cost_bps beim Öffnen).
   - Setzt status="closed", pnl_bps, exit_time.

3. get_open_positions() -> list[Position]
   - Gibt alle offenen Positionen zurück.

4. get_position_history() -> list[Position]
   - Gibt alle geschlossenen Positionen zurück.

5. compute_aggregate_pnl() -> aggregate_metrics
   - Aggregierte Metriken über alle geschlossenen Positionen:
     total_pnl_bps, win_rate, avg_win_bps, avg_loss_bps, max_drawdown_bps, trade_count.
   - Keine offenen Positionen in Aggregation.

6. is_position_open(position_id) -> bool

Interne Helfer:
- _Position NamedTuple oder dataclass: id, ticker, side, entry_price, size, entry_time, exit_price, exit_time, cost_bps, status, pnl_bps
- Positions-Speicher: einfache list oder dict in Modul-Level Variable (keine DB, kein State-File).

Akzeptanzkriterien:
- Alles ist deterministic und offline.
- Kein Netzwerk.
- Kein yfinance/ccxt/ibapi/import von Broker-Libs.
- Keine Orders, keine Live-Ausführung, keine Side Effects.
- open + close + pnl-Berechnung in BPS (nutzt apply_cost_to_return aus Card B als externen Import).
- Negative Inputs (negative prices, size <= 0, etc.) werfen ValueError.
- close_position für unbekannte oder bereits geschlossene ID wirft ValueError.
- Tests decken mindestens ab:
  - open und close einer long Position mit positivem PnL.
  - open und close einer short Position mit positivem PnL.
  - close einer Position mit negativem PnL (Kosten > Return).
  - Win-Rate-Berechnung (2 gewonnen, 1 verloren = 66.7%).
  - max_drawdown_bps Berechnung.
  - is_position_open Verhalten.
  - Fehlerfälle: negative Preise, size=0, doppeltes close.
  - compute_aggregate_pnl mit leerem History = 0/0 trades.
  - Isolation: kein Broker-/Netzwerk-Import per AST-Scan (wie in test_cost_model.py).

Nach Implementierung:
1. Führe tests/test_ledger.py aus — alle müssen grün sein.
2. Führe die volle Suite aus: uv run python -m pytest tests -q.
3. Statischer Scan: keine secrets, shell, eval, network, order in den neuen Dateien.
4. Schreibe exakt Drei Zeilen als Abschluss:
   - "PASS: test_ledger.py"
   - "PASS: full suite"
   - "Neue Dateien: trading_hub/ledger.py, tests/test_ledger.py"