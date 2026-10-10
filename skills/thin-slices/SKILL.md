---
name: thin-slices
description: >
  Land work as thin, complete, reviewable slices: one pull request per plan step, nothing
  half-done on the shared branch, scope held to the step, verification run once per change,
  staging by path with the index read before the commit, a go-ahead for every commit, push and
  post, no force push to a protected branch, no key-shaped literals, no secret ever printed,
  production read-only. This is the execution discipline the hook enforces.
  Triggers on: "implement the next step", "land this", "next step from the plan", "ship this
  slice", "ready to commit", "open a PR", "is it ready to merge", "what should I stage".
license: MIT
compatibility: Any git repository; the hook side needs the agentic-sdlc plugin in Claude Code.
metadata:
  author: Anivar Aravind
  author_url: https://anivar.net
  version: 1.0.0
  tags: implementation, git, pull-requests, staging, secrets, incremental
  derived_from: incremental-implementation (addyosmani/agent-skills, MIT) for the slice cycle and scope discipline; the git, secret and go-ahead rules are the author's own
  rules: SLICE-1 SLICE-2 SLICE-3 SLICE-4 SLICE-5 SLICE-6 SLICE-7 SLICE-8 STAGE-1 PUSH-1 PUSH-2 SECRET-1 SECRET-2 SECRET-3 PROD-1 ASK-1 ASK-2 ASK-3 TRACE-1 GUARD-1 REVIEW-6 TEST-5 ATTR-1 TICKET-3 TICKET-4
---

# Thin slices

Implement one piece, test it, verify it, show it, then the next. Each slice leaves the system
working. The hook turns the git and forge rules below into mechanisms; the rest are the habits
that keep a change small enough to review.

## The rules

| Id | Rule | In practice |
|---|---|---|
| SLICE-1 | One change per step, reviewable in one sitting | One pull request per plan step, with clear acceptance. Around a hundred changed lines reads in one sitting. |
| SLICE-2 | Nothing half-done reaches the shared branch | A step merges complete, with tests, docs and, where the repository keeps one, its changelog entry, or waits. Incomplete work stays behind a flag or on its branch. |
| SLICE-3 | Scope discipline | Only what the step requires. Note adjacent cleanups, unused imports, old syntax; leave them for their own step. |
| SLICE-4 | Verify once per change | Run each check after a change that could affect it. A pass on unchanged code is not repeated. |
| SLICE-5 | Stage by path and read the index | `git add <path>`; when another session may have touched a file, re-read `git diff <file>` and stage whole files by path, or the hunks with `git apply --cached <patch>`; read `git diff --cached --stat` before committing. Never `git add -A` (STAGE-1, hook deny). |
| SLICE-6 | A go-ahead per commit, per push, per post | Each waits for its own yes. Approval for one does not extend to the next (ASK-1, ASK-2, ASK-3, hook ask). |
| SLICE-7 | Auto-merge only where allowed | Armed only where the decider allowed it for that repository and branch. A merge to a release branch is a deliberate human act. |
| SLICE-8 | Fresh new files, confirmed deletions | Check the path is absent before writing a new file. Check a file is untracked before deleting it, or get the deletion confirmed. |
| STAGE-1 | Stage by path | Hook: `git add -A`, `--all` or `-u` without a narrowing path, a root pathspec such as `.`, and `git commit -a` are refused. `git add -A src/` passes. |
| PUSH-1 | No force push to a protected branch | Hook: refused. A protected branch moves by merged pull request only. |
| PUSH-2 | Moving a tag is confirmed and explained | Hook: asks, and says that every workflow triggered on tag pushes runs again and release assets may be rebuilt. |
| SECRET-1 | No key-shaped literals | Hook: staged changes are scanned before the commit; CI runs gitleaks. Tests generate keys at runtime; documentation samples use placeholders. |
| SECRET-2 | Never print a secret | Variable name, `file:line`, length or hash. Exclude token-bearing lines before summarising a log. Never trust a masking regex. |
| PROD-1 | Production is read-only | Unless the decider says otherwise for that action. The production targets are the ones `docs/agents/conventions.md` names. |
| REVIEW-6 | Confirm the diff is absent before merging | And re-diff a conflict resolution against the target's current file. |
| TEST-5 | Gate on exit codes | `check && test`, then the commit on its go-ahead, gated on the exit codes. |
| TRACE-1 | An untraceable gated command is confirmed | Hook: a command that mentions a commit, push, bulk add or forge write the parser cannot trace (a variable, an interpreter, an unusual wrapper) asks. |

## The cycle

1. Read the glossary and the records that touch the area (decision-records), then implement
   the smallest complete piece. Ask first what the simplest thing is that could work; three
   similar lines beat a premature abstraction.
2. Run the repository's own checks (TEST-5).
3. Show what changed, what it deliberately leaves out, and what is next, in the
   change-description form plain-voice owns.
4. Commit on the go-ahead, with a first line that is short, imperative and standalone, and no
   tool attribution (ATTR-1).
5. Next slice. Carry forward; do not restart.

## Slicing

Vertical slices by preference: one complete path through the stack per slice. Risk-first when
one piece is uncertain: prove it before building on it. Contract-first when two sides develop in
parallel: the contract is slice zero. A feature that is not ready for users merges behind a flag
with a safe default.

## Commit text

Commit and pull request text follows the change-description rules plain-voice owns: a short,
imperative, standalone first line; what the change leaves out; no identifiers in code or fixtures
and full links for every reference (TICKET-3, TICKET-4). The signer is the operator of record:
no tool trailer, no generated-with footer (ATTR-1).

## A slice, end to end

1. Plan step P2.3 says: "the search endpoint rejects a page token with 400". One slice.
2. Failing test first (`test-first`), then the smallest handler change that passes it.
3. `just check` exits 0. Nothing else in the tree changed (SLICE-3): a stray formatting fix in
   another file is noted for its own step, not included.
4. Stage by path: `git add src/search.py tests/test_search.py`; read `git diff --cached --stat`.
5. Say what it does, why, and what it leaves out: "Rejects a page token with 400 and a
   `page_token_unsupported` code. Pagination itself is still not implemented; that is P2.4."
6. On the go-ahead: `git commit -m "Reject a page token on search with 400"` (`-s` where the
   repository requires a sign-off). The hook asks (ASK-1), the decider answers, the commit runs.
   No trailer names a tool (ATTR-1).
7. On the next go-ahead: `git push`, a pull request with the same three sentences, the review
   from `review-change`, merge when the checks pass. Then P2.4.

## Hooks and secret files

The repository's hooks run on every commit and push. Never pass `--no-verify` or `commit -n`, and
never point git at another hooks directory or config, on the command line or through
`git config` (GUARD-1); when a hook is wrong, the fix is a change to the hook in its own slice. A file that holds credentials by name
(`.env`, a private key, `.netrc`, `.npmrc`, `credentials.json`, a PEM or keystore file) is not
read, copied or sent without a go-ahead (SECRET-3); name the variable or the file's length or
hash instead (SECRET-2).

## Companion skills

| Need | Skill |
|---|---|
| Tests for the slice | invoke `test-first` |
| The review before merge | invoke `review-change` |
| The plan step the slice implements | plan-project |
| The ticket it closes | cut-tickets |
