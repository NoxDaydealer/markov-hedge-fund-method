# Combo Strategy Comparison — 2026-05-27

| strategy                   | net_pnl   | max_drawdown | fee_to_gross_profit | trades | beats_random | sharpe_ratio | win_rate | gate              |
| -------------------------- | --------- | ------------ | ------------------- | ------ | ------------ | ------------ | -------- | ----------------- |
| vwap_reversion_baseline    | 0.000000  | 0.000000     | inf                 | 0      | True         | 0.000000     | 0.000000 | insufficient_data |
| vwap_rsi_markov_neutral    | 0.000000  | 0.000000     | inf                 | 0      | True         | 0.000000     | 0.000000 | insufficient_data |
| vwap_rsi_markov_contrarian | 0.000000  | 0.000000     | inf                 | 0      | True         | 0.000000     | 0.000000 | insufficient_data |
| bollinger_vwap_no_shorts   | -0.001423 | -0.001423    | 6.135044            | 1      | True         | -13.238520   | 0.000000 | insufficient_data |
| bollinger_vwap_shorts      | -0.030824 | -0.030824    | 28.955088           | 15     | False        | -50.080016   | 0.000000 | insufficient_data |
| combo_fib_liquidity        | 0.000000  | 0.000000     | inf                 | 0      | True         | 0.000000     | 0.000000 | insufficient_data |
| regime_gated_combo         | -0.001423 | -0.001423    | 6.135044            | 1      | True         | -13.238520   | 0.000000 | insufficient_data |
| no_trade                   | 0.000000  | 0.000000     | inf                 | 0      | True         | 0.000000     | 0.000000 | insufficient_data |
| buy_hold                   | -0.924025 | -0.924025    | 8.948259            | 1499   | False        | -670.024801  | 0.000000 | no_go             |
| random_same_freq           | -0.005883 | -0.005883    | inf                 | 3      | False        | -22.920593   | 0.000000 | insufficient_data |
| naive_vwap                 | -0.917236 | -0.917236    | 8.412092            | 1469   | False        | -656.114173  | 0.000000 | no_go             |
