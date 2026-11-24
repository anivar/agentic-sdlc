---
name: review-change
description: >
  Review a change the way a reviewer who will be held to it does: findings only on the change
  that introduced the code, verified at its head sha, one finding per thread in Conventional
  Comments with the defect, file:line, consequence, rule and required behaviour, a two to four
  line summary that ends in a decision, a mutation check before trusting a test, dependency
  bumps one at a time, an adversarial read of your own work before anyone else sees it, a
  fresh-context reader for a plan or design you drafted, and one answer for every finding.
  Triggers on: "review", "code review", "review this PR", "review this MR", "review the diff",
  "LGTM?", "is this safe to merge", "self-review", a diff pasted inline, "before I push",
  "review this plan", "review the design", "fresh eyes".
license: MIT
compatibility: Any repository on GitHub or GitLab; the mutation check needs a runnable test suite.
metadata:
  author: Anivar Aravind
  author_url: https://anivar.net
  version: 1.0.0
  tags: code-review, conventional-comments, mutation-testing, pull-request, merge-request
  derived_from: code-review-and-quality (addyosmani/agent-skills, MIT) for the review walk, the dependency section and the mutation probe (invert one condition, run the suite, restore); the Elephant-Goldfish Model (google/elephant-goldfish-model, Apache-2.0) for the fresh-context reader, the paraphrase before findings and the answer kinds, restated without its text; the finding format, the mutant count and dead-mutant reading, and the self-review are the author's own
  rules: REVIEW-1 REVIEW-2 REVIEW-3 REVIEW-4 REVIEW-5 REVIEW-6 REVIEW-7 REVIEW-8 REVIEW-9 REVIEW-10 REVIEW-11 REVIEW-12 EVID-3 EVID-8 EVID-9 VOICE-9 VOICE-11 PLAN-7 SLICE-1 SECRET-1 SECRET-2
---

# Review a change

A review is a set of findings a second reader can act on without the reviewer in the room,
and a decision. Everything else is noise.

## The rules

| Id | Rule | In practice |
|---|---|---|
| REVIEW-1 | Findings on the introducing change, at the head sha | Open the change's head sha; every `file:line` is at that sha, or reads "from the inline diff" when there is none. A defect that predates the change goes to its own item, not this review. Essential findings only. |
| REVIEW-2 | One finding per thread, in Conventional Comments | Label, defect, `file:line`, consequence, rule broken, required behaviour, at most one suggestion. No hedges. Format in `references/finding-format.md`. |
| REVIEW-3 | The summary carries the decision | Two to four lines. The last one is the decision: approve, request changes, or needs a decider, with the open point and who decides. |
| REVIEW-4 | Mutate before trusting a test | Judge a test against the code it exercises, not its name. Invert one condition the change adds, run the suite, restore the file. A mutant that survives is a finding naming the missing case. A mutant that changed nothing proves nothing. Report mutants and catches as a count. Procedure in `references/mutation-check.md`. |
| REVIEW-5 | Review rounds fix only real defects | Cosmetic bot suggestions get a one-line verdict and no push. On your own change, answer every bot thread (fixed, or refuted with evidence, as REVIEW-12 defines) and resolve it. On someone else's change, reply and leave resolution to the author. |
| REVIEW-6 | Confirm the diff is absent before merging | Before reporting on, merging or closing a change, confirm its diff is not already on the target. Check a stacked change against its parent's tip. Re-diff a conflict resolution against the target's current file. |
| REVIEW-7 | Adversarial self-review before showing | Which claim rests on something not opened this session. Which number was recalled rather than computed. Which action does damage if the premise is wrong. Fix what it finds before any push, merge or live change. |
| REVIEW-8 | Sort proposals by what ships | Internals-only, or changes the released artifact (versioning, signing, distribution). The second needs a strong reason, stated. |
| REVIEW-9 | One dependency per change | Changelog read, package isolated, suite before and after, lockfile diff reviewed, never hand-edited. |
| REVIEW-10 | Test and infrastructure work leaves shipped code alone | No change to shipped code without an explicit ask. Negative-test probes run in a worktree or a temporary repository. |
| REVIEW-11 | A fresh reader reviews a draft | Before a plan or design you drafted goes to the decider for approval, one subagent reads it with the document, the ask and the repository, and nothing else from your conversation. It paraphrases before it finds. More readers need the decider's yes. With no subagent, or after two failures, say "self-review only". Procedure below and in `references/fresh-reader.md`. |
| REVIEW-12 | Every finding gets one answer | Fixed, accepted with the change proposed, refuted with evidence the reviewer could have read, given to the decider, or (a nitpick, a cosmetic bot suggestion) declined in one line. Never refute a comprehension gap, never change a label or decoration. The decider sees every answer; a refutation stands only when the decider does not overrule it. A fixed finding raised again re-opens. A reviewer that returned nothing did not run. Format in `references/finding-format.md`. |

## The walk

1. Understand the intent: what the change claims, which plan step or ticket it implements,
   what behaviour changes. Say up front whether it breaks existing behaviour.
2. Read the tests first, then run REVIEW-4 on at least one new condition when a suite can run;
   otherwise the summary says "mutation check not run".
3. Walk the implementation on five axes: correctness (edge and error paths, races, state),
   readability (names, control flow, dead code, a conditional bolted onto an unrelated flow),
   architecture (does the refactor reduce concepts or relocate them; feature logic in a shared
   module; implicit type boundaries), security (input at boundaries, secrets, injection,
   untrusted external data), performance (unbounded loops, N+1, missing pagination).
4. Size the change (SLICE-1): around a hundred changed lines reads in one sitting; a thousand
   splits. Refactoring and behaviour change are two changes.
5. Write the findings (REVIEW-2), order them by payback, then the summary (REVIEW-3).

## Security and dependencies

The security axis asks, for every new path: input validated at the boundary, authorisation
checked, no secret in code or logs (SECRET-1, SECRET-2), no untrusted data reaching a shell, a
query or a template, and what a dependency change brings in. A new dependency answers five
questions before it lands (EVID-9): the licence, the maintenance record (last release, open
issues), the size and what it pulls in, the vulnerability record, and whether the standard library
or an existing dependency already covers it. Upgrades follow REVIEW-9.

## Approval standard

Approve when the change improves the code and follows the repository's conventions, even if it
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

The self-review runs in the context that wrote the draft, so it shares the draft's blind spots: it
knows what the author meant and reads that into the text. A plan or a design gets a second read,
from a reader who knows only the text, before it goes to the decider for approval (REVIEW-11).
Other documents may get one when the decider asks.

## A draft under fresh eyes

1. Finish the self-review (REVIEW-7) first, so the reader spends its read on what you could not
   see.
2. Spawn one subagent with the brief in `references/fresh-reader.md`, a read-only type where the
   harness has one. Fill in the document's path and the sha, or paste the document's text
   verbatim when it exists only in the conversation, and paste the decider's ask verbatim when
   there is one. Give it read access to the repository and to the sources the document cites.
   Give it nothing else: no summary of the session, no conclusion you hope it reaches, no list of
   issues you already know. A reader told what to look for finds that and stops.
3. Compare the reader's paraphrase with what you meant. Each place where they differ is a finding
   against the document, not against the reader.
4. Open every line the reader cites before you act on it (EVID-3).
5. Answer each finding (REVIEW-12) in the form in `references/finding-format.md`.
6. Show the decider the paraphrase, the decisions the reader found unrecorded, the claims it could
   not check, the findings and the answers. Unrecorded decisions and findings given to the decider
   come first: they need the decider's knowledge, not only a yes. In a plan, each unrecorded
   decision becomes an open row in the Decisions table with options, who decides and by when
   (PLAN-7), or a question in the next grill-plan round.

If the reader fails, times out or returns nothing, retry once. After a second failure, report the
reader as not run and the review as a self-review only. A second round runs when the decider asks
for one, with a new reader; settled findings carry over and are not re-opened.

## Companion skills

| Need | Skill |
|---|---|
| Calibration tags and the sha rule | evidence |
| The voice of threads and summaries | plain-voice |
| Tests that are worth the mutation check | test-first |
| Keeping the change small enough to review | thin-slices |
| Comparing a plan with the ask before the fresh read | plan-project |

## Sources

The approval standard and the disagreement hierarchy follow Google's engineering practices
(CC BY 4.0). The mutation probe follows code-review-and-quality (addyosmani/agent-skills, MIT).
The fresh-context reader, the paraphrase before findings and the answer kinds follow the
Elephant-Goldfish Model (google/elephant-goldfish-model, Apache-2.0), restated in this skill's
own words.
