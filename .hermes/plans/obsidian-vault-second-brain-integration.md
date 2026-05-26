# Obsidian Vault Integration — Second Brain for Nox / Trading Hub

Date: 2026-05-25
Source: Anton Telegram idea after Instagram Reel 1/2 references

## Intent
Evaluate and design a new Obsidian vault as a human-readable second brain for Nox/Hermes and Trading Hub. Anton is new to Obsidian, so the system should be simple, opinionated, and not require manual complex setup.

## Why Obsidian
Obsidian is a good human-facing knowledge layer for:
- project notes
- research summaries
- book/eBook notes
- strategy ideas
- decisions and logs
- links between concepts, tasks, reports, and sources

It should complement, not replace:
- Kanban: durable task/work queue
- Fact Store: compact durable machine memory
- Sessions: conversation history
- GitHub: backup/versioning
- Discord: report delivery

## Desired Architecture
Inputs:
- Telegram messages / voice notes
- Discord reports
- book/eBook OCR summaries
- YouTube strategy intake
- Trading reports
- Kanban task handoffs

Pipeline:
1. Capture inbox note
2. Router tags/classifies item
3. Creates/updates project/source/strategy notes
4. Links notes with Obsidian wikilinks
5. Creates Kanban cards only when action is needed
6. Stores compact durable facts in Fact Store only when long-lived

## Proposed Vault Path
Default candidate:
`/root/trading/ObsidianVault`

Alternative if Anton later syncs from PC/phone:
`/root/ObsidianVault` or a Syncthing/Drive-mounted path.

## Starter Vault Structure
```
00_Inbox/
01_Projects/
  Trading Hub/
  Nox Dashboard/
02_Sources/
  Books/
  YouTube/
  Reels/
03_Strategies/
  Ideas/
  Backtests/
  Paper Trading/
04_Reports/
  Daily Markov/
  Strategy Evaluations/
  Paper Portfolio/
05_Decisions/
06_Templates/
99_Archive/
```

## Starter Notes
- `Home.md` — simple dashboard/index
- `Trading Hub.md` — project overview
- `Nox Mission Control Dashboard.md` — neural UI idea
- `Book Research Index.md`
- `Strategy Idea Template.md`
- `Decision Log.md`
- `Inbox.md`

## MVP Automation
1. Create the vault and starter notes.
2. Add a deterministic no-agent script that can append short report summaries to daily notes.
3. Add a safe capture command/workflow: Telegram message or file => `00_Inbox/YYYY-MM-DD.md`.
4. Add links from Trading Hub book notes to vault notes.
5. Do not dump full copyrighted eBooks into Obsidian; only summaries, page refs, and Anton's own notes.

## Future UI Tie-In
The Neural Mission Control Dashboard can show Obsidian as the knowledge layer:
- note nodes
- source nodes
- strategy idea nodes
- report nodes
- edges via wikilinks/tags

This matches the Instagram Reel 1 idea: capture → route → process → second brain.

## Safety / Scope
- Private vault; do not publish copyrighted content.
- Keep notes concise and navigable.
- Avoid overengineering plugins at first.
- Start filesystem-first; no Obsidian plugin dependency needed for Hermes.

## Status
Backlog/spec only. Current environment has no `OBSIDIAN_VAULT_PATH` set and no fallback `/root/Documents/Obsidian Vault` directory. Create a new vault only after Anton confirms desired path/sync approach, or default to `/root/trading/ObsidianVault` if he says to proceed.
