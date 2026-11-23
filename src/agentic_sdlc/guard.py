"""The decision: given a command and a working directory, allow, ask or deny.

Precedence is deny over ask over allow. Every reason names the rule ids it rests on so the
agent and the user can look them up in ``rules/registry.json``, and carries the rule's fix
line when it has one.
"""

from __future__ import annotations

import fnmatch
import json
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    "RUN-1",
)

# The reason an unattended run gets in place of a prompt nobody would answer (RUN-1). It is read
# by the agent, so it says what to do next.
UNATTENDED_HELD = (
    "this run is unattended (whoever launched it set AGENTIC_SDLC_UNATTENDED), so nobody can give "
    "the go-ahead now and the call is refused. Nothing keeps it for later: do not retry it or work "
    "around it, carry on with the next step, and list it under held calls in the run report so a "
    "person can run it"
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


# Programs that print or search their arguments and never run them. A gated command named in
# their arguments is text, not a call, so TRACE-1 does not ask about it: a search for "git push",
# or a held call written into a run report. Narrower than UNTRACED_READ_ONLY, which holds env and
# find, both of which can run another program.
QUOTING_ONLY = {"echo", "printf", "cat", "head", "tail", "grep", "rg", "wc", "ls"}


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


@dataclass
class ShellText:
    """What the shell would run inside a command line, beyond its simple commands."""

    bodies: list[str] = field(default_factory=list)  # command and process substitutions
    heredocs: int = 0
    unreadable: bool = False  # an unclosed quote, substitution or here-string the scan cannot place


def _close_paren(text: str, open_at: int) -> int:
    """Index of the ``)`` that closes the ``(`` at ``open_at``, or -1."""
    depth, index = 0, open_at
    while index < len(text):
        ch = text[index]
        if ch == "\\":
            index += 2
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return -1


def _heredoc_substitutions(body: str, out: ShellText) -> None:
    """An unquoted heredoc body expands ``$( )`` and backticks; quotes in it are plain text."""
    index = 0
    while index < len(body):
        ch = body[index]
        if ch == "\\":
            index += 2
            continue
        if body.startswith("$(", index):
            close = _close_paren(body, index + 1)
            if close == -1:
                out.bodies.append(body[index + 2 :])
                out.unreadable = True
                return
            out.bodies.append(body[index + 2 : close])
            index = close + 1
            continue
        if ch == "`":
            close = body.find("`", index + 1)
            if close == -1:
                out.bodies.append(body[index + 1 :])
                out.unreadable = True
                return
            out.bodies.append(body[index + 1 : close])
            index = close + 1
            continue
        index += 1


def scan_shell(raw: str) -> ShellText:
    """Find what the shell would run inside ``raw``: the body of every command substitution
    (``$( )``, backticks) and process substitution (``<( )``, ``>( )``), including those in
    unquoted heredocs. Single-quoted text, quoted heredocs and ``#`` comments are skipped, as
    the shell skips them. Anything the scan cannot place marks the text unreadable."""
    out = ShellText()
    text, length = raw, len(raw)
    pending: list[tuple[str, bool, bool]] = []  # tag, quoted, strips tabs
    quote: str | None = None
    index = 0
    while index < length:
        ch = text[index]
        if quote == "'":
            if ch == "'":
                quote = None
            index += 1
            continue
        if ch == "\\":
            index += 2
            continue
        if quote is None and ch == "#" and (index == 0 or text[index - 1] in " \t\n;&|()"):
            newline = text.find("\n", index)
            index = length if newline == -1 else newline
            continue
        if ch == '"':
            quote = None if quote == '"' else '"'
            index += 1
            continue
        if quote is None and ch == "'":
            quote = "'"
            index += 1
            continue
        if quote is None and text.startswith("<<<", index):
            index += 3
            continue
        if quote is None and text.startswith("<<", index):
            match = command_mod.HEREDOC_RE.match(text, index)
            if match:
                pending.append(
                    (match.group("tag"), bool(match.group("q")), "<<-" in match.group(0))
                )
                index = match.end()
                continue
        if text.startswith("$(", index) or (quote is None and text.startswith(("<(", ">("), index)):
            close = _close_paren(text, index + 1)
            if close == -1:
                out.bodies.append(text[index + 2 :])
                out.unreadable = True
                return out
            out.bodies.append(text[index + 2 : close])
            index = close + 1
            continue
        if ch == "`":
            close = text.find("`", index + 1)
            if close == -1:
                out.bodies.append(text[index + 1 :])
                out.unreadable = True
                return out
            out.bodies.append(text[index + 1 : close])
            index = close + 1
            continue
        if ch == "\n" and quote is None and pending:
            index += 1
            for tag, quoted, strips_tabs in pending:
                out.heredocs += 1
                lines: list[str] = []
                while index < length:
                    newline = text.find("\n", index)
                    stop = length if newline == -1 else newline
                    line = text[index:stop]
                    index = length if newline == -1 else newline + 1
                    if (line.lstrip("\t") if strips_tabs else line) == tag:
                        break
                    lines.append(line)
                if not quoted:
                    _heredoc_substitutions("\n".join(lines), out)
            pending = []
            continue
        index += 1
    out.heredocs += len(pending)
    if quote is not None:
        out.unreadable = True
    return out


def _runs_gated(body: str) -> bool:
    """A substitution body that names a gated command and is not a traced read."""
    if not looks_gated(body):
        return False
    try:
        parsed = command_mod.parse(body)
    except Exception:  # noqa: BLE001 - a body the parser cannot read is confirmed, not trusted
        return True
    return parsed.gated or not parsed.traced


def _only_quoting(parsed: command_mod.Parsed, scan: ShellText) -> bool:
    """Every simple command only prints or searches its arguments, and the scan placed every
    quote and heredoc the way the parser did. ``rg --pre`` runs a program, so it does not count."""
    if scan.unreadable or scan.heredocs != len(parsed.heredocs):
        return False
    return bool(parsed.commands) and all(
        facts.program in QUOTING_ONLY
        and not (
            facts.program == "rg"
            and any(t == "--pre" or t.startswith("--pre=") for t in facts.tokens)
        )
        for facts in parsed.commands
    )


def decide(command: str, cwd: Path | None = None, cfg: config_mod.Config | None = None) -> Decision:
    cfg = cfg or config_mod.Config()
    titles = registry.titles()
    fixes = registry.fixes()
    decision = Decision()
    parsed = command_mod.parse(command, cwd, cfg.extra_posting_commands)
    today = datetime.now(timezone.utc).date()
    quiet = {q["rule"]: q["until"] for q in cfg.quiet_rules if q["until"] >= today}

    def quiet_note(rule: str) -> bool:
        """True when a quiet rule covers this ask; the suppression is noted for the record."""
        until = quiet.get(rule)
        if until is None:
            return False
        decision.reasons.append(f"{rule}: suppressed by confirm.quiet_rules until {until}")
        return True

    def add(permission: str, rule: str, reason: str) -> None:
        if permission == "ask" and quiet_note(rule):
            return
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
        if config_mod.UNATTENDED_ENV in facts.sets_variables:
            # The agent's own decision: recorded, never asked about or refused.
            add(
                "allow",
                "RUN-4",
                f"the command sets {config_mod.UNATTENDED_ENV} and starts an unattended run",
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

    scan = scan_shell(command)
    if any(_runs_gated(body) for body in scan.bodies):
        add(
            "ask",
            "TRACE-1",
            "the command runs a commit, push or forge write inside a substitution the parser does not trace; confirm it yourself",
        )
    elif (
        looks_gated(command)
        and not parsed.gated
        and not parsed.traced
        and not _only_quoting(parsed, scan)
    ):
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
        checkpoint = cfg.unattended and facts.is_commit
        if facts.carries_text and facts.text_by_substitution and not checkpoint:
            rule = "ASK-1" if facts.is_commit else "ASK-3"
            if not quiet_note(rule):
                decision.add(
                    "ask",
                    rule,
                    "message text built by a shell substitution is not scanned here; the check after the commit and the pull request check cover it",
                )
        if facts.carries_text and facts.text_file_missing and not checkpoint:
            rule = "ASK-1" if facts.is_commit else "ASK-3"
            if not quiet_note(rule):
                decision.add(
                    "ask",
                    rule,
                    "a message file the command names does not exist yet, so only the command text was scanned; the check after the commit covers the rest",
                )
        if facts.is_commit and not facts.dry_run and cfg.unattended:
            # An unattended run checkpoints with commits, but only on a working branch.
            branch = command_mod.current_branch(facts.workdir or cwd)
            if branch is None or branch in cfg.protected_branches:
                add(
                    "deny",
                    "RUN-1",
                    f"a commit in an unattended run would land on {branch or 'a detached HEAD'}; "
                    "commit on a working branch",
                )
        elif facts.is_commit and not facts.dry_run and cfg.confirm_commit:
            # slice scope: only the commit that would start the unpushed slice asks; the push
            # and the post are the slice boundary and ask unchanged.
            continuing = cfg.confirm_scope == "slice" and not first_unpushed(facts.workdir or cwd)
            if not continuing:
                what = "amend" if facts.amend else "commit"
                add("ask", "ASK-1", f"{what} needs your go-ahead")
        if (
            facts.is_push
            and not facts.dry_run
            and cfg.confirm_push
            and not (cfg.unattended and agent_branch_push(facts, cfg))
        ):
            where = (
                ", ".join(facts.targets)
                if facts.targets
                else ("tags" if facts.tags_pushed else "remote")
            )
            add("ask", "ASK-2", f"push to {where} needs your go-ahead")
        if facts.post and cfg.confirm_post:
            add("ask", "ASK-3", f"{facts.post_reason} publishes or changes something on the forge")
        if facts.unrecognized_verb:
            add(
                "ask",
                "ASK-3",
                f"{facts.post_reason} is not a subcommand the hook recognizes; review it yourself",
            )

    apply_mode(decision, cfg, titles, fixes)
    if cfg.problems:
        decision.reasons.append("config: " + "; ".join(cfg.problems))
    return decision


def agent_branch_push(facts: command_mod.Facts, cfg: config_mod.Config) -> bool:
    """True when an unattended run may push this without a go-ahead (RUN-1): every target is a
    named branch that matches unattended.push_branches and is not protected, with no force, no
    tags, no deletion and no mirror."""
    if not cfg.unattended_push or not facts.targets:
        return False
    if facts.force or facts.tags_pushed or facts.deletes or facts.mirror:
        return False
    protected = set(cfg.protected_branches)
    for target in facts.targets:
        if target in protected or target in ("*", "HEAD"):
            return False
        if not any(fnmatch.fnmatchcase(target, pattern) for pattern in cfg.unattended_push):
            return False
    return True


def apply_mode(
    decision: Decision, cfg: config_mod.Config, titles: dict[str, str], fixes: dict[str, str]
) -> None:
    """Settle who answers an ask. In agent mode, the default, the agent decides: the call is
    allowed and AGENT-1 is recorded beside the rule that asked. In confirm mode a person answers,
    and in an unattended run nobody can, so the ask is refused (RUN-1). A refusal stays a refusal."""
    if decision.permission != "ask":
        return
    if cfg.agent_decides:
        decision.permission = "allow"
        title = titles.get("AGENT-1", "AGENT-1")
        decision.add("allow", "AGENT-1", f"{title}: recorded, not asked")
    elif cfg.unattended:
        hold_for_unattended(decision, titles, fixes)


def hold_for_unattended(decision: Decision, titles: dict[str, str], fixes: dict[str, str]) -> None:
    """Nobody can answer an ask in an unattended run, and an ask there would stop the run at a
    prompt. Turn it into a refusal the agent can act on (RUN-1)."""
    if decision.permission == "ask":
        title = titles.get("RUN-1", "RUN-1")
        decision.add("deny", "RUN-1", f"{title}: {UNATTENDED_HELD}", fixes.get("RUN-1", ""))


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
    apply_mode(decision, cfg, titles, fixes)
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


def first_unpushed(cwd: Path | None) -> bool:
    """True when a commit now would be the branch's first unpushed commit (every commit on
    HEAD is already on a remote), or when git cannot say. The doubt fails closed, so the
    commit asks rather than slipping through."""
    if cwd is None:
        return True
    try:
        remotes = subprocess.run(
            ["git", "-C", str(cwd), "remote"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if remotes.returncode != 0 or not remotes.stdout.strip():
            return True  # no remote to diff against: the safe answer is to ask
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-list", "HEAD", "--not", "--remotes", "--count"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return True
    if result.returncode != 0 or not result.stdout.strip().isdigit():
        return True
    return int(result.stdout.strip()) == 0


def head_sha(cwd: Path) -> str | None:
    """The sha of the commit at HEAD, or None when there is no HEAD (an unborn branch) or
    git cannot answer."""
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    sha = result.stdout.strip()
    return sha if result.returncode == 0 and sha else None


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
