# Crypto Trading Strategy Library
## Binance/Bybit Intraday Strategies (1m-15m Timeframes)

*Research Document — May 2026*

---

## Table of Contents
1. [Strategy Categories Overview](#1-strategy-categories-overview)
2. [Mean Reversion Strategies](#2-mean-reversion-strategies)
3. [Breakout Strategies](#3-breakout-strategies)
4. [Momentum Strategies](#4-momentum-strategies)
5. [Statistical Arbitrage Strategies](#5-statistical-arbitrage-strategies)
6. [Market Making Strategies](#6-market-making-strategies)
7. [Orderflow \& Advanced Techniques](#7-orderflow--advanced-techniques)
8. [Funding Rate Arbitrage](#8-funding-rate-arbitrage)
9. [Markov Trading Strategy](#9-markov-trading-strategy)
10. [Strategy Regime \& Asset Matrix](#10-strategy-regime--asset-matrix)
11. [Universal vs Asset-Specific Strategies](#11-universal-vs-asset-specific-strategies)

---

## 1. Strategy Categories Overview

| Category | Core Premise | Best Timeframes | Risk Profile |
|----------|--------------|-----------------|--------------|
| Mean Reversion | Price reverts to equilibrium | 1m–5m, 15m | Medium |
| Breakout | Price escapes range with momentum | 1m–15m | High |
| Momentum | Trend continuation in direction | 5m–15m | Medium-High |
| Statistical Arbitrage | Pricing inefficiency exploitation | 1m–5m | Low-Medium |
| Market Making | Spread capture via liquidity provision | 1m–1m | Low (requires speed) |

**Universal Strategies** (work across most crypto assets): VWAP reversion, RSI divergences, Bollinger Band squeeze, MACD crossivers, funding rate arbitrage  
**Asset-Specific Strategies**: Orderflow on high-cap only, footprint charts (liquid pairs), liquidity zone hunting (DEX-centric pairs)

---

## 2. Mean Reversion Strategies

### 2.1 RSI Divergence Mean Reversion

**Description**:  
Uses Relative Strength Index divergences to identify exhaustion points where price momentum contrasts with oscillator direction, signaling potential mean reversion.

**Best Market Conditions**:
- Ranging or slightly trending markets with clear boundaries
- Sideways price action with oscillating highs/lows
- NOT effective in strong trending markets with momentum continuation

**Typical Parameters**:
- RSI Period: 14 (standard), 7 (faster signals), 21 (smoother)
- Overbought threshold: 70 (sell), Oversold threshold: 30 (buy)
- Divergence lookback: 5–20 candles
- Timeframe: 5m–15m optimal; 1m possible with noise

**Strengths**:
- Works universally across crypto assets
- Clear entry/exit signals
- Works well in ranging markets (common in crypto sideway phases)
- Combines well with volume confirmation

**Weaknesses**:
- Generates false signals in strong trends
- Lagging indicator — late entries
- Requires filtering to avoid whipsaws
- RSI can stay overbought/oversold for extended periods in trends

**Market Regime**: Ranging, Low volatility  
**Assets**: Universal (BTC, ETH, altcoins with sufficient volume)  
**Timeframe**: 5m–15m preferred; 1m for scalping with filters

---

### 2.2 Bollinger Band Reversion

**Description**:  
Price touching or exceeding outer Bollinger bands signals potential reversion to the mean (middle band or moving average).

**Typical Parameters**:
- SMA Period: 20 (standard), 50 (slower)
- Standard Deviations: 2.0 (standard), 2.5 (wider tolerance)
- Band touch confirmation: close below lower band (buy), above upper band (sell)
- Timeframe: 5m–15m; 1m for aggressive scalping

**Strengths**:
- Visually clear trading zones
- Adapts to volatility dynamically
- Works across all liquid crypto pairs
- Band width indicates regime (squeeze = low volatility breakout setup)

**Weaknesses**:
- Late signals — bands lag price
- False bands touches during trending moves
- Requires volatility filter for trending markets
- Parameters need tuning per asset

**Market Regime**: Ranging, Calm volatility  
**Assets**: Universal for liquid pairs  
**Timeframe**: 5m–15m

---

### 2.3 VWAP Mean Reversion

**Description**:  
Uses Volume Weighted Average Price as the equilibrium line. Price reverts to VWAP after deviations, especially on intraday timeframes.

**Typical Parameters**:
- VWAP reset: Daily (standard for intraday)
- Standard deviation bands: ±1σ, ±2σ for entry zones
- Entry: Price reverts through VWAP with volume confirmation
- Timeframe: 1m–5m (high-frequency scalping)

**Strengths**:
- Incorporates volume reality, not just price
- Institution-focused reference point — widely watched
- Works well for high-volume crypto assets
- Day traders on Binance/Bybit heavily reference VWAP

**Weaknesses**:
- Less reliable on low-volume altcoins
- VWAP reset daily means overnight gaps can invalidate
- Requires real-time calculation — not all platforms provide
- Lagging on lower timeframes

**Market Regime**: Ranging, moderate volume  
**Assets**: High-volume BTC, ETH, and top-20 alts  
**Timeframe**: 1m–5m

---

### 2.4 VWAP Reversion with Anchored VWAP (AVWAP)

**Description**:  
Anchored VWAP from significant pivot points (swing highs/lows, news events) provides more relevant equilibrium lines than simple daily VWAP.

**Typical Parameters**:
- Anchor point selection: Most recent swing high/low
- Lookback: Last 50–100 candles or specific event timestamp
- Entry: Price reverts to AVWAP line with volume confirmation

**Strengths**:
- Contextually relevant — tied to actual price structure
- Works for specific catalyst events (news anchors)
- Highly effective in intraday crypto

**Weaknesses**:
- Subjective anchor selection creates variability
- Requires manual intervention or sophisticated automation
- More complex to backtest reliably

**Market Regime**: Ranging/Transient trends  
**Assets**: High-volume majors + event-driven trading  
**Timeframe**: 5m–15m

---

## 3. Breakout Strategies

### 3.1 Range Breakout (Consolidation Break)

**Description**:  
Identifies tight price consolidation (low volatility squeeze) and trades the directional breakout when price escapes the range with momentum.

**Typical Parameters**:
- Range definition: 10–20 candles of low volatility (ATR or Bollinger width)
- Breakout confirmation: Close above/below range boundary
- Volume requirement: 1.5–2x average volume on breakout
- Timeframe: 5m–15m

**Strengths**:
- High reward-to-risk when caught early
- Clear entry points with defined stops (below/above range)
- Works well in crypto's frequent consolidation-breakout cycles
- Universal applicability

**Weaknesses**:
- False breakouts common (50%+ failure rate without filters)
- Requires filter to distinguish true vs false breakouts
- Lagging confirmation (waiting for close beyond range)
- Ineffective in choppy markets

**Market Regime**: Low volatility → High volatility transition  
**Assets**: Universal with volume confirmation  
**Timeframe**: 5m–15m (1m possible with tight filters)

---

### 3.2 Bollinger Band Squeeze Breakout

**Description**:  
Bollinger Band width compresses to multi-period low ("squeeze"), then trades the directional expansion.

**Typical Parameters**:
- Squeeze detection: Band width < 20% of 100-period average width
- Entry: Close beyond squeeze boundary with momentum
- Stop: Below/above squeeze entry point
- Timeframe: 5m–15m

**Strengths**:
- Built-in volatility regime identification
- Combines range and momentum concepts
- Clear visual pattern recognition
- Works across crypto markets

**Weaknesses**:
- Squeeze can persist before expansion (dead time)
- Does not indicate direction — requires trend bias filter
- Multiple squeeze breakdowns possible

**Market Regime**: Calm → Volatile transition  
**Assets**: Universal  
**Timeframe**: 5m–15m

---

### 3.3 Support/Resistance Breakout

**Description**:  
Trades breaks of key horizontal levels (support/resistance) with volume confirmation.

**Typical Parameters**:
- Level identification: Price clustered at highs/lows (3+ touches)
- Break confirmation: Close beyond level + volume spike
- Retest entry: Wait for pullback to broken level (more conservative)
- Timeframe: 5m–15m (1m for aggressive plays)

**Strengths**:
- Natural support for stop placement
- Institutional relevance — levels widely watched
- Effective in crypto due to clear support clusters

**Weaknesses**:
- Subjective level identification
- Levels break and become invalid (change of character)
- May underperform in non-range-bound markets
- Requires human judgment for level selection

**Market Regime**: Ranging or regime change  
**Assets**: Universal but requires clear structure  
**Timeframe**: 5m–15m

---

## 4. Momentum Strategies

### 4.1 MACD Momentum

**Description**:  
Moving Average Convergence Divergence tracks momentum via crossovers and histogram changes, trading in the direction of momentum alignment.

**Typical Parameters**:
- Fast EMA: 12, Slow EMA: 26, Signal: 9 (standard)
- Crossover entry: MACD crosses above/below signal line
- Histogram: Bars changing direction with growth
- Timeframe: 5m–15m

**Strengths**:
- Clear momentum direction reading
- Works as trend filter + entry trigger
- Widely understood — easy to combine with discretionary analysis
- Effective on crypto timeframes

**Weaknesses**:
- Lagging — late entries in fast markets
- Flat MACD in choppy markets (whipsaw zone)
- Needs trend filter to avoid countertrend trades
- Histogram changes can be noise

**Market Regime**: Trending, Low-to-moderate volatility  
**Assets**: Universal  
**Timeframe**: 5m–15m

---

### 4.2 EMA Ribbon Trend Following

**Description**:  
Multiple EMAs (e.g., 9, 21, 50, 200) aligned in order create a "ribbon" indicating trend direction and strength.

**Typical Parameters**:
- EMAs: 8/21/50/200 or custom set
- Trend: All EMAs aligned (bullish = price above all, bearish = below all)
- Entry: Pullback to nearest EMA with ribbon confirmation
- Timeframe: 5m–15m for intraday

**Strengths**:
- Simple visual trend identification
- Dynamic support/resistance from EMA stack
- Works across all timeframes including crypto
- EMA alignment indicates institutional conviction

**Weaknesses**:
- Lagging — slower than price action
- Conflicting signals in EMA consolidation periods
- EMA spacing narrows in ranging markets
- May produce late entries on fast coins

**Market Regime**: Trending (any timeframe)  
**Assets**: Universal  
**Timeframe**: 5m–15m

---

### 4.3 Supertrend Momentum

**Description**:  
Supertrend indicator combines ATR volatility with closing price to generate trend-following signals with built-in stops.

**Typical Parameters**:
- ATR Period: 10 (standard)
- Multiplier: 3.0 (standard) — wider = fewer signals
- Entry: Close above/below Supertrend line
- Exit: Trend line flip

**Strengths**:
- Built-in trailing stop functionality
- Dynamic adjustment to volatility
- Simple, rules-based entry/exit
- Popular in crypto trading communities

**Weaknesses**:
- Lagging entries in fast trends
- False flips in choppy markets
- Needs ATR period tuning per asset
- May underperform on low-volatility assets

**Market Regime**: Trending, any volatility level  
**Assets**: Universal  
**Timeframe**: 5m–15m

---

## 5. Statistical Arbitrage Strategies

### 5.1 Pairs Trading (Statistical Arbitrage)

**Description**:  
Identifies two correlated assets whose price relationship diverges temporarily; expects reversion to mean. Trades long the underperforming asset and short the overperforming asset.

**Typical Parameters**:
- Correlation threshold: > 0.70 (Pearson or Spearman)
- Spread standard deviation: Entry when spread > 2σ, exit at < 0.5σ
- lookback: 20–50 candles for correlation calculation
- Timeframe: 1m–5m for high-frequency pairs

**Strengths**:
- Market-neutral (hedged directional risk)
- Works well in ranging markets
- Statistically grounded
- Effective on crypto correlated pairs (BTC/ETH, BTC/ETH alternatives)

**Weaknesses**:
- Requires sufficient correlation — many crypto pairs diverge structurally
- Spread can widen and stay divergent (structural break)
- Margin and borrow costs on Bybit/Binance futures affect profitability
- May require large capital for meaningful returns

**Market Regime**: Ranging, low volatility  
**Assets**: Correlated pairs (BTC/ETH, ETH/ALT, exchange-tracked instruments)  
**Timeframe**: 1m–5m

---

### 5.2 Mean Reversion with Z-Score

**Description**:  
Calculates Z-score of price deviation from moving average; enters at extreme Z-scores expecting reversion.

**Typical Parameters**:
- Lookback: 20 candles (standard)
- Entry threshold: Z > 2.0 (overbought), Z < -2.0 (oversold)
- Exit: Z returns to 0
- Timeframe: 1m–5m

**Strengths**:
- Objective, rules-based entry
- Normalizes across assets (comparable Z-scores)
- Works on any mean-reverting asset

**Weaknesses**:
- Does not account for structural trend changes
- Crypto assets often have non-stationary mean
- Z-score can remain extreme in strong trends
- Requires lookback optimization per asset

**Market Regime**: Ranging, mean-reverting behavior  
**Assets**: Universal  
**Timeframe**: 1m–5m

---

## 6. Market Making Strategies

### 6.1 Grid Trading (Automated Market Making)

**Description**:  
Places buy orders at regular price intervals below a reference price and sell orders above, profiting from mean reversion in ranging markets.

**Typical Parameters**:
- Grid spacing: Price increments (e.g., 0.1%, 0.5%, 1% per level)
- Number of grids: 5–20 levels
- Base price: VWAP, spot price, or set manually
- Capital allocation: Equal per grid level

**Strengths**:
- Automated, rules-based execution
- Profitable in ranging markets
- Reduces emotional decision-making
- Popular on Binance/Bybit with API availability

**Weaknesses**:
- One-directional market move causes accumulated positions
- Requires significant capital for multiple grids
- Losses accumulate in strong trends
- Fees can erode profitability on low-margin grids

**Market Regime**: Ranging, low volatility  
**Assets**: High-volume pairs with clear ranges  
**Timeframe**: 1m–15m

---

## 7. Orderflow & Advanced Techniques

### 7.1 Order Book Imbalance (OBI)

**Description**:  
Analyzes the bid/ask depth at multiple levels to identify when one side is exhausted, signaling potential reversal or continuation.

**Typical Parameters**:
- Depth levels: Top 5–10 order book levels
- Imbalance ratio: Bid volume / Ask volume threshold (e.g., > 2.0 or < 0.5)
- Timeframe: 1m (high-frequency observation)
- Exchange: Binance, Bybit (depth data accessible via API)

**Strengths**:
- Direct insight into supply/demand dynamics
- Early signal before price movement
- Works on any exchange with transparent order book

**Weaknesses**:
- Data refresh latency (orders can be canceled quickly)
- Spoofing can create false signals
- Requires real-time data access

**Market Regime**: Any (especially volatile transitions)  
**Assets**: High-volume liquid pairs  
**Timeframe**: 1m

---

### 7.2 Liquidity Zones / Smart Money

**Description**:  
Identifies areas where stop orders cluster (stop hunting zones) and institutional order flow likely resides, trading the "grab" of liquidity.

**Typical Parameters**:
- Zone identification: Areas of recent highs/lows, range boundaries, round numbers
- Liquidity grab: Price sweeps zone, reverses
- Entry: Confirmation candle after liquidity grab
- Timeframe: 5m–15m

**Strengths**:
- Based on observable market behavior
- Explains common price patterns (wicks beyond levels)
- Works with price action analysis

**Weaknesses**:
- Subjective zone identification
- Cannot verify actual stop order locations
- Requires experience for reliable identification

**Market Regime**: Volatile, trending reversals  
**Assets**: Universal (higher reliability on liquid pairs)  
**Timeframe**: 5m–15m

---

## 8. Funding Rate Arbitrage

### 8.1 Cross-Exchange Funding Rate Arbitrage

**Description**:  
Exploits differences in funding rates between exchanges (e.g., Binance vs Bybit perpetual futures) by going long on the lower-fee exchange and short on the higher-fee exchange.

**Typical Parameters**:
- Rate differential threshold: > 0.05% (net after fees)
- Rebalancing frequency: Per funding settlement (every 8 hours on Bybit)
- Position sizing: Based on available capital and margin requirements

**Strengths**:
- Generates consistent returns in ranging markets
- Hedged position reduces directional risk
- Captures structural inefficiency in crypto derivatives markets
- Well-documented in crypto quant literature

**Weaknesses**:
- Requires accounts on multiple exchanges
- Margin and liquidation risk remains
- Funding rates change dynamically (can reverse)
- Requires significant capital for meaningful returns
- Exchange risk (counterparty, withdrawal delays)

**Market Regime**: Ranging, stable funding rates  
**Assets**: BTC, ETH perpetuals on Binance/Bybit  
**Timeframe**: 8h holding (funding settlement intervals)

---

### 8.2 Funding Rate Prediction

**Description**:  
ML-based prediction of funding rates to front-run rate changes, positioning before rate shifts.

**Typical Parameters**:
- Features: Historical funding, open interest, price momentum, exchange flow data
- Model: LightGBM, Random Forest, or LSTM
- Target: Next period funding rate
- Timeframe: 8h forecast horizon

**Strengths**:
- Can generate alpha beyond static arbitrage
- Works with standard exchange APIs
- Can combine with regime detection

**Weaknesses**:
- Funding rates are partially deterministic (pegged to time)
- Model complexity requires ongoing maintenance
- Less relevant for retail traders

**Market Regime**: High volatility, changing funding  
**Assets**: BTC, ETH, high-funding altcoins  
**Timeframe**: 8h forecast

---

## 9. Markov Trading Strategy

### What is a "Markov" Trading Strategy?

In the academic and quantitative finance literature, "Markov trading strategy" refers to one of two concepts:

#### A. Markov State-Based Trading (Hidden Markov Models / HMM)

Uses Hidden Markov Models (HMM) or Markov Switching Dynamic Regression (MSDR) to detect latent market regimes and allocate to strategies accordingly.

**How It Works**:
1. Calibrate HMM on historical returns/volatility
2. Identify current regime (e.g., trending up, ranging, high vol)
3. Allocate to strategy types suited for detected regime
4. Switch strategy allocation as regime changes

**Example Allocation**:
- Trending regime → Momentum strategies
- Ranging regime → Mean reversion strategies
- High volatility → Volatility-targeting, reduced exposure

**Regime Definitions (Example 3-State Model)**:
- **State 0: Bear/Ranging** — Mean reversion performs well
- **State 1: Bull/Trending** — Momentum strategies perform well
- **State 2: High Volatility** — Reduced position size, volatility-targeting

**Strategy Selector Logic**:
```
If regime == "Bear/Ranging":
    Use RSI divergence, Bollinger reversion, VWAP reversion
Elif regime == "Bull/Trending":
    Use MACD crossover, EMA ribbon, Supertrend
Else:  # High volatility
    Reduce position size, use wider stops
```

**Strengths**:
- Adaptively switches strategies based on detected market conditions
- Reduces drawdown by avoiding mismatched strategies

**Weaknesses**:
- Regime detection is backward-looking
- Model may misclassify current regime
- Requires ongoing recalibration

#### B. Reinforcement Learning / MDP Formulation

Some literature refers to "Markov trading strategy" in the context of reinforcement learning where trading is formulated as an MDP:
- **State**: Market features (price, volume, indicators)
- **Action**: Buy, sell, hold
- **Reward**: Profit/loss
- **Transition**: Market state transitions governed by Markov dynamics

---

## 10. Strategy Regime & Asset Matrix

| Strategy | Ranging | Trending | High Vol | BTC | ETH | Alts | Timeframe |
|----------|---------|----------|----------|-----|-----|------|----------|
| RSI Divergence | ★★★★★ | ★★☆☆☆ | ★★☆☆☆ | ✓ | ✓ | ✓ | 5m–15m |
| Bollinger Reversion | ★★★★★ | ★★☆☆☆ | ★★☆☆☆ | ✓ | ✓ | ✓ | 5m–15m |
| VWAP Reversion | ★★★★☆ | ★★☆☆☆ | ★★☆☆☆ | ✓ | ✓ | ~ | 1m–5m |
| Range Breakout | ★★★☆☆ | ★★★★☆ | ★★★★☆ | ✓ | ✓ | ✓ | 5m–15m |
| MACD Momentum | ★★☆☆☆ | ★★★★★ | ★★★☆☆ | ✓ | ✓ | ✓ | 5m–15m |
| EMA Ribbon | ★★☆☆☆ | ★★★★★ | ★★★☆☆ | ✓ | ✓ | ✓ | 5m–15m |
| Supertrend | ★★☆☆☆ | ★★★★☆ | ★★★★☆ | ✓ | ✓ | ✓ | 5m–15m |
| ADX Filter | ★☆☆☆☆ | ★★★★★ | ★★★☆☆ | ✓ | ✓ | ✓ | 5m–15m |
| Pairs Trading | ★★★★★ | ★★☆☆☆ | ★★☆☆☆ | ✓ | ✓ | ~ | 1m–5m |
| Z-Score Reversion | ★★★★☆ | ★★☆☆☆ | ★★☆☆☆ | ✓ | ✓ | ✓ | 1m–5m |
| Grid Trading | ★★★★★ | ★☆☆☆☆ | ★★☆☆☆ | ✓ | ✓ | ✓ | 1m–15m |
| Order Book OBI | ★★★☆☆ | ★★★☆☆ | ★★★★☆ | ✓ | ✓ | ~ | 1m |
| Liquidity Zones | ★★★☆☆ | ★★★★☆ | ★★★★☆ | ✓ | ✓ | ✓ | 5m–15m |
| Funding Arb | ★★★★★ | ★☆☆☆☆ | ★★☆☆☆ | ✓ | ✓ | ~ | 8h |
| Markov HMM Regime | ★★★★★ | ★★★★★ | ★★★★★ | ✓ | ✓ | ✓ | 5m–15m |

---

## 11. Universal vs Asset-Specific Strategies

### Universal Strategies (Work Across Most Crypto Assets)

1. **RSI Divergence** — Works on any liquid asset with sufficient volume
2. **Bollinger Band Reversion** — Adapts to volatility, universal applicability
3. **MACD Momentum** — Standard indicator across all markets
4. **EMA Ribbon** — Trend identification works universally
5. **Supertrend** — Simple trend-following, universal
6. **Support/Resistance Breakout** — Price structure exists on all assets
7. **Range Breakout** — Consolidation patterns universal
8. **Z-Score Mean Reversion** — Statistical approach universal
9. **Grid Trading** — Mechanical approach universal
10. **Markov HMM Regime** — Regime detection can apply to any liquid asset

### Asset-Specific Strategies

1. **VWAP Reversion** — Less reliable on low-volume altcoins
2. **Pairs Trading** — Requires correlated assets (e.g., BTC/ETH)
3. **Funding Rate Arbitrage** — Requires access to Bybit/Binance perpetual differential

---

## Strategy Combination Ideas

1. **Regime Detection + Strategy Selection (Markov Core)**
   - HMM detects regime → selects appropriate strategy type

2. **Trend Filter + Momentum Entry**
   - ADX > 25 filter + MACD crossover for momentum entries

3. **Range Detection + Breakout Entry**
   - Bollinger squeeze detection + breakout confirmation

4. **Volume Confirmation + Mean Reversion**
   - Volume spike confirmation + VWAP reversion entry

5. **Statistical + Technical Confluence**
   - Z-score > 2.0 + RSI oversold + Bollinger lower band touch

---

## References & Further Reading

- **"Hands-On AI Trading with Python, QuantConnect, and AWS"** (Pik/Chan/Broad/Sun/Singh, 2025) — HMM regime models, stat arb, strategy lifecycle
- **"Python for Algorithmic Trading"** (Strimpel) — Intraday strategy implementation
- Binance/Bybit API documentation for order book, funding rate data
- hmmlearn, statsmodels for Hidden Markov Model implementation

---

*Document compiled: May 2026*  
*Strategy research for Binance/Bybit intraday trading (1m–15m timeframes)*  
*Regime-adaptive approach with Markov state detection*