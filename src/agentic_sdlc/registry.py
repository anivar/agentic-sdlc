"""The rule registry: load, validate and look up rules by id.

The registry is JSON so the hook needs nothing outside the standard library. The
validation here mirrors ``schemas/registry.schema.json`` closely enough to fail CI on the
same defects without a JSON Schema dependency.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY_PATH = ROOT / "rules" / "registry.json"

ID_RE = re.compile(r"^[A-Z]+-[0-9]+$")
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
OWNER_RE = re.compile(r"^[a-z][a-z0-9-]*$")
MECHANISMS = {"hook", "ci", "ruleset", "skill"}
DECISIONS = {"deny", "ask"}
STATUSES = {"active", "deprecated"}
REQUIRED = ("id", "title", "statement", "mechanisms", "owner", "since", "status")
OPTIONAL = ("decision", "opt_in", "replaced_by", "notes")


def load(path: Path | None = None) -> dict[str, Any]:
    """Read the registry file. Raises ``FileNotFoundError`` or ``ValueError`` on a bad file."""
    source = path or REGISTRY_PATH
    with open(source, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("registry root must be an object")
    return data


def rules(path: Path | None = None) -> list[dict[str, Any]]:
    return list(load(path).get("rules", []))


def by_id(path: Path | None = None) -> dict[str, dict[str, Any]]:
    return {rule["id"]: rule for rule in rules(path)}


def validate(data: dict[str, Any]) -> list[str]:
    """Return every defect found, as human-readable strings. An empty list means valid."""
    problems: list[str] = []
    version = data.get("version")
    if not isinstance(version, str) or not SEMVER_RE.match(version):
        problems.append("version must be a semver string")
    entries = data.get("rules")
    if not isinstance(entries, list) or not entries:
        return problems + ["rules must be a non-empty array"]
    seen: set[str] = set()
    ids = {r.get("id") for r in entries if isinstance(r, dict)}
    for index, rule in enumerate(entries):
        where = f"rules[{index}]"
        if not isinstance(rule, dict):
            problems.append(f"{where}: not an object")
            continue
        rule_id = rule.get("id", "?")
        where = f"{where} ({rule_id})"
        for key in REQUIRED:
            if key not in rule:
                problems.append(f"{where}: missing {key}")
        for key in rule:
            if key not in REQUIRED and key not in OPTIONAL:
                problems.append(f"{where}: unknown key {key}")
        if not isinstance(rule_id, str) or not ID_RE.match(rule_id):
            problems.append(f"{where}: id must match {ID_RE.pattern}")
        elif rule_id in seen:
            problems.append(f"{where}: duplicate id")
        seen.add(rule_id if isinstance(rule_id, str) else "")
        title = rule.get("title", "")
        if not isinstance(title, str) or not 3 <= len(title) <= 80:
            problems.append(f"{where}: title must be 3 to 80 characters")
        statement = rule.get("statement", "")
        if not isinstance(statement, str) or len(statement) < 20:
            problems.append(f"{where}: statement too short")
        elif not re.search(r"\b(MUST|MUST NOT|SHOULD|SHOULD NOT|MAY)\b", statement):
            problems.append(f"{where}: statement carries no RFC 2119 word")
        mechanisms = rule.get("mechanisms")
        if (
            not isinstance(mechanisms, list)
            or not mechanisms
            or len(set(mechanisms)) != len(mechanisms)
            or any(m not in MECHANISMS for m in mechanisms)
        ):
            problems.append(f"{where}: mechanisms must be a unique subset of {sorted(MECHANISMS)}")
        elif "hook" in mechanisms and rule.get("decision") not in DECISIONS:
            problems.append(f"{where}: a hook rule needs decision deny or ask")
        if "decision" in rule and rule["decision"] not in DECISIONS:
            problems.append(f"{where}: decision must be deny or ask")
        owner = rule.get("owner", "")
        if not isinstance(owner, str) or not OWNER_RE.match(owner):
            problems.append(f"{where}: owner must be a skill name")
        since = rule.get("since", "")
        if not isinstance(since, str) or not SEMVER_RE.match(since):
            problems.append(f"{where}: since must be semver")
        status = rule.get("status")
        if status not in STATUSES:
            problems.append(f"{where}: status must be active or deprecated")
        if status == "deprecated" and "replaced_by" not in rule:
            problems.append(f"{where}: a deprecated rule names its replacement")
        replaced_by = rule.get("replaced_by")
        if replaced_by is not None and replaced_by not in ids:
            problems.append(f"{where}: replaced_by names an unknown rule")
        if "opt_in" in rule and not isinstance(rule["opt_in"], bool):
            problems.append(f"{where}: opt_in must be boolean")
    return problems


def titles(path: Path | None = None) -> dict[str, str]:
    """Rule id to title, with a built-in fallback so the hook can explain itself even when the
    registry file is unreachable (for example a partial plugin install)."""
    try:
        return {rule["id"]: rule["title"] for rule in rules(path)}
    except (OSError, ValueError, KeyError):
        return dict(FALLBACK_TITLES)


FALLBACK_TITLES = {
    "ATTR-1": "No tool attribution in change text",
    "ATTR-2": "Strict mode: no vendor mention in change text",
    "STAGE-1": "Stage by path",
    "PUSH-1": "No force push to a protected branch",
    "PUSH-2": "Moving a tag is confirmed and explained",
    "SECRET-1": "No key-shaped literals",
    "ASK-1": "A commit waits for a go-ahead",
    "ASK-2": "A push waits for a go-ahead",
    "ASK-3": "A post waits for a go-ahead",
}
