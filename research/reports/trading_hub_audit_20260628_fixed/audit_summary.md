# Trading Hub Audit — 2026-06-28

## Scope

Paper-only Trading Hub audit for the existing `/root/trading/markov-strategy` stack. No broker/API credentials, no live orders, no network trading integration.

## Verification

- Full suite: `uv run python -m pytest -q` → `199 passed in 2.80s`
- Targeted baseline regression: `uv run python -m pytest tests/test_hft_evaluator.py::test_buy_hold_baseline_is_one_full_period_trade_not_rebalanced_every_bar tests/test_hft_evaluator.py tests/test_combo_comparison_report.py -q` → `9 passed`

## Fix applied

The `buy_hold` baseline was previously misleading inside HFT/combo reports: a persistent `+1` signal was evaluated with one-bar intraday execution, causing thousands of repeated trades and artificial `-1.000000` PnL under costs.

Fix:

- Added `evaluate_baseline_signal()` in `trading_hub/hft_evaluator.py`.
- `buy_hold` now evaluates as one full-period long trade (`entry = first open`, `exit = last open`) with one round-trip cost.
- Other baselines keep candidate-comparable intraday execution semantics.
- `combo_comparison_report.py` now uses the baseline-aware evaluator.
- Added regression test proving `buy_hold` is one full-period trade, not rebalanced every bar.

## Fresh reports

Generated under `research/reports/trading_hub_audit_20260628_fixed/`:

- `combo_comparison_BTCUSDT_audit_2026-06-28.csv`
- `combo_comparison_BTCUSDT_audit_2026-06-28.md`
- `combo_comparison_ETHUSDT_audit_2026-06-28.csv`
- `combo_comparison_ETHUSDT_audit_2026-06-28.md`

## Result snapshot

### BTCUSDT

- No strategy reaches `go`.
- Most candidates are `insufficient_data` because trade counts are too low.
- `bollinger_vwap_shorts` is `no_go`: negative net PnL, high drawdown, does not beat random.
- Corrected `buy_hold`: `-0.065358`, 1 trade, `insufficient_data` by single-row gate because min-trades rule is not designed for hold baseline.

### ETHUSDT

- No strategy reaches `go`.
- Most candidates are `insufficient_data` because trade counts are too low.
- `bollinger_vwap_shorts` is `no_go`: negative net PnL, high drawdown, does not beat random.
- Corrected `buy_hold`: `-0.117020`, 1 trade, `insufficient_data` by single-row gate because min-trades rule is not designed for hold baseline.

## Interpretation

Current BTC/ETH intraday strategy set is not paper-trading ready. The immediate blocker is not infrastructure anymore; it is strategy quality + too few accepted trades after regime/entry filters. Next work should focus on robust candidate expansion and walk-forward evaluation, not live trading.

## Recommended next card

Build `Trading Hub Candidate Evaluation Matrix v0`:

1. Define a unified candidate registry for adapters/sweeps.
2. Run controlled sweeps across BTCUSDT and ETHUSDT with realistic costs.
3. Add walk-forward folds and minimum sample gates per strategy.
4. Report top candidates, rejected candidates, and failure reasons.
5. Keep live trading locked; if no `go`, do not start paper portfolio.
