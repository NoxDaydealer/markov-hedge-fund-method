# Breiterer Coin-Sweep Plan

## Status Quo
- Nur **BTCUSDT** und **ETHUSDT** in `research/bybit_intraday_strategy_sprint/data/`
- Beide: 20,160 Bars (1m OHLCV), 2026-05-10 bis 2026-05-24
- Quellen: Bybit public REST `/v5/market/kline`, `category=linear`, 1m intervals

## Ziel
- **SOLUSDT, XRPUSDT, ADAUSDT, BNBUSDT, DOGEUSDT** als nächsten Symbols testen
- Gleiche Methodik: VWAP RSI Reversion + Breakout Strategies

## Benötigte Schritte

### 1. Datenbeschaffung
Bybit public endpoints (kein API-Key nötig):
```
GET https://api.bybit.com/v5/market/kline
  ?category=linear
  &symbol=SOLUSDT
  &interval=1
  &start=1746830400000  (2026-05-10)
  &end=1747262400000    (2026-05-24)
  &limit=20000
```

### 2. Datenformat
Erwartete Felder:
- `symbol`, `start_time`, `interval`, `open`, `high`, `low`, `close`, `volume`

### 3. Sweep durchführen
- Gleicher `vwap_volume_rsi_reversion` + `bb_vwap_momentum_breakout` Sweep
- Gleiche Train/Test Split (70/30)
- Neue Symbols zu `all_symbols_all_sweeps.csv` hinzufügen

### 4. Erwartete Herausforderungen
- Bybit rate limits: 100 req/s max, 6000 bars pro Anfrage
- 1 Anfrage pro Symbol nötig
- Volume/Spread kann stark variieren zwischen Symbols

### 5. Entscheidungspunkte
- Falls SOL/XRP bessere sharpe zeigt als ETH → Paper Portfolio anpassen
- Falls neue Symbols deutlich schlechter → erst Datenvalidierung machen
- Falls alle NO-GO → Markov-Gate verfeinern (L2 Orderbook-Features)

## Nächste konkrete Action
1. Daten-Collector Skript schreiben (`fetch_symbol.py`)
2. SOLUSDT Daten laden + ersten Sweep auf existierendem Framework
3. Ergebnisse mit ETH vergleichen

## Zeit-Schätzung
- Datenbeschaffung: 10-15 min (5 Symbols)
- Sweep pro Symbol: ~5 min (pandas, 288 combos)
- Total: ~40 min