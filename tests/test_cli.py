from __future__ import annotations

import json
import shutil
from pathlib import Path

from agentic_sdlc import cli

ROOT = Path(__file__).resolve().parent.parent


def run(*argv: str) -> int:
    return cli.main(list(argv))


def test_guard_summary_and_exit_codes(repo: Path, capsys):
    (repo / ".agentic-sdlc.json").write_text(
        json.dumps({"secrets": {"use_gitleaks": False}}), encoding="utf-8"
    )
    assert run("guard", "git add -A", "--cwd", str(repo)) == 1
    out = capsys.readouterr().out
    assert out.startswith("deny: STAGE-1")
    assert run("guard", "git status", "--cwd", str(repo)) == 0
    assert capsys.readouterr().out.startswith("allow: no rule matched")
    assert run("guard", 'git commit -m "x"', "--cwd", str(repo), "--json") == 0
    assert json.loads(capsys.readouterr().out)["permission"] == "ask"


def test_check_text_files_and_strict(tmp_path: Path, capsys):
    clean = tmp_path / "clean.md"
    clean.write_text("Add Claude Code plugin manifest\n", encoding="utf-8")
    dirty = tmp_path / "dirty.md"
    dirty.write_text(
        "Subject\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n", encoding="utf-8"
    )
    assert run("check-text", str(clean)) == 0
    assert run("check-text", str(dirty)) == 1
    assert "ATTR-1" in capsys.readouterr().out
    assert run("check-text", "--strict", str(clean)) == 1


def test_check_pr_offline(tmp_path: Path, capsys):
    commits = tmp_path / "commits.txt"
    commits.write_text(
        "Fix parser\n\nSigned-off-by: Dev <dev@example.com>\n---\nAdd docs\n\n\U0001f916 Generated with [Claude Code](https://claude.com/claude-code)\n",
        encoding="utf-8",
    )
    code = run(
        "check-pr",
        "--title",
        "Fix",
        "--body",
        "Plain body",
        "--commits-file",
        str(commits),
        "--config-dir",
        str(tmp_path),
    )
    out = capsys.readouterr().out
    assert code == 1 and "ATTR-1" in out and "2 commit(s), 1 problem(s)" in out
    code = run(
        "check-pr",
        "--title",
        "Fix",
        "--body",
        "",
        "--commits-file",
        str(commits),
        "--require-signoff",
        "--config-dir",
        str(tmp_path),
    )
    assert code == 1 and "SIGNOFF" in capsys.readouterr().out


def test_check_pr_reads_event_payload(tmp_path: Path, capsys):
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps(
            {
                "pull_request": {"title": "T", "body": "Made with Cursor", "number": 1},
                "repository": {"full_name": "o/r"},
            }
        ),
        encoding="utf-8",
    )
    empty = tmp_path / "none.txt"
    empty.write_text("", encoding="utf-8")
    code = run(
        "check-pr",
        "--event",
        str(event),
        "--commits-file",
        str(empty),
        "--config-dir",
        str(tmp_path),
    )
    assert code == 1 and "body" in capsys.readouterr().out


def test_lint_voice_levels(tmp_path: Path, capsys):
    doc = tmp_path / "doc.md"
    doc.write_text("Note that this is fine.\nThe result — bad.\n", encoding="utf-8")
    assert run("lint-voice", str(doc), "--fail-on", "fail") == 1
    assert run("lint-voice", str(doc), "--fail-on", "none") == 0
    assert run("lint-voice", str(doc), "--fail-on", "warn") == 1
    clean = tmp_path / "clean.md"
    clean.write_text("Plain sentence.\n", encoding="utf-8")
    assert run("lint-voice", str(clean)) == 0


def make_repo_tree(tmp_path: Path, skill_body: str) -> Path:
    root = tmp_path / "tree"
    (root / "rules").mkdir(parents=True)
    (root / "schemas").mkdir()
    shutil.copy(ROOT / "rules" / "registry.json", root / "rules" / "registry.json")
    skill = root / "skills" / "thin-slices"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(skill_body, encoding="utf-8")
    return root


def test_check_skills_validates_frontmatter_and_citations(tmp_path: Path, capsys):
    good = "---\nname: thin-slices\ndescription: Deliver in reviewable slices.\nlicense: MIT\n---\n\nFollow STAGE-1 and ASK-1.\n"
    root = make_repo_tree(tmp_path, good)
    code = run("check-skills", "--root", str(root))
    out = capsys.readouterr().out
    assert "owner plain-voice has no skill folder" in out
    assert code == 1
    bad = "---\nname: other\ndescription: x\n---\n\nCites NOPE-9.\n"
    root = make_repo_tree(tmp_path / "b", bad)
    code = run("check-skills", "--root", str(root))
    out = capsys.readouterr().out
    assert code == 1
    assert (
        "differs from the folder" in out
        and "license missing" in out
        and "unknown rule ids NOPE-9" in out
    )


def test_check_skills_forbidden_tokens(tmp_path: Path, capsys, monkeypatch):
    good = "---\nname: thin-slices\ndescription: ok\nlicense: MIT\n---\n\nSTAGE-1 applies. Mentions Blorptown here.\n"
    root = make_repo_tree(tmp_path, good)
    monkeypatch.setenv("AGENTIC_SDLC_FORBIDDEN", "blorptown")
    code = run("check-skills", "--root", str(root))
    out = capsys.readouterr().out
    assert code == 1 and "forbidden token present" in out


def test_validate_and_coverage_roundtrip(tmp_path: Path, capsys):
    assert run("validate", "--root", str(ROOT)) == 0
    root = tmp_path / "cov"
    (root / "rules").mkdir(parents=True)
    shutil.copy(ROOT / "rules" / "registry.json", root / "rules" / "registry.json")
    assert run("coverage", "--root", str(root), "--check") == 1
    assert run("coverage", "--root", str(root)) == 0
    assert run("coverage", "--root", str(root), "--check") == 0
    rendered = (root / "docs" / "coverage.md").read_text(encoding="utf-8")
    assert "| ATTR-1 |" in rendered and "| hook |" in rendered


def test_frontmatter_parser_handles_folded_description():
    body = "---\nname: x\ndescription: >\n  First line\n  second line.\nlicense: MIT\n---\n\n# X\n"
    fields = cli.parse_frontmatter(body)
    assert fields == {"name": "x", "description": "First line second line.", "license": "MIT"}
