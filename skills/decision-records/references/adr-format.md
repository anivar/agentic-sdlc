# Decision record format

Records live in `docs/adr/` with sequential numbers: `0001-slug.md`, `0002-slug.md`. Scan the
folder for the highest number and add one.

## Template

```markdown
# <Short title of the decision>

Status: proposed | accepted | deprecated | superseded by ADR-NNNN · Date: <date> · Decides: <role>

<One to three sentences: the context, what was decided, and why. Calibration on each factual
clause: Verified, Measured, Inferred.>
```

That is the whole record. Add a section only when it earns its place:

- **Options considered**: only when the rejected alternatives are worth remembering, as a table
  with the reason each lost.
- **Consequences**: only when a downstream effect is not obvious.
- **Compatibility**: when the decision changes a client-visible behaviour, the per-client table
  from the plan (PLAN-4).

## Rules

- Written in the decider's words where the decider gave them (VOICE-12); otherwise in plain
  declaratives, current state only (VOICE-2).
- No names of individuals (DECIDE-4). "The platform team" or "the decider", never a person.
- A record is never edited to change history; a later record supersedes it.
