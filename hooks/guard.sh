#!/bin/sh
# The shell-command guard. The hook exits 0 or 2. Any other exit means it did not run: no
# python3, a Python too old to load it, or a crash before its own handler. Then the command is
# refused with exit 2, which Claude Code and Codex both treat as a block.
python3 "${0%/*}/../src/agentic_sdlc/hook.py" "$@"
status=$?
case "$status" in
0 | 2) exit "$status" ;;
esac
echo "agentic-sdlc: the guard did not run (exit $status; python3 3.9 or newer must be on PATH), so the command is refused. Do not retry: a person fixes python3 or disables the plugin" >&2
exit 2
