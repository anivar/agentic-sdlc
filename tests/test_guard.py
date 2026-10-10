from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from agentic_sdlc import config as config_mod
from agentic_sdlc import guard, registry
from tests.conftest import git

NO_GITLEAKS = config_mod.from_dict({"secrets": {"use_gitleaks": False}})


def test_every_rule_the_guard_cites_exists():
    ids = set(registry.by_id())
    assert set(guard.RULE_IDS) <= ids


def test_plain_commands_are_allowed(repo: Path):
    for raw in (
        "ls -la",
        "git status",
        "git diff --cached --stat",
        "git log --oneline",
        "gh pr view 1",
        "cargo test",
    ):
        assert guard.decide(raw, repo, NO_GITLEAKS).permission == "allow", raw


def test_add_all_is_denied(repo: Path):
    decision = guard.decide("git add -A", repo, NO_GITLEAKS)
    assert decision.permission == "deny" and decision.rules == ["STAGE-1"]


def test_commit_all_is_denied_before_it_is_asked(repo: Path):
    decision = guard.decide('git commit -am "x"', repo, NO_GITLEAKS)
    assert decision.permission == "deny" and "STAGE-1" in decision.rules


def test_commit_asks(repo: Path):
    decision = guard.decide('git commit -m "Fix parser"', repo, NO_GITLEAKS)
    assert decision.permission == "ask" and decision.rules == ["ASK-1"]
    assert "go-ahead" in decision.reason


def test_attribution_denies_over_ask(repo: Path):
    raw = 'git commit -m "Fix" -m "Co-Authored-By: Claude <noreply@anthropic.com>"'
    decision = guard.decide(raw, repo, NO_GITLEAKS)
    assert decision.permission == "deny"
    assert decision.rules[0] == "ATTR-1"
    assert "ASK-1" in decision.rules


def test_vendor_mention_in_commit_passes_by_default_and_fails_strict(repo: Path):
    raw = 'git commit -m "Add Claude Code plugin manifest"'
    assert guard.decide(raw, repo, NO_GITLEAKS).permission == "ask"
    strict = config_mod.from_dict(
        {"attribution": {"mode": "strict"}, "secrets": {"use_gitleaks": False}}
    )
    decision = guard.decide(raw, repo, strict)
    assert decision.permission == "deny" and "ATTR-2" in decision.rules


def test_pr_body_with_footer_is_denied(repo: Path):
    raw = 'gh pr create --title "x" --body "Does y\n\n\U0001f916 Generated with [Claude Code](https://claude.com/claude-code)"'
    decision = guard.decide(raw, repo, NO_GITLEAKS)
    assert decision.permission == "deny" and "ATTR-1" in decision.rules


def test_push_asks_and_force_to_protected_denies(repo: Path):
    assert guard.decide("git push origin main", repo, NO_GITLEAKS).permission == "ask"
    decision = guard.decide("git push --force origin main", repo, NO_GITLEAKS)
    assert decision.permission == "deny" and "PUSH-1" in decision.rules
    assert guard.decide("git push --force origin feature", repo, NO_GITLEAKS).permission == "ask"
    decision = guard.decide("git push origin :main", repo, NO_GITLEAKS)
    assert decision.permission == "deny"


def test_protected_branches_are_configurable(repo: Path):
    cfg = config_mod.from_dict(
        {"protected_branches": ["release"], "secrets": {"use_gitleaks": False}}
    )
    assert guard.decide("git push --force origin main", repo, cfg).permission == "ask"
    assert guard.decide("git push --force origin release", repo, cfg).permission == "deny"


def test_force_pushing_a_tag_asks_with_the_workflow_warning(repo: Path):
    decision = guard.decide("git push --force origin refs/tags/v1.0.0", repo, NO_GITLEAKS)
    assert decision.permission == "ask" and "PUSH-2" in decision.rules
    assert "runs again" in decision.reason


def test_posting_asks(repo: Path):
    decision = guard.decide('gh issue comment 5 --body "Looks fine"', repo, NO_GITLEAKS)
    assert decision.permission == "ask" and decision.rules == ["ASK-3"]


def test_confirmations_can_be_switched_off(repo: Path):
    cfg = config_mod.from_dict(
        {
            "confirm": {"commit": False, "push": False, "post": False},
            "secrets": {"use_gitleaks": False},
        }
    )
    assert guard.decide('git commit -m "x"', repo, cfg).permission == "allow"
    assert guard.decide("git push", repo, cfg).permission == "allow"
    assert guard.decide("gh pr comment 1 -b x", repo, cfg).permission == "allow"


def test_dry_runs_are_not_gated(repo: Path):
    assert (
        guard.decide("git push --dry-run --force origin main", repo, NO_GITLEAKS).permission
        == "allow"
    )
    assert guard.decide('git commit --dry-run -m "x"', repo, NO_GITLEAKS).permission == "allow"


def test_staged_secret_denies_the_commit(repo: Path):
    secret = repo / "config.py"
    secret.write_text("AWS_KEY = 'AKIA" + "ABCDEFGHIJKLMNOP'\n", encoding="utf-8")
    git(repo, "add", "config.py")
    decision = guard.decide('git commit -m "Add config"', repo, NO_GITLEAKS)
    assert decision.permission == "deny" and "SECRET-1" in decision.rules
    assert "AKIA" not in decision.reason


def test_clean_staged_change_only_asks(repo: Path):
    clean = repo / "notes.md"
    clean.write_text("password = os.environ['PASSWORD']\n", encoding="utf-8")
    git(repo, "add", "notes.md")
    assert guard.decide('git commit -m "Add notes"', repo, NO_GITLEAKS).permission == "ask"


@pytest.mark.skipif(shutil.which("gitleaks") is None, reason="gitleaks not installed")
def test_gitleaks_catches_what_the_patterns_miss(repo: Path):
    leak = repo / "settings.yml"
    leak.write_text(
        "slack_webhook: https://hooks.slack.com/services/T{0}/B{0}/{1}\n".format("0" * 8, "X" * 24),
        encoding="utf-8",
    )
    git(repo, "add", "settings.yml")
    decision = guard.decide('git commit -m "Add settings"', repo, config_mod.Config())
    assert decision.permission == "deny" and "SECRET-1" in decision.rules
    assert "XXXXXXXX" not in decision.reason


def test_config_problems_are_reported_not_fatal(repo: Path):
    cfg = config_mod.from_dict(
        {"attribution": {"mode": "loud"}, "unknown": 1, "secrets": {"use_gitleaks": False}}
    )
    assert cfg.problems
    decision = guard.decide('git commit -m "x"', repo, cfg)
    assert decision.permission == "ask" and "config:" in decision.reason


def test_looks_gated_pre_check():
    assert guard.looks_gated("git commit -m x")
    assert guard.looks_gated("gh pr merge 1")
    assert not guard.looks_gated("cargo build")
