---
name: test-first
description: >
  Build and fix test-first at seams agreed in advance: write the failing test, write only enough
  code to pass it, take expected values from an independent source rather than from the code,
  mock only at system boundaries, gate every commit on exit codes, run suites one at a time
  against shared state, and enumerate the branches before repairing a failing test.
  Triggers on: "TDD", "test first", "red green", "write a failing test", "add tests",
  "integration test", "fix the test", "the test is flaky", "coverage", "what should we test".
license: MIT
user-invocable: true
compatibility: Any language with a test runner the repository already defines.
metadata:
  author: Anivar Aravind
  author_url: https://anivar.net
  version: 1.0.0
  tags: tdd, testing, seams, mocking, integration-tests
  derived_from: tdd (mattpocock/skills, MIT) for the seam-first loop and the good-and-bad-tests catalogue; the gating, independence and repair rules are the author's own
  rules: TEST-1 TEST-2 TEST-3 TEST-4 TEST-5 TEST-6 TEST-7 REVIEW-4 DESIGN-2 EVID-5 SLICE-4
---

# Test first

The loop is red then green. These rules make the loop produce tests worth keeping. Every
section applies on every cycle. Read the glossary first so test names use the project's words.

## The rules

| Id | Rule | In practice |
|---|---|---|
| TEST-1 | Seams agreed before tests | Write down the seams under test and confirm them with the decider. Each proposed seam gets one line on what it catches and what it misses. No test at an unconfirmed seam. |
| TEST-2 | Red before green | The failing test first, then only enough code to pass it. One seam, one test, one minimal implementation per cycle. No speculative features. Refactoring belongs to review-change, not to the loop. |
| TEST-3 | Expected values from an independent source | A known-good literal, a worked example, the specification, with the derivation in the test. Never `expect(add(a, b)).toBe(a + b)`. A test that asserts only a range or a sign is the class that let wrong figures through a passing suite. |
| TEST-4 | Mock only at system boundaries | External services, time, randomness, the file system. Never the code under test, pure functions, value objects or internal collaborators. Inject boundaries; prefer one function per external operation over a generic fetcher. |
| TEST-5 | Gate on exit codes | `check && test && git commit`. A check whose failure is printed and ignored gates nothing. After a pass on unchanged code, do not re-run for reassurance (SLICE-4). |
| TEST-6 | Suites one at a time against shared state | A number that moves between identical runs is a harness artefact (EVID-5). Run suites that share a database one at a time; compare named failures, not counts. |
| TEST-7 | Enumerate branches before repairing | List the branches the code takes before touching a failing test. A better-shaped test often beats a patched one. Confirm with the mutation check (REVIEW-4). |

## What a good test is

It verifies behaviour through the public interface (DESIGN-2). It reads like a specification:
"user can check out with a valid cart" says what capability exists, and survives refactors
because it does not care about internal structure. Examples and anti-patterns are in
`references/good-and-bad-tests.md`.

## Anti-patterns

- Implementation-coupled: mocks internal collaborators, tests private methods, verifies through
  a side channel. The tell: it breaks on a refactor that changed no behaviour.
- Tautological: the assertion recomputes the expected value the way the code does.
- Horizontal slicing: all tests first, then all implementation. Tests of imagined behaviour go
  insensitive to real changes. Work in vertical slices: one test, one implementation, repeat.

## Companion skills

| Need | Skill |
|---|---|
| Where the seam belongs | deep-modules |
| The mutation check and the review of tests | review-change |
| Landing each cycle as a reviewable piece | thin-slices |
