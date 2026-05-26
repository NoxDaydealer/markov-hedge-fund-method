# Bybit L2 Orderbook Imbalance Feature Prototype

## Scope

Research-only feature prototype for Paper Trading. No broker keys, fills, or live orders were used.
The generated CSV is a feature dataset from Bybit public REST orderbook snapshots plus recent trades.
It is not a backtest and not a strategy recommendation.

Artifacts:
- Feature dataset: `research/bybit_l2_feature_prototype/features.csv`
- Machine diagnostics: `research/bybit_l2_feature_prototype/summary.json`
- Runner: `research/bybit_l2_feature_prototype.py`

## Features

Per symbol and snapshot the dataset includes:
- Best bid/ask, mid, spread, spread in bps.
- Top-1 microprice and edge vs mid in bps.
- Top-N bid/ask quantity and notional depth for configured N values.
- Top-N quantity and notional imbalance: `(bid - ask) / (bid + ask)`.
- Top-N pressure price/edge, a microprice-like book-pressure feature.
- Top-N orderbook delta imbalance from consecutive sampled snapshots.
- Recent public-trade buy/sell count, size, notional, and aggressive-flow imbalance since prior sample.

## Diagnostics

### BTCUSDT

Rows: 20 from 2026-05-24T23:50:56.644000+00:00 to 2026-05-24T23:51:10.843000+00:00.
Spread bps mean/median/max: 0.0130 / 0.0130 / 0.0130.
Top-1 microprice edge bps mean/median: 0.0022 / 0.0036.
Aggressive notional-flow imbalance mean/median: -0.0832 / 0.0000.

Top-N imbalance means:
- N=1: qty imbalance mean 0.3465, notional imbalance mean 0.3465, delta imbalance mean -0.2104, pressure edge mean 0.0022 bps.
- N=5: qty imbalance mean 0.3761, notional imbalance mean 0.3760, delta imbalance mean -0.0713, pressure edge mean 0.0070 bps.
- N=10: qty imbalance mean 0.4043, notional imbalance mean 0.4043, delta imbalance mean -0.1600, pressure edge mean 0.0123 bps.
- N=25: qty imbalance mean 0.4325, notional imbalance mean 0.4325, delta imbalance mean -0.0398, pressure edge mean 0.0429 bps.
- N=50: qty imbalance mean 0.2098, notional imbalance mean 0.2097, delta imbalance mean 0.0499, pressure edge mean 0.2409 bps.

### ETHUSDT

Rows: 20 from 2026-05-24T23:50:57.192000+00:00 to 2026-05-24T23:51:10.992000+00:00.
Spread bps mean/median/max: 0.0476 / 0.0476 / 0.0476.
Top-1 microprice edge bps mean/median: 0.0172 / 0.0215.
Aggressive notional-flow imbalance mean/median: 0.0206 / 0.0000.

Top-N imbalance means:
- N=1: qty imbalance mean 0.7217, notional imbalance mean 0.7217, delta imbalance mean 0.1518, pressure edge mean 0.0172 bps.
- N=5: qty imbalance mean 0.7235, notional imbalance mean 0.7235, delta imbalance mean 0.1791, pressure edge mean 0.0710 bps.
- N=10: qty imbalance mean 0.7470, notional imbalance mean 0.7470, delta imbalance mean 0.0795, pressure edge mean 0.1630 bps.
- N=25: qty imbalance mean 0.6013, notional imbalance mean 0.6013, delta imbalance mean 0.0158, pressure edge mean 0.6667 bps.
- N=50: qty imbalance mean 0.2945, notional imbalance mean 0.2944, delta imbalance mean -0.0977, pressure edge mean 0.8078 bps.

## Conservative queue/fill caveats

- REST snapshots are not a lossless historical L2 stream; use websocket deltas with sequence-gap checks before live-like paper reporting.
- Microprice, top-N pressure, and imbalance columns are predictive features only, not executable fill prices.
- Do not assume fills at mid-price; conservative simulation should cross spread for taker fills or model maker queue priority, latency, cancels, and partial fills.
- Bybit recent-trade side is treated as aggressor/taker-side proxy here; confirm endpoint semantics against websocket trade docs before using as alpha.
- Orderbook delta imbalance compares sampled depth snapshots; it misses within-interval add/cancel/trade events and is sensitive to polling cadence.

## Bottom line

Dataset generated for feature diagnostics only; not a strategy and not ready for live orders.
Next step: feed this feature schema from a websocket collector that stores orderbook.50 deltas, best bid/ask, and public trades with strict sequence validation; only then evaluate signals with spread/queue/latency-aware paper fills.
