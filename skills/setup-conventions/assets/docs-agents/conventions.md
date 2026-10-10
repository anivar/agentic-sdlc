# Conventions

How the agentic-sdlc skills read this repository.

## Decision records and glossary

| What | Where |
|---|---|
| Glossary | `GLOSSARY.md` at the root (`GLOSSARY-MAP.md` lists contexts when there are several) |
| Decision records | `docs/adr/NNNN-slug.md` |
| Research documents | `docs/research/<date>-<question>.md` |

Before exploring an area, read the glossary and the records that touch it. If none exist, proceed
without flagging their absence; they are created when the first term or decision qualifies
(DECIDE-1, DECIDE-2). Output that contradicts a record says so (DECIDE-6).

## Voice

Deliverables follow plain-voice. The mechanical rules run as `agentic-sdlc lint-voice` on
`README.md` and `docs/` in CI with `--fail-on fail`.

## Plans

Plans live at `docs/plan/PLAN.md` in the plan-project template. One plan per project or topic
(PLAN-1).

## Review

Findings only on the introducing change at its head sha, one per thread in Conventional
Comments, a summary that ends in a decision (REVIEW-1, REVIEW-2, REVIEW-3). The mutation check
runs on at least one new condition (REVIEW-4).

## Production

| Target | Where | Rule |
|---|---|---|
| <production system> | <how it is reached> | read-only unless the decider says otherwise for that action (PROD-1) |

## Mechanisms in this repository

| Mechanism | Where |
|---|---|
| Claude Code hook | the agentic-sdlc plugin; settings in `.agentic-sdlc.json` |
| Pull request or merge request text check | `.github/workflows/conventions.yml` calling `anivar/agentic-sdlc` at a pinned tag, or the `conventions` job in `.gitlab-ci.yml` |
| Branch rules | the ruleset imported from `rulesets/main-protected.json` |
