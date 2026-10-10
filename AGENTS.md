# agentic-sdlc: rules that bind

For agents working in or on this repository. The skills under `skills/` are the product; this
file is about changing the product.

## How to work

- One plan step at a time. The plan is private to the maintainer; a change says which rule ids
  it touches.
- Commit only when `just check` exits 0: ruff, the test suite, `agentic-sdlc validate`,
  `agentic-sdlc check-skills`, `agentic-sdlc lint-voice`, `agentic-sdlc coverage --check` and
  `claude plugin validate --strict .` (TEST-5).
- Every commit, push and post waits for its own go-ahead (ASK-1, ASK-2, ASK-3). Stage by path
  (STAGE-1). No tool attribution in commit or pull request text (ATTR-1).

## Rules

1. `rules/registry.json` is the single source of rules. A new rule gets the next id in its
   prefix, a statement with an RFC 2119 word, a mechanism list, an owner skill and `since`. An
   id is never reused or renumbered; a retired rule is marked deprecated with `replaced_by`.
2. Every rule with `hook` in its mechanisms has a test in `tests/test_guard.py`, and a case in
   `tests/test_hook.py` when it changes the hook contract.
3. The hook stays standard-library Python that runs on 3.9. No dependency is added to the
   runtime path. `tests/` run on 3.9 and 3.14 in CI.
4. `command.py` parses; `guard.py` decides; `text.py` matches; `hook.py` and `cli.py` adapt.
   A new mechanism goes into those modules, not into the adapters.
5. `docs/coverage.md` is generated. Run `agentic-sdlc coverage` after a registry change; CI
   fails when it is stale.
6. Every `skills/*/SKILL.md` cites existing rule ids, has `name` equal to its folder, a
   description under 1024 characters, and a license line. `check-skills` enforces it.
7. The repository tree carries no attribution patterns, no key-shaped literals and no private
   names. `check-skills` scans for the first two; the forbidden-token list for the third stays
   out of the tree (an environment variable in CI, a gitignored file locally).
8. Text in `README.md`, `docs/`, `skills/` and `templates/` passes `lint-voice --fail-on fail`.
   A line that must quote a banned word carries `voice-lint: skip` in an HTML comment.
9. Actions in workflows are pinned by commit sha with `persist-credentials: false`, and every
   workflow declares `permissions`.
10. A tag-triggered workflow, when one is added, carries `if: github.event.created` so a moved
    tag cannot run it again.
