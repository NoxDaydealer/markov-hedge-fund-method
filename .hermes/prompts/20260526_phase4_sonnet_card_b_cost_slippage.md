Du bist Claude Code Sonnet im Implementierungsmodus. Arbeite nach Claude Code Superpowers: klein, testgetrieben, verifizieren vor Abschluss.

Aufgabe: Implementiere NUR Karte B — isoliertes Cost/Slippage-Modell für Trading Hub Paper-Trading.

Kontext / Stand:
- Karte A PIT-Datenpipeline ist abgeschlossen.
- Neue/aktuelle Dateien aus Karte A:
  - trading_hub/data/__init__.py
  - trading_hub/data/validators.py
  - trading_hub/data/pit_store.py
  - tests/test_pit_data_pipeline.py
- Tests zuletzt: 20/20 neue PIT-Tests grün, bestehende Suite 81/81 grün.
- Karte B soll bewusst unabhängig von Ledger, VirtualAccount, Mark-to-Market, Strategie, Backtest und Discord bleiben.

Bitte zuerst lesen:
1. /root/trading/markov-strategy/.hermes/plans/20260526_phase1_books_to_paper_trading_plan.md falls vorhanden.
2. /root/trading/markov-strategy/.hermes/plans/20260526_phase2_opus_plan_review.md falls vorhanden.
3. tests/test_pit_data_pipeline.py nur als Stil-/Testmuster.
4. pyproject.toml.

Nicht lesen / nicht anfassen:
- Keine full_text.md Buchdateien.
- Keine Exchange-/Broker-Codepfade.
- Keine Secrets / .env / Auth-Dateien.
- Keine Discord-/Telegram-Anbindung.
- Keine weitere Card.

Ziel für Karte B:
Erstelle ein kleines, reines Cost/Slippage-Modul, vermutlich:
- trading_hub/costs.py ODER trading_hub/cost_model.py — wähle den Namen passend zur Projektstruktur, aber halte es klein.
- tests/test_cost_model.py

Gewünschte Public API, falls nicht durch bestehenden Code anders nahegelegt:
1. estimate_round_trip_cost_bps(...)
   - reine Funktion.
   - Parameter z.B. fee_bps, spread_bps, slippage_bps, impact_bps oder impact_coeff/notional/volume.
   - Gibt Roundtrip-Kosten in bps zurück.
   - Long/short-neutral, keine Strategieabhängigkeit.

2. apply_cost_to_return(...)
   - reine Funktion.
   - Brutto-Return minus Kosten.
   - Keine Annahme über echte Trades/Orders.

3. build_slippage_sensitivity_matrix(...)
   - reine Funktion.
   - Inputs: Basis-Kostenparameter + Multiplikatoren z.B. [0.5, 1, 2, 5].
   - Output: pandas DataFrame oder einfache Liste/Dict; wähle wartbar und testbar.
   - Muss klar zeigen: höhere Slippage => höhere Kosten / niedrigere Netto-Rendite.

Akzeptanzkriterien:
- Alles ist deterministic und offline.
- Kein Netzwerk.
- Kein yfinance/ccxt/ibapi/import von Broker-Libs.
- Keine Orders, keine Live-Ausführung, keine Side Effects.
- Eingabevalidierung: negative Kosten oder ungültige Multiplikatoren werfen klare ValueError.
- Tests decken mindestens ab:
  - Basis-Roundtrip-Kosten.
  - Fee + Spread + Slippage addieren sich erwartbar.
  - Impact-Komponente steigt mit Größe oder Parameter.
  - apply_cost_to_return reduziert Return korrekt.
  - Sensitivitätsmatrix ist monoton: höhere Slippage-Multiplikatoren erhöhen Kosten und senken Netto-Return.
  - Negative Inputs werden abgelehnt.
  - Kein Netzwerk/Broker-Import nötig.
- Neue Tests gezielt ausführen, dann nach Möglichkeit volle Suite.

Arbeitsweise:
1. Schreibe zuerst einen Mini-Plan mit konkreten Dateien und Funktionen.
2. Schreibe Tests zuerst oder parallel.
3. Implementiere minimal.
4. Führe gezielte Tests aus, z.B.:
   python -m pytest tests/test_cost_model.py -q
5. Führe danach, wenn möglich, volle Suite aus:
   python -m pytest tests -q
6. Abschlussbericht kurz und exakt:
   - geänderte/neue Dateien
   - Tests + Ergebnis
   - Public API
   - bewusst NICHT gebaut
   - nächste empfohlene Card

Absolute Stop Rule:
- Implementiere exakt diese eine Card B.
- Keine Card C.
- Kein Ledger, kein VirtualAccount, kein Backtest, keine Strategie, kein Reporting, kein Discord.
- Keine Zusatzverbesserungen außerhalb der Card.
- Wenn du merkst, dass die Card größer wird: stoppen und kleinere Teil-Card vorschlagen.
