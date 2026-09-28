---
name: typesafe
description: "TypeSafe Jev judge via UEFN-Ducky — noul/choice/score decisions, Automations/Pipelines tiles, ducky-cluster routing. Not a chat model."
license: MIT
metadata:
  label: TypeSafe
  version: 1
  author: UEFN-Ducky
  copyright: Copyright 2026 Mindful Path Company, LLC
  allow_redistribute: true
  managed_by: uefn-ducky
  source_plugin_id: typesafe
---

# TypeSafe / Jev — judge, not the agent

Jev is TypeSafe's System One model. It returns **typed decisions** (noul / choice / score), not chat or Verse.

**Do not** pick Jev as the chat model. Chat stays Claude / GPT / Codex. Call `typesafe_*` tools or drop TypeSafe tiles on Automations / Pipelines.

**Do not** curl `api.typesafe.ai` or read a `.env`. The key lives in **Settings → LLMs → TypeSafe** (encrypted; use **Test**).

## Tools

- `typesafe_status` — key present? default model? online?
- `typesafe_list_models` — aliases (`jev-latest` → versioned id)
- `typesafe_decide(state, questions, model="")` — many atomic questions in **one** call
- `typesafe_route_ducky(state, profiles_json="")` — pick an installed ducky; then `ducky_spawn_chat(ducky=…)`

Pin `jev-1.13.0` if you tuned thresholds. Otherwise `jev-latest`.

## Question types

- **noul** — yes/no as `0..1`. Gate with a threshold (default 0.7).
- **choice** — one of your options + probabilities + confidence. Option keys become `choice` and `ducky`.
- **score** — 2–10 ordered levels. `score` can land between levels.

Batch every question that shares the same `state`. One question per call is the expensive habit.

## Workflows

Tiles write flat fields onto the run (`noul`, `choice`, `ducky`, `score`, `gate`, `confidence`). Host `flow.branch` reads `field=gate`. Host `pipeline.agent` reads `payload.ducky` — leave its ducky config empty after `typesafe.route_ducky` or `typesafe.choice`.

Do **not** use `ducky.spawn` for routing; it ignores profile.

Premade templates (Pipelines unless noted):

- Jev routes a specialist ducky
- Jev gates then acts
- Jev: Verse vs art vs world
- Jev guardrail
- Jev score then continue
- Jev manual gate (Automations Test)

## Examples

Route a swarm seat from a leader chat:

1. `typesafe_route_ducky(state=user_ask)`
2. `ducky_spawn_chat(ducky=<returned ducky>, group_id=…, message=…)`

Classify a Verse compile error in one decide call: noul "is this a digest deadlock?", choice "9002 / 3509 / other", score "how blocking". Then your own ifs — do not ask Jev to write the fix.
