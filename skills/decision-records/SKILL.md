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
user-invocable: true
compatibility: Any repository. Defaults to GLOSSARY.md at the root and docs/adr/; a repository may point docs/agents/conventions.md elsewhere.
metadata:
  author: Anivar Aravind
  author_url: https://anivar.net
  version: 1.0.0
  tags: adr, glossary, domain-model, research, documentation
  derived_from: domain-modeling (mattpocock/skills, MIT) for the glossary and ADR formats and the lazy-creation rule; the calibration, naming and research-document rules are the author's own
  rules: DECIDE-1 DECIDE-2 DECIDE-3 DECIDE-4 DECIDE-5 DECIDE-6 EVID-10 EVID-1 VOICE-2
---

# Decision records

Three kinds of record, each with a format in `references/`:

| Record | Lives at | Format |
|---|---|---|
| Glossary | `GLOSSARY.md` at the root, or one per context listed in `GLOSSARY-MAP.md` | `references/glossary-format.md` |
| Decision record | `docs/adr/NNNN-slug.md` | `references/adr-format.md` |
| Research document | `<topic folder>/<date>-<question>.md` | `references/research-document.md` |

Create files lazily: a glossary when the first term is resolved, `docs/adr/` when the first
decision qualifies, a research document when a source taught something.

## The rules

| Id | Rule | In practice |
|---|---|---|
| DECIDE-1 | A record for a hard-to-reverse, surprising trade-off | All three must hold. Easy to reverse: you will just reverse it. Not surprising: nobody will wonder why. No real alternative: nothing to record. One paragraph is enough. |
| DECIDE-2 | Glossary terms are opinionated and implementation-free | One term per concept, the others under "avoid", one or two sentences on what it is. No implementation detail, no scratch notes, no specifications. |
| DECIDE-3 | Knowledge in tables with calibration | Tables with fixed columns, in the repository. Every row's calibration is written: "unverified", never blank. Prose is for the reader who already has the table. |
| DECIDE-4 | Records carry no names | Systems and roles, never individuals. A change that concerns a person carries no name in its branch, commit or description, and is not filed on its own: fold it into a neutral tidy-up. |
| DECIDE-5 | One file per topic, never another's file | Check the path before writing. A file not created in this session is not overwritten; a new dated document sits beside the earlier one. |
| DECIDE-6 | Conflicts with a record are surfaced | "Contradicts record 0007 (event-sourced orders); worth reopening because …" rather than a silent override. |

## During design

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
