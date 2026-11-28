# The agent decides, and the guard records

Status: proposed; the kept-asks clause is superseded by [ADR 0009](0009-agent-mode-never-asks.md) · Date: 2026-11-23 · Decides: the maintainer · Extends: [ADR 0005](0005-a-blocking-error-where-no-prompt-is-possible.md), [ADR 0007](0007-an-unattended-run-never-waits-on-a-person.md)

This breaks existing behaviour. In 1.x the guard answers a commit, a push, a forge post, a read
of a secret-named file, an edit of its own configuration and an untraced gated command with
`ask`, and a person answers. From 2.0.0 the default is agent mode: each of those calls runs, and
the decision record keeps the rule that would have asked, with AGENT-1 beside it. A read of a
secret-named file and an edit of the guard's configuration still ask. The rules that
refuse still refuse: staging everything (STAGE-1), skipping hooks (GUARD-1), a force push or
delete of a protected branch (PUSH-1), an attribution trailer (ATTR-1) and a secret in a commit
(SECRET-1). Confirm mode keeps the 1.x behaviour. The unattended signal of ADR 0007 applies there,
and in agent mode to the two asks that remain.

## Context

The operator grants agents decision sovereignty: an agent decides its own commits, pushes,
posts and launches, under its own instructions. An ask spends a person's attention on a call the
agent was trusted to make, and in a run nobody watches it either stops the run (ADR 0005) or,
with the signal, becomes a refusal (ADR 0007). Neither is what the operator asked for. What
stays worth refusing is what an agent cannot undo or what leaks: a secret in history, a rewritten
protected branch, hooks skipped so the other checks never run, the operator's own standing rules
on staging and attribution.

## Decision

- `mode` in `.agentic-sdlc.json`, `agent` (the default) or `confirm`. `AGENTIC_SDLC_MODE`
  overrides the file; a value it does not know means `confirm`, so a typo fails toward a person.
  An unknown value in the file, or a configuration file the guard cannot read, also means
  `confirm`: that file may be the one that set confirm mode.
- In agent mode, `apply_mode` in the guard turns every `ask` into `allow` and adds AGENT-1,
  except an ask that names a rule in `KEPT_ASKS`. The hook says nothing for an allow, so Claude
  Code's own permission system still decides the call; the guard adds no prompt and no refusal of
  its own.
- `KEPT_ASKS` holds GUARD-2 and SECRET-3, which keep asking in agent mode. An edit of the guard's
  configuration can switch every refusal off: an empty `protected_branches` lets a force push to
  `main` through, and the secret scan and the hook can be removed the same way. A read of a
  secret-named file puts the secret into the transcript. With the unattended signal set, these
  asks are refused (RUN-1), so a run nobody watches does not stop at a prompt.
- A `deny` is never changed by the mode.
- The decision record keeps every AGENT-1 and RUN-4 decision whatever `record.decisions` says;
  other decisions follow the setting. The record holds a hash of the command, never its text.
- A command the guard could not analyse still asks, or with the signal is refused: the refusal
  rules never ran on it.
- The unattended signal (RUN-1) holds every ask in confirm mode, and in agent mode only the kept
  asks.
- Starting an unattended run is the agent's decision too: RUN-4 records a command that sets
  `AGENTIC_SDLC_UNATTENDED` and neither asks nor refuses.
- Registry: `record` joins `deny` and `ask` as a hook decision, and `examples_agent` holds
  examples run with no mode set.
- The release is 2.0.0, because the default answer to the most common calls changes.

## Alternatives

| Alternative | Why it lost |
|---|---|
| Keep asking by default, agent mode opt-in | The operator named agent decision as the normal mode; an opt-in leaves every new repository asking |
| Agent mode also lifts the refusals | A secret in history and a rewritten protected branch cannot be undone by the agent that caused them; the operator's standing rules stay rules |
| Return `allow` from the hook in agent mode | An explicit allow skips Claude Code's own permission system as well; saying nothing leaves that system in place |
| One flag per rule (`confirm.commit`, `confirm.push`, `confirm.post`) | They exist and stay, but they cover three of the asks; the mode covers all of them in one place |

## Failure modes

| Failure | Allowed impact | Mechanism | Test |
|---|---|---|---|
| A repository that needs a person in the loop runs in agent mode | calls run unreviewed until the repository sets confirm | `"mode": "confirm"` or `AGENTIC_SDLC_MODE=confirm` | `tests/test_modes.py::test_confirm_mode_from_the_file_asks` |
| A typo in the environment or the file, or a configuration file the guard cannot read | none: the guard asks | an unknown value or an unreadable file means confirm | `test_an_unknown_mode_in_the_environment_means_confirm`, `test_an_unknown_mode_in_the_file_means_confirm`, `test_a_config_file_the_guard_cannot_read_means_confirm` |
| Agent mode lifts a refusal | none allowed | `apply_mode` returns on anything but `ask` | `test_a_refusal_still_refuses`, mutant "agent mode also lifts refusals" killed |
| An agent edits the guard's configuration to switch a refusal off | none: the edit asks, or with the signal is refused | `KEPT_ASKS` in `apply_mode` | `test_a_secret_read_or_a_guard_config_edit_still_asks_in_agent_mode`, `test_a_kept_ask_is_refused_in_an_unattended_agent_mode_run`, mutants "no kept asks" and "no refusal with the signal" killed |
| Nobody can see what the agent decided | none: every AGENT-1 and RUN-4 decision is kept with the record off | `record.must_record` in the hook, on the Bash and the file-tool paths | `test_an_agent_decision_is_recorded_with_no_record_setting` |

## Compatibility

| Client | Effect |
|---|---|
| Claude Code, any permission mode | agent mode: no prompt and no blocking error from the guard on an ask-class call, except GUARD-2 and SECRET-3; confirm mode: as 1.x |
| A repository with `confirm.commit: false` and similar | unchanged; those flags still remove the ask they name in confirm mode |
| A run that sets `AGENTIC_SDLC_UNATTENDED` | agent mode: GUARD-2 and SECRET-3 are refused (RUN-1), nothing else changes; confirm mode: ADR 0007 |
| The decision record | one more rule id (AGENT-1) on calls that would have asked |

Decided by the maintainer, 2026-11-23: a read of a secret-named file (SECRET-3) and an edit of the
guard's own configuration (GUARD-2) keep asking in agent mode.

Parked: a per-rule mode, and an agent-visible note on a recorded ask (a PostToolUse context line).

Confirmation: `tests/test_modes.py` (26 cases) and `tests/test_operability.py::test_registry_agent_examples_decide_as_written`
run on every `just check`; six mutants of the mode code, four of the record rule, two of the confirm fallback and two of the kept asks were killed on
2026-11-23.
