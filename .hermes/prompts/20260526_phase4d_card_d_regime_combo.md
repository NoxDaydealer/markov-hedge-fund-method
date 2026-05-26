Du bist Claude Code Opus im Implementierungsmodus. Arbeite präzise, architektur-bewusst und testgetrieben.

Aufgabe: Implementiere Karte D — RegimeGatedCombo + Backtest Integration für Trading Hub Paper-Trading.

Kontext / Stand:
- Karte A PIT-Datenpipeline: trading_hub/data/pit_store.py, tests/test_pit_data_pipeline.py
- Karte B Cost/Slippage Model: trading_hub/costs.py mit apply_cost_to_return(), estimate_round_trip_cost_bps(), build_slippage_sensitivity_matrix()
- Karte C Ledger: trading_hub/ledger.py mit open_position(), close_position(), compute_aggregate_pnl()
- Karte D kombiniert A+B+C mit Regime-Gating für Strategy-Selection.

Bitte zuerst lesen:
1. trading_hub/costs.py — Import-Point für Cost-Berechnung
2. trading_hub/ledger.py — Import-Point für Position-Tracking
3. trading_hub/data/pit_store.py — Daten-Zugang für historical OHLCV
4. trading_hub/strategies/ (falls vorhanden) — existierende Strategie-Adapter
5. scripts/markov_regime.py (falls vorhanden) — bestehende Regime-Logik
6. tests/test_cost_model.py und tests/test_ledger.py — Testmuster
7. pyproject.toml

Nicht lesen / nicht anfassen:
- Keine full_text.md Buchdateien
- Keine Exchange-/Broker-Codepfade
- Keine Secrets / .env / Auth-Dateien
- Keine Discord-/Telegram-Anbindung

Ziel für Karte D:

== A) Regime Model (kompakt, papierlos) ==

Ein einfaches Regime-Modul:
- trading_hub/regime.py
- 3 Regime: NEUTRAL (0), TRENDING (1), VOLATILE (2)
- regime_from_features(volatility, trend_strength, volume_regime) -> int
- Einfache Schwellenwerte, keine ML-Abhängigkeit
- Keine Daten-Abfrage, keine Netzwerk-Calls
- Test: regime classification auf synthetischen inputs

== B) RegimeGatedCombo ==

- trading_hub/combo.py (oder trading_hub/regime_combo.py)
- Klasse RegimeGatedCombo mit Interface:
  - fit(tickers: list[str], start_date: str, end_date: str) -> self
    Lädt PIT-Daten, trainiert/tuned Regime-Schwellenwerte auf Historisch
  - predict(ticker: str, date: str, features: dict) -> dict
    Return: {regime: int, selected_strategy: str, confidence: float}
  - supported_strategies: ["mean_reversion", "momentum", "fib_liquidity"]

  Intern nutzt es regime.py für die Klassifikation.

== C) Backtest Runner ==

- trading_hub/backtest_runner.py
- Funktion run_backtest(config: dict) -> BacktestResult

  config keys:
    tickers: list[str]
    start_date: str
    end_date: str
    interval: str (z.B. "1d")
    initial_capital: float
    strategies: list[str] (aus combo.supported_strategies)
    use_regime_gating: bool
    cost_bps: float (flat roundtrip cost, default 15.0)

  BacktestResult (dataclass oder dict):
    total_return: float
    pnl_bps: float
    trade_count: int
    win_rate: float
    max_drawdown_bps: float
    sharpe_ratio: float (annualisiert, approximiert)
    regime_weights: dict[int, float] — wie oft jedes Regime aktiv war
    trades: list[dict] — jeder Trade als dict mit: entry_time, exit_time, ticker, side, pnl_bps, regime
    per_ticker_summary: dict[str, dict] — aggregate stats pro ticker

  Ablauf:
  1. Lade PIT-Daten (aus pit_store) für alle tickers
  2. Falls use_regime_gating=True: fit() RegimeGatedCombo
  3. Für jeden Tag mit verfügbaren Daten:
     a) Features berechnen (vol, trend, volume)
     b) Regime bestimmen (oder neutral wenn kein Gating)
     c) Strategie wählen (oder einfache default wenn kein Gating)
     d) Signal generieren (long/short/flat)
     e) Falls Signal != flat: open_position() im Ledger
     f) Falls open position + gegenläufiges Signal oder Ende: close_position()
  4. Nach Ende: compute_aggregate_pnl() aus Ledger
  5. Return BacktestResult

== D) Tests ==

- tests/test_regime.py — Test regime classification
- tests/test_combo.py — Test RegimeGatedCombo fit/predict
- tests/test_backtest_runner.py — Test run_backtest

Minimale Test-Abdeckung:
1. Regime classification: NEUTRAL bei niedriger Vol, TRENDING bei starkem Trend, VOLATILE bei hoher Vol
2. Combo: fit/predict Zyklus, selected_strategy wechselt mit regime
3. Backtest: 1 Ticker, 1 Strategie, 30 Tage synthetische Daten -> trade_count > 0
4. Backtest mit Cost: trades haben pnl_bps < gross_return_bps wegen kosten
5. Backtest mit Regime Gating: regime_weights Summe = 1.0
6. Ledger-Integration: backtest nutzt ledger intern
7. Kein Netz/Broker-Import per AST-Scan
8. Deterministisch: same config -> same result

Akzeptanzkriterien:
- Alles offline, deterministisch
- Kein Netzwerk, keine Broker-Libs
- Keine Orders, keine Live-Ausführung
- Tests laufen: targeted 20+, full suite passes
- Statischer Scan: keine secrets/shell/eval/network/order

WICHTIG: Zwischenergebnis sichern!
Wenn du mehr als 15 Minuten brauchst, schreibe nach jeder substanziellen Teil-Implementierung (regime.py fertig, combo.py fertig, backtest_runner.py fertig) je einen kurzen Status-Commit:
- git add -A && git commit -m "Card D WIP: [was fertig ist]"

Nach Abschluss:
1. uv run python -m pytest tests/test_regime.py tests/test_combo.py tests/test_backtest_runner.py -v
2. uv run python -m pytest tests -q
3. Statischer Scan
4. Drei Zeilen:
   "PASS: targeted tests"
   "PASS: full suite"  
   "Neue Dateien: trading_hub/regime.py, trading_hub/combo.py, trading_hub/backtest_runner.py, tests/test_regime.py, tests/test_combo.py, tests/test_backtest_runner.py"