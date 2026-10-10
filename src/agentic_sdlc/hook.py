"""Claude Code PreToolUse hook: stdin JSON in, a permission decision out.

Runs as ``python3 hook.py`` with no package installed, so the package directory is put on
``sys.path`` first. Exit 0 with no output means "no decision", which hands the call to the
normal permission flow. A decision is one JSON object on stdout.

If the analysis itself fails, a command that looks like a commit, push or post gets an
``ask`` with the error in the reason, and any other command gets no decision: a broken
hook must neither let gated work through silently nor block unrelated commands.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))

from agentic_sdlc import config as config_mod  # noqa: E402
from agentic_sdlc import guard  # noqa: E402


def output(permission: str, reason: str) -> None:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": permission,
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(payload))
    sys.stdout.flush()


def main() -> int:
    raw = sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else {}
    except ValueError:
        return 0
    if not isinstance(event, dict) or event.get("tool_name") != "Bash":
        return 0
    tool_input = event.get("tool_input") or {}
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command.strip():
        return 0
    cwd_value = event.get("cwd")
    cwd = Path(cwd_value) if isinstance(cwd_value, str) and cwd_value else Path.cwd()
    try:
        cfg = config_mod.load(cwd)
        decision = guard.decide(command, cwd, cfg)
    except Exception as exc:  # noqa: BLE001 - the hook must never crash the session
        sys.stderr.write(f"agentic-sdlc hook error: {exc!r}\n")
        if guard.looks_gated(command):
            output(
                "ask", f"agentic-sdlc could not analyse this command ({exc!r}); confirm it yourself"
            )
        return 0
    if decision.permission == "allow":
        return 0
    output(decision.permission, "agentic-sdlc " + decision.reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
