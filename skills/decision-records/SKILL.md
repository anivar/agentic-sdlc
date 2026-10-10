---
name: decision-records
description: >
  Keep a project's shared knowledge where the second reader can reach it: a glossary with one
  term per concept and the words to avoid, decision records for choices that are hard to reverse
  and surprising without context, dated research documents that record what a source taught, all
  as tables with honest calibration, naming systems and roles but never people.
  Triggers on: "ADR", "decision record", "glossary", "define the term", "what do we call",
  "record the decision", "research doc", "write down what we learned", "where should this live",
  a term used in conflict with the glossary, output that contradicts an existing record.
license: MIT
compatibility: Any repository. Defaults to GLOSSARY.md at the root and docs/adr/; a repository may point docs/agents/conventions.md elsewhere.
metadata:
  author: Anivar Aravind
  author_url: https://anivar.net
  version: 1.0.0
  tags: adr, glossary, domain-model, research, documentation
  derived_from: domain-modeling and the domain conventions of setup-matt-pocock-skills (mattpocock/skills, MIT) for the glossary and ADR formats, the lazy-creation rule, the design-session habits and the conflict callout; the calibration, naming and research-document rules are the author's own
  rules: DECIDE-1 DECIDE-2 DECIDE-3 DECIDE-4 DECIDE-5 DECIDE-6 EVID-1 EVID-3 EVID-4 EVID-5 EVID-10 PLAN-4 VOICE-2 VOICE-12
---

# Decision records

Three kinds of record, each with a format in `references/`:

| Record | Lives at | Format |
|---|---|---|
| Glossary | `GLOSSARY.md` at the root, or one per context listed in `GLOSSARY-MAP.md` | `references/glossary-format.md` |
| Decision record | `docs/adr/NNNN-slug.md` | `references/adr-format.md` |
| Research document | `docs/research/<date>-<question>.md`, or the path `docs/agents/conventions.md` names | `references/research-document.md` |

Create files lazily: a glossary when the first term is resolved, `docs/adr/` when the first
decision qualifies, a research document when a source taught something.

## The rules

| Id | Rule | In practice |
|---|---|---|
| DECIDE-1 | A record for a hard-to-reverse, surprising trade-off | All three must hold. Easy to reverse: you will just reverse it. Not surprising: nobody will wonder why. No real alternative: nothing to record. One paragraph is enough. |
| DECIDE-2 | Glossary terms are opinionated and implementation-free | One term per concept, the others under "avoid", one or two sentences on what it is. No implementation detail, no scratch notes, no specifications. |
| DECIDE-3 | Knowledge in tables with calibration | Glossaries, research documents and plan tables have fixed columns, in the repository, and every row's calibration is written (EVID-1): "unverified", never blank. The decision record is the prose exception, one paragraph. Prose elsewhere is for the reader who already has the table. |
| DECIDE-4 | Records carry no names | Systems and roles, never individuals. |
| DECIDE-5 | One file per topic, never another's file | Check the path before writing. A file not created in this session is not overwritten; a new dated document sits beside the earlier one. |
| DECIDE-6 | Conflicts with a record are surfaced | "Contradicts record 0003 (attribution patterns by default); worth reopening because …" rather than a silent override. |

## During design

- Before exploring an area, read `GLOSSARY.md` and the records under `docs/adr/` that touch it;
  the triggers for conflicts fire only on what was read.
- When a term conflicts with the glossary, say so at once: "The glossary defines cancellation as
  X; this means Y. Which is it?"
- When a term is vague or overloaded, propose the canonical one.
- Stress-test relationships with concrete scenarios that probe the edges.
- When a statement about how something works disagrees with the code, surface the contradiction.
- Resolve a term, write it down then. Do not batch glossary updates.

## What qualifies for a decision record

Architectural shape. Integration patterns between contexts. Technology choices with lock-in that
would take a quarter to swap. Boundary and scope decisions, the explicit no as much as the yes.
Deliberate deviations from the obvious path, so the next engineer does not "fix" them.
Constraints not visible in the code. Rejected alternatives when the rejection is non-obvious.

## Companion skills

| Need | Skill |
|---|---|
| The questions that surface the decisions | grill-plan |
| Calibration tags for the rows | evidence |
| The plan's Decisions table for reversible choices | plan-project |
