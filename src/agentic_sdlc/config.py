"""Per-repository configuration from ``.agentic-sdlc.json``.

Every key has a default. The file is optional. Unknown keys are reported, never fatal: a
hook that refuses to run because of a typo in its own config would block every command.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONFIG_NAME = ".agentic-sdlc.json"

# Names that identify a tool when they appear inside a trailer, a footer or a sign-off.
# Wide on purpose: in that position a match is unambiguous.
TRAILER_VENDORS = [
    "claude",
    "claude code",
    "claude-code",
    "anthropic",
    "copilot",
    "chatgpt",
    "openai",
    "gpt",
    "gemini",
    "cursor",
    "codex",
    "devin",
    "aider",
    "windsurf",
    "cline",
    "kimi",
    "qwen",
    "deepseek",
    "mistral",
    "llama",
    "grok",
    "amp",
    "opencode",
    "jules",
    "antigravity",
    "ai assistant",
]

# Names a strict repository refuses anywhere in change text. Narrow on purpose: "cursor",
# "amp" or "llama" are ordinary words in a commit message about code.
STRICT_VENDORS = [
    "claude",
    "claude code",
    "claude-code",
    "anthropic",
    "copilot",
    "chatgpt",
    "openai",
    "gemini",
    "codex",
    "devin",
    "aider",
    "windsurf",
    "cline",
    "kimi",
    "qwen",
    "deepseek",
]

VENDOR_EMAIL_DOMAINS = [
    "anthropic.com",
    "cursor.com",
    "cursor.sh",
    "openai.com",
    "devin.ai",
    "cognition.ai",
    "aider.chat",
    "codeium.com",
    "windsurf.com",
    "sourcegraph.com",
    "ampcode.com",
]


@dataclass
class Config:
    protected_branches: list[str] = field(default_factory=lambda: ["main", "master"])
    attribution_mode: str = "patterns"
    vendors: list[str] = field(default_factory=list)
    confirm_commit: bool = True
    confirm_push: bool = True
    confirm_post: bool = True
    deny_add_all: bool = True
    deny_commit_all: bool = True
    scan_staged: bool = True
    use_gitleaks: bool = True
    extra_secret_patterns: list[str] = field(default_factory=list)
    extra_posting_commands: list[str] = field(default_factory=list)
    source: Path | None = None
    problems: list[str] = field(default_factory=list)

    @property
    def strict(self) -> bool:
        return self.attribution_mode == "strict"

    @property
    def trailer_vendors(self) -> list[str]:
        return _merge(TRAILER_VENDORS, self.vendors)

    @property
    def strict_vendors(self) -> list[str]:
        return _merge(STRICT_VENDORS, self.vendors)


def _merge(base: list[str], extra: list[str]) -> list[str]:
    out = list(base)
    for item in extra:
        low = item.strip().lower()
        if low and low not in out:
            out.append(low)
    return out


def from_dict(data: dict[str, Any], source: Path | None = None) -> Config:
    """Build a Config from parsed JSON, collecting problems instead of raising."""
    cfg = Config(source=source)
    problems = cfg.problems
    known_top = {
        "$schema",
        "version",
        "protected_branches",
        "attribution",
        "confirm",
        "stage",
        "secrets",
        "posting",
    }
    for key in data:
        if key not in known_top:
            problems.append(f"unknown key {key}")
    version = data.get("version", 1)
    if version != 1:
        problems.append(f"unsupported version {version!r}; expected 1")

    branches = data.get("protected_branches")
    if branches is not None:
        if _is_str_list(branches):
            cfg.protected_branches = [b.strip() for b in branches if b.strip()]
        else:
            problems.append("protected_branches must be an array of strings")

    attribution = data.get("attribution") or {}
    if isinstance(attribution, dict):
        mode = attribution.get("mode", "patterns")
        if mode in ("patterns", "strict"):
            cfg.attribution_mode = mode
        else:
            problems.append("attribution.mode must be patterns or strict")
        vendors = attribution.get("vendors")
        if vendors is not None:
            if _is_str_list(vendors):
                cfg.vendors = [v.lower() for v in vendors]
            else:
                problems.append("attribution.vendors must be an array of strings")
    else:
        problems.append("attribution must be an object")

    confirm = data.get("confirm") or {}
    if isinstance(confirm, dict):
        cfg.confirm_commit = _flag(confirm, "commit", True, problems, "confirm")
        cfg.confirm_push = _flag(confirm, "push", True, problems, "confirm")
        cfg.confirm_post = _flag(confirm, "post", True, problems, "confirm")
    else:
        problems.append("confirm must be an object")

    stage = data.get("stage") or {}
    if isinstance(stage, dict):
        cfg.deny_add_all = _flag(stage, "deny_add_all", True, problems, "stage")
        cfg.deny_commit_all = _flag(stage, "deny_commit_all", True, problems, "stage")
    else:
        problems.append("stage must be an object")

    secrets = data.get("secrets") or {}
    if isinstance(secrets, dict):
        cfg.scan_staged = _flag(secrets, "scan_staged", True, problems, "secrets")
        cfg.use_gitleaks = _flag(secrets, "use_gitleaks", True, problems, "secrets")
        extra = secrets.get("extra_patterns", [])
        if _is_str_list(extra):
            cfg.extra_secret_patterns = list(extra)
        else:
            problems.append("secrets.extra_patterns must be an array of strings")
    else:
        problems.append("secrets must be an object")

    posting = data.get("posting") or {}
    if isinstance(posting, dict):
        extra = posting.get("extra_commands", [])
        if _is_str_list(extra):
            cfg.extra_posting_commands = list(extra)
        else:
            problems.append("posting.extra_commands must be an array of strings")
    else:
        problems.append("posting must be an object")
    return cfg


def _flag(obj: dict[str, Any], key: str, default: bool, problems: list[str], section: str) -> bool:
    value = obj.get(key, default)
    if isinstance(value, bool):
        return value
    problems.append(f"{section}.{key} must be true or false")
    return default


def _is_str_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def find_config_file(cwd: Path) -> Path | None:
    """The nearest ``.agentic-sdlc.json`` from ``cwd`` up to the git top level, or up to the
    filesystem root when ``cwd`` is not inside a repository."""
    top = git_toplevel(cwd)
    current = cwd.resolve()
    stop = top.resolve() if top else None
    while True:
        candidate = current / CONFIG_NAME
        if candidate.is_file():
            return candidate
        if stop is not None and current == stop:
            return None
        if current.parent == current:
            return None
        current = current.parent


def git_toplevel(cwd: Path) -> Path | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    path = out.stdout.strip()
    return Path(path) if path else None


def load(cwd: Path) -> Config:
    """Config for a working directory: the nearest file, or the defaults."""
    path = find_config_file(cwd)
    if path is None:
        return Config()
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        cfg = Config(source=path)
        cfg.problems.append(f"{path.name} unreadable: {exc}")
        return cfg
    if not isinstance(data, dict):
        cfg = Config(source=path)
        cfg.problems.append(f"{path.name} must hold a JSON object")
        return cfg
    return from_dict(data, path)
