# Agent mode never asks

Status: proposed · Date: 2026-11-25 · Decides: the maintainer · Supersedes: the kept-asks clause of [ADR 0008](0008-the-agent-decides-and-the-guard-records.md)

This breaks existing behaviour. In agent mode, a read of a secret-named file (SECRET-3), a change
to the guard's own configuration (GUARD-2) and a gated command the guard could not analyse used
to ask a person. They are now refused, and so are the asks the hook adds for a print of the
environment or of a credential variable (SECRET-2), and a database write that reaches
production (PROD-1). Each refusal is recorded with AGENT-1.
Every other call that a rule would ask about still runs and is recorded. Confirm mode keeps the
asks. Under Codex, an ask in confirm mode is refused, because Codex takes only a deny from a
PreToolUse hook.

## Context

Many agent sessions run for hours with nobody watching. A prompt in such a
session waits until someone opens it, so a single ask stops a run that nobody watches. Codex
0.171 rejects `ask` from a PreToolUse hook (its binary carries "PreToolUse hook returned
unsupported permissionDecision:ask"), so an ask there would be dropped and the call would run
unchecked. The kept asks protect what the other rules rely on, or what cannot be undone: a change to the
guard's configuration can switch every refusal off, a secret read or print puts the secret into
the transcript, and a production write is the step PROD-1 exists to stop.

## Decision

- In agent mode, the default, the guard returns allow or deny, never ask (AGENT-1).
- A secret-file read, a secret print, a change to the guard's configuration and a production
  write are refused, with a reason that says a person can do it or can start a session with `AGENTIC_SDLC_MODE=confirm` to be asked.
- A gated command the guard could not analyse is refused in agent mode; its refusal rules never
  ran on it.
- An ask for an agent that cannot show one (an event carrying Codex's `turn_id`) is refused
  with the same reason it would have asked with.
- The unattended signal keeps its RUN-1 reason; in agent mode it changes only the wording of
  the refusal.

## Consequences

- An agent in agent mode cannot change `.agentic-sdlc.json`, `.claude/settings.json`, a git hook,
  a git or Codex configuration file or `.pre-commit-config.yaml`, through the file tools, a Codex
  patch or the shell. The setup skill therefore runs its writes
  in a session started with `AGENTIC_SDLC_MODE=confirm`.
- A task that needs a secret file, a secret value or a production write is a held call for a
  person.
- Nothing in agent mode can stall at the guard. Claude Code's or Codex's own approval prompts
  are outside the guard; the long-running skill names the launch flags that handle them.

Confirmation: `tests/test_modes.py::test_agent_mode_never_asks` decides every command the
registry says asks, in agent mode, and fails on any ask;
`test_an_ask_is_refused_for_an_agent_that_cannot_prompt` covers a Codex-shaped event.
