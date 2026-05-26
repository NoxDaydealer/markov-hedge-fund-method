Du bist Claude Code Opus im Max-Effort/Ultrathink-Planungsmodus. Anton hat explizit genehmigt, dass du über seine Claude-Pro/Claude-Code-Anbindung arbeitest. NICHT implementieren, NICHT schreiben, nur lesen und einen sehr guten Plan ausgeben.

Ziel: Erstelle einen robusten, umsetzbaren Ultraplan für das Trading-Hub Langzeitprojekt nach der Extraktion/Zusammenfassung der ersten drei Trading-Bücher. Fokus: Research/Paper-Trading only, keine echte Order-Ausführung, keine Broker-Anbindung, keine Finanzberatung.

Du sollst dich mit Hermes Context Gateway MCP abstimmen:
1. Nutze context_gateway health.
2. Hole dir ein kompaktes Context Packet für Task: "Trading Hub books to paper-trading roadmap after three book summaries".
3. Optional: suche Memory/Kanban nur, wenn es hilft.

Lies diese Dateien:
- /root/trading/TradingHub_Books/01_quantitative_portfolio_management_isichenko/02_Extrahierte_Notizen_MD/summary_trading_hub.md
- /root/trading/TradingHub_Books/02_python_for_algorithmic_trading_cookbook_strimpel/02_Extrahierte_Notizen_MD/summary_trading_hub.md
- /root/trading/TradingHub_Books/03_hands_on_ai_trading_python_quantconnect_aws/02_Extrahierte_Notizen_MD/summary_trading_hub.md
- /root/trading/TradingHub_Books/00_trading_hub_books_ultraplan.md falls vorhanden, aber behandle ihn als Vorarbeit, nicht als final.
- /root/trading/markov-strategy/graphify-out/GRAPH_REPORT.md
- /root/trading/markov-strategy/README.md
- Relevante Source-Dateien unter /root/trading/markov-strategy/trading_hub/ nur soweit nötig, um den Plan an echte Architektur anzubinden.

Output-Anforderungen:
- Sprache: Deutsch.
- Schreibe einen finalen Markdown-Plan.
- Keine langen Buchzitate, keine urheberrechtlich problematischen Textauszüge; nur eigene Synthese.
- Gliedere in:
  1. Executive Decision: Was muss als nächstes gebaut werden und warum?
  2. Synthese der ersten 3 Bücher: welche Prinzipien sind für Trading Hub wirklich handlungsleitend?
  3. Architektur-Zielbild für Paper-Trading: Ledger, virtual account, risk engine, cost model, strategy registry, walk-forward, reporting.
  4. Konkrete Implementierungs-Roadmap in 8-15 kleinen Karten, jeweils: Titel, Ziel, betroffene Dateien/Module, Tests, Akzeptanzkriterien, Risiko.
  5. Priorisierte OCR-/Foto-Nachforderungen für Anton aus den 3 Büchern: max. 10 Items, jeweils genaue Sektion/Grund/was fotografieren.
  6. Kanban-Schnitt: welche Karten sollten blocked bleiben, welche können als next-ready vorgeschlagen werden.
  7. Qualitäts- und Sicherheitsregeln: no-lookahead, no-live-trading, costs, slippage, drawdown, margin-of-safety, logging.
  8. Open Questions an Anton: maximal 5, nur wirklich entscheidende.

Wichtig:
- Behandle das als Planungs-/Architekturauftrag. Nicht implementieren.
- Nutze Opus-Denken: kritisch, priorisiert, mit klaren Trade-offs.
- Der Plan muss in sich nutzbar sein, um danach Kanban-Tasks anzulegen.
