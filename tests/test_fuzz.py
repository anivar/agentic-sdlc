"""A seeded grammar of shell-ish strings over the parser and the guard: parse never raises,
and decide is deterministic (two calls over the same string agree)."""

from __future__ import annotations

import random

from agentic_sdlc import command as command_mod
from agentic_sdlc import config as config_mod
from agentic_sdlc import guard

NO_SCANNER = config_mod.from_dict({"secrets": {"scanner": "none"}})

PROGRAMS = [
    "git",
    "gh",
    "glab",
    "ls",
    "echo",
    "cat",
    "python3",
    "sh",
    "bash",
    "eval",
    "xargs",
    "env",
    "sudo",
    "curl",
    "make",
    "cd",
]
GIT_VERBS = ["status", "add", "commit", "push", "log", "diff", "tag", "config", "frobnicate"]
FLAGS = [
    "-A",
    "-m",
    "--all",
    "--force",
    "--no-verify",
    "--dry-run",
    "-n",
    "-c",
    ">",
    ">>",
    "2>",
    ">&",
    "<&",
]
WORDS = [
    "x",
    "origin",
    "main",
    "'quoted string'",
    '"double quoted"',
    "$(cat f)",
    "`id`",
    "<<EOF",
    "/tmp/a",
    "*.py",
    "-",
]
OPERATORS = ["|", "&&", ";", "||"]
SAMPLES = 500


def _command(rng: random.Random) -> str:
    parts = []
    for _ in range(rng.randint(1, 4)):
        program = rng.choice(PROGRAMS)
        args = [program]
        if program == "git":
            args.append(rng.choice(GIT_VERBS))
        if program in ("sh", "bash"):
            args += ["-c", "'git push'"]
        args += [rng.choice(FLAGS + WORDS) for _ in range(rng.randint(0, 4))]
        parts.append(" ".join(args))
    joined = parts[0]
    for part in parts[1:]:
        joined += f" {rng.choice(OPERATORS)} {part}"
    return joined


def test_parse_never_raises_and_decide_is_deterministic():
    rng = random.Random(42)
    for _ in range(SAMPLES):
        raw = _command(rng)
        parsed = command_mod.parse(raw)
        assert isinstance(parsed.commands, list), raw
        first = guard.decide(raw, None, NO_SCANNER)
        second = guard.decide(raw, None, NO_SCANNER)
        assert (first.permission, first.rules, first.reasons) == (
            second.permission,
            second.rules,
            second.reasons,
        ), raw
