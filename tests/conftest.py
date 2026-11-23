from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


@pytest.fixture(autouse=True)
def attended_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """A shell that exported AGENTIC_SDLC_UNATTENDED must not change what the suite expects.
    The suite runs in confirm mode, where each rule's own decision shows; test_modes.py covers
    agent mode, the default, which turns each ask into a recorded allow (AGENT-1)."""
    monkeypatch.delenv("AGENTIC_SDLC_UNATTENDED", raising=False)
    monkeypatch.setenv("AGENTIC_SDLC_MODE", "confirm")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A throwaway repository with one commit on main and a clean index."""
    path = tmp_path / "repo"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "test@example.invalid")
    git(path, "config", "user.name", "Test")
    git(path, "config", "commit.gpgsign", "false")
    (path / "README.md").write_text("# test\n", encoding="utf-8")
    git(path, "add", "README.md")
    git(path, "commit", "-q", "-m", "init")
    return path
