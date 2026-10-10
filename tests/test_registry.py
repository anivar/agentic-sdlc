from __future__ import annotations

import json
from pathlib import Path

from agentic_sdlc import registry

ROOT = Path(__file__).resolve().parent.parent


def test_registry_is_valid():
    data = registry.load()
    assert registry.validate(data) == []


def test_hook_rules_carry_a_decision():
    for rule in registry.rules():
        if "hook" in rule["mechanisms"]:
            assert rule.get("decision") in ("deny", "ask"), rule["id"]


def test_owners_are_published_skills_once_skills_exist():
    skills_dir = ROOT / "skills"
    names = {p.name for p in skills_dir.iterdir() if p.is_dir()} if skills_dir.is_dir() else set()
    if not names:
        return
    for rule in registry.rules():
        assert rule["owner"] in names, f"{rule['id']} owner {rule['owner']} has no skill folder"


def test_validate_reports_defects():
    bad = {
        "version": "1.0",
        "rules": [
            {
                "id": "x-1",
                "title": "no",
                "statement": "short",
                "mechanisms": ["hook"],
                "owner": "Bad",
                "since": "1",
                "status": "gone",
            },
            {
                "id": "ATTR-1",
                "title": "dup",
                "statement": "A sentence that MUST be long enough here.",
                "mechanisms": ["skill"],
                "owner": "ok",
                "since": "1.0.0",
                "status": "active",
            },
            {
                "id": "ATTR-1",
                "title": "dup",
                "statement": "A sentence that MUST be long enough here.",
                "mechanisms": ["skill"],
                "owner": "ok",
                "since": "1.0.0",
                "status": "active",
                "extra": 1,
            },
        ],
    }
    problems = registry.validate(bad)
    joined = "\n".join(problems)
    for needle in (
        "version",
        "id must match",
        "title",
        "statement too short",
        "needs decision",
        "owner",
        "since",
        "status",
        "duplicate id",
        "unknown key",
    ):
        assert needle in joined, needle


def test_schema_and_registry_agree_on_mechanisms():
    schema = json.loads((ROOT / "schemas" / "registry.schema.json").read_text(encoding="utf-8"))
    allowed = set(
        schema["properties"]["rules"]["items"]["properties"]["mechanisms"]["items"]["enum"]
    )
    assert allowed == registry.MECHANISMS
