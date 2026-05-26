# Markov Hedge Fund Method

Skill from **video 1 of the Quant Series**: *How To Use The Hedge Fund Method To Win Every Single Trade*.

Framework by **Roan** ([@RohOnChain](https://x.com/RohOnChain)) — I'm the guy installing it on camera.

---

## Install (the headline path — two commands)

In Claude Code:

```
/plugin marketplace add jackson-video-resources/markov-hedge-fund-method
/plugin install markov-hedge-fund-method@markov-hedge-fund-method
```

That's it. The skill is now installed. Invoke it any time, on any asset:

```
/markov-hedge-fund-method:regime
```

…or just ask in plain English: *"detect the regime on BTC-USD"*,
*"add a regime confirmation filter to my SPY momentum strategy"*,
*"what's the long-run regime mix of AAPL — is it too tail-heavy to trade?"*
Claude fires the `regime` skill automatically.

No API keys. No accounts. No `sudo`. Dependencies are resolved on first run by
`uv` (PEP 723 inline metadata) — nothing to pip-install yourself.

---

## What the skill does

It answers one question for **any asset**: what regime are we in, how sticky is
it, and what does that imply for risk and direction?

- Labels every day Bull / Bear / Sideways via a rolling-return rule (default 20-day, ±5%)
- Builds a 3×3 transition matrix from the asset's history (maximum-likelihood)
- Forecasts n-steps ahead by raising the matrix to powers (Chapman-Kolmogorov)
- Computes the long-run stationary distribution (baseline regime mix)
- Emits a signed signal: `bull_prob − bear_prob` → direction + conviction
- Runs a walk-forward backtest (no lookahead) → reports Sharpe + max drawdown
- Optionally fits a Hidden Markov Model via `hmmlearn` (graceful degrade if it can't compile)

It takes **either a ticker** (`--ticker BTC-USD`, fetched via `yfinance`) **or
your own CSV** (`--csv my_prices.csv`, just a date + close column) — so it drops
into whatever data pipeline you already run, on whatever asset you trade.

It's built to **compose**: slot it into a trading agent you already have as a
confirmation layer, a standalone signal, or a tail-risk filter — without
rewriting your strategy. See [`skills/regime/SKILL.md`](./skills/regime/SKILL.md)
for the JSON contract and three worked composition patterns.

---

## The on-camera build / zero-trust manual path

[`markov-hedge-fund-method.md`](./markov-hedge-fund-method.md) is the original
one-shot onboarding prompt — the version built **live on camera**. Paste it
into Claude Code (agent mode) and it builds the whole skill from scratch in
front of you: detects your OS, installs `uv`, writes every file, runs the
sanity check.

It's kept here as the **zero-trust path**: if you don't want to install a
plugin from a marketplace, this builds the identical logic locally so you can
read every line as it's written. Most people should use the two-command plugin
install above — this is the transparent fallback and the on-camera artifact.

---

## Pine Script bonus

[`pine-script/markov-hedge-fund-method.pine`](./pine-script/markov-hedge-fund-method.pine)
— TradingView v5 indicator that paints the framework live on a chart: regime
ribbon, live 3×3 transition matrix in the corner, stationary-distribution
table, current-regime banner. Inputs: lookback window (default 20), Bull/Bear
thresholds (default ±5%), table toggles.

Open TradingView → Pine Editor → paste the `.pine` → Save → Add to Chart.

---

## Markov Paper Trading Hub adapter

This repo also includes the first paper-only strategy adapter:
`trading_hub.strategies.combo_fib_liquidity.ComboFibLiquidityAdapter`.
It accepts caller-supplied OHLCV `pandas.DataFrame` data or a CSV path and
returns local paper signals only — no broker/API keys, live orders, or market-data
network fetches.

```python
from trading_hub.strategies.combo_fib_liquidity import ComboFibLiquidityAdapter

signals = ComboFibLiquidityAdapter(
    lookback=20,
    atr_period=14,
    markov_signal=0.25,   # longs allowed for positive/neutral regime risk
    enable_shorts=False,  # shorts are disabled by default
).generate_signals("./ohlcv.csv")
```

Signals are generated on the setup bar and shifted into `execution_signal` on
the next bar at the next bar open to avoid same-bar lookahead.

### Bollinger VWAP Momentum v0

The intraday Bollinger/VWAP momentum candidate lives at
`trading_hub.strategies.bollinger_vwap_momentum.BollingerVwapMomentumAdapter`.
It is also pure local/paper-only: caller-supplied OHLCV `DataFrame` or CSV in,
next-bar execution intents out; no broker orders and no implicit market-data
network calls.

Entry requires a recent low Bollinger band-width percentile squeeze followed by
band expansion and close breakout, price aligned with VWAP, volume expansion,
and RSI/MACD momentum confirmation. The companion backtest exits with ATR
trailing stop, VWAP recross, max holding-bars time stop, or end-of-data, and has
fee/spread/slippage bps hooks.

```python
from trading_hub.strategies.bollinger_vwap_momentum import BollingerVwapMomentumAdapter

signals = BollingerVwapMomentumAdapter(
    bb_period=20,
    bandwidth_percentile_window=100,
    bandwidth_percentile_threshold=0.20,
    volume_multiplier=1.5,
    enable_shorts=False,
).generate_signals("./intraday_ohlcv.csv")
```

```bash
python -m trading_hub.backtest_report \
  --strategy bollinger_vwap_momentum \
  --csv ./intraday_ohlcv.csv \
  --bb-period 20 \
  --bandwidth-percentile-window 100 \
  --fee-bps 2 --spread-bps 1 --slippage-bps 1 \
  --output-json ./bollinger_vwap_momentum_report.json
```

### Paper backtest/report runner

Run a local, paper-only report from OHLCV CSV data:

```bash
python -m trading_hub.backtest_report \
  --csv ./ohlcv.csv \
  --lookback 20 \
  --atr-period 14 \
  --markov-signal 0.25 \
  --output-json ./combo_fib_liquidity_report.json
```

The runner computes returns only after the adapter's shifted `execution_signal`:
entry at the execution bar open, exit at the following bar open. A final-bar
execution is ignored because its next-bar return is not knowable without
lookahead. The report includes trades, win rate, total/annualized return,
Sharpe, max drawdown, and average trade return.

### Shared HFT evaluator

For intraday/pseudo-HFT strategy research, use `trading_hub.hft_evaluator`.
It adds a broker-free, paper-only evaluation layer with maker/taker fees,
spread, slippage, latency bars, max-trades/day throttles, cooldowns,
train/validation/test walk-forward folds, no-trade/buy-hold/random/VWAP
baselines, and metrics such as net PnL, EV/trade, trades/day, profit factor,
max drawdown, fee-to-gross-profit, and PnL by regime. See
[`research/hft_evaluation_framework.md`](./research/hft_evaluation_framework.md)
for usage notes.

Optional yfinance fetching is available only when explicitly requested:

```bash
python -m trading_hub.backtest_report --ticker SPY --period 1y --interval 1d
```

Install the optional dependency first if needed: `pip install .[yfinance]`.
Unit tests use local fixture data and do not make network calls.

### Bybit public market data collector

The Trading Hub also includes a research-only Bybit public data collector. It
uses no API keys and subscribes to the linear public WebSocket topics
`publicTrade`, `kline.1`, and `orderbook.50` for BTCUSDT/ETHUSDT by default.
Orderbook sequence gaps trigger a public REST `/v5/market/orderbook` snapshot
resync.

```bash
python -m trading_hub.bybit_public_collector --data-dir ./data/bybit_public
# or after installing the package:
bybit-public-collector --data-dir ./data/bybit_public --symbol BTCUSDT --symbol ETHUSDT
```

Output layout:

- `raw/<SYMBOL>.jsonl` — unmodified WebSocket events plus REST resync snapshots.
- `normalized/trades/<SYMBOL>.jsonl` — public trades.
- `normalized/ohlcv_1m/<SYMBOL>.jsonl` — 1-minute OHLCV klines.
- `normalized/best_bid_ask_spread/<SYMBOL>.jsonl` — best bid/ask and spread bps.

---

## Credit

- **Framework:** Roan ([@RohOnChain](https://x.com/RohOnChain)) — read his original article for the underlying maths.
- **Plugin + installer + animations:** [Lewis Jackson](https://www.youtube.com/@lewisjackson).

## License

MIT — see the umbrella [LICENSE](../LICENSE).
