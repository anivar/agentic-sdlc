---
name: unattended-runs
description: >
  Run agent work that nobody watches without stalling it at a prompt, in Claude Code or Codex.
  In agent mode, the guard's default, the guard never asks: a call it would ask about runs and
  is recorded, and a secret read or print, a change to the guard's configuration and a
  production write are refused. In a
  repository set to confirm mode, whoever launches the run sets
  AGENTIC_SDLC_UNATTENDED, so the guard never asks: checkpoint commits pass on a working
  branch, pushes pass only to listed agent branches, and every other gated call is refused with
  a reason the agent acts on. The run starts with a finish condition, a spend cap and a branch
  of its own, and ends with a run report in a file that lists the held calls for a person.
  Triggers on: "run this overnight", "long-running", "unattended", "while I'm away",
  "background session", "keep going until", "/goal", "claude -p", "headless", "scheduled task",
  "routine", "don't stop for permission", "the run stopped at a prompt", "Needs input".
license: MIT
compatibility: Claude Code or Codex with the agentic-sdlc plugin for the guard side; the run modes are the ones Claude Code documented in November 2026 and the flags Codex 0.171 prints in its help.
metadata:
  author: Anivar Aravind
  author_url: https://anivar.net
  version: 1.0.0
  tags: long-running, unattended, headless, permissions, checkpoints, hooks
  derived_from: the long-running harness posts on Anthropic's engineering blog for the checkpoint commit, the progress file and the separate judge; the guard behaviour is the author's own
  rules: RUN-1 RUN-2 RUN-3 RUN-4 HANDOFF-1 HANDOFF-3 HANDOFF-4 SLICE-6 ASK-1 ASK-2 ASK-3 AGENT-1 PUSH-1 STAGE-1 GUARD-1 GUARD-2 SECRET-2 SECRET-3 PROD-1
---

# Unattended runs

A run that nobody watches stops at its first prompt and waits until someone opens it. Set the
run up so nothing waits on a person, the work checkpoints itself on its own branch, and every call that
needed a person is written down for one.

## The rules

| Id | Rule | In practice |
|---|---|---|
| RUN-1 | An unattended run never waits on a person | Hook, opt-in. In agent mode nothing asks, so the signal only changes the reason a kept ask is refused (SECRET-2, SECRET-3, GUARD-2, PROD-1). In confirm mode, with `AGENTIC_SDLC_UNATTENDED` set by the launcher, a commit on a branch that is not protected passes; a push passes only to a branch that matches `unattended.push_branches` and is not protected, with no force, tags, deletion or mirror. Every other call that would ask (a commit elsewhere, any other push, a post, a secret file, a change to the guard's configuration) is refused with a reason that says not to retry. Deny rules still refuse (STAGE-1, PUSH-1, GUARD-1). |
| RUN-2 | Start with a finish line, a cap and its own branch | A finish condition a check can show, a spend cap, a working branch or worktree, and in confirm mode the signal set by whoever launches. Use the platform's own loop, not a loop of your own. |
| RUN-3 | End with a report in a file | Commits with shas, checks with commands and results, held calls, failures and skips, what is left. A held call is never retried or worked around during the run. |
| RUN-4 | An agent may start an unattended run, and the start is recorded | Hook, record only. A command that sets `AGENTIC_SDLC_UNATTENDED` (a leading assignment, `env`, `export`) is the agent's own decision: never asked about or refused, written to the decision record. The run it starts follows RUN-1. |

In agent mode the agent decides every commit, push and post itself, and the decision record
keeps each one. A plain push to a protected branch runs too; only a force push or a delete is
refused (PUSH-1), so the run's own branch is the agent's discipline, not the guard's. In confirm
mode with the signal, a commit on a working branch passes without the person's go-ahead SLICE-6
asks for, because nobody is there to give it. The go-ahead moves to the merge: a person reads the branch, the report and the
held calls, then decides (ASK-1, ASK-2 and ASK-3 apply to them as usual).

## Before the launch

1. A branch or worktree for the run alone: `git switch -c agent/<task>`, or `--worktree <task>`,
   which names the branch `worktree-<task>`. Never the default branch.
2. In confirm mode, where pushes may land, once per repository, in `.agentic-sdlc.json`:
   `"unattended": {"push_branches": ["agent/*", "worktree-*"]}`. Without it every push is
   refused and the work stays in the run's checkout, which in a cloud run is lost with the
   container unless the run can push. Agent mode needs no list.
3. The files the run reads and writes (HANDOFF-1): `.agent/progress.md` and
   `.agent/features.json`, with the finish condition at the top of both.
4. The finish condition, as something the run's own output can show: "`just check` exits 0 and
   every entry in `.agent/features.json` has status `passing`". Not "the feature is done".

## Launch

One command does the launch: `agentic-sdlc run <name> "<task and finish condition>"`, with
`--agent codex` for Codex, `--budget` and `--hours` for the caps. It makes the branch
`agent/<name>` in its own worktree, starts the run detached with nothing that can prompt, and
returns. `agentic-sdlc runs` lists the runs and their state; `runs read`, `runs wait` and
`runs stop` act on one by name. The rows below are the same launches by hand.

In agent mode, the default, leave `AGENTIC_SDLC_UNATTENDED=1` out of the rows below: it changes
nothing there. In a repository set to confirm mode, keep it.

| Where | How |
|---|---|
| Print mode, local or CI | `AGENTIC_SDLC_UNATTENDED=1 claude -p "<task and finish condition>" --worktree <task> --permission-mode auto --permission-prompts none --max-budget-usd <cap>` |
| A session you leave running | `AGENTIC_SDLC_UNATTENDED=1 claude --permission-mode auto`, then `/goal <finish condition>`. A goal does not change the permission mode; auto mode is what lets its turns run. |
| Cloud scheduled task | Set `AGENTIC_SDLC_UNATTENDED=1` in the cloud environment's environment variables. Scheduled tasks start in auto mode. |
| Background session | The session runs under a supervisor process, so a variable exported only in the launching shell may not reach the hook. Prefer one of the rows above, or confirm in the first minute that a checkpoint commit passes without a prompt. |
| Codex, headless | Trust the plugin's hooks once in an interactive `codex` session, then `codex exec "<task and finish condition>" --sandbox workspace-write --approve-for-me`. `--approve-for-me` routes Codex's own approval requests through its automatic review. Codex has no spend cap flag, so the finish condition and a timeout on the launching job bound the run. |

`--permission-prompts none` denies anything else that would prompt and tells the agent not to
retry, so the platform's own prompts cannot stall the run either. Codex takes no ask from a
hook at all, so the guard refuses there whatever it would have asked. In confirm mode without the
signal, modes that cannot prompt refuse every commit (ADR 0005): the run survives but cannot checkpoint.

## During the run

- Take one item from the feature list at a time. Commit when it passes its check, and before any
  step that is hard to undo. Commit text follows thin-slices.
- A refused call: do not retry it, do not reach the same effect through another command, and do
  not edit the guard's configuration (GUARD-2). Write it into the held calls of the progress file
  at once (HANDOFF-4), then take the next step.
- An item that keeps failing the same way is marked `blocked` with the failing command and its
  output, and the run moves to the next item.
- A secret file stays unread (SECRET-3) and a secret value unprinted (SECRET-2). A production
  write waits for a person (PROD-1). If the work needs one, that is a held call.
- An item counts as passing only on its recorded check (HANDOFF-3); the run's own opinion that it
  works is not evidence.

## The run report

Written to `.agent/run-report.md` and committed with the last checkpoint. The finish condition's
result goes in the first line.

```markdown
# Run report: <task>
Finish condition: <text> · Met: yes | no · Branch: <branch> · Started <UTC> · Ended <UTC>

## Commits
| sha | What it does |

## Checks
| Command | Result |

## Held calls
| Call | Rule | Why it waits | What a person does |

## Failed, blocked or skipped
| Item | What happened | Evidence |

## Left
<items not started, in order>
```

## What the guard does

| Call | Agent mode (the default) | Confirm mode, attended | Confirm mode, unattended |
|---|---|---|---|
| Commit on a working branch | runs, recorded (ASK-1, AGENT-1) | asks (ASK-1) | passes |
| Commit on a protected branch or a detached HEAD | runs, recorded | asks | refused |
| Push to a branch in `push_branches` | runs, recorded (ASK-2, AGENT-1) | asks (ASK-2) | passes |
| Any other push, tags | runs, recorded; a force push or delete of a protected branch is refused (PUSH-1) | asks, or refused to a protected branch (PUSH-1) | refused |
| A post to the forge: pull request, comment, review | runs, recorded (ASK-3, AGENT-1) | asks (ASK-3) | refused |
| A secret file or value, the guard's own configuration, a production write | refused (SECRET-2, SECRET-3, GUARD-2, PROD-1, AGENT-1) | asks (SECRET-2, SECRET-3, GUARD-2, PROD-1) | refused |
| `git add -A`, `--no-verify` | refused (STAGE-1, GUARD-1) | refused | refused |

## Companion skills

| Need | Skill |
|---|---|
| The progress file, the feature list, the start-up routine | invoke `session-handoff` |
| Commit text and the size of each checkpoint | thin-slices |
| The read a person does before the merge | review-change |
| Calibrating what the report claims | evidence |
