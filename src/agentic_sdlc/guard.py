"""The decision: given a command and a working directory, allow, ask or deny.

Precedence is deny over ask over allow. Every reason names the rule ids it rests on so the
agent and the user can look them up in ``rules/registry.json``.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import command as command_mod
from . import config as config_mod
from . import registry, text

RULE_IDS = (
    "ATTR-1",
    "ATTR-2",
    "STAGE-1",
    "PUSH-1",
    "PUSH-2",
    "SECRET-1",
    "ASK-1",
    "ASK-2",
    "ASK-3",
    "TRACE-1",
)

GATED_HINT_RE = re.compile(
    r"\bgit\s+(?:-C\s+\S+\s+)?(?:commit|push|tag)\b"
    r"|\bgit\s+(?:-C\s+\S+\s+)?add\s+(?:-A\b|--all\b|\.(?:\s|$))"
    r"|\bgh\s+(?:pr|issue|release|api|repo|label|workflow|run|gist|secret|variable|project)\b"
    r"|\bglab\s+(?:mr|issue|release|api|repo|label|ci|variable)\b",
    re.IGNORECASE,
)


@dataclass
class Decision:
    permission: str = "allow"
    rules: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def add(self, permission: str, rule: str, reason: str) -> None:
        if rule not in self.rules:
            self.rules.append(rule)
        self.reasons.append(f"{rule}: {reason}")
        rank = {"allow": 0, "ask": 1, "deny": 2}
        if rank[permission] > rank[self.permission]:
            self.permission = permission

    @property
    def reason(self) -> str:
        return " | ".join(self.reasons)


def looks_gated(command: str) -> bool:
    """A cheap textual pre-check: the command mentions a commit, push, bulk add or forge write.
    Used to fail closed when analysis crashes, and to ask when the parser could not trace one."""
    return GATED_HINT_RE.search(command) is not None


def decide(command: str, cwd: Path | None = None, cfg: config_mod.Config | None = None) -> Decision:
    cfg = cfg or config_mod.Config()
    titles = registry.titles()
    decision = Decision()
    parsed = command_mod.parse(command, cwd, cfg.extra_posting_commands)

    def title(rule: str) -> str:
        return titles.get(rule, rule)

    for facts in parsed.commands:
        if facts.kind == "git-add" and facts.add_all and cfg.deny_add_all:
            decision.add(
                "deny",
                "STAGE-1",
                f"{title('STAGE-1')}: stage named paths, then check git diff --cached --stat",
            )
        if facts.is_commit and facts.commit_all and cfg.deny_commit_all:
            decision.add(
                "deny",
                "STAGE-1",
                f"{title('STAGE-1')}: git commit -a stages every tracked change; stage by path instead",
            )
        if facts.is_push and not facts.dry_run:
            protected = set(cfg.protected_branches)
            hit = [t for t in facts.targets if t in protected or t == "*"]
            if facts.force and hit:
                names = ", ".join(sorted(hit))
                decision.add(
                    "deny",
                    "PUSH-1",
                    f"{title('PUSH-1')}: force push to {names}; a protected branch moves by merged pull request",
                )
            deleted = [d for d in facts.deletes if d in protected]
            if deleted:
                decision.add("deny", "PUSH-1", f"{title('PUSH-1')}: deleting {', '.join(deleted)}")
            if facts.force_tags:
                decision.add(
                    "ask",
                    "PUSH-2",
                    f"{title('PUSH-2')}: every workflow triggered on tag pushes runs again at the moved tag, and release assets may be rebuilt",
                )

    carried = command_mod.carried_text(parsed, cwd)
    if carried:
        for finding in text.attribution_findings(carried, cfg):
            decision.add(
                "deny", finding.rule, f"{title(finding.rule)}: {finding.name} ({finding.excerpt})"
            )

    if cfg.scan_staged:
        scanned: set[Path] = set()
        for facts in parsed.commands:
            where = facts.workdir or cwd
            if not (facts.is_commit and not facts.dry_run) or where is None or where in scanned:
                continue
            scanned.add(where)
            for finding in staged_secret_findings(where, cfg):
                decision.add(
                    "deny",
                    "SECRET-1",
                    f"{title('SECRET-1')}: {finding.name} at staged line {finding.line}",
                )

    if looks_gated(command) and not parsed.gated and not parsed.traced:
        decision.add(
            "ask",
            "TRACE-1",
            f"{title('TRACE-1')}: the command mentions a commit, push or forge write that the parser could not trace; confirm it yourself",
        )

    for facts in parsed.commands:
        if facts.carries_text and facts.text_by_substitution:
            decision.add(
                "ask",
                "ASK-1" if facts.is_commit else "ASK-3",
                "message text built by a shell substitution is not scanned here; the pull request check covers it",
            )
        if facts.is_commit and not facts.dry_run and cfg.confirm_commit:
            what = "amend" if facts.amend else "commit"
            decision.add("ask", "ASK-1", f"{title('ASK-1')}: {what} needs your go-ahead")
        if facts.is_push and not facts.dry_run and cfg.confirm_push:
            where = (
                ", ".join(facts.targets)
                if facts.targets
                else ("tags" if facts.tags_pushed else "remote")
            )
            decision.add("ask", "ASK-2", f"{title('ASK-2')}: push to {where} needs your go-ahead")
        if facts.post and cfg.confirm_post:
            decision.add(
                "ask",
                "ASK-3",
                f"{title('ASK-3')}: {facts.post_reason} publishes or changes something on the forge",
            )

    if cfg.problems:
        decision.reasons.append("config: " + "; ".join(cfg.problems))
    return decision


def staged_diff(cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "diff", "--cached", "-U0", "--no-color", "--no-ext-diff"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout if result.returncode == 0 else ""


def staged_secret_findings(cwd: Path, cfg: config_mod.Config) -> list[text.Finding]:
    findings = text.secret_findings(text.added_lines(staged_diff(cwd)), cfg.extra_secret_patterns)
    if cfg.use_gitleaks and not findings:
        gitleaks = gitleaks_staged(cwd)
        if gitleaks:
            findings.append(text.Finding("SECRET-1", gitleaks, 0, "value withheld"))
    return findings


def gitleaks_staged(cwd: Path) -> str | None:
    """A one-line description when gitleaks finds a staged secret; None when clean or absent."""
    binary = shutil.which("gitleaks")
    if not binary:
        return None
    try:
        result = subprocess.run(
            [binary, "git", "--staged", "--no-banner", "--redact", "--exit-code", "1", str(cwd)],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode == 1:
        summary = [
            line.strip()
            for line in (result.stderr + result.stdout).splitlines()
            if "leaks found" in line.lower()
        ]
        return "gitleaks: " + (summary[-1] if summary else "staged secret found")
    return None
