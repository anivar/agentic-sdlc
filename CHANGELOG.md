# Changelog

## 1.0.0 (unreleased)

First release. Eleven skills, ninety-five rules in `rules/registry.json`: thirteen enforced by the
Claude Code hook, four of those by the native git hooks as well; nine by the reusable workflow
(attribution and secrets on every call, the six mechanical voice rules when the caller names
`voice-paths`); one by the ruleset. The hook on the Bash tool fails closed: without `python3` on
`PATH`, every Bash tool call is refused. The hook on the file tools fails open by design, so a
broken guard never blocks reading a file.

### Verified before release

- The suite (165 tests, 53 of them the registry's own `examples` run through the guard) on
  Python 3.13.15 (`uv run pytest`, the project venv), 3.14.7 and the stock macOS 3.9.6
  (`uv run --python <interpreter> --no-project --with pytest pytest`), exit 0, 2026-10-10.
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
- Inside Claude Code 2.1.296, print mode, default permission mode, 2026-10-10, in a throwaway
  repository with `record.decisions` on: `cat .env` returned the SECRET-3 ask and was refused;
  `git commit --no-verify` was refused with GUARD-1; the Read tool on `.env` fired the hook on
  `PreToolUse:Read`, which returned the SECRET-3 ask in 64 ms; each decision was in
  `.git/agentic-sdlc/decisions.jsonl` with `mode: default`. For `git add -A` the agent declined
  from the skill rules before any tool call, so the hook saw nothing (debug logs, not committed).
- The forced prompt from a PreToolUse `ask` in auto mode is documented by Claude Code (hooks
  reference, read 2026-10-10), and so is `permission_mode` in the hook input. Observed behaviour
  in the interactive modes (default, `acceptEdits`, auto, `bypassPermissions`, `dontAsk`): not
  yet recorded; see `docs/verification.md`.

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
- `git commit -n` was parsed as a dry run; it is `--no-verify`, so a commit that skipped the
  repository's hooks passed with no ask. It is refused now (GUARD-1).

### Corrected before release, from a second read of the skills on 2026-10-10

- Five `derived_from` lines understated what was taken from the upstream: the pre-agreed seams
  and the independent source of expected values (tdd), the mutation probe (code-review-and-quality),
  the approval round and the ticket templates (to-tickets), the design-session habits
  (domain-modeling), the voice catalogue (unslop). Credited now in the skills, in the registry
  notes, and in a `NOTICE` inside each derived skill folder, so a skills.sh install carries the
  source notice the MIT licence requires.
- `/setup-conventions` pointed at `templates/` at the repository root, which a skills.sh install
  does not copy; the templates live under the skill now, the skill branches on GitHub, GitLab or
  another forge, and asks which agent file to create when neither exists.
- plan-project's template lacked the tables PLAN-4 and PLAN-5 require; added, with the ladder on
  the gate line. Three eval graders could fail a run that followed its skill; corrected.
- test-first sent refactoring to review-change, which has no refactoring step; a refactor is its
  own slice. thin-slices prescribed the interactive `git add -p`; hunks go through
  `git apply --cached`. The mutation probe is stated as safe on the working copy.
- GRILL-4 (conduct in a discussion) is cut, as are the sentences that were the author's own
  channel habits rather than engineering rules (the customer clause in VOICE-1, the wide-audience
  checklist, the meeting-record clauses in EVID-4, the brand clause in VOICE-11); VOICE-13 and
  DECIDE-4 are narrowed to what applies to anyone.
- The change-description rule and the self-review list were each stated three times; plain-voice
  and review-change own them, the others cite the id. `check-skills` now requires every id a
  skill lists to be cited in its body, so the coverage table's Cited-by column is exact.
- Codex sidecars for the two skills that publish or configure; the no-op `user-invocable: true`
  lines dropped.

### Added after the read

- Native git hooks: `agentic-sdlc hooks install` writes `commit-msg` (ATTR-1, ATTR-2),
  `pre-commit` (SECRET-1) and `pre-push` (PUSH-1) that hold for every agent and every person,
  from a copy of the package under `.git/`; `.pre-commit-hooks.yaml` offers the same three
  hooks to the pre-commit framework. The `githook` mechanism appears in the registry and the
  coverage table.
- `docs/coverage.md` shows which skills cite each rule; `check-skills` requires a skill's
  `metadata.rules` list to include every id its body cites.
- The repository keeps its own glossary and four decision records.
- Issue templates, a pull request template, Dependabot for actions, and a release workflow
  guarded with `github.event.created`.
- Three behavioural eval cases under `evals/` for `claude plugin eval`.
- Before-and-after and end-to-end examples in plain-voice, evidence and thin-slices.
- Three rules from a read of comparable projects: GUARD-1 refuses `--no-verify`, `commit -n`,
  a `-c core.hooksPath=`, `include.path=` or alias override, and `git config` setting those keys; GUARD-2 asks before the
  file tools edit `.agentic-sdlc.json`, a git hook, `.claude/settings*.json` or
  `.pre-commit-config.yaml`; SECRET-3 asks before a credential file is read, grepped, copied or
  sent, on Bash and on the Read and Grep tools.
- The hook now runs on the file tools (Read, Grep, Edit, Write, MultiEdit, NotebookEdit) and
  after a Bash command: when a commit ran, the message at HEAD is checked for attribution and a
  hit is reported with the instruction to amend, which closes the `-m "$( … )"` gap after the
  fact.
- In `bypassPermissions` and `dontAsk`, which cannot prompt, an ask or a deny becomes a blocking
  error with the reason (ADR 0005).
- A decision record and a shadow mode (`record.decisions`, `record.shadow`, the environment
  overrides) under `.git/agentic-sdlc/decisions.jsonl`, a hash of the command and never its text
  (ADR 0006); `agentic-sdlc log` prints it.
- Every hook rule carries a `fix` line, appended to its refusal. Ten of the thirteen carry
  `examples` that the test suite runs through the guard and expects to decide as keyed; the
  three that need a strict configuration, a staged file or a file-tool event (ATTR-2, SECRET-1,
  GUARD-2) have their own tests. The registry schema and `validate` check both fields.
- `agentic-sdlc check-mr` for GitLab merge request pipelines, with the job template under
  `skills/setup-conventions/assets/`;
  `agentic-sdlc bench` (on the development machine a parse-only decision takes under 1 ms and a
  decision that consults git, such as a commit's staged diff or a push's branch, about 5 ms).

### Descends from

mattpocock/skills (grilling, grill-with-docs, domain-modeling, codebase-design, tdd, to-tickets,
setup-matt-pocock-skills), addyosmani/agent-skills (spec-driven-development,
incremental-implementation, code-review-and-quality) and the pstack folder of cursor/plugins
(unslop), all MIT; see `NOTICE`. The rules themselves are the author's working conventions,
generalised: the calibration tags, the go-ahead per commit and push, the no-attribution rule,
the finding format, the plan template.
