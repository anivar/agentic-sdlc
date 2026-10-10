# The decision record holds a hash of the command, never its text

Status: accepted · Date: 2026-10-10 · Decides: the maintainer

A team rolling the hook out over an existing workflow needs to see what it would refuse before
it refuses anything, and a maintainer answering "why was this blocked" needs the decision, the
rules and the time it took. That is a record under `.git/agentic-sdlc/decisions.jsonl`, written
only when the repository turns it on (`record.decisions`, `record.shadow`, or the environment
variables `AGENTIC_SDLC_RECORD` and `AGENTIC_SDLC_SHADOW` for one session).

The decision: each line carries the time, the event and tool, the permission mode, the
decision, the rule ids, the reason lines, the command kinds, the milliseconds, the shadow flag
and a truncated SHA-256 of the command. The command text itself is never written: a token
typed into a command line would otherwise land in a file that outlives the session. The reason
lines may name a branch, a file or a trailer the rule matched, which is what the rule already
told the agent.

## Options considered

| Option | Why it lost |
|---|---|
| Write the command text, redacted by the secret patterns | a pattern miss becomes a stored secret; the hash answers "was it this command" without the risk |
| Write nothing, ever | no rollout path and no way to answer "why" after the fact |
| A record outside the repository (`~/.agentic-sdlc/`) | mixes repositories with different rules; under `.git/` it leaves with the clone and never enters the tree |

## Consequences

`record.py` writes and reads the record; `agentic-sdlc log` prints it. `SECURITY.md` states
what the record holds. In shadow mode every decision is recorded and every command is let
through, so the record is the only evidence the hook ran.
