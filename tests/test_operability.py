"""The registry's own examples, the hook-bypass and secret-file rules, the decision record,
shadow mode, the no-prompt modes and the check after a commit."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from agentic_sdlc import cli, guard, record, registry
from agentic_sdlc import config as config_mod
from tests.conftest import git

HOOK = Path(__file__).resolve().parent.parent / "src" / "agentic_sdlc" / "hook.py"
NO_GITLEAKS = config_mod.from_dict({"secrets": {"use_gitleaks": False}})


def example_cases():
    for rule in registry.rules():
        for expected, commands in (rule.get("examples") or {}).items():
            for command in commands:
                yield pytest.param(
                    rule["id"],
                    rule.get("decision"),
                    expected,
                    command,
                    id=f"{rule['id']}:{expected}:{command[:40]}",
                )


@pytest.mark.parametrize("rule_id,own,expected,command", list(example_cases()))
def test_registry_examples_decide_as_written(
    repo: Path, rule_id: str, own: str, expected: str, command: str
):
    """Every example in the registry decides as its key says; when the key is the rule's own
    decision, the rule itself is among the reasons."""
    decision = guard.decide(command, repo, NO_GITLEAKS)
    assert decision.permission == expected, (rule_id, command, decision.reason)
    if expected == own:
        assert rule_id in decision.rules, (rule_id, command, decision.rules)


def test_every_hook_rule_has_a_fix_line_and_examples():
    for rule in registry.rules():
        if "hook" in rule["mechanisms"]:
            assert rule.get("fix"), rule["id"]
            if rule["id"] not in ("ATTR-2", "SECRET-1", "GUARD-2"):
                assert rule.get("examples"), rule["id"]


def test_refusals_carry_the_fix_line(repo: Path):
    decision = guard.decide("git add -A", repo, NO_GITLEAKS)
    assert "Fix: Stage the files by name" in decision.reason


def test_hook_bypass_flags_are_refused(repo: Path):
    for raw in (
        'git commit --no-verify -m "x"',
        'git commit -n -m "x"',
        "git push --no-verify",
        'git -c core.hooksPath=/dev/null commit -m "x"',
        "git -c include.path=/tmp/x commit -m x",
    ):
        decision = guard.decide(raw, repo, NO_GITLEAKS)
        assert decision.permission == "deny" and "GUARD-1" in decision.rules, raw
    assert guard.decide('git commit --dry-run -m "x"', repo, NO_GITLEAKS).permission == "allow"
    for raw in (
        "git config core.hooksPath /tmp/x",
        "git config --global core.hookspath /tmp/x",
        "git config include.path ~/x",
    ):
        decision = guard.decide(raw, repo, NO_GITLEAKS)
        assert decision.permission == "deny" and decision.rules == ["GUARD-1"], raw
    for raw in (
        "git config --get core.hooksPath",
        "git config --unset core.hooksPath",
        "git config user.name Someone",
    ):
        assert guard.decide(raw, repo, NO_GITLEAKS).permission == "allow", raw


def test_secret_file_reads_ask_and_ordinary_reads_do_not(repo: Path):
    for raw in (
        "cat .env",
        "cat .env.production",
        "head -c 40 ~/.ssh/id_ed25519",
        "cp .env /tmp/x",
        "base64 certs/server.key",
    ):
        decision = guard.decide(raw, repo, NO_GITLEAKS)
        assert decision.permission == "ask" and "SECRET-3" in decision.rules, raw
    for raw in (
        "cat README.md",
        "head -n 5 src/main.py",
        "cat .envrc.example.md",
        "cp .env.example .env",
    ):
        assert guard.decide(raw, repo, NO_GITLEAKS).permission == "allow", raw


def test_message_file_written_in_the_same_command_is_scanned_from_the_raw_text(repo: Path):
    raw = (
        "printf 'Note\\n\\nCo-Authored-By: Claude <noreply@anthropic.com>\\n' > msg.txt "
        "&& git commit --allow-empty -F msg.txt"
    )
    decision = guard.decide(raw, repo, NO_GITLEAKS)
    assert decision.permission == "deny" and "ATTR-1" in decision.rules, decision.reason
    missing = guard.decide("git commit -F missing.txt", repo, NO_GITLEAKS)
    assert missing.permission == "ask" and "does not exist yet" in missing.reason
    (repo / "m.txt").write_text("Plain message\n", encoding="utf-8")
    present = guard.decide("git commit -F m.txt", repo, NO_GITLEAKS)
    assert present.permission == "ask" and "does not exist" not in present.reason


def test_file_tool_decisions():
    assert guard.decide_file("Read", ".env").permission == "ask"
    assert guard.decide_file("Read", "/home/u/project/.env.local").rules == ["SECRET-3"]
    assert guard.decide_file("Grep", "secrets/id_rsa").permission == "ask"
    assert guard.decide_file("Read", "README.md").permission == "allow"
    assert guard.decide_file("Edit", "/repo/.agentic-sdlc.json").rules == ["GUARD-2"]
    assert guard.decide_file("Write", "/repo/.claude/settings.local.json").permission == "ask"
    assert guard.decide_file("Write", "/repo/.git/hooks/pre-commit").permission == "ask"
    assert guard.decide_file("Edit", "/repo/src/main.py").permission == "allow"
    assert guard.decide_file("Read", "/repo/.agentic-sdlc.json").permission == "allow"


def run_hook(event: dict, post: bool = False) -> tuple[int, str, str]:
    argv = [sys.executable, str(HOOK)] + (["--post"] if post else [])
    result = subprocess.run(
        argv, input=json.dumps(event), capture_output=True, text=True, check=False
    )
    return result.returncode, result.stdout, result.stderr


def bash_event(command: str, cwd: Path, mode: str = "default") -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": str(cwd),
        "permission_mode": mode,
    }


def write_config(repo: Path, extra: dict) -> None:
    data = {"secrets": {"use_gitleaks": False}}
    data.update(extra)
    (repo / ".agentic-sdlc.json").write_text(json.dumps(data), encoding="utf-8")


def test_no_prompt_modes_turn_an_ask_into_a_block(repo: Path):
    write_config(repo, {})
    for mode in ("bypassPermissions", "dontAsk"):
        code, out, err = run_hook(bash_event('git commit -m "x"', repo, mode))
        assert code == 2 and out == "" and "ASK-1" in err and "cannot prompt" in err, mode
    code, out, _ = run_hook(bash_event('git commit -m "x"', repo, "auto"))
    assert code == 0 and json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_shadow_mode_records_and_lets_through(repo: Path):
    write_config(repo, {"record": {"shadow": True}})
    code, out, _ = run_hook(bash_event("git add -A", repo))
    assert code == 0 and out == ""
    path = repo / ".git" / "agentic-sdlc" / "decisions.jsonl"
    entries = record.read(path)
    assert entries and entries[-1]["decision"] == "deny" and entries[-1]["shadow"] is True
    assert "STAGE-1" in entries[-1]["rules"]
    assert "command" not in entries[-1]
    assert entries[-1]["command_sha256"] == record.command_digest("git add -A")


def test_record_holds_a_hash_not_the_command(repo: Path):
    write_config(repo, {"record": {"decisions": True}})
    secretish = 'git commit -m "token hunter2hunter2hunter2hunter2"'
    code, out, _ = run_hook(bash_event(secretish, repo))
    assert code == 0 and json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "ask"
    body = (repo / ".git" / "agentic-sdlc" / "decisions.jsonl").read_text(encoding="utf-8")
    assert "hunter2" not in body and record.command_digest(secretish) in body
    assert cli.main(["log", "--dir", str(repo), "--last", "5"]) == 0


def test_file_tools_through_the_hook(repo: Path):
    write_config(repo, {})
    event = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Read",
        "tool_input": {"file_path": str(repo / ".env")},
        "cwd": str(repo),
        "permission_mode": "default",
    }
    code, out, _ = run_hook(event)
    assert code == 0 and json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "ask"
    event["tool_name"] = "Edit"
    event["tool_input"] = {"file_path": str(repo / ".agentic-sdlc.json")}
    code, out, _ = run_hook(event)
    assert json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"].startswith(
        "agentic-sdlc GUARD-2"
    )
    event["tool_input"] = {"file_path": str(repo / "README.md")}
    code, out, _ = run_hook(event)
    assert code == 0 and out == ""


def test_post_commit_check_catches_what_landed(repo: Path):
    write_config(repo, {})
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-q", "-m", "Add a", "-m", "Co-Authored-By: Claude <noreply@anthropic.com>")
    code, out, err = run_hook(
        bash_event('git commit -m "Add a" -m "$(cat trailer.txt)"', repo), post=True
    )
    assert code == 2 and "ATTR-1" in err and "amend" in err
    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    git(repo, "add", "b.txt")
    git(repo, "commit", "-q", "-m", "Add b")
    code, out, err = run_hook(bash_event('git commit -m "Add b"', repo), post=True)
    assert code == 0 and err == ""
    code, out, err = run_hook(bash_event("git status", repo), post=True)
    assert code == 0


def test_post_commit_check_ignores_an_old_head(repo: Path):
    """A failed commit leaves HEAD where it was; an old HEAD with attribution is not reported."""
    write_config(repo, {})
    (repo / "old.txt").write_text("old\n", encoding="utf-8")
    git(repo, "add", "old.txt")
    env = dict(
        os.environ,
        GIT_COMMITTER_DATE="2020-01-01T00:00:00Z",
        GIT_AUTHOR_DATE="2020-01-01T00:00:00Z",
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "commit",
            "-q",
            "-m",
            "Old",
            "-m",
            "Co-Authored-By: Claude <noreply@anthropic.com>",
        ],
        check=True,
        env=env,
    )
    code, out, err = run_hook(bash_event('git commit -m "Nothing staged"', repo), post=True)
    assert code == 0 and err == ""


def test_check_mr_offline(repo: Path, monkeypatch, capsys):
    base = git(repo, "rev-parse", "HEAD")
    (repo / "c.txt").write_text("c\n", encoding="utf-8")
    git(repo, "add", "c.txt")
    git(repo, "commit", "-q", "-m", "Add c", "-m", "Generated with Claude Code")
    monkeypatch.setenv("CI_MERGE_REQUEST_TITLE", "Add c")
    monkeypatch.setenv("CI_MERGE_REQUEST_DESCRIPTION", "plain")
    monkeypatch.setenv("CI_MERGE_REQUEST_DIFF_BASE_SHA", base)
    assert cli.main(["check-mr", "--config-dir", str(repo)]) == 1
    out = capsys.readouterr().out
    assert "ATTR-1" in out and "1 commit(s), 1 problem(s)" in out


def test_bench_runs(repo: Path, capsys):
    assert cli.main(["bench", "--iterations", "3", "--cwd", str(repo)]) == 0
    assert "ms median" in capsys.readouterr().out


@pytest.mark.skipif(os.name == "nt", reason="posix paths")
def test_config_schema_documents_record():
    schema = json.loads(
        (Path(__file__).resolve().parent.parent / "schemas" / "config.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert set(schema["properties"]["record"]["properties"]) == {"decisions", "shadow", "path"}
