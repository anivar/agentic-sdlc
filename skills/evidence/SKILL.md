---
name: evidence
description: >
  Calibrate every claim before it leaves the session: tag each factual clause Verified, Measured,
  Inferred or Planned, verify behaviour at the production sha, treat agent and bot output as a
  lead rather than evidence, read sources in full, compute a headline number twice, sweep every
  surface after one defect, and record what a source taught in a dated document.
  Triggers on: "verify", "is this true", "check the source", "what is the evidence", "at which sha",
  "production data", "sweep", a number about to be reported, a finding about to be filed, a summary
  or digest offered in place of a source, "confirmed", "resolved", "live", "100%", "on track".
license: MIT
user-invocable: true
compatibility: Any repository; the sha and deployment-record rules assume a deployed artifact exists.
metadata:
  author: Anivar Aravind
  author_url: https://anivar.net
  version: 1.0.0
  tags: evidence, verification, calibration, provenance, review
  rules: EVID-1 EVID-2 EVID-3 EVID-4 EVID-5 EVID-6 EVID-7 EVID-8 EVID-9 EVID-10 REVIEW-7
---

# Evidence

A claim is worth exactly what was done to check it. This skill fixes the vocabulary for how much
was done, and the handful of checks that turn a plausible sentence into a verified one. Every
other skill in this set cites these rules by id; the ids are stable and live in
`rules/registry.json`.

## When to use

| Situation | Rule |
|---|---|
| A sentence states a fact about code, data, a system or a person's work | EVID-1 |
| The fact is about running behaviour | EVID-2 |
| The fact came from an agent, a retrieval system or a review bot | EVID-3 |
| A summary, digest or transcript excerpt is on offer instead of the source | EVID-4 |
| A number is about to lead a message or a document | EVID-5 |
| One defect was just found | EVID-6 |
| A finding is about to be filed against another team | EVID-7 |
| A file is about to be asserted or edited | EVID-8 |
| Custom code is about to be written | EVID-9 |
| Reading a source taught something | EVID-10 |

## The tags

| Tag | Meaning | What earns it |
|---|---|---|
| Verified | the source was opened in this session | the file, log, record or page, read at the cited location |
| Measured | a number with the query that produced it | the command or query, repeatable |
| Inferred | reasoning from evidence, not the evidence itself | the premises named |
| Planned | intended, not done | a step in a plan |

Never upgrade a level. Merged is not deployed. Deployed is not verified in data. "Live", "100%",
"PASS", "confirmed", "resolved" and "on track" need matching evidence; "green" is never a status.
Give the sha, the date and the lane, or the gate.

## The rules

| Id | Rule | What it means in practice |
|---|---|---|
| EVID-1 | Tag every claim | Each factual clause carries a tag; an untagged clause is Inferred. Calibration is labelled honestly: "unverified", never blank. |
| EVID-2 | Verify at the production sha | `file:line` at the sha found from the live artifact or the deployment record, never a branch head or the latest tag. Behaviour comes from production data; dates from the deployment record. Code alone is a hypothesis; an absence claim needs data. |
| EVID-3 | Agent output is a lead | A sub-agent's quote, a retrieval hit or a bot's finding points at a line; the author opens that line before it is used. A quote is verbatim only after the author compared it. |
| EVID-4 | Read sources in full | A summary is a pointer to the source. Slice a large source rather than skip it. Say which sources were read in full and which were not. When two records of one event exist, read both and name where they disagree. Check who said what before quoting; automatic transcripts mislabel speakers. |
| EVID-5 | Compute a headline number twice | Second method, different path. Never divide counts from two systems with different identity models without the join. A number that moves between identical runs is a harness artefact: run suites one at a time against shared state and compare named failures, not counts. |
| EVID-6 | Sweep after one defect | Name the pattern, list every surface, report each as confirmed, not affected, or not checked. "Not checked" is a valid, honest row. |
| EVID-7 | Refute before filing | The second pass argues the other side. If the finding survives, file it with both passes shown. |
| EVID-8 | Re-read before asserting | Especially after checkout, stash or rebase, and before updating a change request whose state may have moved. |
| EVID-9 | Survey before building | Tool, data source, maintenance, fit: record it, name the pick. Custom code covers only the gap. A vendor's or partner's definition of a mechanism wins over a new mode. |
| EVID-10 | Record what a source taught | A dated document in the topic folder: question, sources (full or partial), method, findings with evidence, open questions, exact commands. Never overwrite the earlier one. |

## Weighting evidence

Weight evidence by what it cost to produce: shipped code, then a written design, then a
documented observation, then an opinion. A claim resting on the cheapest kind is Inferred
until the costlier kind is opened.

## How to apply in a session

1. Before answering on a topic, open what is already established (the topic's memory or dated
   documents), lead with that, then add what is new.
2. While working, tag as you write. A sentence with no tag is a sentence you have not checked.
3. Before showing a deliverable, run the adversarial read in review-change (REVIEW-7): which
   claim rests on something not opened this session, which number was recalled, which action
   does damage if the premise is wrong.
4. After reading a source, write the dated document (EVID-10) before moving on.

## What a tagged paragraph looks like

> The retry loop re-sends non-idempotent requests (Verified: `src/client/send.py:142` at the
> production sha `3f9c2ab`, from the deployment record of 2026-10-08). It produced 17 duplicate
> orders last week (Measured: `SELECT count(*) … WHERE created_at > '2026-10-01'` on the
> production replica, re-computed from the payment provider's export: 17). The cause is the
> timeout after the server accepted the write (Inferred from the request logs; no direct
> evidence of the accept). A fix with an idempotency key is in review (Planned).

Four clauses, four tags, one number computed twice (EVID-5), the inference marked as an
inference rather than upgraded to a finding (EVID-1).

## Companion skills

| Need | Skill |
|---|---|
| The adversarial read before showing work | review-change |
| The words that need evidence, and the form of a verdict-first message | plain-voice |
| Where decision records and glossaries live | decision-records |
| Plans with assumptions tied to tests | plan-project |
