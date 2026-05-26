# Graph Report - markov-strategy  (2026-05-25)

## Corpus Check
- 40 files · ~32,547 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 887 nodes · 1583 edges · 39 communities (36 shown, 3 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 75 edges (avg confidence: 0.73)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `fe24cf94`
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

## God Nodes (most connected - your core abstractions)
1. `ComboFibLiquidityAdapter` - 23 edges
2. `BybitPublicCollector` - 19 edges
3. `train` - 18 edges
4. `test` - 18 edges
5. `all` - 18 edges
6. `train` - 18 edges
7. `test` - 18 edges
8. `all` - 18 edges
9. `QQQ` - 17 edges
10. `^IXIC` - 17 edges

## Surprising Connections (you probably didn't know these)
- `test_orderbook_features_compute_top_n_imbalance_and_delta()` --calls--> `compute_orderbook_features()`  [INFERRED]
  tests/test_bybit_l2_feature_prototype.py → research/bybit_l2_feature_prototype.py
- `test_adapter_emits_next_bar_signal_after_squeeze_breakout_vwap_volume_and_momentum_confirm()` --calls--> `BollingerVwapMomentumAdapter`  [INFERRED]
  tests/test_bollinger_vwap_momentum.py → trading_hub/strategies/bollinger_vwap_momentum.py
- `test_csv_input_matches_dataframe_and_adapter_makes_no_network_calls()` --calls--> `BollingerVwapMomentumAdapter`  [INFERRED]
  tests/test_bollinger_vwap_momentum.py → trading_hub/strategies/bollinger_vwap_momentum.py
- `test_no_future_bar_usage_prior_rows_unchanged_when_future_changes()` --calls--> `BollingerVwapMomentumAdapter`  [INFERRED]
  tests/test_bollinger_vwap_momentum.py → trading_hub/strategies/bollinger_vwap_momentum.py
- `test_backtest_uses_atr_trailing_exit_and_applies_cost_hooks()` --calls--> `run_bollinger_vwap_momentum_backtest()`  [INFERRED]
  tests/test_bollinger_vwap_momentum.py → trading_hub/backtest_report.py

## Communities (39 total, 3 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (33): Protocol, FakeWebSocket, FakeWebSocketConnector, read_jsonl(), StubRestClient, test_collect_once_subscribes_and_processes_mocked_websocket_events(), test_collector_writes_raw_and_normalized_trade_kline_and_spread(), test_orderbook_delta_updates_levels_and_removes_zero_size_levels() (+25 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (54): max, mean, median, min, stdev, max, mean, median (+46 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (47): assets, ^IXIC, NQ=F, QQQ, end, rows, selected_params_train_only, selected_positions_csv (+39 more)

### Community 3 - "Community 3"
Cohesion: 0.12
Nodes (47): imbalance_notional, imbalance_qty, orderbook_delta_imbalance, pressure_edge_bps, imbalance_notional, imbalance_qty, orderbook_delta_imbalance, pressure_edge_bps (+39 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (34): _atr(), BollingerVwapMomentumAdapter, generate_bollinger_vwap_momentum_signals(), _macd(), Pure local, paper-only Bollinger/VWAP/momentum strategy adapter.      The adapte, _rsi(), adapter_kwargs(), fixture_intraday_ohlcv() (+26 more)

### Community 5 - "Community 5"
Cohesion: 0.08
Nodes (33): generate_vwap_volume_rsi_reversion_signals(), Research-only Bybit intraday VWAP + Volume + RSI reversion adapter.      This ad, VWAPVolumeRSIReversionAdapter, fixture_1m_ohlcv(), test_adapter_generates_next_bar_long_after_vwap_rsi_volume_reclaim(), test_adapter_uses_optional_5m_filter_without_network(), test_backtest_exits_at_vwap_target_and_applies_cost_hooks(), test_backtest_supports_atr_stop_and_time_stop_paths() (+25 more)

### Community 6 - "Community 6"
Cohesion: 0.05
Nodes (43): 1.1 — Detect the operating system, 1.2 — Check for an existing install (idempotency), 1.3 — Check for `uv` (Astral's Python toolchain), 2.1 — Create the skill directory tree, 2.2 — Write the skill files, 2.3 — Pin Python 3.12 via uv, 3.1 — Install the required dependencies, 3.2 — Attempt the optional HMM extension (+35 more)

### Community 7 - "Community 7"
Cohesion: 0.08
Nodes (41): selected_params_train_first, sweep_csv, test, selected, selected, bb_vwap_momentum_breakout, atr_period, atr_stop (+33 more)

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
Cohesion: 0.20
Nodes (19): train, avg_trade_return_net, bars, exposure, fee_to_gross_profit, gross_total_return, long_trades, losses (+11 more)

### Community 19 - "Community 19"
Cohesion: 0.11
Nodes (18): Bybit Public Data — machbar ohne API-Key, Datenanforderungen, Entry/Exit-Regeln v0 — VWAP Volume Reversion, Evaluations- und Go/No-Go-Kriterien, Exit v0, Harte Entscheidung: Strategie zuerst, Kanban-Roadmap, Kandidat B: Bollinger Squeeze + VWAP Momentum Breakout (+10 more)

### Community 20 - "Community 20"
Cohesion: 0.31
Nodes (17): annualized_return, avg_trade_return_net, bars, exposure, gross_total_return, long_trades, losses, max_drawdown (+9 more)

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
Cohesion: 0.32
Nodes (7): atr(), _find_column(), generate_vwap_volume_reversion_signals(), Pure local VWAP + volume + RSI/StochRSI mean-reversion adapter.      The adapter, rolling_vwap(), rsi(), VWAPVolumeReversionAdapter

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

## Knowledge Gaps
- **174 isolated node(s):** `period`, `interval`, `train_fraction`, `round_trip_cost`, `rows` (+169 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `^IXIC` connect `Community 2` to `Community 20`, `Community 21`, `Community 22`, `Community 23`, `Community 24`, `Community 25`?**
  _High betweenness centrality (0.009) - this node is a cross-community bridge._
- **Why does `NQ=F` connect `Community 2` to `Community 20`, `Community 21`, `Community 22`, `Community 23`, `Community 24`, `Community 25`?**
  _High betweenness centrality (0.009) - this node is a cross-community bridge._
- **Why does `QQQ` connect `Community 2` to `Community 20`, `Community 21`, `Community 22`, `Community 23`, `Community 24`, `Community 25`?**
  _High betweenness centrality (0.009) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `ComboFibLiquidityAdapter` (e.g. with `BacktestResult` and `DataBundle`) actually correct?**
  _`ComboFibLiquidityAdapter` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `BybitPublicCollector` (e.g. with `StubRestClient` and `FakeWebSocket`) actually correct?**
  _`BybitPublicCollector` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Walk-forward Markov signal fit only on historical labels before each row.`, `period`, `interval` to the rest of the system?**
  _208 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.06845238095238096 - nodes in this community are weakly interconnected._