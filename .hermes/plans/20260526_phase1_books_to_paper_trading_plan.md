# Phase 1 — Books to Paper Trading: Implementierungsplan
*Erstellt: 2026-05-26 | Research/Paper Trading only | Keine echten Orders | Kein Live-Trading*

---

## 1. Executive Decision — Die nächsten 1–3 Bausteine

**Bauen in dieser Reihenfolge:**

### Baustein 1 (sofort): PIT-konformer Paper-Ledger + Virtual Account
**Warum zuerst:** Jede weitere Arbeit ohne sauberes Ledger produziert unzuverlässige Backtests.
Isichenko Ch7, Pik Ch2 und Strimpel Ch9 sind sich einig: Simulation ≠ Backtest ≠ Produktion —
und der Ledger ist die Trennlinie. Ohne ihn kann kein Ergebnis vertraut werden.

**Was gebaut wird:** `PaperLedger`-Klasse mit Virtual Account, täglichem Mark-to-Market,
Transaktionskostenabzug (Slippage + Impact), Drawdown-Tracking und PIT-Timestamp-Enforcement.

### Baustein 2 (danach): Walk-Forward Evaluation Harness
**Warum als zweites:** Jede Strategie muss Out-of-Sample validiert werden, bevor sie in den Ledger darf.
Strimpel Ch6 (VectorBT), Isichenko Ch7 und Pik Ch2 nennen Walk-Forward als den einzigen Goldstandard.
Ein statischer Backtest ohne Walk-Forward ist eine gefährliche Illusion.

**Was gebaut wird:** Rolling-Window-Split, parameter-sensitive Sweep, IS/OOS-Sharpe-Vergleich,
t-Test auf Differenz (p-Wert < 0.05), slippage-Sensitivitätsmatrix (0.5× / 1× / 2× / 5×).

### Baustein 3 (danach): Regime-klassifizierter Signal-Router
**Warum als drittes:** Das bestehende Markov-Regime-Modell braucht eine saubere Anbindung
an die Strategie-Selektion (Momentum → Trend-Regime; Mean-Reversion → Range-Regime),
bevor weitere Signale gebaut werden. Pik Ex3+Ex4 und Isichenko Sec2.2 definieren diesen Layer präzise.

**Was gebaut wird:** `RegimeRouter`-Klasse: Regime-Wahrscheinlichkeit als kontinuierlicher Score (0–1),
graduelle Gewichtung zwischen Strategien, tägliche Kalibrierung auf 3-Jahres-Lookback.

---

## 2. Buch-Synthese — 10 handlungsleitende Prinzipien

Diese 10 Prinzipien kondensieren die drei Bücher zu direkt anwendbaren Handlungsregeln
für das Trading Hub Paper-Trading-System.

**P1 — Signal-Rausch-Ratio ist winzig: Diversifikation ist zwingend (Isichenko)**
Das SNR in Finanzmärkten beträgt ~1bps/Tag vs. ~200bps Volatilität (ε ≈ 10⁻²).
Kein Einzelsignal ist stark genug. Kombination mehrerer unkorrelierter Signale
ist keine Option — sie ist die Voraussetzung für robusten Betrieb.

**P2 — PIT zuerst, alles andere danach (Isichenko + Pik)**
Lookahead-Bias ist die häufigste und verheerendste Fehlerquelle. Jeder Datensatz
braucht einen `available_at`-Timestamp. Signal-Zeit ≠ Execution-Zeit.
Keine OHLCV-Daten des aktuellen Tages für Signale verwenden.

**P3 — Transaktionskosten müssen das Alpha übertreffen, nicht nur positiv sein (Isichenko)**
Gross Alpha und Trading-Kosten bewegen sich in derselben Größenordnung.
Eine Strategie wird nur promotet, wenn sie bei 2× Slippage noch Sharpe > 0.5 hat.
Kostenparameter periodisch an Marktdaten kalibrieren.

**P4 — Walk-Forward oder kein Vertrauen (Strimpel + Pik)**
IS/OOS-Divergenz ist der stärkste Overfitting-Indikator. Der t-Test auf die Sharpe-Differenz
(IS vs OOS, Ziel: p < 0.05) ist Pflicht. Strategien, die nur bei einem einzigen
Parameterwert profitabel sind, werden sofort verworfen (Parsimony-Prinzip: 3R-Regel).

**P5 — Regime-Bewusstsein ersetzt statische Modelle (Pik + Isichenko)**
Statische Optimierungen werden von Regime-Shifts zerstört. Das HMM-Modell
wird täglich auf einem rollierenden 3-Jahres-Lookback neu kalibriert.
Rebalancing nur bei Regime-Wechsel; Wahrscheinlichkeit als kontinuierlicher Score,
nicht als hartes 0/1-Label.

**P6 — Simulation muss Produktion matchen — sonst handelt man im Dunkeln (Isichenko)**
Slippage-Modell alle 30 Tage kalibrieren, Self-Impact in History erkennen,
Corporate Actions korrekt adjustieren, Survival-Bias ausschließen.
Der Paper-Ledger ist die einzige Wahrheitsquelle.

**P7 — Forecast-Forschung und Portfolio-Konstruktion strikt trennen (Isichenko)**
Jeder Layer hat seine eigenen Overfitting-Risiken. Alpha-Parameter werden auf dem
Training-Set einmalig festgelegt und danach nicht mehr verändert.
Portfolio-Größe und Position-Sizing sind separat kalibrierbar.

**P8 — Hierarchische Forecast-Kombination skaliert besser als flat (Isichenko)**
K Signale in √K Gruppen kombinieren, dann Gruppen kombinieren.
Nicht-negative QP-Gewichte (α_i ≥ 0) schlagen naiven Equal-Weight-Ansatz.
Diversifikations-Grenze: Bei ρ=0.25 bringen mehr als ~4 unkorrellierte Portfolios keinen Mehrwert.

**P9 — Einfache Modelle mit gutem Feature Engineering > komplexe Black Boxes (Pik)**
LightGBM/Random Forest mit ~55–65% OOS-Accuracy ist ausreichend für profitable Strategien.
RL und CNN sind erst nach Validierung einfacherer Schichten zu evaluieren.
Corrective AI (dynamische Parameter-Optimierung via ML) kann Sharpe um Faktor 3–4× steigern.

**P10 — Kelly gibt zu hohen Leverage: Monte-Carlo-Simulation als Sicherheitsventil (Isichenko)**
Φ* = E[R]/Var[R] ist nur eine grobe Orientierung (Beispiel: Sharpe=2 → Φ*=159×).
Praktische Regel: Monte-Carlo-Simulation mit strategie-spezifischen Losing Streaks.
Hard Cap: max_leverage = 2.0 im Paper-Portfolio, Drawdown-Stop bei −30%.

---

## 3. Paper-Trading-Zielarchitektur

```
┌─────────────────────────────────────────────────────────────────────┐
│                     TRADING HUB — PAPER TRADING                      │
│                  (No live orders, no real capital)                    │
└─────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────┐
  │  DATA LAYER  │    │  SIGNAL LAYER│    │     REGIME LAYER          │
  │              │    │              │    │                            │
  │ PIT-Pipeline │    │ MeanRev      │───▶│ HMM / MarkovRegression    │
  │ ArcticDB/HDF5│    │ Momentum     │    │ 3-Jahres-Lookback, tägl.  │
  │ yfinance/ccxt│    │ Hurst-H      │    │ Prob-Score (0..1)         │
  │ available_at │    │ Volume-Adj.  │    │ RegimeRouter              │
  └──────┬───────┘    └──────┬───────┘    └────────────┬─────────────┘
         │                   │                          │
         └───────────────────▼──────────────────────────▼
                    ┌─────────────────────────┐
                    │  WALK-FORWARD HARNESS    │
                    │  IS/OOS Split (kein      │
                    │  Shuffle!)               │
                    │  Slippage-Sensitivity    │
                    │  t-Test (p < 0.05)       │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  FORECAST COMBINER       │
                    │  QP Non-Negative Weights │
                    │  Hierarchische Kombi.    │
                    │  IC-gewichtet            │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  RISK ENGINE             │
                    │  CVaR (95%) Monitor      │
                    │  Kelly → Monte-Carlo Cap │
                    │  Dollar-Neutralität      │
                    │  Drawdown-Stop (−30%)    │
                    │  Leverage Cap (2×)       │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  COST / SLIPPAGE MODEL   │
                    │  C(T) = c·|T| +          │
                    │  (λ/2)·T²/ADV            │
                    │  Kalibrierung alle 30 T. │
                    │  Slippage-Matrix: ×0.5   │
                    │  ×1, ×2, ×5             │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  PAPER LEDGER            │
                    │  Virtual Account         │
                    │  Daily Mark-to-Market    │
                    │  PnL-History             │
                    │  Trade-Log (SQLite)      │
                    │  Invariantenprüfung      │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  WALK-FORWARD REPORTING  │
                    │  Sharpe / Sortino / CVaR │
                    │  Max-Drawdown            │
                    │  IC / Factor Turnover    │
                    │  Equity Curve            │
                    │  Discord-Webhook         │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  PROMOTION GATE          │
                    │  Margin-of-Safety Check  │
                    │  OOS Sharpe > 0.5 bei 2× │
                    │  Slippage                │
                    │  p-Wert < 0.05           │
                    └─────────────────────────┘
```

### Komponenten-Beschreibung

| Komponente | Funktion | Key-Klassen/Module |
|---|---|---|
| **PIT-Pipeline** | PIT-konformer Datenzugriff, `available_at`-Enforcement | `PITDataStore`, `validate_pit_compliance()` |
| **Virtual Account** | Kapital-Tracking, Mark-to-Market, Trade-Log | `VirtualAccount`, `PaperLedger` |
| **Risk Engine** | CVaR-Monitor, Kelly-Cap, Drawdown-Stop | `RiskEngine`, `RiskMonitor` |
| **Cost/Slippage Model** | C(T) = c·|T| + (λ/2)·T²/ADV, Slippage-Sensitivität | `CostModel`, `slippage_sensitivity_test()` |
| **Regime Layer** | HMM + MarkovRegression, tägl. Kalibrierung | `MarkovRegimeModel`, `RegimeRouter` |
| **Signal Layer** | MeanRev, Momentum, Hurst-H, Volume-Adj. | `SignalEngine`, `EMAStats` |
| **Walk-Forward Harness** | IS/OOS-Split, t-Test, Walk-Forward-Loop | `WalkForwardHarness` |
| **Forecast Combiner** | QP Non-Negative, hierarchische Kombi | `ForecastCombiner` |
| **Reporting** | Sharpe/CVaR/Drawdown, Discord-Webhook | `DiscordReporter`, `PerformanceReport` |
| **Promotion Gate** | Margin-of-Safety, Slippage-Robustheit | `PromotionGate` |

---

## 4. Roadmap — Implementierungskarten

### KARTE 01 — PIT-konformer Paper-Ledger

| Feld | Inhalt |
|---|---|
| **Titel** | PIT Paper-Ledger mit Virtual Account |
| **Ziel** | Saubere Simulation mit Zeitstempel-Enforcement, Mark-to-Market, Trade-Log |
| **Module/Dateien** | `paper_trading/ledger.py`, `paper_trading/virtual_account.py` |
| **Tests** | Lookahead-Audit schlägt an wenn `signal_time >= data_time`; Leverage-Überschreitung wird erkannt; Drawdown-Berechnung korrekt |
| **Akzeptanzkriterien** | 100 Simulations-Tage ohne Invarianten-Verletzung; tägliches PnL stimmt mit manuellem Referenzwert überein; Slippage korrekt abgezogen |
| **Risiko** | Timestamp-Handling bei Krypto (UTC-Inkonsistenz); Corporate-Action-Adjustment für Aktien |

---

### KARTE 02 — Kosten- und Slippage-Modell

| Feld | Inhalt |
|---|---|
| **Titel** | Konfigurierbare Cost/Slippage-Engine mit Sensitivitätsreport |
| **Ziel** | Formales Kostenmodell C(T) = c·|T| + (λ/2)·T²/ADV; Slippage-Sensitivitätsmatrix |
| **Module/Dateien** | `paper_trading/cost_model.py`, `reporting/sensitivity.py` |
| **Tests** | Kosten bei Trade=0 sind 0; Impact steigt quadratisch mit Trade-Größe; Sensitivitäts-Report produziert 4 Szenarien (0.5× / 1× / 2× / 5×) |
| **Akzeptanzkriterien** | Strategie-Promotion nur wenn OOS-Sharpe > 0.5 bei 2× Slippage; kalibrierbar ohne Code-Änderung |
| **Risiko** | ADV-Schätzung für illiquide Coins erfordert Fallback-Wert |

---

### KARTE 03 — PIT-Datenpipeline mit `available_at`-Enforcement

| Feld | Inhalt |
|---|---|
| **Titel** | PIT-sichere Datenpipeline (ArcticDB/HDF5 + Timestamp-Audit) |
| **Ziel** | Jeder Datensatz trägt `available_at`; `validate_pit_compliance()` als Pre-Signal-Hook |
| **Module/Dateien** | `data/pit_store.py`, `data/validators.py` |
| **Tests** | Validator wirft Exception bei Lookahead; Krypto-Tagesschluss erst nach `T+1`-Open verfügbar; Survival-Bias-Test auf delisted Assets |
| **Akzeptanzkriterien** | 0 Lookahead-Violations im Backtest-Log; alle Signale basieren auf `data.available_at < signal_time` |
| **Risiko** | yfinance und ccxt liefern unterschiedliche Timestamps → Normalisierung erforderlich |

---

### KARTE 04 — Walk-Forward Evaluation Harness

| Feld | Inhalt |
|---|---|
| **Titel** | Rolling Walk-Forward mit IS/OOS-Sharpe-Vergleich und t-Test |
| **Ziel** | Anti-Overfitting-Gate: Jede Strategie muss p < 0.05 im Sharpe-t-Test bestehen |
| **Module/Dateien** | `backtesting/walk_forward.py`, `backtesting/stats.py` |
| **Tests** | IS-Sharpe > OOS-Sharpe triggert Warning; bekannt overfittete Strategie wird korrekt abgelehnt; 30 Splits über 2-Jahre-Fenster laufen ohne Fehler |
| **Akzeptanzkriterien** | Automatischer Report: IS/OOS-Sharpe, t-Wert, p-Wert, Überlebensstatus; 3R-Regel (Remove/Replace/Reduce) dokumentiert |
| **Risiko** | Zu wenige OOS-Datenpunkte bei täglichen Crypto-Daten vor 2020 |

---

### KARTE 05 — Regime-Router (HMM + MarkovRegression)

| Feld | Inhalt |
|---|---|
| **Titel** | Regime-klassifizierter Strategy-Router mit tägl. Kalibrierung |
| **Ziel** | Kontinuierlicher Regime-Score (0..1); graduelle Strategie-Gewichtung statt hartem Switch |
| **Module/Dateien** | `regime/markov_model.py`, `regime/regime_router.py` |
| **Tests** | Regime-Score ∈ [0,1]; bei Neutral-Regime (Score ≈ 0.5) → gleiches Gewicht beider Strategien; Transition-Matrix wird korrekt ausgegeben |
| **Akzeptanzkriterien** | Tägliche Neukalibrierung auf 3-Jahres-Lookback; keine Zukunftsdaten im Trainings-Window; Regime-History im SQLite-Log |
| **Risiko** | hmmlearn nicht deterministisch → fixed `random_state=42`; EM-Konvergenz bei kurzen Zeitreihen |

---

### KARTE 06 — Signal-Engine (MeanRev + Momentum + Hurst)

| Feld | Inhalt |
|---|---|
| **Titel** | Regime-adaptive Signal-Engine: MeanRev, Momentum, Volume-Adj., Hurst-H |
| **Ziel** | Signale werden regime-gewichtet kombiniert: H > 0.5 → Momentum; H < 0.5 → MeanRev |
| **Module/Dateien** | `signals/mean_reversion.py`, `signals/momentum.py`, `signals/hurst.py`, `signals/combiner.py` |
| **Tests** | Hurst-RS-Analyse liefert H ∈ [0,1]; Volume-Adjustierung verstärkt Momentum bei abnormalem Volumen (vol_ratio > 1.5); Ridge-Regularisierung verhindert Overfitting |
| **Akzeptanzkriterien** | IC (Spearman) > 0.02 pro Signal; IC-IR > 0.5; kein Signal nutzt Daten des aktuellen Bars |
| **Risiko** | RS-Analyse rechenintensiv bei großem Universe → EMA-basierte Approximation als Fallback |

---

### KARTE 07 — Forecast Combiner (QP Non-Negative)

| Feld | Inhalt |
|---|---|
| **Titel** | QP-Forecast-Kombination mit nicht-negativen Gewichten |
| **Ziel** | K Signale → hierarchisch kombiniert → 1 finales Signal; QP schlägt Equal-Weight |
| **Module/Dateien** | `signals/forecast_combiner.py`, `signals/qp_weights.py` |
| **Tests** | Gewichte summieren zu 1.0; alle Gewichte ≥ 0; kombiniertes Sharpe ≥ bestes Einzelsignal bei ρ < 0.5 |
| **Akzeptanzkriterien** | 2-Stufen-Hierarchie für > 4 Signale; Korrelation zwischen Signalen wird getracked; Diversifikations-Grenze (ρ=0.25 → max 4 Portfolios) dokumentiert |
| **Risiko** | QP-Solver Instabilität bei singulären Kovarianzmatrizen → Ridge-Regularisierung |

---

### KARTE 08 — Risk Engine mit CVaR-Monitor

| Feld | Inhalt |
|---|---|
| **Titel** | Risk Engine: CVaR, Kelly-Monte-Carlo-Cap, Dollar-Neutralität, Drawdown-Stop |
| **Ziel** | Harte Risk-Guardrails: CVaR(95%) tägl. geprüft; Leverage ≤ 2×; Drawdown-Stop bei −30% |
| **Module/Dateien** | `risk/risk_engine.py`, `risk/kelly.py`, `risk/portfolio_constraints.py` |
| **Tests** | CVaR-Alert bei Überschreitung −5%; Leverage-Cap bei 2× korrekt skaliert; Dollar-Neutralität nach Rebalancing erfüllt (Σ P_s = 0 ± Toleranz) |
| **Akzeptanzkriterien** | Alle Risk-Checks täglich als Invarianten-Protokoll geloggt; Monte-Carlo Kelly-Simulation (1000 Sims, 252 Tage) läuft < 2 Sek. |
| **Risiko** | CVaR-Berechnung erfordert mind. 30 PnL-Datenpunkte → Warm-up-Phase definieren |

---

### KARTE 09 — Performance Reporting + Discord-Webhook

| Feld | Inhalt |
|---|---|
| **Titel** | Täglicher Performance-Report: Sharpe/CVaR/Drawdown + Discord-Webhook |
| **Ziel** | Automatischer täglicher Report nach Marktschluss; Trade-Alerts bei Signal-Wechsel; Risk-Alerts bei Grenzwert-Verletzung |
| **Module/Dateien** | `reporting/discord_reporter.py`, `reporting/performance.py` |
| **Tests** | Equity-Curve-Chart wird als PNG generiert; Trade-Alert enthält Symbol, Action, Regime; Risk-Alert bei CVaR < −5% |
| **Akzeptanzkriterien** | Report enthält: Annual Return, Sharpe, Sortino, Max-DD, CVaR, Regime; Chart und Metriken in einer Webhook-Nachricht; kein PII in Logs |
| **Risiko** | Discord-Webhook-Rate-Limiting bei vielen Alerts → Batching erforderlich |

---

### KARTE 10 — Promotion Gate (Margin-of-Safety)

| Feld | Inhalt |
|---|---|
| **Titel** | Automatisierter Promotion Gate mit Margin-of-Safety-Check |
| **Ziel** | Strategie wird nur in Paper-Ledger aufgenommen wenn sie definierte Hürden übersteht |
| **Module/Dateien** | `backtesting/promotion_gate.py` |
| **Tests** | Absichtlich schlechte Strategie (Sharpe < 0) wird korrekt abgelehnt; OOS-Sharpe bei 2× Slippage < 0.5 → rejected; p > 0.05 → rejected |
| **Akzeptanzkriterien** | 3 Hürden: (1) OOS-Sharpe > 0.5 bei 2× Slippage; (2) p-Wert < 0.05; (3) Max-DD > −30%; Rejection-Grund im Log dokumentiert |
| **Risiko** | Zu strenge Hürden könnten alle Crypto-Strategien in Bear-Phasen abschneiden → Regime-bedingte Schwellwerte prüfen |

---

### KARTE 11 — Slippage-Kalibrierungs-Job (30-Tage-Cycle)

| Feld | Inhalt |
|---|---|
| **Titel** | Automatischer Slippage-Kalibrierungs-Job alle 30 Tage |
| **Ziel** | Kostenparameter bleiben marktnahe; Self-Impact in History erkennbar |
| **Module/Dateien** | `paper_trading/cost_calibration.py`, `scripts/calibrate_costs.py` |
| **Tests** | Kalibrierung ohne Lookahead in historischen Trades; Parameteränderung um > 20% triggert Alert |
| **Akzeptanzkriterien** | Kalibrierungsprotokoll in SQLite; aktueller Slippage-Parameter sichtbar im täglichen Report |
| **Risiko** | Crypto-Spreads sehr variabel (Bull vs. Bear) → Regime-bedingte Kalibrierung als Erweiterung |

---

### KARTE 12 — Crowding/Liquidations-Risk-Screen

| Feld | Inhalt |
|---|---|
| **Titel** | Crypto Crowding-Risk-Screen (Funding Rate, OI, Cross-Correlation) |
| **Ziel** | Frühwarnung vor Quant-Crashes durch gleichzeitige Liquidation ähnlicher Portfolios |
| **Module/Dateien** | `risk/crowding_risk.py` |
| **Tests** | Crowding-Score ∈ [0,1]; Funding Rate > 0.1% → Score-Beitrag korrekt; Cross-Correlation-Spike wird erkannt |
| **Akzeptanzkriterien** | Crowding-Score > 0.6 → automatischer Position-Reduction-Alert; Score-History im täglichen Report |
| **Risiko** | Funding-Rate-Daten nur für Perps verfügbar; Spot-Positionen brauchen alternativen Proxy |

---

## 5. Priorisierte Foto/OCR-Nachforderungen

Maximale 8 Items aus den ersten 3 Büchern (Bücher 4–6 nicht eingeschlossen).
Diese Captures würden den größten Mehrwert liefern, da die Summaries zwar die Konzepte erklären,
aber keine genauen Formeln, Checklistennummern oder genauen Seitentexte enthalten.

**#1 — KRITISCH: Isichenko Ch7 §7.1–7.4 — Simulation vs. Production + Paper Trading**
*Warum:* Die genaue Checkliste (9 Items in der Summary) muss vollständig vorliegen.
Die Summary zeigt die Items, aber die ursprüngliche Formulierung aus dem Buch entscheidet
ob wir alle Edge-Cases abgedeckt haben. Direkte Grundlage für Karte 01.

**#2 — KRITISCH: Isichenko Ch5 §5.1–5.2 — Slippage + Linear Impact Formeln**
*Warum:* Die exakten Formeln für das Kostenmodell C(T) = c·|T| + (λ/2)·T²/ADV müssen
kalibrierbare Parameter enthalten. Die "Comfort Zone"-Formel (P_min*, P_max*) ist Grundlage
für Karte 02 und Karte 11.

**#3 — KRITISCH: Isichenko Ch6.9 — Kelly Criterion + Monte-Carlo Leverage**
*Warum:* Die Summary liefert die Grundformel, aber der Monte-Carlo-Teil (simulate_kelly_leverage)
braucht genaue Parameter-Empfehlungen (n_sims, n_days, leverage_values) aus dem Original.
Direkte Grundlage für Karte 08.

**#4 — WICHTIG: Strimpel Ch6 — Walk-Forward Optimization VectorBT Parameter-Grid**
*Warum:* Die konkreten Split-Parameter (n=30, window_len=365×2, set_lens=180) müssen
für Crypto-Daten (24/7, niedrigere Liquidität) validiert und angepasst werden.
Grundlage für Karte 04.

**#5 — WICHTIG: Strimpel Ch8 — IC + Factor Turnover Berechnung**
*Warum:* Die Schwellwerte (IC > 0.02, IC-IR > 0.5) sind in der Summary erwähnt,
aber die Alphalens-spezifischen Parameter (quantiles=5, periods=(1,5,10,21)) müssen
korrekt gesetzt sein für Karte 06.

**#6 — WICHTIG: Pik Ch2 — Research Lifecycle Diagramm + Lookahead-Bias Checkliste**
*Warum:* Die 8-Item Anti-Lookahead-Checkliste aus Anhang B ist vollständig in der Summary,
aber das Research-Prozess-Diagramm (Hypothese → Research → Backtest → ... → Paper → Live)
fehlt als visuelles Artefakt. Grundlage für PIT-Enforcement.

**#7 — NÜTZLICH: Pik Ch6 Ex3 — Reversion vs. Trending Klassifikationsmodell**
*Warum:* Das neuronale Netz (4 Inputs, 8 Hidden Neurons) für die Regime-Klassifikation
braucht genaue Architektur-Details. Die Features (RSI21, ATR21/SMA21, StdDev21, Fear&Greed)
sind bekannt, aber Threshold für "genugt für profitablen Betrieb" (52–55%) sollte belegt sein.

**#8 — NÜTZLICH: Pik Ch6 Ex4 — HMM SPY/TLT Rotation Lookback-Sensititivät**
*Warum:* "Verschiedene Lookback-Perioden testen (1, 2, 3, 4 Jahre) → Sharpe sensitiv!"
Die genaue Sensitivitätstabelle fehlt in der Summary. Sie würde direkt das optimale
Lookback-Fenster für Karte 05 informieren.

---

## 6. Sicherheitsregeln

**REGEL 1 — No Lookahead (absolut)**
- Jedes Signal darf ausschließlich auf Daten basieren, die zum Zeitpunkt `signal_time - 1 Bar` verfügbar waren.
- `validate_pit_compliance()` wird als Pre-Commit-Hook und als tägliche Invariantenprüfung ausgeführt.
- Violation = sofortiger Stop der Simulation.

**REGEL 2 — No Live Trading (absolut)**
- Das System hat keine Broker-Anbindung, keine echten Order-IDs, keine echte Kapital-Verbindung.
- Alle Order-Objekte sind Paper-Orders im internen Ledger.
- IB-API (aus Strimpel) wird ausschließlich für Paper-Trading-Modus (Port 7497) genutzt, nie für Produktion.

**REGEL 3 — Costs/Slippage immer inklusive**
- Alle Performance-Metriken werden ausschließlich netto (nach Kosten) berechnet und berichtet.
- Gross-Sharpe ohne Kostenabzug darf intern für Debugging genutzt werden, aber nie als Entscheidungsgrundlage.
- Slippage-Parameter werden alle 30 Tage kalibriert.

**REGEL 4 — Drawdown Hard-Stop**
- Drawdown > −30% triggert automatischen Position-Reduction (auf 50%) und Discord-Alert.
- Drawdown > −50% triggert vollständige Paper-Portfolio-Pause und manuelle Review-Anforderung.
- Recovery-Filter: Kein Wiedereinstieg innerhalb von 5 Handelstagen nach neuem Tief.

**REGEL 5 — Margin-of-Safety Promotion Gate**
- Keine Strategie wird in den aktiven Paper-Ledger aufgenommen ohne:
  - OOS-Sharpe > 0.5 bei 2× Slippage
  - p-Wert < 0.05 (IS vs OOS t-Test)
  - Max-Drawdown > −30%
  - Mindestens 60 OOS-Handelstage Validierungshistorie

**REGEL 6 — Keine Finanzberatung**
- Alle Ergebnisse, Reports und Alerts sind ausschließlich für Research-Zwecke.
- Kein Discord-Report enthält Handlungsempfehlungen für echtes Kapital.
- Jeder Report trägt den Disclaimer: "Paper Trading only — No real capital — Not financial advice."

---

## 7. Offene Fragen (max 5)

**F1 — Krypto vs. Aktien: Gemeinsamer oder getrennter Ledger?**
Die aktuelle Architektur geht von einem universellen Ledger aus. Krypto (24/7, keine
Corporate Actions, Funding Rates) und Aktien (Splits, Dividenden, Handelszeiten) haben
fundamental unterschiedliche Datenstrukturen. Ist ein gemeinsamer VirtualAccount mit
Asset-Class-Flags ausreichend, oder werden zwei getrennte Ledger-Instanzen benötigt?

**F2 — Welches Regime-Lookback ist optimal für BTC/ETH?**
Die Pik-Summary empfiehlt 3 Jahre für SPY/TLT. BTC hat erst seit 2017 ausreichende
Handelshistorie und geht durch deutlich extremere Regime-Shifts. Ist 1 Jahr Lookback
für Crypto realistischer? Diese Frage kann nur durch Karte 04 (Walk-Forward) empirisch
beantwortet werden — aber die Priorität muss vor dem Build entschieden werden.

**F3 — Wie wird Survival-Bias bei Krypto-Universe behandelt?**
Isichenko warnt explizit vor Survival-Bias. Delisted Coins (Terra/LUNA, FTX-Token etc.)
müssen im Backtest-Universe enthalten sein. Welche Datenquelle liefert delisted Krypto-OHLCV
historisch? yfinance und ccxt haben hier bekannte Lücken.

**F4 — Discord als einziges Reporting-Backend, oder zusätzlich lokales Dashboard?**
Strimpel beschreibt ein Plotly-Dash-Dashboard (Karte 09). Discord-Webhook ist einfacher
und sofort nutzbar, Dash ist mächtiger für interaktive Analyse. Für Phase 1 reicht Discord —
aber wann wird Dash relevant? Sollte Dash bereits in Phase 1 als Grundstruktur angelegt werden?

**F5 — Welches Kalibrierungsprotokoll für Regime-Modell nach schlechten Walk-Forward-Ergebnissen?**
Wenn der Walk-Forward-Harness (Karte 04) für eine Strategie p > 0.05 liefert: Darf das
Regime-Modell neu kalibriert werden (neue Lookback-Periode) oder gilt dies als Overfitting?
Die Overfitting-Hierarchie aus Isichenko (Signale zuerst festlegen, Risk-Parameter periodisch
kalibrieren) gibt eine Richtung, aber die Grenze zwischen legitimem Kalibrieren und Overfitting
ist für das Regime-Modell nicht explizit definiert.

---

*Plan erstellt: 2026-05-26*
*Quellen: Isichenko (QPM), Strimpel (Python Algo Cookbook), Pik et al. (Hands-On AI Trading), Ultraplan*
*Scope: Phase 1 — Research/Paper Trading only — Keine echten Orders — Keine Finanzberatung*
