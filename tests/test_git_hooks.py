"""The native git hooks: the same rules for every agent and every person."""

from __future__ import annotations

import io
import json
import os
import stat
from pathlib import Path

import pytest

from agentic_sdlc import cli
from tests.conftest import git


def run(*argv: str) -> int:
    return cli.main(list(argv))


def test_commit_msg_hook_refuses_attribution(tmp_path: Path, capsys):
    message = tmp_path / "COMMIT_EDITMSG"
    message.write_text(
        "Fix parser\n\n# a git comment line\nCo-Authored-By: Claude <noreply@anthropic.com>\n",
        encoding="utf-8",
    )
    assert run("check-commit-msg", str(message), "--config-dir", str(tmp_path)) == 1
    assert "ATTR-1" in capsys.readouterr().out
    message.write_text("Fix parser\n\nSigned-off-by: Dev <dev@example.com>\n", encoding="utf-8")
    assert run("check-commit-msg", str(message), "--config-dir", str(tmp_path)) == 0


def test_commit_msg_hook_honours_strict_config(tmp_path: Path):
    (tmp_path / ".agentic-sdlc.json").write_text(
        json.dumps({"attribution": {"mode": "strict"}}), encoding="utf-8"
    )
    message = tmp_path / "msg"
    message.write_text("Add the Claude Code plugin manifest\n", encoding="utf-8")
    assert run("check-commit-msg", str(message), "--config-dir", str(tmp_path)) == 1


def test_pre_commit_hook_refuses_staged_secret(repo: Path, capsys):
    (repo / ".agentic-sdlc.json").write_text(
        json.dumps({"secrets": {"use_gitleaks": False}}), encoding="utf-8"
    )
    assert run("check-staged", "--config-dir", str(repo)) == 0
    (repo / "k.py").write_text("token = 'ghp_" + "a" * 36 + "'\n", encoding="utf-8")
    git(repo, "add", "k.py")
    assert run("check-staged", "--config-dir", str(repo)) == 1
    out = capsys.readouterr().out
    assert "SECRET-1" in out and "aaaa" not in out


def test_pre_push_hook_refuses_non_fast_forward_to_protected(repo: Path, monkeypatch, capsys):
    base = git(repo, "rev-parse", "HEAD")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-q", "-m", "second")
    head = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", "-b", "diverged", base)
    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    git(repo, "add", "b.txt")
    git(repo, "commit", "-q", "-m", "elsewhere")
    diverged = git(repo, "rev-parse", "HEAD")
    zero = "0" * 40

    def push(lines: str) -> int:
        monkeypatch.setattr("sys.stdin", io.StringIO(lines))
        return run("check-push", "origin", "git@example.invalid:o/r.git", "--config-dir", str(repo))

    assert push(f"refs/heads/main {head} refs/heads/main {base}\n") == 0
    assert push(f"refs/heads/main {diverged} refs/heads/main {head}\n") == 1
    assert "PUSH-1" in capsys.readouterr().out
    assert push(f"refs/heads/main {head} refs/heads/main {zero}\n") == 0
    assert push(f"(delete) {zero} refs/heads/main {head}\n") == 1
    assert push(f"refs/heads/feature {diverged} refs/heads/feature {head}\n") == 0


def test_hooks_install_status_uninstall(repo: Path, capsys):
    assert run("hooks", "install", "--dir", str(repo)) == 0
    hooks = repo / ".git" / "hooks"
    for name in ("commit-msg", "pre-commit", "pre-push"):
        path = hooks / name
        assert path.is_file() and path.stat().st_mode & stat.S_IXUSR
        assert cli.HOOK_MARK in path.read_text(encoding="utf-8")
    assert run("hooks", "status", "--dir", str(repo)) == 0
    assert capsys.readouterr().out.count("ours") == 3
    assert (repo / ".git" / "agentic-sdlc" / "agentic_sdlc" / "cli.py").is_file()
    assert run("hooks", "uninstall", "--dir", str(repo)) == 0
    assert not any((hooks / name).exists() for name in ("commit-msg", "pre-commit", "pre-push"))
    assert not (repo / ".git" / "agentic-sdlc").exists()


def test_hooks_install_keeps_a_foreign_hook(repo: Path, capsys):
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(exist_ok=True)
    (hooks / "pre-commit").write_text("#!/bin/sh\necho mine\n", encoding="utf-8")
    assert run("hooks", "install", "--dir", str(repo)) == 1
    assert "not written by agentic-sdlc" in capsys.readouterr().out
    assert run("hooks", "install", "--dir", str(repo), "--force") == 0


@pytest.mark.skipif(os.name == "nt", reason="sh hooks")
def test_installed_commit_msg_hook_blocks_a_real_commit(repo: Path):
    assert run("hooks", "install", "--dir", str(repo)) == 0
    (repo / "c.txt").write_text("c\n", encoding="utf-8")
    git(repo, "add", "c.txt")
    import subprocess

    result = subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", "Add c", "-m", "Generated with Claude Code"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0 and "ATTR-1" in result.stdout + result.stderr
    result = subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", "Add c"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
