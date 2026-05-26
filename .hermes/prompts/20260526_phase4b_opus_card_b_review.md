Du bist Claude Code Opus im Review-Modus. Anton nutzt seine Claude-Code-Subscription. Arbeite kurz und präzise: NICHT implementieren, nur die fertige Card-B-Änderung reviewen.

Aufgabe: Reviewe Karte B — Cost/Slippage-Modell — nachdem Sonnet sie implementiert hat.

Bitte lesen:
- git diff der aktuellen Änderungen gegen vorherigen Stand.
- Neue/geänderte Cost-Datei, z.B. trading_hub/costs.py oder trading_hub/cost_model.py.
- tests/test_cost_model.py.
- Nur bei Bedarf: pyproject.toml.

Nicht lesen:
- full_text.md Buchdateien.
- Secrets / .env / Auth.
- Große Logs/Sessions.

Review-Fokus:
1. Ist das Modul wirklich isoliert und paper/research-only?
2. Gibt es Netzwerk-, Broker-, Exchange- oder Order-Risiken?
3. Sind Kosten/Slippage/Impact sinnvoll und verständlich modelliert?
4. Sind Eingabevalidierungen ausreichend?
5. Sind Tests robust genug, inkl. monotoner Sensitivität und negativer Inputs?
6. Gibt es API-Namen/Struktur-Probleme für spätere Ledger/Backtest-Integration?

Output:
Schreibe eine kurze Review-Datei nach:
/root/trading/markov-strategy/.hermes/plans/20260526_phase4b_opus_card_b_review.md

Format:
# Opus Review — Card B Cost/Slippage

## Verdict
PASS / PASS_WITH_FIXES / FAIL

## Critical Issues
- Maximal 5; wenn keine: "Keine".

## Suggested Fixes Before Next Card
- Maximal 5; nur konkrete kleine Fixes.

## Safety Check
- Paper-only: yes/no
- No network: yes/no
- No broker/order path: yes/no
- Input validation: yes/no
- Tests adequate: yes/no

## Next Card Recommendation
- Eine knappe Empfehlung, welche Karte als nächstes dran sollte.

Absolute Stop Rule:
- Keine Implementierung.
- Keine Dateiänderungen außer der Review-Datei.
- Keine nächste Card starten.
