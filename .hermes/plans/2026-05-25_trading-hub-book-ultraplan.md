# Trading Hub Book Ultraplan — Implementation Roadmap
*Generated: 2026-05-25 | Research/paper-trading only | No real-money execution*

---

## Goal and Non-Goals

**Goal:** Translate the six-book ultraplan into a sequenced, card-by-card implementation roadmap for Trading Hub as a research and paper-trading system.

**Non-Goals:**
- No broker API integration or live order execution
- No real-money position management
- No full-chapter ML model engineering before evaluation infrastructure exists
- No Elliott Wave or RL implementation until simpler layers are validated

---

## Source Files Read

- `/root/trading/TradingHub_Books/00_trading_hub_books_ultraplan.md` — primary source generated from all book notes
- `/root/trading/TradingHub_Books/01_quantitative_portfolio_management_isichenko/notes.md` and `trading_hub_ideen.md`
- `/root/trading/TradingHub_Books/02_python_for_algorithmic_trading_cookbook_strimpel/notes.md` and `trading_hub_ideen.md`
- `/root/trading/TradingHub_Books/03_hands_on_ai_trading_python_quantconnect_aws/notes.md` and `trading_hub_ideen.md`
- `/root/trading/TradingHub_Books/04_technische_analyse_der_finanzmaerkte_murphy/notes.md` and `trading_hub_ideen.md`
- `/root/trading/TradingHub_Books/05_professioneller_boersenhandel_erdal_cene/notes.md` and `trading_hub_ideen.md`
- `/root/trading/TradingHub_Books/06_intelligent_investieren_graham/notes.md` and `trading_hub_ideen.md`

**Book Abbreviations Used Below:**

| Abbrev | Book |
|--------|------|
| `ISI` | Isichenko — Quantitative Portfolio Management |
| `STR` | Strimpel — Python Algo Trading Cookbook |
| `PIK` | Pik et al. — Hands-On AI Trading |
| `MUR` | Murphy — Technische Analyse der Finanzmärkte |
| `CEN` | Cene — Professioneller Börsenhandel |
| `GRA` | Graham — Intelligent Investieren |

---

## Phase A — Safety / Evaluation Foundation

*Must be completed before any strategy evaluation loop is run. These cards establish the conceptual and code boundaries that prevent results from being meaningless.*

---

### A-01 — Simulation-vs-Production Checklist

**Source:** ISI Ch7 §7.1–7.2, §7.4 (T1-01)

**Expected files/modules:**
- `trading_hub/evaluation/sim_checklist.py` — structured checklist dataclass + CLI runner
- `trading_hub/evaluation/paper_ledger.py` — paper trade log schema

**Tests/verification:**
- Unit: checklist raises on missing required fields
- Integration: paper ledger records a simulated fill and is readable via standard report
- Gate: checklist must pass before any strategy enters walk-forward phase

**Risks:** Confusion between backtest PnL and paper PnL if ledger schema is shared.

**Priority:** P0
**Depends on:** nothing

---

### A-02 — Lookahead / Timestamp Audit

**Source:** PIK Ch2 (T1-07), ISI Ch2 (T2-01)

**Expected files/modules:**
- `trading_hub/evaluation/audit.py` — bar-close vs next-open timing assertions
- `tests/test_lookahead.py` — parametrized tests for known leakage patterns

**Tests/verification:**
- Unit: assert signal computed at bar-close is not accessible before bar-close
- Property test: shuffle timestamps and confirm no future bar bleed
- CI gate: runs on every strategy module import

**Risks:** Subtle leakage from reindex fills or `.ffill()` across bar boundaries.

**Priority:** P0
**Depends on:** A-01

---

### A-03 — Strategy Lifecycle Status Labels

**Source:** GRA Ch1 (T2-16), PIK Ch2 (T1-07)

**Expected files/modules:**
- `trading_hub/evaluation/lifecycle.py` — enum: `RESEARCH | EXPERIMENTAL | SPECULATIVE | PAPER_TRACKED | REJECTED`
- `trading_hub/strategy/base.py` — strategy base class carries status field

**Tests/verification:**
- Unit: status transitions obey allowed graph (e.g., RESEARCH → PAPER_TRACKED requires gate pass)
- Docs: each status maps to Graham Ch1 investing/speculation taxonomy

**Risks:** Status drift if not enforced in code; teams may skip stages under time pressure.

**Priority:** P0
**Depends on:** A-01

---

### A-04 — Strategy Development Checklist (Process Gate)

**Source:** MUR App C (T1-10), CEN Ch12 §12.1–12.2 (T1-12)

**Expected files/modules:**
- `trading_hub/evaluation/strategy_checklist.md` — Markdown template (not code)
- `trading_hub/evaluation/strategy_plan.py` — dataclass: idea → objective rules → visual inspect → formal test → eval → money mgmt

**Tests/verification:**
- Manual gate: strategy plan doc must be filled before code is merged
- Linter: CI checks that `strategy_plan.py` fields are non-empty strings

**Risks:** Checklist becomes checkbox theater; enforce with PR review policy.

**Priority:** P0
**Depends on:** A-03

---

### A-05 — Margin-of-Safety Promotion Gate

**Source:** GRA Ch20 (T1-14), ISI Ch7 (T1-01)

**Expected files/modules:**
- `trading_hub/evaluation/promotion_gate.py` — compares strategy metrics vs baseline with configurable buffer
- `tests/test_promotion_gate.py`

**Tests/verification:**
- Unit: gate rejects strategy with Sharpe below `baseline + margin`
- Unit: gate rejects strategy with negative post-cost return
- Integration: gate output feeds lifecycle status transition

**Risks:** Margin threshold set too low; hardcode a conservative default (0.3 Sharpe buffer above baseline).

**Priority:** P0
**Depends on:** A-03, B-02 (costs must be applied before gate)

---

## Phase B — Data Quality + Costs / Slippage

*Ensures all data entering evaluation is clean and all returns include realistic friction. Must precede any walk-forward or signal diagnostic.*

---

### B-01 — Data Quality Gates

**Source:** STR Ch2 (T2-04), PIK Ch4 (T1-15)

**Expected files/modules:**
- `trading_hub/data/quality.py` — missing-bar detection, gap checks, resampling validator
- `tests/test_data_quality.py`

**Tests/verification:**
- Unit: detects injected NaN gaps, zero-volume bars, timestamp discontinuities
- Integration: pipeline refuses to pass data with quality score below threshold
- Fixture: reference OHLCV CSV with known defects used in tests

**Risks:** Crypto OHLCV from different exchanges has inconsistent bar alignment; test against real exchange snapshots.

**Priority:** P0
**Depends on:** nothing

---

### B-02 — Local Market Data Store

**Source:** STR Ch4 (T2-05)

**Expected files/modules:**
- `trading_hub/data/store.py` — SQLite or HDF5 read/write interface
- `trading_hub/data/schema.sql` or `schema.py`

**Tests/verification:**
- Unit: write then read returns identical DataFrame
- Integration: data quality gate (B-01) runs on load

**Risks:** HDF5 can corrupt on unclean close; prefer SQLite for simplicity unless performance dictates otherwise.

**Priority:** P1
**Depends on:** B-01

---

### B-03 — Cost / Slippage Sensitivity Report

**Source:** ISI Ch5 §5.1–5.2 (T1-02), PIK Ch6 ex12 (T2-08)

**Expected files/modules:**
- `trading_hub/evaluation/costs.py` — slippage model (linear impact + instantaneous impact), configurable spread bps
- `trading_hub/evaluation/cost_report.py` — sensitivity sweep: net Sharpe vs cost assumption
- `tests/test_costs.py`

**Tests/verification:**
- Unit: zero-cost returns ≥ cost-adjusted returns always
- Unit: doubling spread halves or more reduces net edge
- Report: must include at least 3 cost scenarios (low/mid/high) per strategy

**Risks:** Underestimating crypto slippage on illiquid pairs; default to pessimistic 10–20 bps.

**Priority:** P0
**Depends on:** B-01

---

### B-04 — Cost-Aware Parameter Ranking

**Source:** PIK Ch6 ex12 (T2-08), ISI Ch3.8 (T2-02)

**Expected files/modules:**
- `trading_hub/evaluation/ranking.py` — ranks parameter sets by net-of-cost metric (not gross)
- Feeds into walk-forward harness (C-01)

**Tests/verification:**
- Unit: high-turnover param set with higher gross return ranked below low-turnover set with same net return
- Property: ranking is stable under cost perturbation within expected range

**Risks:** Cost model from B-03 must be finalized before ranking is meaningful.

**Priority:** P1
**Depends on:** B-03, C-01

---

## Phase C — Strategy / Regime Selection + Walk-Forward

*Core research loop. Produces the signal and regime layer. Requires Phase A gates and Phase B data quality.*

---

### C-01 — Walk-Forward Evaluation Harness

**Source:** STR Ch6 (T1-04), PIK Ch4 (T1-15), ISI Ch7 (T1-01)

**Expected files/modules:**
- `trading_hub/evaluation/walk_forward.py` — expanding/rolling window WFO using VectorBT
- `trading_hub/evaluation/splits.py` — time-series split utility (no look-ahead across folds)
- `tests/test_walk_forward.py`

**Tests/verification:**
- Unit: no train data bleeds into test window
- Integration: produces per-fold metrics dict
- Gate: WFO result feeds promotion gate (A-05)

**Risks:** VectorBT version pinning; document exact version in `pyproject.toml`.

**Priority:** P0
**Depends on:** A-02, B-01, B-03

---

### C-02 — Factor / Signal Diagnostics (IC, Turnover)

**Source:** STR Ch8 (T1-06), ISI Ch3.8 (T2-02)

**Expected files/modules:**
- `trading_hub/evaluation/signal_diagnostics.py` — IC, rank-IC, factor turnover, forward-return quantile
- Integration with Alphalens optional; self-contained fallback acceptable

**Tests/verification:**
- Unit: IC of constant signal is 0
- Unit: IC of perfect signal is 1
- Property: turnover ∈ [0, 1]

**Risks:** Alphalens dependency conflicts; implement IC/turnover from scratch as fallback.

**Priority:** P1
**Depends on:** C-01

---

### C-03 — Regime-Classified Strategy Selection

**Source:** PIK Ch6 ex3 (T1-08), PIK Ch8 (T2-09)

**Expected files/modules:**
- `trading_hub/regime/classifier.py` — classifies market state (Bull/Bear/Sideways/Volatile)
- `trading_hub/regime/selector.py` — maps regime → strategy candidate list
- `tests/test_regime_selector.py`

**Tests/verification:**
- Unit: regime transitions produce deterministic strategy switch
- Integration: selector output is a ranked list, not a single strategy (avoids overconfidence)
- Regression: known historical regime periods produce expected dominant strategy

**Risks:** Regime label is retrospective; ensure forward-only regime signals in WFO context.

**Priority:** P1
**Depends on:** C-01, A-02

---

### C-04 — HMM Regime-Probability Calibration

**Source:** PIK Ch6 ex4 (T2-07), PIK Ch5 (T3-03)

**Expected files/modules:**
- `trading_hub/regime/hmm.py` — HMM state inference, outputs probability vector per bar
- Wraps `hmmlearn` or equivalent; documented dependency

**Tests/verification:**
- Unit: state probabilities sum to 1 per bar
- Integration: HMM output feeds C-03 selector as soft weight
- Validation: held-out regime periods checked against known market events

**Risks:** HMM is sensitive to initialization; test multiple seeds, document best.

**Priority:** P1
**Depends on:** C-03

---

### C-05 — Classic Oscillator Baselines (RSI, MACD, Bollinger BW)

**Source:** MUR Ch10 (T2-12), MUR Ch9 (T2-11)

**Expected files/modules:**
- `trading_hub/strategy/baselines.py` — RSI(14) 70/30, MACD(12,26,9) signal cross, Bollinger BW regime feature
- Fixed canonical parameters per Murphy rules; no optimization

**Tests/verification:**
- Unit: RSI bounded [0, 100]
- Unit: MACD histogram sign-change produces signal
- Integration: baselines used as promotion gate comparators in A-05

**Risks:** Treating these as "just indicators" and optimizing them defeats the baseline purpose.

**Priority:** P1
**Depends on:** B-01

---

### C-06 — Volume / OI Confirmation Filter

**Source:** MUR Ch7 (T2-10)

**Expected files/modules:**
- `trading_hub/strategy/filters.py` — volume spike filter, OI/funding rate filter (crypto)

**Tests/verification:**
- Unit: filter passes on volume > N-day average; rejects below
- Integration: applied as optional gate on signal output from C-03

**Risks:** Crypto funding rate as OI proxy introduces exchange-specific dependency.

**Priority:** P2
**Depends on:** B-01, C-03

---

### C-07 — Previous-Day Level Features

**Source:** CEN Ch9 §9.1–9.4 (T2-15)

**Expected files/modules:**
- `trading_hub/features/daily_levels.py` — prev high/low/close/open as float features

**Tests/verification:**
- Unit: features computed at bar-open only, using prior session close data
- Integration: lookahead audit (A-02) passes on this module

**Risks:** Timezone-aware bar alignment required; UTC normalization mandatory.

**Priority:** P2
**Depends on:** A-02, B-01

---

## Phase D — Paper Portfolio / Risk Alerts

*Paper simulation layer. Consumes signals from Phase C and enforces behavioral guardrails from Cene, Graham, and Strimpel.*

---

### D-01 — Paper Trading Guardrails

**Source:** CEN Ch2 §2.1–2.6 eleven methods (T1-11), CEN Ch13 §13.1/13.3/13.4 (T1-13)

**Expected files/modules:**
- `trading_hub/portfolio/guardrails.py` — enforces: position size cap (2.1), predefined stop/profit (2.2), R:R check (2.4), no loss-pyramiding (2.5)
- `tests/test_guardrails.py`

**Tests/verification:**
- Unit: position size cap rejects oversized fill
- Unit: loss-pyramiding rule rejects add-to-loser
- Unit: R:R below minimum threshold blocks entry
- Integration: guardrails fire before paper ledger records fill

**Risks:** Guardrails only as effective as they are enforced pre-fill; must be non-bypassable.

**Priority:** P0
**Depends on:** A-01

---

### D-02 — Trade Journal Schema

**Source:** CEN Ch2.6 (T1-11), STR Ch9 (T1-05)

**Expected files/modules:**
- `trading_hub/portfolio/journal.py` — trade record: entry/exit price, reason, regime at entry, R:R, outcome, notes
- `trading_hub/portfolio/journal_report.py` — per-trade breakdown table

**Tests/verification:**
- Unit: journal entry schema is complete (no optional fields become silent voids)
- Integration: every paper fill in ledger creates a journal entry

**Risks:** Post-hoc reasoning contamination if "reason" field filled after seeing outcome.

**Priority:** P1
**Depends on:** D-01, A-01

---

### D-03 — Volatility / Drawdown Stop Conditions

**Source:** PIK Ch6 ex8 (T1-09)

**Expected files/modules:**
- `trading_hub/portfolio/stops.py` — ATR-based stop, max drawdown recovery time cap

**Tests/verification:**
- Unit: stop triggers when price moves > N * ATR from entry
- Unit: position closed if drawdown recovery exceeds configured threshold

**Risks:** ATR lookback period should be regime-aware; document chosen default.

**Priority:** P1
**Depends on:** D-01, B-01

---

### D-04 — Position Sizing (Kelly + Inverse-Vol)

**Source:** ISI Ch6.9 (T1-03), CEN Ch2.1 (T1-11), PIK Ch6 ex11 (T2-19)

**Expected files/modules:**
- `trading_hub/portfolio/sizing.py` — fractional-Kelly (0.25 Kelly), inverse-vol allocation mode, hard leverage cap
- `tests/test_sizing.py`

**Tests/verification:**
- Unit: Kelly fraction never exceeds hard cap (e.g., 2x)
- Unit: inverse-vol weights sum to 1 across strategy pool
- Property: sizing monotonically decreases as volatility estimate rises

**Risks:** Kelly requires accurate win-rate / edge estimate; use conservative 0.25 Kelly by default.

**Priority:** P1
**Depends on:** D-01, D-03

---

### D-05 — Rolling Risk + Trade-Level Breakdown Report

**Source:** STR Ch9 (T1-05), ISI Ch4 §4.1/4.8/4.9 (T2-03)

**Expected files/modules:**
- `trading_hub/evaluation/rolling_risk.py` — rolling Sharpe, rolling max drawdown, VaR/ES per window
- `trading_hub/evaluation/trade_report.py` — per-trade metrics table
- `tests/test_rolling_risk.py`

**Tests/verification:**
- Unit: rolling Sharpe on constant returns equals annualized constant
- Integration: reports generated end-to-end from paper ledger without manual steps

**Risks:** Report complexity balloons; lock report schema to a defined set of metrics, no ad-hoc additions.

**Priority:** P1
**Depends on:** A-01, D-02, B-03

---

### D-06 — Paper Portfolio Risk Alerts

**Source:** STR Ch13 (T2-06), ISI Ch4.8 (T2-03)

**Expected files/modules:**
- `trading_hub/portfolio/alerts.py` — threshold-based alert dispatcher (Discord or log)
- Configurable thresholds: daily drawdown %, portfolio VaR breach, liquidity-risk flag

**Tests/verification:**
- Unit: alert fires when drawdown > configured threshold
- Integration: alert system operates without live broker connection
- Mock: Discord webhook mockable in tests

**Risks:** Alert fatigue; default thresholds must be conservative and documented.

**Priority:** P2
**Depends on:** D-05

---

### D-07 — Paper Review Cadence + Cooldown Rules

**Source:** GRA Ch8 (T2-17), CEN Ch2.2 (T1-11)

**Expected files/modules:**
- `trading_hub/portfolio/review.py` — scheduled review windows, cooldown enforcement (no trade within N hours of drawdown event)

**Tests/verification:**
- Unit: cooldown blocks entry after loss event
- Integration: review window generates summary diff vs prior window

**Risks:** Cooldown too aggressive = missed signals; make configurable with sensible default.

**Priority:** P2
**Depends on:** D-01, D-05

---

### D-08 — Money-Management Metrics in Paper Ledger

**Source:** MUR Ch16 (T2-13)

**Expected files/modules:**
- Adds to `trading_hub/portfolio/journal_report.py`: win/loss ratio, post-drawdown position-size step-down

**Tests/verification:**
- Unit: step-down rule reduces size after N consecutive losses
- Integration: metrics appear in D-05 trade report

**Risks:** Step-down rule must not conflict with D-04 Kelly sizing; define precedence.

**Priority:** P2
**Depends on:** D-02, D-04

---

### D-09 — Strategy Correlation + Marginal Attribution

**Source:** ISI Ch3.8 (T2-02), STR Ch5 (T2-20)

**Expected files/modules:**
- `trading_hub/portfolio/attribution.py` — pairwise strategy return correlation, marginal Sharpe contribution

**Tests/verification:**
- Unit: identical strategies have correlation 1.0
- Integration: attribution blocks adding a strategy with correlation > 0.9 to pool

**Risks:** Correlation estimates unstable in short windows; require minimum 60-bar history.

**Priority:** P2
**Depends on:** D-05, C-01

---

## Phase E — Optional Later Research

*Low urgency. Do not start until Phases A–D are stable and paper-trading has run for at least one month.*

---

### E-01 — HMM Deep Dive

**Source:** PIK Ch5 (T3-03) | Extends C-04
*Adds more HMM state structures, emission models. Only if C-04 shows promising regime separation.*

---

### E-02 — Reinforcement Learning Hedging

**Source:** PIK Ch7 (T3-04)
*RL hedging overview. Blocked until D-04 and D-05 are stable. Architecture/safety-boundary only — no live execution.*

---

### E-03 — LLM / RAG Research Intake

**Source:** PIK Ch9 (T3-05), PIK Ch6 ex16–19 (T3-14)
*LLM-assisted research tagging. No trading decisions; information intake only.*

---

### E-04 — Intermarket / Macro Features

**Source:** MUR Ch17 (T3-09)
*Cross-asset features for regime detection. Adds data pipeline complexity.*

---

### E-05 — Interactive PCA Dashboard

**Source:** STR Ch3 (T3-13)
*Plotly Dash visualization layer. Nice-to-have after evaluation is stable.*

---

### E-06 — Futures Roll Methodology

**Source:** MUR App D (T3-15)
*Only if futures data (CME, crypto perps with roll simulation) is added to universe.*

---

## Broker / Live-Trading Chapters — Architecture / Safety Boundary Only

The following book sections touch broker connectivity, live order routing, or live execution. In Trading Hub they are treated as **architectural references for safety boundary design only**:

| Section | Boundary Role |
|---------|--------------|
| Strimpel Ch13 "Triggering Risk Limit Alerts" | Alert dispatch pattern — no order send; paper only (see D-06) |
| Pik Ch2 "Paper/Live" lifecycle stage | Stage labeling vocabulary only (see A-03) |
| Isichenko Ch7 §7.4 "Paper Trading" | Conceptual rationale for paper ledger design (see A-01) |
| Any broker API chapter not listed above | **Out of scope.** Do not implement. Reference architecture docs only if needed to understand the safety boundary. |

No card in this roadmap results in a broker API call, authenticated session, or order submission of any kind.

---

## Final Kanban Candidate Titles

### P0 — Foundation (blocking everything else)

| Card | Title |
|------|-------|
| A-01 | Simulation-vs-Production Checklist + Paper Ledger Schema |
| A-02 | Lookahead / Timestamp Audit Tests |
| A-03 | Strategy Lifecycle Status Labels |
| A-04 | Strategy Development Checklist Process Gate |
| A-05 | Margin-of-Safety Promotion Gate |
| B-01 | Data Quality Gates (missing bars, gaps, resampling) |
| B-03 | Cost / Slippage Sensitivity Report |
| C-01 | Walk-Forward Evaluation Harness (VectorBT) |
| D-01 | Paper Trading Guardrails (Cene 11 Methods) |

### P1 — Core Research Loop

| Card | Title |
|------|-------|
| B-02 | Local Market Data Store (SQLite / HDF5) |
| B-04 | Cost-Aware Parameter Ranking |
| C-02 | Factor / Signal Diagnostics (IC, Turnover) |
| C-03 | Regime-Classified Strategy Selection |
| C-04 | HMM Regime-Probability Calibration |
| C-05 | Classic Oscillator Baselines (RSI, MACD, Bollinger BW) |
| D-02 | Trade Journal Schema |
| D-03 | Volatility / Drawdown Stop Conditions |
| D-04 | Position Sizing (Fractional-Kelly + Inverse-Vol) |
| D-05 | Rolling Risk + Trade-Level Breakdown Report |

### P2 — Paper Portfolio Polish + Enhancements

| Card | Title |
|------|-------|
| C-06 | Volume / OI Confirmation Filter |
| C-07 | Previous-Day Level Features |
| D-06 | Paper Portfolio Risk Alerts (Discord / log) |
| D-07 | Paper Review Cadence + Cooldown Rules |
| D-08 | Money-Management Metrics in Paper Ledger |
| D-09 | Strategy Correlation + Marginal Attribution |
| E-01 | HMM Deep Dive (if C-04 validates) |
| E-02 | RL Hedging — Architecture / Safety-Boundary Only |
| E-03 | LLM / RAG Research Intake (information only) |
| E-04 | Intermarket / Macro Regime Features |
| E-05 | Interactive PCA Dashboard |
| E-06 | Futures Roll Methodology (if futures data added) |
