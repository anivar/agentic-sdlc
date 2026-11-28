# agentic-sdlc

Agent skills and non-negotiable checks for a software delivery process run with coding agents.

Created by **[Anivar Aravind](https://anivar.net)**

## The problem

A coding agent follows the instructions it is given, most of the time. The parts of a delivery
process that matter most are the parts "most of the time" is not good enough for: a commit that
lands without a go-ahead, a `git add -A` that sweeps in a file nobody meant to ship, a force push
that moves a protected branch, a key-shaped literal in a test fixture, a tool's name signed into
the history as a co-author. Instructions in a prompt are requests. The rules a team relies on need
a mechanism that does not negotiate.

## This solution

Thirteen skills that encode the process as rules an agent follows, and four mechanisms that
enforce the rules an agent must not be able to talk its way past:

- a **hook for Claude Code and Codex** on every shell command that refuses tool attribution, bulk
  staging, hook-bypass flags, force pushes to protected branches and staged secrets, and decides
  every commit, push and post; the same hook guards credential files and values, the guard's own
  configuration and database writes that reach production, and checks the commit that just
  landed. In agent mode, the default, nothing asks: the agent answers the commit, push and post
  itself and the decision record keeps the rule (AGENT-1), while a credential read or print, a
  change to the guard's configuration and a production write are refused
  ([ADR 0009](docs/adr/0009-agent-mode-never-asks.md)); `"mode": "confirm"` puts a person in
  front of every ask;
- **native git hooks** (`commit-msg`, `pre-commit`, `pre-push`) that hold the same attribution,
  secret and protected-branch rules for every other agent and every person, installed with one
  command or through the pre-commit framework;
- a **reusable GitHub workflow** that fails a pull request whose title, body or commits carry
  attribution, and runs TruffleHog over the pull request's commits;
- a **ruleset** for the protected branch: merged pull requests only, signatures, linear history,
  the checks required.

Every rule has a stable id in [`rules/registry.json`](rules/registry.json); the skills cite the
ids, the hook names them in its reasons, and [`docs/coverage.md`](docs/coverage.md) is generated
from the registry so the coverage claim is a table, not a sentence.

## Install

**Claude Code** (skills plus the hook), from inside a session:

```
/plugin install agentic-sdlc --marketplace anivar/agentic-sdlc
```

or in two steps: `/plugin marketplace add anivar/agentic-sdlc`, then
`/plugin install agentic-sdlc@agentic-sdlc`. Skills appear as `agentic-sdlc:<name>`.

**Codex** (skills plus the hook), from a shell:

```bash
codex plugin marketplace add anivar/agentic-sdlc
codex plugin add agentic-sdlc@agentic-sdlc
```

Then open `codex` once, run `/hooks`, and trust the agentic-sdlc hooks: Codex runs a plugin's
hooks only after that, and asks again when an update changes them. Codex reads the same
`.claude-plugin` manifests, loads every skill, and reads the rules block from `AGENTS.md`.

**Any other agent** (skills only; the hook runs in Claude Code and in Codex):

```bash
npx skills add anivar/agentic-sdlc -g
```

Do not install both ways into Claude Code or Codex; the plugin already carries the skills. The skill files
carry Claude Code's `argument-hint` field, which the skills CLI tolerates; the claude.ai skill
upload is not a supported path.

**Every agent and every person**, the git hooks, from inside a repository:

```bash
uvx --from git+https://github.com/anivar/agentic-sdlc agentic-sdlc hooks install
```

This copies the package under `.git/` and writes `commit-msg` (ATTR-1, ATTR-2), `pre-commit`
(SECRET-1) and `pre-push` (PUSH-1) into the hooks directory; `hooks status` and `hooks uninstall`
manage them, and an existing hook this tool did not write is left alone unless `--force` is
passed. Teams on the pre-commit framework add the repository to `.pre-commit-config.yaml`
instead; [`.pre-commit-hooks.yaml`](.pre-commit-hooks.yaml) lists the three hook ids.

**The upstream skills.** This set descends from the skills below (see [NOTICE](NOTICE)). Keeping
both installed gives a prompt about tests or reviews two answers; to keep one set:

```bash
npx skills remove grilling grill-with-docs domain-modeling codebase-design tdd to-tickets \
  setup-matt-pocock-skills spec-driven-development incremental-implementation \
  code-review-and-quality unslop -g -y
```

## Baseline

| Component | Needs |
|---|---|
| The hook | `python3` 3.9 or newer on `PATH` (the stock macOS interpreter qualifies); `git`; `trufflehog` optional, used when present, with verification and the update check off. The hook fails closed: when it cannot load, or fails outside its analysis, it refuses every shell command with exit 2, which Claude Code and Codex both treat as a block. The shell hook runs through `hooks/guard.sh`, which turns any other exit, a missing `python3` included, into the same refusal. The hook has a 30 s budget; its own git and TruffleHog calls stay under it |
| Claude Code | 2.1.211 or newer for the forced prompt in auto mode; 2.1.295 or newer for `onFailure: block` |
| Codex | 0.171 or newer: it reads the plugin manifests, sends a shell call to the hook as `Bash` and a file edit as `apply_patch`, takes a deny or exit 2 from a PreToolUse hook, and runs the hooks after a person trusts them |
| The CI check | GitHub Actions; `gh` is preinstalled on the runners |
| The skills | any agent that reads `SKILL.md` |

A constraint, stated plainly rather than as a footnote: on Windows the hook works only where
`python3` resolves to a real executable rather than the Store shim, and the CI matrix does
not run Windows, so Windows behaviour is not verified on every change.

## What is inside

### Skills

| Skill | What it does | Rules |
|---|---|---|
| `evidence` | Calibrate every claim: Verified, Measured, Inferred, Planned; verify at the production sha; agent output is a lead; read sources in full; compute a headline number twice; sweep after one defect | EVID-1 to EVID-10 |
| `plain-voice` | The decision first, current state only, open points left open, misses in the headline, no rhetorical structure, no dashes as punctuation, no tool attribution | VOICE-1 to VOICE-13, ATTR-1, ATTR-2 |
| `review-change` | Findings on the introducing change at its head sha, one per thread in Conventional Comments, a summary that ends in a decision, a mutation check before trusting a test, an adversarial read of your own work, a fresh-context reader for a plan or design you drafted, one answer per finding | REVIEW-1 to REVIEW-12 |
| `plan-project` | One plan file: outcome with measures, decisions as options, assumptions tied to tests, dated steps with done-when, gates, risks, rollout, cut order; compared with the ask before it is shown; the turn ends after the plan | PLAN-1 to PLAN-10 |
| `grill-plan` | Rounds of numbered questions over the settled frontier, each with a recommended answer; facts looked up, decisions put to the decider | GRILL-1 to GRILL-3 |
| `decision-records` | Glossary, decision records and dated research documents, as tables with calibration, naming systems and roles, never people | DECIDE-1 to DECIDE-6 |
| `cut-tickets` | One ticket per real work item with acceptance and blockers, no identifiers or names, full links, published only after approval | TICKET-1 to TICKET-6 |
| `test-first` | Seams agreed first, red before green, expected values from an independent source, mocks at boundaries only, commits gated on exit codes | TEST-1 to TEST-7 |
| `thin-slices` | One pull request per step, nothing half-done, scope held, staging by path, a go-ahead per commit, push and post, secrets never printed | SLICE-1 to SLICE-8, STAGE-1, PUSH-1, PUSH-2, SECRET-1, SECRET-2, PROD-1, ASK-1 to ASK-3 |
| `deep-modules` | The vocabulary and moves for deep modules: interface as the test surface, two adapters make a seam, design it twice with consent | DESIGN-1 to DESIGN-5 |
| `setup-conventions` | One-time repository setup: the rules block, tracker and conventions files, the hook config, and the forge's check (workflow and ruleset, or the GitLab job) as a pull request; the rules block goes in `AGENTS.md` with an `@AGENTS.md` line in `CLAUDE.md` | SETUP-1 to SETUP-3 |
| `unattended-runs` | A run nobody watches, in Claude Code or Codex: the launch flags, a finish condition, a spend cap and a branch of its own, refused calls held for a person, and a run report in a file | RUN-1 to RUN-4 |
| `session-handoff` | Work across sessions and compactions: a progress file and a JSON feature list, a start-up routine, one feature at a time passing on recorded evidence, settled decisions written when settled, lasting knowledge moved to the repository | HANDOFF-1 to HANDOFF-5 |

### Mechanisms

Each row states what the rule decides in confirm mode. In agent mode, the default, nothing asks:
a call marked **asks** runs and the decision record keeps the rule with AGENT-1, except SECRET-2,
SECRET-3, GUARD-2 and PROD-1, which are refused; a call marked **denied** is still denied
([ADR 0008](docs/adr/0008-the-agent-decides-and-the-guard-records.md),
[ADR 0009](docs/adr/0009-agent-mode-never-asks.md)).

| Rule | What happens | Where |
|---|---|---|
| AGENT-1 | in agent mode, the default, any call another rule **asks** about: **runs**, and the decision record keeps that rule beside AGENT-1; a credential read (SECRET-3) or print (SECRET-2), a change to the guard's configuration (GUARD-2), a production write (PROD-1) and a gated command the guard could not analyse: **denied**, recorded with AGENT-1; `"mode": "confirm"` in `.agentic-sdlc.json` or `AGENTIC_SDLC_MODE=confirm` turns it off, and an unknown value or a configuration file the guard cannot read means confirm | hook |
| ATTR-1 | any trailer naming a tool, a "Generated with" footer, or the robot emoji beside one, in a commit, pull request, issue or release text: **denied** | hook, before the command and again on the message at HEAD after a commit ran; git `commit-msg` hook; CI for pull request title, body and commits |
| ATTR-2 | any vendor mention in change text when the repository opts into strict mode: **denied** | hook, git `commit-msg` hook, CI |
| STAGE-1 | `git add -A`, `--all` or `-u` without a narrowing path, a root pathspec such as `.`, `git commit -a`: **denied**; `git add -A src/` passes | hook |
| PUSH-1 | a force push to, or deletion of, a protected branch: **denied** | hook, git `pre-push` hook, ruleset |
| PUSH-2 | a force push of a tag: **asks**, and says that tag-triggered workflows run again | hook |
| SECRET-1 | a key-shaped literal in the staged changes: **denied** (built-in patterns, plus TruffleHog's detectors when installed, over the added lines only) | hook, git `pre-commit` hook, CI |
| ASK-1, ASK-2, ASK-3 | every `git commit`, `git push`, and every `gh`/`glab` command that creates or changes something on the forge: **asks**. A `gh`/`glab` subcommand the verb tables know as neither write nor read asks too ("review it yourself"), and a weekly CI job diffs the tables against the installed CLIs so a new write verb is caught. The forced prompt is documented for auto mode. In `bypassPermissions` and `dontAsk`, which cannot prompt, the hook returns a blocking error with the reason instead ([ADR 0005](docs/adr/0005-a-blocking-error-where-no-prompt-is-possible.md)); what each mode does is recorded in [`CHANGELOG.md`](CHANGELOG.md) as it is observed | hook |
| TRACE-1 | a command that mentions a commit, push, bulk add or forge write but cannot be traced to a `git`, `gh` or `glab` call (a variable, an interpreter, an unusual wrapper), or runs one inside a command or process substitution: **asks**. A command made only of `echo`, `printf`, `cat`, `head`, `tail`, `grep`, `rg`, `wc` or `ls` prints or searches the text and passes | hook |
| TRACE-2 | a command the parser cannot trace at all, when the repository sets `trace.untracked` to ask or deny: **that decision**; a command made only of read-only programs passes | hook |
| GUARD-1 | `--no-verify` or `commit -n`, a `git -c core.hooksPath=…`, `include.path=…` or alias override on the command line, `git config` setting those keys, or git configuration set through the environment (`GIT_CONFIG_PARAMETERS`, `GIT_CONFIG_COUNT`, `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM`): **denied** | hook |
| GUARD-2 | a change to `.agentic-sdlc.json`, a git hook or `.git/hooks`, a git configuration file, `.claude/settings.json`, `.claude/settings.local.json`, `.codex/hooks.json`, `.codex/config.toml`, a plugin's `hooks/hooks.json` or `.pre-commit-config.yaml`, through the file tools, a Codex patch, a redirection, `tee`, `sed -i`, `cp`, `mv`, `rm`, `chmod`, `dd` or inline interpreter code that names the file and writes, or a script with uncommitted changes that an interpreter runs: **asks**; **denied** in agent mode. Code that only reads the file passes | hook, on Bash, Edit, Write, MultiEdit and Codex `apply_patch` |
| SECRET-3 | reading, grepping, copying, archiving or sending a file that holds credentials by name (`.env` files, private keys, `.netrc`, `.npmrc`, `credentials.json`, PEM and keystore files), through a program's operands, an input redirection, a command substitution, inline interpreter code (`python3 -c`, `node -e`, `ruby -e`), or a script with uncommitted changes that an interpreter runs (`python3 read.py`, `bash fix.sh`); a committed script is not opened: **asks**; **denied** in agent mode | hook, on Bash, Read and Grep |
| SECRET-2 | printing the whole environment (`env` or `printenv` alone, `export -p`, `declare -p`, `set` alone), or printing a variable whose name marks a credential (`printenv GITLAB_TOKEN`, `echo "$DB_PASSWORD"`) or whose value is shaped like a key: **asks**; **denied** in agent mode. `${#NAME}`, the length, passes | hook, on Bash; the skills for everything else |
| PROD-1 | a database client (`psql`, `pg_restore`, `mysql`, `mariadb`, `sqlcmd`, `mongosh`, `redis-cli`, `cqlsh`, `clickhouse`) whose target carries a production marker (`prod`, `production`, or `production.markers`) in the command, in a variable the command uses, or in `PGHOST` or `MYSQL_HOST`, and runs a write, or reads its statements from a file, stdin or an interactive session: **asks**; **denied** in agent mode. A read statement passes | hook, on Bash; the skills for every other way to reach production |
| RUN-4 | a command that sets `AGENTIC_SDLC_UNATTENDED` (a leading assignment, `env`, `export`), or `agentic-sdlc run`: **runs**, and the start is recorded; the run it starts follows RUN-1 | hook |
| RUN-1 | in confirm mode, with `AGENTIC_SDLC_UNATTENDED` set in the environment of the Claude Code process (`.agentic-sdlc.json` cannot set it): no call **asks**. A commit on a branch that is not protected passes; a push passes only to a branch in `unattended.push_branches` that is not protected, with no force, tags, deletion or mirror; every other call that would ask is **denied** with a reason that tells the agent not to retry and to list the call in its run report ([ADR 0007](docs/adr/0007-an-unattended-run-never-waits-on-a-person.md)) | hook, opt-in |
| VOICE-3 to VOICE-8 | dashes as punctuation, counting framings, closing offers, banned words in the prose a repository names through `voice-paths`: **fails the check** | CI, when `voice-paths` is set |

The hook reads the command the agent is about to run, parses it (chains, pipes, heredocs,
message files, shell wrappers such as `sh -c` and `eval`, `git -C` and a leading `cd`), and
returns one decision with the rule ids and the reason. Precedence is deny over ask over allow.
Everything else runs without a decision from the hook.

Every refusal and every ask ends with the rule's fix line. A decision the agent makes in place of
a person (AGENT-1) and the start of an unattended run (RUN-4) are always appended to
`.git/agentic-sdlc/decisions.jsonl`; with `record.decisions` on, every decision is. An entry is a hash of the command, the
decision, the rule ids, the permission mode and the milliseconds, never the command text;
`record.shadow` records and lets everything through, which is how a team sees what the hook
would refuse before it refuses anything. `agentic-sdlc log` prints the record.

What the guard prints in agent mode, the default:

```
$ agentic-sdlc guard 'git add -A'
deny: STAGE-1
  STAGE-1: Stage by path: stage named paths, then check git diff --cached --stat. Fix: Stage the files by name (git add <path>), check git diff --cached --stat, then commit.

$ agentic-sdlc guard 'git commit -m "Fix parser" -m "Co-Authored-By: Claude <noreply@anthropic.com>"'
deny: ATTR-1, ASK-1
  ATTR-1: No tool attribution in change text: tool trailer (Co-Authored-By: Claude <noreply@anthropic.com>). Fix: Remove the trailer or footer; the sign-off already names who answers for the change.
  ASK-1: A commit waits for a go-ahead: commit needs your go-ahead. Fix: Show the staged change and the message; commit when the user says yes.

$ agentic-sdlc guard 'sh -c "git push --force origin main"'
deny: PUSH-1, ASK-2
  PUSH-1: No force push to a protected branch: force push to main; a protected branch moves by merged pull request. Fix: Push the branch and open a pull request; a protected branch moves by merge.
  ASK-2: A push waits for a go-ahead: push to main needs your go-ahead. Fix: Say what is pushed and where; push when the user says yes.

$ agentic-sdlc guard 'git commit --no-verify -m "Fix parser"'
deny: GUARD-1, ASK-1
  GUARD-1: Hook bypass flags are refused: --no-verify skips the repository's hooks. Fix: Run the command without the flag and let the hooks run; if a hook is wrong, fix the hook.
  ASK-1: A commit waits for a go-ahead: commit needs your go-ahead. Fix: Show the staged change and the message; commit when the user says yes.

$ agentic-sdlc guard 'cat .env'
deny: SECRET-3, AGENT-1
  SECRET-3: A secret file is read only on a person's go-ahead: .env holds credentials by name. Fix: Name the variable or the file and its length or hash instead. If the work needs the file, a person reads it, or a session in confirm mode asks for it.
  AGENT-1: The agent decides, the guard never asks, and the record keeps the rule: agent mode never waits on a person, so this call is refused instead of asked. Do not retry it or work around it: carry on with the next step and list it as a held call. A person can run it, or start a session with AGENTIC_SDLC_MODE=confirm to be asked

$ agentic-sdlc guard 'gh pr merge 12 --squash'
allow: ASK-3, AGENT-1
  ASK-3: A post waits for a go-ahead: gh pr merge publishes or changes something on the forge. Fix: Show the draft in the conversation; post when the user says yes.
  AGENT-1: The agent decides, the guard never asks, and the record keeps the rule: recorded, not asked
```

In confirm mode the deny lines are the same, `cat .env` prints `ask: SECRET-3`, and the last call
prints `ask: ASK-3` and waits for a person. Under Codex, which takes no ask from a hook, both
are refused with the reason they would have asked with.

### What the mechanisms do not cover

| Gap | Why | What covers it |
|---|---|---|
| Commands outside the Bash tool: MCP tools that post, `!`-prefixed commands typed by the user, other agents | hooks see Bash tool calls only | the git hooks for commits and pushes made any way at all; the CI check for pull request text |
| The merge body typed at squash-merge time | the pull request workflow sees title, body and branch commits; the merge body is written after the checks ran | the hook, when the merge runs through the Bash tool with the body inline or in a file that exists; a body built by `$( … )` is not readable before it runs and the hook says so in its ask |
| Commit-message rules on the forge | GitHub rulesets offer metadata rules on the Enterprise plan only | the required status check from the workflow |
| A user who sets `disableAllHooks`, or a mod that approves after the hook | the hook is a plugin hook, not a managed one | the CI check; the ruleset |
| Codex before a person trusts the hooks | Codex runs a plugin's hooks only after review | the git hooks; the CI check; the ruleset. The install steps include the trust step |
| A hook that times out under Codex | Codex's hooks documentation says a tool hook is "a useful guardrail, not a complete enforcement boundary" and does not say what a timeout does to the call; the wrapper turns a missing `python3` into exit 2, but a kill happens outside it | the git hooks; the CI check; the ruleset. No live Codex session has been run against the hook yet: `docs/verification.md` has the procedure |
| Modes that cannot prompt (`bypassPermissions`, `dontAsk`) | an `ask` has nowhere to go there | the hook returns a blocking error with the reason in those modes; observed in print mode on 2026-10-10 ([`CHANGELOG.md`](CHANGELOG.md)): the block held for the commit, the secret file and the Read tool in both |
| The unattended signal | it is an environment variable of the Claude Code process: a background session takes its supervisor's environment, and a repository's committed `.claude/settings.json` `env` block may set it (inferred from the documentation, not tested) | the guard still refuses a commit on a protected branch and every push outside `unattended.push_branches`; committed config can already remove the asks with `confirm.scope: off` |
| The interactive prompt under `acceptEdits` and auto | the documentation states the auto-mode behaviour; print mode refuses an ask in both ([`CHANGELOG.md`](CHANGELOG.md)) | recorded once observed interactively; `docs/verification.md` is the procedure |
| A gated command the parser cannot see: a git call inside an interpreter (`python -c`, `node -e`), behind a shell alias or a variable (`$g push`), or a direct API call with `curl` | the parser follows wrappers, substitutions and `cd`, not program semantics | TRACE-1 asks when the text still names the operation, and the pre-check names the inline interpreter shapes; `trace.untracked` at ask or deny closes the hole for everything else the parser cannot trace; `posting.extra_commands` can name `curl`; the CI check and the ruleset are the backstops |
| Message text built by a substitution (`-m "$(cat m.txt)"`, `--file=<( … )`) | the text does not exist until the command runs | the ask names it; after the commit ran, the hook compares HEAD with the sha recorded before the command and reads the message that landed, so a backdated commit is still reported with the instruction to amend (when nothing was recorded, a 300-second timestamp guess stands in as the weak fallback); the pull request check scans the resulting commits |
| A credential read or print the parser cannot see: a committed script that reads or prints one, a library that loads `.env` by itself, a path built at run time (`cat "$f"`), a secret that is neither named like one nor shaped like a key, a variable set in a shell profile the hook does not share | SECRET-3 and SECRET-2 match names on the command line, in redirections, substitutions, inline code and uncommitted scripts, and in the file tools, and key shapes in the hook's environment; not what a program does | SECRET-2 in the skills (never print a secret); the agent's sandbox |
| A change to the guard's own configuration the parser cannot see: a committed script that writes it, a path built at run time, a tool outside the shell and the file tools | GUARD-2 matches file names on the command line, in redirections, inline code and uncommitted scripts, in the file tools and in Codex patches | the pull request review sees the change; CI and the ruleset do not read the local config |
| A production write the hook cannot see: a target with no marker in its name, a variable set in a shell profile the hook does not share, a cloud CLI, a migration tool, an ORM script, an HTTP API | PROD-1 in the hook checks database clients whose command, variables or client host carry a production marker | read-only production credentials for agents, which is the boundary; PROD-1 in the skills |
| A crash in the hook on the file tools | it carries no `onFailure: block`, by design: a broken guard must not stop every read | a failed check refuses the guard's configuration and secret files and passes the rest; the Bash hook refuses every shell command when it fails; the error shows in the transcript |
| A bulk stage outside the Bash tool (another agent's manifest, a person at a shell) | STAGE-1 lives in the Claude Code hook only; there is no git hook for staging | code review, said plainly: no server-side mechanism refuses a swept-in file |
| Attribution patterns dodged with look-alike letters or invisible characters | the patterns match ASCII vendor names and trailer keys | each line is normalized before the scan (NFKD, format characters stripped, confusable Cyrillic and Greek mapped to ASCII), and a footer verb followed by any tool-shaped token fires without a known vendor; a script outside the confusable map still evades, and the git hooks and CI scan the same landed text |

## Why no tool attribution

The person who signs a change is the operator of record for it: the one who answers for what
it does. A trailer or footer naming a tool records which product was open, not who is
accountable, and it is the first thing a reader mistakes for the second. The hook refuses the
attribution patterns; a repository that wants no vendor named at all in its history turns on
strict mode.

Accountability is not origination. A record can state that an agent operated a change without
naming a product: a trailer such as `Operated-by: agent` names a role, passes ATTR-1, and sits
beside the sign-off that names the person who answers for it. A repository that wants its
history to carry origination adds that trailer to its commit template; one that does not
records accountability only, and says so.

## Decisions and vocabulary

The repository keeps its own records the way its skills ask adopters to: a [glossary](GLOSSARY.md)
with one term per concept, and decision records under [`docs/adr/`](docs/adr/) for the choices
that are hard to reverse: the standard-library hook, one repository that is also a plugin,
attribution patterns by default, and accountability rather than origination in the record.

## Configuration

A repository may carry `.agentic-sdlc.json` at its root
([schema](schemas/config.schema.json), [template](skills/setup-conventions/assets/agentic-sdlc.json)). Every key has
a default; an absent file means the defaults.

| Key | Default | Rule |
|---|---|---|
| `mode` | `"agent"`: nothing asks; the agent decides and the record keeps the rule, and a secret read or print, a guard edit and a production write are refused; `"confirm"`: a person answers every ask. `AGENTIC_SDLC_MODE` overrides the file | AGENT-1 |
| `protected_branches` | `["main", "master"]` | PUSH-1 |
| `attribution.mode` | `"patterns"`; `"strict"` refuses any vendor mention | ATTR-1, ATTR-2 |
| `attribution.vendors` | adds to the built-in names | ATTR-1, ATTR-2 |
| `confirm.commit`, `confirm.push`, `confirm.post` | `true` | ASK-1, ASK-2, ASK-3 |
| `confirm.scope` | `"each"`; `"slice"` asks for a commit only when it would start the branch's unpushed slice (the push and the post still ask), `"off"` switches all three confirms off | ASK-1 |
| `confirm.quiet_rules` | `[]`; entries `{rule, until}` silence a named ask rule until a UTC date. A deny rule is a config error, an expired entry warns, and a suppressed ask is noted in the decision reason | the ask rules |
| `stage.deny_add_all`, `stage.deny_commit_all` | `true` | STAGE-1 |
| `production.markers`, `production.clients` | `["prod", "production"]`, matched as words (`prod-db`, `$PROD_URL`; not `products`, `nonprod`, `preprod`), and the database clients listed under PROD-1. An empty marker list turns PROD-1 off in the hook; a client without statement flags the hook knows counts as able to write on every call | PROD-1 |
| `trace.untracked` | `"allow"`; `"ask"` or `"deny"` answers with that decision for a command the parser cannot trace to git, gh or glab; a command made only of read-only programs still passes | TRACE-2 |
| `unattended.push_branches` | `[]`; glob patterns such as `"agent/*"` for the branches an unattended run may push to. A protected branch never matches. Empty refuses every push | RUN-1 |
| `secrets.scan_staged`, `secrets.scanner`, `secrets.extra_patterns` | `true`, `"trufflehog"` (or `"none"`), `[]`; the 1.0 key `use_gitleaks` still reads, with a warning | SECRET-1 |
| `posting.extra_commands` | `[]`; regular expressions that count as a post | ASK-3 |
| `record.decisions`, `record.shadow`, `record.path` | `false`, `false`, `<git common dir>/agentic-sdlc/decisions.jsonl`; `AGENTIC_SDLC_RECORD=1` and `AGENTIC_SDLC_SHADOW=1` override for one session; AGENT-1 and RUN-4 decisions are kept whatever `record.decisions` says | the decision record ([ADR 0006](docs/adr/0006-the-decision-record-holds-a-hash-not-the-command.md)); shadow records and lets every command through |

## Adopting it in a repository

1. In the repository, run `/setup-conventions` once. It explores, confirms the choices, and
   writes the rules block into `AGENTS.md` with an `@AGENTS.md` line in `CLAUDE.md`,
   `docs/agents/tracker.md`, `docs/agents/conventions.md` and `.agentic-sdlc.json` as a pull
   request. Start that session with `AGENTIC_SDLC_MODE=confirm`: agent mode refuses an agent's
   write to `.agentic-sdlc.json`.
2. Add the workflow:

   ```yaml
   # .github/workflows/conventions.yml
   name: conventions
   on:
     pull_request:
       types: [opened, edited, synchronize, reopened]
   permissions:
     contents: read
     pull-requests: read
   jobs:
     conventions:
       uses: anivar/agentic-sdlc/.github/workflows/conventions.yml@v1.0.0
       with:
         strict: false
         ref: v1.0.0
   ```

   Pin `ref` to the same tag as the `uses` line. The optional `voice-paths` input (for example
   `"README.md docs"`) also fails the check on the mechanical voice rules over those files;
   leave it out unless the repository wants that. The `secrets` job runs TruffleHog over the
   pull request's commits and fails on a credential that is live or whose check errored; a
   candidate TruffleHog proves dead passes, while the hook, which never verifies, refuses any
   detector match. No licence is needed. A caller that passes `secrets-scan: false` gets a
   skipped job, which GitHub reports as passing to a required check.

3. Import the ruleset, after editing the required check names to the repository's own:

   ```bash
   gh api -X POST repos/<owner>/<repo>/rulesets --input rulesets/main-protected.json
   ```

   This step is not optional. The ruleset is the only mechanism on the server: it refuses
   force pushes, deletions and pushes that skip review on main, and it holds the change-text
   and secrets checks as required, whatever happens on any laptop or in any agent session.

Pin the `uses:` line by commit sha, with the tag in a comment for the reader:

```yaml
uses: anivar/agentic-sdlc/.github/workflows/conventions.yml@<full commit sha> # v1.0.0
```

A tag can move and a sha cannot; this repository's own workflows pin their actions the same
way. Release tags carry an SSH signature: `git tag -v v1.0.0` verifies one, with the
maintainer's key in `gpg.ssh.allowedSignersFile` (SSH signatures need it; without it git
cannot say whom the signature belongs to).

### GitLab

The plugin, the skills and the git hooks are forge-neutral. For the merge request check,
`agentic-sdlc check-mr` reads the predefined `CI_MERGE_REQUEST_*` variables and the commits since
the merge base; [`gitlab-ci.yml`](skills/setup-conventions/assets/gitlab-ci.yml) is the job to include.

### Tuning friction with data

With `record.decisions` on, `agentic-sdlc log --summary` counts the record: decisions by
outcome, asks and denies per rule, the top command kinds, over the dates covered. A rule that
asks every time and is approved every time is a candidate for `confirm.quiet_rules` with an
expiry date; the entry warns once it expires, so a quiet period cannot run forever unnoticed.
`confirm.scope: slice` is the coarser dial: a commit asks only when it would be the branch's
first unpushed commit, and the push and the post still ask because they bound the slice.

## Long-running runs

One command starts a run that nobody has to watch:

```bash
agentic-sdlc run fix-parser "Fix the parser; done when just check passes"
```

The run gets its own branch, `agent/fix-parser`, in a worktree beside the checkout
(`../<repository>.fix-parser`). It runs Claude Code in print mode, or `codex exec` with
`--agent codex`, with nothing that can prompt, and returns at once. The launcher needs macOS or
Linux. The run detaches from the terminal, holds off idle sleep on macOS while it works, and ends
at its spend cap (`--budget`, 20 USD by
default, Claude Code only) or its time limit (`--hours`, 8 by default). It finishes with the run
report in `.agent/run-report.md` on its branch.

| Command | What it does |
|---|---|
| `agentic-sdlc runs` | every run with its state: working, done, failed, timed-out, stopped; orphaned when its supervisor was killed and the agent still runs, until `runs stop` ends it; lost when nothing of it runs, as after a restart |
| `agentic-sdlc runs read <name>` | the end of the run's log (`--lines N`) |
| `agentic-sdlc runs wait <name>` | blocks until the run ends; exit 0 when it ended done, 3 when `--timeout` passed first |
| `agentic-sdlc runs stop <name>` | ends a working run; it never signals a process the run did not start |

Ending a run ends every process the agent started, and a task over 256 KB goes in a file that
the task names. The records and logs live under `<git common dir>/agentic-sdlc/runs/`, never in
a temp directory, so a restart loses nothing and every worktree sees the same runs. The guard records
each start under RUN-4. `--dry-run` prints the record and creates nothing. Codex needs its hooks
trusted once in an interactive session first.

## Try the hook by hand

The package is `agentic-sdlc-guard` and the command it installs is `agentic-sdlc`. Install it from
this repository: the package is not on PyPI, and the PyPI project named `agentic-sdlc` is a
different project, so never run `uvx agentic-sdlc`. The URL below gives the head of `main`; add
`@<tag>` to it for a release tag:

```bash
alias agentic-sdlc='uvx --from git+https://github.com/anivar/agentic-sdlc agentic-sdlc'
agentic-sdlc guard 'git add -A'
agentic-sdlc guard 'git commit -m "Fix parser" -m "Co-Authored-By: Claude <noreply@anthropic.com>"'
agentic-sdlc guard 'git push --force origin main'
agentic-sdlc guard 'gh pr merge 12 --squash --body-file notes.md'
agentic-sdlc guard 'cat .env'
agentic-sdlc log            # the decision record, when the repository keeps one
agentic-sdlc bench          # how long a decision takes
```

Each prints the decision, the rule ids and the reason. `--json` prints what the hook returns.

## Structure

```
├── .claude-plugin/        plugin.json, marketplace.json (read by Claude Code and by Codex)
├── hooks/                 hooks.json: PreToolUse on Bash and the file tools, PostToolUse on Bash;
│                          guard.sh, the wrapper that refuses when the hook cannot run
├── src/agentic_sdlc/      command.py (parse), guard.py (decide), text.py (patterns),
│                          config.py, registry.py, record.py, hook.py (adapter), runs.py
│                          (the run launcher), cli.py
├── rules/registry.json    every rule, stable ids, mechanism, owner
├── schemas/               config and registry JSON Schemas
├── skills/<name>/         SKILL.md, references/ and NOTICE per skill; setup-conventions/assets/ holds what it writes
├── rulesets/              the branch ruleset to import
├── .pre-commit-hooks.yaml the three git hooks for the pre-commit framework
├── evals/                 behavioural cases for `claude plugin eval`
├── AGENTS.md              the rules that bind this repository, for every agent
├── docs/coverage.md       generated from the registry; docs/adr/ the decision records
├── GLOSSARY.md            the repository's own vocabulary
├── tests/                 one test per mechanism rule, the hook contract, the git hooks, the CLI
└── .github/workflows/     gate.yml (this repo), conventions.yml (reusable), release.yml
```

## Development

```bash
uv sync --group dev
just check            # ruff, pytest, validate, check-skills, lint-voice, coverage, plugin validate
just test-stock       # the suite on the stock macOS python3
just guard 'git add -A'
just eval             # the behavioural cases under evals/, with and without the plugin (real model runs)
just codex-check      # load the plugin into a throwaway Codex home; Codex must see every skill
```

CI runs the suite on Python 3.9 and 3.14 and on the stock macOS interpreter, validates the plugin
in strict mode, installs every skill with the skills CLI into a throwaway home, and loads the
plugin into Codex to check that it sees every skill. A release is
created from the CHANGELOG section when a version tag is first pushed; a moved tag does not
run it again.

## Related projects

Read on 2026-10-10. Each line states what the project's own README says it does, and what
this repository does differently.

| Project | What it is | Difference here |
|---|---|---|
| [random1st/secguard](https://github.com/random1st/secguard) | a command guard with hooks for Claude Code, Gemini CLI and Codex, a telemetry record and a shadow mode | the decision record and shadow mode here follow that rollout pattern; this repository binds its rules to skills, git hooks, CI and the ruleset from one registry, and its Claude Code hook also covers the file tools and the commit that landed |
| [ThammanaSrinivas/guardrails](https://github.com/ThammanaSrinivas/guardrails) | rules with ids and `gr explain <id>`, a managed pre-commit block, and the statement that shell parsing is a heuristic | the same honesty about parsing, with TRACE-1 asking when a gated operation is named but not traced, and every refusal carrying its fix |
| [janoppix/silent-code](https://github.com/janoppix/silent-code) | a Claude Code plugin that blocks or strips `Co-Authored-By` trailers and new comments | attribution is refused at three layers here (hook, git hook, CI) and never stripped |
| [obra/superpowers](https://github.com/obra/superpowers) | a skills library whose hook is a `SessionStart` bootstrap | the skills here cite rule ids that mechanisms enforce; nothing rests on the prompt alone |
| [mattpocock/skills](https://github.com/mattpocock/skills), [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | the process skills this set descends from (see [NOTICE](NOTICE)) | the rules became a registry with stable ids and enforcement |

## Ecosystem

Skills by [Anivar Aravind](https://anivar.net):

| Skill | Covers | Install |
|---|---|---|
| [jest-skill](https://github.com/anivar/jest-skill) | Jest 30: mocks, async, timers, snapshots, CI | `npx skills add anivar/jest-skill -g` |
| [zod-skill](https://github.com/anivar/zod-skill) | Zod v4: schema design, parsing, errors, inference | `npx skills add anivar/zod-skill -g` |
| [msw-skill](https://github.com/anivar/msw-skill) | MSW 2.0: handlers, responses, GraphQL | `npx skills add anivar/msw-skill -g` |
| [developer-docs-framework](https://github.com/anivar/developer-docs-framework) | Diátaxis, made enforceable | `npx skills add anivar/developer-docs-framework -g` |
| [contributor-codebase-analyzer](https://github.com/anivar/contributor-codebase-analyzer) | reading a codebase and its contributions before touching it | `npx skills add anivar/contributor-codebase-analyzer -g` |

## Author

**[Anivar Aravind](https://anivar.net)**

## License

MIT. The skills descend in part from MIT-licensed work by other authors; see [NOTICE](NOTICE).
