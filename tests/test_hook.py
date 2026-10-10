from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "src" / "agentic_sdlc" / "hook.py"


def run_hook(event: object, raw: str | None = None) -> tuple[int, str, str]:
    payload = raw if raw is not None else json.dumps(event)
    result = subprocess.run(
        [sys.executable, str(HOOK)], input=payload, capture_output=True, text=True, check=False
    )
    return result.returncode, result.stdout, result.stderr


def bash_event(command: str, cwd: Path) -> dict:
    return {
        "session_id": "s",
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": str(cwd),
        "permission_mode": "auto",
    }


def test_other_tools_get_no_decision(repo: Path):
    code, out, _ = run_hook(
        {"tool_name": "Edit", "tool_input": {"file_path": "x"}, "cwd": str(repo)}
    )
    assert code == 0 and out == ""


def test_malformed_input_gets_no_decision():
    code, out, _ = run_hook(None, raw="{not json")
    assert code == 0 and out == ""


def test_plain_command_gets_no_decision(repo: Path):
    code, out, _ = run_hook(bash_event("git status", repo))
    assert code == 0 and out == ""


def test_commit_returns_ask(repo: Path):
    (repo / ".agentic-sdlc.json").write_text(
        json.dumps({"secrets": {"use_gitleaks": False}}), encoding="utf-8"
    )
    code, out, _ = run_hook(bash_event('git commit -m "Fix"', repo))
    assert code == 0
    decision = json.loads(out)["hookSpecificOutput"]
    assert decision["hookEventName"] == "PreToolUse"
    assert decision["permissionDecision"] == "ask"
    assert "ASK-1" in decision["permissionDecisionReason"]


def test_add_all_returns_deny(repo: Path):
    code, out, _ = run_hook(bash_event("git add -A", repo))
    assert code == 0
    decision = json.loads(out)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "STAGE-1" in decision["permissionDecisionReason"]


def test_repo_config_is_honoured(repo: Path):
    (repo / ".agentic-sdlc.json").write_text(
        json.dumps({"attribution": {"mode": "strict"}, "secrets": {"use_gitleaks": False}}),
        encoding="utf-8",
    )
    code, out, _ = run_hook(bash_event('git commit -m "Mention Claude in the subject"', repo))
    assert code == 0
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_missing_cwd_does_not_crash():
    code, out, _ = run_hook(bash_event("git add -A", Path("/nonexistent/path")))
    assert code == 0
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"
