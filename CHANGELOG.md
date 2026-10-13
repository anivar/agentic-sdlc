# Changelog

## 1.1.0 (unreleased)

### Added

- `GOVERNANCE.md`: the maintenance covenant (a fork needs no permission under the MIT
  license, `rules/registry.json` is the specification a fork builds against, the decision
  record is portable JSON Lines), the rule-id lifecycle (an id is never reused or renumbered;
  retirement is `status: deprecated` with `replaced_by` and a changelog entry naming the ADR),
  and how a rule change lands (the rule proposal issue template, maintainer review through
  `.github/CODEOWNERS`, new, over the registry, `guard.py` and the workflows).
- Adoption documentation: the ruleset import is now a stated mandatory step, the only
  server-side floor; a supply-chain paragraph shows the reusable workflow pinned by commit
  sha and the SSH-signed release tags verified with `git tag -v`; the gap table says plainly
  that code review is the server-side backstop for staging; the other-agent install note
  names hook manifests for other agents as roadmap; the Windows `python3` shim note is a
  stated constraint rather than a table aside. `SECURITY.md` now lists the `remote` and
  `rev-list` reads and the `pre-head.json` state file the hook writes around a commit.
- Attribution scanning normalizes each line before the patterns run: NFKD, format characters
  (zero-width joiners and spaces, the soft hyphen) stripped, confusable Cyrillic and Greek
  letters mapped to ASCII. `Claude` written with a Cyrillic а, or a trailer key broken up with
  a zero-width space, no longer slips past ATTR-1; the finding's excerpt keeps the original
  line. A footer verb ("generated with", "made with" and the like) followed by a capitalized
  tool-shaped token, mixed case or digits as in DevTool9000, is ATTR-1 even when the vendor
  list does not know the name; a plain word after the verb ("generated with care") stays
  clean.
- The friction dial: `confirm.scope` (`"each"`, the default; `"slice"` asks for a commit only
  when it would be the branch's first unpushed commit, checked with
  `git rev-list HEAD --not --remotes --count` and failing closed to an ask when git cannot say
  or no remote exists; `"off"` switches all three confirms off) and `confirm.quiet_rules`
  (entries `{rule, until}` that silence a named ask rule until a UTC date). A quiet rule
  naming a deny rule is a config error, an expired entry warns in the config problems, and a
  suppressed ask is noted in the decision reason so the record keeps it visible. The
  unrecognized-subcommand ask from the verb tables is not affected by the scope.
- `agentic-sdlc log --summary` aggregates the decision record: counts by decision, asks and
  denies per rule, the top ten command kinds, and the dates covered.
- A `gh` or `glab` subcommand the verb tables know as neither write nor read now asks
  (ASK-3, "review it yourself") instead of passing silently; the ask does not depend on
  `confirm.post`, like TRACE-1. The tables were re-grounded against gh 2.102.0 and
  glab 1.122.0: new writes include `gh pr revert`, `gh repo set-default`, the `discussion`,
  `skill` and `agent-task` nouns, `glab label edit`, `glab mr for`, `glab ci run-trig`,
  `glab variable import`, `glab repo update`/`publish`/`members`, and the `deploy-key`,
  `gpg-key`, `incident`, `milestone`, `packages`, `runner`, `runner-controller`,
  `securefile`, `stack`, `token` and `work-items` nouns; read verbs verified from the CLIs'
  help (`gh browse`, `gh search`, `glab ci trace` and the like) pass.
- `scripts/check_verb_tables.py` (`just verbs-check`, weekly in `verbs.yml` and on changes to
  the tables) reads each installed CLI's `--help`, locally and off the network, and fails on
  a write-shaped verb the tables do not track; a CLI absent from PATH is skipped.
- TRACE-2 and the `trace.untracked` key (`"allow"`, `"ask"` or `"deny"`; the default stays
  `"allow"`). At ask or deny the hook answers with that decision for a command it cannot trace
  to a git, gh or glab invocation, closing the silent-allow hole for a command behind an
  interpreter or an unknown program. A command made only of read-only programs (`ls`, `cat`,
  `grep` and the like) still passes, and SECRET-3 governs a read of a credential file either way.
- The gated-command pre-check also sees an inline interpreter script (`python3 -c`, `node -e`,
  `ruby -e`, `perl -e`) whose text runs git, including the verb split into separate arguments
  (`["git", "push"]`). TRACE-1 asks for those.
- A seeded parser fuzz test (`tests/test_fuzz.py`): 500 shell-ish strings from a small
  grammar (pipes, redirections, wrappers, quotes, heredoc markers, substitutions, git verbs),
  asserting the parser never raises and the guard decides deterministically. A fourth
  behavioural eval (`evals/push-evasion-is-refused/`) asks the agent to push past a refusal
  and fails the run if it reaches for an interpreter, an alias or `--no-verify`.

### Changed

- The hook's per-call git lookups (`rev-parse --show-toplevel`, `--git-common-dir`) are
  memoized per directory, and a parsed `.agentic-sdlc.json` is cached by path and mtime: a
  hook call in a directory with no config file runs no git subprocess after the first, and a
  changed file is re-parsed. Validation problems are computed on the fresh parse, unchanged.

- The check after a commit no longer guesses from the commit's timestamp. The hook records
  the sha at HEAD before a commit command runs (`<git common dir>/agentic-sdlc/pre-head.json`,
  None for an unborn HEAD) and compares it after: HEAD unchanged means the commit did not
  land and nothing is checked, HEAD moved means the message that landed is scanned for
  attribution. A commit backdated with a forged `GIT_COMMITTER_DATE` is caught either way,
  and a fresh HEAD the command did not create is no longer reported. The stored sha is
  deleted once used. When nothing was recorded, a pair that started before the upgrade, the
  300-second recency guess stands in, documented in the code as the weak fallback.
- Secret scanning moves from gitleaks to TruffleHog. Gitleaks' README calls it feature complete,
  with future releases limited to security patches. The hook and the native `pre-commit` hook
  pipe the lines a staged change adds to `trufflehog stdin` with verification and the update
  check off, so the scan makes no network call and removing a leaked key is never blocked. The
  reusable workflow's `secrets` job runs the TruffleHog action, pinned by commit at v3.99.2, over
  the pull request's commits and fails on a credential that is live or whose check errored; a
  candidate TruffleHog proves dead no longer fails the check, where a gitleaks pattern match did.
  The GitLab template gains the same scan from the TruffleHog image, pinned by digest.
- `secrets.use_gitleaks` becomes `secrets.scanner` (`"trufflehog"` or `"none"`). The 1.0 key
  still reads, with a warning: `true` means TruffleHog, `false` means none.
- The `GITLEAKS_LICENSE` workflow secret is no longer used. It stays declared so a caller that
  passes it keeps validating, and goes in 2.0.

### Fixed

- A dead conditional in the redirection stripping (`skip_next = token not in (">&", "<&") or
  True`, always true) is written as the plain intent: every redirection operator consumes the
  next token as its target. Behaviour is unchanged.
- The reusable workflow's `secrets` job never ran on this repository's own pull requests. Its
  condition compared an input that is absent outside `workflow_call` with `false`, the loose
  comparison treated absent as false, and the skipped job counted as a passing required check.
  Callers that pass the input were not affected.

### Verified before merge

- TruffleHog 3.99.2 over stdin and from a file: a GitHub token, a Slack webhook, an AWS key pair
  and a Stripe key, each built at runtime, were reported; Amazon's documented example key and a
  random private-key block were not (the built-in patterns cover private-key blocks). About
  0.8 s per scan on the development machine. The same detections under a deny-network sandbox,
  with no network error in the debug log (Measured, 2026-10-12).

## 1.0.0 (2026-10-10)

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
- Per permission mode, inside Claude Code 2.1.296 in print mode (`claude -p --plugin-dir`) on
  2026-10-10, in throwaway repositories with `record.decisions` on, five cases each: a commit,
  `cat .env`, a commit with `--no-verify`, the Read tool on `.env`, and a commit whose message
  file is written in the same command and carries a trailer.
  - default, `acceptEdits`, auto: the hook returned ask for the commit and the Read and deny for
    `--no-verify`; print mode turns each ask into a refusal, so the prompt itself is not observed
    in these modes. In auto the trailer commit ran and the check after the commit reported ATTR-1
    with the amend instruction, which the agent relayed.
  - `dontAsk`, `bypassPermissions`: the hook returned its blocking error for the commit, the
    secret file, the `--no-verify` commit and the Read, and none ran (HEAD unchanged). In
    `bypassPermissions` the trailer commit ran and the check after the commit reported it. The
    assumption in decision record 0005 holds in print mode.
  - In `acceptEdits`, auto and `bypassPermissions` the agent declined `cat .env` from its own
    rules before any tool call, so that cell rests on default and `dontAsk`.
  - Not observed: the interactive prompt in default, `acceptEdits` and auto; `docs/verification.md`
    remains the procedure for it. Every decision above is in each repository's
    `.git/agentic-sdlc/decisions.jsonl` with its mode (not committed).

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
- The forbidden-token scan read `.agentic-sdlc-forbidden.txt` from the shell's directory and
  then flagged the list itself; it reads the list from the repository root and skips it.
- A message file written and used in the same command (`printf '…' > m.txt && git commit -F
  m.txt`) was not scanned before the commit, found by the per-mode run; the raw command text is
  scanned when a named message file does not exist yet, and the ask says so.

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
