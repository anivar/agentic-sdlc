"""The decision: given a command and a working directory, allow, ask or deny.

Precedence is deny over ask over allow. Every reason names the rule ids it rests on so the
agent and the user can look them up in ``rules/registry.json``, and carries the rule's fix
line when it has one.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
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
    "SECRET-3",
    "ASK-1",
    "ASK-2",
    "ASK-3",
    "TRACE-1",
    "TRACE-2",
    "GUARD-1",
    "GUARD-2",
)

TRUFFLEHOG_FOUND = 183  # TruffleHog's exit code for results with --fail

GATED_HINT_RE = re.compile(
    r"\bgit\s+(?:-C\s+\S+\s+)?(?:commit|push|tag)\b"
    r"|\bgit\s+(?:-C\s+\S+\s+)?add\s+(?:-A\b|--all\b|\.(?:\s|$))"
    r"|\bgh\s+(?:pr|issue|release|api|repo|label|workflow|run|gist|secret|variable|project)\b"
    r"|\bglab\s+(?:mr|issue|release|api|repo|label|ci|variable)\b"
    # Interpreter evasion: an inline script whose text runs git, with the verb spelled out or
    # split into separate arguments ("git", "push"). Scoped to a -c/-e flag so an interpreter
    # call that never names git stays out.
    r"|\b(?:python3?|node|ruby|perl)\b(?:\s+-[^\s]*[ce][^\s]*)+\s+[^\n]*\bgit\b[\s'\",]+(?:push|commit|add)\b",
    re.IGNORECASE,
)

# Files whose edit changes what the guard does (GUARD-2), matched on the path's tail.
GUARD_CONFIG_RE = re.compile(
    r"(^|/)(\.agentic-sdlc\.json|\.pre-commit-config\.yaml|\.claude/settings(\.local)?\.json"
    r"|\.git/hooks/[^/]+|hooks/hooks\.json)$"
)

# Programs an untraced command may be made of and still pass TRACE-2: they only read or print.
# Anything else the parser cannot trace is unknown, and unknown means suspicious.
UNTRACED_READ_ONLY = {
    "ls",
    "pwd",
    "echo",
    "cat",
    "head",
    "tail",
    "grep",
    "find",
    "wc",
    "sort",
    "uniq",
    "which",
    "env",
    "date",
    "uname",
    "true",
    "test",
    "printf",
}


@dataclass
class Decision:
    permission: str = "allow"
    rules: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def add(self, permission: str, rule: str, reason: str, fix: str = "") -> None:
        if rule not in self.rules:
            self.rules.append(rule)
        line = f"{rule}: {reason}"
        if fix:
            line += f". Fix: {fix}"
        self.reasons.append(line)
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


def _only_read_only(parsed: command_mod.Parsed) -> bool:
    """Every simple command is one of the read-only programs in ``UNTRACED_READ_ONLY``."""
    return bool(parsed.commands) and all(
        facts.program in UNTRACED_READ_ONLY for facts in parsed.commands
    )


def decide(command: str, cwd: Path | None = None, cfg: config_mod.Config | None = None) -> Decision:
    cfg = cfg or config_mod.Config()
    titles = registry.titles()
    fixes = registry.fixes()
    decision = Decision()
    parsed = command_mod.parse(command, cwd, cfg.extra_posting_commands)

    def add(permission: str, rule: str, reason: str) -> None:
        decision.add(permission, rule, f"{titles.get(rule, rule)}: {reason}", fixes.get(rule, ""))

    for facts in parsed.commands:
        if facts.kind == "git-add" and facts.add_all and cfg.deny_add_all:
            add("deny", "STAGE-1", "stage named paths, then check git diff --cached --stat")
        if facts.is_commit and facts.commit_all and cfg.deny_commit_all:
            add(
                "deny",
                "STAGE-1",
                "git commit -a stages every tracked change; stage by path instead",
            )
        if (facts.is_commit or facts.is_push) and facts.no_verify:
            add("deny", "GUARD-1", "--no-verify skips the repository's hooks")
        if facts.hooks_path_override:
            add(
                "deny", "GUARD-1", "a -c override of hooks, includes or aliases on the command line"
            )
        if facts.kind == "read" and facts.reads_secret_file:
            names = ", ".join(facts.reads_secret_file[:3])
            add("ask", "SECRET-3", f"{names} holds credentials by name")
        if facts.is_push and not facts.dry_run:
            protected = set(cfg.protected_branches)
            hit = [t for t in facts.targets if t in protected or t == "*"]
            if facts.force and hit:
                names = ", ".join(sorted(hit))
                add(
                    "deny",
                    "PUSH-1",
                    f"force push to {names}; a protected branch moves by merged pull request",
                )
            deleted = [d for d in facts.deletes if d in protected]
            if deleted:
                add("deny", "PUSH-1", f"deleting {', '.join(deleted)}")
            if facts.force_tags:
                add(
                    "ask",
                    "PUSH-2",
                    "every workflow triggered on tag pushes runs again at the moved tag, and release assets may be rebuilt",
                )

    carried = command_mod.carried_text(parsed, cwd)
    if carried:
        for finding in text.attribution_findings(carried, cfg):
            add("deny", finding.rule, f"{finding.name} ({finding.excerpt})")

    if cfg.scan_staged:
        scanned: set[Path] = set()
        for facts in parsed.commands:
            where = facts.workdir or cwd
            if not (facts.is_commit and not facts.dry_run) or where is None or where in scanned:
                continue
            scanned.add(where)
            for finding in staged_secret_findings(where, cfg):
                add("deny", "SECRET-1", f"{finding.name} at staged line {finding.line}")

    if looks_gated(command) and not parsed.gated and not parsed.traced:
        add(
            "ask",
            "TRACE-1",
            "the command mentions a commit, push or forge write that the parser could not trace; confirm it yourself",
        )

    if cfg.trace_untracked != "allow" and not parsed.traced and not _only_read_only(parsed):
        add(
            cfg.trace_untracked,
            "TRACE-2",
            "the parser could not trace this command to a git, gh or glab invocation; an untraced command is suspicious under trace.untracked",
        )

    for facts in parsed.commands:
        if facts.carries_text and facts.text_by_substitution:
            decision.add(
                "ask",
                "ASK-1" if facts.is_commit else "ASK-3",
                "message text built by a shell substitution is not scanned here; the check after the commit and the pull request check cover it",
            )
        if facts.carries_text and facts.text_file_missing:
            decision.add(
                "ask",
                "ASK-1" if facts.is_commit else "ASK-3",
                "a message file the command names does not exist yet, so only the command text was scanned; the check after the commit covers the rest",
            )
        if facts.is_commit and not facts.dry_run and cfg.confirm_commit:
            what = "amend" if facts.amend else "commit"
            add("ask", "ASK-1", f"{what} needs your go-ahead")
        if facts.is_push and not facts.dry_run and cfg.confirm_push:
            where = (
                ", ".join(facts.targets)
                if facts.targets
                else ("tags" if facts.tags_pushed else "remote")
            )
            add("ask", "ASK-2", f"push to {where} needs your go-ahead")
        if facts.post and cfg.confirm_post:
            add("ask", "ASK-3", f"{facts.post_reason} publishes or changes something on the forge")

    if cfg.problems:
        decision.reasons.append("config: " + "; ".join(cfg.problems))
    return decision


def decide_file(
    tool: str, path: str, cwd: Path | None = None, cfg: config_mod.Config | None = None
) -> Decision:
    """Decisions for the file tools: a secret file read (SECRET-3) and an edit of the guard's
    own configuration (GUARD-2) ask; everything else is allowed."""
    cfg = cfg or config_mod.Config()
    titles = registry.titles()
    fixes = registry.fixes()
    decision = Decision()
    if not path:
        return decision
    reads = tool in ("Read", "Grep")
    writes = tool in ("Edit", "Write", "MultiEdit", "NotebookEdit")
    if reads and command_mod.is_secret_file(path):
        decision.add(
            "ask",
            "SECRET-3",
            f"{titles.get('SECRET-3', 'SECRET-3')}: {path} holds credentials by name",
            fixes.get("SECRET-3", ""),
        )
    if writes and GUARD_CONFIG_RE.search(path.replace("\\", "/")):
        decision.add(
            "ask",
            "GUARD-2",
            f"{titles.get('GUARD-2', 'GUARD-2')}: {path} changes what the guard does",
            fixes.get("GUARD-2", ""),
        )
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
    added = text.added_lines(staged_diff(cwd))
    findings = text.secret_findings(added, cfg.extra_secret_patterns)
    if cfg.scanner == "trufflehog" and not findings:
        external = trufflehog_scan(added)
        if external:
            findings.append(text.Finding("SECRET-1", external, 0, "value withheld"))
    return findings


def trufflehog_scan(added: str) -> str | None:
    """A one-line description when TruffleHog's detectors match the lines a staged change adds;
    None when clean or when the binary is absent. Only added lines are scanned, so removing a
    leaked key is never blocked. The text goes to ``trufflehog stdin`` with verification and the
    update check off, so the scan makes no network call and a candidate is never tried against
    a provider from a hook."""
    binary = shutil.which("trufflehog")
    if not binary or not added.strip():
        return None
    try:
        result = subprocess.run(
            [
                binary,
                "stdin",
                "--no-verification",
                "--results=unverified",
                "--json",
                "--no-update",
                "--fail",
                "--log-level=-1",
            ],
            input=added,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != TRUFFLEHOG_FOUND:
        return None
    detectors: list[str] = []
    for line in result.stdout.splitlines():
        if not line.startswith("{"):
            continue
        try:
            name = json.loads(line).get("DetectorName")
        except ValueError:
            continue
        if isinstance(name, str) and name not in detectors:
            detectors.append(name)
    named = ", ".join(detectors[:3]) if detectors else "a credential"
    return f"trufflehog: {named} detected in the staged changes"


def head_age_seconds(cwd: Path) -> float | None:
    """Seconds since the commit at HEAD was made, or None when there is no HEAD."""
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "log", "-1", "--format=%ct"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 or not result.stdout.strip().isdigit():
        return None
    return max(0.0, time.time() - int(result.stdout.strip()))


def head_message(cwd: Path) -> str:
    """The message of the commit at HEAD, for the check after a commit ran."""
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "log", "-1", "--format=%B"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout if result.returncode == 0 else ""
