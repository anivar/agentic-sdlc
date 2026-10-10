---
name: grill-plan
description: >
  Interrogate a plan, design or decision until nothing is silently assumed: map the decisions as
  a tree, ask the whole settled frontier in one numbered round with a recommended answer per
  question, look facts up instead of asking for them, put only decisions to the decider, and
  record each settled decision in the plan or as a decision record. Also the discipline for
  walking into a discussion: three questions written first, direct answers to direct questions.
  Triggers on: "grill me", "grill this", "stress-test", "poke holes", "interrogate the plan",
  "what am I missing", "challenge this", "before I commit to this", "prepare me for the meeting".
license: MIT
user-invocable: true
argument-hint: "<plan, design or decision to grill>"
compatibility: Any plan or design; records decisions through plan-project and decision-records.
metadata:
  author: Anivar Aravind
  author_url: https://anivar.net
  version: 1.0.0
  tags: planning, decisions, questions, design-review, meetings
  derived_from: grilling and grill-with-docs (mattpocock/skills, MIT) for the design tree and the frontier; the room discipline is the author's own
  rules: GRILL-1 GRILL-2 GRILL-3 GRILL-4 PLAN-7 DECIDE-1 EVID-1
---

# Grill a plan

Interview until there is a shared understanding and nothing is left assumed. The decisions
form a tree: every decision branches into the decisions that hang off it. Work the tree in
rounds.

## The rules

| Id | Rule | In practice |
|---|---|---|
| GRILL-1 | Rounds over the frontier | The frontier is every decision whose prerequisites are settled. Ask the whole frontier in one round: number each question, give a recommended answer, word the question so "yes" accepts the recommendation. A question that depends on another one still open waits for the next round. |
| GRILL-2 | Facts are the agent's job | Anything the filesystem, the repository, a document or a tool can answer is looked up, never asked. A running lookup is an unsettled prerequisite: ask the rest of the frontier now, hold only the questions downstream of it. |
| GRILL-3 | The session ends when the frontier is empty | Every branch visited, nothing silently assumed. Act on nothing until the decider confirms the shared understanding. Each settled decision goes into the plan's Decisions table (PLAN-7) or, when it is hard to reverse and surprising, a decision record (DECIDE-1). |
| GRILL-4 | Questions before the room, direct answers in it | Before a discussion, write three questions and ask them first. Answer a direct question about authority directly. A proposal has a name, an owner and a date, or it is not a proposal. Let someone presenting their own work finish before extending it. |

## A round

```
Q1. <title>: <the question, with the options when there are several>
    Recommended: <answer>. Yes accepts it.

Q2. <title>: <question>
    Recommended: <answer>.
```

Plain text, no emoji, no decoration. After the answers, recompute the frontier: settled
decisions unblock the questions that depended on them. Ask the next round.

## What a good question does

- It separates a decision (the decider's) from a fact (yours to find).
- It names the consequence of each option in one line, tagged Verified, Measured or Inferred
  (EVID-1).
- It is specific enough that "yes" is an answer.

## Companion skills

| Need | Skill |
|---|---|
| Where the settled decisions go | plan-project, decision-records |
| The vocabulary for interface and seam questions | deep-modules |
| Calibrating the consequences you state | evidence |
