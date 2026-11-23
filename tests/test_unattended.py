"""RUN-1: a run the launcher marks unattended gets no ask from the guard, because an ask there
stops the run at a prompt nobody answers. Checkpoint commits pass on a working branch; every
other call that would ask is refused with a reason the agent can act on."""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

from agentic_sdlc import config as config_mod
from agentic_sdlc import guard, hook, registry
from tests.conftest import git
from tests.test_fuzz import SAMPLES, _command

HOOK = Path(__file__).resolve().parent.parent / "src" / "agentic_sdlc" / "hook.py"
CFG = config_mod.from_dict(
    {"secrets": {"scanner": "none"}, "unattended": {"push_branches": ["agent/*"]}}
)


@pytest.fixture
def unattended(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_SDLC_UNATTENDED", "1")


@pytest.fixture
def work(repo: Path) -> Path:
    git(repo, "checkout", "-q", "-b", "agent/work")
    return repo


def run_hook(command: str, cwd: Path, mode: str, env_on: bool) -> tuple[int, str, str]:
    env = dict(os.environ)
    env.pop("AGENTIC_SDLC_UNATTENDED", None)
    if env_on:
        env["AGENTIC_SDLC_UNATTENDED"] = "1"
    event = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": str(cwd),
        "permission_mode": mode,
    }
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


def test_checkpoint_commit_passes_on_a_working_branch(work: Path, unattended: None):
    decision = guard.decide('git commit -m "Add the parser"', work, CFG)
    assert decision.permission == "allow", decision.reason


@pytest.mark.parametrize("branch", ["main", "master"])
def test_commit_on_a_protected_branch_is_refused(repo: Path, unattended: None, branch: str):
    if branch != "main":
        git(repo, "checkout", "-q", "-b", branch)
    decision = guard.decide('git commit -m "Add the parser"', repo, CFG)
    assert decision.permission == "deny" and "RUN-1" in decision.rules
    assert f"would land on {branch}" in decision.reason


def test_commit_on_a_detached_head_is_refused(repo: Path, unattended: None):
    git(repo, "checkout", "-q", "--detach")
    decision = guard.decide('git commit -m "x"', repo, CFG)
    assert decision.permission == "deny" and "a detached HEAD" in decision.reason


def test_a_refusal_tells_the_agent_to_carry_on(work: Path, unattended: None):
    decision = guard.decide("git push origin main", work, CFG)
    assert decision.permission == "deny"
    assert decision.rules[-1] == "RUN-1"
    assert "do not retry" in decision.reason and "carry on with the next step" in decision.reason
    assert "held calls in the run report" in decision.reason


def test_a_listed_pattern_never_opens_a_protected_branch(work: Path, unattended: None):
    cfg = config_mod.from_dict(
        {"secrets": {"scanner": "none"}, "unattended": {"push_branches": ["*"]}}
    )
    assert guard.decide("git push origin main", work, cfg).permission == "deny"
    assert guard.decide("git push origin agent/work", work, cfg).permission == "allow"


def test_no_push_passes_without_a_listed_pattern(work: Path, unattended: None):
    cfg = config_mod.from_dict({"secrets": {"scanner": "none"}})
    assert guard.decide("git push origin agent/work", work, cfg).permission == "deny"


def test_deny_rules_still_refuse(work: Path, unattended: None):
    """RUN-1 removes asks; it never loosens a deny."""
    for command, rule in (
        ("git add -A", "STAGE-1"),
        ('git commit --no-verify -m "x"', "GUARD-1"),
        ("git push --force origin main", "PUSH-1"),
    ):
        decision = guard.decide(command, work, CFG)
        assert decision.permission == "deny" and rule in decision.rules, command


def test_file_tools_never_ask(work: Path, unattended: None):
    for tool, path in (("Read", ".env"), ("Edit", ".agentic-sdlc.json")):
        decision = guard.decide_file(tool, path, work, CFG)
        assert decision.permission == "deny" and "RUN-1" in decision.rules, (tool, path)


def test_no_example_and_no_fuzz_command_asks(work: Path, unattended: None):
    """The invariant: with the signal on, no decision is an ask. Every registry example in both
    sets and the fuzz corpus go through the guard, and so does each untraced ask the config can
    turn on."""
    commands = []
    for rule in registry.rules():
        for key in ("examples", "examples_unattended", "examples_agent"):
            for listed in (rule.get(key) or {}).values():
                commands.extend(listed)
    rng = random.Random(42)
    commands.extend(_command(rng) for _ in range(SAMPLES))
    trace_ask = config_mod.from_dict(
        {"secrets": {"scanner": "none"}, "trace": {"untracked": "ask"}}
    )
    for cfg in (CFG, trace_ask):
        for command in commands:
            decision = guard.decide(command, work, cfg)
            assert decision.permission != "ask", (command, decision.reason)


def test_attended_runs_are_unchanged(work: Path):
    decision = guard.decide('git commit -m "x"', work, CFG)
    assert decision.permission == "ask" and "RUN-1" not in decision.rules


def test_committed_config_cannot_switch_it_on(work: Path):
    cfg = config_mod.from_dict({"unattended": {"enabled": True}})
    assert not cfg.unattended
    assert "unknown key unattended.enabled" in cfg.problems


def test_push_branches_must_be_a_list_of_strings():
    cfg = config_mod.from_dict({"unattended": {"push_branches": "agent/*"}})
    assert cfg.unattended_push == []
    assert "unattended.push_branches must be an array of strings" in cfg.problems


def test_hook_lets_a_checkpoint_through_in_a_mode_that_cannot_prompt(work: Path):
    (work / ".agentic-sdlc.json").write_text(
        json.dumps({"secrets": {"scanner": "none"}}), encoding="utf-8"
    )
    for mode in ("bypassPermissions", "dontAsk", "auto", "default"):
        code, out, err = run_hook('git commit -m "x"', work, mode, env_on=True)
        assert (code, out) == (0, ""), (mode, err)


def test_hook_refuses_a_held_call_without_a_prompt(work: Path):
    (work / ".agentic-sdlc.json").write_text(
        json.dumps({"secrets": {"scanner": "none"}}), encoding="utf-8"
    )
    code, out, _ = run_hook("git push origin main", work, "auto", env_on=True)
    decision = json.loads(out)["hookSpecificOutput"]
    assert code == 0 and decision["permissionDecision"] == "deny"
    assert "RUN-1" in decision["permissionDecisionReason"]
    code, out, err = run_hook("git push origin main", work, "bypassPermissions", env_on=True)
    assert code == 2 and out == "" and "RUN-1" in err


def test_no_prompt_refusal_is_written_for_the_agent(work: Path):
    (work / ".agentic-sdlc.json").write_text(
        json.dumps({"secrets": {"scanner": "none"}}), encoding="utf-8"
    )
    code, _, err = run_hook('git commit -m "x"', work, "dontAsk", env_on=False)
    assert code == 2 and "Do not retry it" in err and "do it yourself" not in err


def test_analysis_failure_is_refused_not_asked(
    work: Path, unattended: None, monkeypatch: pytest.MonkeyPatch, capsys
):
    def broken(*_args, **_kwargs):
        raise RuntimeError("parser fell over")

    monkeypatch.setattr(guard, "decide", broken)
    call = hook.Call({"tool_name": "Bash", "tool_input": {"command": "git push"}, "cwd": str(work)})
    assert hook.before_bash(call) == 0
    decision = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert (
        decision["permissionDecision"] == "deny" and "RUN-1" in decision["permissionDecisionReason"]
    )
    monkeypatch.delenv("AGENTIC_SDLC_UNATTENDED")
    hook.before_bash(call)
    assert json.loads(capsys.readouterr().out)["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_registry_refuses_an_ask_among_unattended_examples():
    """An unattended run never asks, so its example set has no ask list."""
    data = registry.load()
    rule = next(r for r in data["rules"] if r["id"] == "RUN-1")
    rule["examples_unattended"] = {"ask": ["git push origin main"]}
    assert any(
        "examples_unattended keys must be allow or deny" in p for p in registry.validate(data)
    )


def test_unattended_run_can_record_a_held_call_and_search_for_one(repo: Path, monkeypatch):
    """RUN-3 asks for held calls in a file; writing one down must not itself be refused."""
    monkeypatch.setenv("AGENTIC_SDLC_UNATTENDED", "1")
    for raw in (
        "printf '| git push origin main | RUN-1 | protected |\\n' >> .agent/progress.md",
        'rg -n "gh pr create" .agent',
    ):
        assert (
            guard.decide(
                raw, repo, config_mod.from_dict({"secrets": {"scanner": "none"}})
            ).permission
            == "allow"
        ), raw
    hidden = guard.decide(
        'cat "$(git push origin main)"',
        repo,
        config_mod.from_dict({"secrets": {"scanner": "none"}}),
    )
    assert hidden.permission == "deny" and "RUN-1" in hidden.rules


# RUN-4: starting an unattended run is the agent's own decision. The guard records it and
# neither asks nor refuses; the run it starts follows RUN-1.
SETS_THE_SIGNAL = [
    'AGENTIC_SDLC_UNATTENDED=1 claude -p "commit and push the fix"',
    "env AGENTIC_SDLC_UNATTENDED=1 claude -p x",
    "env -u HOME AGENTIC_SDLC_UNATTENDED=1 claude -p x",
    "export AGENTIC_SDLC_UNATTENDED=1",
    "export PATH AGENTIC_SDLC_UNATTENDED",
    "declare -x AGENTIC_SDLC_UNATTENDED=yes",
    "cd sub && AGENTIC_SDLC_UNATTENDED=1 ./run.sh",
    "nohup env AGENTIC_SDLC_UNATTENDED=1 claude -p x &",
]
NAMES_THE_SIGNAL = [
    "printf 'AGENTIC_SDLC_UNATTENDED=1\\n'",
    "rg -n AGENTIC_SDLC_UNATTENDED src",
    "unset AGENTIC_SDLC_UNATTENDED",
    "echo $AGENTIC_SDLC_UNATTENDED",
    "env -u AGENTIC_SDLC_UNATTENDED claude -p x",
    "OTHER=1 claude -p x",
]


@pytest.mark.parametrize("command", SETS_THE_SIGNAL)
def test_starting_an_unattended_run_is_recorded_and_not_asked(repo: Path, command: str):
    decision = guard.decide(command, repo, CFG)
    assert decision.permission == "allow" and "RUN-4" in decision.rules, decision.reason


@pytest.mark.parametrize("command", NAMES_THE_SIGNAL)
def test_a_command_that_only_names_the_signal_is_not_recorded(repo: Path, command: str):
    decision = guard.decide(command, repo, CFG)
    assert decision.permission == "allow" and "RUN-4" not in decision.rules, decision.reason


def test_an_unattended_run_may_start_another_and_the_start_is_recorded(
    work: Path, unattended: None
):
    decision = guard.decide("AGENTIC_SDLC_UNATTENDED=1 claude -p x", work, CFG)
    assert decision.permission == "allow" and "RUN-4" in decision.rules, decision.reason
    assert "RUN-1" not in decision.rules
