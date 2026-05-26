Du bist Claude Code im Kanban-Setup-Modus. Aufgabe: Lege NUR eine Kanban-Karte für Karte B an. NICHT implementieren.

Kontext:
- Karte A PIT-Datenpipeline ist abgeschlossen.
- Es gibt eine alte, breitere Kanban-Karte t_67048522 ("transaction costs, slippage, and turnover"), aber die ist scheduled, abhängig von altem Parent und zu breit/zu backtest-nah.
- Jetzt soll eine neue, kleine, isolierte Karte B angelegt werden: Cost/Slippage-Modell als reine Funktionen, ohne Ledger/Backtest/Strategie.
- Der Implementierungsprompt existiert hier:
  /root/trading/markov-strategy/.hermes/prompts/20260526_phase4_sonnet_card_b_cost_slippage.md

Bitte mache:
1. Erstelle eine neue Kanban-Karte mit assignee=coder.
2. Status soll NICHT automatisch starten, falls möglich: blocked oder scheduled/waiting for Anton approval.
3. Titel: "Trading Hub Card B: isolated cost/slippage model"
4. Body soll kurz enthalten:
   - Implementiere NUR Karte B: isoliertes Cost/Slippage-Modell.
   - Nutze Prompt: /root/trading/markov-strategy/.hermes/prompts/20260526_phase4_sonnet_card_b_cost_slippage.md
   - Ziel-Dateien wahrscheinlich: trading_hub/costs.py oder trading_hub/cost_model.py + tests/test_cost_model.py
   - Acceptance: deterministic/offline, no network, no broker/exchange/order path, negative inputs ValueError, sensitivity monotonic, tests targeted + full suite.
   - Explicit non-goals: kein Ledger, kein VirtualAccount, kein Backtest, keine Strategie, kein Reporting, kein Discord, keine zweite Card.
5. Verifiziere mit `hermes kanban show <task_id>`.
6. Berichte nur Task-ID, Status, Assignee, und ob sie blockiert/scheduled ist.

Nicht tun:
- Nicht implementieren.
- Nicht alte Karte t_67048522 bearbeiten, außer du erwähnst sie als ältere breitere Referenz.
- Nicht Dispatcher nudgen.
