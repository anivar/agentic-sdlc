#!/usr/bin/env python3
"""Flag write-shaped gh/glab verbs that the tables in ``command.py`` do not know.

Runs each CLI's ``--help`` locally (no network). A verb whose first hyphen segment is
write-shaped (create, delete, set, ...) and that appears in neither the WRITE nor the READ
table means a CLI release added or renamed a write the hook would only catch through the
unrecognized-verb ask. Nouns in ``LOCAL_NOUNS`` change only local state (aliases, CLI
configuration, extensions); the hook deliberately leaves them to that ask and they are
skipped here. A CLI absent from PATH is skipped, so the check runs anywhere.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentic_sdlc import command as command_mod  # noqa: E402

WRITE_SHAPED = {
    "create",
    "edit",
    "delete",
    "close",
    "reopen",
    "merge",
    "comment",
    "review",
    "upload",
    "enable",
    "disable",
    "set",
    "add",
    "remove",
    "archive",
    "rename",
    "transfer",
    "unlock",
    "lock",
    "pin",
    "unpin",
}

# Nouns whose write-shaped verbs touch only local state, so they stay out of the tables
# on purpose.
LOCAL_NOUNS = {
    "gh": {"auth", "alias", "config", "completion", "copilot", "extension", "licenses", "preview"},
    "glab": {"alias", "config"},
}


def _run(*args: str) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout


def _gh_entries(text: str) -> list[str]:
    """Names listed under any ``... COMMANDS`` section, as ``name: description``."""
    out: list[str] = []
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.endswith("COMMANDS") and stripped.upper() == stripped:
            in_section = True
            continue
        if in_section and stripped and not line.startswith("  "):
            in_section = False
            continue
        if in_section:
            match = re.match(r"^  ([a-z][a-z0-9-]*):", line)
            if match:
                out.append(match.group(1))
    return out


def _glab_entries(text: str) -> list[str]:
    """Names listed under the ``COMMANDS`` section, indented four spaces."""
    out: list[str] = []
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "COMMANDS":
            in_section = True
            continue
        if in_section and stripped and not line.startswith("    "):
            in_section = False
            continue
        if in_section:
            match = re.match(r"^    ([a-z][a-z0-9-]*)[\s\[]", line)
            if match:
                out.append(match.group(1))
    return out


def check(
    cli: str,
    entries,
    write: dict[str, set[str]],
    read: set[str],
    read_nouns: set[str],
) -> list[str]:
    """Write-shaped verbs the tables do not know, as ``cli noun verb`` strings."""
    missing: list[str] = []
    for noun in entries(_run(cli, "--help")):
        if noun in LOCAL_NOUNS[cli] or noun in read_nouns:
            continue
        known = write.get(noun, set())
        for verb in entries(_run(cli, noun, "--help")):
            if verb in known or verb in read:
                continue
            if verb.split("-", 1)[0] in WRITE_SHAPED:
                missing.append(f"{cli} {noun} {verb}")
    return missing


def main() -> int:
    missing: list[str] = []
    for cli, entries, write, read, read_nouns in (
        ("gh", _gh_entries, command_mod.GH_WRITE, command_mod.GH_READ, command_mod.GH_READ_NOUNS),
        (
            "glab",
            _glab_entries,
            command_mod.GLAB_WRITE,
            command_mod.GLAB_READ,
            command_mod.GLAB_READ_NOUNS,
        ),
    ):
        if shutil.which(cli) is None:
            print(f"SKIP: {cli} is not on PATH")
            continue
        missing.extend(check(cli, entries, write, read, read_nouns))
    if missing:
        print("write-shaped verbs missing from the tables in src/agentic_sdlc/command.py:")
        for name in missing:
            print(f"  {name}")
        return 1
    print("verb tables: up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
