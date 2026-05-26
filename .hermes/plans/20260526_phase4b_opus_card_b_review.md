# Opus Review — Card B Cost/Slippage

## Verdict
PASS_WITH_FIXES

## Critical Issues
- `test_cost_model_does_not_import_broker_or_network_libraries` ist strukturell wirkungslos: `trading_hub.costs` ist beim Test-Load bereits über die Top-Level-Imports in `tests/test_cost_model.py` in `sys.modules`. Der nachträglich gemonkeypatchte `importlib.import_module` greift dann nur noch beim Cache-Lookup, nicht bei den ursprünglichen transitive Imports. Der Test grünt unabhängig davon, was `costs.py` tatsächlich importiert — die Isolation wird nicht wirklich verifiziert.

## Suggested Fixes Before Next Card
- Den Broker-Import-Test durch einen statischen AST-Scan oder `ast.parse(Path("trading_hub/costs.py").read_text())` ersetzen, der nach `import`/`from ... import` für die `forbidden`-Liste sucht. Alternativ: in einem Subprozess mit leerer `sys.modules` importieren und `sys.modules.keys()` prüfen.
- Quadratisches Impact-Modell `(notional / ADV) ** 2` kurz kommentieren — die Literatur (Almgren-Chriss, Kissel-Glantz) nutzt häufiger Square-Root. Aktuell konservativer, aber als bewusste Research-Entscheidung dokumentieren.
- Validierungs-Trigger in `estimate_round_trip_cost_bps` schärfen: aktuell wirft `notional > 0` ohne ADV, auch wenn `impact_coefficient_bps == 0` (dann wäre `size_impact_bps` ohnehin 0). Bedingung auf `impact_coefficient_bps > 0.0` reduzieren oder ein expliziter Test für `notional > 0, coeff == 0`.
- Ein Test, der monotone Sensitivität auch in der ADV-Richtung prüft (größere ADV bei gleichem Notional → niedrigere Kosten), würde das Impact-Modell weiter absichern.

## Safety Check
- Paper-only: yes
- No network: yes
- No broker/order path: yes
- Input validation: yes
- Tests adequate: yes (mit Caveat zum Isolations-Test, s.o.)

## Next Card Recommendation
- Karte C — Ledger/Position-Tracking-Modul (reine In-Memory-Buchführung). Die `apply_cost_to_return`-API ist dafür der natürliche Andockpunkt; danach lässt sich Backtest-Integration sauber gegen Costs + Ledger schreiben.
