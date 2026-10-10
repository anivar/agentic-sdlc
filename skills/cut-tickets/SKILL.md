---
name: cut-tickets
description: >
  Break an approved plan, spec or conversation into tickets: one per real work item, each a
  vertical slice with acceptance criteria and the tickets that block it, free of infrastructure
  identifiers, secret paths, partner URLs and colleagues' names, with full links for every
  reference. The breakdown is shown and approved in the conversation; publishing to the tracker
  is a post and waits for its go-ahead.
  Triggers on: "cut tickets", "break this down", "create issues", "to tickets", "split into
  tasks", "what are the work items", "file the issues", "ticket this".
license: MIT
user-invocable: true
argument-hint: "<plan path, spec path, issue link, or nothing for the conversation>"
compatibility: Any tracker recorded in docs/agents/tracker.md; local markdown tickets when none is.
metadata:
  author: Anivar Aravind
  author_url: https://anivar.net
  version: 1.0.0
  tags: tickets, issues, planning, vertical-slices, tracker
  derived_from: to-tickets (mattpocock/skills, MIT) for tracer-bullet slicing and the expand-contract sequence; the content rules are the author's own
  rules: TICKET-1 TICKET-2 TICKET-3 TICKET-4 TICKET-5 TICKET-6 ASK-3 SETUP-2 VOICE-11
---

# Cut tickets

A ticket is a promise someone else can check. Cut them so each one is a complete, narrow path
through every layer, demoable or verifiable on its own, and so the set as a whole has a frontier:
the tickets whose blockers are done.

## The rules

| Id | Rule | In practice |
|---|---|---|
| TICKET-1 | One ticket per real work item | Never one per checklist step. A vertical slice through schema, API, interface and tests, sized to one working session. Any prefactoring goes first. |
| TICKET-2 | Acceptance and blockers | What to build from the user's perspective, acceptance criteria someone else can check, the tickets that block it. Native dependency links where the tracker has them; a "Blocked by" line otherwise. |
| TICKET-3 | No identifiers, secrets or names | No infrastructure identifiers, secret paths, partner URLs or colleagues' names. Describe the step and point to the internal runbook. Ownership reads "to be agreed with <team>". |
| TICKET-4 | Full links | Every reference to another change or ticket is a full link, never a bare number. |
| TICKET-5 | Approval before publishing | Show the breakdown as a numbered list: title, blocked by, what it delivers. Ask about granularity, blocking edges, merges and splits. Publish only after approval, and publishing is a post (ASK-3). The parent item is never closed or edited by the breakdown. |
| TICKET-6 | Wide refactors use expand and contract | A mechanical change that breaks thousands of call sites at once cannot be a slice. Expand (add the new form beside the old), migrate in batches sized by blast radius, contract (delete the old form). Each batch its own ticket, blocked by the expand; the contract blocked by every batch. |

## Where tickets go

The tracker and its label vocabulary are recorded in `docs/agents/tracker.md` (SETUP-2). If the
file is absent, say so and ask the decider to run `/setup-conventions`; until then write local
tickets under `.scratch/<feature>/issues/NN-slug.md` and add `.scratch/` to `.gitignore` so a
local ticket is never one `git add` away from the public repository.

## Ticket template

See `references/ticket-template.md`. Avoid file paths and code in a ticket: they go stale.
The exception is a snippet from a prototype that encodes a decision more precisely than prose
(a state machine, a schema, a type shape); inline the decision-rich part and say where it came
from.

## Companion skills

| Need | Skill |
|---|---|
| The plan the tickets come from | plan-project |
| The voice of the ticket text | plain-voice |
| Landing each ticket | thin-slices |
| Recording the tracker and labels | setup-conventions |
