Du bist Claude Code Opus im Review-Modus. Anton nutzt seine Claude-Code-Subscription. Arbeite sparsam: NICHT neu planen, NICHT implementieren, nur Review der vorhandenen Plan-Datei.

Ziel: Prüfe den von Sonnet erstellten Phase-1-Plan für Trading Hub Paper-Trading und verbessere ihn als Architektur-/Risiko-Review, ohne ihn komplett neu zu schreiben.

Input-Datei:
/root/trading/markov-strategy/.hermes/plans/20260526_phase1_books_to_paper_trading_plan.md

Optional lesen, nur wenn für Review zwingend nötig:
- /root/trading/TradingHub_Books/00_trading_hub_books_ultraplan.md
- /root/trading/markov-strategy/README.md

Nicht lesen:
- full_text.md Dateien
- komplette Source-Trees
- große Logs/Sessions
- weitere Buchordner 04-06

Review-Fokus:
1. Ist die Reihenfolge der Roadmap sinnvoll?
2. Fehlt ein zwingender Baustein für Paper-Trading: Ledger, Virtual Account, Risk Engine, Cost/Slippage, Walk-forward, Reporting, Strategy Registry?
3. Sind die Karten klein genug für Sonnet-Implementierung?
4. Gibt es Lookahead-/Live-Trading-/Risk-Safety-Gefahren?
5. Welche Card sollte Sonnet als erstes schreiben?

Output-Datei:
/root/trading/markov-strategy/.hermes/plans/20260526_phase2_opus_plan_review.md

Output-Format:
# Opus Review — Trading Hub Phase-1 Plan

## Verdict
- PASS / PASS_WITH_FIXES / FAIL
- 3-5 Sätze warum.

## Critical Fixes Before Implementation
- Maximal 7 Punkte.

## Roadmap Reordering
- Wenn nötig, neue Reihenfolge der ersten 5 Cards.
- Wenn nicht nötig: "Keine Änderung".

## First Implementation Card Recommendation
- Card-Titel
- Warum diese zuerst
- Was Sonnet genau bauen soll
- Was Sonnet NICHT bauen soll

## Safety Checklist For Sonnet
- konkrete Regeln, die im nächsten Implementierungsprompt stehen müssen.

Wichtig:
- Keine Implementierung.
- Keine riesige Neuschreibung.
- Kurz, präzise, umsetzbar.

## Absolute Stop Rule
- Nach Plan/Review: NICHT implementieren, sondern stoppen.
- Bei Implementierung: exakt EINE Card, nämlich die erste im Opus-Review empfohlene Card.
- Keine zweite Card, keine Zusatzverbesserungen, kein großer Refactor.
- Wenn die Card größer wirkt als ein kleiner sicherer Schritt: vor Codeänderungen stoppen und kleinere Teil-Card vorschlagen.

