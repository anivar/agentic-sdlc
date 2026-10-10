# Changelog

## 1.0.0 (unreleased)

First release. Eleven skills, ninety-three rules in `rules/registry.json`: ten enforced by the
Claude Code hook; nine by the reusable workflow (attribution and secrets on every call, the six
mechanical voice rules when the caller names `voice-paths`); one by the ruleset. The hook fails
closed: without `python3` on `PATH`, every Bash tool call is refused.

### Verified before release

- The suite (91 tests) on Python 3.13.15 (`uv run pytest`, the project venv), 3.14.7
  (`uv run --python <3.14> --no-project --with pytest pytest`) and the stock macOS 3.9.6
  (`/usr/bin/python3`), exit 0, 2026-10-10.
- `claude plugin validate --strict .` on Claude Code 2.1.296: passed, 2026-10-10.
- `agentic-sdlc validate`, `check-skills`, `lint-voice --fail-on fail`, `coverage --check`:
  exit 0 on the tree, 2026-10-10.
- The hook's decisions for each mechanism rule are exercised by `tests/test_guard.py` and the
  stdin/stdout contract by `tests/test_hook.py` (an `ask` for a commit, a `deny` for `git add -A`,
  no decision for other tools and for malformed input, the repository config honoured).
- Inside Claude Code 2.1.296, print mode, `claude -p --plugin-dir <this repo>` on 2026-10-10:
  the plugin and its eleven skills loaded, the hook fired on the Bash tool, `git add -A` was
  refused with STAGE-1, `git commit` returned the ASK-1 reason (print mode turns an ask into a
  refusal), the hook finished with exit 0 (debug log, not committed).
- The forced prompt from a PreToolUse `ask` in auto mode is documented by Claude Code (hooks
  reference, read 2026-10-10). Observed behaviour in the interactive modes (default,
  `acceptEdits`, auto, `bypassPermissions`): not yet recorded; see `docs/verification.md`.

### Corrected before release, from an adversarial read on 2026-10-10

- Shell wrappers and substitutions walked past the hook (`sh -c`, `bash -lc`, `eval`, `xargs`,
  `env -i`, `nice`, `timeout`, subshells, `$( … )`, backticks): the parser now follows wrappers
  and masks substitutions, and TRACE-1 asks when a gated operation is named but not traceable.
- `git commit --trailer "Co-authored-by: <tool>"` was asked, not refused: trailer values are
  scanned.
- A trailer behind an escaped `\n` (`printf 'x\nCo-Authored-By: …' | git commit -F -`) was
  missed: raw text is unescaped before the scan. Text built by a substitution is named in the
  ask instead of being silently unscanned.
- `git -C <dir>` and `cd <dir> &&` were judged against the hook's own directory: the staged
  scan and the branch check now follow them.
- A redirection operand counted as a pathspec (`xargs git add -A < /dev/null` passed).
- `git add -A src/` was refused although scoped; it passes now, and STAGE-1 says so.
- The robot emoji anywhere in a message was refused; it counts only beside a footer verb or a
  vendor name.
- The gitleaks call could outlive the hook's budget and block on timeout: budgets lowered.
- The reusable workflow could not receive `GITLEAKS_LICENSE`, which organisation accounts need.
- The README claimed the prompt "in every permission mode" and CI coverage for issue and
  release text; both corrected. "Strips" became "refuses".
- Attribution to Michael Feathers, John Ousterhout and Google's engineering practices was
  missing from the rewritten skills; restored in the skills and in NOTICE.

### Descends from

mattpocock/skills (grilling, grill-with-docs, domain-modeling, codebase-design, tdd, to-tickets,
setup-matt-pocock-skills), addyosmani/agent-skills (spec-driven-development,
incremental-implementation, code-review-and-quality) and the pstack folder of cursor/plugins
(unslop), all MIT; see `NOTICE`. The rules themselves are the author's working conventions,
generalised: the calibration tags, the go-ahead per commit and push, the no-attribution rule,
the finding format, the plan template.
