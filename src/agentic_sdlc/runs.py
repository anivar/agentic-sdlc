"""Long-running agent runs: one command starts a named run that nobody has to watch.

``agentic-sdlc run <name> "<task and finish condition>"`` creates a worktree on the branch
``agent/<name>``, starts Claude Code in print mode or ``codex exec`` there with nothing that can
prompt, and returns once the run has started. The run detaches from the terminal, keeps the Mac
awake while it works, and stops at its spend cap or its time limit. ``agentic-sdlc runs`` lists
the runs with their state; ``runs read``, ``runs wait`` and ``runs stop`` act on one by name.

The record of each run is a JSON file beside its log under ``<git common dir>/agentic-sdlc/
runs/``, so every worktree of the repository sees the same runs. After the start, the run's
supervisor is the only writer of its record.

Processes: the supervisor leads its own session, and the agent leads a process group inside
that session. Ending a run ends the agent's whole group (SIGTERM, then SIGKILL after the
grace), so no child of the agent outlives the run. The supervisor holds an exclusive lock on
the run's lock file while it lives, and the kernel drops the lock when it dies, so a held lock
is the proof that the supervisor is alive. A process is signalled only when it is provably this
run's: the supervisor by its held lock; the agent's group by its group and session ids, or, once
its leader is gone, by the group itself (POSIX does not reuse a process id while a process
group with that id exists).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from agentic_sdlc import config as config_mod

# The supervisor needs POSIX sessions, process groups and file locks: macOS and Linux.
POSIX = os.name == "posix"
NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
SETTLED = {"done", "failed", "timed-out", "stopped", "lost"}
STOP_GRACE_SECONDS = 10.0
POLL_SECONDS = 2.0
START_SECONDS = 30.0
TASK_LIMIT = 256 * 1024
LOG_TAIL_LIMIT = 4 * 1024 * 1024
PROMPT_TAIL = (
    "This is an unattended run named {name} on the branch {branch}. Nobody is watching it. "
    "Follow the unattended-runs and session-handoff skills: keep the progress file, commit each "
    "passing step on this branch, never wait for a person, write every refused call into the "
    "held calls, and finish with the run report in .agent/run-report.md, committed with the "
    "last checkpoint."
)


class RunError(Exception):
    """A run that cannot start or a name that does not resolve; the message says why."""


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def runs_dir(cwd: Path) -> Path:
    common = config_mod.git_common_dir(cwd)
    if common is None:
        raise RunError(f"{cwd} is not inside a git repository")
    return common / "agentic-sdlc" / "runs"


def agent_command(agent: str, prompt: str, budget: float) -> list[str]:
    """The agent's own command line for a run with nothing that can prompt. Claude Code takes a
    spend cap; Codex has none, so the time limit bounds a Codex run."""
    if agent == "claude":
        return [
            "claude",
            "-p",
            prompt,
            "--permission-mode",
            "auto",
            "--permission-prompts",
            "none",
            "--max-budget-usd",
            f"{budget:g}",
        ]
    if agent == "codex":
        return ["codex", "exec", prompt, "--sandbox", "workspace-write", "--approve-for-me"]
    raise RunError(f"unknown agent {agent!r}; use claude or codex")


def plan(
    name: str, task: str, agent: str, budget: float, hours: float, base: str, cwd: Path
) -> dict:
    """The run record before anything is created. Refuses a system without POSIX processes, a
    bad name, a name in use, a branch or worktree path that exists, a task too long for a
    command line, and an agent that is not on PATH."""
    if not POSIX:
        raise RunError(
            "agentic-sdlc run needs macOS or Linux: it uses POSIX sessions, process groups "
            "and file locks"
        )
    if not NAME_RE.match(name):
        raise RunError(f"run name {name!r} must match {NAME_RE.pattern}")
    if not task.strip():
        raise RunError("the task is empty; give the task and its finish condition")
    if len(task.encode("utf-8")) > TASK_LIMIT:
        raise RunError(
            f"the task is over {TASK_LIMIT // 1024} KB; write it to a file in the repository "
            "and name the file in the task"
        )
    if hours <= 0 or budget <= 0:
        raise RunError("--hours and --budget must be above zero")
    top = config_mod.git_toplevel(cwd)
    if top is None:
        raise RunError(f"{cwd} is not inside a git repository")
    folder = runs_dir(cwd)
    if (folder / f"{name}.json").exists():
        raise RunError(
            f"a run named {name} exists; pick another name, or read it: agentic-sdlc runs read {name}"
        )
    branch = f"agent/{name}"
    if _git(top, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0:
        raise RunError(f"the branch {branch} exists; pick another name")
    worktree = top.parent / f"{top.name}.{name}"
    if worktree.exists():
        raise RunError(f"{worktree} exists; pick another name")
    command = agent_command(
        agent, f"{task.strip()}\n\n{PROMPT_TAIL.format(name=name, branch=branch)}", budget
    )
    if shutil.which(command[0]) is None:
        raise RunError(f"{command[0]} is not on PATH")
    return {
        "name": name,
        "agent": agent,
        "task": task.strip(),
        "branch": branch,
        "base": base,
        "worktree": str(worktree),
        "repository": str(top),
        "budget_usd": budget if agent == "claude" else None,
        "hours": hours,
        "grace_seconds": STOP_GRACE_SECONDS,
        "command": command,
        "log": str(folder / f"{name}.log"),
        "state": "planned",
    }


def start(record: dict, wait: bool = False) -> int:
    """Create the worktree, write the record and start the supervisor detached from this
    terminal; return once the supervisor has taken the record over. With wait, block until the
    run settles and print the end of its log."""
    top = Path(record["repository"])
    made = _git(
        top, "worktree", "add", "-q", "-b", record["branch"], record["worktree"], record["base"]
    )
    if made.returncode != 0:
        raise RunError(f"git worktree add failed: {made.stderr.strip()}")
    file = Path(record["log"]).with_suffix(".json")
    file.parent.mkdir(parents=True, exist_ok=True)
    record.update(state="starting", started=now())
    _save(file, record)
    with open(record["log"], "ab") as log:
        supervisor = subprocess.Popen(
            [sys.executable, "-m", "agentic_sdlc", "run", "--supervise", str(file)],
            cwd=record["worktree"],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=_child_env(),
        )
    deadline = time.monotonic() + START_SECONDS
    while not _load(file).get("supervisor_pid"):
        if supervisor.poll() is not None:
            # It died before taking the record over, so this process is still its only writer.
            failed = dict(record, state="failed", exit_code=supervisor.returncode, ended=now())
            _save(file, failed)
            raise RunError(f"the run did not start; its log: {record['log']}")
        if time.monotonic() >= deadline:
            raise RunError(
                f"the run has not started after {START_SECONDS:g}s; its log: {record['log']}"
            )
        time.sleep(0.05)
    if wait:
        return wait_for(record["name"], Path(record["worktree"]), timeout=None, out=sys.stdout)
    return 0


def supervise(file: Path) -> int:
    """Run the agent to its end, its time limit or a stop, and keep the record current. It runs
    in its own session, so closing the terminal does not end it."""
    stopping: list[int] = []

    def on_stop(signum: int, _frame: object) -> None:
        stopping.append(signum)

    signal.signal(signal.SIGTERM, on_stop)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    import fcntl  # POSIX only, like the sessions and signals below

    lock = open(_lock_file(file), "a")  # noqa: SIM115 - held open for this process's life
    fcntl.flock(lock, fcntl.LOCK_EX)
    record = _load(file)
    if record.get("state") != "starting":
        print(f"agentic-sdlc run {record['name']}: already {record.get('state')}", flush=True)
        return 1
    record.update(supervisor_pid=os.getpid())
    _save(file, record)
    if shutil.which("caffeinate"):
        # Idle sleep is held off until this process ends; lid close and low battery still sleep.
        subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())], stdout=subprocess.DEVNULL)
    grace = float(record.get("grace_seconds", STOP_GRACE_SECONDS))
    env = dict(os.environ, **{config_mod.UNATTENDED_ENV: "1"})
    print(f"agentic-sdlc run {record['name']}: {record['agent']} started {now()}", flush=True)
    try:
        agent = subprocess.Popen(
            record["command"],
            cwd=record["worktree"],
            stdin=subprocess.DEVNULL,
            env=env,
            preexec_fn=os.setpgrp,  # the agent leads a group in this session
        )
    except OSError as exc:
        record.update(state="failed", error=f"the agent did not start: {exc}", ended=now())
        _save(file, record)
        print(f"agentic-sdlc run {record['name']}: failed, {record['error']}", flush=True)
        return 0
    record.update(state="working", agent_pid=agent.pid)
    _save(file, record)
    deadline = time.monotonic() + float(record["hours"]) * 3600
    state = "working"
    while state == "working":
        try:
            code = agent.wait(timeout=1)
            state = "done" if code == 0 else "failed"
        except subprocess.TimeoutExpired:
            if stopping:
                state = "stopped"
            elif time.monotonic() >= deadline:
                state = "timed-out"
    code = end_group(agent.pid, grace, agent)
    record.update(state=state, exit_code=code, ended=now())
    _save(file, record)
    print(
        f"\nagentic-sdlc run {record['name']}: {state} {record['ended']}, exit {code}", flush=True
    )
    return 0


def end_group(pgid: int, grace: float, agent: subprocess.Popen | None = None) -> int | None:
    """End the agent's process group: SIGTERM, then SIGKILL to whatever is left after the
    grace. Children the agent left behind are ended too, when it has already exited."""
    _signal_group(pgid, signal.SIGTERM)
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        if agent is not None:
            agent.poll()  # reap the leader, so a group of one zombie reads as gone
        if not _group_exists(pgid):
            break
        time.sleep(0.1)
    _signal_group(pgid, signal.SIGKILL)
    return agent.wait() if agent is not None else None


def load_all(cwd: Path) -> list[dict]:
    records = [_read(p) for p in sorted(runs_dir(cwd).glob("*.json"))]
    return sorted(records, key=lambda r: r.get("started", ""))


def load_one(name: str, cwd: Path) -> dict:
    file = runs_dir(cwd) / f"{name}.json"
    if not file.exists():
        raise RunError(f"no run named {name}; agentic-sdlc runs lists them")
    return _read(file)


def _read(file: Path) -> dict:
    """The record with its live state. When the supervisor is found gone, the record is read
    again: a supervisor writes its last state before it exits, so the second read sees it."""
    record = _load(file)
    record["state"] = _live_state(record)
    if record["state"] in ("lost", "orphaned"):
        record = _load(file)
        record["state"] = _live_state(record)
    return record


def read_log(name: str, cwd: Path, lines: int) -> str:
    """The last lines of the run's log, read from its end."""
    log = Path(load_one(name, cwd)["log"])
    if not log.exists():
        return ""
    with open(log, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        position = handle.tell()
        data = b""
        while position > 0 and data.count(b"\n") <= lines and len(data) < LOG_TAIL_LIMIT:
            step = min(64 * 1024, position)
            position -= step
            handle.seek(position)
            data = handle.read(step) + data
    tail = deque(data.decode("utf-8", errors="replace").splitlines(), maxlen=lines)
    return "\n".join(tail)


def wait_for(name: str, cwd: Path, timeout: float | None, out=sys.stdout) -> int:
    """Block until the run settles or the timeout passes. Exit 0 when it ended done, 1 when it
    ended any other way, 3 when the timeout passed first."""
    deadline = None if timeout is None else time.monotonic() + timeout
    while True:
        record = load_one(name, cwd)
        if record["state"] in SETTLED:
            print(f"{name}: {record['state']}", file=out)
            print(read_log(name, cwd, 20), file=out)
            return 0 if record["state"] == "done" else 1
        if deadline is not None and time.monotonic() >= deadline:
            print(f"{name}: still {record['state']}", file=out)
            return 3
        time.sleep(POLL_SECONDS)


def stop(name: str, cwd: Path) -> str:
    """Stop a run. A working run's supervisor ends the agent and records the stop. An
    orphaned run, whose supervisor is gone, has its agent's group ended here and is recorded
    as stopped. Nothing that is not provably this run's is signalled."""
    record = load_one(name, cwd)
    state = record["state"]
    if state in SETTLED:
        return f"{name} is already {state}"
    if state == "orphaned":
        end_group(record["agent_pid"], float(record.get("grace_seconds", STOP_GRACE_SECONDS)))
        file = runs_dir(cwd) / f"{name}.json"
        _save(file, dict(_load(file), state="stopped", ended=now()))
        return f"{name}: its supervisor was gone; the agent's processes are ended"
    pid = record.get("supervisor_pid")
    if not pid or not _supervisor_alive(record):
        return f"{name} is starting; stop it again in a moment"
    os.kill(pid, signal.SIGTERM)
    return f"{name}: stop sent; agentic-sdlc runs wait {name} shows when it has ended"


def _live_state(record: dict) -> str:
    """The recorded state, checked against the processes. A run whose supervisor is gone is
    orphaned while its agent's group still runs, and lost once nothing of it runs: its worktree
    and branch keep what it committed."""
    state = record.get("state", "planned")
    if state not in ("starting", "working"):
        return state
    if _supervisor_alive(record):
        return state
    if not record.get("supervisor_pid"):
        return "starting" if _age_seconds(record) < START_SECONDS else "lost"
    return "orphaned" if _agent_group_is_ours(record) else "lost"


def _lock_file(record_file: Path) -> Path:
    return record_file.with_suffix(".lock")


def _supervisor_alive(record: dict) -> bool:
    """True while a supervisor holds the run's lock. The probe takes the lock for an instant
    when it is free; a supervisor that starts in that instant waits for it."""
    import fcntl

    if not record.get("log"):
        return False
    file = _lock_file(Path(record["log"]).with_suffix(".json"))
    if not file.exists():
        return False
    with open(file, "a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        except OSError:
            return False
        fcntl.flock(handle, fcntl.LOCK_UN)
    return False


def _agent_group_is_ours(record: dict) -> bool:
    pgid, supervisor = record.get("agent_pid"), record.get("supervisor_pid")
    if not pgid or not _group_exists(pgid):
        return False
    if not _process_exists(pgid):
        return True  # a group without its leader is the group that leader made
    try:
        return os.getpgid(pgid) == pgid and os.getsid(pgid) == supervisor
    except OSError:
        return False


def _process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def _signal_group(pgid: int, signum: int) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pgid, signum)


def _age_seconds(record: dict) -> float:
    try:
        started = datetime.strptime(record["started"], "%Y-%m-%dT%H:%M:%SZ")
    except (KeyError, ValueError):
        return float("inf")
    return (datetime.now(timezone.utc) - started.replace(tzinfo=timezone.utc)).total_seconds()


def on_battery() -> bool:
    if not shutil.which("pmset"):
        return False
    result = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, check=False)
    return "Battery Power" in result.stdout.splitlines()[0] if result.stdout else False


def _child_env() -> dict[str, str]:
    """The supervisor's environment: this one, with the package importable from its source
    tree when it runs from a checkout rather than an install."""
    env = dict(os.environ)
    package_root = str(Path(__file__).resolve().parent.parent)
    env["PYTHONPATH"] = os.pathsep.join(p for p in (package_root, env.get("PYTHONPATH", "")) if p)
    return env


def _load(file: Path) -> dict:
    return json.loads(file.read_text(encoding="utf-8"))


def _save(file: Path, record: dict) -> None:
    temporary = file.with_name(f"{file.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    temporary.replace(file)


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=False
    )
