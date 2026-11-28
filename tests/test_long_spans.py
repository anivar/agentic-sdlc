"""Long literal spans are tokenized in linear time and to the same tokens shlex gives: the
shield in command.tokenize changes speed, never the tokens or a decision."""

from __future__ import annotations

import json
import random
import shlex
import time
from pathlib import Path

import pytest

from agentic_sdlc import command, guard
from agentic_sdlc import config as config_mod

ROOT = Path(__file__).resolve().parents[1]


def plain_shlex(line: str) -> list[str]:
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError:
        return line.split()


def corpus() -> list[str]:
    registry = json.loads((ROOT / "rules" / "registry.json").read_text(encoding="utf-8"))
    lines = [
        e
        for r in registry["rules"]
        for k in ("allow", "deny", "ask")
        for e in r.get("examples", {}).get(k, [])
    ]
    pick = random.Random(20261125)
    alphabet = "ab $()'\"\\;|&<>=-./\n\t`{}#*"
    lines += [
        "".join(pick.choice(alphabet) for _ in range(pick.randint(0, 40))) for _ in range(4000)
    ]
    return lines


def test_shielding_every_span_gives_the_tokens_shlex_gives(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(command, "LONG_SPAN", 1)  # every literal span is swapped out and back
    mismatches = [line for line in corpus() if command.tokenize(line) != plain_shlex(line)]
    assert mismatches == []


def test_a_megabyte_word_is_tokenized_in_linear_time():
    started = time.perf_counter()
    assert command.tokenize("echo " + "a" * 1_000_000) == ["echo", "a" * 1_000_000]
    body = '{"k": "' + "v " * 500_000 + '"}'
    assert command.tokenize(f"curl -d '{body}' x") == ["curl", "-d", body, "x"]
    assert time.perf_counter() - started < 3


def test_a_gated_command_after_a_long_word_keeps_its_decision():
    started = time.perf_counter()
    cfg = config_mod.from_dict({})
    decision = guard.decide("echo " + "a" * 500_000 + " && git push --force origin main", None, cfg)
    assert decision.permission == guard.decide("git push --force origin main", None, cfg).permission
    assert time.perf_counter() - started < 5
