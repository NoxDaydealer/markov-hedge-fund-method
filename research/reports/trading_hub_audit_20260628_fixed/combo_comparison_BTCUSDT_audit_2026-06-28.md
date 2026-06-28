# Combo Strategy Comparison — BTCUSDT_audit_2026-06-28

| strategy                   | net_pnl   | max_drawdown | fee_to_gross_profit | trades | beats_random | sharpe_ratio | win_rate | gate              |
| -------------------------- | --------- | ------------ | ------------------- | ------ | ------------ | ------------ | -------- | ----------------- |
| vwap_reversion_baseline    | -0.008398 | -0.008398    | 21.657766           | 3      | True         | -7.528049    | 0.000000 | insufficient_data |
| vwap_rsi_markov_neutral    | 0.000000  | 0.000000     | inf                 | 0      | True         | 0.000000     | 0.000000 | insufficient_data |
| vwap_rsi_markov_contrarian | 0.000000  | 0.000000     | inf                 | 0      | True         | 0.000000     | 0.000000 | insufficient_data |
| bollinger_vwap_no_shorts   | -0.024325 | -0.024325    | 6.738377            | 16     | True         | -19.784924   | 0.000000 | insufficient_data |
| bollinger_vwap_shorts      | -0.240665 | -0.240665    | 8.463331            | 165    | False        | -62.491497   | 0.018182 | no_go             |
| combo_fib_liquidity        | -0.011079 | -0.011079    | 5.800244            | 7      | True         | -12.330462   | 0.000000 | insufficient_data |
| regime_gated_combo         | -0.010281 | -0.010281    | 14.433904           | 6      | True         | -12.269769   | 0.000000 | insufficient_data |
| no_trade                   | 0.000000  | 0.000000     | inf                 | 0      | True         | 0.000000     | 0.000000 | insufficient_data |
| buy_hold                   | -0.065358 | -0.065358    | inf                 | 1      | False        | -5.106145    | 0.000000 | insufficient_data |
| random_same_freq           | -0.054877 | -0.054877    | 9.246119            | 33     | False        | -27.950610   | 0.030303 | no_go             |
| naive_vwap                 | -1.000000 | -1.000000    | 11.074690           | 10049  | False        | -675.728901  | 0.002587 | no_go             |
