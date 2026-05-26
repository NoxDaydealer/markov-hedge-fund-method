Ich habe alle relevanten Dateien gelesen. Jetzt schreibe ich den vollständigen Ultraplan.

---

# Ultraplan: Strategy-Combination Evaluation Roadmap

**Repo:** `/root/trading/markov-strategy` | **Datum:** 2026-05-25 | **Bezug:** Kanban-Task t_9136788d

---

## 1. Executive Summary

Das Repo hat vier funktionsfähige Strategie-Adapter, eine vollständige Walk-Forward/Baselines/Kosten-Evaluierungs-Engine und einen Markov-Regime-Gate — aber **keinen Verbindungsschicht**, die diese Komponenten systematisch kombiniert und vergleichbar macht. Der nächste Sprint schließt diese Lücke: ein `StrategyCombinationRunner`, eine generische `ParameterSweep`-Infrastruktur und ein `RegimeGatedCombo`-Signal. Alles bleibt paper/research-only. Keine Renditeversprechen, kein Broker.

---

## 2. Was der Graph/Repo-Zustand nahelegt

| Befund | Implikation |
|---|---|
| `ComboFibLiquidityAdapter` = God Node (23 Kanten) | Das tägliche Fib-Liquidity-Adapter dominiert strukturell, obwohl es nachweislich nur 1 Trade/5 Jahre auf QQQ liefert. Risiko: Sweep-Ressourcen verschwenden. |
| Communities 20–25 enthalten identische Metrik-Schemata | `hft_evaluator.compute_hft_metrics` wird gut wiederverwendet. Aber `backtest_report.py` hat eine *separate* `_compute_metrics`-Funktion mit anderem Schema — das ist eine stille Inkonsistenz. |
| 174 isolierte Knoten (darunter `z_threshold`, `interval`, `period`) | Parameter-Nodes haben keine Verbindung zu ihren Adaptern im Graph → kein systematischer Sweep existiert, Parameter leben in CLI-Defaults vergraben. |
| Community 16 (IntradayMarkovGate, Kohäsion 0.20) | Gate gut gekapselt. `_orderbook_imbalance_regime()` hat bereits einen Fallback-Pfad für L2-Features — Integration ist vorbereitet aber nicht verknüpft. |
| Community 8 (HFT-Evaluator-Tests, Kohäsion 0.12) | Evaluator-Tests gut abgedeckt. Kein Test für Kombinations-Runner oder Vergleichsreport vorhanden. |
| `backtest_report.py` importiert nur `BollingerVwapMomentumAdapter` + `ComboFibLiquidityAdapter` | `VWAPVolumeRSIReversionAdapter` hat keinen Einstiegspunkt im Haupt-CLI. Kein Adapter ruft `hft_evaluator.walk_forward_evaluate()` aus einer einheitlichen Oberfläche. |

**Kernbefund:** Die Evaluierungs-Infrastruktur ist stark, aber jede Strategie lebt in einer Silo-CLI. Die Kombinations-Evaluierungsschicht fehlt vollständig.

---

## 3. Zielarchitektur für den Strategy Combination Evaluator

```
                ┌─────────────────────────────────────────────────────┐
                │               OHLCV-Daten (CSV / DataFrame)         │
                └────────────────────────┬────────────────────────────┘
                                         │
          ┌──────────────────────────────▼──────────────────────────────┐
          │              ParameterSweepRunner                           │
          │  (grid über Adapter-Params → Liste von Signalen + Namen)    │
          └──────────────┬───────────────────────────────┬──────────────┘
                         │                               │
          ┌──────────────▼──────────┐     ┌─────────────▼──────────────┐
          │  Einzelstrategie-Signal │     │  RegimeGatedComboSignal     │
          │  (vwap_rsi / bollinger  │     │  (IntradayMarkovRegimeGate  │
          │   / combo_fib)          │     │   → wählt Adapter per Bar)  │
          └──────────────┬──────────┘     └─────────────┬──────────────┘
                         │                               │
          ┌──────────────▼───────────────────────────────▼──────────────┐
          │                  hft_evaluator                               │
          │  evaluate_intraday_strategy() / walk_forward_evaluate()      │
          │  + evaluate_with_baselines()                                 │
          └──────────────────────────────┬──────────────────────────────┘
                                         │
          ┌──────────────────────────────▼──────────────────────────────┐
          │               ComboComparisonReport                         │
          │  (CSV + MD: alle Strategien + Combos + Baselines in einer   │
          │   Tabelle. go_no_go Gate: pass / fail)                      │
          └─────────────────────────────────────────────────────────────┘
```

**Invarianten der Architektur:**
- Alle Signale sind per-Bar (`pd.Series`, Index = OHLCV-Index, Werte -1/0/+1)
- Keine Strategie kennt die Evaluierungslogik; keine Evaluierung kennt Strategie-Interna
- Alle Ausgaben sind deterministisch (kein `time.time()`, kein Random ohne Seed)
- `hft_evaluator` bleibt die einzige Metrik-Quelle (keine zweite `_compute_metrics`)

---

## 4. Daten- und Schnittstellenvertrag

### 4.1 Pflicht-Eingabe (alle Strategien)

```python
# OHLCV DataFrame
# Index: pd.DatetimeIndex, monoton steigend
# Spalten: open, high, low, close, volume (float64)
# Optionale Spalten für L2-Anreicherung:
#   orderbook_imbalance (float, -1..+1)
#   bid_size, ask_size (float)
#   spread (float, abs. Wert)
```

### 4.2 Signal-Konvention (bestehend, unveränderlich)

```python
# pd.Series, selber Index wie OHLCV
# +1 = Long-Execution auf nächstem Bar-Open
#  0 = kein Trade
# -1 = Short (nur wenn enable_shorts=True)
# Shift um 1 Bar zur Execution bereits im Adapter implementiert (kein Lookahead)
```

### 4.3 Kosten-Standard (konservativ, aus hft_evaluator.CostModel)

```python
CostModel(
    taker_fee_bps=5.5,   # Bybit Taker
    spread_bps=1.0,
    slippage_bps=2.0,
    order_type='taker',
)
# Round-trip = 2 * (5.5 + 1.0 + 2.0) / 10000 = 0.17 %
```

### 4.4 Walk-Forward Standard

```python
WalkForwardConfig(
    train_bars=30 * 1440,       # 30 Tage × 1min = 43200 Bars
    validation_bars=7 * 1440,   # 7 Tage = 10080 Bars
    test_bars=7 * 1440,
    step_bars=7 * 1440,
)
# Minimum-Folds bei 6 Monaten Daten: ~3 Folds
```

### 4.5 Output-Schema (unified, neu)

```
sweep_results.csv:
  strategy_name, combo_type, param_*, 
  net_pnl, gross_pnl, max_drawdown, sharpe,
  trades, win_rate, ev_per_trade, trades_per_day,
  fee_to_gross_profit, profit_factor,
  pnl_bull, pnl_bear, pnl_sideways,
  beats_random, beats_buy_hold, beats_naive_vwap,
  fold (int, None wenn kein walk-forward)
```

---

## 5. Implementierungs-Karten (Kanban-Karten)

---

### KARTE 01 — `StrategyCombinationRunner`

**Titel:** Kombinations-Runner: Regime-getriebene Signal-Selektion pro Bar

**Ziel:** Eine reine Funktion, die einen `regime_gate_output`-DataFrame (aus `IntradayMarkovRegimeGate.generate()`) und ein Dict von Strategie-Signalen nimmt, pro Bar das passende Signal auswählt und ein kombiniertes Signal (`pd.Series`) zurückgibt.

**Neue Datei:** `trading_hub/combination_runner.py`

**Schnittstelle:**
```python
def build_regime_gated_signal(
    regime_gate: pd.DataFrame,      # aus IntradayMarkovRegimeGate.generate()
    signals: dict[str, pd.Series],  # {'mean_reversion': ..., 'momentum': ...}
    *,
    regime_to_strategy: dict[str, str],  # {'mean_reversion': 'mean_reversion', 'momentum': 'momentum'}
    flat_default: int = 0,           # was tun wenn Regime='flat'
) -> pd.Series:
```

**Konflikte:** Wenn zwei Regime-Bedingungen auf denselben Bar zutreffen würden (edge case), nimmt die Reihenfolge in `regime_to_strategy` Priorität.

**Tests:** `tests/test_combination_runner.py`
- Zwei Signale auf nicht-überlappenden Bars → keine Überlagerung im Output
- Regime=flat → Signal=0 (no trade)
- Regime wechselt mid-series → Signal-Sequenz korrekt
- Output Index identisch mit OHLCV-Index

**Akzeptanzkriterien:**
- Max. 1 Signal pro Bar (keine Überlagerung)
- `pd.Series` mit Werten in {-1, 0, 1}
- Keine Exception bei leeren oder constant-0 Eingaben

**Risiken:** Markov-Gate produziert `'flat'` als Default bei untrainierten Bars — darf nicht als echter Regime-State behandelt werden. → Sicherstellen dass `flat_default=0` gilt.

**Schätzung:** 2–3 Stunden

---

### KARTE 02 — Generische Parameter-Sweep-Infrastruktur

**Titel:** `run_param_sweep()`: Grid-Sweep über beliebige Adapter-Parameter

**Ziel:** Eine Funktion, die ein Parameter-Grid (Dict von Listen) expandiert, für jede Kombination die Signal-Factory aufruft und Metriken in einem DataFrame sammelt. Hängt von keiner spezifischen Strategie ab.

**Neue Datei:** `trading_hub/parameter_sweep.py`

**Schnittstelle:**
```python
def run_param_sweep(
    ohlcv: pd.DataFrame,
    signal_factory: Callable[[dict[str, Any]], pd.Series],
    param_grid: dict[str, list[Any]],
    *,
    cost_model: CostModel | None = None,
    execution: ExecutionAssumptions | None = None,
    constraints: TradeConstraints | None = None,
    regime: pd.Series | None = None,
    periods_per_year: int = 365 * 24 * 60,
    name_prefix: str = 'sweep',
) -> pd.DataFrame:
```

**Tests:** `tests/test_parameter_sweep.py`
- 2×2 Grid → 4 Ergebniszeilen
- Alle Metriken aus `compute_hft_metrics` vorhanden
- Param-Spalten mit Präfix `param_` vorhanden
- `signal_factory` erhält dict, nicht kwargs (testbar durch Mock)

**Akzeptanzkriterien:**
- Jede Zeile entspricht genau einer Param-Kombination
- Metrik-Spalten-Schema identisch mit `EvaluationResult.metrics`
- Kein Silence bei leerer Signal-Serie (0 Trades → Metriken trotzdem ausgegeben)
- Deterministisch (gleiche Inputs → gleiche Outputs)

**Risiken:** Bei großem Grid (>1000 Kombinationen) kann Laufzeit hoch sein — keine Parallelisierung im ersten Schritt. Sweep-Größe durch `max_combinations`-Guard begrenzen (default: 500).

**Schätzung:** 3–4 Stunden

---

### KARTE 03 — VWAP/Volume/RSI Reversion Parameter-Sweep

**Titel:** Sweep: VWAP RSI Reversion (Bybit 1m, Markov-Gate-Modi)

**Ziel:** Ersten systematischen Sweep über die Haupt-Parameter von `VWAPVolumeRSIReversionAdapter` ausführen und Ergebnisse als CSV ablegen.

**Parameter-Grid (konservativ, 3×3×2×3 = 54 Kombinationen):**
```python
{
    'markov_gate': ['off', 'neutral_only', 'contrarian_ok'],
    'z_threshold': [1.0, 1.5, 2.0],
    'rsi_long': [25.0, 30.0, 35.0],
    'volume_multiple': [1.5, 2.0],
}
```

**Neue Datei:** `trading_hub/sweeps/vwap_rsi_reversion_sweep.py`

**Schnittstelle:**
```python
def run_vwap_rsi_reversion_sweep(
    ohlcv: pd.DataFrame,
    *,
    cost_model: CostModel | None = None,
    output_csv: Path | None = None,
) -> pd.DataFrame:
```

**Tests:** `tests/test_vwap_rsi_reversion_sweep.py`
- Smoke-Test: 2×2-Unter-Grid → korrekte Anzahl Zeilen
- `markov_gate='off'` ist immer in den Ergebnissen
- Output-CSV wird nur geschrieben wenn `output_csv` angegeben

**Akzeptanzkriterien:**
- `research/reports/sweep_vwap_rsi_reversion.csv` entsteht bei CLI-Aufruf
- Enthält `param_markov_gate`, alle Standard-Metriken
- Bester Param-Set nach `net_pnl` nur auf Train-Daten selektiert (kein Test-Lookahead)

**Risiken:** `markov_lookback`/`markov_min_train` fest auf Defaults gelassen — sonst explodiert der Suchraum.

**Schätzung:** 2–3 Stunden

---

### KARTE 04 — Bollinger VWAP Momentum Parameter-Sweep

**Titel:** Sweep: Bollinger/VWAP Momentum (Squeeze-Threshold, Volume-Multiplikator)

**Ziel:** Systematischer Sweep über die squeeze- und momentum-kritischen Parameter von `BollingerVwapMomentumAdapter`.

**Parameter-Grid (2×3×2×2 = 24 Kombinationen):**
```python
{
    'bb_period': [20, 30],
    'bandwidth_percentile_threshold': [0.15, 0.20, 0.25],
    'volume_multiplier': [1.5, 2.0],
    'enable_shorts': [False, True],
}
```

**Neue Datei:** `trading_hub/sweeps/bollinger_vwap_momentum_sweep.py`

**Tests:** Analog zu Karte 03 (Smoke-Test 2×2, CSV-Output)

**Akzeptanzkriterien:**
- Gleiche CSV-Schema wie Karte 03
- `enable_shorts=False` Varianten sind immer dabei
- `backtest_report.py`'s eigene `_compute_metrics` wird **nicht** verwendet — nur `hft_evaluator`

**Risiken:** `BollingerVwapMomentumAdapter` verwendet einen anderen Backtest-Loop in `backtest_report.py` (ATR-Trailing während Trade). Für den Sweep wird der einfachere `hft_evaluator`-Loop benutzt (open-to-next-open). Die Resultate sind daher nicht direkt mit `backtest_report.py`-Zahlen vergleichbar. Dieses Delta explizit in den CSV-Metadaten vermerken.

**Schätzung:** 2 Stunden

---

### KARTE 05 — Combo Fib Liquidity Sweep (niedrige Priorität)

**Titel:** Sweep: combo_fib_liquidity — Verifikation der Irrelevanz für Intraday

**Ziel:** Dokumentieren, ob `ComboFibLiquidityAdapter` bei irgendeinem Parameter-Set auf Intraday-Daten einen Edge hat (Erwartung: nein — bestätigt die Entscheidung aus dem Hermes-Plan).

**Parameter-Grid (3×3×3 = 27 Kombinationen):**
```python
{
    'lookback': [15, 20, 30],
    'atr_stop_multiple': [0.75, 1.0, 1.5],
    'atr_take_profit_multiple': [1.5, 2.0, 3.0],
}
```

**Neue Datei:** `trading_hub/sweeps/combo_fib_liquidity_sweep.py`

**Akzeptanzkriterien:**
- Ergebnis-CSV enthält Trades > 0 für mindestens einige Kombinationen
- Wenn net_pnl < 0 für alle Kombinationen → explizites "no_edge"-Flag in Ergebnisdatei
- Keine Weiterentwicklung dieser Strategie wenn Go/No-Go-Gate nicht bestanden

**Risiken:** `ComboFibLiquidityAdapter` braucht mindestens `lookback + atr_period` Bars Warm-up — bei Intraday 1m kann das kurz sein. Keine Gefahr.

**Schätzung:** 1.5 Stunden

---

### KARTE 06 — Regime-Gated Combo: Einheitliches Kombinations-Signal

**Titel:** RegimeGatedCombo: Markov wählt per Bar zwischen Reversion und Momentum

**Ziel:** Das eigentliche Kombinations-Hypothesis-Signal: VWAP RSI Reversion wenn Regime=mean_reversion, Bollinger Momentum wenn Regime=momentum, kein Trade wenn flat oder high_spread.

**Neue Datei:** `trading_hub/combo_signal.py`

**Schnittstelle:**
```python
@dataclass(frozen=True)
class RegimeGatedComboConfig:
    mean_reversion_regime: str = 'mean_reversion'
    momentum_regime: str = 'momentum'
    blocked_when_high_spread: bool = True

def build_regime_gated_combo_signal(
    gate_output: pd.DataFrame,        # aus IntradayMarkovRegimeGate.generate()
    reversion_signal: pd.Series,      # aus VWAPVolumeRSIReversionAdapter
    momentum_signal: pd.Series,       # aus BollingerVwapMomentumAdapter
    config: RegimeGatedComboConfig | None = None,
) -> pd.Series:
```

**Tests:** `tests/test_combo_signal.py`
- Regime=mean_reversion → reversion_signal übernommen
- Regime=momentum → momentum_signal übernommen
- Regime=flat → Signal=0
- high_spread_blocked → Signal=0, unabhängig von Regime
- Kein Lookahead: Signal aus Bar t → Execution in Bar t+1 (beide Adapter shiften bereits um 1)
- Signalkollision (beide Adapter gleiche Bar, verschiedene Seiten) → tie-breaking: reversion gewinnt (konfigurierbar)

**Akzeptanzkriterien:**
- `pd.Series` {-1, 0, +1}, gleicher Index wie OHLCV
- Kein Signal-Overlap (max. 1 Signal pro Bar)
- `trade_allowed=False` in gate_output → Signal=0

**Schätzung:** 2–3 Stunden

---

### KARTE 07 — Unified Comparison Report

**Titel:** `combo_comparison_report.py`: Alle Strategien + Kombinationen in einem Report

**Ziel:** Einen einzigen Einstiegspunkt (CLI + Python-API), der alle Strategie-Varianten auf demselben OHLCV-Datensatz evaluiert und eine vergleichbare Tabelle produziert.

**Evaluierungsmatrix:**
```
1. VWAPVolumeReversionAdapter (baseline, markov=off)
2. VWAPVolumeRSIReversionAdapter (markov=neutral_only)
3. VWAPVolumeRSIReversionAdapter (markov=contrarian_ok)
4. BollingerVwapMomentumAdapter (shorts=off)
5. BollingerVwapMomentumAdapter (shorts=on)
6. ComboFibLiquidityAdapter (daily, zur Referenz)
7. RegimeGatedCombo (markov selects 1 vs 4)
8. Baselines: no_trade, buy_hold, random_same_freq, naive_vwap
```

**Neue Datei:** `trading_hub/combo_comparison_report.py`

**Output:**
- `research/reports/combo_comparison_<YYYY-MM-DD>.csv` (maschinenlesbar)
- `research/reports/combo_comparison_<YYYY-MM-DD>.md` (menschenlesbar, Markdown-Tabelle)

**Tests:** `tests/test_combo_comparison_report.py`
- Mindestens 7 Strategien + 4 Baselines im Output
- Alle Pflicht-Metriken vorhanden (net_pnl, max_drawdown, fee_to_gross_profit, trades, beats_random)
- CLI: `--csv data.csv` → Output in `research/reports/`
- MD-Report enthält Go/No-Go-Spalte (aus Karte 10)

**Akzeptanzkriterien:**
- Ein einziger CLI-Befehl führt alle 11 Evaluierungen durch
- Kein Netzwerkaufruf (alles lokal)
- CSV kann direkt in Pandas eingelesen werden

**Schätzung:** 3–4 Stunden

---

### KARTE 08 — L2 Feature Bridge (optional, nach Datenbasis)

**Titel:** L2-Feature-Bridge: Orderbook-Imbalance als optionaler Markov-Input

**Ziel:** `bybit_l2_feature_prototype.py` generiert bereits Imbalance-Metriken. Diese sollen als optionale Spalte in den OHLCV-Frame reinjiziert werden, damit `IntradayMarkovRegimeGate._orderbook_imbalance_regime()` (bereits implementiert, aber nur aktiviert wenn Spalte vorhanden) echte Werte liefert.

**Neue Datei:** `trading_hub/l2_feature_bridge.py`

**Schnittstelle:**
```python
def enrich_ohlcv_with_l2(
    ohlcv: pd.DataFrame,
    l2_features: pd.DataFrame,    # aus bybit_l2_feature_prototype features.csv
    *,
    imbalance_col: str = 'imbalance_notional_top5',
    resample_rule: str | None = '1min',
) -> pd.DataFrame:
```

**Tests:** `tests/test_l2_feature_bridge.py`
- Enriched Frame hat neue Spalte `orderbook_imbalance`
- Zeitstempel-Alignment: L2-Snapshots (1s) korrekt auf 1min OHLCV gemappt (ffill oder mean)
- Wenn L2-Daten außerhalb OHLCV-Range: Spalte enthält NaN (kein Crash)
- `IntradayMarkovRegimeGate` mit enriched Frame: kein 'unknown' mehr für ob_regime

**Akzeptanzkriterien:**
- Bridge ist optional: OHLCV ohne L2 funktioniert unverändert
- Fallback-Verhalten von `_orderbook_imbalance_regime()` bleibt erhalten
- Kein REST-Call in Bridge (nur lokale CSV)

**Voraussetzung:** Erst ausführen wenn `research/bybit_l2_feature_prototype/features.csv` vorliegt (mind. 1h Daten).

**Schätzung:** 2–3 Stunden

---

### KARTE 09 — Walk-Forward Run (alle Kombinationen)

**Titel:** Walk-Forward Evaluation: Train/Val/Test-Folds für alle Strategien

**Ziel:** `walk_forward_evaluate()` für alle Strategien aus Karte 07 auf einem ausreichend langen Datensatz ausführen und Fold-Ergebnisse ablegen.

**Dateien:**
- `trading_hub/walk_forward_runner.py` (neu, schlanker Wrapper)
- Outputs in `research/reports/wf_<strategy>_<date>.csv`

**Walk-Forward Config (Standard):**
```python
WalkForwardConfig(
    train_bars=30 * 1440,
    validation_bars=7 * 1440,
    test_bars=7 * 1440,
    step_bars=7 * 1440,
)
```

**Tests:** `tests/test_walk_forward_runner.py`
- Mindestens 3 Folds wenn Daten ≥ 44 Tage
- Fold-Struktur: train/val/test-Zeiten überlappen sich nicht
- Output-CSV enthält `fold`, `split` (train/val/test), alle Metriken

**Akzeptanzkriterien:**
- Kein Train-auf-Test-Lookahead (durch bestehende `walk_forward_evaluate()` Garantie)
- Ergebnis-CSV: eine Zeile pro Fold × Split × Strategie
- Logging wenn Test-Net-PnL < Val-Net-PnL (mögliches Overfitting-Signal)

**Schätzung:** 3 Stunden

---

### KARTE 10 — Go/No-Go Gate

**Titel:** `go_no_go.py`: Entscheidungsfilter nach hft_evaluation_framework.md

**Ziel:** Eine Funktion, die `WalkForwardFold`-Liste oder einzelnen `EvaluationResult` prüft und ein strukturiertes Go/No-Go-Urteil mit Begründung liefert.

**Kriterien (aus `research/hft_evaluation_framework.md`):**

```python
@dataclass(frozen=True)
class GoNoGoResult:
    verdict: Literal['go', 'no_go', 'insufficient_data']
    reasons_failed: list[str]  # leer bei 'go'
    metrics_summary: dict[str, float]

def evaluate_go_no_go(
    folds: list[WalkForwardFold],
    *,
    min_trades_per_fold: int = 20,
    max_drawdown_threshold: float = -0.30,
    fee_to_gross_profit_max: float = 0.50,
    min_fraction_folds_beat_random: float = 0.60,
) -> GoNoGoResult:
```

**Tests:** `tests/test_go_no_go.py`
- Strategie mit net_pnl > 0 auf allen Test-Folds und > 20 Trades → 'go'
- Strategie mit 0 Gebühren und edge nur bei fee=0 → 'no_go' (fee_to_gross_profit > threshold)
- < 20 Trades pro Fold → 'insufficient_data'
- Drawdown < -0.30 → 'no_go'
- < 60% Folds beat random → 'no_go'

**Akzeptanzkriterien:**
- Alle Kriterien aus `hft_evaluation_framework.md` abgedeckt
- `reasons_failed` enthält lesbare Strings (kein Exception-Stacktrace)
- Integration in Karte 07 Report: Go/No-Go-Spalte im MD-Output

**Schätzung:** 2 Stunden

---

## 6. Priorität und Implementierungsreihenfolge

```
Welle 1 (Fundament):
  KARTE 01 — CombinationRunner          [~2h]
  KARTE 02 — ParameterSweep Infrastruktur [~3h]

Welle 2 (Kern-Sweeps):
  KARTE 03 — VWAP RSI Reversion Sweep   [~2h]  ← höchste Alpha-Hypothese
  KARTE 04 — Bollinger Momentum Sweep   [~2h]

Welle 3 (Kombinations-Evaluation):
  KARTE 06 — RegimeGatedCombo Signal    [~2h]  ← Kernhypothese des Plans
  KARTE 07 — Unified Comparison Report  [~3h]
  KARTE 10 — Go/No-Go Gate              [~2h]

Welle 4 (Robustheit):
  KARTE 09 — Walk-Forward Runner        [~3h]

Welle 5 (Optional/Nach Datenbasis):
  KARTE 05 — Combo Fib Sweep            [~1.5h] ← niedriger Nutzen erwartet
  KARTE 08 — L2 Feature Bridge          [~2h]   ← erst wenn features.csv vorliegt
```

**Gesamtschätzung Wellen 1–4:** ~21 Stunden Entwicklungszeit (reine Code + Tests, exkl. Laufzeit der Sweeps).

---

## 7. Was NICHT getan werden soll

1. **Keine Broker-Integration, keine echten Orders.** Auch kein "simuliertes Paper-Trading" mit Echtzeit-Daten-Feed.
2. **Kein Umschreiben bestehender Adapter** — `VWAPVolumeReversionAdapter`, `BollingerVwapMomentumAdapter`, `ComboFibLiquidityAdapter` und `IntradayMarkovRegimeGate` bleiben unverändert. Nur additive Schicht.
3. **Keine neue ML/DL-Strategie** in diesem Sprint. Erst bestehendes evaluieren.
4. **Keine Portfoliooptimierung** (Markowitz, Kelly-Sizing) — zu viel Scope, ohne nachgewiesenen Edge sinnlos.
5. **Kein Zusammenführen der duplizierten `_load_ohlcv`- und `_compute_metrics`-Funktionen** als Teil dieses Sprints (Refactoring-Task für danach).
6. **Kein Frequenz-Upgrade auf Sub-1min** ohne L2-Websocket-Datenbasis und Queue/Latenz-Modell.
7. **Kein Entfernen oder Deprecating von `backtest_report.py`** — bleibt als Referenz; Sweep-Karten nutzen `hft_evaluator` und dokumentieren die Divergenz explizit.
8. **Keine Funding-Rate-, OI- oder Sentiment-Features** in diesem Sprint.
9. **Keine Renditeversprechen, keine "erwartete Alpha"-Aussagen** im Code oder in Report-Texten.

---

## 8. Offene Fragen an Anton (max. 5)

1. **Daten-Asset und Zeitraum:** Welches Asset und welchen Zeitraum soll der erste Sweep verwenden — `BTCUSDT` 1m (aus Bybit-Collector, letzter verfügbarer Zeitraum) oder `QQQ`/`NQ=F` Intraday-CSV? Das bestimmt die Warm-up-Bar-Zahl und die sinnvolle Walk-Forward-Fenstergröße.

2. **Sweep-Budget:** Soll ein `max_combinations`-Limit gelten (z.B. 500) um Laufzeit zu begrenzen, oder darf ein vollständiges Grid (möglicherweise 1000+ Kombinationen bei Welle 2 + 3 + Combo) unkontrolliert laufen? (Hinweis: 1000 Kombinationen × 1h 1m-Daten ≈ 5–15 min auf einem CPU-Core.)

3. **`combo_fib_liquidity` — weiter oder deprecaten?** Der Graph zeigt es als God Node, der Hermes-Plan hat es de facto durch Intraday-Strategien ersetzt. Soll Karte 05 (Fib-Sweep) die Entscheidung dokumentieren und danach die Strategie aus Haupt-Evaluierungen ausgenommen werden?

4. **L2-Daten-Basis:** Liegt bereits eine `features.csv` aus dem Bybit L2 Prototype vor, oder muss Karte 08 auf eine Datensammelphase warten? Falls ja — soll der Collector parallel im Hintergrund laufen während die OHLCV-Sweeps laufen?

5. **Report-Ausgabepfad und Format:** `research/reports/` als Output-Verzeichnis — OK so? Und: Soll der Comparison Report in Karte 07 zusätzlich als Hermes-Kanban-Update strukturiert werden oder reicht CSV + MD?

---

*Dieser Plan ist konservativ und baut ausschließlich auf bestehendem Code auf. Er enthält keine Renditeversprechen. Alle Backtests sind paper/research-only.*
