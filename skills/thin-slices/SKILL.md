---
name: thin-slices
description: >
  Land work as thin, complete, reviewable slices: one pull request per plan step, nothing
  half-done on the shared branch, scope held to the step, verification run once per change,
  staging by path with the index read before the commit, a go-ahead for every commit, push and
  post, no force push to a protected branch, no key-shaped literals, no secret ever printed,
  production read-only. This is the execution discipline the hook enforces.
  Triggers on: "implement", "build", "ship", "land this", "next step from the plan",
  "commit", "push", "open a PR", "is it ready to merge", "what should I stage".
license: MIT
user-invocable: true
compatibility: Any git repository; the hook side needs the agentic-sdlc plugin in Claude Code.
metadata:
  author: Anivar Aravind
  author_url: https://anivar.net
  version: 1.0.0
  tags: implementation, git, pull-requests, staging, secrets, incremental
  derived_from: incremental-implementation (addyosmani/agent-skills, MIT) for the slice cycle and scope discipline; the git, secret and go-ahead rules are the author's own
  rules: SLICE-1 SLICE-2 SLICE-3 SLICE-4 SLICE-5 SLICE-6 SLICE-7 SLICE-8 STAGE-1 PUSH-1 PUSH-2 SECRET-1 SECRET-2 PROD-1 ASK-1 ASK-2 ASK-3 TRACE-1 REVIEW-6 TEST-5
---

# Thin slices

Implement one piece, test it, verify it, show it, then the next. Each slice leaves the system
working. The hook turns the git and forge rules below into mechanisms; the rest are the habits
that keep a change small enough to review.

## The rules

| Id | Rule | In practice |
|---|---|---|
| SLICE-1 | One change per step, reviewable in one sitting | One pull request per plan step, with clear acceptance. Around a hundred changed lines reads in one sitting. |
| SLICE-2 | Nothing half-done reaches the shared branch | A step merges complete, with tests, docs and its changelog entry, or waits. Incomplete work stays behind a flag or on its branch. |
| SLICE-3 | Scope discipline | Only what the step requires. Note adjacent cleanups, unused imports, old syntax; leave them for their own step. |
| SLICE-4 | Verify once per change | Run each check after a change that could affect it. A pass on unchanged code is not repeated. |
| SLICE-5 | Stage by path and read the index | `git add <path>`; `git add -p` when another session may have touched the file; read `git diff --cached --stat` before committing. Never `git add -A` (STAGE-1, hook deny). |
| SLICE-6 | A go-ahead per commit, per push, per post | Each waits for its own yes. Approval for one does not extend to the next (ASK-1, ASK-2, ASK-3, hook ask). |
| SLICE-7 | Auto-merge only where allowed | Armed only where the decider allowed it for that repository and branch. A merge to a release branch is a deliberate human act. |
| SLICE-8 | Fresh new files, confirmed deletions | Check the path is absent before writing a new file. Check a file is untracked before deleting it, or get the deletion confirmed. |
| STAGE-1 | Stage by path | Hook: `git add -A`, `--all` or `-u` without a narrowing path, a root pathspec such as `.`, and `git commit -a` are refused. `git add -A src/` passes. |
| PUSH-1 | No force push to a protected branch | Hook: refused. A protected branch moves by merged pull request only. |
| PUSH-2 | Moving a tag is confirmed and explained | Hook: asks, and says that every workflow triggered on tag pushes runs again and release assets may be rebuilt. |
| SECRET-1 | No key-shaped literals | Hook: staged changes are scanned before the commit; CI runs gitleaks. Tests generate keys at runtime; documentation samples use placeholders. |
| SECRET-2 | Never print a secret | Variable name, `file:line`, length or hash. Exclude token-bearing lines before summarising a log. Never trust a masking regex. |
| PROD-1 | Production is read-only | Unless the decider says otherwise for that action. |
| REVIEW-6 | Confirm the diff is absent before merging | And re-diff a conflict resolution against the target's current file. |
| TEST-5 | Gate on exit codes | `check && test && git commit`. |
| TRACE-1 | An untraceable gated command is confirmed | Hook: a command that mentions a commit, push, bulk add or forge write the parser cannot trace (a variable, an interpreter, an unusual wrapper) asks. |

## The cycle

1. Implement the smallest complete piece. Ask first what the simplest thing is that could work;
   three similar lines beat a premature abstraction.
2. Run the repository's own checks (TEST-5).
3. Show what changed, what it deliberately leaves out, and what is next. Before a pull request
   exists, say in a few plain sentences what it does, why, and what it leaves out.
4. Commit on the go-ahead, with a first line that is short, imperative and standalone, and no
   tool attribution (ATTR-1).
5. Next slice. Carry forward; do not restart.

## Slicing

Vertical slices by preference: one complete path through the stack per slice. Risk-first when
one piece is uncertain: prove it before building on it. Contract-first when two sides develop in
parallel: the contract is slice zero. A feature that is not ready for users merges behind a flag
with a safe default.

## Commit text

The first line is short, imperative and standalone. The body says what changes and why, and
names what it leaves out. No ticket keys, incident numbers or customer names in code, comments,
tests or fixtures; they belong in the commit title and the change description. The signer is the
operator of record: no tool trailer, no generated-with footer (ATTR-1).

## Companion skills

| Need | Skill |
|---|---|
| Tests for the slice | test-first |
| The review before merge | review-change |
| The plan step the slice implements | plan-project |
| The ticket it closes | cut-tickets |
