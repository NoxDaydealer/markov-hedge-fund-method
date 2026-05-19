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

## Credit

- **Framework:** Roan ([@RohOnChain](https://x.com/RohOnChain)) — read his original article for the underlying maths.
- **Plugin + installer + animations:** [Lewis Jackson](https://www.youtube.com/@lewisjackson).

## License

MIT — see the umbrella [LICENSE](../LICENSE).
