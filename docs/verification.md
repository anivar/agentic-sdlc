# Verifying the hook inside Claude Code

The unit tests prove the decisions. This procedure proves the wiring: the plugin loads, the hook
fires on the Bash tool, `${CLAUDE_PLUGIN_ROOT}` resolves, and a decision reaches the permission
system in each mode. Record the observed behaviour per mode in `CHANGELOG.md`.

## Setup

```bash
tmp="$(mktemp -d)" && cd "$tmp" && git init -q -b main && git commit -q --allow-empty -m init
claude --plugin-dir ~/code/personal/agentic-sdlc
```

In the session, `/hooks` lists the PreToolUse hook under the plugin, and `/plugin` shows no
error in its Errors tab.

## Cases

Ask the agent to run each command. The expected result is the hook's decision; the words the
agent uses do not matter.

| Ask the agent to run | Expected |
|---|---|
| `git status` | runs with no prompt from the hook |
| `git add -A` | refused, reason names STAGE-1 |
| `printf 'x\n' > a.txt && git add a.txt && git commit -m "Add a"` | a prompt naming ASK-1; the commit runs only after yes |
| `git commit --allow-empty -m "Note" -m "Co-Authored-By: Claude <noreply@anthropic.com>"` | refused, reason names ATTR-1 |
| `printf 'token = "ghp_%s"\n' "$(head -c 40 /dev/zero | tr '\0' a)" > s.py && git add s.py && git commit -m "Add s"` | refused, reason names SECRET-1, no value shown |
| `git push --force origin main` | refused, reason names PUSH-1 |
| `git push origin main` | a prompt naming ASK-2 (the push itself fails: no remote) |
| `gh issue comment 1 --body hi` | a prompt naming ASK-3 (the command itself fails: no repo) |

Run the table once in each permission mode: default, `acceptEdits` (`/permissions` or
`--permission-mode acceptEdits`), auto, and `bypassPermissions`. The documentation states that
a hook's `ask` forces a prompt in auto mode; the other two are the open assumptions.

## Recording

One line per mode in `CHANGELOG.md` under the release, in the form: mode, date, Claude Code
version, which cases prompted, which were refused, anything unexpected. A case that did not
behave as the table says is a defect in this repository; file it with the command, the mode and
the hook's stderr (`claude --debug-file hook.log` captures it).
