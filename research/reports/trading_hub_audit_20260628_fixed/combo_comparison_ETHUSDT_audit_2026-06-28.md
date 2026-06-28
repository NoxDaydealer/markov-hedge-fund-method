# Combo Strategy Comparison — ETHUSDT_audit_2026-06-28

| strategy                   | net_pnl   | max_drawdown | fee_to_gross_profit | trades | beats_random | sharpe_ratio | win_rate | gate              |
| -------------------------- | --------- | ------------ | ------------------- | ------ | ------------ | ------------ | -------- | ----------------- |
| vwap_reversion_baseline    | -0.004046 | -0.004046    | 4.864092            | 3      | True         | -8.839603    | 0.000000 | insufficient_data |
| vwap_rsi_markov_neutral    | 0.000000  | 0.000000     | inf                 | 0      | True         | 0.000000     | 0.000000 | insufficient_data |
| vwap_rsi_markov_contrarian | 0.000000  | 0.000000     | inf                 | 0      | True         | 0.000000     | 0.000000 | insufficient_data |
| bollinger_vwap_no_shorts   | -0.016713 | -0.016713    | 138.317913          | 8      | True         | -14.243112   | 0.000000 | insufficient_data |
| bollinger_vwap_shorts      | -0.224505 | -0.224505    | 7.097146            | 154    | False        | -59.014995   | 0.019481 | no_go             |
| combo_fib_liquidity        | -0.013159 | -0.013159    | 7.669586            | 8      | True         | -13.854981   | 0.000000 | insufficient_data |
| regime_gated_combo         | -0.006512 | -0.006512    | inf                 | 3      | True         | -8.785753    | 0.000000 | insufficient_data |
| no_trade                   | 0.000000  | 0.000000     | inf                 | 0      | True         | 0.000000     | 0.000000 | insufficient_data |
| buy_hold                   | -0.117020 | -0.117020    | inf                 | 1      | False        | -5.106145    | 0.000000 | insufficient_data |
| random_same_freq           | -0.045067 | -0.045067    | 6.480757            | 29     | False        | -25.707195   | 0.034483 | no_go             |
| naive_vwap                 | -1.000000 | -1.000000    | 9.035204            | 10049  | False        | -641.735234  | 0.005374 | no_go             |
