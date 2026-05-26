# HFT Evaluation Framework (paper/research only)

This module adds a shared evaluator for intraday strategy adapters at
`trading_hub.hft_evaluator`. It is deliberately broker-free: callers provide
OHLCV bars plus a desired side signal (`-1`, `0`, `+1`), and the evaluator
simulates delayed paper fills, costs, throttles, baselines, and walk-forward
splits.

## Core assumptions

- No live orders, API keys, broker calls, or income claims.
- Signals are shifted by `ExecutionAssumptions.latency_bars` before execution.
- Trades enter at the execution bar open and exit after `hold_bars` at a future
  open to avoid same-bar lookahead.
- Costs are charged as a conservative round trip:
  `2 * (maker_or_taker_fee_bps + spread_bps + slippage_bps) / 10_000`.
- Throttles support `max_trades_per_day` and `cooldown_bars`.

## Required evaluation surface

Implemented in `trading_hub.hft_evaluator`:

- Costs: maker/taker fees, spread, slippage.
- Latency assumptions: configurable bar delay before fill.
- Trade constraints: max trades/day, cooldown bars.
- Walk-forward: train/validation/test windows with rolling step.
- Baselines:
  - no-trade
  - buy-hold
  - random same frequency
  - naive VWAP reversion
- Metrics:
  - net PnL
  - EV/trade
  - trades/day
  - profit factor and gross profit factor
  - max drawdown
  - fee-to-gross-profit
  - PnL by regime
  - long/short trade counts, win rate, gross PnL, total costs, Sharpe

## Minimal usage

```python
from trading_hub.hft_evaluator import (
    CostModel,
    ExecutionAssumptions,
    TradeConstraints,
    WalkForwardConfig,
    evaluate_with_baselines,
    walk_forward_evaluate,
)

results = evaluate_with_baselines(
    ohlcv_frame,
    strategy_signal,
    name="vwap_volume_rsi_reversion",
    cost_model=CostModel(taker_fee_bps=5.5, spread_bps=1.0, slippage_bps=2.0),
    execution=ExecutionAssumptions(latency_bars=1, hold_bars=5),
    constraints=TradeConstraints(max_trades_per_day=20, cooldown_bars=2),
    regime=regime_labels,
)

folds = walk_forward_evaluate(
    ohlcv_frame,
    strategy_signal,
    WalkForwardConfig(train_bars=30 * 1440, validation_bars=7 * 1440, test_bars=7 * 1440),
    cost_model=CostModel(taker_fee_bps=5.5, spread_bps=1.0, slippage_bps=2.0),
    execution=ExecutionAssumptions(latency_bars=1, hold_bars=5),
)
```

## Paper-report gate

A candidate should not be used in a report unless its test folds are positive
after costs, beat the same-frequency random and naive VWAP baselines, have enough
trades for the sample, and do not lose the edge under higher slippage.
