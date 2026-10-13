"""Command-line entry points used by CI, by the repository's own gate and by hand.

agentic-sdlc guard 'git add -A'           decide as the hook would
agentic-sdlc check-text [--strict]        attribution findings over stdin or files
agentic-sdlc check-pr --event $GITHUB_EVENT_PATH
agentic-sdlc lint-voice README.md docs    the mechanical plain-voice rules
agentic-sdlc check-skills                 skill frontmatter, rule citations, attribution, forbidden tokens
agentic-sdlc validate                     the registry and the repository config
agentic-sdlc coverage [--check]           docs/coverage.md from the registry
agentic-sdlc hooks install|status|uninstall native git hooks for any agent
agentic-sdlc log [--last N] [--summary]   the decisions the hook recorded here
agentic-sdlc check-mr [--strict]          GitLab CI: title, description and commits of the MR
agentic-sdlc bench                        how long a decision takes
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent
if __name__ == "__main__" and str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))

from agentic_sdlc import (  # noqa: E402
    __version__,  # noqa: E402
    guard,
    record,
    registry,
    text,
)
from agentic_sdlc import config as config_mod  # noqa: E402

TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".rst"}
SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".ruff_cache",
    ".pytest_cache",
    "dist",
    "build",
}
FORBIDDEN_FILE = ".agentic-sdlc-forbidden.txt"
RULE_ID_RE = re.compile(r"\b([A-Z]{2,}-[0-9]+)\b")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
SKILL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    return int(args.func(args))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentic-sdlc",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"agentic-sdlc {__version__}")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("guard", help="decide a shell command as the hook would")
    p.add_argument("shell_command", help="the command string, quoted")
    p.add_argument("--cwd", default=".", help="working directory the command would run in")
    p.add_argument("--json", action="store_true", help="print the hook JSON instead of a summary")
    p.set_defaults(func=cmd_guard)

    p = sub.add_parser("check-text", help="attribution findings over text (stdin or files)")
    p.add_argument("paths", nargs="*", help="files to check; stdin when empty")
    p.add_argument("--strict", action="store_true", help="also refuse any vendor mention (ATTR-2)")
    p.add_argument("--vendor", action="append", default=[], help="extra vendor name; repeatable")
    p.add_argument(
        "--secrets", action="store_true", help="also report key-shaped literals (SECRET-1)"
    )
    p.set_defaults(func=cmd_check_text)

    p = sub.add_parser("check-pr", help="scan a pull request's title, body and commits")
    p.add_argument("--event", help="path to the GitHub event payload (GITHUB_EVENT_PATH)")
    p.add_argument("--repo", help="owner/name; defaults to the event's repository")
    p.add_argument("--pr", type=int, help="pull request number; defaults to the event's")
    p.add_argument("--title", help="offline: the title to check")
    p.add_argument("--body", help="offline: the body to check")
    p.add_argument(
        "--commits-file",
        help="offline: a file with one commit message per block separated by a line of ---",
    )
    p.add_argument("--strict", action="store_true", help="refuse any vendor mention (ATTR-2)")
    p.add_argument(
        "--require-signoff",
        action="store_true",
        help="every commit carries a Signed-off-by trailer",
    )
    p.add_argument("--config-dir", default=".", help="directory holding .agentic-sdlc.json")
    p.set_defaults(func=cmd_check_pr)

    p = sub.add_parser(
        "lint-voice", help="the mechanical plain-voice rules over markdown and text files"
    )
    p.add_argument("paths", nargs="+", help="files or directories")
    p.add_argument(
        "--fail-on",
        choices=["fail", "warn", "none"],
        default="fail",
        help="lowest level that fails the run",
    )
    p.set_defaults(func=cmd_lint_voice)

    p = sub.add_parser("check-skills", help="validate skills/*/SKILL.md and the tree")
    p.add_argument("--root", default=".", help="repository root")
    p.add_argument(
        "--forbidden-file", help="file with one forbidden token per line (kept out of the tree)"
    )
    p.set_defaults(func=cmd_check_skills)

    p = sub.add_parser("validate", help="validate rules/registry.json and .agentic-sdlc.json")
    p.add_argument("--root", default=".", help="repository root")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("coverage", help="write docs/coverage.md from the registry")
    p.add_argument("--root", default=".", help="repository root")
    p.add_argument("--check", action="store_true", help="fail when the file on disk is stale")
    p.set_defaults(func=cmd_coverage)

    p = sub.add_parser(
        "check-commit-msg", help="git commit-msg hook: refuse attribution in the message file"
    )
    p.add_argument("message_file")
    p.add_argument("--config-dir", default=".", help="directory holding .agentic-sdlc.json")
    p.set_defaults(func=cmd_check_commit_msg)

    p = sub.add_parser(
        "check-staged", help="git pre-commit hook: refuse key-shaped literals in the index"
    )
    p.add_argument("--config-dir", default=".", help="repository directory")
    p.set_defaults(func=cmd_check_staged)

    p = sub.add_parser(
        "check-push",
        help="git pre-push hook: refuse a non-fast-forward or deleting push to a protected branch (reads the ref lines git passes on stdin)",
    )
    p.add_argument("remote_name", nargs="?", default="")
    p.add_argument("remote_url", nargs="?", default="")
    p.add_argument("--config-dir", default=".", help="repository directory")
    p.set_defaults(func=cmd_check_push)

    p = sub.add_parser(
        "hooks", help="install or remove the native git hooks that call these checks"
    )
    p.add_argument("action", choices=["install", "uninstall", "status"])
    p.add_argument("--dir", default=".", help="repository directory")
    p.add_argument("--force", action="store_true", help="replace a hook this tool did not write")
    p.set_defaults(func=cmd_hooks)

    p = sub.add_parser("log", help="print the decisions the hook recorded for this repository")
    p.add_argument("--dir", default=".", help="repository directory")
    p.add_argument("--last", type=int, default=20, help="how many recent decisions to print")
    p.add_argument(
        "--summary",
        action="store_true",
        help="aggregate the whole record: counts by decision, per rule and by kind",
    )
    p.set_defaults(func=cmd_log)

    p = sub.add_parser(
        "check-mr",
        help="GitLab CI: scan the merge request title, description and commits (CI_MERGE_REQUEST_* variables)",
    )
    p.add_argument("--strict", action="store_true", help="refuse any vendor mention (ATTR-2)")
    p.add_argument(
        "--require-signoff",
        action="store_true",
        help="every commit carries a Signed-off-by trailer",
    )
    p.add_argument("--config-dir", default=".", help="repository directory")
    p.set_defaults(func=cmd_check_mr)

    p = sub.add_parser("bench", help="time the decision on a set of commands")
    p.add_argument("--iterations", type=int, default=50)
    p.add_argument("--cwd", default=".")
    p.set_defaults(func=cmd_bench)
    return parser


# guard -------------------------------------------------------------------------------------


def cmd_guard(args: argparse.Namespace) -> int:
    cwd = Path(args.cwd).resolve()
    cfg = config_mod.load(cwd)
    decision = guard.decide(args.shell_command, cwd, cfg)
    if args.json:
        payload = {
            "permission": decision.permission,
            "rules": decision.rules,
            "reason": decision.reason,
        }
        print(json.dumps(payload, indent=2))
    else:
        print(f"{decision.permission}: {', '.join(decision.rules) or 'no rule matched'}")
        for reason in decision.reasons:
            print(f"  {reason}")
    return 1 if decision.permission == "deny" else 0


# check-text ----------------------------------------------------------------------------------


def cmd_check_text(args: argparse.Namespace) -> int:
    cfg = config_mod.from_dict(
        {"attribution": {"mode": "strict" if args.strict else "patterns", "vendors": args.vendor}}
    )
    sources: list[tuple[str, str]] = []
    if args.paths:
        for name in args.paths:
            sources.append((name, Path(name).read_text(encoding="utf-8", errors="replace")))
    else:
        sources.append(("<stdin>", sys.stdin.read()))
    count = 0
    for name, body in sources:
        findings = text.attribution_findings(body, cfg)
        if args.secrets:
            findings += text.secret_findings(body)
        for finding in findings:
            count += 1
            print(f"{name}:{finding.line}: {finding.describe()}")
    return 1 if count else 0


# check-pr ------------------------------------------------------------------------------------


def cmd_check_pr(args: argparse.Namespace) -> int:
    cfg = config_mod.load(Path(args.config_dir).resolve())
    if args.strict:
        cfg.attribution_mode = "strict"
    title, body, number, repo = args.title or "", args.body or "", args.pr, args.repo
    if args.event:
        event = json.loads(Path(args.event).read_text(encoding="utf-8"))
        pull = event.get("pull_request") or {}
        title = title or pull.get("title") or ""
        body = body or pull.get("body") or ""
        number = number or pull.get("number")
        repo = repo or (event.get("repository") or {}).get("full_name")
    commits: list[tuple[str, str]] = []
    if args.commits_file:
        blocks = Path(args.commits_file).read_text(encoding="utf-8").split("\n---\n")
        commits = [
            (f"commit {i}", block.strip())
            for i, block in enumerate(blocks, start=1)
            if block.strip()
        ]
    elif number and repo:
        commits = fetch_pr_commits(repo, number)
    problems = scan_change_texts(
        [("title", title), ("body", body), *commits], cfg, args.require_signoff, annotate
    )
    if cfg.problems:
        annotate("warning", "CONFIG", "; ".join(cfg.problems))
    print(f"check-pr: {len(commits)} commit(s), {problems} problem(s)")
    return 1 if problems else 0


SIGNOFF_RE = re.compile(r"^Signed-off-by: .+", re.M)


def scan_change_texts(
    items: list[tuple[str, str]],
    cfg: config_mod.Config,
    require_signoff: bool,
    report: Callable[[str, str, str], None],
) -> int:
    """Attribution findings over (label, text) pairs, plus the sign-off check on commits.
    ``report(level, title, message)`` renders one problem; the count comes back."""
    problems = 0
    for label, content in items:
        for finding in text.attribution_findings(content, cfg):
            problems += 1
            report("error", finding.rule, f"{label}: {finding.name}: {finding.excerpt}")
        if require_signoff and label.startswith("commit") and not SIGNOFF_RE.search(content):
            problems += 1
            report("error", "SIGNOFF", f"{label}: no Signed-off-by trailer")
    return problems


def plain_report(level: str, title: str, message: str) -> None:
    print(f"{level.upper()} {title} {message}")


def fetch_pr_commits(repo: str, number: int) -> list[tuple[str, str]]:
    """Commit messages of a pull request through the gh CLI (GH_TOKEN in CI)."""
    result = subprocess.run(
        [
            "gh",
            "api",
            "--paginate",
            f"repos/{repo}/pulls/{number}/commits",
            "--jq",
            ".[] | [.sha, .commit.message] | @json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        annotate("warning", "FETCH", f"could not list commits: {result.stderr.strip()[:200]}")
        return []
    out: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        try:
            sha, message = json.loads(line)
        except ValueError:
            continue
        out.append((f"commit {sha[:7]}", message))
    return out


def annotate(level: str, title: str, message: str) -> None:
    clean = message.replace("\n", " ").replace("\r", "")
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::{level} title={title}::{clean}")
    else:
        print(f"{level}: {title}: {clean}")


# lint-voice ----------------------------------------------------------------------------------


def iter_text_files(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for name in paths:
        path = Path(name)
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                if (
                    child.is_file()
                    and child.suffix.lower() in TEXT_SUFFIXES
                    and not (SKIP_DIRS & set(child.parts))
                ):
                    out.append(child)
        elif path.is_file():
            out.append(path)
    return out


def cmd_lint_voice(args: argparse.Namespace) -> int:
    threshold = {"fail": 2, "warn": 1, "none": 3}[args.fail_on]
    levels = {"warn": 1, "fail": 2}
    failing = 0
    for path in iter_text_files(args.paths):
        body = path.read_text(encoding="utf-8", errors="replace")
        for finding in text.voice_findings(body):
            level = text.voice_level(finding)
            print(f"{path}:{finding.line}: {finding.describe()}")
            if levels[level] >= threshold:
                failing += 1
    return 1 if failing else 0


# check-skills --------------------------------------------------------------------------------


def parse_frontmatter(body: str) -> dict[str, str] | None:
    """A flat reading of the YAML frontmatter: top-level ``key: value`` pairs, folded scalars
    joined with spaces. Enough to validate without a YAML dependency."""
    match = FRONTMATTER_RE.match(body)
    if not match:
        return None
    fields: dict[str, str] = {}
    current: str | None = None
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        if line[0] in " \t":
            if current is not None:
                fields[current] = (fields[current] + " " + line.strip()).strip()
            continue
        key, sep, value = line.partition(":")
        if not sep:
            continue
        current = key.strip()
        value = value.strip()
        if value in (">", "|", ">-", "|-"):
            value = ""
        fields[current] = value.strip("\"'")
    return fields


def cmd_check_skills(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    problems: list[str] = []
    known = set(registry.by_id(root / "rules" / "registry.json"))
    skills_dir = root / "skills"
    names: set[str] = set()
    if skills_dir.is_dir():
        for folder in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
            names.add(folder.name)
            skill_file = folder / "SKILL.md"
            if not skill_file.is_file():
                problems.append(f"{folder.name}: no SKILL.md")
                continue
            body = skill_file.read_text(encoding="utf-8", errors="replace")
            fields = parse_frontmatter(body)
            if fields is None:
                problems.append(f"{folder.name}: no frontmatter")
                continue
            name = fields.get("name", "")
            if name != folder.name:
                problems.append(f"{folder.name}: frontmatter name {name!r} differs from the folder")
            if not SKILL_NAME_RE.match(name):
                problems.append(
                    f"{folder.name}: name must be lowercase letters, digits and hyphens, at most 64 characters"
                )
            description = fields.get("description", "")
            if not 1 <= len(description) <= 1024:
                problems.append(
                    f"{folder.name}: description must be 1 to 1024 characters (got {len(description)})"
                )
            if fields.get("license", "") == "":
                problems.append(f"{folder.name}: license missing")
            prose = FRONTMATTER_RE.sub("", body, count=1)
            for reference in sorted(folder.glob("references/*.md")):
                prose += "\n" + reference.read_text(encoding="utf-8", errors="replace")
            cited = set(RULE_ID_RE.findall(prose))  # the prose, not the frontmatter list
            unknown = sorted(cited - known)
            if unknown:
                problems.append(f"{folder.name}: cites unknown rule ids {', '.join(unknown)}")
            if not cited:
                problems.append(f"{folder.name}: cites no registry rule")
            listed_match = re.search(r"\brules:\s*([A-Z0-9 -]+)", fields.get("metadata", ""))
            if listed_match:
                listed = set(listed_match.group(1).split())
                listed_only = sorted((listed & known) - cited)
                if listed_only:
                    problems.append(
                        f"{folder.name}: lists {', '.join(listed_only)} in metadata.rules but never cites them"
                    )
                body_only = sorted(cited - listed)
                if body_only:
                    problems.append(
                        f"{folder.name}: cites {', '.join(body_only)} in the body but not in metadata.rules"
                    )
                unknown_listed = sorted(listed - known)
                if unknown_listed:
                    problems.append(
                        f"{folder.name}: metadata.rules names unknown ids {', '.join(unknown_listed)}"
                    )
            else:
                problems.append(f"{folder.name}: metadata.rules missing")
    for rule in registry.rules(root / "rules" / "registry.json"):
        if names and rule["owner"] not in names:
            problems.append(f"{rule['id']}: owner {rule['owner']} has no skill folder")
    forbidden = load_forbidden(args.forbidden_file, root)
    for path in iter_tree_text(root):
        body = path.read_text(encoding="utf-8", errors="replace")
        for finding in text.attribution_findings(body):
            parts = set(path.relative_to(root).parts)
            if path.name in ("text.py", "registry.json") or parts & {"tests", "evals"}:
                continue
            problems.append(f"{path.relative_to(root)}:{finding.line}: {finding.describe()}")
        for token in forbidden:
            if token and re.search(re.escape(token), body, re.I):
                problems.append(f"{path.relative_to(root)}: forbidden token present")
                break
    for problem in problems:
        print(problem)
    print(f"check-skills: {len(names)} skill(s), {len(problems)} problem(s)")
    return 1 if problems else 0


def load_forbidden(path_value: str | None, root: Path | None = None) -> list[str]:
    """Tokens from AGENTIC_SDLC_FORBIDDEN (comma-separated) and from the named file, or from
    the gitignored list at the repository root when no file is named."""
    tokens: list[str] = []
    env = os.environ.get("AGENTIC_SDLC_FORBIDDEN", "")
    tokens += [t.strip() for t in env.split(",") if t.strip()]
    default = (root or Path(".")) / FORBIDDEN_FILE
    candidates = [Path(path_value)] if path_value else [default]
    for candidate in candidates:
        if candidate.is_file():
            tokens += [
                line.strip()
                for line in candidate.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#")
            ]
    return tokens


def iter_tree_text(root: Path) -> list[Path]:
    """Text files under root, skipping build and cache directories and the forbidden list itself."""
    out: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or SKIP_DIRS & set(path.relative_to(root).parts):
            continue
        if path.name == FORBIDDEN_FILE:
            continue
        if path.suffix.lower() in TEXT_SUFFIXES | {".json", ".yml", ".yaml", ".py", ".toml"}:
            out.append(path)
    return out


# validate ------------------------------------------------------------------------------------


def cmd_validate(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    problems: list[str] = []
    try:
        problems += [
            f"registry: {p}"
            for p in registry.validate(registry.load(root / "rules" / "registry.json"))
        ]
    except (OSError, ValueError) as exc:
        problems.append(f"registry: {exc}")
    config_path = root / config_mod.CONFIG_NAME
    if config_path.is_file():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            problems += [
                f"{config_mod.CONFIG_NAME}: {p}"
                for p in config_mod.from_dict(data, config_path).problems
            ]
        except ValueError as exc:
            problems.append(f"{config_mod.CONFIG_NAME}: {exc}")
    for problem in problems:
        print(problem)
    print(f"validate: {len(problems)} problem(s)")
    return 1 if problems else 0


# coverage ------------------------------------------------------------------------------------


def skill_citations(root: Path) -> dict[str, list[str]]:
    """Rule id to the sorted names of the skills whose SKILL.md cites it."""
    cited: dict[str, set[str]] = {}
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return {}
    for folder in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        skill_file = folder / "SKILL.md"
        if not skill_file.is_file():
            continue
        for rule_id in set(
            RULE_ID_RE.findall(skill_file.read_text(encoding="utf-8", errors="replace"))
        ):
            cited.setdefault(rule_id, set()).add(folder.name)
    return {k: sorted(v) for k, v in cited.items()}


def render_coverage(data: dict, citations: dict[str, list[str]] | None = None) -> str:
    citations = citations or {}
    lines = [
        "# Rule coverage",
        "",
        f"Generated from `rules/registry.json` version {data.get('version')} by `agentic-sdlc coverage`. Do not edit by hand.",
        "",
        "Mechanism: **hook** means the PreToolUse hook decides; **githook** means a native git hook (commit-msg, pre-commit, pre-push) refuses it for every agent and every person; **ci** means the reusable workflow fails the check; **ruleset** means the forge refuses the push; **skill** means text an agent follows and nothing enforces.",
        "",
        "| Id | Rule | Statement | Mechanisms | Hook decision | Owner | Cited by | Since | Status |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for rule in data.get("rules", []):
        statement = rule["statement"].replace("|", "\\|")
        cited_by = ", ".join(citations.get(rule["id"], [])) or "(none)"
        lines.append(
            f"| {rule['id']} | {rule['title']} | {statement} | {', '.join(rule['mechanisms'])} | "
            f"{rule.get('decision', '')} | {rule['owner']} | {cited_by} | {rule['since']} | {rule['status']}"
            f"{' (opt-in)' if rule.get('opt_in') else ''} |"
        )
    totals = {}
    for rule in data.get("rules", []):
        for mechanism in rule["mechanisms"]:
            totals[mechanism] = totals.get(mechanism, 0) + 1
    lines += ["", "| Mechanism | Rules |", "|---|---|"]
    for mechanism in ("hook", "githook", "ci", "ruleset", "skill"):
        lines.append(f"| {mechanism} | {totals.get(mechanism, 0)} |")
    lines.append("")
    return "\n".join(lines)


def cmd_coverage(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    rendered = render_coverage(
        registry.load(root / "rules" / "registry.json"), skill_citations(root)
    )
    target = root / "docs" / "coverage.md"
    if args.check:
        current = target.read_text(encoding="utf-8") if target.is_file() else ""
        if current != rendered:
            print("coverage: docs/coverage.md is stale; run `agentic-sdlc coverage`")
            return 1
        print("coverage: up to date")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8")
    print(f"coverage: wrote {target.relative_to(root)}")
    return 0


# native git hooks ---------------------------------------------------------------------------

HOOK_MARK = "# agentic-sdlc hook"
HOOK_NAMES = ("commit-msg", "pre-commit", "pre-push")
ZERO_SHA = "0" * 40


def cmd_check_commit_msg(args: argparse.Namespace) -> int:
    """commit-msg hook: ATTR-1 and ATTR-2 over the message git is about to record."""
    cfg = config_mod.load(Path(args.config_dir).resolve())
    body = Path(args.message_file).read_text(encoding="utf-8", errors="replace")
    message = "\n".join(line for line in body.splitlines() if not line.startswith("#"))
    findings = text.attribution_findings(message, cfg)
    for finding in findings:
        print(f"agentic-sdlc {finding.describe()}")
    if findings:
        print(
            "agentic-sdlc: the commit message carries tool attribution; the signer is the operator of record (ATTR-1)"
        )
    return 1 if findings else 0


def cmd_check_staged(args: argparse.Namespace) -> int:
    """pre-commit hook: SECRET-1 over the index."""
    where = Path(args.config_dir).resolve()
    cfg = config_mod.load(where)
    if not cfg.scan_staged:
        return 0
    findings = guard.staged_secret_findings(where, cfg)
    for finding in findings:
        print(
            f"agentic-sdlc SECRET-1 {finding.name} at staged line {finding.line} (value withheld)"
        )
    return 1 if findings else 0


def cmd_check_push(args: argparse.Namespace) -> int:
    """pre-push hook: PUSH-1 over the ref lines git passes on stdin."""
    where = Path(args.config_dir).resolve()
    cfg = config_mod.load(where)
    protected = set(cfg.protected_branches)
    problems = 0
    for line in sys.stdin.read().splitlines():
        parts = line.split()
        if len(parts) != 4:
            continue
        _local_ref, local_sha, remote_ref, remote_sha = parts
        branch = remote_ref[len("refs/heads/") :] if remote_ref.startswith("refs/heads/") else None
        if branch is None or branch not in protected:
            continue
        if local_sha == ZERO_SHA:
            print(f"agentic-sdlc PUSH-1: deleting protected branch {branch} is refused")
            problems += 1
            continue
        if remote_sha == ZERO_SHA:
            continue
        ancestor = subprocess.run(
            ["git", "-C", str(where), "merge-base", "--is-ancestor", remote_sha, local_sha],
            capture_output=True,
            check=False,
        )
        if ancestor.returncode != 0:
            print(
                f"agentic-sdlc PUSH-1: push to {branch} is not a fast-forward of {remote_sha[:7]}; a protected branch moves by merged pull request"
            )
            problems += 1
    return 1 if problems else 0


def installed_package_dir(git_dir: Path) -> Path:
    """Where `hooks install` copies this package so the hooks outlive any cache the CLI ran from."""
    return git_dir / "agentic-sdlc" / "agentic_sdlc"


def hook_script(name: str, cli: Path) -> str:
    call = f'python3 "{cli}"'
    if name == "commit-msg":
        body = f'{call} check-commit-msg "$1" --config-dir "$(git rev-parse --show-toplevel)"'
    elif name == "pre-commit":
        body = f'{call} check-staged --config-dir "$(git rev-parse --show-toplevel)"'
    else:
        body = f'{call} check-push "$@" --config-dir "$(git rev-parse --show-toplevel)"'
    return (
        "#!/bin/sh\n"
        f"{HOOK_MARK}: {name}, written by `agentic-sdlc hooks install`; remove with `agentic-sdlc hooks uninstall`\n"
        f'if [ ! -f "{cli}" ]; then echo "agentic-sdlc: {cli} is missing; reinstall the hooks or remove this file" >&2; exit 1; fi\n'
        f"{body}\n"
    )


def _git_path(repo: Path, what: str) -> Path | None:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--git-path", what],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    path = Path(result.stdout.strip())
    return (path if path.is_absolute() else repo / path).resolve()


def hooks_dir(repo: Path) -> Path | None:
    return _git_path(repo, "hooks")


def cmd_hooks(args: argparse.Namespace) -> int:
    repo = Path(args.dir).resolve()
    target = hooks_dir(repo)
    common = config_mod.git_common_dir(repo)
    if target is None or common is None:
        print(f"hooks: {repo} is not a git repository")
        return 1
    package_copy = installed_package_dir(common)
    cli = package_copy / "cli.py"
    if args.action == "status":
        for name in HOOK_NAMES:
            path = target / name
            state = "absent"
            if path.is_file():
                state = (
                    "ours"
                    if HOOK_MARK in path.read_text(encoding="utf-8", errors="replace")
                    else "foreign"
                )
            print(f"{name}: {state}")
        print(f"package copy: {'present' if cli.is_file() else 'absent'} ({package_copy})")
        return 0
    if args.action == "uninstall":
        for name in HOOK_NAMES:
            path = target / name
            if path.is_file() and HOOK_MARK in path.read_text(encoding="utf-8", errors="replace"):
                path.unlink()
                print(f"removed {path}")
            elif path.is_file():
                print(f"kept {path}: not written by agentic-sdlc")
        if package_copy.parent.is_dir():
            shutil.rmtree(package_copy.parent)
            print(f"removed {package_copy.parent}")
        return 0
    target.mkdir(parents=True, exist_ok=True)
    for name in HOOK_NAMES:
        path = target / name
        ours = path.is_file() and HOOK_MARK in path.read_text(encoding="utf-8", errors="replace")
        if path.is_file() and not ours and not args.force:
            print(
                f"hooks: {path} exists and was not written by agentic-sdlc; pass --force to replace it, or chain it yourself"
            )
            return 1
    source = Path(__file__).resolve().parent
    if package_copy.exists():
        shutil.rmtree(package_copy)
    shutil.copytree(source, package_copy, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    print(f"copied the package to {package_copy}")
    for name in HOOK_NAMES:
        path = target / name
        path.write_text(hook_script(name, cli), encoding="utf-8")
        path.chmod(0o755)
        print(f"wrote {path}")
    return 0


# log, check-mr, bench ---------------------------------------------------------------------


def cmd_log(args: argparse.Namespace) -> int:
    repo = Path(args.dir).resolve()
    cfg = config_mod.load(repo)
    path = record.record_path(cfg, repo)
    if path is None or not path.is_file():
        print(
            "log: no decisions recorded here; set record.decisions in .agentic-sdlc.json "
            "or AGENTIC_SDLC_RECORD=1"
        )
        return 0
    entries = record.read(path, 0 if args.summary else args.last)
    if args.summary:
        return print_log_summary(entries)
    for entry in entries:
        shadow = " (shadow)" if entry.get("shadow") else ""
        rules = ", ".join(entry.get("rules", [])) or "-"
        print(
            f"{entry.get('ts', '?')}  {entry.get('event', '?'):<11} "
            f"{entry.get('decision', '?'):<5}{shadow}  {rules}  {entry.get('ms', '?')} ms  "
            f"{entry.get('command_sha256', '')}"
        )
    return 0


def print_log_summary(entries: list[dict]) -> int:
    """The whole record as counts: by decision first, then per rule, then the top kinds."""
    if not entries:
        print("log: the record is empty")
        return 0
    decisions = Counter(e.get("decision", "?") for e in entries)
    headline = ", ".join(f"{decisions[d]} {d}" for d in ("allow", "ask", "deny") if decisions[d])
    print(f"{len(entries)} decisions: {headline}")
    per_rule: dict[str, Counter] = {}
    for entry in entries:
        for rule in entry.get("rules", []):
            per_rule.setdefault(rule, Counter())[entry.get("decision", "?")] += 1
    for rule in sorted(per_rule):
        counts = per_rule[rule]
        detail = ", ".join(f"{counts[d]} {d}" for d in ("allow", "ask", "deny") if counts[d])
        print(f"  {rule:<10} {detail}")
    kinds = Counter(kind for entry in entries for kind in entry.get("kinds", []))
    if kinds:
        print("top kinds: " + ", ".join(f"{kind} {n}" for kind, n in kinds.most_common(10)))
    days = [e.get("ts", "")[:10] for e in entries if e.get("ts")]
    if days:
        print(f"from {min(days)} to {max(days)}")
    return 0


def cmd_check_mr(args: argparse.Namespace) -> int:
    """GitLab merge request check from the predefined CI variables and the branch commits."""
    cfg = config_mod.load(Path(args.config_dir).resolve())
    if args.strict:
        cfg.attribution_mode = "strict"
    title = os.environ.get("CI_MERGE_REQUEST_TITLE", "")
    body = os.environ.get("CI_MERGE_REQUEST_DESCRIPTION", "")
    base = os.environ.get("CI_MERGE_REQUEST_DIFF_BASE_SHA", "")
    commits: list[tuple[str, str]] = []
    if base:
        result = subprocess.run(
            ["git", "-C", args.config_dir, "log", "--format=%H%x1f%B%x1e", f"{base}..HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            for block in result.stdout.split("\x1e"):
                if "\x1f" in block:
                    sha, message = block.strip("\n").split("\x1f", 1)
                    commits.append((f"commit {sha[:7]}", message))
        else:
            print(f"WARNING could not list commits: {result.stderr.strip()[:200]}")
    problems = scan_change_texts(
        [("title", title), ("description", body), *commits],
        cfg,
        args.require_signoff,
        plain_report,
    )
    print(f"check-mr: {len(commits)} commit(s), {problems} problem(s)")
    return 1 if problems else 0


BENCH_COMMANDS = (
    "git status",
    "git add -A",
    'git commit -m "Fix the parser"',
    "sh -c 'git push --force origin main'",
    'gh pr merge 12 --squash --body "done"',
)


def cmd_bench(args: argparse.Namespace) -> int:
    cwd = Path(args.cwd).resolve()
    cfg = config_mod.from_dict({"secrets": {"scanner": "none"}})
    for command in BENCH_COMMANDS:
        samples = []
        for _ in range(args.iterations):
            start = time.perf_counter()
            guard.decide(command, cwd, cfg)
            samples.append((time.perf_counter() - start) * 1000)
        print(f"{statistics.median(samples):7.2f} ms median  {max(samples):7.2f} ms max  {command}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
