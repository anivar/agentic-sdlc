## Rules that bind

This repository runs with the agentic-sdlc skills and hook (https://github.com/anivar/agentic-sdlc).
The rule ids below are stable and defined in that repository's `rules/registry.json`.

- Every commit, push and post waits for its own go-ahead (ASK-1, ASK-2, ASK-3). Drafts are
  shown in the conversation and never posted.
- Stage by path; never `git add -A` (STAGE-1). No force push to a protected branch (PUSH-1).
- No tool attribution in commits, pull requests or issues (ATTR-1). The signer is the operator
  of record for the change.
- No key-shaped literals anywhere, not in tests, fixtures or samples (SECRET-1). Never print a
  secret (SECRET-2).
- Commits are gated on exit codes (TEST-5). One pull request per plan step, complete or not at
  all (SLICE-1, SLICE-2).
- Every factual claim carries Verified, Measured, Inferred or Planned (EVID-1).
- Before exploring an area, read `GLOSSARY.md` and the records under `docs/adr/` that touch it;
  output that contradicts a record says so (DECIDE-6).

Where things live: tickets and labels in `docs/agents/tracker.md`; decision records, glossary
and voice settings in `docs/agents/conventions.md`; hook settings in `.agentic-sdlc.json`.
