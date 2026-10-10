# A mode that cannot prompt gets a blocking error, not an ask

Status: accepted · Date: 2026-10-10 · Decides: the maintainer

The hook's answer to a commit, a push or a post is an `ask`: the user decides, every time. Two
permission modes have no prompt to show. The hooks reference lists `bypassPermissions` and
`dontAsk` among the values of `permission_mode` in the hook input, and the permission-modes
reference states that `dontAsk` denies anything that would prompt and that `bypassPermissions`
approves everything. An `ask` returned into either mode has nowhere to go.

The decision: when `permission_mode` is one of those two, the hook turns an `ask` or a `deny`
into a blocking error (exit 2) whose stderr carries the same reason plus the sentence that the
mode cannot prompt. The hooks reference states that exit 2 on `PreToolUse` prevents the tool
call and that Claude sees the stderr; it does not qualify this by mode. Whether
`bypassPermissions` lets the block stand is recorded per mode in `CHANGELOG.md` once observed
in this repository, with the procedure in `docs/verification.md`.

## Options considered

| Option | Why it lost |
|---|---|
| Return the `ask` and let the mode decide | in `bypassPermissions` the documentation says everything is approved, so the gate would open exactly where it matters most |
| Return `deny` in those modes | a JSON `deny` is a decision field; the reference says exit 2 blocks even when the fields could not, so the stronger signal is the honest one |
| Refuse to run in those modes at all | blocks `git status`; the hook's own rule is that a broken guard never stops unrelated work |

## Consequences

`hook.py` reads `permission_mode`. A user in those modes sees the reason and runs the command
themselves. `docs/verification.md` carries the two modes as the open assumption.
