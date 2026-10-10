# Security

## Reporting

Report a vulnerability through GitHub's private vulnerability reporting on this repository
(Security tab, "Report a vulnerability"). Do not open a public issue for it. Expect an
acknowledgement within seven days.

## What the hook does and does not do

The hook reads the JSON event Claude Code sends for a Bash tool call, parses the command
string, and may run read-only git commands in the working directory (`rev-parse`,
`symbolic-ref`, `show-ref`, `diff --cached`, and `log -1` after a commit ran) and
`gitleaks git --staged` when gitleaks is installed. It reads message files the command names
when they exist. For the file tools (Read, Grep, Edit, Write, MultiEdit, NotebookEdit) it reads
the path in the event and nothing else. It sends nothing over the network and prints no secret:
a staged secret is reported by pattern name and line number only, and a credential file is
named, never read.

It writes nothing unless the repository turns the decision record on (`record.decisions` or
`record.shadow` in `.agentic-sdlc.json`, or `AGENTIC_SDLC_RECORD=1` / `AGENTIC_SDLC_SHADOW=1`
for one session). The record is `<git common dir>/agentic-sdlc/decisions.jsonl`, one JSON line
per decision: time, event, tool, permission mode, decision, rule ids, the reason lines, the
command kinds, milliseconds, the shadow flag and a truncated SHA-256 of the command. The command
text is never written; a reason line may name a branch, a file or the trailer a rule matched. A
write failure never fails the hook.

The native git hooks that `agentic-sdlc hooks install` writes call a copy of this package under
the repository's `.git/agentic-sdlc/` with the stock `python3`; they read the commit message
file, the index and the ref lines git passes to `pre-push`, run the same read-only git commands,
and write nothing else. `hooks uninstall` removes both the hooks and the copy.

The hook is a guard, not a sandbox. It sees tool calls only, it can be disabled by a user
setting, and a command the user types with the `!` prefix runs outside it. `--no-verify`, a
`-c core.hooksPath=` override and an edit to the guard's own configuration are refused or
put to the user (GUARD-1, GUARD-2), but a person who wants past the guard can edit the settings by
hand. The CI check and the ruleset are the backstops for what reaches the forge.

## Supply chain

The runtime path is the Python standard library. Development dependencies are pinned in
`uv.lock`. Workflow actions are pinned by commit sha.
