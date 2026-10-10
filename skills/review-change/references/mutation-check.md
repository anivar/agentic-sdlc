# Mutation check

REVIEW-4: a test is judged against the code it exercises, never from its body or its name.

## Procedure

1. Pick one condition the change adds or alters: a comparison, a guard, a boolean, a boundary.
2. Copy the file aside. Invert the condition in place: drop a negation, swap `&&` for `||`, move
   a boundary by one, return the other branch.
3. Run the suite the repository defines, exactly as CI runs it.
4. Restore the file from the copy. Confirm with `git diff` that nothing else changed.
5. Record the result as a count: `mutants 3, caught 2, survived 1`.

## Reading the result

- A mutant the suite catches: the test earns its place.
- A mutant that survives: a finding. Name the test case that is missing, not "add tests".
- A mutant that changed nothing (the suite passes because the mutated line is unreachable or
  duplicated elsewhere): proves nothing about the test, and is itself a finding about dead or
  duplicated code.

## What the check does not do

It does not replace a project-wide mutation score. It answers one question for one change:
would this test have noticed if the new code were wrong. Enumerate the branches the change adds
before repairing a test; a better-shaped test often beats a patched one. Tests that assert only
a range or a sign are the class of test that lets wrong figures through; prefer a hand-derived
expected value with the derivation in the test's docstring.

## In a worktree

Run the probe in a worktree or a temporary repository when the checkout carries uncommitted
work (REVIEW-10). Never on the working copy with changes you have not committed.
