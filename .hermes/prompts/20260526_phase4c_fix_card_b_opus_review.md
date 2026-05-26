Du bist Kanban Coder. Implementiere NUR die kleinen Fixes aus dem Opus-Review zu Card B. Keine neue Card, kein Ledger, kein Backtest, keine Strategie.

Kontext:
- Original Card B: t_b7192275
- Review-Datei:
  /root/trading/markov-strategy/.hermes/plans/20260526_phase4b_opus_card_b_review.md
- Geänderte Dateien aus Card B:
  - /root/trading/markov-strategy/trading_hub/costs.py
  - /root/trading/markov-strategy/tests/test_cost_model.py

Aufgabe:
1. Lies die Review-Datei.
2. Implementiere nur die Suggested Fixes Before Next Card, soweit klein und lokal:
   - Ersetze den unwirksamen Broker-/Network-Import-Test durch einen statischen AST-Scan oder äquivalent robuste Prüfung.
   - Dokumentiere kurz bewusstes quadratisches Impact-Modell in costs.py.
   - Schärfe die ADV-Validierung: ADV nur erforderlich, wenn impact_coefficient_bps > 0 und size-based impact tatsächlich berechnet wird. Falls notional > 0 aber coeff == 0, soll kein ADV nötig sein.
   - Ergänze Tests für diesen Fall und für ADV-Monotonie, falls klein.
3. Führe aus:
   uv run python -m pytest tests/test_cost_model.py -q
   uv run python -m pytest tests -q
4. Blocke mit review-required und kurzer Handoff-Zusammenfassung.

Absolute Stop Rules:
- Keine Dateien außer trading_hub/costs.py und tests/test_cost_model.py ändern.
- Keine neue Funktionalität außerhalb Card B.
- Kein Netzwerk, kein Broker, keine Orders.
- Keine nächste Card starten.
