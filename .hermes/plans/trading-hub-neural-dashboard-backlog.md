# Trading Hub / Nox Neural Dashboard Backlog

Date: 2026-05-25
Source: Anton Telegram feedback + Instagram references

## Intent
Build a visually strong dashboard as either a replacement for, or companion to, the existing Kanban board. The dashboard should make Hermes/Nox feel like a live command center rather than a plain task list.

## Visual Direction
- Dark cinematic command-center base.
- Living neural network / neuron graph as the core visual metaphor.
- Nodes should glow/pulse when agents/jobs/tasks are active.
- Edges should represent relationships, dependencies, data flow, or report routing.
- Optional alternative visualization: colorful neural/data cloud with clustered nodes.
- Color clusters can represent domains:
  - Trading Hub strategy lab
  - book/eBook research
  - YouTube/intake pipeline
  - cron/watchdogs
  - Discord/Telegram reporting
  - paper portfolio / risk
  - Kanban worker states
- Should feel premium, alive, and useful — not decorative noise.

## Product Goal
A second dashboard layer beside Kanban:
- Kanban remains the durable task board.
- Neural Dashboard becomes the high-level mission-control / observability view.
- It should answer quickly: what is active, what is blocked, what produced output, where did the report go, what needs Anton.

## MVP Scope
1. Read real state from existing sources where possible:
   - Kanban tasks/statuses
   - cron jobs
   - Trading Hub report outputs
   - watched book/eBook folders
   - Discord thread routing config
2. Render an interactive neural/graph view:
   - nodes for agents, jobs, projects, report threads, research sources
   - animated glow/pulse for active/recent updates
   - colors by domain/status
   - click node => side panel with details/actions
3. Provide dashboard panels:
   - Active automations
   - Waiting on Anton
   - Last reports
   - Open research inputs
   - Strategy lab status
   - Paper portfolio / risk status
4. Keep Kanban integration visible:
   - blocked/todo/running/done counts
   - top blocked cards
   - dependency lines when available

## Candidate Visual Variants
A. Neural Brain Map
- central AI/agent core
- radial clusters per project/domain
- glowing synapse-like edges

B. Data Cloud / Particle Map
- colorful 3D-ish cloud of nodes
- clusters drift subtly
- useful for live observability / ambient mode

C. Command Center Hybrid
- left: neural graph
- right: cards/panels/actions
- best candidate for actual daily use

## Constraints
- No real trading execution; research/paper-trading only.
- Avoid breaking existing Kanban dashboard.
- Build as companion first, replacement later only after it is clearly better.
- Must be visually verified in browser screenshots.
- Must have real data behind the nodes; placeholders only in the first design sketch.

## Suggested Implementation Path
1. Sketch 2-3 static/interactive HTML variants.
2. Anton chooses visual direction.
3. Implement MVP as Hermes dashboard plugin or Trading Hub standalone dashboard.
4. Connect to read-only state APIs first.
5. Add safe actions later: open report, run cron once, pause/resume job, open Kanban card.

## Backlog Status
Created as backlog/spec artifact. Kanban cards should remain blocked until deliberately started, because current Kanban workers have known stability issues.
