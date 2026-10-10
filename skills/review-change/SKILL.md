---
name: review-change
description: >
  Review a change the way a reviewer who will be held to it does: findings only on the change
  that introduced the code, verified at its head sha, one finding per thread in Conventional
  Comments with the defect, file:line, consequence, rule and required behaviour, a two to four
  line summary that ends in a decision, a mutation check before trusting a test, dependency
  bumps one at a time, and an adversarial read of your own work before anyone else sees it.
  Triggers on: "review", "code review", "review this PR", "review this MR", "review the diff",
  "LGTM?", "is this safe to merge", "self-review", a diff pasted inline, "before I push".
license: MIT
user-invocable: true
compatibility: Any repository on GitHub or GitLab; the mutation check needs a runnable test suite.
metadata:
  author: Anivar Aravind
  author_url: https://anivar.net
  version: 1.0.0
  tags: code-review, conventional-comments, mutation-testing, pull-request, merge-request
  derived_from: code-review-and-quality (addyosmani/agent-skills, MIT) for the review walk and the dependency section; the finding format, the mutation check and the self-review are the author's own
  rules: REVIEW-1 REVIEW-2 REVIEW-3 REVIEW-4 REVIEW-5 REVIEW-6 REVIEW-7 REVIEW-8 REVIEW-9 REVIEW-10 EVID-3 EVID-8 VOICE-11
---

# Review a change

A review is a set of findings a second reader can act on without the reviewer in the room,
and a decision. Everything else is noise.

## The rules

| Id | Rule | In practice |
|---|---|---|
| REVIEW-1 | Findings on the introducing change, at the head sha | Open the change's head sha; every `file:line` is at that sha. A defect that predates the change goes to its own item, not this review. Essential findings only. |
| REVIEW-2 | One finding per thread, in Conventional Comments | Label, defect, `file:line`, consequence, rule broken, required behaviour, at most one suggestion. No hedges. Format in `references/finding-format.md`. |
| REVIEW-3 | The summary carries the decision | Two to four lines. The last one is the decision: approve, request changes, or needs a decider, with the open point and who decides. |
| REVIEW-4 | Mutate before trusting a test | Judge a test against the code it exercises, not its name. Invert one condition the change adds, run the suite, restore the file. A mutant that survives is a finding naming the missing case. A mutant that changed nothing proves nothing. Report mutants and catches as a count. Procedure in `references/mutation-check.md`. |
| REVIEW-5 | Review rounds fix only real defects | Cosmetic bot suggestions get a one-line verdict and no push. On your own change, answer every bot thread (fixed, or refuted with evidence) and resolve it. On someone else's change, reply and leave resolution to the author. |
| REVIEW-6 | Confirm the diff is absent before merging | Before reporting on, merging or closing a change, confirm its diff is not already on the target. Check a stacked change against its parent's tip. Re-diff a conflict resolution against the target's current file. |
| REVIEW-7 | Adversarial self-review before showing | Which claim rests on something not opened this session. Which number was recalled rather than computed. Which action does damage if the premise is wrong. Fix what it finds before any push, merge or live change. |
| REVIEW-8 | Sort proposals by what ships | Internals-only, or changes what ships (versioning, signing, distribution). The second needs a strong reason, stated. |
| REVIEW-9 | One dependency per change | Changelog read, package isolated, suite before and after, lockfile diff reviewed, never hand-edited. |
| REVIEW-10 | Test and infrastructure work leaves shipped code alone | No change to shipped code without an explicit ask. Negative-test probes run in a worktree or a temporary repository. |

## The walk

1. Understand the intent: what the change claims, which plan step or ticket it implements,
   what behaviour changes. Say up front whether it breaks existing behaviour.
2. Read the tests first, then run REVIEW-4 on at least one new condition.
3. Walk the implementation on five axes: correctness (edge and error paths, races, state),
   readability (names, control flow, dead code, a conditional bolted onto an unrelated flow),
   architecture (does the refactor reduce concepts or relocate them; feature logic in a shared
   module; implicit type boundaries), security (input at boundaries, secrets, injection,
   untrusted external data), performance (unbounded loops, N+1, missing pagination).
4. Size the change: around a hundred changed lines reads in one sitting; a thousand splits.
   Refactoring and behaviour change are two changes.
5. Write the findings (REVIEW-2), order them by payback, then the summary (REVIEW-3).

## Approval standard

The standard and the disagreement hierarchy below follow Google's engineering practices
(CC BY 4.0). Approve when the change improves the code and follows the repository's conventions, even if it
is not how you would have written it. Block only for a defect, a security issue, a lost test, or
a structure that makes the next change harder. "I'll clean it up later" is a decline: the cleanup
lands before the merge or as its own tracked item with an owner.

## Disagreements

Facts and data over preferences. The style guide decides style. Design is judged on engineering
grounds. Consistency with the codebase is acceptable when it does not degrade it. Comment on the
code, never the person (VOICE-11).

## Reviewing your own work

Run REVIEW-7 on every plan, finding, draft and change before it is shown, unasked. Treat your
own earlier output and any agent's output as a lead (EVID-3): open every cited line again. Re-read
a file before asserting its state (EVID-8).

## Companion skills

| Need | Skill |
|---|---|
| Calibration tags and the sha rule | evidence |
| The voice of threads and summaries | plain-voice |
| Tests that are worth the mutation check | test-first |
| Keeping the change small enough to review | thin-slices |
