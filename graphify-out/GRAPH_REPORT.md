# Graph Report - markov-strategy  (2026-05-27)

## Corpus Check
- 90 files · ~70,504 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1466 nodes · 2465 edges · 77 communities (71 shown, 6 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 337 edges (avg confidence: 0.73)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8b348aac`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]

## God Nodes (most connected - your core abstractions)
1. `open_position()` - 45 edges
2. `RegimeGatedCombo` - 36 edges
3. `run_backtest()` - 31 edges
4. `close_position()` - 28 edges
5. `ComboFibLiquidityAdapter` - 24 edges
6. `Trade` - 22 edges
7. `BacktestResult` - 21 edges
8. `BybitPublicCollector` - 19 edges
9. `PITDataStore` - 19 edges
10. `train` - 18 edges

## Surprising Connections (you probably didn't know these)
- `tmp_store()` --calls--> `PITDataStore`  [INFERRED]
  tests/test_pit_data_pipeline.py → trading_hub/data/pit_store.py
- `test_negative_cost_bps_in_apply_cost_to_return_raises_value_error()` --calls--> `apply_cost_to_return()`  [INFERRED]
  tests/test_cost_model.py → trading_hub/costs.py
- `test_invalid_sensitivity_multiplier_raises_value_error()` --calls--> `build_slippage_sensitivity_matrix()`  [INFERRED]
  tests/test_cost_model.py → trading_hub/costs.py
- `_eval()` --calls--> `EvaluationResult`  [INFERRED]
  tests/test_go_no_go_gate.py → trading_hub/hft_evaluator.py
- `_fold()` --calls--> `WalkForwardFold`  [INFERRED]
  tests/test_go_no_go_gate.py → trading_hub/hft_evaluator.py

## Communities (77 total, 6 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (33): Protocol, FakeWebSocket, FakeWebSocketConnector, read_jsonl(), StubRestClient, test_collect_once_subscribes_and_processes_mocked_websocket_events(), test_collector_writes_raw_and_normalized_trade_kline_and_spread(), test_orderbook_delta_updates_levels_and_removes_zero_size_levels() (+25 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (54): max, mean, median, min, stdev, max, mean, median (+46 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (64): assets, ^IXIC, NQ=F, QQQ, annualized_return, avg_trade_return_net, bars, exposure (+56 more)

### Community 3 - "Community 3"
Cohesion: 0.12
Nodes (47): imbalance_notional, imbalance_qty, orderbook_delta_imbalance, pressure_edge_bps, imbalance_notional, imbalance_qty, orderbook_delta_imbalance, pressure_edge_bps (+39 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (34): _atr(), BollingerVwapMomentumAdapter, generate_bollinger_vwap_momentum_signals(), _macd(), Pure local, paper-only Bollinger/VWAP/momentum strategy adapter.      The adapte, _rsi(), adapter_kwargs(), fixture_intraday_ohlcv() (+26 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (40): atr(), _find_column(), generate_vwap_volume_reversion_signals(), Pure local VWAP + volume + RSI/StochRSI mean-reversion adapter.      The adapter, rolling_vwap(), rsi(), VWAPVolumeReversionAdapter, generate_vwap_volume_rsi_reversion_signals() (+32 more)

### Community 6 - "Community 6"
Cohesion: 0.05
Nodes (43): 1.1 — Detect the operating system, 1.2 — Check for an existing install (idempotency), 1.3 — Check for `uv` (Astral's Python toolchain), 2.1 — Create the skill directory tree, 2.2 — Write the skill files, 2.3 — Pin Python 3.12 via uv, 3.1 — Install the required dependencies, 3.2 — Attempt the optional HMM extension (+35 more)

### Community 7 - "Community 7"
Cohesion: 0.06
Nodes (60): selected_params_train_first, sweep_csv, test, train, selected, selected, bb_vwap_momentum_breakout, atr_period (+52 more)

### Community 8 - "Community 8"
Cohesion: 0.12
Nodes (32): hft_fixture(), test_baselines_include_no_trade_buy_hold_random_same_frequency_and_vwap(), test_cost_model_applies_taker_fees_spread_and_slippage_to_trade_ev(), test_evaluate_with_baselines_reports_pnl_by_regime_and_required_metrics(), test_latency_max_trades_per_day_and_cooldown_throttle_signals(), test_walk_forward_evaluate_creates_train_validation_test_folds_with_test_baselines(), _align_regime(), _align_signal() (+24 more)

### Community 9 - "Community 9"
Cohesion: 0.10
Nodes (32): best_by_test_net_total_return, best_by_test_test_trades, random_test_median_net_return, random_test_p95_net_return, random_train_median_net_return, random_train_p95_net_return, selected_test_gross_total_return, selected_test_net_total_return (+24 more)

### Community 10 - "Community 10"
Cohesion: 0.07
Nodes (26): data_csv, end, rows, start, test_end, test_start, train_end, train_start (+18 more)

### Community 11 - "Community 11"
Cohesion: 0.11
Nodes (24): analyze(), build_transition_matrix(), fetch_ticker(), fit_hmm(), _hmm_summary(), label_regimes(), load_csv(), main() (+16 more)

### Community 12 - "Community 12"
Cohesion: 0.18
Nodes (17): ComboFibLiquidityAdapter, _find_column(), generate_combo_fib_liquidity_signals(), Paper-only adapter for the combo_fib_liquidity TradingEngine strategy.      The, Convenience functional API for paper combo_fib_liquidity signals., fixture_ohlcv(), test_adapter_accepts_dataframe_and_returns_next_bar_paper_signals(), test_adapter_does_not_make_network_calls() (+9 more)

### Community 13 - "Community 13"
Cohesion: 0.17
Nodes (17): BybitPublicClient, collect_feature_dataset(), compute_aggressive_trade_flow(), compute_orderbook_features(), L2Config, main(), make_diagnostics(), parse_args() (+9 more)

### Community 14 - "Community 14"
Cohesion: 0.10
Nodes (20): Bollinger VWAP Momentum v0, Bybit public market data collector, code:block1 (/plugin marketplace add jackson-video-resources/markov-hedge), code:block2 (/markov-hedge-fund-method:regime), code:python (from trading_hub.strategies.combo_fib_liquidity import Combo), code:python (from trading_hub.strategies.bollinger_vwap_momentum import B), code:bash (python -m trading_hub.backtest_report \), code:bash (python -m trading_hub.backtest_report \) (+12 more)

### Community 15 - "Community 15"
Cohesion: 0.22
Nodes (20): add_features(), atr(), breakout_grid(), breakout_positions(), BreakoutParams, compute_metrics(), evaluate_breakout(), evaluate_reversion() (+12 more)

### Community 16 - "Community 16"
Cohesion: 0.20
Nodes (10): _find_column(), generate_intraday_markov_gate(), IntradayMarkovRegimeGate, Trailing-only intraday regime gate for HFT strategy candidates.      The gate co, Convenience functional API for intraday Markov regime-gate outputs., intraday_fixture(), test_gate_is_no_lookahead_when_future_bars_change(), test_gate_outputs_intraday_features_decisions_and_optimizer_inputs() (+2 more)

### Community 17 - "Community 17"
Cohesion: 0.20
Nodes (19): avg_trade_return_net, bars, exposure, fee_to_gross_profit, gross_total_return, long_trades, losses, max_drawdown (+11 more)

### Community 18 - "Community 18"
Cohesion: 0.05
Nodes (42): _make_ohlcv(), Targeted tests for trading_hub.backtest_runner — Card D.  Scope: RegimeGatedComb, Low volatility regime should select mean_reversion as it's better suited., High volatility regime should select momentum as trend following benefits., Deterministic OHLCV DataFrame for testing., Equity curve should not have NaN or infinite values., TestATR, TestATRPercentile (+34 more)

### Community 19 - "Community 19"
Cohesion: 0.11
Nodes (18): Bybit Public Data — machbar ohne API-Key, Datenanforderungen, Entry/Exit-Regeln v0 — VWAP Volume Reversion, Evaluations- und Go/No-Go-Kriterien, Exit v0, Harte Entscheidung: Strategie zuerst, Kanban-Roadmap, Kandidat B: Bollinger Squeeze + VWAP Momentum Breakout (+10 more)

### Community 20 - "Community 20"
Cohesion: 0.06
Nodes (70): Enum, clean_ledger(), clean_ledger(), Targeted tests for trading_hub.ledger — Card C.  Scope: pure in-memory position, Reset ledger state before and after every test., test_close_position_already_closed(), test_close_position_breakeven_with_costs(), test_close_position_exit_before_entry() (+62 more)

### Community 21 - "Community 21"
Cohesion: 0.31
Nodes (17): annualized_return, avg_trade_return_net, bars, exposure, gross_total_return, long_trades, losses, max_drawdown (+9 more)

### Community 22 - "Community 22"
Cohesion: 0.31
Nodes (17): annualized_return, avg_trade_return_net, bars, exposure, gross_total_return, long_trades, losses, max_drawdown (+9 more)

### Community 23 - "Community 23"
Cohesion: 0.31
Nodes (17): markov_only_test, annualized_return, avg_trade_return_net, bars, exposure, gross_total_return, long_trades, losses (+9 more)

### Community 24 - "Community 24"
Cohesion: 0.31
Nodes (17): annualized_return, avg_trade_return_net, bars, exposure, gross_total_return, long_trades, losses, max_drawdown (+9 more)

### Community 25 - "Community 25"
Cohesion: 0.31
Nodes (17): markov_only_train, annualized_return, avg_trade_return_net, bars, exposure, gross_total_return, long_trades, losses (+9 more)

### Community 26 - "Community 26"
Cohesion: 0.31
Nodes (13): buy_hold(), combo_positions(), evaluate_param(), fetch_ohlcv(), main(), markov_only(), markov_signal(), Metrics (+5 more)

### Community 27 - "Community 27"
Cohesion: 0.15
Nodes (12): (a) Regime confirmation on an existing momentum/strategy, (b) Stationary distribution as a tail-risk / position-size filter, (c) Standalone signal, code:bash (# any ticker yfinance knows (stocks, ETFs, crypto, FX, futur), code:python (import json, subprocess), code:python (bear_baseline = r["stationary_distribution"]["bear"]), code:python (position = r["signal"]        # +0.6 → 60% long; -0.4 → 40% ), Composition — slot it into what the user already has (+4 more)

### Community 28 - "Community 28"
Cohesion: 0.04
Nodes (44): A-01 — Simulation-vs-Production Checklist, A-02 — Lookahead / Timestamp Audit, A-03 — Strategy Lifecycle Status Labels, A-04 — Strategy Development Checklist (Process Gate), A-05 — Margin-of-Safety Promotion Gate, B-01 — Data Quality Gates, B-02 — Local Market Data Store, B-03 — Cost / Slippage Sensitivity Report (+36 more)

### Community 29 - "Community 29"
Cohesion: 0.18
Nodes (10): Artifacts, Data and assumptions, Default-settings sanity check, Diagnostic best-test variants (not train-selected), Interpretation, NASDAQ combo_fib_liquidity parameter sweep, Objective, Parameter grid (+2 more)

### Community 30 - "Community 30"
Cohesion: 0.20
Nodes (9): Baselines and diagnostics, Bottom line, Bybit Intraday Strategy Sprint Verdict, Headline results, Implementation recommendation, Scope, Selected train-first variants, Strategies evaluated (+1 more)

### Community 31 - "Community 31"
Cohesion: 0.22
Nodes (8): Bottom line, BTCUSDT, Bybit L2 Orderbook Imbalance Feature Prototype, Conservative queue/fill caveats, Diagnostics, ETHUSDT, Features, Scope

### Community 32 - "Community 32"
Cohesion: 0.47
Nodes (8): asset(), load_report_module(), test_config_entries_include_required_metadata(), test_default_config_enabled_universe_matches_existing_tickers(), test_disabled_assets_are_skipped(), test_main_prints_readable_config_error_without_traceback(), test_malformed_config_raises_readable_error(), write_config()

### Community 33 - "Community 33"
Cohesion: 0.25
Nodes (7): metadata, description, version, name, owner, name, plugins

### Community 34 - "Community 34"
Cohesion: 0.29
Nodes (5): Core assumptions, HFT Evaluation Framework (paper/research only), Minimal usage, Paper-report gate, Required evaluation surface

### Community 35 - "Community 35"
Cohesion: 0.33
Nodes (5): author, name, description, name, version

### Community 39 - "Community 39"
Cohesion: 0.05
Nodes (35): 1. Executive Summary, 2. Was der Graph/Repo-Zustand nahelegt, 3. Zielarchitektur für den Strategy Combination Evaluator, 4.1 Pflicht-Eingabe (alle Strategien), 4.2 Signal-Konvention (bestehend, unveränderlich), 4.3 Kosten-Standard (konservativ, aus hft_evaluator.CostModel), 4.4 Walk-Forward Standard, 4.5 Output-Schema (unified, neu) (+27 more)

### Community 40 - "Community 40"
Cohesion: 0.08
Nodes (34): comparison_results(), _fixture(), Tests for trading_hub.combo_comparison_report., Synthetic OHLCV with enough bars for all strategy indicators to warm up., test_csv_contains_required_columns(), _eval(), _fold(), Tests for trading_hub.go_no_go_gate. (+26 more)

### Community 41 - "Community 41"
Cohesion: 0.09
Nodes (29): Tests für Karte B — isoliertes Cost/Slippage-Modul.  Deterministisch und offline, Das Kostenmodul bleibt isoliert von Broker-/Datenquellen-Bibliotheken.      Verw, notional > 0 aber impact_coefficient_bps == 0: kein ADV erforderlich., Bei gleichem Notional: groesserer ADV → niedrigere Impact-Kosten (Monotonie in A, Roundtrip-Kosten addieren Fees pro Seite, Spread einmal, Slippage pro Seite., Eine explizite Impact-Komponente wird auf die Basis-Kosten addiert., Größere Trade-Größe erhöht die modellierte Impact-Komponente., 100 bps Kosten reduzieren einen 5%-Brutto-Return auf 4%. (+21 more)

### Community 42 - "Community 42"
Cohesion: 0.10
Nodes (18): Run a compact, local-only Bollinger/VWAP/momentum parameter sweep.      This wra, run_bollinger_vwap_momentum_sweep(), _write_optional_csv(), Run a compact, local-only VWAP/volume/RSI reversion parameter sweep.      This i, run_vwap_volume_rsi_reversion_sweep(), _ohlcv(), test_param_sweep_keeps_zero_trade_combinations_with_hft_metric_schema(), test_param_sweep_rejects_too_many_combinations_before_running_adapters() (+10 more)

### Community 43 - "Community 43"
Cohesion: 0.08
Nodes (25): 1. Executive Decision — Die nächsten 1–3 Bausteine, 2. Buch-Synthese — 10 handlungsleitende Prinzipien, 3. Paper-Trading-Zielarchitektur, 4. Roadmap — Implementierungskarten, 5. Priorisierte Foto/OCR-Nachforderungen, 6. Sicherheitsregeln, 7. Offene Fragen (max 5), Baustein 1 (sofort): PIT-konformer Paper-Ledger + Virtual Account (+17 more)

### Community 44 - "Community 44"
Cohesion: 0.28
Nodes (16): _gate(), _idx(), test_no_lookahead_behavior(), test_regime_flat_returns_zero(), test_regime_high_spread_blocked(), test_regime_momentum_passes_momentum_signal(), test_regime_reversion_passes_reversion_signal(), test_signalkollision_reversion_wins() (+8 more)

### Community 45 - "Community 45"
Cohesion: 0.12
Nodes (6): Write and read back produces identical close column., All rows returned by read(as_of=T) satisfy available_at <= T., read(as_of=very_early) returns empty DataFrame., available_at defaults to date + 1 business day (EOD PIT convention)., If DataFrame already has available_at, it is not overwritten., TestPITDataStore

### Community 46 - "Community 46"
Cohesion: 0.18
Nodes (9): Raise LookaheadError if any row has available_at >= signal_time.      Parameters, validate_pit_compliance(), No exception when all available_at are strictly before signal_time., LookaheadError raised when a row has available_at >= signal_time., LookaheadError raised when available_at is after signal_time., LookaheadError raised when available_at column is absent., Empty DataFrame with available_at column does not raise., Custom available_at column name is respected. (+1 more)

### Community 47 - "Community 47"
Cohesion: 0.19
Nodes (7): PITDataStore, Load PIT-safe OHLCV data for symbol.          Returns only rows where available_, Return list of symbols present in the store., Local filesystem store for PIT-compliant OHLCV data.      Layout on disk (per sy, Persist OHLCV DataFrame for symbol with available_at column.          If the Dat, BacktestConfig, TypedDict

### Community 48 - "Community 48"
Cohesion: 0.24
Nodes (12): test_regime_gated_signal_flattens_explicit_flat_and_disallowed_rows(), test_regime_gated_signal_handles_empty_and_constant_zero_inputs(), test_regime_gated_signal_preserves_gate_index_and_reindexes_inputs(), test_regime_gated_signal_rejects_flat_regime_mapping_to_prevent_flat_trades(), test_regime_gated_signal_rejects_nonzero_flat_default_to_prevent_default_trades(), test_regime_gated_signal_selects_non_overlapping_strategy_signals_per_bar(), test_regime_gated_signal_uses_mapping_order_as_conflict_priority(), build_regime_gated_signal() (+4 more)

### Community 49 - "Community 49"
Cohesion: 0.15
Nodes (12): code:block1 (00_Inbox/), Desired Architecture, Future UI Tie-In, Intent, MVP Automation, Obsidian Vault Integration — Second Brain for Nox / Trading Hub, Proposed Vault Path, Safety / Scope (+4 more)

### Community 50 - "Community 50"
Cohesion: 0.17
Nodes (11): code:bash (# easiest: just open it in a browser), code:bash (cd sketches/006-opus-jarvis-reference-neural-cloud), code:block3 (sketches/006-opus-jarvis-reference-neural-cloud/), Data model (mocked), Disclaimer, File structure, How to open, Interactions (+3 more)

### Community 51 - "Community 51"
Cohesion: 0.24
Nodes (8): _make_ohlcv(), Tests für Karte A — PIT-Datenpipeline.  Kein Netzwerk. Kein yfinance. Nur lokale, A 'delisted' symbol written once still returns its historical data.          Thi, Delisted and active symbols coexist in the store without conflict., Build a minimal OHLCV DataFrame for testing (no network calls)., sample_df(), TestSurvivalBias, tmp_store()

### Community 52 - "Community 52"
Cohesion: 0.20
Nodes (9): Backlog Status, Candidate Visual Variants, Constraints, Intent, MVP Scope, Product Goal, Suggested Implementation Path, Trading Hub / Nox Neural Dashboard Backlog (+1 more)

### Community 53 - "Community 53"
Cohesion: 0.25
Nodes (7): Card: **Karte A — PIT-Datenpipeline mit `available_at`-Enforcement**, Critical Fixes Before Implementation, First Implementation Card Recommendation, Opus Review — Trading Hub Phase-1 Plan, Roadmap Reordering, Safety Checklist For Sonnet, Verdict

### Community 54 - "Community 54"
Cohesion: 0.25
Nodes (7): Absolute Stop Rule, Critical Fixes Before Implementation, First Implementation Card Recommendation, Opus Review — Trading Hub Phase-1 Plan, Roadmap Reordering, Safety Checklist For Sonnet, Verdict

### Community 55 - "Community 55"
Cohesion: 0.29
Nodes (6): Critical Issues, Next Card Recommendation, Opus Review — Card B Cost/Slippage, Safety Check, Suggested Fixes Before Next Card, Verdict

### Community 56 - "Community 56"
Cohesion: 0.29
Nodes (6): Critical Issues, Next Card Recommendation, Opus Review — Card B Cost/Slippage, Safety Check, Suggested Fixes Before Next Card, Verdict

### Community 57 - "Community 57"
Cohesion: 0.33
Nodes (5): Best for, Design stance, Key choices, Trade-offs, Variant: Jarvis Reference Neural Cloud

### Community 58 - "Community 58"
Cohesion: 0.40
Nodes (4): Design stance, Key choices, Trade-offs, Variant: Neural Brain Map

### Community 59 - "Community 59"
Cohesion: 0.40
Nodes (4): Design stance, Key choices, Trade-offs, Variant: Data Cloud Particle Map

### Community 60 - "Community 60"
Cohesion: 0.40
Nodes (4): Design stance, Key choices, Trade-offs, Variant: Command Center Hybrid

### Community 61 - "Community 61"
Cohesion: 0.40
Nodes (4): LookaheadError, PIT-Compliance-Validator.  Regel: Ein Signal zum Zeitpunkt T darf ausschließlich, Raised when a feature DataFrame contains future data relative to signal_time., Exception

### Community 62 - "Community 62"
Cohesion: 0.40
Nodes (3): Full pipeline: write → read(as_of) → validate_pit_compliance passes., Using data available_at == signal_time raises LookaheadError., TestEndToEndPITPipeline

### Community 63 - "Community 63"
Cohesion: 0.50
Nodes (3): fetch_yfinance(), PITDataStore — Point-in-Time-konformer lokaler Datenspeicher.  Storage-Entscheid, Fetch OHLCV data via yfinance (read-only).      Returns a DataFrame with lowerca

## Knowledge Gaps
- **308 isolated node(s):** `period`, `interval`, `train_fraction`, `round_trip_cost`, `rows` (+303 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_backtest()` connect `Community 18` to `Community 41`, `Community 20`, `Community 47`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **Why does `_build_strategy_signals()` connect `Community 40` to `Community 4`, `Community 5`, `Community 12`, `Community 44`, `Community 16`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **Why does `PITDataStore` connect `Community 47` to `Community 45`, `Community 46`, `Community 18`, `Community 51`, `Community 62`, `Community 63`?**
  _High betweenness centrality (0.015) - this node is a cross-community bridge._
- **Are the 38 inferred relationships involving `open_position()` (e.g. with `test_open_position_returns_id()` and `test_open_position_increments_ids()`) actually correct?**
  _`open_position()` has 38 INFERRED edges - model-reasoned connections that need verification._
- **Are the 30 inferred relationships involving `RegimeGatedCombo` (e.g. with `TestClassifyRegime` and `TestBarReturns`) actually correct?**
  _`RegimeGatedCombo` has 30 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `run_backtest()` (e.g. with `.test_empty_tickers_raises()` and `.test_default_capital()`) actually correct?**
  _`run_backtest()` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 24 inferred relationships involving `close_position()` (e.g. with `test_close_position_returns_pnl_bps()` and `test_close_position_stores_exit_data()`) actually correct?**
  _`close_position()` has 24 INFERRED edges - model-reasoned connections that need verification._