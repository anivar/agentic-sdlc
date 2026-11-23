"""AGENT-1: the agent decides by default. A call a rule would ask about runs, and the decision
record keeps the rule that would have asked; a rule that refuses still refuses. Confirm mode,
from the file or the environment, puts a person in front of every ask."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from agentic_sdlc import config as config_mod
from agentic_sdlc import guard
from tests.conftest import git

SRC = Path(__file__).resolve().parent.parent / "src"
HOOK = SRC / "agentic_sdlc" / "hook.py"
NO_SCANNER = {"secrets": {"scanner": "none"}}


@pytest.fixture
def agent_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENTIC_SDLC_MODE", raising=False)


def cfg(**extra: object) -> config_mod.Config:
    return config_mod.from_dict({**NO_SCANNER, **extra})


@pytest.mark.parametrize(
    "command,rule",
    [
        ('git commit -m "Add the parser"', "ASK-1"),
        ("git push origin main", "ASK-2"),
        ('gh pr create --title "Add it" --body "Adds it."', "ASK-3"),
        ("cat .env", "SECRET-3"),
    ],
)
def test_an_ask_runs_and_records_the_rule_that_would_have_asked(
    repo: Path, agent_mode: None, command: str, rule: str
):
    decision = guard.decide(command, repo, cfg())
    assert decision.permission == "allow", decision.reason
    assert {rule, "AGENT-1"} <= set(decision.rules)


@pytest.mark.parametrize(
    "command,rule",
    [
        ("git add -A", "STAGE-1"),
        ('git commit --no-verify -m "x"', "GUARD-1"),
        ("git push --force origin main", "PUSH-1"),
    ],
)
def test_a_refusal_still_refuses(repo: Path, agent_mode: None, command: str, rule: str):
    decision = guard.decide(command, repo, cfg())
    assert decision.permission == "deny" and rule in decision.rules, decision.reason
    assert "AGENT-1" not in decision.rules


def test_an_edit_to_the_guard_config_runs_and_is_recorded(repo: Path, agent_mode: None):
    decision = guard.decide_file("Edit", str(repo / ".agentic-sdlc.json"), repo, cfg())
    assert decision.permission == "allow" and {"GUARD-2", "AGENT-1"} <= set(decision.rules)


def test_confirm_mode_from_the_file_asks(repo: Path, agent_mode: None):
    decision = guard.decide('git commit -m "x"', repo, cfg(mode="confirm"))
    assert decision.permission == "ask" and "AGENT-1" not in decision.rules


def test_confirm_mode_from_the_environment_overrides_the_file(
    repo: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("AGENTIC_SDLC_MODE", "confirm")
    decision = guard.decide('git commit -m "x"', repo, cfg(mode="agent"))
    assert decision.permission == "ask"


def test_agent_mode_from_the_environment_overrides_the_file(
    repo: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("AGENTIC_SDLC_MODE", "agent")
    decision = guard.decide('git commit -m "x"', repo, cfg(mode="confirm"))
    assert decision.permission == "allow"


def test_an_unknown_mode_in_the_environment_means_confirm(
    repo: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("AGENTIC_SDLC_MODE", "yolo")
    decision = guard.decide('git commit -m "x"', repo, cfg())
    assert decision.permission == "ask"


def test_an_unknown_mode_in_the_file_is_a_problem():
    assert "mode must be agent or confirm" in cfg(mode="yolo").problems


@pytest.mark.parametrize("value", ["yolo", "Agent", "", 1, None])
def test_an_unknown_mode_in_the_file_means_confirm(repo: Path, agent_mode: None, value: object):
    decision = guard.decide('git commit -m "x"', repo, cfg(mode=value))
    assert decision.permission == "ask" and "AGENT-1" not in decision.rules, decision.reason


@pytest.mark.parametrize("body", ['{"mode": "confirm",', "[]"])
def test_a_config_file_the_guard_cannot_read_means_confirm(repo: Path, agent_mode: None, body: str):
    (repo / ".agentic-sdlc.json").write_text(body, encoding="utf-8")
    loaded = config_mod.load(repo)
    assert loaded.problems and loaded.effective_mode == "confirm"
    assert guard.decide('git commit -m "x"', repo, loaded).permission == "ask"


def test_the_unattended_signal_changes_nothing_in_agent_mode(
    repo: Path, agent_mode: None, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("AGENTIC_SDLC_UNATTENDED", "1")
    decision = guard.decide('git commit -m "x"', repo, cfg())
    assert decision.permission == "allow" and "RUN-1" not in decision.rules, decision.reason


def hook_env() -> dict[str, str]:
    drop = (
        "AGENTIC_SDLC_MODE",
        "AGENTIC_SDLC_UNATTENDED",
        "AGENTIC_SDLC_RECORD",
        "AGENTIC_SDLC_SHADOW",
    )
    return {k: v for k, v in os.environ.items() if k not in drop}


def run_hook(repo: Path, tool: str, tool_input: dict[str, str]) -> subprocess.CompletedProcess:
    event = {
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "cwd": str(repo),
        "permission_mode": "default",
        "tool_input": tool_input,
    }
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=hook_env(),
    )


def decision_log(repo: Path) -> str:
    # The stock-interpreter lane runs without the project installed, so the CLI subprocess
    # imports the package from the source tree.
    env = hook_env()
    env["PYTHONPATH"] = str(SRC)
    result = subprocess.run(
        [sys.executable, "-m", "agentic_sdlc", "log"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )
    return result.stdout + result.stderr


@pytest.mark.parametrize(
    "command,rules",
    [
        ('git commit --allow-empty -m "x"', "ASK-1, AGENT-1"),
        ("AGENTIC_SDLC_UNATTENDED=1 claude -p x", "RUN-4"),
    ],
)
def test_an_agent_decision_is_recorded_with_no_record_setting(repo: Path, command: str, rules: str):
    """The record is off by default, and a decision the agent makes in place of a person is
    kept anyway: an agent decision nobody can see afterwards is the failure ADR 0008 names."""
    (repo / ".agentic-sdlc.json").write_text(json.dumps(NO_SCANNER))
    result = run_hook(repo, "Bash", {"command": command})
    assert result.returncode == 0 and result.stdout.strip() == "", result.stdout + result.stderr
    assert rules in decision_log(repo)
    git(repo, "status")


def test_a_file_edit_the_agent_decides_is_recorded(repo: Path):
    (repo / ".agentic-sdlc.json").write_text(json.dumps(NO_SCANNER))
    result = run_hook(repo, "Edit", {"file_path": str(repo / ".agentic-sdlc.json")})
    assert result.returncode == 0 and result.stdout.strip() == "", result.stdout + result.stderr
    assert "GUARD-2, AGENT-1" in decision_log(repo)


def test_a_plain_allow_is_not_recorded_by_default(repo: Path):
    (repo / ".agentic-sdlc.json").write_text(json.dumps(NO_SCANNER))
    assert run_hook(repo, "Bash", {"command": "git status"}).returncode == 0
    assert "no decisions recorded here" in decision_log(repo)
