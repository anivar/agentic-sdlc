"""Command shapes an agent could use to slip past the rules. Each one was reproduced on
2026-10-10 before the fix; the expected decision is the rule's, not a convenience."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_sdlc import command as command_mod
from agentic_sdlc import config as config_mod
from agentic_sdlc import guard
from tests.conftest import git

NO_GITLEAKS = config_mod.from_dict({"secrets": {"use_gitleaks": False}})


@pytest.mark.parametrize(
    "raw",
    [
        "sh -c 'git add -A'",
        'bash -lc "git add -A"',
        "zsh -c 'git add -A'",
        "bash -o pipefail -c 'git add -A'",
        "eval git add -A",
        "xargs git add -A < /dev/null",
        "env -i git add -A",
        "nice -n 5 git add -A",
        "timeout -k 1 5 git add -A",
        "( git add -A )",
        "{ git add -A; }",
        "sh -c \"sh -c 'git add -A'\"",
    ],
)
def test_wrappers_do_not_hide_a_bulk_add(repo: Path, raw: str):
    decision = guard.decide(raw, repo, NO_GITLEAKS)
    assert decision.permission == "deny" and "STAGE-1" in decision.rules, raw


def test_wrapped_force_push_and_commit_are_still_gated(repo: Path):
    decision = guard.decide('bash -lc "git push --force origin main"', repo, NO_GITLEAKS)
    assert decision.permission == "deny" and "PUSH-1" in decision.rules
    decision = guard.decide("bash -c 'git commit -m x'", repo, NO_GITLEAKS)
    assert decision.permission == "ask" and "ASK-1" in decision.rules


def test_trailer_flag_is_scanned(repo: Path):
    raw = 'git commit -m x --trailer "Co-authored-by: Claude <noreply@anthropic.com>"'
    decision = guard.decide(raw, repo, NO_GITLEAKS)
    assert decision.permission == "deny" and "ATTR-1" in decision.rules
    raw = 'git commit -m x --trailer="Co-authored-by: Claude <noreply@anthropic.com>"'
    assert guard.decide(raw, repo, NO_GITLEAKS).permission == "deny"


def test_escaped_newline_before_a_trailer_is_scanned(repo: Path):
    raw = "printf 'Fix thing\\nCo-Authored-By: Claude <noreply@anthropic.com>\\n' | git commit -F -"
    decision = guard.decide(raw, repo, NO_GITLEAKS)
    assert decision.permission == "deny" and "ATTR-1" in decision.rules
    # A message built by a substitution cannot be read before it runs: the ask names that,
    # and the pull request check scans the resulting commit.
    raw = "git commit -m \"$(printf 'x\\n\\nCo-Authored-By: Claude <noreply@anthropic.com>')\""
    decision = guard.decide(raw, repo, NO_GITLEAKS)
    assert decision.permission == "ask" and "substitution" in decision.reason


def test_substituted_message_text_is_named_in_the_ask(repo: Path):
    decision = guard.decide('git commit -m "$(cat m.txt)"', repo, NO_GITLEAKS)
    assert decision.permission == "ask"
    assert "substitution" in decision.reason
    decision = guard.decide("git commit --file=<(printf x)", repo, NO_GITLEAKS)
    assert "substitution" in decision.reason


def test_secret_scan_follows_dash_c_and_cd(repo: Path, tmp_path: Path):
    (repo / "k.py").write_text("AWS_KEY = 'AKIA" + "ABCDEFGHIJKLMNOP'\n", encoding="utf-8")
    git(repo, "add", "k.py")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    decision = guard.decide(f'git -C {repo} commit -m "Add k"', elsewhere, NO_GITLEAKS)
    assert decision.permission == "deny" and "SECRET-1" in decision.rules
    decision = guard.decide(f'cd {repo} && git commit -m "Add k"', elsewhere, NO_GITLEAKS)
    assert decision.permission == "deny" and "SECRET-1" in decision.rules


def test_force_push_follows_dash_c_and_cd(repo: Path, tmp_path: Path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    decision = guard.decide(f"git -C {repo} push -f", elsewhere, NO_GITLEAKS)
    assert decision.permission == "deny" and "PUSH-1" in decision.rules
    decision = guard.decide(f"cd {repo} && git push -f", elsewhere, NO_GITLEAKS)
    assert decision.permission == "deny" and "PUSH-1" in decision.rules


def test_untraceable_gated_commands_ask(repo: Path):
    for raw in ('some-tool --run "git commit -m x"', "./release.sh 'git push origin main'"):
        decision = guard.decide(raw, repo, NO_GITLEAKS)
        assert decision.permission == "ask" and decision.rules == ["TRACE-1"], raw


def test_traced_reads_do_not_trigger_trace(repo: Path):
    for raw in ("gh pr view 12", "git log --oneline", "grep -r TODO src/"):
        assert guard.decide(raw, repo, NO_GITLEAKS).permission == "allow", raw


def test_scoped_bulk_add_is_allowed_and_root_is_not():
    assert not command_mod.parse("git add -A src/").commands[0].add_all
    assert not command_mod.parse("git add -u docs/ src/").commands[0].add_all
    assert command_mod.parse("git add -A").commands[0].add_all
    assert command_mod.parse("git add -A .").commands[0].add_all
    assert command_mod.parse("git add src/ .").commands[0].add_all


def test_robot_emoji_only_counts_beside_a_footer_or_vendor(repo: Path):
    decision = guard.decide(
        'git commit -m "\U0001f916 Add the robot emoji to the README"', repo, NO_GITLEAKS
    )
    assert decision.permission == "ask"
    decision = guard.decide(
        'git commit -m "x" -m "\U0001f916 Generated with [Claude Code](https://claude.com/claude-code)"',
        repo,
        NO_GITLEAKS,
    )
    assert decision.permission == "deny" and "ATTR-1" in decision.rules


def test_command_v_is_not_a_wrapper():
    parsed = command_mod.parse("command -v git")
    assert parsed.commands[0].kind == "other"
