# An unattended run never waits on a person

Status: proposed · Date: 2026-11-22 · Decides: the maintainer · Extends: [ADR 0005](0005-a-blocking-error-where-no-prompt-is-possible.md)

The guard answers a commit, a push and a post with `ask`. In a run that nobody watches, an ask
stops the run. The hooks reference states that a hook's `ask` in auto mode goes to the permission
prompt; the agent view reference shows a background session as "Needs input" while a prompt
waits; the routines reference states that a scheduled task waits on any prompt until someone
opens the run. In the modes that cannot prompt, ADR 0005 turns the ask into a blocking error: the
run survives, but no commit lands, so a long run cannot checkpoint its work. The hook input
carries the permission mode and nothing that says whether a person is present.

The decision: whoever launches the run marks it unattended with the environment variable
`AGENTIC_SDLC_UNATTENDED`. With it set, no decision is an ask.

- A commit on a branch that is not protected passes, so the run checkpoints. A commit on a
  protected branch or a detached HEAD is refused.
- A push passes only to a branch that matches `unattended.push_branches` and is not protected,
  with no force, tags, deletion or mirror. The list is empty by default, so every push is refused
  until a repository names its agent branches.
- Every other ask becomes a deny under RUN-1. The reason tells the agent that nobody can approve
  now, not to retry or work around the call, to carry on, and to list the call in its run report.
- Deny rules do not change. An analysis failure inside the hook is refused, not asked.

In the modes that cannot prompt, the blocking error now speaks to the agent ("Do not retry it:
carry on with the next step and list it in the run report") in place of telling a person to run
the command themselves. This text applies with or without the signal.

## Options considered

| Option | Why it lost |
|---|---|
| Infer "nobody is watching" from `permission_mode` | the input has no presence field, and auto mode runs both attended and unattended |
| A key in `.agentic-sdlc.json` | committed config travels with every clone, so a clone or an agent's edit would switch the asks off for every user; the launcher is the party that knows nobody is watching |
| `confirm.scope: off` | it exists, but it turns the asks into allows everywhere, pushes and posts included |
| Return `defer` | it ends the turn of a print-mode run for the calling program, which stops the run it is meant to keep going |
| Keep the ask and rely on `--permission-prompts none` | that denies the commit too, so the run still cannot checkpoint, and it does nothing for auto mode or scheduled tasks |

## Consequences

- An unattended commit on a working branch passes without the go-ahead of ASK-1. The go-ahead
  moves to the merge, where a person reads the branch, the run report and the held calls.
- Agent pushes wait for a repository decision: the patterns in `unattended.push_branches`.
- The signal is the environment of the Claude Code process. `.agentic-sdlc.json` cannot set it,
  and an agent's edit to `.claude/settings.json` through the file tools is refused during the run
  (GUARD-2). A background session takes its supervisor's environment, and a repository's committed
  `.claude/settings.json` `env` block may set the variable; both are inferred from the
  documentation, not tested, and both are listed in the README's gaps table.
- The skills `unattended-runs` and `session-handoff` carry the practice around the mechanism: the
  finish condition, the spend cap, the branch, the progress files and the run report.

Confirmation: `tests/test_unattended.py::test_no_example_and_no_fuzz_command_asks` sends every
registry example and the fuzz corpus through the guard with the signal on and fails on any ask;
the hook's answer per permission mode is in the same file, and RUN-1's `examples_unattended` run
in `tests/test_operability.py`. Not yet observed in a real run; `docs/verification.md` is the
procedure.
