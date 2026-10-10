# Changelog

## 1.0.0 (unreleased)

First release. Eleven skills, ninety-two rules in `rules/registry.json`: nine enforced by the
Claude Code hook; nine by the reusable workflow (attribution and secrets on every call, the six
mechanical voice rules when the caller names `voice-paths`); one by the ruleset. The hook fails
closed: without `python3` on `PATH`, every Bash tool call is refused.

### Verified before release

- `uv run pytest`: 68 tests on Python 3.14.7 and on the stock macOS Python 3.9.6
  (`/usr/bin/python3`), exit 0, 2026-10-10.
- `claude plugin validate --strict .` on Claude Code 2.1.296: passed, 2026-10-10.
- `agentic-sdlc validate`, `check-skills`, `lint-voice --fail-on fail`, `coverage --check`:
  exit 0 on the tree, 2026-10-10.
- The hook's decisions for each mechanism rule are exercised by `tests/test_guard.py` and the
  stdin/stdout contract by `tests/test_hook.py` (an `ask` for a commit, a `deny` for `git add -A`,
  no decision for other tools and for malformed input, the repository config honoured).
- The forced prompt from a PreToolUse `ask` in auto mode is documented by Claude Code (hooks
  reference, read 2026-10-10). Observed behaviour under `acceptEdits` and `bypassPermissions`:
  not yet recorded; see `docs/verification.md` for the procedure.

### Descends from

mattpocock/skills (grilling, grill-with-docs, domain-modeling, codebase-design, tdd, to-tickets,
setup-matt-pocock-skills), addyosmani/agent-skills (spec-driven-development,
incremental-implementation, code-review-and-quality) and the pstack folder of cursor/plugins
(unslop), all MIT; see `NOTICE`. The rules themselves are the author's working conventions,
generalised: the calibration tags, the go-ahead per commit and push, the no-attribution rule,
the finding format, the plan template.
