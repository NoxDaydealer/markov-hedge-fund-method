# Trading Hub Plan: High-Frequency/Paper-Trading Strategy Sprint

## Ziel

Die bisherige `combo_fib_liquidity`-Strategie ist für Antons Ziel ungeeignet: QQQ 5y daily erzeugte nur 1 Trade und ca. +0.2% Total Return. Wir wechseln daher von seltenen Daily-Signalen zu intraday/pseudo-HFT Paper-Trading mit höherer Signalfrequenz.

Wichtig: Das bleibt vorerst **Research + Paper-Trading only**. Keine Broker-Keys, keine echten Orders, keine Einkommensversprechen.

## Harte Entscheidung: Strategie zuerst

### Primärer Kandidat v0: Bybit Crypto Perps — VWAP + Volume + RSI/StochRSI Mean-Reversion

Warum zuerst:
- Höhere Frequenz als Daily/NASDAQ-Signale.
- Bybit liefert öffentliche 1m-Klines, Trades und L2-Orderbook ohne API-Key.
- BTCUSDT/ETHUSDT sind 24/7 liquide und einfacher zu testen als NASDAQ-Level-2.
- VWAP/Volume/RSI-Regeln sind klar testbar und Markov kann später zwischen Mean-Reversion und Trend-Modus umschalten.

Erste Märkte:
- `BTCUSDT` linear perp
- `ETHUSDT` linear perp
- optional später `SOLUSDT`

Zeitebenen:
- Signal-Timeframe: 1m und 5m testen
- Kontext-Timeframe: 15m/1h für Markov-Regime und Trendfilter

## Entry/Exit-Regeln v0 — VWAP Volume Reversion

### Long Entry v0
Alle Bedingungen:
1. Preis unter Intraday-/Session-VWAP oder Rolling-VWAP.
2. Abstand zu VWAP größer als Schwelle, z. B. `zscore(price_vs_vwap) <= -1.5`.
3. RSI(14) < 35 oder StochRSI < 0.2.
4. Volume Spike: aktuelles Volumen > 1.5x rolling median volume.
5. Reclaim/Bestätigung: Close wieder über vorheriges 1m-High oder grüne Umkehrkerze.
6. Spread/Liquiditätsfilter OK.
7. Markov erlaubt Mean-Reversion oder ist neutral.

### Short Entry v0
Nur im Paper-Test:
1. Preis über VWAP mit `zscore >= +1.5`.
2. RSI(14) > 65 oder StochRSI > 0.8.
3. Volume Spike.
4. Bearische Umkehrbestätigung.
5. Spread/Liquidität OK.
6. Markov erlaubt Short/Risk-Off.

### Exit v0
- Take Profit 1: Rückkehr zu VWAP oder 0.5–1.0 ATR.
- Stop: lokales Extrem ± ATR-Puffer.
- Time stop: nach 5–20 Kerzen raus, wenn kein Mean-Reversion-Effekt.
- Hard stop: wenn Spread weitet oder Markov-Regime kippt.
- Max Trades/Tag und Cooldown nach Verlusten.

## Zwei parallele Kandidaten

### Kandidat B: Bollinger Squeeze + VWAP Momentum Breakout

Einsatz:
- Wenn Markov Trend/Momentum-Regime erkennt.

Long Entry:
- Bollinger-Band-Breite unter unterem Perzentil, z. B. 20%.
- Breakout über Range/oberes Band.
- Preis über VWAP.
- Volumen > 1.5x rolling median.
- RSI > 50 oder MACD-Histogramm steigend.

Exit:
- ATR trailing stop.
- Exit bei VWAP-Cross zurück.
- Time stop, falls Breakout nicht weiterläuft.

### Kandidat C: Bybit L2 Orderbook Imbalance Scalping

Nicht als erste Strategie live testen, sondern zuerst als Daten-/Feature-Prototyp.

Features:
- Top-N Bid/Ask Imbalance, z. B. depth 50.
- Spread.
- Microprice.
- Trade aggressor flow aus publicTrade.
- Orderbook delta imbalance.

Entry-Idee:
- Long, wenn Bid-Imbalance stark positiv, aggressive Käufe zunehmen, Preis über Micro-VWAP.
- Exit sehr schnell: Imbalance kippt, kleiner TP, harter Time Stop.

Warnung:
- Paper-Fills bei L2/HFT sind schwierig wegen Queue-Position, Latenz und Fake Liquidity. Erst Daten sammeln, dann konservativ simulieren.

## Datenanforderungen

### Bybit Public Data — machbar ohne API-Key
- REST Snapshot: `/v5/market/orderbook`
- WebSocket public topics:
  - `orderbook.50.BTCUSDT`
  - `publicTrade.BTCUSDT`
  - `kline.1.BTCUSDT`
  - analog ETHUSDT
- Optional REST:
  - funding history
  - open interest
  - tickers

### Speicher v0
- Raw JSONL für WebSocket Events.
- Normalisierte Parquet/CSV für:
  - 1m OHLCV
  - trades
  - best bid/ask/spread
  - periodic orderbook snapshots

## Markov-Integration

Markov soll kein magischer Alpha-Generator sein, sondern Gate/Optimizer:

1. Regime-Features:
   - short-term returns
   - realized volatility
   - spread regime
   - volume regime
   - VWAP distance regime
   - optional orderbook imbalance regime

2. Regime-Aktionen:
   - Mean-reversion regime: VWAP reversion aktivieren.
   - Trend/momentum regime: Bollinger/VWAP breakout aktivieren.
   - High-volatility + wide-spread regime: Positionsgröße runter oder kein Trade.
   - Risk-off regime: Longs blocken, Shorts nur Paper.

3. Optimizer später:
   - Parameter pro Regime wählen, z. B. VWAP zscore Schwelle, RSI Threshold, ATR Stop, Time Stop.
   - Nur walk-forward, niemals auf finalem Testset optimieren.

## Evaluations- und Go/No-Go-Kriterien

Minimum, bevor irgendetwas ernst genommen wird:

- Mindestens 50–100 Trades im Backtest/Paper-Sample, sonst Aussage zu schwach.
- Gebühren + Spread + Slippage einbauen.
- Gegen Baselines testen:
  - no-trade
  - buy-and-hold
  - random entry gleiche Frequenz
  - naive VWAP-only
  - Strategie ohne Markov
  - Strategie mit Markov
- Walk-forward:
  - Train 30–60 Tage
  - Validation 7–14 Tage
  - Test 7–14 Tage
- Metriken:
  - Net PnL nach Kosten
  - EV pro Trade
  - Trades/Tag
  - Max Drawdown
  - Profit Factor
  - Sharpe/Sortino
  - Fee-to-Gross-Profit Ratio
  - Slippage Sensitivity
  - PnL nach Regime

Go nur wenn:
- Out-of-sample nach Kosten positiv.
- Markov-Version besser oder risikoärmer als No-Markov.
- Ergebnis über mehrere Zeitfenster stabil.
- Profit verschwindet nicht bei 2x Slippage.

No-Go wenn:
- Edge nur bei 0 Gebühren/0 Slippage existiert.
- Ein einzelner Trade erklärt den Gewinn.
- Parameter extrem instabil sind.
- Paper-Fills stark vom Backtest abweichen.

## Kanban-Roadmap

1. Build Bybit public market data collector.
2. Implement VWAP Volume Reversion v0 adapter/backtest.
3. Implement Bollinger VWAP Momentum v0 adapter/backtest.
4. Add Markov intraday regime gate for strategy selection.
5. Add costs/slippage/spread execution model.
6. Run parameter sweep + walk-forward on BTCUSDT/ETHUSDT.
7. Prototype L2 imbalance features after enough orderbook data is collected.
8. Start daily paper report only after a candidate passes basic backtests.

## Open Questions

- Welche Märkte bevorzugt Anton zuerst: Crypto Bybit Perps oder NASDAQ/QQQ Intraday?
- Akzeptiert Anton Paper-Shorts in Crypto? Real-money Shorts bleiben ausgeschlossen.
- Gewünschte Frequenz: 5–20 Trades/Tag oder 50–100+ Signale/Tag?
- Soll L2 direkt mitgeloggt werden, auch wenn die erste Strategie noch OHLCV-basiert ist? Empfehlung: Ja, parallel sammeln.
