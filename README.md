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

Eleven skills that encode the process as rules an agent follows, and three mechanisms that
enforce the rules an agent must not be able to talk its way past:

- a **Claude Code hook** on every Bash command that refuses tool attribution, bulk staging, force
  pushes to protected branches and staged secrets, and asks before every commit, push and post;
- a **reusable GitHub workflow** that fails a pull request whose title, body or commits carry
  attribution, and runs gitleaks over the history;
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

Do not install both ways into Claude Code; the plugin already carries the skills.

**Replacing the upstream skills.** This set descends from, and replaces, these skills; keep one
set installed so a prompt about tests or reviews has one answer:

```bash
npx skills remove grilling grill-with-docs domain-modeling codebase-design tdd to-tickets \
  setup-matt-pocock-skills spec-driven-development incremental-implementation \
  code-review-and-quality unslop -g -y
```

## Baseline

| Component | Needs |
|---|---|
| The hook | `python3` 3.9 or newer on `PATH` (the stock macOS interpreter qualifies); `git`; `gitleaks` optional, used when present. The hook fails closed: on a machine where `python3` does not resolve, every Bash tool call is refused until it does or the plugin is disabled. On Windows, `python3` must resolve to a real executable, not a shim |
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
| `grill-plan` | Rounds of numbered questions over the settled frontier, each with a recommended answer; facts looked up, decisions put to the decider | GRILL-1 to GRILL-4 |
| `decision-records` | Glossary, decision records and dated research documents, as tables with calibration, naming systems and roles, never people | DECIDE-1 to DECIDE-6 |
| `cut-tickets` | One ticket per real work item with acceptance and blockers, no identifiers or names, full links, published only after approval | TICKET-1 to TICKET-6 |
| `test-first` | Seams agreed first, red before green, expected values from an independent source, mocks at boundaries only, commits gated on exit codes | TEST-1 to TEST-7 |
| `thin-slices` | One pull request per step, nothing half-done, scope held, staging by path, a go-ahead per commit, push and post, secrets never printed | SLICE-1 to SLICE-8, STAGE-1, PUSH-1, PUSH-2, SECRET-1, SECRET-2, PROD-1, ASK-1 to ASK-3 |
| `deep-modules` | The vocabulary and moves for deep modules: interface as the test surface, two adapters make a seam, design it twice with consent | DESIGN-1 to DESIGN-5 |
| `setup-conventions` | One-time repository setup: the rules block, tracker and conventions files, the hook config, the workflow and the ruleset as a pull request | SETUP-1 to SETUP-3 |

### Mechanisms

| Rule | What happens | Where |
|---|---|---|
| ATTR-1 | a Co-Authored-By or Signed-off-by trailer naming a tool, a "Generated with" footer or the robot emoji in a commit, pull request, issue or release text: **denied** | hook, CI |
| ATTR-2 | any vendor mention in change text when the repository opts into strict mode: **denied** | hook, CI |
| STAGE-1 | `git add -A`, `--all`, `.`, `-u` without paths, `git commit -a`: **denied** | hook |
| PUSH-1 | a force push to, or deletion of, a protected branch: **denied** | hook, ruleset |
| PUSH-2 | a force push of a tag: **asks**, and says that tag-triggered workflows run again | hook |
| SECRET-1 | a key-shaped literal in the staged changes: **denied** (built-in patterns, plus gitleaks when installed) | hook, CI |
| ASK-1, ASK-2, ASK-3 | every `git commit`, `git push`, and every `gh`/`glab` command that creates or changes something on the forge: **asks**, in every permission mode | hook |
| VOICE-3 to VOICE-8 | dashes as punctuation, counting framings, closing offers, banned words in the prose a repository names through `voice-paths`: **fails the check** | CI, when `voice-paths` is set |

The hook reads the command the agent is about to run, parses it (chains, pipes, heredocs,
message files), and returns one decision with the rule ids and the reason. Precedence is deny over
ask over allow. Everything else runs without a decision from the hook.

### What the mechanisms do not cover

| Gap | Why | What covers it |
|---|---|---|
| Commands outside the Bash tool: MCP tools that post, `!`-prefixed commands typed by the user, other agents | hooks see Bash tool calls only | the skills' text; the CI check for pull request text |
| The merge body typed at squash-merge time | the pull request workflow sees title, body and branch commits; the merge body is written after the checks ran | the hook, when the merge is run through the Bash tool |
| Commit-message rules on the forge | GitHub rulesets offer metadata rules on the Enterprise plan only | the required status check from the workflow |
| A user who sets `disableAllHooks`, or a mod that approves after the hook | the hook is a plugin hook, not a managed one | the CI check; the ruleset |
| The forced prompt under `acceptEdits` and `bypassPermissions` | the documentation states the auto-mode behaviour only | recorded per mode in [`CHANGELOG.md`](CHANGELOG.md) once observed |

## Why no tool attribution

The person who signs a change is the operator of record for it: the one who answers for what
it does. A trailer or footer naming a tool records which product was open, not who is
accountable, and it is the first thing a reader mistakes for the second. The hook strips the
attribution patterns; a repository that wants no vendor named at all in its history turns on
strict mode.

## Configuration

A repository may carry `.agentic-sdlc.json` at its root
([schema](schemas/config.schema.json), [template](templates/agentic-sdlc.json)). Every key has
a default; an absent file means the defaults.

| Key | Default | Rule |
|---|---|---|
| `protected_branches` | `["main", "master"]` | PUSH-1 |
| `attribution.mode` | `"patterns"`; `"strict"` refuses any vendor mention | ATTR-1, ATTR-2 |
| `attribution.vendors` | adds to the built-in names | ATTR-1, ATTR-2 |
| `confirm.commit`, `confirm.push`, `confirm.post` | `true` | ASK-1, ASK-2, ASK-3 |
| `stage.deny_add_all`, `stage.deny_commit_all` | `true` | STAGE-1 |
| `secrets.scan_staged`, `secrets.use_gitleaks`, `secrets.extra_patterns` | `true`, `true`, `[]` | SECRET-1 |
| `posting.extra_commands` | `[]`; regular expressions that count as a post | ASK-3 |

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
         voice-paths: "README.md docs"
   ```

3. Import the ruleset, after editing the required check names to the repository's own:

   ```bash
   gh api -X POST repos/<owner>/<repo>/rulesets --input rulesets/main-protected.json
   ```

## Try the hook by hand

```bash
agentic-sdlc guard 'git add -A'
agentic-sdlc guard 'git commit -m "Fix parser" -m "Co-Authored-By: Claude <noreply@anthropic.com>"'
agentic-sdlc guard 'git push --force origin main'
agentic-sdlc guard 'gh pr merge 12 --squash --body-file notes.md'
```

Each prints the decision, the rule ids and the reason. `--json` prints what the hook returns.

## Structure

```
├── .claude-plugin/        plugin.json, marketplace.json
├── hooks/hooks.json       the PreToolUse hook on Bash
├── src/agentic_sdlc/      command.py (parse), guard.py (decide), text.py (patterns),
│                          config.py, registry.py, hook.py (adapter), cli.py
├── rules/registry.json    every rule, stable ids, mechanism, owner
├── schemas/               config and registry JSON Schemas
├── skills/<name>/         SKILL.md and references/ per skill
├── templates/             what setup-conventions writes into a repository
├── rulesets/              the branch ruleset to import
├── docs/coverage.md       generated from the registry
├── tests/                 one test per mechanism rule, the hook contract, the CLI
└── .github/workflows/     gate.yml (this repo), conventions.yml (reusable)
```

## Development

```bash
uv sync --group dev
just check            # ruff, pytest, validate, check-skills, lint-voice, coverage, plugin validate
just test-stock       # the suite on the stock macOS python3
just guard 'git add -A'
```

CI runs the suite on Python 3.9 and 3.14, validates the plugin in strict mode, and installs every
skill with the skills CLI into a throwaway home.

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
