# Security

## Reporting

Report a vulnerability through GitHub's private vulnerability reporting on this repository
(Security tab, "Report a vulnerability"). Do not open a public issue for it. Expect an
acknowledgement within seven days.

## What the hook does and does not do

The hook reads the JSON event Claude Code or Codex sends for a shell tool call, parses the
command string, and may run read-only git commands in the working directory (`rev-parse`,
`symbolic-ref`, `show-ref`, `remote`, `rev-list`, `status --porcelain` on one file,
`diff --cached`, and `log -1` after a commit ran), and pipes the
lines the staged change adds to `trufflehog stdin --no-verification --no-update` when TruffleHog
is installed, so the scanner makes no network call. It reads message files the command names
when they exist, and a script an interpreter is about to run when that script has uncommitted
changes and is under 256 KB; a committed script and a secret file are never opened. It reads the
value of an environment variable the command uses, from its own environment, to match it against
the production markers and the key shapes; the value never enters a reason. For the file tools
(Read, Grep, Edit, Write, MultiEdit, NotebookEdit) it reads the path in the event and nothing
else, and for a Codex patch (`apply_patch`) the file names in the patch. It sends nothing over
the network and prints no secret:
a staged secret is reported by pattern name and line number only, and a credential file is
named, never read.

Before a commit command runs, the hook records the sha at HEAD in
`<git common dir>/agentic-sdlc/pre-head.json` (a null for an unborn HEAD) and deletes the
file after the command, so the check after a commit can tell whether HEAD moved. That is the
only write apart from the decision record.

It always records a decision the agent makes in place of a person (AGENT-1) and the start of an
unattended run (RUN-4). It records every other decision only when the repository turns the
decision record on (`record.decisions` or `record.shadow` in `.agentic-sdlc.json`, or
`AGENTIC_SDLC_RECORD=1` / `AGENTIC_SDLC_SHADOW=1` for one session). The record is `<git common dir>/agentic-sdlc/decisions.jsonl`, one JSON line
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

## The run launcher

`agentic-sdlc run` is a command a person or an agent starts; it runs apart from the hook. It
creates a git worktree beside the checkout on a new branch `agent/<name>`, and starts Claude Code
there in print mode (`--permission-mode auto --permission-prompts none --max-budget-usd <cap>`)
or `codex exec --sandbox workspace-write --approve-for-me`, detached from the terminal. The agent
inherits the environment of the shell that launched the run, credentials included, with
`AGENTIC_SDLC_UNATTENDED=1` added. The record and the log of a run are files under
`<git common dir>/agentic-sdlc/runs/`: the record holds the task text and the agent's command
line in plain text, and the log holds whatever the agent printed. Keep secrets out of the task.
Stopping a run signals only the supervisor that holds the run's lock and the process group the
agent leads. The launcher needs macOS or Linux.

## Supply chain

The runtime path is the Python standard library. Development dependencies are pinned in
`uv.lock`. Workflow actions are pinned by commit sha.
