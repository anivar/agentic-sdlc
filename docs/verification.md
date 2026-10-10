# Verifying the hook inside Claude Code

The unit tests prove the decisions. This procedure proves the wiring: the plugin loads, the hook
fires on the Bash tool and on the file tools, `${CLAUDE_PLUGIN_ROOT}` resolves, and a decision
reaches the permission system in each mode. Record the observed behaviour per mode in
`CHANGELOG.md`.

## Setup

```bash
tmp="$(mktemp -d)" && cd "$tmp" && git init -q -b main && git commit -q --allow-empty -m init
printf 'EXAMPLE_TOKEN=placeholder\n' > .env
printf '{"record": {"decisions": true}}\n' > .agentic-sdlc.json
claude --plugin-dir <path to this repository>
```

In the session, `/hooks` lists the PreToolUse hooks (Bash, and the file tools) and the
PostToolUse hook under the plugin, and `/plugin` shows no error in its Errors tab. With
`record.decisions` on, `agentic-sdlc log` lists every decision afterwards, with the mode.

## Cases

Ask the agent to run each command. The expected result is the hook's decision; the words the
agent uses do not matter.

| Ask the agent to | Expected |
|---|---|
| run `git status` | runs with no prompt from the hook |
| run `git add -A` | refused, reason names STAGE-1 and the fix |
| run `printf 'x\n' > a.txt && git add a.txt && git commit -m "Add a"` | a prompt naming ASK-1; the commit runs only after yes |
| run `git commit --allow-empty -m "Note" -m "Co-Authored-By: Claude <noreply@anthropic.com>"` | refused, reason names ATTR-1 |
| run `git commit --allow-empty -m "Note" -m "$(printf 'Co-Authored-By: Claude <noreply@anthropic.com>')"` | a prompt naming ASK-1 and the substitution; after yes, the hook reports ATTR-1 on the commit that landed and tells the agent to amend |
| run `printf 'token = "ghp_%s"\n' "$(head -c 40 /dev/zero \| tr '\0' a)" > s.py && git add s.py && git commit -m "Add s"` | refused, reason names SECRET-1, no value shown |
| run `git commit --no-verify --allow-empty -m "Note"` | refused, reason names GUARD-1 |
| run `git push --force origin main` | refused, reason names PUSH-1 |
| run `git push origin main` | a prompt naming ASK-2 (the push itself fails: no remote) |
| run `gh issue comment 1 --body hi` | a prompt naming ASK-3 (the command itself fails: no repo) |
| run `cat .env` | a prompt naming SECRET-3 |
| read `.env` with the Read tool | a prompt naming SECRET-3 |
| edit `.agentic-sdlc.json` to set `confirm.commit` to false | a prompt naming GUARD-2 |

Run the table once in each permission mode: default, `acceptEdits` (`/permissions` or
`--permission-mode acceptEdits`), auto, `bypassPermissions` and `dontAsk`. The documentation
states that a hook's `ask` forces a prompt in auto mode. In `bypassPermissions` and `dontAsk`
the hook returns a blocking error instead of an ask, and the expected result for every "prompt"
row is: the command does not run and the reason appears in the transcript. Whether
`bypassPermissions` lets that block stand is the open assumption.

## Observed so far

Print mode (`claude -p`), Claude Code 2.1.296, 2026-10-10, all five modes: see the changelog's
"Verified before release" section. The blocking error held in `bypassPermissions` and `dontAsk`
for the commit, the secret file, the `--no-verify` commit and the Read tool; the check after the
commit reported a trailer that landed in auto and `bypassPermissions`. What this procedure still
adds is the interactive prompt in default, `acceptEdits` and auto, which print mode cannot show.

## Recording

One line per mode in `CHANGELOG.md` under the release, in the form: mode, date, Claude Code
version, which cases prompted, which were refused, anything unexpected; `agentic-sdlc log` in
the temporary repository is the source. A case that did not behave as the table says is a
defect in this repository; file it with the command, the mode and the hook's stderr
(`claude --debug-file hook.log` captures it).
