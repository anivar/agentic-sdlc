---
name: plan-project
description: >
  Write one plan file for a project or a change: outcome with measures, decisions laid out as
  options for a decider, numbered assumptions each tied to the test that proves it, dated steps
  with an owner and a "done when", gates between phases, risks with triggers, a rollout with a
  rollback, a cut order and a never-cut list, and the commitments made along the way. The plan
  is written, shown, and the turn ends; implementation starts only after the decider approves.
  Triggers on: "plan", "write a plan", "project plan", "roadmap", "spec", "specify",
  "requirements", "before we build", "how would we approach", "PRD", "what are the steps".
license: MIT
user-invocable: true
argument-hint: "<project or change> [plan file path]"
compatibility: Any project. Writes docs/plan/PLAN.md unless told another path.
metadata:
  author: Anivar Aravind
  author_url: https://anivar.net
  version: 1.0.0
  tags: planning, specification, assumptions, gates, rollout, decisions
  derived_from: spec-driven-development (addyosmani/agent-skills, MIT) for the human review gate between phases and the assumption list; the template and the decider profile are the author's own
  rules: PLAN-1 PLAN-2 PLAN-3 PLAN-4 PLAN-5 PLAN-6 PLAN-7 PLAN-8 PLAN-9 EVID-1 VOICE-2 VOICE-9 VOICE-13 GRILL-3
---

# Plan a project

One plan file, in the template below, at `docs/plan/PLAN.md` unless the decider names another
path. When the project has code, a repository `AGENTS.md` carries the rules that bind. Nothing
else: no index, no brief, no mapping document unless asked.

## The gate

Writing the plan and starting the work are different turns. Save the plan, summarise it, list
the open questions, ask the decider to approve or amend, and end the turn. Planning tasks and
writing code start only after approval arrives in a later turn.

## The template

```markdown
# <Project>: plan

Status: proposal | agreed · Delivery owner: <team or role> · Decides: <role> · Updated: <date>

Evidence tags: Verified (source opened), Measured (number plus query), Inferred, Planned.

## Outcome
What changes, for whom. 2 to 4 measures, each baseline → target, with how it is measured.
Not doing: <explicit non-goals>.

## Decisions
| # | Decision | Options | Proposal | Decides | By |

## Assumptions
| # | Assumption | Evidence | Proven by (test, query, vendor answer) | Status: open / proven / broken |

## Plan
### Phase <n>: <name>. Gate: <what must be true to move on>, reviewed by <role>
| ID | Step | Owner | Days | Depends on | Done when | Date | Status |

## Risks
| # | Risk | Trigger to watch | Mitigation | Owner |

## Rollout
Pilot → widen (1 → 5 → all, with a hold point at each). Rollback: <the one step that undoes it>.
Run: monitoring, runbook, escalation ladder (who, after how long).

## If time runs short
Cut in this order: <list>. Never cut: <list>.

## Commitments
| What | To whom | By | Status |
```

## The rules

| Id | Rule | In practice |
|---|---|---|
| PLAN-1 | One plan file, dated steps with done-when | A step is at most three days, has one owner, a date the owner named, and a "done when" someone else can check. Each step is reversible, or says how it is undone. A gate sits between phases. |
| PLAN-2 | Assumptions tied to tests | Number each assumption, tie it to the test, query or vendor answer that proves it, or mark it open. The first step attacks the riskiest assumption. Vertical slices that work end to end, not layers. |
| PLAN-3 | Cut order and never-cut list | Say what goes first if time runs short and what never goes. A slip is reported before its date; a scope cut goes in the headline; a baseline never moves silently. |
| PLAN-4 | Behaviour change stated up front | Does it break existing behaviour, what exactly changes, what was parked. A failure-mode table (failure, allowed impact, mechanism, test) and a per-client compatibility table. New pieces degrade alone; one bug never stops business activity. |
| PLAN-5 | Gates carry escalation ladders | Self-service, a named decider role, automatic lanes, a ceiling, each with a response time. |
| PLAN-6 | No resourcing, trivia or blocker words | No headcount, no operational trivia, no "production blocker" in a repository document, no follow-up-ticket line where a decision belongs. |
| PLAN-7 | Decisions in the decider's words | Options in the table; the decision recorded in the decider's own words, with who decides and by when. The decider approves and evaluates; delivery steps belong to the team. On an inherited programme the decider's role is to evaluate and unblock, never to own delivery. |
| PLAN-8 | Newest production version | Check what the platform runs in production, then decide. Never design on a beta; never drop a version for compatibility. |
| PLAN-9 | Platform changes prove out on staging | Validated there by the decider before production. |

## Sizing

A size with no basis is marked as a guess. Numbers carry their source: a query, `file:line` at a
named commit, or a link (EVID-1).

## Guardrails against false claims

- Tag every factual clause Verified, Measured, Inferred or Planned. Never upgrade a level.
- "Live", "100%", "PASS", "confirmed", "zero data loss", "on track", "resolved" need matching evidence. <!-- voice-lint: skip -->
- Banned outright: seamless, robust, best-in-class, leverage, comprehensive, world-class. <!-- voice-lint: skip -->
- Plain declaratives, no rhetorical structure, no decorative lines, numbered lists only for real
  work items, current state only (plain-voice).
- Before handing over: read it as the receiver; check every claim traces to a source; check every
  assumption is tested or marked open; check nothing is promised that the decider did not promise;
  check the decider could explain the plan in three sentences without the document.

## Repository AGENTS.md, when there is code

```markdown
# <repo>: rules that bind
## How to work
- One plan step at a time. Update the plan with the code.
- Commit only when lint, typecheck and every test pass, gated on exit codes.
## Rules
1. <the invariants that must never break, each one line>
```

## Companion skills

| Need | Skill |
|---|---|
| Settling the decisions table before the plan is final | grill-plan |
| Recording a decision that is hard to reverse | decision-records |
| Turning approved steps into tickets | cut-tickets |
| Landing each step | thin-slices |
