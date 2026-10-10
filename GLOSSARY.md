# agentic-sdlc

The vocabulary this repository uses for its own rules, mechanisms and documents. One term per
concept; the words to avoid are listed so the documents do not drift.

## Language

| Term | Is | Avoid | Calibration |
|---|---|---|---|
| Rule | One normative statement with a stable id in `rules/registry.json`, an owner skill and a mechanism list. | guideline, principle, check (for the statement) | Verified in `schemas/registry.schema.json` |
| Mechanism | What enforces a rule without negotiation: the hook, the CI check or the ruleset. A rule whose only mechanism is `skill` is text an agent follows. | guardrail, gate (as a synonym) | Verified in `docs/coverage.md` |
| Decision | What the hook returns for one command: allow, ask or deny, with the rule ids and a reason. Deny outranks ask outranks allow. | verdict, block | Verified in `src/agentic_sdlc/guard.py` |
| Gated command | A commit, a push, a bulk add or a forge write: the operations the hook always has a decision about. | dangerous command | Verified in `src/agentic_sdlc/command.py` |
| Traced | A simple command the parser recognised as `git`, `gh` or `glab` after following wrappers, substitutions and `cd`. An untraced gated command asks (TRACE-1). | parsed, understood | Verified in `src/agentic_sdlc/command.py` |
| Decider | The role that approves plans, settles decisions and gives the go-ahead for a commit, a push or a post. A role, not a person. | user, owner, manager | Verified in `skills/plan-project/SKILL.md` |
| Go-ahead | The decider's explicit yes for one commit, one push or one post. It does not carry over to the next. | approval (in general), permission | Verified in rules ASK-1 to ASK-3 |
| Attribution | Text in a change that names a tool as author, co-author, generator or assistant. The signer is the operator of record; a role marker such as `Operated-by: agent` is not attribution. | credit, co-authorship | Verified in rule ATTR-1 |
| Operator of record | The person who signs a change and answers for it. | author (when the agent typed it) | Verified in README "Why no tool attribution" |
| Origination | Whether a human or an agent operated a change. Recorded, when a repository wants it, by a role trailer; never by a product name. | AI-generated flag | Verified in README "Why no tool attribution" |
| Evidence tag | Verified, Measured, Inferred or Planned on a factual clause. A level is never upgraded. | confidence level | Verified in `skills/evidence/SKILL.md` |
| Slice | One complete, reviewable change that leaves the system working: one pull request per plan step. | increment, chunk | Verified in `skills/thin-slices/SKILL.md` |
| Seam | Michael Feathers' term: where a module's interface lives and behaviour can be altered without editing in that place. | boundary | Verified in `skills/deep-modules/SKILL.md` |
| Coverage table | `docs/coverage.md`, generated from the registry: every rule, its mechanisms and the skills that cite it. | matrix | Verified in `src/agentic_sdlc/cli.py` |
