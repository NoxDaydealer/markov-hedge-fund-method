# Universelle Strategie Analyse — Warum ETH und nicht BTC?

## Kernbefund: Trade-Level Analyse

| | BTCUSDT | ETHUSDT |
|---|---|---|
| **Gross/trade (vor Fees)** | **-0.0003%** ❌ | **+0.0156%** ✅ |
| Win Rate | 21.3% | 33.3% |
| Avg Win | 0.19% | 0.25% |
| Avg Loss | 0.05% | 0.10% |
| Trades gestoppt | **79%** | 60% |
| R/R Ratio | 3.66x | 2.45x |
| Breakeven Fee | **-3.5bps** | **+155.9bps** |

**Kritische Interpretation:**
- BTC verliert GELD VOR Gebühren — das Signal ist fundamental broken
- ETH verdient +0.0156% pro Trade VOR Gebühren — kann sich 156bps leisten
- BTC's 79% Stop-Rate = "Signal wird gestoppt bevor Mean Reversion eintritt"
- Selbst 3.66x R/R kann 21% Win Rate nicht kompensieren

## Warum BTC's Mean Reversion nicht funktioniert

### Analyse der Trade-Exit Gründe
- BTC: 48 von 61 Trades (79%) werden GESTOPPT
- ETH: 29 von 48 Trades (60%) werden gestoppt

BTC's Mean Reversion Signale werden zu schnell gestoppt — die Reversion kommt nicht schnell genug.

### Mögliche Ursachen

**1. BTC's "Mean Reversion" existiert — aber mit anderem Profil:**
- Nach RSI<30: BTC +0.0017% (POSITIVE next-bar return) ← Signal FUNKTIONIERT
- Aber: Dieses positive Return ist zu klein und noisig für profitable Trades
- Der Vorteil wird durch die 1-bar Verzögerung der Strategie eliminiert

**2. Volatility-Adjusted Return:**
- BTC ret_std = 4.52bps/Bar, ETH ret_std = 6.19bps/Bar
- ETH ist 37% volatiler → grössere potenzielle Moves → mehr P&L pro Trade
- BTC's Avg Win (0.19%) ist zu klein um nach Fee-Verlust noch profitabel zu sein

**3. Asset-spezifische Microstructure:**
- ETH's höheres Volume → VWAP ist stabiler, weniger noise
- BTC's VWAP ist noisier bei dünnen Zeiträumen → falsche Signale
- ETH's breiterer Spread (0.067% vs 0.050%) ist proportional billiger wegen Volumen

## Lösungsansätze (getestet)

### Getestet und gescheitert auf BTC:
- Tieferer z_threshold (0.5 statt 2.0) → keine Verbesserung
- Tighter ATR Stop (0.4 statt 0.8) → mehr Verluste (17.7% Win Rate)
- Verschiedene RSI-Schwellen (20-35) → keine positive Gross-Performance
- Kurze z_window (60, 120) → 0 trades oder 9% Win Rate

### Vielversprechend aber nicht ausreichend:
- Tight Stop + tiefer zthr: gross=+0.0139% aber Win Rate=17.7% → nach Fees noch negativ

## Universelle Strategie Empfehlung

### Ansatz A: Asset-Kategorisierung (pragmatisch)
NICHT versuchen, eine universell funktionierende Strategie zu finden. Stattdessen:
- **Kategorie A (High-Volume, hohe Volatilität):** ETHUSDT, SOL, etc. → Mean Reversion
- **Kategorie B (Low-Volume, niedrige Volatilität):** BTC, BNB → Breakout oder ausschliessen
- **Kategorie C (Neue Assets):** Erst validieren bevor Handeln

### Ansatz B: Percentile-basierte Signale (universell adaptiv)
```python
# Statt fixer Schwellen:
if rsi < rsi.rolling(200).quantile(0.20)  # Adaptive Schwelle
if dist > dist.rolling(200).std() * 2.0   # Adaptive Distanz
```
Passt sich automatisch an Volatilitätsregime an — auf BTC wären die Schwellen tiefer als auf ETH.

### Ansatz C: Volatility-normalisierte Position Sizing
```python
position_size = base_size * (eth_vol / btc_vol)  # BTC bekommt 1.37x grössere Position
```
Kompensiert die niedrigere BTC-Volatilität — ABER: hilft nicht wenn das Signal fundamental broken ist.

### Ansatz D: Regime-Hybrid (universell)
- Ranging (ADX<20): Mean Reversion
- Trending (ADX>25): Breakout/Momentum
Auf BTC: Wenn ADX zeigt dass es trending ist → breakout statt reversion.

## Empfohlene Implementierung

```
UniversalStrategy:
  1. Asset Screener:
     - Nur Assets mit Volume > Percentile(40) im Rolling-50-Bars Window
     - Nur Assets mit ret_std > 3bps (per bar)
  
  2. Regime Detection:
     - ADX < 20: Ranging → Mean Reversion mit Percentile-RSI
     - ADX > 25: Trending → Breakout
  
  3. Entry (Mean Reversion):
     - rsi < Percentile(20)
     - dist > Percentile(80)  
     - Volume > Percentile(50)
     - z_norm > 2.0 (volatility-normalisiert)
  
  4. Position Sizing:
     - Kelly Criterion mit max 10% Exposure
     - Volatility-normalisiert (hohe Vol = kleine Position)
  
  5. Exit:
     - VWAP Cross
     - ATR-trailing (für trending regime)
```

## Nächste konkrete Schritte

1. **Market-Width Filter**: Nur handeln wenn ETH und BTC gleichzeitig im Oversold sind (stärkeres Signal)
2. **ADX-basierter Regime-Hybrid** auf BTC testen: Mean Reversion + Breakout je nach Trendstärke
3. **Percentile-RSI Sweep** auf BTC: Adaptive Schwellen statt fixer Werte
4. **Breakout-Strategie** auf BTC mit angepassten Parametern (bb_window, ATR stop)

## Sprache: Deutsch