# Sketch 006 — Opus Jarvis / NeuroCloud Command Center

A static, self-contained HTML prototype of the **NOX / Hermes Trading Hub** as a
dense, Jarvis-style command field. Inspired by the "Video 2" reference: a
single-screen neural lattice + particle cloud that visualises the cluster of
agents, memories, strategies, crons, routes and risk gates around the **NOX
core** at the center.

> **Prototype only.** This is a design sketch. No live trading, no real
> orders, no network calls to exchanges. Everything you see is mocked data
> hard-coded inside `index.html`.

---

## How to open

The prototype is a single HTML file with no build step.

```bash
# easiest: just open it in a browser
xdg-open sketches/006-opus-jarvis-reference-neural-cloud/index.html
# or on macOS
open  sketches/006-opus-jarvis-reference-neural-cloud/index.html
```

If you prefer a local server (so Google Fonts load over HTTPS rather than
file://), any static server works:

```bash
cd sketches/006-opus-jarvis-reference-neural-cloud
python3 -m http.server 8006
# then visit http://localhost:8006
```

There are no `npm install`, no bundler, no API keys. Offline-friendly: the
only external resource is the Google Fonts stylesheet. If fonts fail to load
the layout still renders cleanly via system-ui / monospace fallbacks.

---

## What you get

A three-panel command center, viewable at 1100px+ desktop widths:

- **Left rail — NOX // CORE**
  - System Vitals KPIs (live entities, active routes, blocked tasks, completed)
  - Domain Filter chips (ALL, CORE, AGENTS, MEMORY, RESEARCH, TRADING, RISK,
    ROUTES, CRONJOBS, BLOCKED) — filter the graph live
  - Pulse Feed — rolling stream of mock events with new items every ~6.5s
- **Center — Mission Field**
  - 180+ node neural mesh around the NOX core
  - 200+ animated curved edges, with hot/inner/spoke/dim classes
  - Light pulses animating along hot and spoke edges
  - **Mode toggle:** `NEURAL LATTICE` (ringed lattice around the core) vs
    `PARTICLE CLOUD` (clustered nebula by category, with depth-shaded dust)
  - Top/bottom HUDs: uptime, FPS, node/edge counts, regime, risk
  - Bottom legend mapping color → entity category
- **Right rail — Selected Entity**
  - Detail hero card with state, link count, uptime/rate, etc.
  - Connected Entities list (click to traverse)
  - Live Queue of top work items (click to focus that entity)

### Interactions

| Action | Result |
|---|---|
| Click a node | Selects it; right panel updates; selection ring appears on graph |
| Hover a node | Tooltip with label · category · state |
| Click a domain chip | Filters visible nodes + edges to that category |
| Click `NEURAL LATTICE` / `PARTICLE CLOUD` | Switches layout |
| Click a Connected Entity row | Selects that entity, follows the link |
| Click a Live Queue card | Selects the underlying entity |
| Keyboard `L` | Switch to lattice mode |
| Keyboard `C` | Switch to cloud mode |
| Keyboard `Esc` | Clear selection |

### Layout & rendering

- Pure SVG for the central graph (nodes, edges, labels, pulses, rings)
- One `<canvas>` background for the drifting nebula dust (colored particles
  with soft shadow blur)
- CSS-only scanlines, brackets, panel chrome and KPI sparkbars
- Animations via SVG `<animate>` / `<animateMotion>` and CSS keyframes — no
  third-party animation libraries

### Data model (mocked)

The dataset lives in `index.html`:

- `NAMED` — 37 first-class entities (Hermes, Kanban, Markov Engine, …)
- `SATS` — labelled satellites (tasks, signals, files, notes, books, videos,
  crons) attached to a parent named entity
- `DUST` — 92 unlabelled background dust particles for density
- `EDGES` — typed edges (`spoke` / `inner` / `hot` / `dim`)

Categories map to the legend colors: `core`, `agent`, `memory`, `research`,
`trading`, `risk`, `route`, `cron`, plus the state-flag `blocked`.

---

## File structure

```
sketches/006-opus-jarvis-reference-neural-cloud/
├── README.md      ← this file
└── index.html     ← the entire prototype (HTML + CSS + JS in one)
```

---

## Disclaimer

This sketch exists to explore visual language for the Trading Hub control
surface. **It is not connected to any exchange, broker, or live data feed.**
Numbers (Sharpe, CAGR, regime probabilities, equity, drawdown, etc.) are
illustrative mocks chosen to make the design legible — not signals, not
forecasts, not advice. Do not trade on what you see here.
