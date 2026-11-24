"""Command shapes an agent could use to slip past the rules. Each one was reproduced on
2026-10-10 before the fix; the expected decision is the rule's, not a convenience."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_sdlc import command as command_mod
from agentic_sdlc import config as config_mod
from agentic_sdlc import guard
from tests.conftest import git

NO_SCANNER = config_mod.from_dict({"secrets": {"scanner": "none"}})


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
    decision = guard.decide(raw, repo, NO_SCANNER)
    assert decision.permission == "deny" and "STAGE-1" in decision.rules, raw


def test_wrapped_force_push_and_commit_are_still_gated(repo: Path):
    decision = guard.decide('bash -lc "git push --force origin main"', repo, NO_SCANNER)
    assert decision.permission == "deny" and "PUSH-1" in decision.rules
    decision = guard.decide("bash -c 'git commit -m x'", repo, NO_SCANNER)
    assert decision.permission == "ask" and "ASK-1" in decision.rules


def test_trailer_flag_is_scanned(repo: Path):
    raw = 'git commit -m x --trailer "Co-authored-by: Claude <noreply@anthropic.com>"'
    decision = guard.decide(raw, repo, NO_SCANNER)
    assert decision.permission == "deny" and "ATTR-1" in decision.rules
    raw = 'git commit -m x --trailer="Co-authored-by: Claude <noreply@anthropic.com>"'
    assert guard.decide(raw, repo, NO_SCANNER).permission == "deny"


def test_escaped_newline_before_a_trailer_is_scanned(repo: Path):
    raw = "printf 'Fix thing\\nCo-Authored-By: Claude <noreply@anthropic.com>\\n' | git commit -F -"
    decision = guard.decide(raw, repo, NO_SCANNER)
    assert decision.permission == "deny" and "ATTR-1" in decision.rules
    # A message built by a substitution cannot be read before it runs: the ask names that,
    # and the pull request check scans the resulting commit.
    raw = "git commit -m \"$(printf 'x\\n\\nCo-Authored-By: Claude <noreply@anthropic.com>')\""
    decision = guard.decide(raw, repo, NO_SCANNER)
    assert decision.permission == "ask" and "substitution" in decision.reason


def test_substituted_message_text_is_named_in_the_ask(repo: Path):
    decision = guard.decide('git commit -m "$(cat m.txt)"', repo, NO_SCANNER)
    assert decision.permission == "ask"
    assert "substitution" in decision.reason
    decision = guard.decide("git commit --file=<(printf x)", repo, NO_SCANNER)
    assert "substitution" in decision.reason


def test_secret_scan_follows_dash_c_and_cd(repo: Path, tmp_path: Path):
    (repo / "k.py").write_text("AWS_KEY = 'AKIA" + "ABCDEFGHIJKLMNOP'\n", encoding="utf-8")
    git(repo, "add", "k.py")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    decision = guard.decide(f'git -C {repo} commit -m "Add k"', elsewhere, NO_SCANNER)
    assert decision.permission == "deny" and "SECRET-1" in decision.rules
    decision = guard.decide(f'cd {repo} && git commit -m "Add k"', elsewhere, NO_SCANNER)
    assert decision.permission == "deny" and "SECRET-1" in decision.rules


def test_force_push_follows_dash_c_and_cd(repo: Path, tmp_path: Path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    decision = guard.decide(f"git -C {repo} push -f", elsewhere, NO_SCANNER)
    assert decision.permission == "deny" and "PUSH-1" in decision.rules
    decision = guard.decide(f"cd {repo} && git push -f", elsewhere, NO_SCANNER)
    assert decision.permission == "deny" and "PUSH-1" in decision.rules


def test_untraceable_gated_commands_ask(repo: Path):
    for raw in ('some-tool --run "git commit -m x"', "./release.sh 'git push origin main'"):
        decision = guard.decide(raw, repo, NO_SCANNER)
        assert decision.permission == "ask" and decision.rules == ["TRACE-1"], raw


def _untracked(value: str) -> config_mod.Config:
    return config_mod.from_dict({"trace": {"untracked": value}, "secrets": {"scanner": "none"}})


def test_untraced_commands_follow_trace_untracked(repo: Path):
    raw = "python3 deploy.py"
    assert guard.decide(raw, repo, NO_SCANNER).permission == "allow"
    decision = guard.decide(raw, repo, _untracked("ask"))
    assert decision.permission == "ask" and decision.rules == ["TRACE-2"]
    decision = guard.decide(raw, repo, _untracked("deny"))
    assert decision.permission == "deny" and decision.rules == ["TRACE-2"]
    assert "Fix:" in decision.reason


def test_read_only_untraced_commands_pass_under_trace_untracked(repo: Path):
    for raw in (
        "ls -la",
        "echo hi | grep h | sort | uniq",
        "pwd && date",
        "find . -name '*.py' | wc -l",
        "test -f README.md && true",
    ):
        assert guard.decide(raw, repo, _untracked("deny")).permission == "allow", raw
    decision = guard.decide("ls && make deploy", repo, _untracked("deny"))
    assert decision.permission == "deny" and "TRACE-2" in decision.rules


def test_trace_1_still_fires_beside_trace_2(repo: Path):
    decision = guard.decide('some-tool --run "git commit -m x"', repo, _untracked("deny"))
    assert decision.permission == "deny"
    assert "TRACE-1" in decision.rules and "TRACE-2" in decision.rules


def test_trace_untracked_rejects_a_bad_value():
    cfg = config_mod.from_dict({"trace": {"untracked": "yolo"}})
    assert cfg.trace_untracked == "allow"
    assert any("trace.untracked" in problem for problem in cfg.problems)


def test_interpreter_evasion_hints_are_gated(repo: Path):
    for raw in (
        'python3 -c \'import subprocess; subprocess.run(["git", "push"])\'',
        "node -e \"require('child_process').execSync('git commit')\"",
        'ruby -e \'system("git", "push")\'',
        'perl -e \'system "git", "add", "."\'',
    ):
        decision = guard.decide(raw, repo, NO_SCANNER)
        assert decision.permission == "ask" and "TRACE-1" in decision.rules, raw
    # An inline script that never names git stays allowed.
    assert guard.decide("python3 -c 'print(1)'", repo, NO_SCANNER).permission == "allow"


def test_traced_reads_do_not_trigger_trace(repo: Path):
    for raw in ("gh pr view 12", "git log --oneline", "grep -r TODO src/"):
        assert guard.decide(raw, repo, NO_SCANNER).permission == "allow", raw


def test_scoped_bulk_add_is_allowed_and_root_is_not():
    assert not command_mod.parse("git add -A src/").commands[0].add_all
    assert not command_mod.parse("git add -u docs/ src/").commands[0].add_all
    assert command_mod.parse("git add -A").commands[0].add_all
    assert command_mod.parse("git add -A .").commands[0].add_all
    assert command_mod.parse("git add src/ .").commands[0].add_all


def test_robot_emoji_only_counts_beside_a_footer_or_vendor(repo: Path):
    decision = guard.decide(
        'git commit -m "\U0001f916 Add the robot emoji to the README"', repo, NO_SCANNER
    )
    assert decision.permission == "ask"
    decision = guard.decide(
        'git commit -m "x" -m "\U0001f916 Generated with [Claude Code](https://claude.com/claude-code)"',
        repo,
        NO_SCANNER,
    )
    assert decision.permission == "deny" and "ATTR-1" in decision.rules


def test_command_v_is_not_a_wrapper():
    parsed = command_mod.parse("command -v git")
    assert parsed.commands[0].kind == "other"


@pytest.mark.parametrize(
    "raw",
    [
        'cat "$(git push origin main)"',
        "echo `git push origin main`",
        "head -1 <(gh pr create --title x --body y)",
        "tail -f x > >(gh pr create --title t --body b)",
        "cat <<EOF\n`git push origin main`\nEOF",
        'echo "$(date) $(git commit -m x)"',
        "cat <<EOF\n'$(git push origin main)'\nEOF",
        "cat <<EOF\ndon't\n$(git push origin main)\nEOF",
        "echo hi # don't\necho $(git push origin main)",
        "echo it's $(git push origin main)",
        'echo "<<X"\ngit push origin main\nX',
    ],
)
def test_a_gated_command_inside_a_substitution_asks(repo: Path, raw: str):
    """The shell runs a substitution's body; a program that only prints its arguments does not
    make the body text."""
    decision = guard.decide(raw, repo, NO_SCANNER)
    assert decision.permission == "ask" and "TRACE-1" in decision.rules, raw


@pytest.mark.parametrize(
    "raw",
    [
        'rg -n "git push" docs',
        "grep -rn 'git commit' src | head -5",
        "printf '| git push origin main | RUN-1 |\\n' >> .agent/progress.md",
        "echo 'gh pr create' | wc -l",
        "cat >> .agent/progress.md <<'EOF'\n| `git push origin main` | RUN-1 |\nEOF",
        "cat >> .agent/progress.md <<EOF\n| git push origin main | held, don't retry |\nEOF",
        'echo "$(date) held: git push origin main" >> .agent/progress.md',
        'echo "$(gh pr view 12 --json title)"',
        'git log "$(git merge-base HEAD origin/main)"..HEAD',
    ],
)
def test_printing_or_searching_for_a_gated_command_is_not_a_call(repo: Path, raw: str):
    """A search for "git push", or a held call written into a run report, runs nothing."""
    assert guard.decide(raw, repo, NO_SCANNER).permission == "allow", raw


@pytest.mark.parametrize(
    "raw",
    [
        "echo 'git push origin main' | sh",
        "rg --pre ./x 'git push' .",
        "env -S 'git push origin main'",
        r"find . -name x -exec git push \;",
    ],
)
def test_text_that_reaches_a_runner_still_asks(repo: Path, raw: str):
    decision = guard.decide(raw, repo, NO_SCANNER)
    assert decision.permission == "ask" and "TRACE-1" in decision.rules, raw


def test_a_substituted_commit_message_is_not_a_hidden_call(repo: Path):
    decision = guard.decide('git commit -m "$(cat msg.txt)"', repo, NO_SCANNER)
    assert "TRACE-1" not in decision.rules


def test_a_here_string_is_not_a_heredoc(repo: Path):
    """``<<<`` reads no lines, so the line after it is a command, not a heredoc body."""
    decision = guard.decide("cat <<<x\ngit push origin main", repo, NO_SCANNER)
    assert decision.permission == "ask" and "ASK-2" in decision.rules
    assert command_mod.parse("tr a b <<<x").heredocs == []
