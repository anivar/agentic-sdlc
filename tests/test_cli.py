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
        json.dumps({"secrets": {"scanner": "none"}}), encoding="utf-8"
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


def make_repo_tree(
    tmp_path: Path, skill_body: str, folder: str = "thin-slices", references: dict | None = None
) -> Path:
    root = tmp_path / "tree"
    (root / "rules").mkdir(parents=True)
    (root / "schemas").mkdir()
    shutil.copy(ROOT / "rules" / "registry.json", root / "rules" / "registry.json")
    skill = root / "skills" / folder
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(skill_body, encoding="utf-8")
    for name, body in (references or {}).items():
        (skill / "references").mkdir(exist_ok=True)
        (skill / "references" / name).write_text(body, encoding="utf-8")
    return root


def skill_text(
    frontmatter_extra: str = "", body: str = "STAGE-1 applies.\n", name: str = "thin-slices"
) -> str:
    return (
        f"---\nname: {name}\ndescription: ok\nlicense: MIT\n{frontmatter_extra}"
        f"metadata:\n  rules: STAGE-1\n---\n\n{body}"
    )


def check_skills_output(root: Path, capsys) -> str:
    run("check-skills", "--root", str(root))
    return capsys.readouterr().out


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


def test_check_skills_reads_the_root_list_and_never_flags_it(tmp_path: Path, capsys):
    good = "---\nname: thin-slices\ndescription: ok\nlicense: MIT\n---\n\nSTAGE-1 applies. Mentions Blorptown here.\n"
    root = make_repo_tree(tmp_path, good)
    (root / ".agentic-sdlc-forbidden.txt").write_text("# names\nblorptown\n", encoding="utf-8")
    code = run("check-skills", "--root", str(root))
    out = capsys.readouterr().out
    assert code == 1
    assert "SKILL.md: forbidden token present" in out
    assert ".agentic-sdlc-forbidden.txt" not in out


def test_check_skills_requires_listed_ids_to_be_cited(tmp_path: Path, capsys):
    listed_only = (
        "---\nname: thin-slices\ndescription: ok\nlicense: MIT\nmetadata:\n  rules: STAGE-1 ASK-2\n---\n\n"
        "STAGE-1 applies.\n"
    )
    root = make_repo_tree(tmp_path, listed_only)
    code = run("check-skills", "--root", str(root))
    out = capsys.readouterr().out
    assert code == 1 and "lists ASK-2 in metadata.rules but never cites" in out


def test_check_skills_name_has_single_hyphens_and_none_at_either_end(tmp_path: Path, capsys):
    for i, bad in enumerate(("thin--slices", "thin-slices-")):
        root = make_repo_tree(tmp_path / str(i), skill_text(name=bad), folder=bad)
        assert "name must be lowercase letters, digits and single hyphens" in check_skills_output(
            root, capsys
        )
    root = make_repo_tree(tmp_path / "ok", skill_text())
    assert "single hyphens" not in check_skills_output(root, capsys)


def test_check_skills_refuses_frontmatter_keys_outside_the_specification(tmp_path: Path, capsys):
    root = make_repo_tree(tmp_path, skill_text("version: 1.0.0\n"))
    assert (
        "frontmatter key 'version' is not in the Agent Skills specification"
        in check_skills_output(root, capsys)
    )
    plugin_keys = 'argument-hint: "[path]"\ndisable-model-invocation: true\nallowed-tools: Bash(git:*) Read\ncompatibility: Any git repository\n'
    root = make_repo_tree(tmp_path / "ok", skill_text(plugin_keys))
    assert "not in the Agent Skills specification" not in check_skills_output(root, capsys)


def test_check_skills_caps_compatibility_at_500_characters(tmp_path: Path, capsys):
    root = make_repo_tree(tmp_path, skill_text("compatibility: " + "x" * 501 + "\n"))
    assert "compatibility must be 1 to 500 characters (got 501)" in check_skills_output(
        root, capsys
    )
    root = make_repo_tree(tmp_path / "ok", skill_text("compatibility: " + "x" * 500 + "\n"))
    assert "compatibility must be" not in check_skills_output(root, capsys)


def test_check_skills_metadata_maps_strings_to_strings(tmp_path: Path, capsys):
    body = (
        "---\nname: thin-slices\ndescription: ok\nlicense: MIT\nmetadata:\n  rules: STAGE-1\n"
        "  version: 1.0\n  released: 2026-11-22\n  stable: true\n  tags:\n    - a\n"
        "  flow: [a, b]\n  empty:\n"
        '  quoted: "1.0"\n  semver: 1.2.6\n---\n\nSTAGE-1 applies.\n'
    )
    out = check_skills_output(make_repo_tree(tmp_path, body), capsys)
    for key in ("version", "released", "stable", "empty"):
        assert f"metadata.{key} is not a string" in out
    for key in ("tags", "flow"):
        assert f"metadata.{key} holds a nested value" in out
    assert (
        "metadata.quoted" not in out
        and "metadata.semver" not in out
        and "metadata.rules" not in out
    )


def test_check_skills_keeps_skill_md_under_500_lines(tmp_path: Path, capsys):
    root = make_repo_tree(tmp_path, skill_text(body="STAGE-1 applies.\n" + "line\n" * 491))
    assert "SKILL.md has 500 lines" in check_skills_output(root, capsys)
    root = make_repo_tree(tmp_path / "ok", skill_text(body="STAGE-1 applies.\n" + "line\n" * 490))
    assert "SKILL.md has" not in check_skills_output(root, capsys)


def test_check_skills_long_reference_opens_with_a_contents_list(tmp_path: Path, capsys):
    long_body = "# Guide\n\n" + "".join(f"## Part {i}\n\ntext\n\n" for i in range(30))
    root = make_repo_tree(tmp_path, skill_text(), references={"guide.md": long_body})
    assert "references/guide.md has 122 lines and no contents list" in check_skills_output(
        root, capsys
    )
    listed = "# Guide\n\n## Contents\n\n- Part 0\n\n" + long_body[len("# Guide\n\n") :]
    root = make_repo_tree(tmp_path / "ok", skill_text(), references={"guide.md": listed})
    assert "no contents list" not in check_skills_output(root, capsys)


def test_check_skills_contents_list_starts_after_100_lines(tmp_path: Path, capsys):
    root = make_repo_tree(tmp_path, skill_text(), references={"guide.md": "line\n" * 101})
    assert "references/guide.md has 101 lines and no contents list" in check_skills_output(
        root, capsys
    )
    root = make_repo_tree(tmp_path / "ok", skill_text(), references={"guide.md": "line\n" * 100})
    assert "no contents list" not in check_skills_output(root, capsys)


def test_check_skills_contents_heading_inside_a_code_block_does_not_count(tmp_path: Path, capsys):
    quoted = "```markdown\n## Contents\n```\n" + "line\n" * 101
    root = make_repo_tree(tmp_path, skill_text(), references={"guide.md": quoted})
    assert "references/guide.md has 104 lines and no contents list" in check_skills_output(
        root, capsys
    )


def test_check_skills_refuses_a_same_length_fence_nested_in_a_block(tmp_path: Path, capsys):
    nested = "STAGE-1 applies.\n\n```markdown\n# Title\n\n```bash\nnpm install\n```\n```\n"
    root = make_repo_tree(tmp_path, skill_text(body=nested))
    out = check_skills_output(root, capsys)
    assert "SKILL.md:14: a fence with a language sits inside the block opened at line 11" in out
    widened = "STAGE-1 applies.\n\n````markdown\n# Title\n\n```bash\nnpm install\n```\n````\n"
    root = make_repo_tree(tmp_path / "ok", skill_text(body=widened))
    assert "sits inside the block" not in check_skills_output(root, capsys)


def test_check_skills_looks_for_nested_fences_in_every_markdown_file(tmp_path: Path, capsys):
    nested = "# Guide\n\n```markdown\n```bash\nls\n```\n```\n"
    root = make_repo_tree(tmp_path, skill_text(), references={"guide.md": nested})
    out = check_skills_output(root, capsys)
    assert (
        "references/guide.md:4: a fence with a language sits inside the block opened at line 3"
        in out
    )


def test_config_scanner_key_and_the_retired_gitleaks_alias():
    from agentic_sdlc import config as config_mod

    assert config_mod.from_dict({}).scanner == "trufflehog"
    assert config_mod.from_dict({"secrets": {"scanner": "none"}}).scanner == "none"
    bad = config_mod.from_dict({"secrets": {"scanner": "gitleaks"}})
    assert bad.scanner == "trufflehog" and any("scanner" in p for p in bad.problems)
    legacy = config_mod.from_dict({"secrets": {"use_gitleaks": False}})
    assert legacy.scanner == "none" and any("use_gitleaks" in p for p in legacy.problems)
    assert config_mod.from_dict({"secrets": {"use_gitleaks": True}}).scanner == "trufflehog"


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


def test_log_summary_aggregates_the_record(tmp_path: Path, capsys):
    entries = [
        {
            "ts": "2026-10-01T10:00:00+00:00",
            "event": "PreToolUse",
            "decision": "allow",
            "rules": [],
            "kinds": ["other"],
        },
        {
            "ts": "2026-10-02T10:00:00+00:00",
            "event": "PreToolUse",
            "decision": "ask",
            "rules": ["ASK-1"],
            "kinds": ["git-commit"],
        },
        {
            "ts": "2026-10-03T10:00:00+00:00",
            "event": "PreToolUse",
            "decision": "deny",
            "rules": ["STAGE-1"],
            "kinds": ["git-add"],
        },
        {
            "ts": "2026-10-03T11:00:00+00:00",
            "event": "PreToolUse",
            "decision": "ask",
            "rules": ["ASK-1"],
            "kinds": ["git-commit"],
        },
    ]
    (tmp_path / "decisions.jsonl").write_text(
        "\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8"
    )
    (tmp_path / ".agentic-sdlc.json").write_text(
        json.dumps({"record": {"path": "decisions.jsonl"}}), encoding="utf-8"
    )
    assert run("log", "--dir", str(tmp_path), "--summary") == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "4 decisions: 1 allow, 2 ask, 1 deny"
    assert "ASK-1" in out and "2 ask" in out and "STAGE-1" in out
    assert "top kinds: git-commit 2" in out
    assert "from 2026-10-01 to 2026-10-03" in out
    # Without --summary the entries print one per line.
    assert run("log", "--dir", str(tmp_path), "--last", "1") == 0
    assert len(capsys.readouterr().out.strip().splitlines()) == 1
