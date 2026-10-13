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

Eleven skills that encode the process as rules an agent follows, and four mechanisms that
enforce the rules an agent must not be able to talk its way past:

- a **Claude Code hook** on every Bash command that refuses tool attribution, bulk staging,
  hook-bypass flags, force pushes to protected branches and staged secrets, and asks before every
  commit, push and post; the same hook asks before a credential file is read or the guard's own
  configuration is edited through the file tools, and checks the commit that just landed;
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

**Any other agent** (skills only; the hook is Claude Code specific):

```bash
npx skills add anivar/agentic-sdlc -g
```

Do not install both ways into Claude Code; the plugin already carries the skills. The skill files
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
| The hook | `python3` 3.9 or newer on `PATH` (the stock macOS interpreter qualifies); `git`; `trufflehog` optional, used when present, with verification and the update check off. The hook fails closed: on a machine where `python3` does not resolve, every Bash tool call is refused until it does or the plugin is disabled. On Windows, `python3` must resolve to a real executable, not a shim. The hook has a 30 s budget; its own git and TruffleHog calls stay under it |
| The plugin | Claude Code 2.1.211 or newer for the forced prompt in auto mode; 2.1.295 or newer for `onFailure: block` |
| The CI check | GitHub Actions; `gh` is preinstalled on the runners |
| The skills | any agent that reads `SKILL.md` |

## What is inside

### Skills

| Skill | What it does | Rules |
|---|---|---|
| `evidence` | Calibrate every claim: Verified, Measured, Inferred, Planned; verify at the production sha; agent output is a lead; read sources in full; compute a headline number twice; sweep after one defect | EVID-1 to EVID-10 |
| `plain-voice` | The decision first, current state only, open points left open, misses in the headline, no rhetorical structure, no dashes as punctuation, no tool attribution | VOICE-1 to VOICE-13, ATTR-1, ATTR-2 |
| `review-change` | Findings on the introducing change at its head sha, one per thread in Conventional Comments, a summary that ends in a decision, a mutation check before trusting a test, an adversarial read of your own work | REVIEW-1 to REVIEW-10 |
| `plan-project` | One plan file: outcome with measures, decisions as options, assumptions tied to tests, dated steps with done-when, gates, risks, rollout, cut order; the turn ends after the plan | PLAN-1 to PLAN-9 |
| `grill-plan` | Rounds of numbered questions over the settled frontier, each with a recommended answer; facts looked up, decisions put to the decider | GRILL-1 to GRILL-3 |
| `decision-records` | Glossary, decision records and dated research documents, as tables with calibration, naming systems and roles, never people | DECIDE-1 to DECIDE-6 |
| `cut-tickets` | One ticket per real work item with acceptance and blockers, no identifiers or names, full links, published only after approval | TICKET-1 to TICKET-6 |
| `test-first` | Seams agreed first, red before green, expected values from an independent source, mocks at boundaries only, commits gated on exit codes | TEST-1 to TEST-7 |
| `thin-slices` | One pull request per step, nothing half-done, scope held, staging by path, a go-ahead per commit, push and post, secrets never printed | SLICE-1 to SLICE-8, STAGE-1, PUSH-1, PUSH-2, SECRET-1, SECRET-2, PROD-1, ASK-1 to ASK-3 |
| `deep-modules` | The vocabulary and moves for deep modules: interface as the test surface, two adapters make a seam, design it twice with consent | DESIGN-1 to DESIGN-5 |
| `setup-conventions` | One-time repository setup: the rules block, tracker and conventions files, the hook config, and the forge's check (workflow and ruleset, or the GitLab job) as a pull request | SETUP-1 to SETUP-3 |

### Mechanisms

| Rule | What happens | Where |
|---|---|---|
| ATTR-1 | any trailer naming a tool, a "Generated with" footer, or the robot emoji beside one, in a commit, pull request, issue or release text: **denied** | hook, before the command and again on the message at HEAD after a commit ran; git `commit-msg` hook; CI for pull request title, body and commits |
| ATTR-2 | any vendor mention in change text when the repository opts into strict mode: **denied** | hook, git `commit-msg` hook, CI |
| STAGE-1 | `git add -A`, `--all` or `-u` without a narrowing path, a root pathspec such as `.`, `git commit -a`: **denied**; `git add -A src/` passes | hook |
| PUSH-1 | a force push to, or deletion of, a protected branch: **denied** | hook, git `pre-push` hook, ruleset |
| PUSH-2 | a force push of a tag: **asks**, and says that tag-triggered workflows run again | hook |
| SECRET-1 | a key-shaped literal in the staged changes: **denied** (built-in patterns, plus TruffleHog's detectors when installed, over the added lines only) | hook, git `pre-commit` hook, CI |
| ASK-1, ASK-2, ASK-3 | every `git commit`, `git push`, and every `gh`/`glab` command that creates or changes something on the forge: **asks**. The forced prompt is documented for auto mode. In `bypassPermissions` and `dontAsk`, which cannot prompt, the hook returns a blocking error with the reason instead ([ADR 0005](docs/adr/0005-a-blocking-error-where-no-prompt-is-possible.md)); what each mode does is recorded in [`CHANGELOG.md`](CHANGELOG.md) as it is observed | hook |
| TRACE-1 | a command that mentions a commit, push, bulk add or forge write but cannot be traced to a `git`, `gh` or `glab` call (a variable, an interpreter, an unusual wrapper): **asks** | hook |
| GUARD-1 | `--no-verify` or `commit -n`, a `git -c core.hooksPath=…`, `include.path=…` or alias override on the command line, or `git config` setting those keys: **denied** | hook |
| GUARD-2 | an edit to `.agentic-sdlc.json`, a git hook, `.claude/settings.json`, `.claude/settings.local.json` or `.pre-commit-config.yaml` through the file tools: **asks** | hook, on Edit, Write and MultiEdit |
| SECRET-3 | reading, grepping, copying or sending a file that holds credentials by name (`.env` files, private keys, `.netrc`, `.npmrc`, `credentials.json`, PEM and keystore files): **asks** | hook, on Bash, Read and Grep |
| VOICE-3 to VOICE-8 | dashes as punctuation, counting framings, closing offers, banned words in the prose a repository names through `voice-paths`: **fails the check** | CI, when `voice-paths` is set |

The hook reads the command the agent is about to run, parses it (chains, pipes, heredocs,
message files, shell wrappers such as `sh -c` and `eval`, `git -C` and a leading `cd`), and
returns one decision with the rule ids and the reason. Precedence is deny over ask over allow.
Everything else runs without a decision from the hook.

Every refusal and every ask ends with the rule's fix line. With `record.decisions` on, each
decision is appended to `.git/agentic-sdlc/decisions.jsonl` as a hash of the command, the
decision, the rule ids, the permission mode and the milliseconds, never the command text;
`record.shadow` records and lets everything through, which is how a team sees what the hook
would refuse before it refuses anything. `agentic-sdlc log` prints the record.

What a refusal looks like:

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
ask: SECRET-3
  SECRET-3: Reading a secret file asks: .env holds credentials by name. Fix: Name the variable or the file and its length or hash instead; read the file only when the user says yes.

$ agentic-sdlc guard 'gh pr merge 12 --squash'
ask: ASK-3
  ASK-3: A post waits for a go-ahead: gh pr merge publishes or changes something on the forge. Fix: Show the draft in the conversation; post when the user says yes.
```

### What the mechanisms do not cover

| Gap | Why | What covers it |
|---|---|---|
| Commands outside the Bash tool: MCP tools that post, `!`-prefixed commands typed by the user, other agents | hooks see Bash tool calls only | the git hooks for commits and pushes made any way at all; the CI check for pull request text |
| The merge body typed at squash-merge time | the pull request workflow sees title, body and branch commits; the merge body is written after the checks ran | the hook, when the merge runs through the Bash tool with the body inline or in a file that exists; a body built by `$( … )` is not readable before it runs and the hook says so in its ask |
| Commit-message rules on the forge | GitHub rulesets offer metadata rules on the Enterprise plan only | the required status check from the workflow |
| A user who sets `disableAllHooks`, or a mod that approves after the hook | the hook is a plugin hook, not a managed one | the CI check; the ruleset |
| Modes that cannot prompt (`bypassPermissions`, `dontAsk`) | an `ask` has nowhere to go there | the hook returns a blocking error with the reason in those modes; observed in print mode on 2026-10-10 ([`CHANGELOG.md`](CHANGELOG.md)): the block held for the commit, the secret file and the Read tool in both |
| The interactive prompt under `acceptEdits` and auto | the documentation states the auto-mode behaviour; print mode refuses an ask in both ([`CHANGELOG.md`](CHANGELOG.md)) | recorded once observed interactively; `docs/verification.md` is the procedure |
| A gated command the parser cannot see: a git call inside an interpreter (`python -c`, `node -e`), behind a shell alias or a variable (`$g push`), or a direct API call with `curl` | the parser follows wrappers, substitutions and `cd`, not program semantics | TRACE-1 asks when the text still names the operation, and the pre-check names the inline interpreter shapes; `trace.untracked` at ask or deny closes the hole for everything else the parser cannot trace; `posting.extra_commands` can name `curl`; the CI check and the ruleset are the backstops |
| Message text built by a substitution (`-m "$(cat m.txt)"`, `--file=<( … )`) | the text does not exist until the command runs | the ask names it; after the commit ran, the hook compares HEAD with the sha recorded before the command and reads the message that landed, so a backdated commit is still reported with the instruction to amend (when nothing was recorded, a 300-second timestamp guess stands in as the weak fallback); the pull request check scans the resulting commits |
| A credential read the parser cannot see: through an interpreter (`python -c 'open(".env")'`), or the whole environment printed (`env`, `printenv`) | SECRET-3 matches file names on the command line and in the file tools, not program semantics | SECRET-2 in the skills (never print a secret); the agent's sandbox |
| An edit to the guard's own configuration through Bash (`sed -i`, a redirection), or hooks moved through the environment (`GIT_CONFIG_PARAMETERS`) | GUARD-2 watches the file tools; the parser drops redirection targets and environment assignments | the pull request review sees the change; CI and the ruleset do not read the local config |
| A crash in the hook on the file tools | it carries no `onFailure: block`, by design: a broken guard must not stop every read | the Bash hook keeps `onFailure: block`; the error shows in the transcript |

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
| `protected_branches` | `["main", "master"]` | PUSH-1 |
| `attribution.mode` | `"patterns"`; `"strict"` refuses any vendor mention | ATTR-1, ATTR-2 |
| `attribution.vendors` | adds to the built-in names | ATTR-1, ATTR-2 |
| `confirm.commit`, `confirm.push`, `confirm.post` | `true` | ASK-1, ASK-2, ASK-3 |
| `stage.deny_add_all`, `stage.deny_commit_all` | `true` | STAGE-1 |
| `trace.untracked` | `"allow"`; `"ask"` or `"deny"` answers with that decision for a command the parser cannot trace to git, gh or glab; a command made only of read-only programs still passes | TRACE-2 |
| `secrets.scan_staged`, `secrets.scanner`, `secrets.extra_patterns` | `true`, `"trufflehog"` (or `"none"`), `[]`; the 1.0 key `use_gitleaks` still reads, with a warning | SECRET-1 |
| `posting.extra_commands` | `[]`; regular expressions that count as a post | ASK-3 |
| `record.decisions`, `record.shadow`, `record.path` | `false`, `false`, `<git common dir>/agentic-sdlc/decisions.jsonl`; `AGENTIC_SDLC_RECORD=1` and `AGENTIC_SDLC_SHADOW=1` override for one session | the decision record ([ADR 0006](docs/adr/0006-the-decision-record-holds-a-hash-not-the-command.md)); shadow records and lets every command through |

## Adopting it in a repository

1. In the repository, run `/setup-conventions` once. It explores, confirms the choices, and
   writes the rules block, `docs/agents/tracker.md`, `docs/agents/conventions.md` and
   `.agentic-sdlc.json` as a pull request.
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

### GitLab

The plugin, the skills and the git hooks are forge-neutral. For the merge request check,
`agentic-sdlc check-mr` reads the predefined `CI_MERGE_REQUEST_*` variables and the commits since
the merge base; [`gitlab-ci.yml`](skills/setup-conventions/assets/gitlab-ci.yml) is the job to include.

## Try the hook by hand

The CLI ships inside the plugin and is not on PyPI; run it from the repository with `uvx`:

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
├── .claude-plugin/        plugin.json, marketplace.json
├── hooks/hooks.json       the hooks: PreToolUse on Bash and the file tools, PostToolUse on Bash
├── src/agentic_sdlc/      command.py (parse), guard.py (decide), text.py (patterns),
│                          config.py, registry.py, record.py, hook.py (adapter), cli.py
├── rules/registry.json    every rule, stable ids, mechanism, owner
├── schemas/               config and registry JSON Schemas
├── skills/<name>/         SKILL.md, references/ and NOTICE per skill; setup-conventions/assets/ holds what it writes
├── rulesets/              the branch ruleset to import
├── .pre-commit-hooks.yaml the three git hooks for the pre-commit framework
├── evals/                 behavioural cases for `claude plugin eval`
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
```

CI runs the suite on Python 3.9 and 3.14 and on the stock macOS interpreter, validates the plugin
in strict mode, and installs every skill with the skills CLI into a throwaway home. A release is
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
