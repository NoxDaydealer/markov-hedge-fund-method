Du bist Claude Code Sonnet im Implementierungsmodus. Arbeite nach Claude Code Superpowers: klein, testgetrieben, verifizieren vor Abschluss. Anton hat Implementierung nur für die erste freigegebene Card erlaubt.

Kontext lesen:
1. Phase-1-Plan:
/root/trading/markov-strategy/.hermes/plans/20260526_phase1_books_to_paper_trading_plan.md

2. Opus-Review:
/root/trading/markov-strategy/.hermes/plans/20260526_phase2_opus_plan_review.md

3. Projekt-README:
/root/trading/markov-strategy/README.md

4. Nur die konkret relevanten bestehenden Source-/Test-Dateien, nachdem du aus Plan+Review die erste Card bestimmt hast.

Aufgabe:
- Implementiere NUR die im Opus-Review empfohlene "First Implementation Card".
- Wenn das Review keine eindeutige Card nennt, wähle die kleinste sichere Foundation-Card für Paper-Trading, bevorzugt: Paper Ledger / Virtual Account Foundation ohne Live-Trading.

Harte Grenzen:
- Keine echte Order-Ausführung.
- Keine Broker-/Exchange-Trading-Anbindung.
- Keine Secrets lesen oder ausgeben.
- Keine Netzwerkcalls zu Exchanges.
- Keine Implementierung weiterer Cards.
- Kein großer Refactor außerhalb der Card.
- Keine full_text.md Buchdateien lesen.

Arbeitsweise:
1. Schreibe zuerst einen Mini-Plan mit betroffenen Dateien und Tests.
2. Erstelle/ändere Tests passend zur Card.
3. Implementiere minimal.
4. Führe gezielte Tests aus.
5. Falls gezielte Tests grün sind, führe nach Möglichkeit die relevante Testsuite aus.
6. Berichte am Ende exakt:
   - geänderte Dateien
   - Tests und Ergebnis
   - was bewusst NICHT gemacht wurde
   - nächste empfohlene Card

Akzeptanz:
- Code ist paper/research-only.
- Tests decken Kernverhalten ab.
- No-lookahead/Safety-Regeln aus Opus-Review sind eingehalten.
- Bestehende Tests brechen nicht unnötig.

Wenn du unsicher bist oder die Card zu groß wirkt:
- Stoppe vor Codeänderungen.
- Schlage eine kleinere Card vor.

## Absolute Stop Rule
- Nach Plan/Review: NICHT implementieren, sondern stoppen.
- Bei Implementierung: exakt EINE Card, nämlich die erste im Opus-Review empfohlene Card.
- Keine zweite Card, keine Zusatzverbesserungen, kein großer Refactor.
- Wenn die Card größer wirkt als ein kleiner sicherer Schritt: vor Codeänderungen stoppen und kleinere Teil-Card vorschlagen.

