# Opus Review — Trading Hub Phase-1 Plan

*Reviewer: Claude Opus 4.7 | Datum: 2026-05-26 | Input: 20260526_phase1_books_to_paper_trading_plan.md*

---

## Verdict

**PASS_WITH_FIXES**

Der Plan ist strukturell solide, prinzipientreu (Isichenko/Strimpel/Pik korrekt synthetisiert) und liefert klare Akzeptanzkriterien je Karte. Drei Schwächen verhindern aber direkten Implementierungsstart: (1) Die Reihenfolge der ersten Karten ist nicht topologisch korrekt — der Ledger wird vor seiner Datenquelle gebaut. (2) Eine **Strategy Registry** fehlt komplett, obwohl Promotion Gate und Strategy-Lifecycle-Labels sie zwingend voraussetzen. (3) Mehrere Karten (01, 03, 06, 08) bündeln zu viele Verantwortlichkeiten und sind für eine Sonnet-Session zu groß. Alle Fixes sind chirurgisch möglich, ohne den Plan neu zu schreiben.

---

## Critical Fixes Before Implementation

1. **Strategy Registry als neue Karte einfügen** — Ohne Registry mit Status-Feld (`research` / `experimental` / `paper-tracked` / `rejected`) und Versionierung kann das Promotion Gate (Karte 10) nicht funktionieren, der Trade-Log lässt sich nicht zu Strategie-Versionen zurückverfolgen, und Graham Ch1 / Pik Ch2 Lifecycle-Labels haben keine technische Verankerung. Pflicht vor Karte 10.

2. **Topologische Reihenfolge korrigieren** — Karte 03 (PIT-Datenpipeline) muss vor Karte 01 (Ledger) kommen. Der Ledger braucht Mark-to-Market-Daten; das Cost-Modell braucht ADV. Aktuelle Reihenfolge erzeugt Mock-Daten-Coupling.

3. **Karte 01 splitten** — `PaperLedger` und `VirtualAccount` sind zwei distinkte Verantwortlichkeiten: VirtualAccount = Kapital + Positionen + Invarianten; PaperLedger = Trade-Log + PnL-History + Mark-to-Market-Loop. Eine Sonnet-Session pro Klasse.

4. **Karte 06 splitten** — MeanRev, Momentum, Hurst und Volume-Adjustment in einer Karte ist zu viel. Mindestens auftrennen in: (a) Basis-Signal-Interface + MeanRev, (b) Momentum + Hurst, (c) Volume-Adjustment-Layer. Jedes Signal mit eigener IC-Validierung.

5. **IB-API in Phase 1 vollständig ausschließen** — Der Plan referenziert Strimpel Ch12 (IB-API Paper Trading auf Port 7497). Eine Single-Char-Änderung (7497 → 7496) wechselt zu Live-Trading. Phase 1 darf **nur** den internen Simulator nutzen; `ibapi` darf nicht importierbar sein. Ergänzung in Sicherheitsregeln nötig.

6. **Drawdown-Stop verschärfen** — −30% Hard-Stop ist für Paper-Trading mit Research-Charakter zu großzügig (Isichenko empfiehlt CVaR-basierte Limits, Pik Ex8 erwähnt drawdown-recovery). Empfehlung: −15% triggert Position-Reduction auf 50%, −25% triggert vollständige Pause. Die −30%-Regel ist OK als Final-Pause-Schwelle.

7. **Walk-Forward PIT-Validation pro OOS-Bar** — Karte 04 muss explizit verlangen, dass `validate_pit_compliance()` für jeden einzelnen OOS-Bar im Sliding Window läuft, nicht nur einmal am Anfang. Sonst entsteht subtiler Lookahead durch shared Feature-Buffers zwischen Splits. Dieser Punkt fehlt in den aktuellen Akzeptanzkriterien.

---

## Roadmap Reordering

**Neue Reihenfolge der ersten 5 Cards:**

1. **Karte A (war 03)** — PIT-Datenpipeline mit `available_at`-Enforcement
   *Basis für alles. Liefert kontrollierte Daten + Validator.*

2. **Karte B (war 02)** — Cost/Slippage-Modell + Sensitivitätsreport
   *Pure Funktion ohne Datenabhängigkeit. Kann parallel zu A entwickelt werden.*

3. **Karte C (NEU)** — Virtual Account (Kapital + Positionen + Invarianten)
   *Aus altem Karte 01 herausgelöst. Reine Buchhaltungsklasse.*

4. **Karte D (war 01, reduziert)** — Paper Ledger (Trade-Log + Mark-to-Market + PnL-History)
   *Nutzt Karte C als Backend. SQLite-Schema dokumentiert.*

5. **Karte E (NEU)** — Strategy Registry + Config Schema
   *YAML/TOML Config, Strategy-Status-Felder, Versions-Tracking. Voraussetzung für jede spätere Karte.*

Danach unverändert: Walk-Forward, Risk Engine, Regime-Router, Signal-Engine (gesplittet), Combiner, Reporting, Promotion Gate, Calibration, Crowding Risk.

---

## First Implementation Card Recommendation

### Card: **Karte A — PIT-Datenpipeline mit `available_at`-Enforcement**

**Warum diese zuerst:**
- Einzige Karte, die ohne andere Komponenten testbar ist (keine Inputs außer rohen Datenquellen).
- Liefert die unverzichtbare PIT-Garantie, von der jede andere Komponente abhängt.
- Wenn diese Karte falsch ist, sind alle nachgelagerten Karten korrumpiert — also der maximale Hebel für frühe Qualitätssicherung.
- Klein genug für eine fokussierte Sonnet-Session (geschätzt 300–400 LOC inkl. Tests).

**Was Sonnet genau bauen soll:**
- `data/pit_store.py`: Klasse `PITDataStore` mit Read-API, die für jeden Datensatz `available_at` zurückliefert.
- `data/validators.py`: Funktion `validate_pit_compliance(signal_time, feature_df)` — wirft `LookaheadError` bei Verletzung.
- Adapter für **eine** Datenquelle (yfinance für Aktien ODER ccxt-Read-Only für Krypto — Sonnet wählt eine).
- Storage-Layer: HDF5 ODER ArcticDB — Sonnet wählt eine, dokumentiert die Wahl.
- pytest-Suite mit mindestens: (a) Lookahead wird erkannt, (b) `available_at` ist immer < `signal_time`, (c) Survival-Bias-Test: delisted-Asset-Stub gibt Daten zurück.

**Was Sonnet NICHT bauen soll:**
- **KEIN** Ledger, VirtualAccount, oder Mark-to-Market.
- **KEIN** Signal, kein Backtest, keine Strategie.
- **KEINE** Discord-Anbindung.
- **KEIN** IB-API, **KEIN** ccxt-Order-Code (nur Read-Endpunkte).
- **KEINE** zweite Datenquelle — die zweite kommt in einer separaten Folgekarte.
- **KEINE** Konfigurations-UI oder Dashboard.

---

## Safety Checklist For Sonnet

Diese Regeln **müssen wortwörtlich** im nächsten Implementierungsprompt erscheinen:

1. **No-Lookahead Hard Gate**: Jede Funktion, die historische Daten konsumiert, ruft `validate_pit_compliance()` vor Nutzung auf. Bei Verletzung: `raise LookaheadError`, kein Silent-Skip.

2. **No-Live-Trading Imports verboten**: `ibapi`, `ccxt.binance().create_order`, `interactive_brokers`, `alpaca_trade_api.rest.REST.submit_order` dürfen nicht importiert werden. `ccxt` nur für Read-Endpunkte (`fetch_ohlcv`, `fetch_ticker`).

3. **No-Real-Money Defaults**: Alle Konstruktor-Parameter, die Kapital, Leverage oder Orders betreffen, müssen explizite Default-Werte tragen (`paper_mode=True`, `live=False`). Kein Default darf in echte Order-Pfade führen.

4. **Deterministische Reproduzierbarkeit**: Alle Random-Komponenten (HMM-Init, Sampling) brauchen `random_state=42` als Default. Datums-Operationen in UTC.

5. **PIT-Audit pro Test**: Jeder neue Test, der eine Strategie/Signal/Backtest aufruft, muss vor dem Assert `validate_pit_compliance()` durchlaufen.

6. **Files-Layout-Disziplin**: Sonnet erstellt nur die in der Karte genannten Module. Keine "praktischen Helper" in eigenen Files. Kein README, keine Doku — nur Code + pytest.

7. **Storage-Schema explizit**: Wenn SQLite/HDF5 angefasst wird, muss ein Schema-Dump-Skript (`scripts/dump_schema.py`) ausgegeben werden. Magic-Strings als Tabellennamen verboten.

8. **Discord-Alerts mit Paper-Prefix**: Sobald `DiscordReporter` gebaut wird (spätere Karte), muss jede Nachricht mit `[PAPER]` beginnen — präventiv jetzt schon in Sicherheitsregeln verankern.

9. **Card-Scope-Disziplin**: Sonnet implementiert ausschließlich die in der aktiven Karte definierten Module. Wenn eine Abhängigkeit fehlt, wird sie als Mock + TODO markiert, **nicht** spontan mitgebaut. "Out-of-scope work" ist ein Fehler.

10. **Drawdown-Stop-Werte**: −15% Position-Reduction, −25% Pause, −30% Final-Stop. Diese Werte sind als Defaults im Config-File hartzucodieren, sobald Karte E (Config) gebaut wird.

---

*Review abgeschlossen. Bereit für Phase-2-Implementierungsprompt mit Sonnet auf Karte A (PIT-Datenpipeline).*
