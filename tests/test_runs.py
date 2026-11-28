"""agentic-sdlc run: one command starts a named run in its own worktree that nobody has to
watch, and the runs commands list, read, wait for and stop it by name. A fake agent on PATH
stands in for Claude Code and Codex."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

from agentic_sdlc import cli, guard, runs
from agentic_sdlc import config as config_mod

FAKE_AGENT = """#!/bin/sh
echo "fake agent: unattended=${AGENTIC_SDLC_UNATTENDED:-unset} cwd=$(pwd)"
if [ "${FAKE_MODE:-}" = childful ]; then
  (trap '' TERM; while :; do echo x >> "$FAKE_BEAT"; sleep 0.1; done) &
  sleep 60
fi
sleep "${FAKE_SLEEP:-0}"
exit "${FAKE_EXIT:-0}"
"""


@pytest.fixture
def agents(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "bin"
    folder.mkdir()
    for name in ("claude", "codex"):
        (folder / name).write_text(FAKE_AGENT, encoding="utf-8")
        (folder / name).chmod(0o755)
    # Only the fakes and the system folders: a test can never reach an installed agent.
    monkeypatch.setenv("PATH", os.pathsep.join((str(folder), "/usr/bin", "/bin")))
    monkeypatch.delenv(config_mod.UNATTENDED_ENV, raising=False)
    monkeypatch.setattr(runs, "POLL_SECONDS", 0.2)
    return folder


def begin(repo: Path, name: str, agent: str = "claude", hours: float = 1.0) -> dict:
    record = runs.plan(
        name, "Write a note; done when note.md exists", agent, 5, hours, "HEAD", repo
    )
    assert runs.start(record) == 0
    assert runs.load_one(name, repo).get("supervisor_pid")  # the supervisor took it over
    return record


def test_a_run_name_is_short_lower_case_and_unused(repo: Path, agents: Path):
    for bad in ("Fix", "1fix", "fix parser", "x" * 33, ""):
        with pytest.raises(runs.RunError):
            runs.plan(bad, "task", "claude", 5, 1, "HEAD", repo)
    begin(repo, "note")
    assert runs.wait_for("note", repo, timeout=30) == 0
    with pytest.raises(runs.RunError, match="exists"):
        runs.plan("note", "task", "claude", 5, 1, "HEAD", repo)


def test_a_dry_run_shows_a_launch_with_nothing_that_can_prompt(repo: Path, agents: Path):
    claude = runs.plan("one", "task", "claude", 7.5, 1, "HEAD", repo)["command"]
    assert claude[:2] == ["claude", "-p"]
    assert claude[claude.index("--permission-prompts") + 1] == "none"
    assert claude[claude.index("--max-budget-usd") + 1] == "7.5"
    codex = runs.plan("two", "task", "codex", 7.5, 1, "HEAD", repo)
    assert codex["command"][:2] == ["codex", "exec"] and "--approve-for-me" in codex["command"]
    assert codex["budget_usd"] is None
    assert cli.main(["run", "three", "task", "--dry-run", "--cwd", str(repo)]) == 0
    assert not (repo.parent / "repo.three").exists()


def test_a_run_works_in_its_own_worktree_with_the_signal_set_for_it_alone(repo: Path, agents: Path):
    record = begin(repo, "note")
    assert runs.wait_for("note", repo, timeout=30) == 0
    log = runs.read_log("note", repo, 40)
    assert "unattended=1" in log and f"cwd={repo.parent / 'repo.note'}" in log
    assert runs.load_one("note", repo)["state"] == "done"
    branch = subprocess.run(
        ["git", "-C", record["worktree"], "branch", "--show-current"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert branch == "agent/note"
    assert config_mod.UNATTENDED_ENV not in os.environ


def test_an_agent_that_fails_ends_the_run_failed(
    repo: Path, agents: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("FAKE_EXIT", "3")
    begin(repo, "broken", agent="codex")
    assert runs.wait_for("broken", repo, timeout=30) == 1
    record = runs.load_one("broken", repo)
    assert record["state"] == "failed" and record["exit_code"] == 3


def test_the_time_limit_ends_a_run(repo: Path, agents: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FAKE_SLEEP", "60")
    begin(repo, "slow", hours=0.0005)
    assert runs.wait_for("slow", repo, timeout=30) == 1
    assert runs.load_one("slow", repo)["state"] == "timed-out"


def test_stop_ends_a_working_run(repo: Path, agents: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FAKE_SLEEP", "60")
    begin(repo, "long")
    assert runs.wait_for("long", repo, timeout=1) == 3  # still working
    supervisor = runs.load_one("long", repo)["supervisor_pid"]
    assert os.getsid(supervisor) != os.getsid(0)  # its own session: closing the terminal spares it
    asked = time.monotonic()
    assert "stop sent" in runs.stop("long", repo)
    assert runs.wait_for("long", repo, timeout=30) == 1
    assert time.monotonic() - asked < runs.STOP_GRACE_SECONDS / 2  # no wait for the grace
    assert runs.load_one("long", repo)["state"] == "stopped"


def test_a_run_whose_supervisor_is_gone_is_lost_and_is_not_signalled(repo: Path, agents: Path):
    gone = subprocess.Popen(["true"])
    gone.wait()
    folder = runs.runs_dir(repo)
    folder.mkdir(parents=True)
    for name, pid in (("gone", gone.pid), ("other", os.getpid())):
        record = {
            "name": name,
            "agent": "claude",
            "branch": f"agent/{name}",
            "log": str(folder / f"{name}.log"),
        }
        record.update(state="working", supervisor_pid=pid)
        runs._save(folder / f"{name}.json", record)
        assert runs.load_one(name, repo)["state"] == "lost"
        assert "stop sent" not in runs.stop(name, repo)


def test_agentic_sdlc_run_starts_an_unattended_run_and_is_recorded(repo: Path):
    decision = guard.decide('agentic-sdlc run fix "Fix it"', repo, config_mod.from_dict({}))
    assert decision.permission == "allow" and "RUN-4" in decision.rules
    dry = guard.decide('agentic-sdlc run fix "Fix it" --dry-run', repo, config_mod.from_dict({}))
    assert "RUN-4" not in dry.rules


def heartbeat(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """A fake agent whose child ignores SIGTERM and writes a line every 0.1 s."""
    beat = tmp_path / "beat"
    monkeypatch.setenv("FAKE_MODE", "childful")
    monkeypatch.setenv("FAKE_BEAT", str(beat))
    monkeypatch.setattr(runs, "STOP_GRACE_SECONDS", 1.0)
    return beat


def until(condition, seconds: float = 15.0) -> None:
    end = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < end, "condition not met in time"
        time.sleep(0.05)


def still(beat: Path) -> bool:
    size = beat.stat().st_size
    time.sleep(0.5)
    return beat.stat().st_size == size


def test_ending_a_run_ends_every_process_it_started(
    repo: Path, agents: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    beat = heartbeat(monkeypatch, tmp_path)
    begin(repo, "kids")
    until(beat.exists)
    runs.stop("kids", repo)
    assert runs.wait_for("kids", repo, timeout=30) == 1
    assert still(beat)  # the child that ignored SIGTERM got SIGKILL after the grace


def test_a_run_whose_supervisor_is_killed_is_orphaned_until_stopped(
    repo: Path, agents: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    beat = heartbeat(monkeypatch, tmp_path)
    begin(repo, "orphan")
    until(beat.exists)
    os.kill(runs.load_one("orphan", repo)["supervisor_pid"], signal.SIGKILL)
    until(lambda: runs.load_one("orphan", repo)["state"] == "orphaned")
    os.kill(runs.load_one("orphan", repo)["agent_pid"], signal.SIGKILL)  # its child lives on
    time.sleep(0.3)
    assert runs.load_one("orphan", repo)["state"] == "orphaned"
    assert "processes are ended" in runs.stop("orphan", repo)
    assert runs.load_one("orphan", repo)["state"] == "stopped"
    assert still(beat)


def test_an_agent_that_cannot_start_ends_the_run_failed(repo: Path, agents: Path):
    record = runs.plan("noexec", "task", "claude", 5, 1, "HEAD", repo)
    (agents / "claude").chmod(0o644)
    assert runs.start(record) == 0
    assert runs.wait_for("noexec", repo, timeout=30) == 1
    assert "did not start" in runs.load_one("noexec", repo)["error"]


def test_a_task_too_long_for_a_command_line_is_refused(repo: Path, agents: Path):
    with pytest.raises(runs.RunError, match="KB"):
        runs.plan("long", "x" * (runs.TASK_LIMIT + 1), "claude", 5, 1, "HEAD", repo)


def test_reading_a_log_reads_its_end(repo: Path):
    folder = runs.runs_dir(repo)
    folder.mkdir(parents=True)
    log = folder / "big.log"
    log.write_text("".join(f"line {i}\n" for i in range(200_000)), encoding="utf-8")
    runs._save(folder / "big.json", {"name": "big", "state": "done", "log": str(log)})
    assert runs.read_log("big", repo, 3) == "line 199997\nline 199998\nline 199999"


def test_a_run_not_yet_taken_over_is_starting_and_then_lost(repo: Path):
    folder = runs.runs_dir(repo)
    folder.mkdir(parents=True)
    for name, started in (("fresh", runs.now()), ("stale", "2026-01-01T00:00:00Z")):
        runs._save(folder / f"{name}.json", {"name": name, "state": "starting", "started": started})
    assert runs.load_one("fresh", repo)["state"] == "starting"
    assert runs.load_one("stale", repo)["state"] == "lost"
    assert "starting" in runs.stop("fresh", repo)


def test_a_run_that_ends_while_it_is_read_reads_as_ended(
    repo: Path, monkeypatch: pytest.MonkeyPatch
):
    folder = runs.runs_dir(repo)
    folder.mkdir(parents=True)
    file = folder / "edge.json"
    runs._save(
        file, {"name": "edge", "state": "working", "supervisor_pid": 1, "started": runs.now()}
    )

    def supervisor_ends_now(_record: dict) -> bool:
        # The supervisor writes its last state and exits between the read and the check.
        runs._save(file, dict(runs._load(file), state="done"))
        return False

    monkeypatch.setattr(runs, "_supervisor_alive", supervisor_ends_now)
    assert runs.load_one("edge", repo)["state"] == "done"
