# Candidate Evaluation Matrix Summary — 2026-06-28

## Scope

Controlled local evaluation across candidate strategy families and BTC/ETH 1m OHLCV. Research/paper-only; live trading remains locked.

## Outputs

- CSV: `/root/trading/markov-strategy/research/reports/candidate_evaluation_matrix_20260628/candidate_evaluation_matrix_2026-06-28.csv`
- Markdown: `/root/trading/markov-strategy/research/reports/candidate_evaluation_matrix_20260628/candidate_evaluation_matrix_2026-06-28.md`

## Gate counts

- go: 0
- no_go: 192
- insufficient_data: 0

## Interpretation

No candidate passed the walk-forward gate. Do not start a paper portfolio from this matrix yet; use the failure reasons to expand/refine candidates.

## Least-bad active rows

- BTCUSDT vwap_volume_rsi_reversion full_net_pnl=-0.001813, full_trades=1, avg_test_net_pnl=0.000000; params={"atr_period":7,"enable_shorts":false,"local_extreme_lookback":2,"markov_gate":"off","rsi_period":7,"stochrsi_period":7,"volume_multiple":1.25,"volume_window":10,"vwap_window":20,"z_threshold":0.5,"z_window":20}
- BTCUSDT vwap_volume_rsi_reversion full_net_pnl=-0.001813, full_trades=1, avg_test_net_pnl=0.000000; params={"atr_period":7,"enable_shorts":false,"local_extreme_lookback":3,"markov_gate":"off","rsi_period":7,"stochrsi_period":7,"volume_multiple":1.25,"volume_window":10,"vwap_window":20,"z_threshold":0.5,"z_window":20}
- BTCUSDT vwap_volume_rsi_reversion full_net_pnl=-0.001813, full_trades=1, avg_test_net_pnl=0.000000; params={"atr_period":7,"enable_shorts":false,"local_extreme_lookback":2,"markov_gate":"off","rsi_period":7,"stochrsi_period":7,"volume_multiple":1.25,"volume_window":10,"vwap_window":20,"z_threshold":0.75,"z_window":20}
- BTCUSDT vwap_volume_rsi_reversion full_net_pnl=-0.001813, full_trades=1, avg_test_net_pnl=0.000000; params={"atr_period":7,"enable_shorts":false,"local_extreme_lookback":3,"markov_gate":"off","rsi_period":7,"stochrsi_period":7,"volume_multiple":1.25,"volume_window":10,"vwap_window":20,"z_threshold":0.75,"z_window":20}
- BTCUSDT vwap_volume_rsi_reversion full_net_pnl=-0.001813, full_trades=1, avg_test_net_pnl=0.000000; params={"atr_period":7,"enable_shorts":false,"local_extreme_lookback":2,"markov_gate":"off","rsi_period":7,"stochrsi_period":7,"volume_multiple":1.25,"volume_window":10,"vwap_window":20,"z_threshold":1.0,"z_window":20}
