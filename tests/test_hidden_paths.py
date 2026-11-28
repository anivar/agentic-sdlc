"""Calls that reach the guard's own configuration, a secret or production by a path the parser
once did not follow: a shell write, inline interpreter code, an input redirection, a command
substitution, the environment, a database client, a Codex patch, and a hook that fails. Each
shape ran unchecked on 2026-11-25 before the fix."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from agentic_sdlc import command as command_mod
from agentic_sdlc import config as config_mod
from agentic_sdlc import guard, hook

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "src" / "agentic_sdlc" / "hook.py"
NO_SCANNER = config_mod.from_dict({"secrets": {"scanner": "none"}})


def run(hook_path: Path, event: dict, env: dict | None = None) -> tuple[int, str, str]:
    result = subprocess.run(
        [sys.executable, str(hook_path)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


def event(tool: str, tool_input: dict, cwd: Path, **extra: str) -> dict:
    return {
        "session_id": "s",
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": tool_input,
        "cwd": str(cwd),
        "permission_mode": "default",
        **extra,
    }


def patch(*lines: str) -> str:
    return "\n".join(["*** Begin Patch", *lines, "*** End Patch"])


@pytest.mark.parametrize(
    "raw",
    [
        "tee .agentic-sdlc.json < /dev/null",
        "cat new.json > ./.agentic-sdlc.json",
        "jq '.mode=\"agent\"' x.json >| .agentic-sdlc.json",
        "perl -pi -e 's/confirm/agent/' .agentic-sdlc.json",
        "dd if=/dev/null of=.agentic-sdlc.json",
        "cp /tmp/x.json .claude/settings.local.json",
        "rm -rf .git/hooks",
        "git config --list > /dev/null; echo '[features]' >> ~/.codex/config.toml",
        "node -e \"require('fs').writeFileSync('.agentic-sdlc.json', '{}')\"",
        'bash -c "echo {} > .agentic-sdlc.json"',
    ],
)
def test_guard_2_refuses_a_shell_change_to_the_guard_config(repo: Path, raw: str):
    decision = guard.decide(raw, repo, NO_SCANNER)
    assert decision.permission == "ask" and "GUARD-2" in decision.rules, (raw, decision.reason)


@pytest.mark.parametrize(
    "raw",
    [
        "awk 1 .env",
        "sort .env.production",
        "diff .env .env.example",
        "tar czf out.tgz .env",
        "openssl rsa -in server.key -text",
        "ruby -e 'puts File.read(\".env\")'",
        'while read line; do echo "$line"; done < .env',
        "x=$(cat ~/.netrc) && echo ok",
    ],
)
def test_secret_3_follows_every_reader_of_a_secret_file(repo: Path, raw: str):
    decision = guard.decide(raw, repo, NO_SCANNER)
    assert decision.permission == "ask" and "SECRET-3" in decision.rules, (raw, decision.reason)


def test_trace_1_still_asks_when_a_file_read_comes_first(repo: Path):
    """A cat in front is not a traced git call, so the interpreter push is still untraced."""
    raw = "cat README.md; python3 -c \"import subprocess; subprocess.run(['git','push'])\""
    decision = guard.decide(raw, repo, NO_SCANNER)
    assert decision.permission == "ask" and "TRACE-1" in decision.rules, decision.reason


@pytest.mark.parametrize(
    "name,secret",
    [
        ("GITLAB_TOKEN", True),
        ("AWS_SECRET_ACCESS_KEY", True),
        ("DB_PASSWORD", True),
        ("GITHUBTOKEN", True),
        ("PATH", False),
        ("PWD", False),
        ("HOME", False),
        ("BYPASS_CACHE", False),
        ("KEYBOARD", False),
    ],
)
def test_secret_2_knows_a_credential_variable_by_its_name(name: str, secret: bool):
    assert command_mod.secret_variable(name) is secret


@pytest.mark.parametrize(
    "raw",
    [
        "redis-cli -h cache-prod",
        "PGHOST=db-prod psql -f migrate.sql",
        "mongosh \"$PROD_MONGO\" --eval 'db.orders.updateMany({}, {$set: {x: 1}})'",
        'pg_restore -d "$PROD_URL" dump.sql',
        "psql \"$PROD_URL\" -c '\\i fix.sql'",
        'sqlcmd -S orders-production -Q "EXEC dbo.Rebuild"',
    ],
)
def test_prod_1_refuses_a_write_or_unseen_input_to_production(repo: Path, raw: str):
    decision = guard.decide(raw, repo, NO_SCANNER)
    assert decision.permission == "ask" and "PROD-1" in decision.rules, (raw, decision.reason)


@pytest.mark.parametrize(
    "raw",
    [
        "psql \"$NONPROD_URL\" -c 'delete from t'",
        "psql \"$PREPROD_URL\" -c 'delete from t'",
        "psql products -c 'delete from t'",
        'psql "$PROD_URL" -c "select status from orders where note like \'%created%\'"',
        "mysql -h db-prod -e 'show processlist'",
    ],
)
def test_prod_1_lets_reads_and_non_production_targets_through(repo: Path, raw: str):
    decision = guard.decide(raw, repo, NO_SCANNER)
    assert "PROD-1" not in decision.rules, (raw, decision.reason)


def test_prod_1_markers_come_from_the_config(repo: Path):
    off = config_mod.from_dict({"secrets": {"scanner": "none"}, "production": {"markers": []}})
    assert "PROD-1" not in guard.decide("psql \"$PROD_URL\" -c 'drop table t'", repo, off).rules
    named = config_mod.from_dict(
        {"secrets": {"scanner": "none"}, "production": {"markers": [r"orders-db-[0-9]+"]}}
    )
    decision = guard.decide("psql -h orders-db-7 -c 'drop table t'", repo, named)
    assert "PROD-1" in decision.rules, decision.reason


def test_prod_1_config_problems_are_reported():
    cfg = config_mod.from_dict({"production": {"markers": ["("], "clients": "psql"}})
    assert any("production.markers" in p for p in cfg.problems)
    assert any("production.clients" in p for p in cfg.problems)


def test_guard_2_covers_the_codex_files_through_the_file_tools(repo: Path):
    decision = guard.decide_file("Edit", str(repo / ".codex" / "config.toml"), repo, NO_SCANNER)
    assert decision.permission == "ask" and "GUARD-2" in decision.rules


def test_guard_2_refuses_a_codex_patch_to_the_guard_config(repo: Path):
    text = patch("*** Update File: notes.md", "*** Move to: .agentic-sdlc.json", "+{}")
    code, out, _ = run(HOOK, event("apply_patch", {"command": text}, repo, turn_id="t1"))
    decision = json.loads(out)["hookSpecificOutput"]
    assert code == 0 and decision["permissionDecision"] == "deny"
    assert "GUARD-2" in decision["permissionDecisionReason"]


def test_a_codex_patch_to_an_ordinary_file_gets_no_decision(repo: Path):
    text = patch("*** Add File: notes.md", "+hello")
    code, out, _ = run(HOOK, event("apply_patch", {"command": text}, repo, turn_id="t1"))
    assert code == 0 and out == ""


def test_the_file_hook_matches_codex_patches():
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    matchers = [entry["matcher"] for entry in hooks["hooks"]["PreToolUse"]]
    assert any("apply_patch" in m.split("|") for m in matchers), matchers


def test_a_hook_that_cannot_load_refuses_shell_commands_and_passes_file_tools(
    repo: Path, tmp_path: Path
):
    """Exit 2 with a reason blocks in Claude Code and in Codex, so a broken install never lets
    a shell command through unchecked."""
    copy = tmp_path / "plugin"
    shutil.copytree(ROOT / "src", copy / "src")
    (copy / "src" / "agentic_sdlc" / "guard.py").write_text("raise RuntimeError('broken')\n")
    broken = copy / "src" / "agentic_sdlc" / "hook.py"
    code, out, err = run(broken, event("Bash", {"command": "ls"}, repo))
    assert code == 2 and out == "" and "could not load" in err
    code, out, _ = run(broken, event("Read", {"file_path": "README.md"}, repo))
    assert code == 0 and out == ""


def test_a_hook_crash_outside_the_analysis_refuses_the_shell_command(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    def broken(*_args, **_kwargs):
        raise RuntimeError("record fell over")

    monkeypatch.setattr(hook, "settle", broken)
    monkeypatch.setattr(sys, "stdin", _stdin(event("Bash", {"command": "git add -A"}, repo)))
    assert hook.main([]) == 2
    assert "refusal rules never ran" in capsys.readouterr().err


def test_a_failed_file_check_refuses_only_guarded_and_secret_paths(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    def broken(*_args, **_kwargs):
        raise RuntimeError("config fell over")

    monkeypatch.setattr(hook.config_mod, "load", broken)
    for path, expected in ((".agentic-sdlc.json", 2), (".env", 2), ("README.md", 0)):
        monkeypatch.setattr(sys, "stdin", _stdin(event("Write", {"file_path": path}, repo)))
        assert hook.main([]) == expected, path
    capsys.readouterr()


def _stdin(payload: dict):
    import io

    return io.StringIO(json.dumps(payload))


def git_commit(repo: Path, name: str) -> None:
    for args in (["add", "--", name], ["commit", "-q", "-m", f"Add {name}"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_secret_3_reads_a_script_with_uncommitted_changes(repo: Path):
    (repo / "read.py").write_text("print(open('.env').read())\n", encoding="utf-8")
    decision = guard.decide("python3 read.py", repo, NO_SCANNER)
    assert decision.permission == "ask" and "SECRET-3" in decision.rules, decision.reason


def test_a_committed_script_is_reviewed_code_and_is_not_opened(repo: Path):
    (repo / "serve.py").write_text("from dotenv import load_dotenv\nload_dotenv('.env')\n")
    git_commit(repo, "serve.py")
    assert guard.decide("python3 serve.py", repo, NO_SCANNER).permission == "allow"


def test_a_shell_script_is_parsed_as_shell(repo: Path):
    (repo / "fix.sh").write_text(
        "set -e\necho '{}' > .agentic-sdlc.json\npsql \"$PROD_URL\" -c 'drop table orders'\n"
    )
    decision = guard.decide("bash fix.sh", repo, NO_SCANNER)
    assert {"GUARD-2", "PROD-1"} <= set(decision.rules), decision.reason


def test_a_shell_script_that_only_reads_passes(repo: Path):
    (repo / "ok.sh").write_text("cat README.md\nls\n")
    assert guard.decide("sh ok.sh", repo, NO_SCANNER).permission == "allow"


def test_inline_code_that_only_reads_the_guard_config_passes(repo: Path):
    raw = "python3 -c \"import json; print(json.load(open('.agentic-sdlc.json')))\""
    assert "GUARD-2" not in guard.decide(raw, repo, NO_SCANNER).rules


def test_prod_1_ignores_a_marker_inside_the_statement(repo: Path):
    raw = "psql local -c 'delete from prod_orders'"
    assert "PROD-1" not in guard.decide(raw, repo, NO_SCANNER).rules


def test_prod_1_reads_the_target_from_a_variable_value(repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://app@orders-prod.internal/app")
    decision = guard.decide("psql \"$DATABASE_URL\" -c 'delete from t'", repo, NO_SCANNER)
    assert "PROD-1" in decision.rules and "$DATABASE_URL points there" in decision.reason
    assert "orders-prod" not in decision.reason


def test_prod_1_reads_the_host_a_client_takes_from_its_environment(
    repo: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("PGHOST", "db-production")
    assert "PROD-1" in guard.decide("psql -c 'drop table t'", repo, NO_SCANNER).rules
    monkeypatch.setenv("PGHOST", "localhost")
    assert "PROD-1" not in guard.decide("psql -c 'drop table t'", repo, NO_SCANNER).rules


def test_secret_2_knows_a_key_shaped_value_behind_a_neutral_name(
    repo: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("FOO", "ghp_" + "a" * 36)  # built at run time, never a literal
    decision = guard.decide('echo "$FOO"', repo, NO_SCANNER)
    assert "SECRET-2" in decision.rules and "GitHub token" in decision.reason
    assert "aaaa" not in decision.reason
    monkeypatch.setenv("FOO", "plain words")
    assert "SECRET-2" not in guard.decide('echo "$FOO"', repo, NO_SCANNER).rules


def test_the_wrapper_refuses_the_command_when_python3_is_missing(tmp_path: Path):
    wrapper = ROOT / "hooks" / "guard.sh"
    result = subprocess.run(
        ["/bin/sh", str(wrapper)],
        input="{}",
        capture_output=True,
        text=True,
        env={"PATH": str(tmp_path)},
        check=False,
    )
    assert result.returncode == 2 and "did not run" in result.stderr


def test_the_wrapper_passes_the_hook_decision_through(repo: Path):
    wrapper = ROOT / "hooks" / "guard.sh"
    for command, expected in (("git status", 0), ("git add -A", 0)):
        result = subprocess.run(
            ["/bin/sh", str(wrapper)],
            input=json.dumps(event("Bash", {"command": command}, repo)),
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == expected and "did not run" not in result.stderr
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_the_shell_hook_runs_through_the_wrapper():
    """Without the wrapper, a missing python3 is left to the agent's own failure handling."""
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    shell = [e for e in hooks["hooks"]["PreToolUse"] if e["matcher"] == "Bash"]
    assert [h["command"] for h in shell[0]["hooks"]] == [
        'sh "${CLAUDE_PLUGIN_ROOT}/hooks/guard.sh"'
    ]
