"""The decision record: one JSON line per hook decision, when a repository turns it on.

The record is the witness for a rollout: with ``record.shadow`` a team sees what the hook
would have decided before it refuses anything. It never stores the command text, only its
hash, so a secret typed into a command cannot end up in the record.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config as config_mod

RECORD_NAME = "decisions.jsonl"


def record_path(cfg: config_mod.Config, cwd: Path | None) -> Path | None:
    if cfg.record_path:
        path = Path(cfg.record_path)
        if not path.is_absolute() and cwd is not None:
            path = cwd / path
        return path
    if cwd is None:
        return None
    common = config_mod.git_common_dir(cwd)
    return None if common is None else common / "agentic-sdlc" / RECORD_NAME


def command_digest(command: str) -> str:
    return hashlib.sha256(command.encode("utf-8", errors="replace")).hexdigest()[:16]


def entry(
    *,
    event: str,
    tool: str,
    decision: str,
    rules: list[str],
    reasons: list[str],
    mode: str,
    command: str,
    kinds: list[str],
    ms: float,
    shadow: bool,
) -> dict[str, Any]:
    return {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "event": event,
        "tool": tool,
        "mode": mode,
        "decision": decision,
        "rules": rules,
        "reasons": reasons,
        "command_sha256": command_digest(command),
        "kinds": kinds,
        "ms": round(ms, 2),
        "shadow": shadow,
    }


def append(cfg: config_mod.Config, cwd: Path | None, line: dict[str, Any]) -> None:
    """Append one entry; a failure to write never fails the hook."""
    path = record_path(cfg, cwd)
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")
    except OSError:
        return


def read(path: Path, last: int = 20) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-last:] if last > 0 else lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out
