"""Command-line entry points used by CI, by the repository's own gate and by hand.

agentic-sdlc guard 'git add -A'           decide as the hook would
agentic-sdlc check-text [--strict]        attribution findings over stdin or files
agentic-sdlc check-pr --event $GITHUB_EVENT_PATH
agentic-sdlc lint-voice README.md docs    the mechanical plain-voice rules
agentic-sdlc check-skills                 skill frontmatter, rule citations, attribution, forbidden tokens
agentic-sdlc validate                     the registry and the repository config
agentic-sdlc coverage [--check]           docs/coverage.md from the registry
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent
if __name__ == "__main__" and str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))

from agentic_sdlc import (  # noqa: E402
    __version__,  # noqa: E402
    guard,
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
    problems = 0
    for label, content in [("title", title), ("body", body), *commits]:
        for finding in text.attribution_findings(content, cfg):
            problems += 1
            annotate("error", finding.rule, f"{label}: {finding.name}: {finding.excerpt}")
        if (
            args.require_signoff
            and label.startswith("commit")
            and not re.search(r"^Signed-off-by: .+", content, re.M)
        ):
            problems += 1
            annotate("error", "SIGNOFF", f"{label}: no Signed-off-by trailer")
    if cfg.problems:
        annotate("warning", "CONFIG", "; ".join(cfg.problems))
    print(f"check-pr: {len(commits)} commit(s), {problems} problem(s)")
    return 1 if problems else 0


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
            cited = set(RULE_ID_RE.findall(body))
            unknown = sorted(cited - known)
            if unknown:
                problems.append(f"{folder.name}: cites unknown rule ids {', '.join(unknown)}")
            if not cited:
                problems.append(f"{folder.name}: cites no registry rule")
    for rule in registry.rules(root / "rules" / "registry.json"):
        if names and rule["owner"] not in names:
            problems.append(f"{rule['id']}: owner {rule['owner']} has no skill folder")
    forbidden = load_forbidden(args.forbidden_file)
    for path in iter_tree_text(root):
        body = path.read_text(encoding="utf-8", errors="replace")
        for finding in text.attribution_findings(body):
            if path.name in ("text.py", "registry.json") or path.parent.name == "tests":
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


def load_forbidden(path_value: str | None) -> list[str]:
    tokens: list[str] = []
    env = os.environ.get("AGENTIC_SDLC_FORBIDDEN", "")
    tokens += [t.strip() for t in env.split(",") if t.strip()]
    candidates = [Path(path_value)] if path_value else [Path(".agentic-sdlc-forbidden.txt")]
    for candidate in candidates:
        if candidate.is_file():
            tokens += [
                line.strip()
                for line in candidate.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#")
            ]
    return tokens


def iter_tree_text(root: Path) -> list[Path]:
    out: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or SKIP_DIRS & set(path.relative_to(root).parts):
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


def render_coverage(data: dict) -> str:
    lines = [
        "# Rule coverage",
        "",
        f"Generated from `rules/registry.json` version {data.get('version')} by `agentic-sdlc coverage`. Do not edit by hand.",
        "",
        "Mechanism: **hook** means the PreToolUse hook decides; **ci** means the reusable workflow fails the check; **ruleset** means the forge refuses the push; **skill** means text an agent follows and nothing enforces.",
        "",
        "| Id | Rule | Statement | Mechanisms | Hook decision | Owner | Since | Status |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for rule in data.get("rules", []):
        statement = rule["statement"].replace("|", "\\|")
        lines.append(
            f"| {rule['id']} | {rule['title']} | {statement} | {', '.join(rule['mechanisms'])} | "
            f"{rule.get('decision', '')} | {rule['owner']} | {rule['since']} | {rule['status']}"
            f"{' (opt-in)' if rule.get('opt_in') else ''} |"
        )
    totals = {}
    for rule in data.get("rules", []):
        for mechanism in rule["mechanisms"]:
            totals[mechanism] = totals.get(mechanism, 0) + 1
    lines += ["", "| Mechanism | Rules |", "|---|---|"]
    for mechanism in ("hook", "ci", "ruleset", "skill"):
        lines.append(f"| {mechanism} | {totals.get(mechanism, 0)} |")
    lines.append("")
    return "\n".join(lines)


def cmd_coverage(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    rendered = render_coverage(registry.load(root / "rules" / "registry.json"))
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


if __name__ == "__main__":
    sys.exit(main())
